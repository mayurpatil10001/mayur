"""
Unit tests for ghost trade import fixes (Trading Evaluator flush, EOD purge, adaptive threshold, pm indentation).

Run: python -m pytest tests/test_ghost_import_fixes.py -v
"""
import datetime
import os
import sys

import pytest

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zoneinfo import ZoneInfo

from trading_platform.services.binary_log_parser import (
    _crosses_daily_close_ny,
    _is_ghost_fill,
    _parse_file_nitro,
    BinaryLogParser,
)

NY_TZ = ZoneInfo("America/New_York")


# --- _crosses_daily_close_ny ---


def test_eod_crosses_boundary_only():
    """Trade that crosses 17:00 NY (entry before, exit after) must be detected for purge."""
    # 16:55 NY -> 17:05 NY: crosses boundary
    base = datetime.datetime(2025, 12, 18, 0, 0, 0, tzinfo=datetime.timezone.utc)
    t1_ny = datetime.datetime(2025, 12, 18, 16, 55, 0, tzinfo=NY_TZ)
    t2_ny = datetime.datetime(2025, 12, 18, 17, 5, 0, tzinfo=NY_TZ)
    t1 = t1_ny.astimezone(datetime.timezone.utc)
    t2 = t2_ny.astimezone(datetime.timezone.utc)
    assert _crosses_daily_close_ny(t1, t2) is True


def test_eod_does_not_over_purge():
    """Trade fully within next session (17:01–17:30 NY) must NOT be purged."""
    t1_ny = datetime.datetime(2025, 12, 18, 17, 1, 0, tzinfo=NY_TZ)
    t2_ny = datetime.datetime(2025, 12, 18, 17, 30, 0, tzinfo=NY_TZ)
    t1 = t1_ny.astimezone(datetime.timezone.utc)
    t2 = t2_ny.astimezone(datetime.timezone.utc)
    assert _crosses_daily_close_ny(t1, t2) is False


def test_eod_no_cross_same_session():
    """Trade 15:00–16:00 NY does not cross 17:00."""
    t1_ny = datetime.datetime(2025, 12, 18, 15, 0, 0, tzinfo=NY_TZ)
    t2_ny = datetime.datetime(2025, 12, 18, 16, 0, 0, tzinfo=NY_TZ)
    t1 = t1_ny.astimezone(datetime.timezone.utc)
    t2 = t2_ny.astimezone(datetime.timezone.utc)
    assert _crosses_daily_close_ny(t1, t2) is False


# --- _is_ghost_fill (note-based ghost detection) ---


def test_ghost_fill_empty_note_is_ghost():
    """Fill with empty note (outside EOD window) is ghost."""
    # 09:05 UTC = 04:05 NY, not in 16:55–17:05
    ts = "2025-12-18T09:05:00"
    assert _is_ghost_fill("V_SIM16", "", ts) is True


def test_ghost_fill_with_note_not_ghost():
    """Fill with strategy note is not ghost."""
    ts = "2025-12-18T09:05:00"
    assert _is_ghost_fill("V_SIM16", "AT_NQ_TM(D-R-2+3)", ts) is False


def test_ghost_fill_eod_exception():
    """Fill at 16:58 NY without note is not ghost (EOD exception)."""
    # 16:58 NY = 21:58 UTC (EST)
    ts = "2025-12-18T21:58:00"
    assert _is_ghost_fill("V_SIM16", "", ts) is False


# --- Trading Evaluator blocked at flush (via _parse_file_nitro) ---


def test_trading_evaluator_blocked_at_flush():
    """Fills with 'trading evaluator' in msgtxt are allowed if they have note or 'text: tag'. Ghosts (no note/tag) must be suggests_ghost."""
    base_paths = [
        "D:\\SierraChart_Simulated_Feed\\TradeActivityLogs",
        os.path.expanduser("~/SierraChart_Simulated_Feed/TradeActivityLogs"),
        os.path.join(os.getcwd(), "TradeActivityLogs"),
    ]
    path = None
    for base in base_paths:
        for ext in ("TradeActivityLog_2025-12-18_UTC.V_SIM16.DATA", "TradeActivityLog_2025-12-18_UTC.V_SIM16.data"):
            candidate = os.path.join(base, ext)
            if os.path.isfile(candidate):
                path = candidate
                break
        if path:
            break
    if not path:
        pytest.skip("V_SIM16 12/18 binary log not found")
    fills, _ = _parse_file_nitro(path, acc_filter=["V_SIM16"])
    for f in fills:
        msgtxt = (f.get("msgtxt") or "").lower()
        if "trading evaluator" not in msgtxt:
            continue
        has_note = bool((f.get("note") or "").strip())
        has_tag_in_msg = "text: tag" in msgtxt or "tag: at_" in msgtxt
        assert has_note or has_tag_in_msg or f.get("suggests_ghost"), (
            "Fill with 'trading evaluator' and no note/tag must be suggests_ghost"
        )


