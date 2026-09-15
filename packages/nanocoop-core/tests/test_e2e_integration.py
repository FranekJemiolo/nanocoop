"""End-to-End 3-tier integration test proving:
1. Initial ledger state setup.
2. Incoming SMS receipt intercepted by SMS Bridge and forwarded to Core Ledger.
3. Ledger verifies idempotency and records DEPOSIT_MOBILE_MONEY.
4. Teller App queries updated member balance.
5. Teller App performs dual-signed cash withdrawal.
6. Chain integrity and Merkle tree state proofs remain 100% valid.
7. Duplicate SMS transmission safely dropped without double-crediting.
"""

import hashlib
import time
import uuid
import pytest
import aiosqlite
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


@pytest.mark.asyncio
async def test_full_three_tier_e2e_flow(tmp_path):
    """Complete 3-tier end-to-end integration test."""
    db_path = str(tmp_path / "nanocoop_e2e.db")
    await init_db(db_path)

    async def override_db():
        conn = await aiosqlite.connect(db_path)
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Setup Identities
        teller_priv, teller_pub = generate_keypair()
        member_priv, member_pub = generate_keypair()
        gateway_priv, gateway_pub = generate_keypair()
        member_phone = "+254712345678"

        # Step 1: Initial state check
        init_stats = (await client.get("/api/v1/stats")).json()
        assert init_stats["total_balance"] == 0.0
        assert init_stats["total_events"] == 0
        assert init_stats["is_chain_valid"] is True

        # Step 2: Simulate incoming Mobile Money SMS receipt via SMS Gateway
        # e.g., "QA12BC34DE Confirmed. You have received USD 150.00 from Jane Member +254712345678"
        sms_tx_code = "QA12BC34DE"
        sms_amount = 150.0

        gateway_payload_to_sign = {
            "tx": sms_tx_code,
            "amount": sms_amount,
            "sender": member_phone,
        }
        gateway_sig = sign_payload(gateway_priv, gateway_payload_to_sign)

        sms_webhook_req = {
            "transaction_code": sms_tx_code,
            "sender_phone": member_phone,
            "amount": sms_amount,
            "currency": "USD",
            "user_public_key": member_pub,
            "timestamp": int(time.time()),
            "gateway_signature": gateway_sig,
        }

        # SMS Gateway HTTP POSTs to Core
        sms_res = await client.post("/api/v1/sms/webhook", json=sms_webhook_req)
        assert sms_res.status_code == 200
        sms_data = sms_res.json()
        assert sms_data["status"] == "SUCCESS"
        sms_event_id = sms_data["event_id"]
        assert sms_event_id is not None

        # Step 3: Assert Teller Client queries reflect updated community vault & member balance
        member_bal = (await client.get(f"/api/v1/balance/{member_pub}")).json()
        assert member_bal["current_balance"] == 150.0

        stats_after_sms = (await client.get("/api/v1/stats")).json()
        assert stats_after_sms["total_balance"] == 150.0
        assert stats_after_sms["total_events"] == 1
        assert stats_after_sms["is_chain_valid"] is True
        sms_merkle_root = stats_after_sms["merkle_root"]
        assert sms_merkle_root != GENESIS_HASH

        # Step 4: Teller App processes Cash Withdrawal of $50.00 with Dual-Signatures (Teller + Member NFC)
        withdrawal_amount = 50.0

        # Get latest event hash to link chain
        events_page = (await client.get("/api/v1/events")).json()
        assert len(events_page["events"]) == 1
        last_event_hash = events_page["events"][0]["current_hash"]

        withdraw_payload = {
            "amount": withdrawal_amount,
            "currency": "USD",
            "user_public_key": member_pub,
            "notes": "Emergency branch cash withdrawal",
        }

        # Dual signing: Teller local key + Customer NFC key
        teller_sig = sign_payload(teller_priv, withdraw_payload)
        user_sig = sign_payload(member_priv, withdraw_payload)

        signatures = {
            "teller_sig": teller_sig,
            "user_sig": user_sig,
        }

        p_bytes = serialize_for_hashing(withdraw_payload)
        s_bytes = serialize_for_hashing(signatures)
        withdraw_current_hash = generate_event_hash(last_event_hash, p_bytes, s_bytes)

        withdrawal_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "event_type": "WITHDRAWAL_CASH",
            "payload": withdraw_payload,
            "previous_hash": last_event_hash,
            "signatures": signatures,
            "current_hash": withdraw_current_hash,
        }

        # Submit withdrawal event
        withdraw_res = await client.post("/api/v1/events", json=withdrawal_event)
        assert withdraw_res.status_code == 201

        # Step 5: Assert final balance is $100.00 ($150 deposit - $50 cash withdrawal)
        final_bal = (await client.get(f"/api/v1/balance/{member_pub}")).json()
        assert final_bal["current_balance"] == 100.0

        # Step 6: Assert Audit Verification passes with complete Merkle proof
        audit_res = (await client.get("/api/v1/audit/verify")).json()
        assert audit_res["is_valid"] is True
        assert audit_res["total_events"] == 2
        assert audit_res["last_hash"] == withdraw_current_hash
        assert audit_res["tamper_details"] is None

        # Step 7: Prove Idempotency - Simulate Gateway re-transmitting exact same SMS transaction
        duplicate_res = await client.post("/api/v1/sms/webhook", json=sms_webhook_req)
        assert duplicate_res.status_code == 200
        duplicate_data = duplicate_res.json()
        assert duplicate_data["status"] == "DROPPED"
        assert "Duplicate transaction" in duplicate_data["message"]

        # Balance remains strictly $100.00 (Zero double-crediting)
        post_dup_bal = (await client.get(f"/api/v1/balance/{member_pub}")).json()
        assert post_dup_bal["current_balance"] == 100.0

    app.dependency_overrides.clear()
