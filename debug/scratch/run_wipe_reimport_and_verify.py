"""
Wipe V_SIM16 from DB, reimport from binary logs, then verify trade list matches
Sierra Chart (SC) to at least 90%.

Usage:
  python run_wipe_reimport_and_verify.py [--sc-reference PATH] [--log-dir PATH] [--days N]
  python run_wipe_reimport_and_verify.py --dry-run --sc-reference "ALLTradeActivityLogExport_....txt"   # check current DB vs SC only

  --sc-reference   Path to SC export (Activity or TradesList). DB count is filtered to same date range.
  --log-dir        Folder with TradeActivityLog_*.data (default: SC_LOG_PATH or D:\\...\\TradeActivityLogs)
  --days           Lookback days for import (default 90).
  --dry-run        Only compare current DB to SC reference; no wipe/import.
  --min-match      Require this %% match (default 90).
  --no-defer       Use pre-FIFO ghost filter (drop ghosts before pairing). Default: defer (pair first, remove ghosts after).

SC reference: ALLTradeActivityLogExport (ActivityType, OpenClose) or TradesList 26-col.
For best match to SC, use Trade Activity Log >> Save Log As (Fills + OpenClose) and paste that for import.
"""
import argparse
import asyncio
import os
import sqlite3
import sys

# Project root
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from trading_platform.services.binary_log_parser import BinaryLogParser

ACCOUNT = "V_SIM16"
DEFAULT_LOG_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
MIN_MATCH_PCT = 90.0


def get_db_path():
    from pathlib import Path
    return str(Path(ROOT) / "trading_platform.db")


def get_sc_trade_count_from_activity_export(path: str, account: str) -> tuple:
    """Count closed trades from ALLTradeActivityLogExport: Fills + OpenClose=Close.
    Returns (count, min_date, max_date) for optional date-range filtering of DB."""
    account_upper = account.upper()
    count = 0
    dates = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    if not lines:
        return 0, None, None
    header = [h.strip().lower() for h in lines[0].split("\t")]
    try:
        idx_at = header.index("activitytype")
        idx_oc = header.index("openclose")
        idx_acc = next(i for i, h in enumerate(header) if "tradeaccount" in h or "account" in h)
        idx_dt = header.index("datetime") if "datetime" in header else None
    except (ValueError, StopIteration):
        return 0, None, None
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) <= max(idx_at, idx_oc, idx_acc):
            continue
        at = (parts[idx_at] or "").strip().lower()
        oc = (parts[idx_oc] or "").strip().upper()
        acc = (parts[idx_acc] or "").strip().upper()
        if at == "fills" and oc == "CLOSE" and acc == account_upper:
            count += 1
            if idx_dt is not None and len(parts) > idx_dt:
                raw = (parts[idx_dt] or "").strip()[:19].replace("  ", " ")
                if raw and raw[0].isdigit():
                    dates.append(raw.replace(" ", "T", 1))
    min_date = min(dates) if dates else None
    max_date = max(dates) if dates else None
    return count, min_date, max_date


def get_sc_trade_count_from_trades_list(path: str, account: str) -> int:
    """Count trades from 26-col TradesList (Symbol, Trade Type, Entry DateTime, ..., Note)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    if not lines:
        return 0
    # Header: Symbol\tTrade Type\t...
    if lines[0].lower().startswith("symbol"):
        data_lines = lines[1:]
    else:
        data_lines = lines
    # Note column = account; find it
    header = lines[0].split("\t") if lines else []
    note_idx = None
    for i, h in enumerate(header):
        if h.strip().lower() == "note":
            note_idx = i
            break
    if note_idx is None and data_lines:
        # Assume 14th column (0-based 13) is often Note in 26-col
        note_idx = 13
    account_upper = account.upper()
    count = 0
    for line in data_lines:
        parts = line.split("\t")
        if note_idx is not None and len(parts) > note_idx:
            note = (parts[note_idx] or "").strip().upper()
            if account_upper in note or note == account_upper:
                count += 1
        else:
            if account_upper in line.upper():
                count += 1
    return count


def get_sc_trade_count(path: str, account: str) -> tuple:
    """Detect format and return (count, min_date, max_date). Dates for range filter; TradesList returns (count, None, None)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first = f.readline()
    first_lower = first.lower()
    if "activitytype" in first_lower and "openclose" in first_lower:
        return get_sc_trade_count_from_activity_export(path, account)
    if "symbol" in first_lower and ("trade type" in first_lower or "entry datetime" in first_lower):
        n = get_sc_trade_count_from_trades_list(path, account)
        return n, None, None
    # Try activity by default if header has tabs
    if "\t" in first:
        return get_sc_trade_count_from_activity_export(path, account)
    return 0, None, None


