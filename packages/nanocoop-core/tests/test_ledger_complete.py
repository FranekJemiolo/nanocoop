"""Exhaustive unit tests for ledger, schema validation, and database connection."""

import json
import time
import uuid
import aiosqlite
import pytest

from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    generate_keypair,
    serialize_for_hashing,
    sign_payload,
)
from app.db.database import get_db, get_db_connection, init_db
from app.ledger.ledger import (
    ChainIntegrityError,
    CryptographicError,
    EventLedger,
)
from app.ledger.schema import (
    EventModel,
    EventPayload,
    EventSignatures,
    EventType,
)


@pytest.fixture
async def memory_db(tmp_path):
    db_path = str(tmp_path / "test_ledger_complete.db")
    await init_db(db_path)
    db = await get_db_connection(db_path)
    yield db
    await db.close()


def create_signed_event(
    user_priv: str,
    teller_priv: str,
    user_pub: str,
    event_type: EventType,
    amount: float,
    previous_hash: str,
    include_user_sig: bool = True,
    include_teller_sig: bool = True,
    bad_hash: bool = False,
    notes: str | None = None,
) -> EventModel:
    payload_obj = EventPayload(
        amount=amount,
        currency="USD",
        user_public_key=user_pub,
        notes=notes,
    )
    payload_dict = payload_obj.model_dump(exclude_none=True)

    user_sig = sign_payload(user_priv, payload_dict) if include_user_sig else None
    teller_sig = sign_payload(teller_priv, payload_dict) if include_teller_sig else ""

    signatures_obj = EventSignatures(
        teller_sig=teller_sig or ("0" * 64),
        user_sig=user_sig,
    )
    sig_dict = signatures_obj.model_dump(exclude_none=True)

    p_bytes = serialize_for_hashing(payload_dict)
    s_bytes = serialize_for_hashing(sig_dict)
    c_hash = "badhash" * 8 if bad_hash else generate_event_hash(previous_hash, p_bytes, s_bytes)

    return EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=event_type,
        payload=payload_obj,
        previous_hash=previous_hash,
        signatures=signatures_obj,
        current_hash=c_hash,
    )


async def test_schema_event_id_validation():
    user_priv, user_pub = generate_keypair()
    teller_priv, _ = generate_keypair()

    with pytest.raises(ValueError, match="Invalid event_id"):
        EventModel(
            event_id="short",  # Less than 8 chars
            timestamp=123,
            event_type=EventType.DEPOSIT_CASH,
            payload=EventPayload(amount=10.0, user_public_key=user_pub),
            previous_hash=GENESIS_HASH,
            signatures=EventSignatures(teller_sig="0" * 64, user_sig="0" * 64),
            current_hash="0" * 64,
        )


async def test_ledger_current_hash_mismatch(memory_db):
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, _ = generate_keypair()

    bad_event = create_signed_event(
        u_priv, t_priv, u_pub, EventType.DEPOSIT_CASH, 50.0, GENESIS_HASH, bad_hash=True
    )
    with pytest.raises(CryptographicError, match="current_hash mismatch"):
        await ledger.append_event(bad_event)


