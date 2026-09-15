"""Comprehensive API integration tests for VSLA domain endpoints and telecom webhooks."""

import time
import uuid
import aiosqlite
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
async def async_client(tmp_path):
    test_db_path = str(tmp_path / "test_api_vsla.db")
    await init_db(test_db_path)

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


async def test_api_accounts_and_welfare_stats(async_client):
    # Test /accounts
    res = await async_client.get("/api/v1/accounts")
    assert res.status_code == 200
    assert isinstance(res.json(), dict)

    # Test /welfare/stats
    res = await async_client.get("/api/v1/welfare/stats")
    assert res.status_code == 200
    data = res.json()
    assert "social_fund_balance" in data
    assert "total_capital" in data


async def test_api_vsla_loans_and_welfare_flow(async_client):
    b_priv, b_pub = generate_keypair()
    t_priv, _ = generate_keypair()

    # 1. Successful loan disbursement with dual signatures
    payload_disburse = {
        "amount": 250.0,
        "currency": "USD",
        "interest_rate": 5.0,
        "loan_id": "LOAN-001",
        "notes": "Farm equipment loan",
        "term_months": 6,
        "user_public_key": b_pub,
    }
    b_sig = sign_payload(b_priv, payload_disburse)
    t_sig = sign_payload(t_priv, payload_disburse)

    disburse_req = {
        "borrower_public_key": b_pub,
        "amount": 250.0,
        "currency": "USD",
        "loan_id": "LOAN-001",
        "interest_rate": 5.0,
        "term_months": 6,
        "notes": "Farm equipment loan",
        "teller_sig": t_sig,
        "borrower_sig": b_sig,
    }
    res_loan = await async_client.post("/api/v1/loans/disburse", json=disburse_req)
    assert res_loan.status_code == 201

    # Bad signature should return 400
    bad_req = dict(disburse_req)
    bad_req["borrower_sig"] = "0" * 64
    res_bad = await async_client.post("/api/v1/loans/disburse", json=bad_req)
    assert res_bad.status_code == 400

    # 2. Successful loan repayment
    payload_repay = {
        "amount": 50.0,
        "currency": "USD",
        "loan_id": "LOAN-001",
        "notes": "Monthly installment",
        "user_public_key": b_pub,
    }
    b_repay_sig = sign_payload(b_priv, payload_repay)
    t_repay_sig = sign_payload(t_priv, payload_repay)

    repay_req = {
        "borrower_public_key": b_pub,
        "amount": 50.0,
        "currency": "USD",
        "loan_id": "LOAN-001",
        "notes": "Monthly installment",
        "teller_sig": t_repay_sig,
        "borrower_sig": b_repay_sig,
    }
    res_repay = await async_client.post("/api/v1/loans/repay", json=repay_req)
    assert res_repay.status_code == 201

    # Bad user signature on repay returns 400
    bad_repay = dict(repay_req)
    bad_repay["borrower_sig"] = "0" * 64
    res_repay_bad = await async_client.post("/api/v1/loans/repay", json=bad_repay)
    assert res_repay_bad.status_code == 400

    # 3. Successful welfare contribution
    payload_welf = {
        "amount": 10.0,
        "currency": "USD",
        "notes": "Weekly social emergency fund contribution",
        "user_public_key": b_pub,
    }
    t_welf_sig = sign_payload(t_priv, payload_welf)
    welf_req = {
        "member_public_key": b_pub,
        "amount": 10.0,
        "currency": "USD",
        "notes": "Weekly social emergency fund contribution",
        "teller_sig": t_welf_sig,
    }
    res_welf = await async_client.post("/api/v1/welfare/contribute", json=welf_req)
    assert res_welf.status_code == 201

    # Bad member sig on welfare contribution returns 400
    bad_welf = dict(welf_req)
    bad_welf["member_sig"] = "0" * 64
    res_welf_bad = await async_client.post("/api/v1/welfare/contribute", json=bad_welf)
    assert res_welf_bad.status_code == 400

    # 4. Successful welfare payout
    payload_payout = {
        "amount": 5.0,
        "currency": "USD",
        "notes": "Emergency welfare grant: Medical clinic visit",
        "user_public_key": b_pub,
    }
    b_payout_sig = sign_payload(b_priv, payload_payout)
    t_payout_sig = sign_payload(t_priv, payload_payout)
    payout_req = {
        "member_public_key": b_pub,
        "amount": 5.0,
        "currency": "USD",
        "purpose": "Medical clinic visit",
        "teller_sig": t_payout_sig,
        "member_sig": b_payout_sig,
    }
    res_payout = await async_client.post("/api/v1/welfare/payout", json=payout_req)
    assert res_payout.status_code == 201

    # Bad signature on welfare payout returns 400
    bad_payout = dict(payout_req)
    bad_payout["member_sig"] = "0" * 64
    res_payout_bad = await async_client.post("/api/v1/welfare/payout", json=bad_payout)
    assert res_payout_bad.status_code == 400


async def test_api_create_event_error_branches(async_client):
    # Test CryptographicError branch on /events
    _, u_pub = generate_keypair()

    bad_event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "event_type": "DEPOSIT_CASH",
        "payload": {
            "amount": 50.0,
            "currency": "USD",
            "user_public_key": u_pub,
        },
        "previous_hash": GENESIS_HASH,
        "signatures": {
            "teller_sig": "0" * 64,
            "user_sig": "0" * 64,
        },
        "current_hash": "0" * 64,
    }
    res = await async_client.post("/api/v1/events", json=bad_event)
    assert res.status_code == 400
    assert "detail" in res.json()


