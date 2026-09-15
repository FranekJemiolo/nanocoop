"""Concurrency and Idempotency tests proving duplicate protection under race conditions."""

import asyncio
import hashlib
import time
import pytest
import aiosqlite

from app.db.database import CREATE_EVENTS_TABLE, CREATE_IDEMPOTENCY_TABLE
from app.ledger.ledger import EventLedger


@pytest.fixture
async def temp_db(tmp_path):
    """Temporary file-backed SQLite database testing WAL mode concurrency."""
    db_file = str(tmp_path / "concurrency_test.db")
    db = await aiosqlite.connect(db_file)
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA synchronous=NORMAL;")
    await db.executescript(CREATE_EVENTS_TABLE)
    await db.executescript(CREATE_IDEMPOTENCY_TABLE)
    await db.commit()
    db.row_factory = aiosqlite.Row
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_concurrent_duplicate_sms_requests(temp_db):
    """Simulate 5 identical SMS transactions fired asynchronously within 1ms.

    Proves that the SQLite Idempotency Cache records exactly 1 success and drops the 4 duplicates.
    """
    raw_tx = "MPESA98765:50.0:+254712345678"
    tx_hash = hashlib.sha256(raw_tx.encode("utf-8")).hexdigest()

    async def fire_duplicate():
        ledger = EventLedger(temp_db)
        return await ledger.check_and_record_idempotency(tx_hash)

    # Fire 5 tasks concurrently in asyncio event loop
    results = await asyncio.gather(*(fire_duplicate() for _ in range(5)))

    # Exactly one must succeed (True), and exactly four must be dropped (False)
    successes = [r for r in results if r is True]
    dropped = [r for r in results if r is False]

    assert len(successes) == 1, "Only one transaction should be processed"
    assert len(dropped) == 4, "Remaining 4 duplicate requests must be safely dropped"

    # Verify database contents
    cursor = await temp_db.execute(
        "SELECT * FROM idempotency_cache WHERE transaction_hash = ?", (tx_hash,)
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "SUCCESS"
