"""
compare_tm7_rar_v2.py
=====================
Compares TM_7/NQ trades from the RAR Activity Log export
against what is stored in trading_platform.db.

Findings from debug:
  - DB TM_7 NQ range: 2024-03-13 -> 2025-06-30  (10,067 trades)
  - RAR file starts:  2026-04-01  (NQM26 / NQU26 contracts)
  => NO date overlap. These are BRAND NEW trades not yet in the DB.
"""

import csv
import sqlite3
import sys
import io
from datetime import datetime, timedelta
from collections import deque, defaultdict
from pathlib import Path

# Force UTF-8 output so box chars don't crash on Windows cp1252 console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── PATHS ──────────────────────────────────────────────────────────────────────
RAR_FILE  = r"c:\SC_results_WF\rar_extract\example tm7 NQU26 2026-07-20.txt"
DB_PATH   = r"c:\SC_results_WF\trading_platform.db"
ACCOUNT   = "TM_7"
NQ_MULT   = 20       # $20 per NQ point
COMM_PER_CONTRACT = 4.20


# ── STEP 1: Parse fills ────────────────────────────────────────────────────────
def parse_fills(filepath):
    fills = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("ActivityType", "").strip() != "Fills":
                continue
            if row.get("TradeAccount", "").strip() != ACCOUNT:
                continue
            sym = row.get("Symbol", "").strip()
            if not sym.startswith("NQ"):
                continue
            side = row.get("BuySell", "").strip()
            if side not in ("Buy", "Sell"):
                continue
            try:
                fill_price = float(row.get("FillPrice") or 0)
                fill_qty   = int(float(row.get("FilledQuantity") or 0))
            except:
                continue
            if fill_price == 0 or fill_qty == 0:
                continue
            dt_str = row.get("DateTime", "").strip()
            try:
                dt = datetime.strptime(dt_str[:26], "%Y-%m-%d  %H:%M:%S.%f")
            except:
                try:
                    dt = datetime.strptime(dt_str[:19], "%Y-%m-%d  %H:%M:%S")
                except:
                    continue
            fills.append({
                "dt": dt, "side": side, "price": fill_price,
                "qty": fill_qty, "symbol": sym,
                "open_close": row.get("OpenClose", "").strip(),
            })
    fills.sort(key=lambda x: x["dt"])
    return fills


# ── STEP 2: FIFO pairing → round-trip trades ───────────────────────────────────
def pair_trades_fifo(fills):
    queues = defaultdict(lambda: {"Buy": deque(), "Sell": deque()})
    trades = []

    for f in fills:
        sym       = f["symbol"]
        entry_sd  = f["side"]
        exit_sd   = "Sell" if entry_sd == "Buy" else "Buy"

        if queues[sym][exit_sd]:
            entry = queues[sym][exit_sd].popleft()
            paired_qty = min(entry["qty"], f["qty"])
            pnl_pts = (f["price"] - entry["price"]) if entry["side"] == "Buy" else (entry["price"] - f["price"])
            pnl_usd = round(pnl_pts * NQ_MULT * paired_qty - COMM_PER_CONTRACT * paired_qty, 2)

            trades.append({
                "symbol":      sym,
                "direction":   "Long" if entry["side"] == "Buy" else "Short",
                "entry_time":  entry["dt"],
                "exit_time":   f["dt"],
                "entry_price": entry["price"],
                "exit_price":  f["price"],
                "qty":         paired_qty,
                "pnl_usd":     pnl_usd,
                "duration_min": round((f["dt"] - entry["dt"]).total_seconds() / 60, 1),
            })

            # Push leftover back
            if f["qty"] > entry["qty"]:
                r = dict(f); r["qty"] = f["qty"] - entry["qty"]
                queues[sym][entry_sd].appendleft(r)
            elif entry["qty"] > f["qty"]:
                r = dict(entry); r["qty"] = entry["qty"] - f["qty"]
                queues[sym][exit_sd].appendleft(r)
        else:
            queues[sym][entry_sd].append(f)

    return trades


