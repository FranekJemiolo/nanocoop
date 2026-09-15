"""Unit tests for telecom and mobile money integrations (Daraja, MTN MoMo, Airtel, Orange, Wave, Africa's Talking)."""

import hashlib
import hmac
import time
import httpx
import pytest
from app.integrations.africas_talking import AfricasTalkingClient
from app.integrations.airtel_money import AirtelMoneyClient
from app.integrations.daraja import DarajaClient
from app.integrations.mtn_momo import MtnMoMoClient
from app.integrations.orange_money import OrangeMoneyClient
from app.integrations.wave import WaveClient

# --- Safaricom Daraja Tests ---


async def test_daraja_unconfigured_mocks():
    client = DarajaClient(consumer_key="", consumer_secret="", passkey="", environment="sandbox")
    assert not client.is_configured

    token = await client.get_auth_token()
    assert "mock" in token

    resp = await client.initiate_stk_push(
        phone_number="0712345678",
        amount=100.0,
        account_reference="VSLA01",
    )
    assert resp["ResponseCode"] == "0"
    assert resp["simulated"] is True


async def test_daraja_configured_with_mocked_http():
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "access_token": "live_test_token_12345",
                "ResponseCode": "0",
                "ResponseDescription": "Success",
                "MerchantRequestID": "MR-1",
                "CheckoutRequestID": "CR-1",
            },
        )
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client = DarajaClient(
            consumer_key="key123",
            consumer_secret="sec123",
            passkey="pass123",
            shortcode="174379",
            environment="production",
        )
        assert client.is_configured
        assert client.base_url == "https://api.safaricom.co.ke"

        token = await client.get_auth_token(client=http_client)
        assert token == "live_test_token_12345"

        resp = await client.initiate_stk_push(
            phone_number="+254712345678",
            amount=50.0,
            account_reference="COOP",
            client=http_client,
        )
        assert resp["ResponseCode"] == "0"


def test_daraja_parse_callbacks():
    # Successful STK callback
    success_payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "MR-1",
                "CheckoutRequestID": "ws_CO_123",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 250.0},
                        {"Name": "MpesaReceiptNumber", "Value": "QWE123RTY"},
                        {"Name": "TransactionDate", "Value": "20260915190000"},
                        {"Name": "PhoneNumber", "Value": "254712345678"},
                    ]
                },
            }
        }
    }
    parsed = DarajaClient.parse_stk_callback(success_payload)
    assert parsed["is_successful"] is True
    assert parsed["amount"] == 250.0
    assert parsed["receipt_number"] == "QWE123RTY"
    assert parsed["phone_number"] == "254712345678"

    # Failed STK callback
    failed_payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "MR-2",
                "CheckoutRequestID": "ws_CO_456",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user",
            }
        }
    }
    parsed_fail = DarajaClient.parse_stk_callback(failed_payload)
    assert parsed_fail["is_successful"] is False
    assert parsed_fail["result_code"] == 1032

    # C2B confirmation
    c2b_payload = {
        "TransID": "RTY987UIO",
        "TransAmount": "500.00",
        "MSISDN": "254700000000",
        "BillRefNumber": "ACC1",
        "FirstName": "Grace",
        "TransTime": "20260915120000",
    }
    c2b_parsed = DarajaClient.parse_c2b_confirmation(c2b_payload)
    assert c2b_parsed["transaction_id"] == "RTY987UIO"
    assert c2b_parsed["amount"] == 500.0
    assert c2b_parsed["first_name"] == "Grace"


# --- MTN Mobile Money Tests ---


async def test_mtn_momo_unconfigured_mocks():
    client = MtnMoMoClient(subscription_key="", api_user="", api_key="", environment="sandbox")
    assert not client.is_configured

    token = await client.get_access_token()
    assert "mock" in token

    req_resp = await client.request_to_pay(
        amount=50.0,
        currency="UGX",
        phone_number="+256770000000",
        external_id="TX-001",
    )
    assert req_resp["status"] == "PENDING"
    assert req_resp["simulated"] is True

    status_resp = await client.get_transaction_status("test-ref-123")
    assert status_resp["status"] == "SUCCESSFUL"


