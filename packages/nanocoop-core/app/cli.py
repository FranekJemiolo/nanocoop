"""NanoCoop Administrative Command Line Interface (CLI).

Provides terminal commands for cooperative officers, field treasurers, and developers:
- nanocoop verify: Cryptographic chain integrity check
- nanocoop stats: Community financial health & Merkle root
- nanocoop create-member: Generate cryptographic keypair and member passbook credentials
- nanocoop passbook <pubkey>: Print member transaction passbook statement
- nanocoop seed: Pre-populate cooperative with initial members and transactions
"""

import argparse
import asyncio
import sys
import time
import uuid
from typing import Sequence

from app.core.config import settings
from app.core.crypto import (
    GENESIS_HASH,
    generate_event_hash,
    generate_keypair,
    serialize_for_hashing,
    sign_payload,
)
from app.db.database import get_db_connection, init_db
from app.ledger.ledger import EventLedger
from app.ledger.schema import (
    EventModel,
    EventPayload,
    EventSignatures,
    EventType,
)


async def cmd_verify(db_path: str | None = None) -> int:
    """Verify cryptographic integrity of entire ledger chain."""
    path = db_path or settings.DB_PATH
    await init_db(path)
    db = await get_db_connection(path)
    try:
        ledger = EventLedger(db)
        is_valid, details = await ledger.verify_chain_integrity()
        root = await ledger.get_merkle_root()
        count = await ledger.get_event_count()

        print("==================================================")
        print("  NanoCoop Cryptographic Chain Integrity Auditor  ")
        print("==================================================")
        print(f"Total Block Events: {count}")
        print(f"Merkle Tree Root:   {root}")
        if is_valid:
            print("Cryptographic Chain: VERIFIED ✓ (Zero tampering detected)")
            return 0
        else:
            print(f"Cryptographic Chain: CORRUPTED ✗ - {details}")
            return 1
    finally:
        await db.close()


async def cmd_stats(db_path: str | None = None) -> int:
    """Print VSLA community financial health metrics."""
    path = db_path or settings.DB_PATH
    await init_db(path)
    db = await get_db_connection(path)
    try:
        ledger = EventLedger(db)
        metrics = await ledger.get_community_metrics()
        accounts = await ledger.get_all_account_balances()
        count = await ledger.get_event_count()
        root = await ledger.get_merkle_root()

        print("==================================================")
        print("         NanoCoop VSLA Community Portfolio        ")
        print("==================================================")
        print(f"Total Active Members:     {len(accounts)}")
        print(f"Total Member Savings:     ${metrics['total_savings']:.2f}")
        print(f"Active Loans Outstanding: ${metrics['total_loans_outstanding']:.2f}")
        print(f"Social Welfare Fund:      ${metrics['total_social_fund']:.2f}")
        print(f"Total Cooperative Capital:${metrics['total_capital']:.2f}")
        print(f"Total Ledger Events:      {count}")
        print(f"Merkle Tree Root:         {root[:16]}...{root[-8:]}")
        print("==================================================")
        return 0
    finally:
        await db.close()


def cmd_create_member(name: str) -> dict[str, str]:
    """Generate new cryptographic credentials for a cooperative member."""
    priv_hex, pub_hex = generate_keypair()
    print("==================================================")
    print("      New Cooperative Member Credentials Generated ")
    print("==================================================")
    print(f"Member Name:  {name}")
    print(f"Public Key:   {pub_hex}")
    print(f"Private Key:  {priv_hex}")
    print("--------------------------------------------------")
    print("IMPORTANT: Write private key to NFC tag or print")
    print("as QR smartcard. Keep private key strictly secret.")
    print("==================================================")
    return {"name": name, "public_key": pub_hex, "private_key": priv_hex}