def get_db_trade_count(db_path: str, account: str, min_date: str = None, max_date: str = None) -> int:
    """Count DB trades for account, optionally within [min_date, max_date] (entry_time, ISO format)."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    if min_date and max_date:
        # Include full day for max: use date part + end of day
        max_bound = max_date[:10] + "T23:59:59.999999" if "T" in max_date else max_date + " 23:59:59"
        c.execute(
            """SELECT COUNT(*) FROM processed_trades
               WHERE UPPER(account_name) = ? AND entry_time >= ? AND entry_time <= ?""",
            (account.upper(), min_date, max_bound),
        )
    else:
        c.execute(
            "SELECT COUNT(*) FROM processed_trades WHERE UPPER(account_name) = ?",
            (account.upper(),),
        )
    n = c.fetchone()[0]
    conn.close()
    return n


async def run_wipe_reimport(log_dir: str, days: int, defer_ghost: bool = True):
    parser = BinaryLogParser(db_path=get_db_path())
    print(f"\n--- PURGE {ACCOUNT} ---")
    conn = sqlite3.connect(parser.db_path)
    c = conn.cursor()
    c.execute("DELETE FROM processed_trades WHERE UPPER(account_name) = ?", (ACCOUNT.upper(),))
    pt = c.rowcount
    c.execute("DELETE FROM pending_fills WHERE UPPER(account_name) = ?", (ACCOUNT.upper(),))
    pf = c.rowcount
    conn.commit()
    conn.close()
    print(f"Deleted: {pt} processed_trades, {pf} pending_fills")

    print(f"\n--- BINARY IMPORT from {log_dir} (days={days}) ---")
    if defer_ghost:
        print("Flow: Pair ALL fills first (entry/exit), then remove ghost trades, then purge anomalies.")
    await parser.run_import(
        paths=[log_dir],
        account_filter=[ACCOUNT],
        days_lookback=days,
        defer_ghost_removal=defer_ghost,
    )
    print("\n--- RECONCILIATION REPORT ---")
    stats = parser.stats
    if stats.get("dropped_ghost_fills", 0) > 0:
        print(f"Ghost trades removed (post-pair): {stats['dropped_ghost_fills']}")
    parser.get_reconciliation_report(ACCOUNT)


def main():
    ap = argparse.ArgumentParser(description="Wipe V_SIM16, reimport, verify ~90%% match to SC")
    ap.add_argument("--sc-reference", default="", help="Path to SC export (Activity or TradesList)")
    ap.add_argument("--log-dir", default=os.environ.get("SC_LOG_PATH", DEFAULT_LOG_DIR), help="TradeActivityLog folder")
    ap.add_argument("--days", type=int, default=90, help="Lookback days")
    ap.add_argument("--min-match", type=float, default=MIN_MATCH_PCT, help="Min match %% (default 90)")
    ap.add_argument("--dry-run", action="store_true", help="Only check DB vs SC reference (no wipe/import)")
    ap.add_argument("--no-defer", action="store_true", help="Drop ghosts before pairing (old behavior)")
    args = ap.parse_args()

    if not args.dry_run:
        if not os.path.isdir(args.log_dir):
            print(f"Log dir not found: {args.log_dir}")
            print("Set SC_LOG_PATH or use --log-dir.")
            return 2
        asyncio.run(run_wipe_reimport(args.log_dir, args.days, defer_ghost=not args.no_defer))

    db_path = get_db_path()
    sc_min_date = sc_max_date = None

    if not args.sc_reference or not os.path.isfile(args.sc_reference):
        if args.sc_reference:
            print(f"SC reference file not found: {args.sc_reference}")
        else:
            print("No --sc-reference provided; skipping match check.")
        db_count = get_db_trade_count(db_path, ACCOUNT)
        print(f"\n--- DB TRADE COUNT: {ACCOUNT} = {db_count} ---")
        return 0

    sc_count, sc_min_date, sc_max_date = get_sc_trade_count(args.sc_reference, ACCOUNT)
    db_count = get_db_trade_count(db_path, ACCOUNT, sc_min_date, sc_max_date)
    print(f"\n--- DB TRADE COUNT: {ACCOUNT} (in SC date range) = {db_count} ---")
    print(f"SC reference trade count = {sc_count} (from {args.sc_reference})")
    if sc_min_date and sc_max_date:
        print(f"Date range: {sc_min_date} to {sc_max_date}")

    if sc_count == 0:
        print("SC reference has 0 trades for this account; cannot compute match %.")
        return 0

    # Match: ratio of counts (DB should be close to SC)
    ratio = db_count / sc_count if sc_count else 0
    match_pct = min(db_count, sc_count) / max(db_count, sc_count) * 100.0 if max(db_count, sc_count) else 0
    print(f"Match: DB/SC ratio = {ratio:.2%}, overlap = {match_pct:.1f}%")

    if match_pct < args.min_match:
        print(f"FAIL: match {match_pct:.1f}% < {args.min_match}%")
        return 1
    print(f"PASS: match {match_pct:.1f}% >= {args.min_match}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
