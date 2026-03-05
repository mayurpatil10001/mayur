"""
Test Open/Close pairing for SC-exact matching (entry 3 + exit 3).

When importing from ALLTradeActivityLogExport text with ActivityType=Fills
and OpenClose columns, the system pairs Open with Close via ParentInternalOrderID
instead of FIFO. This produces trades that match Sierra Chart's Trades list exactly.

Run: python -m pytest tests/test_open_close_pairing.py -v --tb=short
"""

import os
import sys
import sqlite3
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading_platform.services.trade_import_service import (
    TradeImportService,
    ImportResult,
)


# ALLTradeActivityLogExport header (tab-delimited)
ACTIVITY_LOG_HEADER = (
    "ActivityType\tDateTime\tTransDateTime\tServiceOrderID\tOrderType\tQuantity\t"
    "OrderStatus\tTradeAccount\tBuySell\tPrice\tPrice2\tFillPrice\tFilledQuantity\t"
    "Note\tPositionQuantity\tOrderActionSource\tInternalOrderID\tOpenClose\t"
    "IsAutomated\tSymbol\tParentInternalOrderID\tFillExecutionServiceID\t"
    "HighDuringPosition\tLowDuringPosition\tAccountBalance\tExchangeOrderID\t"
    "ClientOrderID\tTimeInForce\tUsername"
)


def _make_activity_log(*rows):
    """Build activity log text with header."""
    parts = [ACTIVITY_LOG_HEADER]
    parts.extend(rows)
    return "\n".join(parts)


def _temp_db():
    """Create temp SQLite DB with processed_trades table."""
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


