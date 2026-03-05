"""
Test binary import (TradeActivityLog .data files).

Uses a minimal programmatically-created .data fixture to test:
- _parse_file_nitro extracts fills from binary
- BinaryLogParser.run_import produces trades via FIFO pairing
- Trades are written to processed_trades

Run: python -m pytest tests/test_binary_import.py -v --tb=short
"""

import datetime
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading_platform.services.binary_log_parser import (
    BinaryLogParser,
    _parse_file_nitro,
)


def _create_binary_fixture(path: str, fills: list) -> None:
    """Create minimal .data file. fills: [{"ts_unix_micros", "side", "price", "qty"}, ...]"""
    import struct
    TAG_TIME, TAG_NOTE, TAG_ORDER_TYPE = 102, 0x82, 107
    TAG_SYMBOL, TAG_MESSAGE, TAG_QUANTITY = 0x67, 104, 108

    def write_tlv(f, tag, value):
        f.write(struct.pack("<II", tag, len(value)))
        f.write(value)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        for fill in fills:
            ts = fill["ts_unix_micros"]
            side = fill["side"].upper()
            price = fill["price"]
            qty = fill["qty"]
            write_tlv(f, TAG_TIME, struct.pack("<q", ts))
            write_tlv(f, TAG_NOTE, b"AT_NQ_TM")
            write_tlv(f, TAG_ORDER_TYPE, b"Market")
            write_tlv(f, TAG_SYMBOL, b"NQZ25")
            msg = f"{'Bought' if side == 'BUY' else 'Sold'} {qty}. Trade simulation fill. Bid: {price:.0f} Ask: {price:.0f} Last: {price:.0f}".encode()
            write_tlv(f, TAG_MESSAGE, msg)
            write_tlv(f, TAG_QUANTITY, struct.pack("<d", float(qty)))


class TestBinaryImport:
    """Test binary .data file import."""

    def test_parse_file_nitro_extracts_fills(self, tmp_path):
        """_parse_file_nitro extracts BUY and SELL fills from minimal binary."""
        # 2025-12-18 02:26:00 UTC, 04:18:00 UTC
        ts1 = 1734492360000000  # 02:26
        ts2 = 1734499080000000  # 04:18
        path = tmp_path / "TradeActivityLog_2025-12-18_UTC.V_SIM16.data"
        _create_binary_fixture(str(path), [
            {"ts_unix_micros": ts1, "side": "BUY", "price": 21500.0, "qty": 3},
            {"ts_unix_micros": ts2, "side": "SELL", "price": 21510.0, "qty": 3},
        ])
        fills, ghosts = _parse_file_nitro(str(path), acc_filter=["V_SIM16"])
        assert len(fills) == 2
        assert fills[0]["side"] == "BUY" and fills[0]["quantity"] == 3
        assert fills[1]["side"] == "SELL" and fills[1]["quantity"] == 3
        assert fills[0]["account_name"] == "V_SIM16"
        assert fills[0]["symbol"] == "NQZ25"

    def test_binary_import_produces_trades(self, tmp_path):
        """Full binary import produces closed trades in DB."""
        ts1 = 1734492360000000  # 02:26 UTC
        ts2 = 1734499080000000  # 04:18 UTC
        path = tmp_path / "TradeActivityLog_2025-12-18_UTC.V_SIM16.data"
        _create_binary_fixture(str(path), [
            {"ts_unix_micros": ts1, "side": "BUY", "price": 21500.0, "qty": 3},
            {"ts_unix_micros": ts2, "side": "SELL", "price": 21510.0, "qty": 3},
        ])
        db_path = str(tmp_path / "test.db")
        parser = BinaryLogParser(db_path=db_path)
        import asyncio
        asyncio.run(parser.run_import([str(tmp_path)], account_filter=["V_SIM16"], days_lookback=None))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM processed_trades").fetchall()
        conn.close()
        assert len(rows) >= 1
        r = rows[0]
        assert r["side"] == "LONG"
        assert r["quantity"] == 3
        assert r["symbol"] == "NQ"
        assert r["entry_price"] == pytest.approx(21500.0, abs=0.01)
        assert r["exit_price"] == pytest.approx(21510.0, abs=0.01)

    def test_binary_fifo_pairing(self, tmp_path):
        """FIFO pairing: SELL closes oldest BUY first."""
        # BUY 3 @ 07:00, BUY 3 @ 02:26, SELL 3 @ 04:18
        # FIFO: SELL 3 closes BUY @ 07:00 (SHORT 07:00->04:18), not BUY @ 02:26
        base = 1734476400  # 2025-12-18 00:00 UTC
        ts_07 = (base + 7 * 3600) * 1_000_000   # 07:00
        ts_02 = (base + 2 * 3600 + 26 * 60) * 1_000_000  # 02:26
        ts_04 = (base + 4 * 3600 + 18 * 60) * 1_000_000  # 04:18
        path = tmp_path / "TradeActivityLog_2025-12-18_UTC.V_SIM16.data"
        _create_binary_fixture(str(path), [
            {"ts_unix_micros": ts_07, "side": "SELL", "price": 21490.0, "qty": 3},  # SHORT open
            {"ts_unix_micros": ts_02, "side": "BUY", "price": 21500.0, "qty": 3},   # LONG open
            {"ts_unix_micros": ts_04, "side": "SELL", "price": 21510.0, "qty": 3},  # Close LONG
        ])
        db_path = str(tmp_path / "test.db")
        parser = BinaryLogParser(db_path=db_path)
        import asyncio
        asyncio.run(parser.run_import([str(tmp_path)], account_filter=["V_SIM16"], days_lookback=None))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM processed_trades ORDER BY entry_time").fetchall()
        conn.close()
        # FIFO: SELL @ 04:18 closes BUY @ 02:26 (LONG 02:26->04:18)
        long_trades = [r for r in rows if r["side"] == "LONG"]
        assert len(long_trades) >= 1
        assert long_trades[0]["quantity"] == 3
