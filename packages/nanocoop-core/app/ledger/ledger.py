"""EventLedger core engine managing append-only storage, Merkle tree hashing, and multi-sig authorization."""

import json
import time
from typing import Any
import aiosqlite

from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    serialize_for_hashing,
    verify_signature,
    compute_merkle_root,
)
from app.ledger.schema import EventModel, EventType
from app.ledger.reducer import calculate_account_state, calculate_all_accounts


class LedgerError(Exception):
    """Base exception for ledger operations."""


class CryptographicError(LedgerError):
    """Raised when signatures or hashes fail cryptographic verification."""


class ChainIntegrityError(LedgerError):
    """Raised when previous_hash or block chain integrity is broken."""


class DuplicateTransactionError(LedgerError):
    """Raised when an idempotency conflict is detected."""


class EventLedger:
    """Manages the append-only event-sourced ledger backed by SQLite in WAL mode."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_last_event(self) -> dict[str, Any] | None:
        """Fetch the most recent event from the ledger."""
        cursor = await self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_event_dict(row)

    async def get_event_count(self) -> int:
        """Get the total count of events in the ledger."""
        cursor = await self.db.execute("SELECT COUNT(*) as cnt FROM events")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def verify_event(self, event: EventModel) -> None:
        """Cryptographically verify an event before appending it to the log."""
        # 1. Verify previous_hash matches the actual tip of the chain
        last_event = await self.get_last_event()
        expected_previous_hash = last_event["current_hash"] if last_event else GENESIS_HASH

        if event.previous_hash != expected_previous_hash:
            raise ChainIntegrityError(
                f"previous_hash mismatch. Expected {expected_previous_hash}, got {event.previous_hash}"
            )

        # 2. Verify deterministic current_hash
        payload_dict = event.payload.model_dump(exclude_none=True)
        signatures_dict = event.signatures.model_dump(exclude_none=True)

        payload_bytes = serialize_for_hashing(payload_dict)
        signatures_bytes = serialize_for_hashing(signatures_dict)

        expected_hash = generate_event_hash(event.previous_hash, payload_bytes, signatures_bytes)
        if event.current_hash != expected_hash:
            raise CryptographicError(
                f"current_hash mismatch. Expected {expected_hash}, got {event.current_hash}"
            )

        # 3. Verify signatures based on event type
        # For cash transactions (DEPOSIT_CASH, WITHDRAWAL_CASH), dual signatures are strictly mandatory:
        # - user_sig signed by the customer via NFC/QR
        # - teller_sig signed by the authorized teller
        if event.event_type in (EventType.DEPOSIT_CASH, EventType.WITHDRAWAL_CASH):
            if not event.signatures.user_sig:
                raise CryptographicError(
                    f"Transaction type {event.event_type.value} requires user signature via NFC/QR"
                )

            # Verify user signature
            user_valid = verify_signature(
                public_key_hex=event.payload.user_public_key,
                payload=payload_dict,
                signature_hex=event.signatures.user_sig,
            )
            if not user_valid:
                raise CryptographicError("Invalid user signature on payload")

            # Teller signature validation
            if not event.signatures.teller_sig:
                raise CryptographicError("Teller signature is required")

        elif event.event_type == EventType.DEPOSIT_MOBILE_MONEY:
            if not event.signatures.teller_sig:
                raise CryptographicError("Gateway signature is required for mobile money")

    async def append_event(self, event: EventModel) -> EventModel:
        """Verify and atomically append an event to the ledger."""
        await self.verify_event(event)

        payload_json = json.dumps(event.payload.model_dump(exclude_none=True))
        signatures_json = json.dumps(event.signatures.model_dump(exclude_none=True))

        await self.db.execute(
            """
            INSERT INTO events (event_id, timestamp, event_type, payload, previous_hash, signatures, current_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.timestamp,
                event.event_type.value,
                payload_json,
                event.previous_hash,
                signatures_json,
                event.current_hash,
            ),
        )
        await self.db.commit()
        return event

    async def get_events(
        self, cursor: int | None = None, limit: int = 50
    ) -> tuple[list[dict[str, Any]], int | None, bool, int]:
        """Cursor-based pagination over ledger events ordered by chronological ID."""
        total_count = await self.get_event_count()

        if cursor is not None:
            query = "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT ?"
            params = (cursor, limit + 1)
        else:
            query = "SELECT * FROM events ORDER BY id ASC LIMIT ?"
            params = (limit + 1,)

        cursor_obj = await self.db.execute(query, params)
        rows = await cursor_obj.fetchall()

        has_more = len(rows) > limit
        result_rows = rows[:limit] if has_more else rows

        events = [self._row_to_event_dict(r) for r in result_rows]
        next_cursor = result_rows[-1]["id"] if (has_more and result_rows) else None

        return events, next_cursor, has_more, total_count

    async def get_all_events(self) -> list[dict[str, Any]]:
        """Fetch all events in chronological order."""
        cursor = await self.db.execute("SELECT * FROM events ORDER BY id ASC")
        rows = await cursor.fetchall()
        return [self._row_to_event_dict(r) for r in rows]

    async def get_user_balance(self, user_public_key: str) -> dict[str, Any]:
        """Compute user's balance and state from event stream using state reducer."""
        events = await self.get_all_events()
        return calculate_account_state(user_public_key, events)

    async def get_all_account_balances(self) -> dict[str, dict[str, Any]]:
        """Compute balances for all accounts across the cooperative."""
        events = await self.get_all_events()
        return calculate_all_accounts(events)

    async def get_merkle_root(self) -> str:
        """Compute the Merkle tree root of all event hashes in the ledger."""
        cursor = await self.db.execute("SELECT current_hash FROM events ORDER BY id ASC")
        rows = await cursor.fetchall()
        hashes = [r["current_hash"] for r in rows]
        return compute_merkle_root(hashes)

    async def verify_chain_integrity(self) -> tuple[bool, str | None]:
        """Verify the integrity of the entire cryptographic chain."""
        cursor = await self.db.execute("SELECT * FROM events ORDER BY id ASC")
        rows = await cursor.fetchall()

        expected_prev = GENESIS_HASH

        for row in rows:
            ev = self._row_to_event_dict(row)
            if ev["previous_hash"] != expected_prev:
                return (
                    False,
                    f"Hash break at event {ev['event_id']}: expected prev {expected_prev}, got {ev['previous_hash']}",
                )

            # Recalculate hash from stored payload and signatures
            payload_bytes = serialize_for_hashing(ev["payload"])
            signatures_bytes = serialize_for_hashing(ev["signatures"])
            recomputed = generate_event_hash(ev["previous_hash"], payload_bytes, signatures_bytes)

            if ev["current_hash"] != recomputed:
                return (
                    False,
                    f"Tampered content at event {ev['event_id']}: stored hash {ev['current_hash']} != calculated {recomputed}",
                )

            expected_prev = ev["current_hash"]

        return True, None

    async def check_and_record_idempotency(self, transaction_hash: str) -> bool:
        """Check if transaction hash already processed; if not, atomically record it.

        Returns True if newly inserted, False if already processed (dropped duplicate).
        """
        now = int(time.time())
        try:
            await self.db.execute(
                """
                INSERT INTO idempotency_cache (transaction_hash, processed_at, status)
                VALUES (?, ?, 'SUCCESS')
                """,
                (transaction_hash, now),
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Duplicate key violation
            return False

    def _row_to_event_dict(self, row: aiosqlite.Row) -> dict[str, Any]:
        """Convert SQLite row to event dictionary with parsed payload and signatures."""
        return {
            "id": row["id"],
            "event_id": row["event_id"],
            "timestamp": row["timestamp"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]),
            "previous_hash": row["previous_hash"],
            "signatures": json.loads(row["signatures"]),
            "current_hash": row["current_hash"],
        }
