#!/usr/bin/env python3
"""
Cross-correlate trades across: Trade List, Activity List, Binary, and Chart annotations.
12/18 NQ V_SIM16 - find best way to match max trades between all sources.
"""
import os
import re
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
TRADE_LIST = os.path.join(ROOT, "1218 nq trade list.txt")
ACTIVITY_LIST = os.path.join(ROOT, "1218 nq all activity list.txt")
BINARY_LOG_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
BINARY_PATTERN = "TradeActivityLog_2025-12-18_UTC.*[Vv]_[Ss]im16*.data"

# Chart annotations extracted from screenshots (approx time, qty@price)
# Format: (time_str, qty, price, side) - side: B=Buy, S=Sell
CHART_ANNOTATIONS = [
    # Image 1: 00:00-01:57
    ("00:03", -1, 24980.00, "S"),
    ("00:09", -3, 24986.25, "S"),
    ("00:21", 1, 24976.75, "B"),
    ("00:24", 1, 24977.00, "B"),
    ("00:27", 1, 24982.25, "B"),
    ("00:42", 3, 24991.50, "B"),
    ("00:51", 3, 24988.75, "B"),
    ("00:54", -3, 24979.50, "S"),
    ("01:03", 3, 24985.00, "B"),
    ("01:06", -3, 24976.00, "S"),
    ("01:12", -3, 24976.00, "S"),
    ("01:21", -3, 24972.25, "S"),
    ("01:39", -3, 24975.25, "S"),
    ("01:45", 1, 24973.00, "B"),
    ("01:48", -3, 24955.00, "S"),
    ("01:48", 1, 24966.00, "B"),
    ("01:51", 1, 24971.25, "B"),
    ("01:54", 3, 24969.50, "B"),
]


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse SC datetime: 2025-12-18  00:14:42.982 or ISO 2025-12-18T00:01:42.504285."""
    if not s or not s.strip():
        return None
    s = re.sub(r'\s+(BP|EP)\s*$', '', str(s).strip())
    s = re.sub(r'\s+', ' ', s)
    # ISO format from binary parser (T separator)
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d  %H:%M:%S.%f"
    ]:
        try:
            return datetime.strptime(s[:26], fmt[:min(len(fmt), len(s) + 5)])
        except ValueError:
            continue
    # Fallback: normalize T to space and retry
    s2 = s.replace("T", " ", 1)
    for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(s2[:26], fmt[:min(len(fmt), len(s2) + 5)])
        except ValueError:
            continue
    return None


def load_trade_list(path: str) -> List[Dict]:
    """Load 26-col trade list. Filter 12/18, V_sim16."""
    trades = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            if not row.get("Symbol"):
                continue
            acc = (row.get("Account") or "").strip()
            sym = (row.get("Symbol") or "").strip()
            if "sim16" not in acc.lower() and "sim16" not in sym.lower():
                continue
            entry_s = row.get("Entry DateTime", "").strip()
            exit_s = row.get("Exit DateTime", "").strip()
            if not exit_s or exit_s == "Total:":
                continue
            entry_dt = _parse_dt(entry_s)
            exit_dt = _parse_dt(exit_s)
            if not entry_dt or not exit_dt:
                continue
            if "2025-12-18" not in (entry_dt.date().isoformat(), exit_dt.date().isoformat()):
                continue
            try:
                ep = float(row.get("Entry Price", 0) or 0)
                xp = float(row.get("Exit Price", 0) or 0)
                qty = int(float(row.get("Trade Quantity", 0) or 0))
            except (ValueError, TypeError):
                continue
            side = "Short" if "Short" in str(row.get("Trade Type", "")) else "Long"
            trades.append({
                "entry_dt": entry_dt,
                "exit_dt": exit_dt,
                "entry_price": ep,
                "exit_price": xp,
                "qty": qty,
                "side": side,
                "entry_str": entry_s,
                "exit_str": exit_s,
            })
    return trades


def load_activity_fills(path: str) -> List[Dict]:
    """Load Fills from activity list. Extract key fields."""
    fills = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            if row.get("ActivityType") != "Fills":
                continue
            # TransDateTime = actual fill time (matches Trade List); DateTime = processing time
            dt_s = (row.get("TransDateTime") or row.get("DateTime") or "").strip()
            dt = _parse_dt(dt_s)
            if not dt:
                continue
            try:
                price = float(row.get("FillPrice", 0) or row.get("Price", 0) or 0)
                qty = int(float(row.get("FilledQuantity", 0) or row.get("Quantity", 0) or 0))
            except (ValueError, TypeError):
                continue
            buy_sell = (row.get("BuySell", "") or "").strip().upper()
            side = "Long" if buy_sell == "BUY" else "Short"
            oc = (row.get("OpenClose", "") or "").strip()
            internal = (row.get("InternalOrderID", "") or "").strip()
            parent = (row.get("ParentInternalOrderID", "") or "").strip()
            fills.append({
                "dt": dt,
                "price": price,
                "qty": qty,
                "side": side,
                "open_close": oc,
                "internal_order_id": internal,
                "parent_internal_order_id": parent,
            })
    return fills


def pair_activity_fills(fills: List[Dict]) -> List[Dict]:
    """Pair Open and Close fills: ParentInternalOrderID when available, else FIFO (matches trade_import_service)."""
    opens_by_id = {}
    for f in fills:
        if f["open_close"] == "Open" and f.get("internal_order_id"):
            oid = f["internal_order_id"]
            if oid not in opens_by_id:
                opens_by_id[oid] = []
            opens_by_id[oid].append({"fill": f, "qty_left": f["qty"]})

    opens_fifo = [{"fill": f, "qty_left": f["qty"]} for f in fills if f["open_close"] == "Open"]
    opens_fifo.sort(key=lambda x: x["fill"]["dt"])

    pairs = []
    closes = [f for f in fills if f["open_close"] == "Close"]
    closes.sort(key=lambda x: x["dt"])

    for cf in closes:
        close_qty = cf["qty"]
        parent = (cf.get("parent_internal_order_id") or "").strip()

        # Try parent-based pairing first (when ParentInternalOrderID is populated)
        if parent and parent in opens_by_id and opens_by_id[parent]:
            entry_list = opens_by_id[parent]
            while close_qty > 0 and entry_list:
                o = entry_list[0]
                match_qty = min(close_qty, o["qty_left"])
                if match_qty <= 0:
                    entry_list.pop(0)
                    continue
                of = o["fill"]
                pairs.append({
                    "entry_dt": of["dt"], "exit_dt": cf["dt"],
                    "entry_price": of["price"], "exit_price": cf["price"],
                    "qty": int(match_qty), "side": of["side"], "source": "activity_parent",
                })
                o["qty_left"] -= match_qty
                close_qty -= match_qty
                if o["qty_left"] <= 0:
                    entry_list.pop(0)

        # FIFO fallback (when parent empty or no match - same as trade_import_service)
        want_open_side = "Short" if cf["side"] == "Long" else "Long"
        i = 0
        while close_qty > 0 and i < len(opens_fifo):
            o = opens_fifo[i]
            of = o["fill"]
            if o["qty_left"] <= 0:
                i += 1
                continue
            if of["side"] != want_open_side:
                i += 1
                continue
            if of["dt"] >= cf["dt"]:
                i += 1
                continue
            match_qty = min(close_qty, o["qty_left"])
            if match_qty <= 0:
                i += 1
                continue
            pairs.append({
                "entry_dt": of["dt"], "exit_dt": cf["dt"],
                "entry_price": of["price"], "exit_price": cf["price"],
                "qty": int(match_qty), "side": of["side"], "source": "activity_fifo",
            })
            o["qty_left"] -= match_qty
            close_qty -= match_qty
            if o["qty_left"] <= 0:
                opens_fifo.pop(i)
            else:
                i += 1

    return [p for p in pairs if p["entry_dt"] < p["exit_dt"]]


def load_binary_fills(log_dir: str) -> List[Dict]:
    """Parse binary TradeActivityLog for 12/18 V_SIM16. Returns raw fills."""
    import glob
    from trading_platform.services.binary_log_parser import _parse_file_nitro

    pattern = os.path.join(log_dir, "TradeActivityLog_2025-12-18_UTC*.data")
    files = glob.glob(pattern) + glob.glob(os.path.join(log_dir, "TradeActivityLog_2025-12-18_UTC*.DATA"))
    # Only V_sim16 (not 3Q_sim16, V500_sim16) for 12/18 NQ V_SIM16 cross-check
    vsim_files = [p for p in files if re.search(r"[._]V_sim16\.(?:data|DATA)$", os.path.basename(p), re.I)]
    seen = set()
    vsim_files = [p for p in vsim_files if os.path.normcase(p) not in seen and not seen.add(os.path.normcase(p))]
    if not vsim_files:
        return []

    all_fills = []
    for fp in vsim_files:
        fn = os.path.basename(fp)
        acc_match = re.search(r"UTC[._]([^.]+)\.(?:data|DATA)", fn, re.I)
        acc = acc_match.group(1) if acc_match else "V_SIM16"
        try:
            fills, _ = _parse_file_nitro(fp, acc_filter=[acc])
            for f in fills:
                ts = f.get("timestamp") or f.get("ts_val")
                if ts:
                    if isinstance(ts, (int, float)):
                        from datetime import datetime, timezone
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        dt = dt.replace(tzinfo=None)
                    else:
                        dt = _parse_dt(str(ts))
                    if dt and dt.date().isoformat() == "2025-12-18":
                        all_fills.append({
                            "dt": dt,
                            "price": f.get("price", 0),
                            "qty": f.get("quantity", 0),
                            "side": "Long" if (f.get("side", "") or "").upper() == "BUY" else "Short",
                            "source": "binary",
                        })
        except Exception as e:
            print(f"  [Binary] Skip {fn}: {e}")
    return all_fills


def fifo_pair_fills(fills: List[Dict]) -> List[Dict]:
    """Pair fills using FIFO (buy vs sell)."""
    buys = [f for f in fills if f["side"] == "Long"]
    sells = [f for f in fills if f["side"] == "Short"]
    buys.sort(key=lambda x: x["dt"])
    sells.sort(key=lambda x: x["dt"])
    pairs = []
    i, j = 0, 0
    while i < len(buys) and j < len(sells):
        b, s = buys[i], sells[j]
        pairs.append({
            "entry_dt": b["dt"],
            "exit_dt": s["dt"],
            "entry_price": b["price"],
            "exit_price": s["price"],
            "qty": min(b["qty"], s["qty"]),
            "side": "Long",
            "source": "binary_fifo",
        })
        if b["qty"] <= s["qty"]:
            i += 1
            if b["qty"] < s["qty"]:
                sells[j] = {**s, "qty": s["qty"] - b["qty"]}
            else:
                j += 1
        else:
            j += 1
            buys[i] = {**b, "qty": b["qty"] - s["qty"]}
    return [p for p in pairs if p["entry_dt"] < p["exit_dt"]]


def match_trade(a: Dict, b: Dict, tol_sec: int = 5, tol_price: float = 0.5) -> bool:
    """Check if two trades match (entry/exit within tolerance)."""
    if a.get("side") != b.get("side"):
        return False
    if abs(a.get("qty", 0) - b.get("qty", 0)) > 0:
        return False
    ea, xa = a.get("entry_dt"), a.get("exit_dt")
    eb, xb = b.get("entry_dt"), b.get("exit_dt")
    if not all([ea, xa, eb, xb]):
        return False
    if abs((ea - eb).total_seconds()) > tol_sec or abs((xa - xb).total_seconds()) > tol_sec:
        return False
    if abs(a.get("entry_price", 0) - b.get("entry_price", 0)) > tol_price:
        return False
    if abs(a.get("exit_price", 0) - b.get("exit_price", 0)) > tol_price:
        return False
    return True


def main():
    print("=" * 80)
    print("TRADE MATCHING: 12/18 NQ V_SIM16 — Trade List, Activity, Binary, Chart")
    print("=" * 80)

    # 1. Trade List (SC Trades tab - source of truth)
    trade_list = load_trade_list(TRADE_LIST)
    print(f"\n1. TRADE LIST: {len(trade_list)} trades")
    if trade_list:
        print(f"   First: {trade_list[0]['entry_dt']} -> {trade_list[0]['exit_dt']} {trade_list[0]['side']} {trade_list[0]['qty']} @ {trade_list[0]['entry_price']}/{trade_list[0]['exit_price']}")
        print(f"   Last:  {trade_list[-1]['entry_dt']} -> {trade_list[-1]['exit_dt']} {trade_list[-1]['side']} {trade_list[-1]['qty']}")

    # 2. Activity List (Fills + ParentInternalOrderID pairing)
    fills = load_activity_fills(ACTIVITY_LIST)
    activity_pairs = pair_activity_fills(fills)
    print(f"\n2. ACTIVITY LIST: {len(fills)} fills -> {len(activity_pairs)} paired trades (Open/Close)")
    if activity_pairs:
        print(f"   First: {activity_pairs[0]['entry_dt']} -> {activity_pairs[0]['exit_dt']} {activity_pairs[0]['side']} {activity_pairs[0]['qty']}")

    # 3. Binary (FIFO pairing)
    binary_fills = []
    log_dir = BINARY_LOG_DIR
    try:
        import json
        cfg = os.path.join(ROOT, "app_settings.json")
        if os.path.isfile(cfg):
            with open(cfg) as f:
                js = json.load(f)
            for s in (js.get("scanners") or []):
                if "NQ" in (s.get("symbol") or ""):
                    log_dir = s.get("path", log_dir)
                    break
    except Exception:
        pass
    if os.path.isdir(log_dir):
        try:
            binary_fills = load_binary_fills(log_dir)
            binary_pairs = fifo_pair_fills(binary_fills)
            print(f"\n3. BINARY: {len(binary_fills)} fills -> {len(binary_pairs)} FIFO-paired trades")
            if binary_pairs:
                print(f"   First: {binary_pairs[0]['entry_dt']} -> {binary_pairs[0]['exit_dt']} {binary_pairs[0]['side']} {binary_pairs[0]['qty']}")
        except ImportError:
            print("\n3. BINARY: (binary_log_parser not importable, skipping)")
            binary_pairs = []
    else:
        print(f"\n3. BINARY: Log dir not found: {log_dir}")
        binary_pairs = []

    # 4. Chart annotations (for reference - no pairing)
    print(f"\n4. CHART: {len(CHART_ANNOTATIONS)} annotations (qty@price)")

    # --- MATCHING ---
    print("\n" + "=" * 80)
    print("MATCHING: Trade List vs Activity Pairs")
    print("=" * 80)

    matched_tl_act = []
    for tl in trade_list:
        for ap in activity_pairs:
            if match_trade(tl, ap):
                matched_tl_act.append((tl, ap))
                break

    print(f"\nTrade List vs Activity: {len(matched_tl_act)} / {len(trade_list)} matched")
    if len(trade_list) > len(matched_tl_act):
        unmatched = len(trade_list) - len(matched_tl_act)
        print(f"  -> {unmatched} trade list rows have no Activity pair (scaling/partials or different pairing)")

    # Trade List vs Binary
    if binary_pairs:
        matched_tl_bin = sum(1 for tl in trade_list for bp in binary_pairs if match_trade(tl, bp))
        print(f"\nTrade List vs Binary FIFO: {matched_tl_bin} / {len(trade_list)} matched")
        print(f"  -> Binary FIFO often differs from SC's order-based pairing")

    # Activity vs Binary (fill-level)
    print(f"\nActivity fills vs Binary fills: {len(fills)} vs {len(binary_fills)}")
    if fills and binary_fills:
        act_by_ts = defaultdict(list)
        for f in fills:
            k = (f["dt"].strftime("%H:%M:%S"), round(f["price"], 2), f["qty"], f["side"])
            act_by_ts[k].append(f)
        bin_matched = 0
        for bf in binary_fills:
            k = (bf["dt"].strftime("%H:%M:%S"), round(bf["price"], 2), bf["qty"], bf["side"])
            if k in act_by_ts:
                bin_matched += 1
        print(f"  -> ~{bin_matched} binary fills have matching Activity fill (time+price+qty+side)")

    # Summary table: first 20 trades
    print("\n" + "=" * 80)
    print("SAMPLE: First 20 Trade List rows vs Activity match")
    print("=" * 80)
    print(f"{'#':<4} {'Entry':<22} {'Exit':<22} {'Side':<6} {'Qty':<4} {'EntryP':<10} {'ExitP':<10} {'Act':<4}")
    print("-" * 100)
    for i, tl in enumerate(trade_list[:20]):
        act_match = "Y" if any(match_trade(tl, ap) for ap in activity_pairs) else "N"
        print(f"{i+1:<4} {str(tl['entry_dt'])[11:22]:<22} {str(tl['exit_dt'])[11:22]:<22} {tl['side']:<6} {tl['qty']:<4} {tl['entry_price']:<10.2f} {tl['exit_price']:<10.2f} {act_match:<4}")

    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("""
Best way to match max trades:
1. TRADE LIST + ACTIVITY: Use Activity Fills with ParentInternalOrderID for pairing.
   - Activity has explicit Open/Close links = exact SC pairing.
   - Trade List is SC's computed view; Activity is the fill-level source.
   - Match rate depends on whether Trade List uses same pairing (it should).

2. BINARY: Binary lacks OpenClose/ParentInternalOrderID in the format.
   - FIFO pairing will NOT match SC when multiple positions overlap.
   - To match binary->SC: need to parse OpenClose from binary (format not documented)
   - Or: use Activity export as primary source instead of binary.

3. CHART: Annotations (qty@price) can validate specific fills by time+price.
   - Use for spot-checks, not systematic pairing.

4. IMPORT STRATEGY: For SC-exact import, use run_sc_first_import.py with
   ALLTradeActivityLogExport (Activity) file - it has ParentInternalOrderID.
""")


if __name__ == "__main__":
    main()