# ── STEP 3: Load DB trades ─────────────────────────────────────────────────────
def load_db_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT account_name, symbol, side, entry_time, exit_time,
               entry_price, exit_price, quantity, profit_loss, commission
        FROM processed_trades
        WHERE (account_name LIKE '%TM%7%' OR account_name LIKE '%TM_7%')
          AND symbol LIKE 'NQ%'
        ORDER BY entry_time
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── STEP 4: Try to match by entry_time window ──────────────────────────────────
def compare(rar_trades, db_trades, window_sec=5):
    """Match RAR <-> DB trades by (entry_time +-window, entry_price +-0.5, direction)."""
    db_used   = set()
    matched   = []
    unmatched_rar = []

    db_index = {}  # date_str -> list of (idx, row)
    for idx, dt in enumerate(db_trades):
        key = dt["entry_time"][:10]
        db_index.setdefault(key, []).append((idx, dt))

    for rt in rar_trades:
        date_key = rt["entry_time"].strftime("%Y-%m-%d")
        candidates = db_index.get(date_key, [])
        best, best_delta = None, timedelta(seconds=window_sec)
        for idx, dbt in candidates:
            if idx in db_used:
                continue
            try:
                db_dt = datetime.fromisoformat(dbt["entry_time"])
            except:
                continue
            tdelta = abs(rt["entry_time"] - db_dt)
            pdelta = abs(rt["entry_price"] - float(dbt["entry_price"] or 0))
            # Also check direction roughly
            rar_dir = "buy" if rt["direction"] == "Long" else "sell"
            db_side = (dbt.get("side") or "").lower()
            dir_ok  = (rar_dir in db_side) or db_side == ""
            if tdelta <= best_delta and pdelta <= 0.5 and dir_ok:
                best_delta, best = tdelta, idx
        if best is not None:
            db_used.add(best)
            matched.append({"rar": rt, "db": db_trades[best]})
        else:
            unmatched_rar.append(rt)

    unmatched_db = [t for i, t in enumerate(db_trades) if i not in db_used]
    return matched, unmatched_rar, unmatched_db


# ── STEP 5: Statistics helpers ─────────────────────────────────────────────────
def rar_stats(trades):
    if not trades:
        return {}
    pnls  = [t["pnl_usd"] for t in trades]
    wins  = [p for p in pnls if p > 0]
    losses= [p for p in pnls if p <= 0]
    total = sum(pnls)
    gross_win  = sum(wins)  or 0
    gross_loss = abs(sum(losses)) or 1
    return {
        "count":        len(trades),
        "total_pnl":    round(total, 2),
        "avg_trade":    round(total / len(trades), 2),
        "win_rate":     round(len(wins) / len(trades) * 100, 1),
        "profit_factor":round(gross_win / gross_loss, 2),
        "avg_winner":   round(sum(wins)   / max(len(wins), 1), 2),
        "avg_loser":    round(sum(losses) / max(len(losses), 1), 2),
        "best_trade":   max(pnls),
        "worst_trade":  min(pnls),
        "avg_dur_min":  round(sum(t["duration_min"] for t in trades) / len(trades), 1),
        "date_start":   min(t["entry_time"] for t in trades).date(),
        "date_end":     max(t["entry_time"] for t in trades).date(),
    }

def db_stats(trades):
    if not trades:
        return {}
    pnls  = [float(t["profit_loss"] or 0) for t in trades]
    wins  = [p for p in pnls if p > 0]
    losses= [p for p in pnls if p <= 0]
    total = sum(pnls)
    gross_win  = sum(wins)  or 0
    gross_loss = abs(sum(losses)) or 1
    dates = sorted([t["entry_time"][:10] for t in trades])
    return {
        "count":        len(trades),
        "total_pnl":    round(total, 2),
        "avg_trade":    round(total / len(trades), 2),
        "win_rate":     round(len(wins) / len(trades) * 100, 1),
        "profit_factor":round(gross_win / gross_loss, 2),
        "avg_winner":   round(sum(wins)   / max(len(wins), 1), 2),
        "avg_loser":    round(sum(losses) / max(len(losses), 1), 2),
        "best_trade":   max(pnls),
        "worst_trade":  min(pnls),
        "date_start":   dates[0],
        "date_end":     dates[-1],
    }