async def test_mtn_momo_configured_with_mocked_http():
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            202,
            json={
                "access_token": "mtn_test_token_live",
                "status": "SUCCESSFUL",
                "financialTransactionId": "FIN-123",
            },
        )
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client = MtnMoMoClient(
            subscription_key="sub123",
            api_user="user-uuid-123",
            api_key="key123",
            environment="live",
        )
        assert client.is_configured
        assert client.base_url == "https://momodeveloper.mtn.com"

        token = await client.get_access_token(client=http_client)
        assert token == "mtn_test_token_live"

        req_resp = await client.request_to_pay(
            amount=75.0,
            currency="GHS",
            phone_number="233240000000",
            external_id="TX-002",
            client=http_client,
        )
        assert req_resp["status"] == "PENDING"

        status_resp = await client.get_transaction_status("ref-123", client=http_client)
        assert status_resp["status"] == "SUCCESSFUL"


def test_mtn_momo_parse_callback():
    payload = {
        "financialTransactionId": "FT-999",
        "externalId": "COOP-EXT-1",
        "amount": "150.00",
        "currency": "UGX",
        "status": "SUCCESSFUL",
        "payer": {"partyIdType": "MSISDN", "partyId": "256771122334"},
    }
    parsed = MtnMoMoClient.parse_callback(payload)
    assert parsed["is_successful"] is True
    assert parsed["financial_transaction_id"] == "FT-999"
    assert parsed["amount"] == 150.0
    assert parsed["payer"] == "256771122334"


# --- Africa's Talking Tests ---


def test_africas_talking_regex_parsing():
    client = AfricasTalkingClient()

    # 1. M-Pesa format
    mpesa_sms = {
        "text": "ABC123XYZ0 Confirmed. Ksh1,500.50 received from MARY WANJIKU 254711223344",
        "from": "+254711223344",
        "id": "SMS-001",
    }
    res_mpesa = client.parse_inbound_sms(mpesa_sms)
    assert res_mpesa["is_valid"] is True
    assert res_mpesa["provider"] == "MPESA"
    assert res_mpesa["transaction_code"] == "ABC123XYZ0"
    assert res_mpesa["amount"] == 1500.50

    # 2. MTN MoMo format
    mtn_sms = {
        "text": "TxId:MOMO888999 received UGX 50,000.00 from JOHN MUKASA 256772000000",
        "from": "+256772000000",
        "id": "SMS-002",
    }
    res_mtn = client.parse_inbound_sms(mtn_sms)
    assert res_mtn["is_valid"] is True
    assert res_mtn["provider"] == "MTN_MOMO"
    assert res_mtn["transaction_code"] == "MOMO888999"
    assert res_mtn["amount"] == 50000.0

    # 3. Airtel Money format
    airtel_sms = {
        "text": "Trans. ID: AIR777 received Ksh 300.00 from PETER OTIENO 254733000000",
        "from": "+254733000000",
        "id": "SMS-003",
    }
    res_airtel = client.parse_inbound_sms(airtel_sms)
    assert res_airtel["is_valid"] is True
    assert res_airtel["provider"] == "AIRTEL"
    assert res_airtel["transaction_code"] == "AIR777"
    assert res_airtel["amount"] == 300.0

    # 4. Generic Coop receipt
    generic_sms = {
        "text": "NANOCOOP DEPOSIT 45.00 REF NC9999",
        "from": "+254700000000",
        "id": "SMS-004",
    }
    res_gen = client.parse_inbound_sms(generic_sms)
    assert res_gen["is_valid"] is True
    assert res_gen["provider"] == "GENERIC"
    assert res_gen["transaction_code"] == "NC9999"
    assert res_gen["amount"] == 45.0

    # 5. Invalid SMS
    invalid_sms = {
        "text": "Hello, when is the next cooperative meeting?",
        "from": "+254700000000",
        "id": "SMS-005",
    }
    res_inv = client.parse_inbound_sms(invalid_sms)
    assert res_inv["is_valid"] is False