async def cmd_passbook(user_public_key: str, db_path: str | None = None) -> int:
    """Print member passbook transaction history and current standing."""
    path = db_path or settings.DB_PATH
    await init_db(path)
    db = await get_db_connection(path)
    try:
        ledger = EventLedger(db)
        state = await ledger.get_user_balance(user_public_key)
        all_events = await ledger.get_all_events()

        member_events = [
            e for e in all_events if e.get("payload", {}).get("user_public_key") == user_public_key
        ]

        print("==================================================")
        print(f" Member Passbook: {user_public_key[:12]}...{user_public_key[-6:]} ")
        print("==================================================")
        print(f"Savings Balance:       ${state['savings_balance']:.2f}")
        print(f"Outstanding Loan Debt: ${state['loan_balance']:.2f}")
        print(f"Social Contributions:  ${state['social_fund_contributions']:.2f}")
        print(f"Net Financial Standing:${state['net_balance']:.2f}")
        print("--------------------------------------------------")
        print("Historical Transactions:")
        for ev in member_events:
            ts = ev.get("timestamp", 0)
            etype = ev.get("event_type", "UNKNOWN")
            amt = ev.get("payload", {}).get("amount", 0.0)
            notes = ev.get("payload", {}).get("notes", "")
            h = ev.get("current_hash", "")[:8]
            print(f" [{ts}] {etype:<22} ${amt:>7.2f} (Hash:{h}..) {notes}")
        print("==================================================")
        return 0
    finally:
        await db.close()