async def test_integrations_status_and_stk_push(async_client):
    # 1. /integrations/status
    res = await async_client.get("/api/v1/integrations/status")
    assert res.status_code == 200
    data = res.json()
    assert "safaricom_daraja" in data
    assert "mtn_momo" in data
    assert "africas_talking" in data

    # 2. /integrations/mpesa/stk-push
    res_stk = await async_client.post(
        "/api/v1/integrations/mpesa/stk-push",
        params={"phone_number": "254712345678", "amount": 100.0, "account_reference": "NANO"},
    )
    assert res_stk.status_code == 200
    assert "ResponseCode" in res_stk.json()


async def test_daraja_stk_callback_success_failed_and_duplicate(async_client):
    # 1. Successful callback
    success_callback = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "MR-100",
                "CheckoutRequestID": "ws_CO_TEST_999",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 75.0},
                        {"Name": "MpesaReceiptNumber", "Value": "MPESA_REC_01"},
                        {"Name": "TransactionDate", "Value": "20260915193000"},
                        {"Name": "PhoneNumber", "Value": "254712345678"},
                    ]
                },
            }
        }
    }
    res = await async_client.post("/api/v1/integrations/mpesa/stk-callback", json=success_callback)
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCESS"
    assert res.json()["receipt_number"] == "MPESA_REC_01"

    # Duplicate callback -> DROPPED
    res_dup = await async_client.post("/api/v1/integrations/mpesa/stk-callback", json=success_callback)
    assert res_dup.status_code == 200
    assert res_dup.json()["status"] == "DROPPED"

    # 2. Failed callback
    failed_callback = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "MR-101",
                "CheckoutRequestID": "ws_CO_TEST_FAIL",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user",
            }
        }
    }
    res_fail = await async_client.post("/api/v1/integrations/mpesa/stk-callback", json=failed_callback)
    assert res_fail.status_code == 200
    assert res_fail.json()["status"] == "FAILED"


async def test_daraja_c2b_validation_and_confirmation(async_client):
    # Validation hook
    res_val = await async_client.post("/api/v1/integrations/mpesa/c2b-validation", json={})
    assert res_val.status_code == 200
    assert res_val.json()["ResultCode"] == 0

    # Confirmation hook missing TransID
    res_no_tx = await async_client.post("/api/v1/integrations/mpesa/c2b-confirmation", json={})
    assert res_no_tx.status_code == 200
    assert res_no_tx.json()["status"] == "REJECTED"

    # Valid confirmation hook
    c2b_data = {
        "TransID": "C2B_REC_101",
        "TransAmount": "120.00",
        "MSISDN": "254711998877",
        "BillRefNumber": "SAVINGS",
        "FirstName": "Amina",
        "TransTime": "20260915200000",
    }
    res_conf = await async_client.post("/api/v1/integrations/mpesa/c2b-confirmation", json=c2b_data)
    assert res_conf.status_code == 200
    assert res_conf.json()["ResultCode"] == 0

    # Duplicate confirmation hook -> DROPPED
    res_conf_dup = await async_client.post("/api/v1/integrations/mpesa/c2b-confirmation", json=c2b_data)
    assert res_conf_dup.status_code == 200
    assert res_conf_dup.json()["status"] == "DROPPED"


async def test_mtn_momo_request_to_pay_and_callback(async_client):
    # 1. RequestToPay
    res_req = await async_client.post(
        "/api/v1/integrations/mtn/request-to-pay",
        params={
            "amount": 60.0,
            "currency": "UGX",
            "phone_number": "256770001122",
            "external_id": "COOP-TEST",
        },
    )
    assert res_req.status_code == 200
    assert "reference_id" in res_req.json()

    # 2. Failed callback -> IGNORED
    res_cb_fail = await async_client.post(
        "/api/v1/integrations/mtn/callback",
        json={"status": "FAILED", "financialTransactionId": "FAIL_1"},
    )
    assert res_cb_fail.status_code == 200
    assert res_cb_fail.json()["status"] == "IGNORED"

    # 3. Successful callback
    momo_cb = {
        "status": "SUCCESSFUL",
        "financialTransactionId": "MOMO_TX_777",
        "externalId": "COOP-EXT-01",
        "amount": "80.00",
        "currency": "UGX",
        "payer": {"partyId": "256770001122"},
    }
    res_cb = await async_client.post("/api/v1/integrations/mtn/callback", json=momo_cb)
    assert res_cb.status_code == 200
    assert res_cb.json()["status"] == "SUCCESS"

    # Duplicate callback -> DROPPED
    res_cb_dup = await async_client.post("/api/v1/integrations/mtn/callback", json=momo_cb)
    assert res_cb_dup.status_code == 200
    assert res_cb_dup.json()["status"] == "DROPPED"


async def test_africas_talking_inbound_and_duplicate(async_client):
    # 1. Invalid SMS -> IGNORED
    res_inv = await async_client.post(
        "/api/v1/integrations/africas-talking/inbound",
        json={"text": "Hello cooperative treasurer", "from": "+254712000000", "id": "1"},
    )
    assert res_inv.status_code == 200
    assert res_inv.json()["status"] == "IGNORED"

    # 2. Valid SMS -> SUCCESS
    valid_sms = {
        "text": "NANOCOOP DEPOSIT 90.00 REF NC_SMS_999",
        "from": "+254712000000",
        "id": "SMS_TEST_001",
    }
    res_val = await async_client.post("/api/v1/integrations/africas-talking/inbound", json=valid_sms)
    assert res_val.status_code == 200
    assert res_val.json()["status"] == "SUCCESS"
    assert res_val.json()["amount"] == 90.0

    # Duplicate SMS -> DROPPED
    res_dup = await async_client.post("/api/v1/integrations/africas-talking/inbound", json=valid_sms)
    assert res_dup.status_code == 200
    assert res_dup.json()["status"] == "DROPPED"