async def test_africas_talking_send_sms():
    # Unconfigured mock
    client_unconfigured = AfricasTalkingClient(username="", api_key="")
    assert not client_unconfigured.is_configured
    resp_mock = await client_unconfigured.send_sms("254712345678", "Hello VSLA Member")
    assert resp_mock["status"] == "SIMULATED"

    # Configured with mock transport
    mock_transport = httpx.MockTransport(
        lambda req: httpx.Response(
            201, json={"SMSMessageData": {"Recipients": [{"status": "Success"}]}}
        )
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client_configured = AfricasTalkingClient(
            username="production_user",
            api_key="at_key_123",
            sender_id="NANOCOOP",
        )
        assert client_configured.is_configured
        assert client_configured.base_url == "https://api.africastalking.com/version1"

        resp = await client_configured.send_sms(
            to_phone="+254712345678",
            message="Your deposit was confirmed",
            client=http_client,
        )
        assert "SMSMessageData" in resp

    # Passbook formatter
    msg = AfricasTalkingClient.format_passbook_sms(
        event_type="Deposit",
        amount=50.0,
        currency="USD",
        balance=150.0,
        reference="TX123",
    )
    assert "[NanoCoop]" in msg
    assert "USD 50.00" in msg
    assert "USD 150.00" in msg


async def test_clients_without_injected_http_client(monkeypatch):
    class MockResp:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    async def mock_get(self, url, *args, **kwargs):
        return MockResp({"access_token": "token_without_client", "status": "SUCCESSFUL"})

    async def mock_post(self, url, *args, **kwargs):
        return MockResp(
            {
                "access_token": "token_without_client",
                "ResponseCode": "0",
                "status": "PENDING",
                "SMSMessageData": {"status": "ok"},
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    # Test Daraja
    daraja = DarajaClient(consumer_key="k", consumer_secret="s", passkey="p")
    t1 = await daraja.get_auth_token()
    assert t1 == "token_without_client"
    r1 = await daraja.initiate_stk_push("0712345678", 50.0, "ACC")
    assert r1["ResponseCode"] == "0"

    # Test MTN MoMo
    momo = MtnMoMoClient(subscription_key="s", api_user="u", api_key="k")
    t2 = await momo.get_access_token()
    assert t2 == "token_without_client"
    r2 = await momo.request_to_pay(10.0, "UGX", "25677000", "EXT")
    assert r2["status"] == "PENDING"
    r3 = await momo.get_transaction_status("ref-1")
    assert r3["status"] == "SUCCESSFUL"

    # Test Africa's Talking
    at = AfricasTalkingClient(username="usr", api_key="k")
    r4 = await at.send_sms("254712345678", "Hello")
    assert "SMSMessageData" in r4

    # Test Airtel Money
    airtel = AirtelMoneyClient(client_id="id", client_secret="sec")
    t3 = await airtel.get_access_token()
    assert t3 == "token_without_client"
    r5 = await airtel.request_to_pay("0712345678", 20.0, "REF")
    assert r5["ResponseCode"] == "0"
    r6 = await airtel.get_payment_status("tx-1")
    assert r6["status"] == "SUCCESSFUL"

    # Test Orange Money
    orange = OrangeMoneyClient(client_id="id", client_secret="sec", merchant_key="mk")
    t4 = await orange.get_access_token()
    assert t4 == "token_without_client"
    r7 = await orange.initiate_payment("order-1", 500.0)
    assert r7["ResponseCode"] == "0"
    r8 = await orange.get_transaction_status("order-1", 500.0, "paytok")
    assert r8["ResponseCode"] == "0"

    # Test Wave
    wave = WaveClient(api_key="wave_key")
    r9 = await wave.create_checkout_session(1000.0)
    assert r9["ResponseCode"] == "0"


# --- Airtel Money Tests ---


async def test_airtel_unconfigured_mocks():
    client = AirtelMoneyClient(client_id="", client_secret="", environment="staging")
    assert not client.is_configured
    assert client.base_url == "https://openapiuat.airtel.africa"

    token = await client.get_access_token()
    assert "mock" in token

    r1 = await client.request_to_pay("0712345678", 150.0, "SAVINGS-01")
    assert r1["simulated"] is True
    assert r1["status"]["code"] == "200"

    r2 = await client.get_payment_status("tx-123")
    assert r2["simulated"] is True
    assert r2["data"]["transaction"]["status"] == "TS"


async def test_airtel_configured_with_mocked_http():
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "access_token": "airtel_live_token",
                "data": {"transaction": {"id": "TX_AIRTEL_99", "status": "TIP"}},
                "status": {"code": "200", "success": True},
            },
        )
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client = AirtelMoneyClient(
            client_id="cid",
            client_secret="csec",
            country="KE",
            currency="KES",
            environment="production",
        )
        assert client.is_configured
        assert client.base_url == "https://openapi.airtel.africa"

        token = await client.get_access_token(client=http_client)
        assert token == "airtel_live_token"

        r1 = await client.request_to_pay("+254712345678", 200.0, "VSLA", client=http_client)
        assert r1["status"]["success"] is True

        r2 = await client.get_payment_status("TX_AIRTEL_99", client=http_client)
        assert r2["status"]["success"] is True


def test_airtel_parse_callback():
    payload_success = {
        "transaction": {
            "id": "AIRTEL-TX-001",
            "amount": "350.00",
            "currency": "KES",
            "status": "TS",
            "message": "Paid",
        },
        "subscriber": {"msisdn": "254712345678"},
    }
    parsed = AirtelMoneyClient.parse_callback(payload_success)
    assert parsed["is_successful"] is True
    assert parsed["transaction_id"] == "AIRTEL-TX-001"
    assert parsed["amount"] == 350.0
    assert parsed["subscriber_phone"] == "254712345678"

    payload_fail = {
        "transaction": {"id": "AIRTEL-TX-002", "amount": 100, "status": "TF"},
        "subscriber": {"msisdn": "254712000000"},
    }
    parsed_fail = AirtelMoneyClient.parse_callback(payload_fail)
    assert parsed_fail["is_successful"] is False


# --- Orange Money Tests ---


async def test_orange_unconfigured_mocks():
    client = OrangeMoneyClient(client_id="", client_secret="", merchant_key="")
    assert not client.is_configured

    token = await client.get_access_token()
    assert "mock" in token

    r1 = await client.initiate_payment("ORDER-1", 5000.0)
    assert r1["simulated"] is True
    assert r1["status"] == 201
    assert "pay_token" in r1

    r2 = await client.get_transaction_status("ORDER-1", 5000.0, "tok-1")
    assert r2["simulated"] is True
    assert r2["status"] == "SUCCESS"


async def test_orange_configured_with_mocked_http():
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "access_token": "orange_live_token",
                "status": 201,
                "pay_token": "OM_LIVE_TOK",
                "payment_url": "https://webpayment.orange.com/pay/OM_LIVE_TOK",
            },
        )
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client = OrangeMoneyClient(
            client_id="cid",
            client_secret="csec",
            merchant_key="mkey",
            environment="production",
        )
        assert client.is_configured

        token = await client.get_access_token(client=http_client)
        assert token == "orange_live_token"

        r1 = await client.initiate_payment("ORD-99", 2500.0, client=http_client)
        assert r1["status"] == 201

        r2 = await client.get_transaction_status(
            "ORD-99", 2500.0, "OM_LIVE_TOK", client=http_client
        )
        assert r2["status"] == 201