async def cmd_seed(db_path: str | None = None) -> int:
    """Seed cooperative ledger with initial realistic members and transactions."""
    path = db_path or settings.DB_PATH
    await init_db(path)
    db = await get_db_connection(path)
    try:
        ledger = EventLedger(db)
        existing_count = await ledger.get_event_count()
        if existing_count > 0:
            print(f"Ledger already contains {existing_count} events. Skipping seed.")
            return 0

        teller_priv, _ = generate_keypair()
        m1_priv, m1_pub = generate_keypair()
        m2_priv, m2_pub = generate_keypair()

        # Event 1: Member 1 Initial Savings Deposit
        p1 = EventPayload(
            amount=100.0,
            currency="USD",
            user_public_key=m1_pub,
            notes="Initial cycle savings deposit",
        )
        s1 = EventSignatures(
            teller_sig=sign_payload(teller_priv, p1.model_dump(exclude_none=True)),
            user_sig=sign_payload(m1_priv, p1.model_dump(exclude_none=True)),
        )
        h1 = generate_event_hash(
            GENESIS_HASH,
            serialize_for_hashing(p1.model_dump(exclude_none=True)),
            serialize_for_hashing(s1.model_dump(exclude_none=True)),
        )
        ev1 = EventModel(
            event_id=str(uuid.uuid4()),
            timestamp=int(time.time()) - 3600,
            event_type=EventType.DEPOSIT_CASH,
            payload=p1,
            previous_hash=GENESIS_HASH,
            signatures=s1,
            current_hash=h1,
        )
        await ledger.append_event(ev1)

        # Event 2: Member 2 Mobile Money Deposit
        p2 = EventPayload(
            amount=75.0,
            currency="USD",
            user_public_key=m2_pub,
            reference="MPESA7788",
            notes="M-Pesa deposit from +254712345678",
        )
        s2 = EventSignatures(
            teller_sig=sign_payload(teller_priv, p2.model_dump(exclude_none=True)),
            user_sig=None,
        )
        h2 = generate_event_hash(
            h1,
            serialize_for_hashing(p2.model_dump(exclude_none=True)),
            serialize_for_hashing(s2.model_dump(exclude_none=True)),
        )
        ev2 = EventModel(
            event_id=str(uuid.uuid4()),
            timestamp=int(time.time()) - 1800,
            event_type=EventType.DEPOSIT_MOBILE_MONEY,
            payload=p2,
            previous_hash=h1,
            signatures=s2,
            current_hash=h2,
        )
        await ledger.append_event(ev2)

        # Event 3: Member 1 Micro-loan Disbursed
        p3 = EventPayload(
            amount=50.0,
            currency="USD",
            user_public_key=m1_pub,
            loan_id="LOAN-001",
            interest_rate=5.0,
            term_months=3,
            notes="Farm fertilizer micro-loan",
        )
        s3 = EventSignatures(
            teller_sig=sign_payload(teller_priv, p3.model_dump(exclude_none=True)),
            user_sig=sign_payload(m1_priv, p3.model_dump(exclude_none=True)),
        )
        h3 = generate_event_hash(
            h2,
            serialize_for_hashing(p3.model_dump(exclude_none=True)),
            serialize_for_hashing(s3.model_dump(exclude_none=True)),
        )
        ev3 = EventModel(
            event_id=str(uuid.uuid4()),
            timestamp=int(time.time()) - 600,
            event_type=EventType.LOAN_DISBURSED,
            payload=p3,
            previous_hash=h2,
            signatures=s3,
            current_hash=h3,
        )
        await ledger.append_event(ev3)

        # Event 4: Member 2 Social Welfare Contribution
        p4 = EventPayload(
            amount=10.0,
            currency="USD",
            user_public_key=m2_pub,
            notes="Weekly emergency safety net contribution",
        )
        s4 = EventSignatures(
            teller_sig=sign_payload(teller_priv, p4.model_dump(exclude_none=True)),
            user_sig=None,
        )
        h4 = generate_event_hash(
            h3,
            serialize_for_hashing(p4.model_dump(exclude_none=True)),
            serialize_for_hashing(s4.model_dump(exclude_none=True)),
        )
        ev4 = EventModel(
            event_id=str(uuid.uuid4()),
            timestamp=int(time.time()),
            event_type=EventType.SOCIAL_FUND_CONTRIBUTION,
            payload=p4,
            previous_hash=h3,
            signatures=s4,
            current_hash=h4,
        )
        await ledger.append_event(ev4)

        print("==================================================")
        print("  Cooperative Seeded with Initial Demo Ledger     ")
        print("==================================================")
        print("Seeded 4 events:")
        print(" 1. Member 1: $100.00 cash deposit")
        print(" 2. Member 2: $75.00 mobile money deposit")
        print(" 3. Member 1: $50.00 micro-loan disbursed (5% interest)")
        print(" 4. Member 2: $10.00 emergency safety net contribution")
        print("==================================================")
        return 0
    finally:
        await db.close()


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nanocoop",
        description="NanoCoop Cryptographic Community Banking Engine CLI",
    )
    parser.add_argument("--db-path", help="Path to SQLite database", default=None)
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    subparsers.add_parser("verify", help="Verify cryptographic chain integrity")
    subparsers.add_parser("stats", help="Show community portfolio metrics")

    parser_create = subparsers.add_parser("create-member", help="Create member credentials")
    parser_create.add_argument("--name", default="Member", help="Member name")

    parser_pb = subparsers.add_parser("passbook", help="View member passbook")
    parser_pb.add_argument("public_key", help="User Ed25519 public key")

    subparsers.add_parser("seed", help="Seed cooperative with demo members & transactions")

    return parser.parse_args(args)


async def async_main(args: Sequence[str] | None = None) -> int:
    parsed = parse_args(args)
    cmd = parsed.command

    if cmd == "verify":
        return await cmd_verify(parsed.db_path)
    elif cmd == "stats":
        return await cmd_stats(parsed.db_path)
    elif cmd == "create-member":
        cmd_create_member(parsed.name)
        return 0
    elif cmd == "passbook":
        return await cmd_passbook(parsed.public_key, parsed.db_path)
    elif cmd == "seed":
        return await cmd_seed(parsed.db_path)
    else:
        print("NanoCoop CLI - use --help for usage instructions")
        return 0


def main(args: Sequence[str] | None = None) -> int:
    return asyncio.run(async_main(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
