"""Tests for NanoCoop Administrative CLI."""

import json
from unittest.mock import patch
import aiosqlite
import pytest
from app.cli import async_main, main
from app.db.database import init_db


async def test_cli_lifecycle(tmp_path, capsys):
    test_db = str(tmp_path / "cli_test.db")
    await init_db(test_db)

    # 1. Test CLI with no arguments
    rc_none = await async_main([])
    assert rc_none == 0

    # 2. Test create-member
    rc_member = await async_main(["create-member", "--name", "Grace Achieng"])
    assert rc_member == 0
    captured_member = capsys.readouterr().out
    assert "Grace Achieng" in captured_member

    # 3. Test seed command
    rc_seed = await async_main(["--db-path", test_db, "seed"])
    assert rc_seed == 0
    captured_seed = capsys.readouterr().out
    assert "Cooperative Seeded" in captured_seed

    # Repeat seed: should report already contains events
    rc_seed_repeat = await async_main(["--db-path", test_db, "seed"])
    assert rc_seed_repeat == 0
    assert "already contains" in capsys.readouterr().out

    # 4. Test verify on valid chain
    rc_verify = await async_main(["--db-path", test_db, "verify"])
    assert rc_verify == 0
    captured_verify = capsys.readouterr().out
    assert "VERIFIED ✓" in captured_verify

    # 5. Test stats command
    rc_stats = await async_main(["--db-path", test_db, "stats"])
    assert rc_stats == 0
    captured_stats = capsys.readouterr().out
    assert "Total Active Members" in captured_stats
    assert "Total Member Savings" in captured_stats

    # 6. Test passbook command
    db = await aiosqlite.connect(test_db)
    cursor = await db.execute("SELECT payload FROM events LIMIT 1")
    row = await cursor.fetchone()
    payload = json.loads(row[0])
    pubkey = payload["user_public_key"]
    await db.close()

    rc_pb = await async_main(["--db-path", test_db, "passbook", pubkey])
    assert rc_pb == 0
    captured_pb = capsys.readouterr().out
    assert "Member Passbook" in captured_pb

    # 7. Test verify failure when chain is corrupted
    db = await aiosqlite.connect(test_db)
    await db.execute("UPDATE events SET previous_hash = 'corrupted_hash' WHERE id = 2")
    await db.commit()
    await db.close()

    rc_fail = await async_main(["--db-path", test_db, "verify"])
    assert rc_fail == 1
    captured_fail = capsys.readouterr().out
    assert "CORRUPTED" in captured_fail

    # 8. Test main() entrypoint wrapper
    with patch("app.cli.async_main", return_value=0):
        with patch("asyncio.run", return_value=0) as mock_run:
            rc_wrapper = main(["verify"])
            assert rc_wrapper == 0
            mock_run.assert_called_once()