async def test_ledger_missing_or_bad_signatures(memory_db):
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    other_priv, _ = generate_keypair()
    t_priv, _ = generate_keypair()

    # 1. Missing user signature on LOAN_DISBURSED
    ev_no_user_sig = create_signed_event(
        u_priv, t_priv, u_pub, EventType.LOAN_DISBURSED, 100.0, GENESIS_HASH, include_user_sig=False
    )
    with pytest.raises(CryptographicError, match="requires user signature"):
        await ledger.append_event(ev_no_user_sig)

    # 2. Bad user signature on SOCIAL_FUND_PAYOUT
    ev_bad_user_sig = create_signed_event(
        other_priv, t_priv, u_pub, EventType.SOCIAL_FUND_PAYOUT, 40.0, GENESIS_HASH
    )
    with pytest.raises(CryptographicError, match="Invalid user signature"):
        await ledger.append_event(ev_bad_user_sig)

    # 3. Missing gateway signature on DEPOSIT_MOBILE_MONEY
    payload_obj = EventPayload(amount=20.0, user_public_key=u_pub)
    sig_obj = EventSignatures(teller_sig="a" * 64, user_sig=None)
    payload_dict = payload_obj.model_dump(exclude_none=True)
    p_bytes = serialize_for_hashing(payload_dict)
    sig_empty_dict = {"teller_sig": ""}
    s_empty_bytes = serialize_for_hashing(sig_empty_dict)
    c_hash_empty = generate_event_hash(GENESIS_HASH, p_bytes, s_empty_bytes)

    ev_mobile_no_sig = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.DEPOSIT_MOBILE_MONEY,
        payload=payload_obj,
        previous_hash=GENESIS_HASH,
        signatures=sig_obj,
        current_hash=c_hash_empty,
    )
    ev_mobile_no_sig.signatures.teller_sig = ""
    with pytest.raises(CryptographicError, match="Gateway signature is required"):
        await ledger.verify_event(ev_mobile_no_sig)

    # 4. Missing teller signature on LOAN_REPAID
    ev_repay_no_sig = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.LOAN_REPAID,
        payload=payload_obj,
        previous_hash=GENESIS_HASH,
        signatures=sig_obj,
        current_hash=c_hash_empty,
    )
    ev_repay_no_sig.signatures.teller_sig = ""
    with pytest.raises(CryptographicError, match="Teller signature is required"):
        await ledger.verify_event(ev_repay_no_sig)

    # 5. Bad user signature on LOAN_REPAID with optional user_sig provided
    ev_repay_bad_user = create_signed_event(
        other_priv, t_priv, u_pub, EventType.LOAN_REPAID, 50.0, GENESIS_HASH
    )
    with pytest.raises(CryptographicError, match="Invalid user signature"):
        await ledger.append_event(ev_repay_bad_user)

    # 6. Valid user signature but empty teller signature on DEPOSIT_CASH
    payload_cash = EventPayload(amount=30.0, user_public_key=u_pub)
    valid_u_sig = sign_payload(u_priv, payload_cash.model_dump(exclude_none=True))
    p_bytes = serialize_for_hashing(payload_cash.model_dump(exclude_none=True))
    s_bytes = serialize_for_hashing({"teller_sig": "", "user_sig": valid_u_sig})
    c_hash_no_teller = generate_event_hash(GENESIS_HASH, p_bytes, s_bytes)
    ev_no_teller = EventModel(
        event_id=str(uuid.uuid4()),
        timestamp=int(time.time()),
        event_type=EventType.DEPOSIT_CASH,
        payload=payload_cash,
        previous_hash=GENESIS_HASH,
        signatures=EventSignatures(teller_sig="a" * 64, user_sig=valid_u_sig),
        current_hash=c_hash_no_teller,
    )
    ev_no_teller.signatures.teller_sig = ""
    with pytest.raises(CryptographicError, match="Teller signature is required"):
        await ledger.verify_event(ev_no_teller)


async def test_ledger_chain_break_and_metrics(memory_db):
    ledger = EventLedger(memory_db)
    u_priv, u_pub = generate_keypair()
    t_priv, _ = generate_keypair()

    # Append valid event 1
    ev1 = create_signed_event(u_priv, t_priv, u_pub, EventType.DEPOSIT_CASH, 100.0, GENESIS_HASH)
    await ledger.append_event(ev1)

    # Append valid event 2
    ev2 = create_signed_event(
        u_priv, t_priv, u_pub, EventType.SOCIAL_FUND_CONTRIBUTION, 15.0, ev1.current_hash
    )
    await ledger.append_event(ev2)

    # Check community metrics
    metrics = await ledger.get_community_metrics()
    assert metrics["total_savings"] == 100.0
    assert metrics["total_social_fund"] == 15.0
    assert metrics["total_capital"] == 115.0

    # Corrupt event 2 previous_hash in the database to test verify_chain_integrity failure branch
    await memory_db.execute(
        "UPDATE events SET previous_hash = 'tampered_previous_hash' WHERE id = 2"
    )
    await memory_db.commit()

    is_valid, details = await ledger.verify_chain_integrity()
    assert not is_valid
    assert "Hash break at event" in details


async def test_database_get_db_generator(tmp_path):
    """Verify that get_db generator properly opens and closes a connection."""
    test_db_path = str(tmp_path / "test_get_db.db")
    await init_db(test_db_path)

    import app.core.config

    old_path = app.core.config.settings.DB_PATH
    app.core.config.settings.DB_PATH = test_db_path
    try:
        gen = get_db()
        db = await anext(gen)
        assert isinstance(db, aiosqlite.Connection)
        cursor = await db.execute("SELECT 1")
        row = await cursor.fetchone()
        assert row[0] == 1
        try:
            await anext(gen)
        except StopAsyncIteration:
            pass
    finally:
        app.core.config.settings.DB_PATH = old_path