class TestOpenClosePairing:
    """
    GO: Open/Close pairing produces SC-exact trades (entry 3 + exit 3).
    """

    def test_open_close_pairs_entry3_exit3(self):
        """
        Open BUY 3 @ 02:26 and Close SELL 3 @ 04:18 with same ParentInternalOrderID
        must produce LONG 3 with entry 02:26 and exit 04:18 (not FIFO mismatch).
        """
        # Open: BUY 3 @ 02:26, InternalOrderID=1001
        # Close: SELL 3 @ 04:18, ParentInternalOrderID=1001
        open_row = (
            "Fills\t2025-12-18 02:26:00.123456\t2025-12-18 02:26:00.000000\t"
            "34866990\tMarket\t3\tFilled\tV_sim16\tBuy\t\t\t21500.00\t3\t"
            "AT_NQ_TM\t3\tTrading Evaluator (Filled)\t1001\tOpen\tY\tNQZ25\t\t"
            "34866990.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        close_row = (
            "Fills\t2025-12-18 04:18:00.654321\t2025-12-18 04:18:00.000000\t"
            "34866991\tLimit\t3\tFilled\tV_sim16\tSell\t\t\t21510.00\t3\t"
            "AT_NQ_TM\t0\tTrading Evaluator (Filled)\t1002\tClose\tY\tNQZ25\t1001\t"
            "34866991.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        text = _make_activity_log(open_row, close_row)

        db_path = _temp_db()
        try:
            svc = TradeImportService(db_path=db_path)
            result = svc.import_trades(text)

            assert result.new_trades == 1, f"Expected 1 trade, got {result.new_trades}"
            assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM processed_trades LIMIT 1").fetchone()
            conn.close()

            assert row is not None, "No trade inserted"
            assert row["side"] == "LONG"
            assert row["quantity"] == 3
            assert row["symbol"] == "NQ"
            # Entry 02:26 UTC → stored as NY time; exit 04:18 UTC → NY time
            assert "26" in row["entry_time"] and "18" in row["exit_time"]  # minute
            assert row["entry_time"] < row["exit_time"]  # entry before exit
            assert row["entry_price"] == pytest.approx(21500.00, abs=0.01)
            assert row["exit_price"] == pytest.approx(21510.00, abs=0.01)
        finally:
            os.unlink(db_path)

    def test_open_close_vs_fifo_order(self):
        """
        With multiple opens/closes, Open/Close pairing must match by ParentInternalOrderID,
        not by FIFO. E.g. Open1@07:00, Open2@02:26, Close2@04:18 -> Close2 pairs with Open2.
        """
        # Open1: SELL 3 @ 07:00 (SHORT)
        # Open2: BUY 3 @ 02:26 (LONG) - InternalOrderID=2001
        # Close2: SELL 3 @ 04:18 - ParentInternalOrderID=2001
        # FIFO would pair Close2 with Open1 (wrong). Open/Close pairs Close2 with Open2.
        open1_row = (
            "Fills\t2025-12-18 07:00:00.000000\t2025-12-18 07:00:00.000000\t"
            "34866988\tMarket\t3\tFilled\tV_sim16\tSell\t\t\t21490.00\t3\t"
            "AT_NQ_TM\t3\tTrading Evaluator (Filled)\t3001\tOpen\tY\tNQZ25\t\t"
            "34866988.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        open2_row = (
            "Fills\t2025-12-18 02:26:00.000000\t2025-12-18 02:26:00.000000\t"
            "34866990\tMarket\t3\tFilled\tV_sim16\tBuy\t\t\t21500.00\t3\t"
            "AT_NQ_TM\t3\tTrading Evaluator (Filled)\t2001\tOpen\tY\tNQZ25\t\t"
            "34866990.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        close2_row = (
            "Fills\t2025-12-18 04:18:00.000000\t2025-12-18 04:18:00.000000\t"
            "34866991\tLimit\t3\tFilled\tV_sim16\tSell\t\t\t21510.00\t3\t"
            "AT_NQ_TM\t0\tTrading Evaluator (Filled)\t2002\tClose\tY\tNQZ25\t2001\t"
            "34866991.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        text = _make_activity_log(open1_row, open2_row, close2_row)

        db_path = _temp_db()
        try:
            svc = TradeImportService(db_path=db_path)
            result = svc.import_trades(text)

            # Should get 2 trades: SHORT (07:00->?) and LONG (02:26->04:18)
            # Open1 (SHORT) has no Close yet -> unpaired
            # Open2+Close2 -> LONG 02:26->04:18
            assert result.new_trades >= 1, f"Expected at least 1 trade, got {result.new_trades}"

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM processed_trades ORDER BY entry_time"
            ).fetchall()
            conn.close()

            # Find the LONG trade (entry 02:26, exit 04:18)
            long_trades = [r for r in rows if r["side"] == "LONG"]
            assert len(long_trades) >= 1, "Expected at least one LONG trade"
            lt = long_trades[0]
            assert lt["quantity"] == 3
            assert lt["entry_time"] < lt["exit_time"]  # Open/Close paired correctly
        finally:
            os.unlink(db_path)

    def test_activity_type_fills_only(self):
        """Orders rows are filtered out; only Fills are processed."""
        orders_row = (
            "Orders\t2025-12-18 02:26:00.000000\t2025-12-18 02:26:00.000000\t"
            "34866990\tMarket\t3\tFilled\tV_sim16\tBuy\t\t\t21500.00\t3\t"
            "AT_NQ_TM\t3\tTrading Evaluator (Filled)\t1001\tOpen\tY\tNQZ25\t\t"
            "34866990.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        fills_row = (
            "Fills\t2025-12-18 02:26:00.123456\t2025-12-18 02:26:00.000000\t"
            "34866990\tMarket\t3\tFilled\tV_sim16\tBuy\t\t\t21500.00\t3\t"
            "AT_NQ_TM\t3\tTrading Evaluator (Filled)\t1001\tOpen\tY\tNQZ25\t\t"
            "34866990.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        close_row = (
            "Fills\t2025-12-18 04:18:00.000000\t2025-12-18 04:18:00.000000\t"
            "34866991\tLimit\t3\tFilled\tV_sim16\tSell\t\t\t21510.00\t3\t"
            "AT_NQ_TM\t0\tTrading Evaluator (Filled)\t1002\tClose\tY\tNQZ25\t1001\t"
            "34866991.1\t\t\t0.00\t\t\tGood till Canceled\tshimishon"
        )
        text = _make_activity_log(orders_row, fills_row, close_row)

        db_path = _temp_db()
        try:
            svc = TradeImportService(db_path=db_path)
            result = svc.import_trades(text)

            # Should still get 1 trade (Fills only)
            assert result.new_trades == 1
        finally:
            os.unlink(db_path)
