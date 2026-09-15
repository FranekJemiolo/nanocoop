"""FastAPI REST API routes for NanoCoop Core."""

import hashlib
import time
import uuid
from typing import Any
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    generate_keypair,
    serialize_for_hashing,
    sign_payload,
)
from app.db.database import get_db
from app.integrations.africas_talking import africas_talking_client
from app.integrations.daraja import daraja_client
from app.integrations.mtn_momo import momo_client
from app.ledger.ledger import (
    ChainIntegrityError,
    CryptographicError,
    EventLedger,
)
from app.ledger.schema import (
    AccountState,
    AuditVerification,
    CommunityStats,
    EventModel,
    EventPayload,
    EventSignatures,
    EventType,
    LoanDisbursementRequest,
    LoanRepaymentRequest,
    MobileMoneyWebhookPayload,
    PaginatedEvents,
    SocialFundContributionRequest,
    SocialFundPayoutRequest,
)

router = APIRouter()

# Server-side key for auto-signing verified telecom integration webhooks if needed
_server_signer_priv, _server_signer_pub = generate_keypair()


@router.post("/events", response_model=EventModel, status_code=status.HTTP_201_CREATED)
async def create_event(event: EventModel, db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Submit a cryptographically authorized event to the append-only ledger."""
    ledger = EventLedger(db)
    try:
        appended = await ledger.append_event(event)
        return appended
    except (CryptographicError, ChainIntegrityError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ledger error: {str(e)}",
        )


@router.get("/events", response_model=PaginatedEvents)
async def list_events(
    cursor: int | None = Query(None, description="Cursor for pagination (last event ID)"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    db: aiosqlite.Connection = Depends(get_db),
) -> Any:
    """Fetch paginated events using cursor-based pagination."""
    ledger = EventLedger(db)
    events, next_cursor, has_more, total_count = await ledger.get_events(cursor=cursor, limit=limit)
    return PaginatedEvents(
        events=[EventModel(**e) for e in events],
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )


@router.get("/balance/{user_public_key}", response_model=AccountState)
async def get_balance(user_public_key: str, db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Get current account state computed by state reducer from event stream."""
    ledger = EventLedger(db)
    account_state = await ledger.get_user_balance(user_public_key)
    return AccountState(**account_state)


@router.get("/accounts")
async def get_all_accounts(db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Get all cooperative member account states."""
    ledger = EventLedger(db)
    return await ledger.get_all_account_balances()


@router.get("/stats", response_model=CommunityStats)
async def get_community_stats(db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Get overall community banking stats, VSLA portfolio, Merkle tree root, and chain validity."""
    ledger = EventLedger(db)
    events = await ledger.get_all_events()
    accounts = await ledger.get_all_account_balances()
    metrics = await ledger.get_community_metrics()
    merkle_root = await ledger.get_merkle_root()
    is_valid, _ = await ledger.verify_chain_integrity()

    return CommunityStats(
        total_balance=metrics["total_savings"],
        total_savings=metrics["total_savings"],
        total_loans_outstanding=metrics["total_loans_outstanding"],
        total_social_fund=metrics["total_social_fund"],
        total_capital=metrics["total_capital"],
        total_members=len(accounts),
        total_events=len(events),
        merkle_root=merkle_root,
        is_chain_valid=is_valid,
    )


@router.get("/audit/verify", response_model=AuditVerification)
async def verify_chain(db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Verify cryptographic integrity of entire ledger chain and Merkle root."""
    ledger = EventLedger(db)
    is_valid, tamper_details = await ledger.verify_chain_integrity()
    events = await ledger.get_all_events()
    merkle_root = await ledger.get_merkle_root()
    last_event = events[-1] if events else None

    return AuditVerification(
        is_valid=is_valid,
        total_events=len(events),
        merkle_root=merkle_root,
        last_hash=last_event["current_hash"] if last_event else GENESIS_HASH,
        tamper_details=tamper_details,
    )


# --- VSLA Microfinance Domain Endpoints ---


@router.post("/loans/disburse", response_model=EventModel, status_code=status.HTTP_201_CREATED)
async def disburse_loan(
    req: LoanDisbursementRequest, db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Disburse a micro-loan to a cooperative member with dual cryptographic multi-sig."""
    ledger = EventLedger(db)
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    loan_id = req.loan_id or f"LOAN-{uuid.uuid4().hex[:8].upper()}"
    payload_obj = EventPayload(
        amount=req.amount,
        currency=req.currency,
        user_public_key=req.borrower_public_key,
        loan_id=loan_id,
        interest_rate=req.interest_rate,
        term_months=req.term_months,
        notes=req.notes or f"Micro-loan disbursement: {loan_id}",
    )
    signatures_obj = EventSignatures(
        teller_sig=req.teller_sig,
        user_sig=req.borrower_sig,
    )

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.LOAN_DISBURSED,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    try:
        return await ledger.append_event(event_model)
    except (CryptographicError, ChainIntegrityError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/loans/repay", response_model=EventModel, status_code=status.HTTP_201_CREATED)
async def repay_loan(req: LoanRepaymentRequest, db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Record a loan repayment reducing outstanding debt."""
    ledger = EventLedger(db)
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=req.amount,
        currency=req.currency,
        user_public_key=req.borrower_public_key,
        loan_id=req.loan_id,
        notes=req.notes or "Loan repayment",
    )
    signatures_obj = EventSignatures(
        teller_sig=req.teller_sig,
        user_sig=req.borrower_sig,
    )

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.LOAN_REPAID,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    try:
        return await ledger.append_event(event_model)
    except (CryptographicError, ChainIntegrityError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/welfare/contribute", response_model=EventModel, status_code=status.HTTP_201_CREATED)
async def contribute_social_fund(
    req: SocialFundContributionRequest, db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Contribute to cooperative social emergency safety net fund."""
    ledger = EventLedger(db)
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=req.amount,
        currency=req.currency,
        user_public_key=req.member_public_key,
        notes=req.notes or "Weekly social emergency fund contribution",
    )
    signatures_obj = EventSignatures(
        teller_sig=req.teller_sig,
        user_sig=req.member_sig,
    )

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.SOCIAL_FUND_CONTRIBUTION,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    try:
        return await ledger.append_event(event_model)
    except (CryptographicError, ChainIntegrityError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/welfare/payout", response_model=EventModel, status_code=status.HTTP_201_CREATED)
async def payout_social_fund(
    req: SocialFundPayoutRequest, db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Disburse an approved emergency relief grant from the social welfare fund."""
    ledger = EventLedger(db)
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=req.amount,
        currency=req.currency,
        user_public_key=req.member_public_key,
        notes=f"Emergency welfare grant: {req.purpose}",
    )
    signatures_obj = EventSignatures(
        teller_sig=req.teller_sig,
        user_sig=req.member_sig,
    )

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.SOCIAL_FUND_PAYOUT,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    try:
        return await ledger.append_event(event_model)
    except (CryptographicError, ChainIntegrityError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/welfare/stats")
async def get_welfare_stats(db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Get cooperative social fund safety net balances."""
    ledger = EventLedger(db)
    metrics = await ledger.get_community_metrics()
    return {
        "social_fund_balance": metrics["total_social_fund"],
        "total_capital": metrics["total_capital"],
    }


# --- Telecom Integrations & Mobile Money Endpoints ---


@router.get("/integrations/status")
async def get_integrations_status() -> Any:
    """Get status of telecom gateways (reports if credentials are configured without leaking secrets)."""
    return {
        "safaricom_daraja": {
            "configured": daraja_client.is_configured,
            "environment": daraja_client.environment,
            "shortcode": daraja_client.shortcode,
        },
        "mtn_momo": {
            "configured": momo_client.is_configured,
            "environment": momo_client.environment,
        },
        "africas_talking": {
            "configured": africas_talking_client.is_configured,
            "username": africas_talking_client.username,
        },
    }


@router.post("/integrations/mpesa/stk-push")
async def initiate_mpesa_stk(
    phone_number: str = Query(..., description="Customer phone (e.g. 254712345678)"),
    amount: float = Query(..., gt=0),
    account_reference: str = Query("NanoCoop"),
) -> Any:
    """Initiate M-Pesa STK Push prompt on member phone."""
    return await daraja_client.initiate_stk_push(
        phone_number=phone_number,
        amount=amount,
        account_reference=account_reference,
    )


@router.post("/integrations/mpesa/stk-callback")
async def process_mpesa_callback(
    payload: dict[str, Any], db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Receive Safaricom STK Push callback and record deposit with idempotency."""
    parsed = daraja_client.parse_stk_callback(payload)
    if not parsed["is_successful"]:
        return {"status": "FAILED", "reason": parsed["result_desc"]}

    tx_code = parsed["receipt_number"] or parsed["checkout_request_id"] or str(uuid.uuid4())
    raw_tx_id = f"MPESA:{tx_code}:{parsed['amount']}:{parsed['phone_number']}"
    tx_hash = hashlib.sha256(raw_tx_id.encode("utf-8")).hexdigest()

    ledger = EventLedger(db)
    if not await ledger.check_and_record_idempotency(tx_hash):
        return {"status": "DROPPED", "message": f"Duplicate M-Pesa transaction {tx_code}"}

    # Find or assign member public key
    user_key = f"mpesa_{parsed['phone_number']}".ljust(32, "0")
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=parsed["amount"],
        currency="KES",
        user_public_key=user_key,
        reference=tx_code,
        notes=f"M-Pesa STK Push from {parsed['phone_number']}",
    )
    sig = sign_payload(_server_signer_priv, payload_obj.model_dump(exclude_none=True))
    signatures_obj = EventSignatures(teller_sig=sig, user_sig=None)

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.DEPOSIT_MOBILE_MONEY,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    await ledger.append_event(event_model)
    return {
        "status": "SUCCESS",
        "receipt_number": tx_code,
        "amount": parsed["amount"],
        "current_hash": current_hash,
    }


@router.post("/integrations/mpesa/c2b-validation")
async def mpesa_c2b_validation(payload: dict[str, Any]) -> Any:
    """Safaricom C2B Validation URL callback."""
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/integrations/mpesa/c2b-confirmation")
async def mpesa_c2b_confirmation(
    payload: dict[str, Any], db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Safaricom C2B Payment Confirmation URL callback."""
    parsed = daraja_client.parse_c2b_confirmation(payload)
    tx_code = parsed["transaction_id"]
    if not tx_code:
        return {"status": "REJECTED", "detail": "Missing TransID"}

    raw_tx_id = f"C2B:{tx_code}:{parsed['amount']}:{parsed['phone_number']}"
    tx_hash = hashlib.sha256(raw_tx_id.encode("utf-8")).hexdigest()

    ledger = EventLedger(db)
    if not await ledger.check_and_record_idempotency(tx_hash):
        return {"status": "DROPPED", "message": f"Duplicate C2B transaction {tx_code}"}

    user_key = f"c2b_{parsed['phone_number']}".ljust(32, "0")
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=parsed["amount"],
        currency="KES",
        user_public_key=user_key,
        reference=tx_code,
        notes=f"M-Pesa C2B payment from {parsed['first_name']} ({parsed['phone_number']})",
    )
    sig = sign_payload(_server_signer_priv, payload_obj.model_dump(exclude_none=True))
    signatures_obj = EventSignatures(teller_sig=sig, user_sig=None)

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.DEPOSIT_MOBILE_MONEY,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    await ledger.append_event(event_model)
    return {"ResultCode": 0, "ResultDesc": "Success", "transaction_id": tx_code}


@router.post("/integrations/mtn/request-to-pay")
async def mtn_request_to_pay(
    amount: float = Query(..., gt=0),
    currency: str = Query("UGX"),
    phone_number: str = Query(...),
    external_id: str = Query("COOP-001"),
) -> Any:
    """Trigger MTN Mobile Money RequestToPay prompt on member phone."""
    return await momo_client.request_to_pay(
        amount=amount,
        currency=currency,
        phone_number=phone_number,
        external_id=external_id,
    )


@router.post("/integrations/mtn/callback")
async def mtn_callback(payload: dict[str, Any], db: aiosqlite.Connection = Depends(get_db)) -> Any:
    """Receive MTN Mobile Money webhook callback and record deposit if successful."""
    parsed = momo_client.parse_callback(payload)
    if not parsed["is_successful"]:
        return {"status": "IGNORED", "reason": f"Status is {parsed['status']}"}

    tx_code = parsed["financial_transaction_id"] or str(uuid.uuid4())
    raw_tx_id = f"MTN:{tx_code}:{parsed['amount']}:{parsed['payer']}"
    tx_hash = hashlib.sha256(raw_tx_id.encode("utf-8")).hexdigest()

    ledger = EventLedger(db)
    if not await ledger.check_and_record_idempotency(tx_hash):
        return {"status": "DROPPED", "message": f"Duplicate MTN transaction {tx_code}"}

    user_key = f"mtn_{parsed['payer']}".ljust(32, "0")
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=parsed["amount"],
        currency=parsed["currency"],
        user_public_key=user_key,
        reference=tx_code,
        notes=f"MTN Mobile Money deposit from {parsed['payer']}",
    )
    sig = sign_payload(_server_signer_priv, payload_obj.model_dump(exclude_none=True))
    signatures_obj = EventSignatures(teller_sig=sig, user_sig=None)

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.DEPOSIT_MOBILE_MONEY,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    await ledger.append_event(event_model)
    return {"status": "SUCCESS", "transaction_id": tx_code, "amount": parsed["amount"]}


@router.post("/integrations/africas-talking/inbound")
async def africas_talking_inbound(
    payload: dict[str, Any], db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Receive Africa's Talking inbound SMS and auto-credit ledger if payment receipt."""
    parsed = africas_talking_client.parse_inbound_sms(payload)
    if not parsed["is_valid"]:
        return {"status": "IGNORED", "reason": "Not a recognized payment SMS receipt"}

    tx_code = parsed["transaction_code"]
    raw_tx_id = f"AT:{tx_code}:{parsed['amount']}:{parsed['sender_phone']}"
    tx_hash = hashlib.sha256(raw_tx_id.encode("utf-8")).hexdigest()

    ledger = EventLedger(db)
    if not await ledger.check_and_record_idempotency(tx_hash):
        return {"status": "DROPPED", "message": f"Duplicate SMS receipt {tx_code}"}

    user_key = f"sms_{parsed['sender_phone']}".ljust(32, "0")
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=parsed["amount"],
        currency="KES" if parsed["provider"] == "MPESA" else "USD",
        user_public_key=user_key,
        reference=tx_code,
        notes=f"Inbound SMS {parsed['provider']} deposit from {parsed['sender_phone']}",
    )
    sig = sign_payload(_server_signer_priv, payload_obj.model_dump(exclude_none=True))
    signatures_obj = EventSignatures(teller_sig=sig, user_sig=None)

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_model = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.DEPOSIT_MOBILE_MONEY,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    await ledger.append_event(event_model)
    return {
        "status": "SUCCESS",
        "provider": parsed["provider"],
        "receipt": tx_code,
        "amount": parsed["amount"],
    }


# --- SMS Gateway Webhook (from nanocoop-sms-bridge Android receiver) ---


@router.post("/sms/webhook")
async def process_sms_receipt(
    receipt: MobileMoneyWebhookPayload, db: aiosqlite.Connection = Depends(get_db)
) -> Any:
    """Process incoming mobile money SMS receipt with strict SQLite idempotency checks."""
    ledger = EventLedger(db)

    # 1. Deterministic transaction hash for idempotency check
    raw_tx_id = f"{receipt.transaction_code}:{receipt.amount}:{receipt.sender_phone}"
    tx_hash = hashlib.sha256(raw_tx_id.encode("utf-8")).hexdigest()

    # 2. Check & record idempotency cache
    is_new = await ledger.check_and_record_idempotency(tx_hash)
    if not is_new:
        return {
            "status": "DROPPED",
            "message": f"Duplicate transaction {receipt.transaction_code} safely dropped",
            "transaction_hash": tx_hash,
        }

    # 3. Create and append DEPOSIT_MOBILE_MONEY event
    last_event = await ledger.get_last_event()
    previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

    payload_obj = EventPayload(
        amount=receipt.amount,
        currency=receipt.currency,
        user_public_key=receipt.user_public_key,
        reference=receipt.transaction_code,
        notes=f"SMS Deposit from {receipt.sender_phone}",
    )
    signatures_obj = EventSignatures(
        teller_sig=receipt.gateway_signature,
        user_sig=None,
    )

    payload_bytes = serialize_for_hashing(payload_obj.model_dump(exclude_none=True))
    signatures_bytes = serialize_for_hashing(signatures_obj.model_dump(exclude_none=True))
    current_hash = generate_event_hash(previous_hash, payload_bytes, signatures_bytes)

    event_id = str(uuid.uuid4())
    event_model = EventModel(
        event_id=event_id,
        timestamp=receipt.timestamp or int(time.time()),
        event_type=EventType.DEPOSIT_MOBILE_MONEY,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=current_hash,
    )

    await ledger.append_event(event_model)

    return {
        "status": "SUCCESS",
        "message": f"Transaction {receipt.transaction_code} credited successfully",
        "event_id": event_id,
        "current_hash": current_hash,
        "transaction_hash": tx_hash,
    }
