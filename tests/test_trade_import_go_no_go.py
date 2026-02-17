"""
Go/No-Go Test Suite — Phase 1: Trade Import

Tests the trade import service with known pass/fail metrics.
Run:  python -m pytest tests/test_trade_import_go_no_go.py -v --tb=short

Go/No-Go Metrics
────────────────
1. Parse valid 26-col text         → 100% of valid rows parsed without error
2. Parse handles malformed rows    → Malformed rows in errors[], no crash
3. Deduplication                   → Re-import same data → 0 new trades
4. Account extraction              → account_name equals full Note column value
5. Empty input                     → Returns empty results, no crash
6. Base symbol extraction          → F.US.MNQH23 → MNQ, NQH24 → NQ
7. DateTime parsing                → Handles BP/EP markers + all formats
8. Float parsing                   → Handles trailing " F" and "%" markers
"""

import os
import sys
import sqlite3
import tempfile
import pytest

# ── ensure project root is importable ──────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading_platform.services.trade_import_service import (
    TradeImportService,
    ImportResult,
    ParsedTrade,
)


# ──────────────────────────────────────────────────────────────
# Test fixtures
# ──────────────────────────────────────────────────────────────

SAMPLE_HEADER = (
    "Symbol\tTrade Type\tEntry DateTime\tEntry Price\tExit DateTime\t"
    "Exit Price\tTrade Quantity\tMax Open Quantity\tMax Closed Quantity\t"
    "Profit/Loss (C)\tCumulative Profit/Loss (C)\tCommission (C)\t"
    "FlatToFlat Profit/Loss (C)\tNote\t"
    "FlatToFlat Max Open Profit (C)\tFlatToFlat Max Open Loss (C)\t"
    "Max Open Profit (C)\tMax Open Loss (C)\t"
    "Entry Efficiency\tExit Efficiency\tTotal Efficiency\t"
    "High Price While Open\tLow Price While Open\t"
    "Open Position Quantity\tClose Position Quantity\tDuration"
)

SAMPLE_ROW_1 = (
    "F.US.MNQH23 (105484)\tShort\t2023-01-03  14:01:16.410 BP\t10908.50\t"
    "2023-01-03  14:16:24.141\t10918.25\t1\t2\t1\t-20.24\t-20.24\t0.74\t"
    "-20.24\t"
    "AT_NQ_IPS(1)+TM(all+last50) T1 ATR1  S-trail h-l T2 ATR3 S-be-trail h-l MAX S1ATR\t"
    "30.00\t-19.50\t30.00\t-19.50\t100.0%\t-1.5%\t-40.9%\t"
    "10918.25\t10893.50\t1\t1\t00:15:07"
)

SAMPLE_ROW_2 = (
    "F.US.MNQH23\tShort\t2023-01-03  14:18:37.509 BP\t10912.00\t"
    "2023-01-03  14:24:17.070\t10893.00\t1\t2\t1\t37.26\t-4.22\t0.74\t"
    "37.26\t"
    "AT_NQ_AB2-IPS(1)+TM(2+last100) T1 ATR2 S-h-lT2 ATR6 S-be-trail h-l\t"
    "38.00\t-3.00\t38.00\t-3.00\t100.0%\t98.2%\t90.9%\t"
    "10913.50\t10893.00\t2\t1\t00:05:39"
)

SAMPLE_ROW_FLAT = (
    "F.US.MNQH23\tShort\t2023-01-03  14:18:37.509\t10912.00\t"
    "2023-01-03  14:25:33.521 EP\t10896.75\t1\t2\t2\t29.76\t25.54\t0.74\t"
    "67.02 F\t"
    "AT_NQ_AB2-IPS(1)+TM(2+last100) T1 ATR2 S-h-lT2 ATR6 S-be-trail h-l\t"
    "77.50\t-6.00\t39.50\t-3.00\t100.0%\t42.8%\t35.6%\t"
    "10913.50\t10892.25\t2\t0\t00:06:56"
)


def _make_text(*rows, include_header=True):
    """Build multi-line pasted text."""
    parts = []
    if include_header:
        parts.append(SAMPLE_HEADER)
    parts.extend(rows)
    return "\n".join(parts)