def test_orange_parse_callback():
    payload_success = {
        "status": "SUCCESS",
        "txnid": "OM-TXN-12345",
        "order_id": "ORD-123",
        "amount": "4500",
        "currency": "XOF",
        "customer_id": "221770001122",
    }
    parsed = OrangeMoneyClient.parse_callback(payload_success)
    assert parsed["is_successful"] is True
    assert parsed["transaction_id"] == "OM-TXN-12345"
    assert parsed["amount"] == 4500.0
    assert parsed["customer_phone"] == "221770001122"

    payload_fail = {"status": "FAILED", "order_id": "ORD-FAIL", "amount": 100}
    parsed_fail = OrangeMoneyClient.parse_callback(payload_fail)
    assert parsed_fail["is_successful"] is False


# --- Wave Mobile Money Tests ---


async def test_wave_unconfigured_mocks():
    client = WaveClient(api_key="", webhook_secret="")
    assert not client.is_configured

    r1 = await client.create_checkout_session(2000.0)
    assert r1["simulated"] is True
    assert "wave_launch_url" in r1

    # Permissive signature verification when unconfigured
    assert client.verify_webhook_signature(b"{}", "") is True


async def test_wave_configured_with_mocked_http():
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "id": "cos_wave_123",
                "amount": "5000",
                "currency": "XOF",
                "wave_launch_url": "https://pay.wave.com/c/cos_wave_123",
            },
        )
    )
    async with httpx.AsyncClient(transport=mock_transport) as http_client:
        client = WaveClient(api_key="wave_secret_key", webhook_secret="wh_secret")
        assert client.is_configured

        r1 = await client.create_checkout_session(
            5000.0,
            restrict_payer_mobile="+221770000000",
            client=http_client,
        )
        assert r1["id"] == "cos_wave_123"


