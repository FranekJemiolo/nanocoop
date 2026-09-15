"""Tests for application lifespan, health check, and internal error handler."""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.crypto import GENESIS_HASH, generate_keypair
from app.db.database import init_db
from app.main import app, lifespan


async def test_app_lifespan(tmp_path):
    test_db_path = str(tmp_path / "test_lifespan.db")
    import app.core.config

    old_path = app.core.config.settings.DB_PATH
    app.core.config.settings.DB_PATH = test_db_path

    try:
        async with lifespan(app):
            pass
    finally:
        app.core.config.settings.DB_PATH = old_path


async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy", "service": "nanocoop-core"}


async def test_create_event_internal_server_error(tmp_path):
    test_db_path = str(tmp_path / "test_500.db")
    await init_db(test_db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        _, u_pub = generate_keypair()
        dummy_event = {
            "event_id": "test-uuid-500",
            "timestamp": 123456789,
            "event_type": "DEPOSIT_CASH",
            "payload": {
                "amount": 50.0,
                "currency": "USD",
                "user_public_key": u_pub,
            },
            "previous_hash": GENESIS_HASH,
            "signatures": {
                "teller_sig": "a" * 64,
                "user_sig": "b" * 64,
            },
            "current_hash": "c" * 64,
        }

        # Mock EventLedger.append_event to raise an unexpected RuntimeError
        with patch(
            "app.api.routes.EventLedger.append_event", side_effect=RuntimeError("Disk crash")
        ):
            res = await client.post("/api/v1/events", json=dummy_event)
            assert res.status_code == 500
            assert "Ledger error: Disk crash" in res.json()["detail"]
