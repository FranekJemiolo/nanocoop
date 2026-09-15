"""API integration tests for all FastAPI endpoints using httpx AsyncClient."""

import time
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    generate_keypair,
    serialize_for_hashing,
    sign_payload,
)
from app.db.database import get_db, init_db
from app.main import app


@pytest.fixture
async def test_client(tmp_path):
    """Async HTTP test client with isolated SQLite database."""
    test_db_path = str(tmp_path / "test_api.db")
    await init_db(test_db_path)

    import aiosqlite

    async def override_get_db():
        db = await aiosqlite.connect(test_db_path)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check(test_client):
    """Test /health endpoint."""
    res = await test_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_and_query_events(test_client):
    """Test creating an event via POST /api/v1/events and retrieving balance and stats."""
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    payload = {
        "amount": 75.50,
        "currency": "USD",
        "user_public_key": u_pub,
    }
    teller_sig = sign_payload(t_priv, payload)
    user_sig = sign_payload(u_priv, payload)
    signatures = {
        "teller_sig": teller_sig,
        "user_sig": user_sig,
    }

    current_hash = generate_event_hash(
        GENESIS_HASH,
        serialize_for_hashing(payload),
        serialize_for_hashing(signatures),
    )

    event_req = {
        "event_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "event_type": "DEPOSIT_CASH",
        "payload": payload,
        "previous_hash": GENESIS_HASH,
        "signatures": signatures,
        "current_hash": current_hash,
    }

    # Submit event
    res = await test_client.post("/api/v1/events", json=event_req)
    assert res.status_code == 201
    assert res.json()["event_id"] == event_req["event_id"]

    # Query balance
    bal_res = await test_client.get(f"/api/v1/balance/{u_pub}")
    assert bal_res.status_code == 200
    assert bal_res.json()["current_balance"] == 75.50

    # Query events list
    events_res = await test_client.get("/api/v1/events")
    assert events_res.status_code == 200
    data = events_res.json()
    assert data["total_count"] == 1
    assert len(data["events"]) == 1

    # Query stats
    stats_res = await test_client.get("/api/v1/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_balance"] == 75.50
    assert stats["total_events"] == 1
    assert stats["is_chain_valid"] is True

    # Query audit verification
    audit_res = await test_client.get("/api/v1/audit/verify")
    assert audit_res.status_code == 200
    audit = audit_res.json()
    assert audit["is_valid"] is True
    assert audit["total_events"] == 1


@pytest.mark.asyncio
async def test_sms_webhook_idempotency(test_client):
    """Test mobile money SMS webhook and idempotency handling."""
    gateway_priv, gateway_pub = generate_keypair()
    _, u_pub = generate_keypair()

    webhook_payload = {
        "transaction_code": "MPESA_XYZ123",
        "sender_phone": "+254700000000",
        "amount": 20.0,
        "currency": "USD",
        "user_public_key": u_pub,
        "timestamp": int(time.time()),
        "gateway_signature": "00" * 32,  # 64 hex characters
    }

    # First attempt: SUCCESS
    res1 = await test_client.post("/api/v1/sms/webhook", json=webhook_payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "SUCCESS"

    # Second attempt: DROPPED
    res2 = await test_client.post("/api/v1/sms/webhook", json=webhook_payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "DROPPED"
    assert "Duplicate transaction" in res2.json()["message"]

    # Verify balance updated exactly once ($20, not $40)
    bal_res = await test_client.get(f"/api/v1/balance/{u_pub}")
    assert bal_res.json()["current_balance"] == 20.0