def test_wave_verify_webhook_signature():
    secret = "test_webhook_secret_key"
    client = WaveClient(api_key="key", webhook_secret=secret)

    now = int(time.time())
    body = b'{"type": "checkout.session.completed"}'
    signed_payload = f"{now}.".encode("utf-8") + body
    valid_sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    header = f"t={now},v1={valid_sig}"
    assert client.verify_webhook_signature(body, header) is True

    # Bad sig
    bad_header = f"t={now},v1=invalid_signature_hex"
    assert client.verify_webhook_signature(body, bad_header) is False

    # Bad format
    assert client.verify_webhook_signature(body, "invalid_format") is False
    assert client.verify_webhook_signature(body, "t=invalid_ts,v1=sig") is False

    # Expired timestamp (older than 300s)
    old_ts = now - 600
    old_payload = f"{old_ts}.".encode("utf-8") + body
    old_sig = hmac.new(secret.encode("utf-8"), old_payload, hashlib.sha256).hexdigest()
    assert client.verify_webhook_signature(body, f"t={old_ts},v1={old_sig}") is False


def test_wave_parse_webhook():
    payload_success = {
        "type": "checkout.session.completed",
        "data": {
            "id": "cos_001",
            "transaction_id": "WAVE_TX_999",
            "amount": "1200",
            "currency": "XOF",
            "client_reference": "COOP-WAVE-01",
            "customer": {"mobile": "+221770001122"},
        },
    }
    parsed = WaveClient.parse_webhook(payload_success)
    assert parsed["is_successful"] is True
    assert parsed["transaction_id"] == "WAVE_TX_999"
    assert parsed["amount"] == 1200.0
    assert parsed["payer_mobile"] == "+221770001122"

    payload_other = {"type": "checkout.session.cancelled", "data": {}}
    parsed_other = WaveClient.parse_webhook(payload_other)
    assert parsed_other["is_successful"] is False