# --- purge_anomalies EOD uses _crosses_daily_close_ny ---


def test_purge_eod_uses_crosses_boundary(tmp_path):
    """purge_anomalies drops only trades that cross 17:00 NY, not trades fully in next session."""
    db_path = str(tmp_path / "test_eod.db")
    conn = __import__("sqlite3").connect(db_path)
    conn.executescript("""
        CREATE TABLE processed_trades (
            trade_id TEXT PRIMARY KEY,
            account_name TEXT, symbol TEXT, entry_time TEXT, exit_time TEXT,
            entry_price REAL, exit_price REAL, quantity INTEGER, side TEXT,
            profit_loss REAL, commission REAL, duration_minutes INTEGER,
            hour_of_day INTEGER, day_of_week INTEGER
        );
    """)
    ny = NY_TZ
    # Trade that crosses 17:00: 16:55 -> 17:05 NY
    t1 = datetime.datetime(2025, 12, 18, 21, 55, 0, tzinfo=datetime.timezone.utc)  # 16:55 NY
    t2 = datetime.datetime(2025, 12, 18, 22, 5, 0, tzinfo=datetime.timezone.utc)  # 17:05 NY
    conn.execute(
        """INSERT INTO processed_trades (
            trade_id, account_name, symbol, entry_time, exit_time,
            entry_price, exit_price, quantity, side, profit_loss, commission,
            duration_minutes, hour_of_day, day_of_week
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("CROSS", "EOD_ACC", "NQ", t1.isoformat(), t2.isoformat(),
         25000.0, 25010.0, 1, "LONG", 100.0, 4.2, 10, 16, 3),
    )
    # Trade fully in next session: 17:01 -> 17:30 NY
    t3 = datetime.datetime(2025, 12, 18, 22, 1, 0, tzinfo=datetime.timezone.utc)
    t4 = datetime.datetime(2025, 12, 18, 22, 30, 0, tzinfo=datetime.timezone.utc)
    conn.execute(
        """INSERT INTO processed_trades (
            trade_id, account_name, symbol, entry_time, exit_time,
            entry_price, exit_price, quantity, side, profit_loss, commission,
            duration_minutes, hour_of_day, day_of_week
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("NO_CROSS", "EOD_ACC", "NQ", t3.isoformat(), t4.isoformat(),
         25010.0, 25020.0, 1, "LONG", 100.0, 4.2, 29, 17, 3),
    )
    conn.commit()
    conn.close()

    parser = BinaryLogParser(db_path=db_path)
    breakdown = parser.purge_anomalies(account="EOD_ACC", purge_overnight=True)
    conn = __import__("sqlite3").connect(db_path)
    remaining = conn.execute(
        "SELECT trade_id FROM processed_trades WHERE account_name = 'EOD_ACC'"
    ).fetchall()
    conn.close()

    # CROSS should be purged, NO_CROSS should remain
    remaining_ids = {r[0] for r in remaining}
    assert "CROSS" not in remaining_ids, "Trade crossing 17:00 NY should be purged"
    assert "NO_CROSS" in remaining_ids, "Trade 17:01–17:30 NY should not be purged"


# --- pm undefined when sh/acc false: no crash ---


def test_parse_file_nitro_no_crash_without_symbol():
    """_parse_file_nitro does not crash when symbol/account missing (pm not used)."""
    # Call with non-existent file; should return [], [] without error
    fills, ghosts = _parse_file_nitro("/nonexistent/path.TEST.data", acc_filter=None)
    assert fills == []
    assert ghosts == []
