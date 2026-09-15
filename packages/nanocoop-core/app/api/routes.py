"""FastAPI REST API routes for NanoCoop Core."""

import hashlib
import time
import uuid
from typing import Any
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    serialize_for_hashing,
    sign_payload,
)
from app.db.database import get_db
from app.ledger.ledger import (
    ChainIntegrityError,
    CryptographicError,
    DuplicateTransactionError,
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
    MobileMoneyWebhookPayload,
    PaginatedEvents,
)

router = APIRouter()


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
    """Get current account balance computed by state reducer from event stream."""
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
    """Get overall community banking stats, Merkle tree root, and chain validity."""
    ledger = EventLedger(db)
    events = await ledger.get_all_events()
    accounts = await ledger.get_all_account_balances()
    merkle_root = await ledger.get_merkle_root()
    is_valid, _ = await ledger.verify_chain_integrity()

    total_balance = sum(acc["current_balance"] for acc in accounts.values())

    return CommunityStats(
        total_balance=round(total_balance, 2),
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
