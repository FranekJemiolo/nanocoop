"""Ledger append-only, cryptographic chain integrity, and state reducer unit tests."""

import time
import uuid
import pytest
import aiosqlite

from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    generate_keypair,
    serialize_for_hashing,
    sign_payload,
)
from app.db.database import CREATE_EVENTS_TABLE, CREATE_IDEMPOTENCY_TABLE
from app.ledger.ledger import (
    ChainIntegrityError,
    CryptographicError,
    EventLedger,
)
from app.ledger.reducer import calculate_account_state, calculate_all_accounts
from app.ledger.schema import EventModel, EventPayload, EventSignatures, EventType


@pytest.fixture
async def memory_db():
    """In-memory SQLite fixture with WAL-equivalent tables."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(CREATE_EVENTS_TABLE)
    await db.executescript(CREATE_IDEMPOTENCY_TABLE)
    await db.commit()
    yield db
    await db.close()


def create_mock_event(
    prev_hash: str,
    user_priv: str,
    user_pub: str,
    teller_priv: str,
    amount: float = 50.0,
    event_type: EventType = EventType.DEPOSIT_CASH,
    omit_user_sig: bool = False,
    corrupt_sig: bool = False,
) -> EventModel:
    """Helper to construct signed valid or invalid event models."""
    payload = EventPayload(
        amount=amount,
        currency="USD",
        user_public_key=user_pub,
    )
    payload_dict = payload.model_dump(exclude_none=True)

    teller_sig = sign_payload(teller_priv, payload_dict)

    if omit_user_sig:
        user_sig = None
    elif corrupt_sig:
        user_sig = "ab" * 64
    else:
        user_sig = sign_payload(user_priv, payload_dict)

    signatures = EventSignatures(
        teller_sig=teller_sig,
        user_sig=user_sig,
    )
    signatures_dict = signatures.model_dump(exclude_none=True)

    payload_bytes = serialize_for_hashing(payload_dict)
    signatures_bytes = serialize_for_hashing(signatures_dict)
    current_hash = generate_event_hash(prev_hash, payload_bytes, signatures_bytes)

    return EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=event_type,
        payload=payload,
        previous_hash=prev_hash,
        signatures=signatures,
        current_hash=current_hash,
    )


@pytest.mark.asyncio
async def test_append_valid_event(memory_db):
    """Verify appending a valid dual-signed event succeeds."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    event = create_mock_event(GENESIS_HASH, u_priv, u_pub, t_priv, amount=100.0)
    appended = await ledger.append_event(event)

    assert appended.event_id == event.event_id
    assert await ledger.get_event_count() == 1

    last = await ledger.get_last_event()
    assert last is not None
    assert last["current_hash"] == event.current_hash


@pytest.mark.asyncio
async def test_missing_user_signature_rejected(memory_db):
    """Proving missing user signature rejects the transaction."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    event = create_mock_event(GENESIS_HASH, u_priv, u_pub, t_priv, amount=50.0, omit_user_sig=True)

    with pytest.raises(CryptographicError, match="requires user signature"):
        await ledger.append_event(event)


@pytest.mark.asyncio
async def test_invalid_user_signature_rejected(memory_db):
    """Proving invalid user signature rejects the transaction."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    event = create_mock_event(GENESIS_HASH, u_priv, u_pub, t_priv, amount=50.0, corrupt_sig=True)

    with pytest.raises(CryptographicError, match="Invalid user signature"):
        await ledger.append_event(event)


@pytest.mark.asyncio
async def test_previous_hash_mismatch_rejected(memory_db):
    """Proving broken previous_hash is rejected."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    # Provide fake previous hash when ledger is empty (expects GENESIS_HASH)
    event = create_mock_event("f" * 64, u_priv, u_pub, t_priv, amount=50.0)

    with pytest.raises(ChainIntegrityError, match="previous_hash mismatch"):
        await ledger.append_event(event)


@pytest.mark.asyncio
async def test_tampering_with_past_event_invalidates_chain(memory_db):
    """Proving that tampering with a past event invalidates the cryptographic chain."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    # Append Event 1
    ev1 = create_mock_event(GENESIS_HASH, u_priv, u_pub, t_priv, amount=100.0)
    await ledger.append_event(ev1)

    # Append Event 2
    ev2 = create_mock_event(ev1.current_hash, u_priv, u_pub, t_priv, amount=50.0)
    await ledger.append_event(ev2)

    # Chain should initially be valid
    is_valid, err = await ledger.verify_chain_integrity()
    assert is_valid is True
    assert err is None

    # Directly tamper with Event 1's payload in the SQLite table (e.g. modify amount to 1000)
    await memory_db.execute(
        """
        UPDATE events 
        SET payload = '{"amount":1000.0,"currency":"USD","user_public_key":"' || ? || '"}'
        WHERE event_id = ?
        """,
        (u_pub, ev1.event_id),
    )
    await memory_db.commit()

    # Chain integrity check must now detect tampering
    is_valid_after_tamper, tamper_details = await ledger.verify_chain_integrity()
    assert is_valid_after_tamper is False
    assert "Tampered content" in tamper_details


@pytest.mark.asyncio
async def test_state_reducer_balances(memory_db):
    """Test state reducer calculation across deposits, withdrawals, and interest."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    # 1. Deposit $100
    ev1 = create_mock_event(
        GENESIS_HASH, u_priv, u_pub, t_priv, amount=100.0, event_type=EventType.DEPOSIT_CASH
    )
    await ledger.append_event(ev1)

    # 2. Deposit $50
    ev2 = create_mock_event(
        ev1.current_hash, u_priv, u_pub, t_priv, amount=50.0, event_type=EventType.DEPOSIT_CASH
    )
    await ledger.append_event(ev2)

    # 3. Withdraw $30
    ev3 = create_mock_event(
        ev2.current_hash, u_priv, u_pub, t_priv, amount=30.0, event_type=EventType.WITHDRAWAL_CASH
    )
    await ledger.append_event(ev3)

    account_state = await ledger.get_user_balance(u_pub)
    assert account_state["current_balance"] == 120.0
    assert account_state["user_public_key"] == u_pub


@pytest.mark.asyncio
async def test_cursor_pagination(memory_db):
    """Verify cursor-based pagination over ledger events."""
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, t_pub = generate_keypair()

    prev = GENESIS_HASH
    for i in range(5):
        ev = create_mock_event(prev, u_priv, u_pub, t_priv, amount=10.0 + i)
        await ledger.append_event(ev)
        prev = ev.current_hash

    # Fetch page 1 (limit 2)
    p1_events, p1_cursor, p1_has_more, total = await ledger.get_events(cursor=None, limit=2)
    assert len(p1_events) == 2
    assert p1_has_more is True
    assert total == 5
    assert p1_cursor is not None

    # Fetch page 2 (limit 2)
    p2_events, p2_cursor, p2_has_more, _ = await ledger.get_events(cursor=p1_cursor, limit=2)
    assert len(p2_events) == 2
    assert p2_has_more is True

    # Fetch page 3 (limit 2) -> only 1 remaining
    p3_events, p3_cursor, p3_has_more, _ = await ledger.get_events(cursor=p2_cursor, limit=2)
    assert len(p3_events) == 1
    assert p3_has_more is False
    assert p3_cursor is None
