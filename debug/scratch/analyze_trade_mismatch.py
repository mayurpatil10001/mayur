"""
List binary vs SC trades in one table by chronological order (entry then exit).
Run: python analyze_trade_mismatch.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.test_binary_benchmark_1218 import (
    _load_binary_fills_for_ny_1218,
    _load_trade_list_struct,
    _match_trade,
)
from trading_platform.services.binary_log_parser import BinaryLogParser

ROOT = Path(__file__).resolve().parent
REF_TRADES = ROOT / "1218 nq trade list.txt"
TOL_SEC = 5
TOL_PRICE = 0.5
SEP = "-" * 110


def fmt_ts(d: dt.datetime) -> str:
    return d.strftime("%H:%M:%S.%f")[:-3] if d else ""


def _find_fill_for_exit(fills: list, exit_dt: dt.datetime, exit_price: float, qty: int, side: str):
    """Find a binary fill that matches this exit (time, price, qty, side). Returns fill dict or None."""
    side_bs = "BUY" if side == "Long" else "SELL"
    for f in fills:
        if f.get("quantity") != qty or f.get("side") != side_bs:
            continue
        ts = f.get("timestamp") or f.get("trans_timestamp") or ""
        try:
            t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t.tzinfo:
                t = t.replace(tzinfo=None)
        except Exception:
            continue
        if abs((t - exit_dt).total_seconds()) > TOL_SEC:
            continue
        if abs(float(f.get("price", 0)) - exit_price) > TOL_PRICE:
            continue
        return f
    return None


def main():
    # Fills without ghost -> for pairing (what we actually produce)
    fills = _load_binary_fills_for_ny_1218(use_trans_time=True, include_ghost=False)
    # Fills with ghost -> for annotating SC trades (so we can mark "ghost" when exit fill is ghost)
    fills_with_ghost = _load_binary_fills_for_ny_1218(use_trans_time=True, include_ghost=True)

    parser = BinaryLogParser(db_path=":memory:")
    raw_trades, unpaired, _ = parser._pairs_to_trades(fills, persist_state=False)
    sc_trades = _load_trade_list_struct(REF_TRADES)

    # Trades we would have if we included ghost fills (to find "removed" ghost trades)
    raw_with_ghost, _, _ = parser._pairs_to_trades(fills_with_ghost, persist_state=False)
    trades_with_ghost = set()
    for t in raw_with_ghost:
        e = dt.datetime.fromisoformat(t["entry_time"])
        x = dt.datetime.fromisoformat(t["exit_time"])
        if e >= x:
            continue
        key = (e, x, int(t["quantity"]), (t.get("side") or "").upper()[:5])
        trades_with_ghost.add(key)

    binary_trades = []
    for t in raw_trades:
        e = dt.datetime.fromisoformat(t["entry_time"])
        x = dt.datetime.fromisoformat(t["exit_time"])
        if e >= x:
            continue
        side = "Long" if (t.get("side") or "").upper() == "LONG" else "Short"
        binary_trades.append({
            "entry_dt": e,
            "exit_dt": x,
            "entry_price": float(t["entry_price"]),
            "exit_price": float(t["exit_price"]),
            "qty": int(t["quantity"]),
            "side": side,
        })

    def find_sc_match(bt):
        for sc in sc_trades:
            if _match_trade(bt, sc, TOL_SEC, TOL_PRICE):
                return sc
        return None

    def mismatch_reason(bt, sc_list):
        for sc in sc_list:
            if bt["side"] != sc["side"] or bt["qty"] != sc["qty"]:
                continue
            de = abs((bt["entry_dt"] - sc["entry_dt"]).total_seconds())
            dx = abs((bt["exit_dt"] - sc["exit_dt"]).total_seconds())
            ep = abs(bt["entry_price"] - sc["entry_price"])
            xp = abs(bt["exit_price"] - sc["exit_price"])
            if de <= TOL_SEC and dx <= TOL_SEC and ep <= TOL_PRICE and xp <= TOL_PRICE:
                return "MATCH", sc
        for sc in sc_list:
            if bt["side"] != sc["side"] or bt["qty"] != sc["qty"]:
                continue
            de = abs((bt["entry_dt"] - sc["entry_dt"]).total_seconds())
            dx = abs((bt["exit_dt"] - sc["exit_dt"]).total_seconds())
            ep = abs(bt["entry_price"] - sc["entry_price"])
            xp = abs(bt["exit_price"] - sc["exit_price"])
            entry_ok = de <= TOL_SEC and ep <= TOL_PRICE
            exit_ok = dx <= TOL_SEC and xp <= TOL_PRICE
            if entry_ok and not exit_ok:
                return "SAME_ENTRY_WRONG_EXIT", sc
            if exit_ok and not entry_ok:
                return "SAME_EXIT_WRONG_ENTRY", sc
        for sc in sc_list:
            if bt["side"] != sc["side"] or bt["qty"] != sc["qty"]:
                continue
            return "WRONG_ENTRY_AND_EXIT", sc
        return "NO_SC_CLOSE_MATCH", None

    def why_no_match(sc, use_ghost_fills: list):
        reasons = []
        dur_sec = (sc["exit_dt"] - sc["entry_dt"]).total_seconds()
        if dur_sec > 24 * 3600:
            reasons.append(">24hrs")
        if sc["exit_dt"].time() >= dt.time(17, 0, 0):
            reasons.append("close_after_17:00")
        exit_fill = _find_fill_for_exit(
            use_ghost_fills, sc["exit_dt"], sc["exit_price"], sc["qty"], sc["side"]
        )
        if exit_fill and exit_fill.get("suggests_ghost"):
            reasons.append("ghost")
        if not reasons:
            reasons.append("pairing")
        return "; ".join(reasons)

    binary_trades_set = set()
    for bt in binary_trades:
        binary_trades_set.add((bt["entry_dt"], bt["exit_dt"], bt["qty"], bt["side"]))

    # Removed ghost trades (in pairing with ghost but not in normal pairing)
    removed_ghost = []
    for t in raw_with_ghost:
        e = dt.datetime.fromisoformat(t["entry_time"])
        x = dt.datetime.fromisoformat(t["exit_time"])
        if e >= x:
            continue
        side = "Long" if (t.get("side") or "").upper() == "LONG" else "Short"
        qty = int(t["quantity"])
        key = (e, x, qty, side)
        if key not in binary_trades_set:
            removed_ghost.append((e, x, side, qty, float(t["entry_price"]), float(t["exit_price"])))

    sc_matched_ids = set()
    combined = []  # (entry_dt, exit_dt, side, qty, ep, xp, source, match_or_why)
    for i, bt in enumerate(binary_trades):
        sc = find_sc_match(bt)
        if sc:
            sc_matched_ids.add(id(sc))
            combined.append((bt["entry_dt"], bt["exit_dt"], bt["side"], bt["qty"],
                             bt["entry_price"], bt["exit_price"], "binary", "Yes", "MATCH"))
        else:
            reason, _ = mismatch_reason(bt, sc_trades)
            combined.append((bt["entry_dt"], bt["exit_dt"], bt["side"], bt["qty"],
                             bt["entry_price"], bt["exit_price"], "binary", "No", reason))

    for e, x, side, qty, ep, xp in removed_ghost:
        combined.append((e, x, side, qty, ep, xp, "removed", "-", "ghost"))

    unmatched_sc = [sc for sc in sc_trades if id(sc) not in sc_matched_ids]
    for sc in unmatched_sc:
        why = why_no_match(sc, fills_with_ghost)
        combined.append((sc["entry_dt"], sc["exit_dt"], sc["side"], sc["qty"],
                         sc["entry_price"], sc["exit_price"], "SC_only", "-", why))

    combined.sort(key=lambda r: (r[0], r[1]))

    n_match = sum(1 for r in combined if r[6] == "binary" and r[7] == "Yes")
    n_binary = len(binary_trades)
    lines = []
    lines.append("=" * 110)
    lines.append("TRADE MATCH REPORT: All trades in chronological order (binary + SC-only) — 2025-12-18 V_SIM16")
    lines.append("=" * 110)
    lines.append("")
    lines.append("SUMMARY")
    lines.append("-" * 60)
    lines.append(f"  Binary-derived trades: {n_binary}")
    lines.append(f"  SC trade list trades:   {len(sc_trades)}")
    lines.append(f"  Strict matches:         {n_match} ({100 * n_match / n_binary:.1f}% of binary)")
    n_removed = sum(1 for r in combined if r[6] == "removed")
    lines.append(f"  Removed (ghost):        {n_removed}")
    lines.append(f"  Total rows in table:    {len(combined)} (binary + removed + SC-only, by entry then exit time)")
    lines.append("")
    lines.append("TABLE — ALL TRADES BY ORDER (entry time, then exit time). Source: binary | removed | SC_only. Match=Yes/No for binary; removed=ghost we filtered; SC_only=why (ghost/pairing/close_after_17:00/>24hrs)")
    lines.append("=" * 110)
    lines.append(
        f"{'Entry':<14} {'Exit':<14} {'Side':<6} {'Qty':<3} | {'Entry $':<8} {'Exit $':<8} | {'Source':<8} {'Match':<4} | Reason / Why no match"
    )
    lines.append(SEP)
    for r in combined:
        entry_dt, exit_dt, side, qty, ep, xp, source, match, reason = r
        lines.append(
            f"{fmt_ts(entry_dt):<14} {fmt_ts(exit_dt):<14} {side:<6} {qty:<3} | {ep:<8.2f} {xp:<8.2f} | {source:<8} {match:<4} | {reason}"
        )
        lines.append(SEP)
    lines.append("")

    reason_counts = {}
    for r in combined:
        if r[6] == "binary" and r[7] == "No":
            reason_counts[r[8]] = reason_counts.get(r[8], 0) + 1
    lines.append("Unmatched binary — reason counts:")
    for k, c in sorted(reason_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {k}: {c}")
    lines.append("")

    why_counts = {}
    for r in combined:
        if r[6] == "SC_only":
            for w in r[8].split("; "):
                why_counts[w] = why_counts.get(w, 0) + 1
    lines.append("SC_only (no binary match) — why counts:")
    for w, c in sorted(why_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {w}: {c}")
    lines.append("")
    lines.append("Legend: removed = ghost trade we filtered (exit/entry fill had no note); ghost (SC_only) = SC trade whose exit fill we flag as ghost; pairing = binary did not produce this trade; close_after_17:00 = EOD; >24hrs = duration.")
    lines.append("")

    out = "\n".join(lines)
    print(out)
    out_path = ROOT / "trade_mismatch_report.txt"
    out_path.write_text(out, encoding="utf-8")
    print(f"Report saved to {out_path}")


if __name__ == "__main__":
    main()