def _temp_db():
    """Create a temp SQLite DB with the processed_trades table."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE processed_trades (
            trade_id TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            side TEXT NOT NULL,
            profit_loss REAL NOT NULL,
            commission REAL DEFAULT 0,
            duration_minutes INTEGER DEFAULT 0,
            hour_of_day INTEGER DEFAULT 0,
            day_of_week INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    return path


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────

class TestParseValidText:
    """GO: 100% of valid rows parsed without error."""

    def test_two_rows_parsed(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1, SAMPLE_ROW_2))
        assert result.total_parsed == 2, f"Expected 2 parsed, got {result.total_parsed}"
        assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"

    def test_three_rows_with_flat_marker(self):
        """Row with '67.02 F' flat-to-flat marker should parse."""
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1, SAMPLE_ROW_2, SAMPLE_ROW_FLAT))
        assert result.total_parsed == 3
        assert len(result.errors) == 0

    def test_no_header_still_works(self):
        """Data without header line should still parse."""
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1, include_header=False))
        assert result.total_parsed == 1
        assert len(result.errors) == 0


class TestMalformedRows:
    """GO: Malformed rows captured in errors[], not crashes."""

    def test_short_row(self):
        bad_row = "F.US.MNQH23\tShort\tMissing columns"
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1, bad_row))
        assert result.total_parsed == 1  # Only good row
        assert len(result.errors) == 1   # Bad row captured

    def test_completely_garbage(self):
        svc = TradeImportService()
        result = svc.preview("this is not trade data at all\nneither is this")
        assert result.total_parsed == 0
        assert len(result.errors) >= 1


class TestDeduplication:
    """GO: Re-import same data → 0 new trades."""

    def test_import_then_reimport(self):
        db_path = _temp_db()
        try:
            svc = TradeImportService(db_path=db_path)
            text = _make_text(SAMPLE_ROW_1, SAMPLE_ROW_2)

            # First import
            r1 = svc.import_trades(text)
            assert r1.new_trades == 2, f"First import: expected 2 new, got {r1.new_trades}"
            assert r1.duplicates == 0

            # Second import — same data
            r2 = svc.import_trades(text)
            assert r2.new_trades == 0, f"Second import: expected 0 new, got {r2.new_trades}"
            assert r2.duplicates == 2, f"Second import: expected 2 dupes, got {r2.duplicates}"
        finally:
            os.unlink(db_path)

    def test_partial_overlap(self):
        """Import 2 rows, then import 3 rows (2 overlap, 1 new)."""
        db_path = _temp_db()
        try:
            svc = TradeImportService(db_path=db_path)

            r1 = svc.import_trades(_make_text(SAMPLE_ROW_1, SAMPLE_ROW_2))
            assert r1.new_trades == 2

            r2 = svc.import_trades(_make_text(SAMPLE_ROW_1, SAMPLE_ROW_2, SAMPLE_ROW_FLAT))
            assert r2.new_trades == 1
            assert r2.duplicates == 2
        finally:
            os.unlink(db_path)


class TestAccountExtraction:
    """GO: account_name equals the full Note column value."""

    def test_note_is_account(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1))
        trade = result.parsed_trades[0]
        expected = "AT_NQ_IPS(1)+TM(all+last50) T1 ATR1  S-trail h-l T2 ATR3 S-be-trail h-l MAX S1ATR"
        assert trade.account_name == expected, f"Got: {trade.account_name}"

    def test_different_account(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_2))
        trade = result.parsed_trades[0]
        expected = "AT_NQ_AB2-IPS(1)+TM(2+last100) T1 ATR2 S-h-lT2 ATR6 S-be-trail h-l"
        assert trade.account_name == expected


class TestEmptyInput:
    """GO: Returns empty results, no crash."""

    def test_empty_string(self):
        svc = TradeImportService()
        result = svc.preview("")
        assert result.total_parsed == 0
        assert len(result.errors) == 0

    def test_whitespace_only(self):
        svc = TradeImportService()
        result = svc.preview("   \n   \n   ")
        assert result.total_parsed == 0

    def test_header_only(self):
        svc = TradeImportService()
        result = svc.preview(SAMPLE_HEADER)
        assert result.total_parsed == 0
        assert len(result.errors) == 0


class TestBaseSymbolExtraction:
    """GO: F.US.MNQH23 → MNQ, NQH24 → NQ, etc."""

    def test_mnq_with_exchange(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1))
        assert result.parsed_trades[0].base_symbol == "MNQ"

    def test_mnq_without_exchange(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_2))
        assert result.parsed_trades[0].base_symbol == "MNQ"

    def test_nq_symbol(self):
        svc = TradeImportService()
        # Build a row with NQH24 symbol
        row = SAMPLE_ROW_1.replace("F.US.MNQH23 (105484)", "NQH24")
        result = svc.preview(_make_text(row))
        assert result.parsed_trades[0].base_symbol == "NQ"


class TestDateTimeParsing:
    """GO: Handles BP/EP markers + multiple datetime formats."""

    def test_bp_marker(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1))
        trade = result.parsed_trades[0]
        assert trade.entry_datetime.hour == 14
        assert trade.entry_datetime.minute == 1

    def test_ep_marker(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_FLAT))
        trade = result.parsed_trades[0]
        assert trade.exit_datetime.hour == 14
        assert trade.exit_datetime.minute == 25


class TestFloatParsing:
    """GO: Handles trailing ' F' and '%' markers."""

    def test_flat_marker(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_FLAT))
        trade = result.parsed_trades[0]
        assert trade.flat_to_flat_pnl == pytest.approx(67.02, abs=0.01)

    def test_percentage(self):
        svc = TradeImportService()
        result = svc.preview(_make_text(SAMPLE_ROW_1))
        trade = result.parsed_trades[0]
        assert trade.entry_efficiency == "100.0%"


class TestDatabaseImport:
    """GO: Trades correctly stored in processed_trades table."""

    def test_inserted_fields_correct(self):
        db_path = _temp_db()
        try:
            svc = TradeImportService(db_path=db_path)
            svc.import_trades(_make_text(SAMPLE_ROW_1))

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM processed_trades LIMIT 1").fetchone()
            conn.close()

            assert row is not None, "No trade inserted"
            assert row["symbol"] == "MNQ"
            assert row["side"] == "SHORT"
            assert row["profit_loss"] == pytest.approx(-20.24, abs=0.01)
            assert row["entry_price"] == pytest.approx(10908.50, abs=0.01)
            assert row["quantity"] == 1
            assert row["hour_of_day"] == 14
            assert row["day_of_week"] == 1  # Tuesday (2023-01-03)
        finally:
            os.unlink(db_path)
