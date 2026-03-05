"""
Benchmark tests for 2025-12-18 V_SIM16 using binary-only reconstruction.

Binary .data remains the only import source.
Trade List / All Activity files are used for reference metrics only.
"""

from __future__ import annotations

import csv
import datetime as dt
import glob
import os
import sqlite3
import sys
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro, _scan_position_fill_order


ROOT = Path(__file__).resolve().parents[1]
REF_ACTIVITY = ROOT / "1218 nq all activity list.txt"
REF_TRADES = ROOT / "1218 nq trade list.txt"
BINARY_FILE = Path(
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
)
BINARY_GLOB_2D = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-1[789]_UTC.V_sim16.data"


def _parse_dt(value: str) -> dt.datetime | None:
    if not value:
        return None
    s = value.strip().replace("T", " ")
    s = s.replace(" BP", "").replace(" EP", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _load_trade_list_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not row.get("Symbol"):
                continue
            if "sim16" not in (row.get("Account") or "").lower() and "sim16" not in (
                row.get("Symbol") or ""
            ).lower():
                continue
            entry_dt = _parse_dt(row.get("Entry DateTime", ""))
            exit_dt = _parse_dt(row.get("Exit DateTime", ""))
            if not entry_dt or not exit_dt:
                continue
            start_time = dt.datetime(2025, 12, 17, 17, 59, 30)
            end_time = dt.datetime(2025, 12, 18, 17, 30, 0)
            if not (start_time <= entry_dt <= end_time) and not (start_time <= exit_dt <= end_time):
                continue
            rows.append(row)
    return rows


def _load_trade_list_struct(path: Path) -> list[dict]:
    rows: list[dict] = []
    for row in _load_trade_list_rows(path):
        entry_dt = _parse_dt(row.get("Entry DateTime", ""))
        exit_dt = _parse_dt(row.get("Exit DateTime", ""))
        if not entry_dt or not exit_dt:
            continue
        try:
            ep = float(row.get("Entry Price", 0) or 0)
            xp = float(row.get("Exit Price", 0) or 0)
            qty = int(float(row.get("Trade Quantity", 0) or 0))
        except (TypeError, ValueError):
            continue
        side = "Long"
        if "short" in (row.get("Trade Type") or "").lower():
            side = "Short"
        rows.append(
            {
                "entry_dt": entry_dt,
                "exit_dt": exit_dt,
                "entry_price": ep,
                "exit_price": xp,
                "qty": qty,
                "side": side,
            }
        )
    return rows


def _match_trade(a: dict, b: dict, tol_sec: int = 5, tol_price: float = 0.5) -> bool:
    if a.get("side") != b.get("side"):
        return False
    if int(a.get("qty", 0)) != int(b.get("qty", 0)):
        return False
    de = abs((a["entry_dt"] - b["entry_dt"]).total_seconds())
    dx = abs((a["exit_dt"] - b["exit_dt"]).total_seconds())
    if de > tol_sec or dx > tol_sec:
        return False
    if abs(float(a["entry_price"]) - float(b["entry_price"])) > tol_price:
        return False
    if abs(float(a["exit_price"]) - float(b["exit_price"])) > tol_price:
        return False
    return True


def _load_activity_fills(path: Path) -> list[dict]:
    fills: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if (row.get("ActivityType") or "").strip().lower() != "fills":
                continue
            if (row.get("OrderStatus") or "").strip().upper() != "FILLED":
                continue
            if "sim16" not in (row.get("TradeAccount") or "").lower():
                continue
            ts = _parse_dt(row.get("DateTime", ""))
            start_time = dt.datetime(2025, 12, 17, 17, 59, 30)
            end_time = dt.datetime(2025, 12, 18, 17, 30, 0)
            if not ts or not (start_time <= ts <= end_time):
                continue
            try:
                price = float((row.get("FillPrice") or "0").strip() or 0)
                qty = int(float((row.get("FilledQuantity") or "0").strip() or 0))
            except ValueError:
                continue
            side = (row.get("BuySell") or "").strip().upper()
            if side not in ("BUY", "SELL"):
                continue
            fills.append({"dt": ts, "price": price, "qty": qty, "side": side})
    return fills


def _load_activity_fills_with_oids(path: Path) -> list[dict]:
    """Activity Fills with InternalOrderID and OpenClose for reference-derived pairing."""
    fills: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if (row.get("ActivityType") or "").strip().lower() != "fills":
                continue
            if (row.get("OrderStatus") or "").strip().upper() != "FILLED":
                continue
            if "sim16" not in (row.get("TradeAccount") or "").lower():
                continue
            ts = _parse_dt((row.get("TransDateTime") or row.get("DateTime") or "").strip())
            start_time = dt.datetime(2025, 12, 17, 18, 0, 0)
            end_time = dt.datetime(2025, 12, 18, 17, 0, 0)
            if not ts or not (start_time <= ts <= end_time):
                continue
            try:
                price = float((row.get("FillPrice") or "0").strip() or 0)
                qty = int(float((row.get("FilledQuantity") or "0").strip() or 0))
            except ValueError:
                continue
            side = (row.get("BuySell") or "").strip().upper()
            if side not in ("BUY", "SELL"):
                continue
            oid = (row.get("InternalOrderID") or "").strip()
            oc = (row.get("OpenClose") or "").strip().upper()
            if not oid:
                continue
            fills.append({"dt": ts, "price": price, "qty": qty, "side": side, "internal_oid": oid, "open_close": oc})
    return fills


def _exact_pairing_via_reference(
    binary_fills: list[dict], sc_trade_rows: list[dict], tol_sec: int = 5, tol_price: float = 0.5
) -> tuple[float, int]:
    """
    Exact pairing by deriving (entry_oid, exit_oid) from SC trade list + activity list,
    then mapping to binary fills by internal_order_id. Proves binary can pair exactly when reference exists.
    Returns (strict_match_pct, num_trades_built).
    """
    activity = _load_activity_fills_with_oids(REF_ACTIVITY)
    open_fills = [a for a in activity if a.get("open_close") == "OPEN"]
    close_fills = [a for a in activity if a.get("open_close") == "CLOSE"]

    def match_activity(adt, aprice, aqty, side, candidates, qty_must_equal: bool = True):
        for c in candidates:
            if abs((adt - c["dt"]).total_seconds()) > tol_sec:
                continue
            if abs(c["price"] - aprice) > tol_price:
                continue
            if c["side"] != side:
                continue
            if qty_must_equal and c["qty"] != aqty:
                continue
            if not qty_must_equal and c["qty"] < aqty:
                continue
            return c.get("internal_oid")
        return None

    ref_pairs: list[tuple[str, str, int, float, float, str]] = []
    for sc in sc_trade_rows:
        entry_dt = sc.get("entry_dt")
        exit_dt = sc.get("exit_dt")
        ep = float(sc.get("entry_price", 0) or 0)
        xp = float(sc.get("exit_price", 0) or 0)
        qty = int(float(sc.get("qty", 0) or 0))
        side = sc.get("side", "Long")
        # Long: open=BUY, close=SELL. Short: open=SELL, close=BUY.
        entry_act_side = "BUY" if side == "Long" else "SELL"
        exit_act_side = "SELL" if side == "Long" else "BUY"
        # Entry: OPEN fill with same time/price/side; open qty can be >= trade qty (partial close).
        entry_oid = match_activity(entry_dt, ep, qty, entry_act_side, open_fills, qty_must_equal=False)
        exit_oid = match_activity(exit_dt, xp, qty, exit_act_side, close_fills, qty_must_equal=True)
        if entry_oid and exit_oid:
            ref_pairs.append((entry_oid, exit_oid, qty, ep, xp, side))

    by_oid: dict[str, list[dict]] = {}
    for bf in binary_fills:
        oid = str(bf.get("internal_order_id") or "")
        if oid:
            by_oid.setdefault(oid, []).append(bf)

    built: list[dict] = []
    for entry_oid, exit_oid, qty, ep, xp, side in ref_pairs:
        entry_cands = [f for f in by_oid.get(entry_oid, []) if (f.get("open_close") or "").upper() == "OPEN"]
        exit_cands = [f for f in by_oid.get(exit_oid, []) if (f.get("open_close") or "").upper() == "CLOSE"]
        if not entry_cands or not exit_cands:
            continue
        entry_f = min(entry_cands, key=lambda x: x.get("ts_val", 0))
        exit_f = min(exit_cands, key=lambda x: x.get("ts_val", 0))
        built.append({
            "entry_dt": dt.datetime.fromisoformat(entry_f["timestamp"]),
            "exit_dt": dt.datetime.fromisoformat(exit_f["timestamp"]),
            "entry_price": float(entry_f["price"]),
            "exit_price": float(exit_f["price"]),
            "qty": qty,
            "side": side,
        })

    match_count = sum(1 for bt in built if any(_match_trade(bt, sc) for sc in sc_trade_rows))
    pct = (match_count / len(built) * 100.0) if built else 0.0
    return (pct, len(built))


def _load_binary_fills_for_ny_1218(use_trans_time: bool = False, include_ghost: bool = False) -> list[dict]:
    """Load binary fills for 12/18 NY. When use_trans_time=True, prefer TransDateTime (tag 160)
    for timestamp/ts_val so ordering and trade times align with SC Trade List (which uses TransDateTime).
    Uses position-update order (Fill of InternalOrderID in Position messages) for exact SC pairing.
    When include_ghost=True, fills with suggests_ghost are included (e.g. for annotating SC trades)."""
    ny = ZoneInfo("America/New_York")
    # Build global position-update order (SC execution order) from both files
    position_order_list: list[str] = []
    for fp in sorted(glob.glob(BINARY_GLOB_2D)):
        position_order_list.extend(_scan_position_fill_order(fp))
    position_order_map = {oid: i for i, oid in enumerate(position_order_list)}

    out: list[dict] = []
    for fp in sorted(glob.glob(BINARY_GLOB_2D)):
        fills, _ = _parse_file_nitro(fp, acc_filter=["V_SIM16"])
        for f in fills:
            if not include_ghost and f.get("suggests_ghost"):
                continue
            ts_raw = (f.get("trans_timestamp") or f["timestamp"]) if use_trans_time else f["timestamp"]
            d_utc = dt.datetime.fromisoformat(ts_raw)
            if d_utc.tzinfo is None:
                d_utc = d_utc.replace(tzinfo=dt.timezone.utc)
            d_ny = d_utc.astimezone(ny).replace(tzinfo=None)
            start_time = dt.datetime(2025, 12, 17, 17, 59, 30)
            end_time = dt.datetime(2025, 12, 18, 17, 30, 0)
            if not (start_time <= d_ny <= end_time):
                continue
            z = dict(f)
            z["timestamp"] = d_ny.isoformat()
            z["ts_val"] = d_ny.timestamp()
            z["_position_order"] = position_order_map.get(str(z.get("internal_order_id", "")), 999999)
            out.append(z)
    # Exact SC order: position-update sequence first, then time, then file/record
    out.sort(key=lambda x: (x.get("_position_order", 999999), x.get("ts_val", 0), x.get("file_path", ""), x.get("_record_index", 0), x.get("offset", 0)))
    return out


@pytest.mark.skipif(not REF_ACTIVITY.exists(), reason="Missing 1218 all activity reference file.")
@pytest.mark.skipif(not REF_TRADES.exists(), reason="Missing 1218 trade list reference file.")
def test_reference_files_parse_for_1218_benchmark():
    """
    Reference benchmark files should parse cleanly.
    These values are reference-only; import logic remains binary-only.
    """
    trade_rows = _load_trade_list_rows(REF_TRADES)
    activity_fills = _load_activity_fills(REF_ACTIVITY)

    # Known 12/18 benchmark counts from current dataset.
    assert len(trade_rows) == 171
    assert len(activity_fills) == 210


@pytest.mark.skipif(not BINARY_FILE.exists(), reason="Missing 12/18 V_sim16 binary file.")
def test_binary_file_parses_for_vsim16_1218():
    """
    Binary parser must produce fills from the V_sim16 file.
    """
    fills, _ = _parse_file_nitro(str(BINARY_FILE), acc_filter=["V_SIM16"])
    assert len(fills) > 100  # expected ~155 on this dataset
    assert all(f.get("account_name", "").upper() == "V_SIM16" for f in fills)


@pytest.mark.skipif(not BINARY_FILE.exists(), reason="Missing 12/18 V_sim16 binary file.")
def test_binary_session_ledger_reconstructs_trades_without_cross_session_match():
    """
    Reconstruct trades from binary-only fills and assert core consistency invariants:
    - closed trades exist
    - no trade has entry >= exit
    """
    fills, _ = _parse_file_nitro(str(BINARY_FILE), acc_filter=["V_SIM16"])
    parser = BinaryLogParser(db_path=":memory:")
    trades, unpaired, _warnings = parser._pairs_to_trades(fills, persist_state=False)

    assert len(trades) > 0
    assert unpaired >= 0

    for t in trades:
        e = dt.datetime.fromisoformat(t["entry_time"])
        x = dt.datetime.fromisoformat(t["exit_time"])
        assert e < x


@pytest.mark.skipif(not BINARY_FILE.exists(), reason="Missing 12/18 V_sim16 binary file.")
@pytest.mark.skipif(not REF_TRADES.exists(), reason="Missing 1218 trade list reference file.")
def test_binary_to_reference_benchmark_report_is_generated():
    """
    Produce a benchmark metric against trade-list reference.
    This is a reporting guard, not a hard quality gate yet.
    """
    fills = _load_binary_fills_for_ny_1218()
    parser = BinaryLogParser(db_path=":memory:")
    trades, _unpaired, _warnings = parser._pairs_to_trades(fills, persist_state=False)
    trade_rows = _load_trade_list_struct(REF_TRADES)

    normalized = []
    for t in trades:
        side = "Long" if (t.get("side") or "").upper() == "LONG" else "Short"
        normalized.append(
            {
                "entry_dt": dt.datetime.fromisoformat(t["entry_time"]),
                "exit_dt": dt.datetime.fromisoformat(t["exit_time"]),
                "entry_price": float(t["entry_price"]),
                "exit_price": float(t["exit_price"]),
                "qty": int(t["quantity"]),
                "side": side,
            }
        )

    strict_match_count = sum(1 for bt in normalized if any(_match_trade(bt, sc) for sc in trade_rows))
    strict_match_pct = (strict_match_count / len(normalized) * 100.0) if normalized else 0.0

    # Binary-only pairing (FIFO + open/close + position order) reaches ~24% without ParentInternalOrderID.
    assert strict_match_pct >= 20.0, (
        f"Strict binary->SC trade match is {strict_match_pct:.2f}% "
        f"({strict_match_count}/{len(normalized)}). Expected >= 20%."
    )

    # When reference (trade list + activity) exists, exact pairing via reference-derived map must reach 90%+
    if REF_ACTIVITY.exists():
        ref_match_pct, ref_trades = _exact_pairing_via_reference(fills, trade_rows)
        assert ref_match_pct >= 90.0, (
            f"Reference-derived exact pairing should reach 90%+; got {ref_match_pct:.2f}% ({ref_trades} trades)."
        )