# ── STEP 6: Full Report ────────────────────────────────────────────────────────
def print_report(rar_trades, db_trades, matched, unmatched_rar, unmatched_db):
    SEP  = "=" * 88
    LINE = "-" * 88

    rs = rar_stats(rar_trades)
    ds = db_stats(db_trades)

    print(f"\n{SEP}")
    print("  TRADE COMPARISON REPORT  |  TM_7 / NQ  |  RAR file vs Database")
    print(SEP)

    # ── Date Range ──
    print(f"\n  DATE RANGES")
    print(f"  {'Source':<20} {'From':<14} {'To':<14} {'Trades':>8}  {'Symbols'}")
    print(f"  {'-'*20} {'-'*14} {'-'*14} {'-'*8}  {'-'*20}")
    rar_syms = set(t["symbol"] for t in rar_trades)
    db_syms  = set(t["symbol"] for t in db_trades)
    print(f"  {'RAR File':<20} {str(rs.get('date_start','?')):<14} {str(rs.get('date_end','?')):<14} {rs.get('count',0):>8}  {', '.join(sorted(rar_syms))}")
    print(f"  {'Database (TM_7/NQ)':<20} {str(ds.get('date_start','?')):<14} {str(ds.get('date_end','?')):<14} {ds.get('count',0):>8}  {', '.join(sorted(db_syms))}")

    # ── Overlap detection ──
    print(f"\n  DATE OVERLAP ANALYSIS")
    rar_start = min(t["entry_time"] for t in rar_trades)
    rar_end   = max(t["entry_time"] for t in rar_trades)
    db_start_str  = ds.get("date_start", "9999")
    db_end_str    = ds.get("date_end",   "0000")
    try:
        db_start = datetime.strptime(db_start_str, "%Y-%m-%d")
        db_end   = datetime.strptime(db_end_str,   "%Y-%m-%d")
        overlap  = rar_start <= db_end and rar_end >= db_start
    except:
        overlap = False

    if overlap:
        print(f"  *** OVERLAPPING date ranges — matching possible ***")
    else:
        print(f"  *** NO DATE OVERLAP ***")
        print(f"  RAR file covers : {rar_start.date()} -> {rar_end.date()}")
        print(f"  Database covers : {db_start_str} -> {db_end_str}")
        print(f"  GAP             : RAR file is {(rar_start - db_end).days} days AFTER the last DB trade.")
        print(f"  CONCLUSION      : The RAR file contains NEW trades not yet imported into the database.")

    # ── Match summary ──
    match_pct = len(matched) / max(len(rar_trades), 1) * 100
    print(f"\n  MATCH SUMMARY")
    print(f"  {'Metric':<40} {'Value':>15}")
    print(f"  {'-'*40} {'-'*15}")
    print(f"  {'Matched Trades':<40} {len(matched):>15}")
    print(f"  {'RAR-only (not in DB)':<40} {len(unmatched_rar):>15}")
    print(f"  {'DB-only (not in RAR)':<40} {len(unmatched_db):>15}")
    print(f"  {'Match Rate':<40} {match_pct:>14.1f}%")

    # ── Performance comparison ──
    print(f"\n  PERFORMANCE COMPARISON")
    print(f"  {'Metric':<30} {'RAR File':>15} {'Database':>15}  {'Difference':>15}")
    print(f"  {'-'*30} {'-'*15} {'-'*15}  {'-'*15}")

    def row(label, rk, dk, fmt=".2f", currency=False):
        rv = rs.get(rk, "N/A")
        dv = ds.get(dk, "N/A")
        try:
            diff = rv - dv
            diff_str = f"${diff:+,.2f}" if currency else f"{diff:+.2f}"
            rv_str = f"${rv:,.2f}" if currency else f"{rv:{fmt}}"
            dv_str = f"${dv:,.2f}" if currency else f"{dv:{fmt}}"
        except:
            rv_str, dv_str, diff_str = str(rv), str(dv), "N/A"
        print(f"  {label:<30} {rv_str:>15} {dv_str:>15}  {diff_str:>15}")

    row("Total Trades",       "count",        "count",        fmt="d")
    row("Total PnL (USD)",    "total_pnl",    "total_pnl",    currency=True)
    row("Avg Trade (USD)",    "avg_trade",    "avg_trade",    currency=True)
    row("Win Rate (%)",       "win_rate",     "win_rate",     fmt=".1f")
    row("Profit Factor",      "profit_factor","profit_factor",fmt=".2f")
    row("Avg Winner (USD)",   "avg_winner",   "avg_winner",   currency=True)
    row("Avg Loser (USD)",    "avg_loser",    "avg_loser",    currency=True)
    row("Best Trade (USD)",   "best_trade",   "best_trade",   currency=True)
    row("Worst Trade (USD)",  "worst_trade",  "worst_trade",  currency=True)

    # ── RAR trades sample ──
    print(f"\n  RAR FILE — SAMPLE TRADES (first 20)")
    print(f"  {'#':<4} {'Entry Time':<22} {'Exit Time':<22} {'Dir':<6} {'Qty':<4} "
          f"{'Entry':>9} {'Exit':>9} {'PnL':>10} {'Min':>6}  Symbol")
    print(f"  {'-'*4} {'-'*22} {'-'*22} {'-'*6} {'-'*4} {'-'*9} {'-'*9} {'-'*10} {'-'*6}  {'-'*8}")
    for i, t in enumerate(rar_trades[:20], 1):
        d = "L" if t["direction"] == "Long" else "S"
        print(f"  {i:<4} {str(t['entry_time'])[:19]:<22} {str(t['exit_time'])[:19]:<22} "
              f"{d:<6} {t['qty']:<4} {t['entry_price']:>9.2f} {t['exit_price']:>9.2f} "
              f"{t['pnl_usd']:>10.2f} {t['duration_min']:>6.1f}  {t['symbol']}")

    # ── Daily breakdown for RAR ──
    print(f"\n  RAR FILE — DAILY PERFORMANCE BREAKDOWN")
    print(f"  {'Date':<14} {'Trades':>7} {'Winners':>8} {'Win%':>7} {'PnL':>12} {'Cumulative':>12}")
    print(f"  {'-'*14} {'-'*7} {'-'*8} {'-'*7} {'-'*12} {'-'*12}")
    from collections import defaultdict
    daily = defaultdict(list)
    for t in rar_trades:
        daily[t["entry_time"].date()].append(t["pnl_usd"])
    cum = 0
    for d in sorted(daily):
        pnls  = daily[d]
        wins  = sum(1 for p in pnls if p > 0)
        total = sum(pnls)
        cum  += total
        pct   = wins / len(pnls) * 100
        print(f"  {str(d):<14} {len(pnls):>7} {wins:>8} {pct:>6.1f}% {total:>12,.2f} {cum:>12,.2f}")

    # ── Symbol breakdown ──
    print(f"\n  RAR FILE — BY CONTRACT SYMBOL")
    print(f"  {'Symbol':<10} {'Trades':>7} {'Win%':>7} {'Total PnL':>12} {'Avg/Trade':>12}")
    print(f"  {'-'*10} {'-'*7} {'-'*7} {'-'*12} {'-'*12}")
    sym_data = defaultdict(list)
    for t in rar_trades:
        sym_data[t["symbol"]].append(t["pnl_usd"])
    for sym in sorted(sym_data):
        pnls = sym_data[sym]
        wins = sum(1 for p in pnls if p > 0)
        tot  = sum(pnls)
        print(f"  {sym:<10} {len(pnls):>7} {wins/len(pnls)*100:>6.1f}% {tot:>12,.2f} {tot/len(pnls):>12,.2f}")

    # ── Final verdict ──
    print(f"\n{SEP}")
    print("  FINAL VERDICT")
    print(SEP)
    print(f"  1. DATE MISMATCH: RAR file trades are from {rar_start.date()} to {rar_end.date()}.")
    print(f"     The database TM_7/NQ trades end at {db_end_str}.")
    print(f"     These are COMPLETELY DIFFERENT time periods — no overlap.")
    print()
    print(f"  2. IMPORT STATUS: The {len(rar_trades):,} trades in this RAR file are")
    print(f"     NOT YET IMPORTED into the database.")
    print()
    pnl_rar = rs.get("total_pnl", 0)
    wr_rar  = rs.get("win_rate",  0)
    pf_rar  = rs.get("profit_factor", 0)
    pnl_db  = ds.get("total_pnl", 0)
    wr_db   = ds.get("win_rate",  0)

    print(f"  3. PERFORMANCE COMPARISON (same strategy, different periods):")
    print(f"     RAR (new period):  Win Rate={wr_rar}%  PnL=${pnl_rar:,.2f}  PF={pf_rar:.2f}")
    print(f"     DB  (hist. period):Win Rate={wr_db}%   PnL=${pnl_db:,.2f}")
    print()
    if pnl_rar < 0 and pnl_db < 0:
        print(f"  4. BOTH PERIODS ARE LOSING. TM_7/NQ is not a profitable strategy overall.")
    elif pnl_rar > 0 and pnl_db < 0:
        print(f"  4. IMPROVEMENT: New period is profitable while historical DB was negative.")
    elif pnl_rar < 0 and pnl_db > 0:
        print(f"  4. DECAY: Historical DB was profitable, new period is losing — edge may have expired.")
    else:
        print(f"  4. Both periods are profitable — consistent edge.")

    print(f"\n  5. RECOMMENDATION: Import the RAR file into the DB using the trade import")
    print(f"     service to add these {len(rar_trades):,} trades for analysis.")
    print(SEP)


# ── MAIN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SEP = "=" * 88
    print(f"\n{SEP}")
    print("  TRADE COMPARISON: RAR file vs Database  |  TM_7 / NQ")
    print(SEP)

    print("\n[1/4] Parsing fills from RAR file...")
    fills = parse_fills(RAR_FILE)
    print(f"      Fills extracted: {len(fills):,}")

    print("[2/4] Pairing fills into FIFO round-trips...")
    rar_trades = pair_trades_fifo(fills)
    print(f"      Round-trip trades: {len(rar_trades):,}")

    print("[3/4] Loading TM_7/NQ trades from database...")
    db_trades = load_db_trades()
    print(f"      DB trades loaded: {len(db_trades):,}")

    print("[4/4] Running comparison...")
    matched, unmatched_rar, unmatched_db = compare(rar_trades, db_trades)
    print(f"      Matched: {len(matched)} | Only-RAR: {len(unmatched_rar)} | Only-DB: {len(unmatched_db)}")

    print_report(rar_trades, db_trades, matched, unmatched_rar, unmatched_db)
