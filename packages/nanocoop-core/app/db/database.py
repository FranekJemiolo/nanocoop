"""SQLite Database layer using aiosqlite with WAL mode and resilient crash recovery."""

import aiosqlite
from typing import AsyncGenerator
from app.core.config import settings

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    timestamp INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    signatures TEXT NOT NULL,
    current_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_id ON events (id);
CREATE INDEX IF NOT EXISTS idx_events_event_id ON events (event_id);
CREATE INDEX IF NOT EXISTS idx_events_current_hash ON events (current_hash);
"""

CREATE_IDEMPOTENCY_TABLE = """
CREATE TABLE IF NOT EXISTS idempotency_cache (
    transaction_hash TEXT PRIMARY KEY,
    processed_at INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('SUCCESS', 'DROPPED'))
);
"""


async def get_db_connection(db_path: str | None = None) -> aiosqlite.Connection:
    """Open an aiosqlite connection and configure WAL mode and NORMAL synchronous."""
    path = db_path or settings.DB_PATH
    db = await aiosqlite.connect(path)
    # Enable WAL mode and synchronous=NORMAL for high throughput and power failure resilience
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA synchronous=NORMAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    db.row_factory = aiosqlite.Row
    return db


async def init_db(db_path: str | None = None) -> None:
    """Initialize database schemas and tables."""
    db = await get_db_connection(db_path)
    try:
        await db.executescript(CREATE_EVENTS_TABLE)
        await db.executescript(CREATE_IDEMPOTENCY_TABLE)
        await db.commit()
    finally:
        await db.close()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """FastAPI dependency yielding a configured aiosqlite connection."""
    db = await get_db_connection()
    try:
        yield db
    finally:
        await db.close()
