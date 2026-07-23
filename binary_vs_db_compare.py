"""
binary_vs_db_compare.py
========================
1. Runs BinaryLogParser.run_import() on the TM_7 .data files for a
   chosen date window (same range already in processed_trades)
2. Reads what the parser wrote to a SCRATCH copy of the DB
3. Compares those parser-generated trades field-by-field against
   the original processed_trades rows for the same window
4. Reports matches, mismatches, and missing trades

This directly answers: "are the trades in the DB identical to what
the binary parser generates today from the raw .data files?"
"""

import sys, io, shutil, sqlite3, os, hashlib
sys.path.insert(0, r"c:\SC_results_WF")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import asyncio

# ── Config ─────────────────────────────────────────────────────────────────────
DATASET_DIR   = r"c:\SC_results_WF\dataset"
ORIG_DB       = r"c:\SC_results_WF\trading_platform.db"
SCRATCH_DB    = r"c:\SC_results_WF\scratch_parser_test.db"
ACCOUNT       = "TM_7"          # account name in filenames (case-insensitive)
# Date range to compare (must overlap with what's in processed_trades)
DATE_FROM     = "2024-03-13"    # first date in DB for TM_7/NQ
DATE_TO       = "2025-06-30"    # last date in DB for TM_7/NQ

SEP  = "="*88
LINE = "-"*88

print(f"\n{SEP}")
print("  BINARY PARSER vs DATABASE COMPARISON  |  TM_7 / NQ")
print(f"  Range: {DATE_FROM} → {DATE_TO}")
print(SEP)

# ── STEP 1: Build list of TM_7 .data files in the date window ──────────────────
print(f"\n[1/5] Collecting TM_7 .data files in date range {DATE_FROM} to {DATE_TO}...")
import re

from_dt = datetime.strptime(DATE_FROM, "%Y-%m-%d")
to_dt   = datetime.strptime(DATE_TO,   "%Y-%m-%d")

target_files = []
for f in sorted(Path(DATASET_DIR).glob("*TM_7*.data")):
    m = re.search(r'(\d{4}-\d{2}-\d{2})', f.name)
    if not m:
        continue
    try:
        fdate = datetime.strptime(m.group(1), "%Y-%m-%d")
    except:
        continue
    if from_dt <= fdate <= to_dt:
        target_files.append(str(f))

print(f"      Files found: {len(target_files)}")
if target_files:
    print(f"      First:  {Path(target_files[0]).name}")
    print(f"      Last:   {Path(target_files[-1]).name}")

# ── STEP 2: Copy DB schema to scratch DB, run BinaryLogParser on those files ──
print(f"\n[2/5] Setting up scratch database and running BinaryLogParser.run_import()...")

# Remove old scratch DB
if os.path.exists(SCRATCH_DB):
    os.remove(SCRATCH_DB)

# Copy schema from original DB (empty tables)
src = sqlite3.connect(ORIG_DB)
dst = sqlite3.connect(SCRATCH_DB)
src.backup(dst)   # full backup — we want the schema AND existing data for comparison
dst.close()
src.close()

# NOW wipe only processed_trades in scratch so the parser fills it fresh
scratch = sqlite3.connect(SCRATCH_DB)
scratch.execute("DELETE FROM processed_trades WHERE account_name = ?", (ACCOUNT,))
scratch.commit()
scratch.close()

print(f"      Scratch DB created at: {SCRATCH_DB}")
print(f"      Running parser on {len(target_files)} files (this may take a minute)...")

# Run the parser
from trading_platform.services.binary_log_parser import BinaryLogParser

parser = BinaryLogParser(db_path=SCRATCH_DB)

# run_import(paths, account_filter) — pass exact file list + account filter
async def do_import():
    await parser.run_import(
        paths=target_files,
        account_filter=[ACCOUNT],
    )

asyncio.run(do_import())

print("      Parser run complete.")

# ── STEP 3: Load parser-generated trades from scratch ─────────────────────────
print(f"\n[3/5] Loading parser-generated trades from scratch DB...")
scratch = sqlite3.connect(SCRATCH_DB)
scratch.row_factory = sqlite3.Row

cur = scratch.cursor()
cur.execute("""
    SELECT account_name, symbol, side, entry_time, exit_time,
           entry_price, exit_price, quantity, profit_loss, commission,
           duration_minutes, hour_of_day, day_of_week
    FROM processed_trades
    WHERE account_name = ? AND symbol = 'NQ'
      AND entry_time >= ? AND entry_time <= ?
    ORDER BY entry_time
""", (ACCOUNT, DATE_FROM, DATE_TO + "T23:59:59"))
parser_trades = [dict(r) for r in cur.fetchall()]
scratch.close()

print(f"      Parser-generated trades (NQ, date range): {len(parser_trades):,}")

# ── STEP 4: Load original DB trades for same range ────────────────────────────
print(f"\n[4/5] Loading original DB trades for same range...")
orig = sqlite3.connect(ORIG_DB)
orig.row_factory = sqlite3.Row

cur2 = orig.cursor()
cur2.execute("""
    SELECT account_name, symbol, side, entry_time, exit_time,
           entry_price, exit_price, quantity, profit_loss, commission,
           duration_minutes, hour_of_day, day_of_week
    FROM processed_trades
    WHERE account_name = ? AND symbol = 'NQ'
      AND entry_time >= ? AND entry_time <= ?
    ORDER BY entry_time
""", (ACCOUNT, DATE_FROM, DATE_TO + "T23:59:59"))
db_trades = [dict(r) for r in cur2.fetchall()]
orig.close()

print(f"      Original DB trades (NQ, date range):      {len(db_trades):,}")

# ── STEP 5: Field-by-field comparison ─────────────────────────────────────────
print(f"\n[5/5] Performing field-by-field comparison...")

# Index by date for fuzzy matching
def by_date(trades):
    d = defaultdict(list)
    for i, t in enumerate(trades):
        d[(t["entry_time"] or "")[:10]].append((i, t))
    return d

parser_by_date = by_date(parser_trades)
db_by_date     = by_date(db_trades)

parser_used = set()
db_used     = set()
matched     = []  # (parser_trade, db_trade, field_diffs)
only_parser = []
only_db     = []

for pi, pt in enumerate(parser_trades):
    date_key = (pt["entry_time"] or "")[:10]
    cands    = db_by_date.get(date_key, [])
    best_di, best_delta = None, timedelta(seconds=5)

    try:
        pt_dt = datetime.fromisoformat(pt["entry_time"])
    except:
        only_parser.append(pt)
        continue

    for di, dt in cands:
        if di in db_used:
            continue
        try:
            db_dt = datetime.fromisoformat(dt["entry_time"])
        except:
            continue
        td = abs(pt_dt - db_dt)
        pd = abs(float(pt["entry_price"] or 0) - float(dt["entry_price"] or 0))
        sd = (pt.get("side") or "") == (dt.get("side") or "")
        if td <= best_delta and pd <= 0.5 and sd:
            best_delta, best_di = td, di

    if best_di is not None:
        db_used.add(best_di)
        parser_used.add(pi)
        db_t = db_trades[best_di]

        # Compare every field
        diffs = {}
        for field in ["side", "entry_price", "exit_price", "quantity",
                      "profit_loss", "commission", "duration_minutes",
                      "hour_of_day", "day_of_week"]:
            pv = pt.get(field)
            dv = db_t.get(field)
            try:
                if isinstance(pv, float) or isinstance(dv, float):
                    diff = abs(float(pv or 0) - float(dv or 0))
                    if diff > 0.01:
                        diffs[field] = (pv, dv, diff)
                elif str(pv) != str(dv):
                    diffs[field] = (pv, dv, None)
            except:
                if str(pv) != str(dv):
                    diffs[field] = (pv, dv, None)

        matched.append((pt, db_t, diffs))
    else:
        only_parser.append(pt)

only_db = [t for i, t in enumerate(db_trades) if i not in db_used]

# ── Report ─────────────────────────────────────────────────────────────────────
match_pct = len(matched) / max(len(parser_trades), 1) * 100
exact_pct = sum(1 for _, _, d in matched if not d) / max(len(matched), 1) * 100

# PnL stats
def pnl_stats(trades, pnl_key="profit_loss"):
    pnls = [float(t.get(pnl_key) or 0) for t in trades]
    if not pnls:
        return {}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    return {
        "n": len(pnls),
        "total": round(sum(pnls), 2),
        "avg": round(sum(pnls) / len(pnls), 2),
        "wr": round(len(wins) / len(pnls) * 100, 1),
    }

ps = pnl_stats(parser_trades)
ds = pnl_stats(db_trades)

print(f"\n\n{SEP}")
print("  COMPARISON REPORT  |  BinaryLogParser (fresh) vs DB (stored)")
print(SEP)

print(f"\n  TRADE COUNT COMPARISON")
print(f"  {'Source':<40} {'Trades':>8} {'PnL':>14} {'Avg/Trade':>12} {'WinRate':>9}")
print(f"  {'-'*40} {'-'*8} {'-'*14} {'-'*12} {'-'*9}")
print(f"  {'Parser (re-parsed from .data files)':<40} {ps.get('n',0):>8,} "
      f"{ps.get('total',0):>14,.2f} {ps.get('avg',0):>12,.2f} {ps.get('wr',0):>8.1f}%")
print(f"  {'Database (stored processed_trades)':<40} {ds.get('n',0):>8,} "
      f"{ds.get('total',0):>14,.2f} {ds.get('avg',0):>12,.2f} {ds.get('wr',0):>8.1f}%")
diff_n    = ps.get("n", 0) - ds.get("n", 0)
diff_pnl  = ps.get("total", 0) - ds.get("total", 0)
print(f"  {'DIFFERENCE':<40} {diff_n:>+8,} {diff_pnl:>+14,.2f}")

print(f"\n  MATCH ANALYSIS")
print(f"  {'Metric':<50} {'Value':>12}")
print(f"  {'-'*50} {'-'*12}")
print(f"  {'Matched (entry time ±5s + price ±0.5 + direction)':<50} {len(matched):>12,}  ({match_pct:.1f}%)")
print(f"  {'Exactly matched (all fields identical)':<50} {sum(1 for _,_,d in matched if not d):>12,}  ({exact_pct:.1f}%)")
print(f"  {'Only in parser output (not in DB)':<50} {len(only_parser):>12,}")
print(f"  {'Only in DB (not regenerated by parser)':<50} {len(only_db):>12,}")

# Field-by-field accuracy
if matched:
    print(f"\n  FIELD ACCURACY (on {len(matched):,} matched trades)")
    print(f"  {'Field':<25} {'Exact%':>9} {'Avg Error':>12} {'Max Error':>12} {'Mismatch #':>12}")
    print(f"  {'-'*25} {'-'*9} {'-'*12} {'-'*12} {'-'*12}")

    for field in ["profit_loss", "entry_price", "exit_price", "quantity",
                  "commission", "duration_minutes", "hour_of_day", "day_of_week", "side"]:
        mismatches = [(pt, db_t, diffs) for pt, db_t, diffs in matched if field in diffs]
        exact = len(matched) - len(mismatches)
        epct  = exact / len(matched) * 100
        if mismatches:
            errs = []
            for pt, db_t, diffs in mismatches:
                d = diffs[field]
                if d[2] is not None:
                    errs.append(float(d[2]))
            avg_err = sum(errs) / len(errs) if errs else 0
            max_err = max(errs) if errs else 0
            print(f"  {field:<25} {epct:>8.1f}% {avg_err:>12.4f} {max_err:>12.4f} {len(mismatches):>12,}")
        else:
            print(f"  {field:<25} {100.0:>8.1f}% {'0':>12} {'0':>12} {'0':>12}")

    # Sample of mismatched trades
    pnl_mismatches = [(pt, db_t, diffs) for pt, db_t, diffs in matched if "profit_loss" in diffs]
    if pnl_mismatches:
        print(f"\n  PROFIT_LOSS MISMATCHES (first 20 of {len(pnl_mismatches):,})")
        print(f"  {'Entry Time':<20} {'Dir':<6} {'Qty':<4} "
              f"{'Parser PnL':>12} {'DB PnL':>12} {'Diff':>10}")
        print(f"  {'-'*20} {'-'*6} {'-'*4} {'-'*12} {'-'*12} {'-'*10}")
        for pt, db_t, diffs in pnl_mismatches[:20]:
            p_pnl = float(pt.get("profit_loss") or 0)
            d_pnl = float(db_t.get("profit_loss") or 0)
            diff  = round(p_pnl - d_pnl, 2)
            print(f"  {(pt['entry_time'] or '')[:19]:<20} "
                  f"{(pt.get('side') or '')[:6]:<6} {int(pt.get('quantity') or 0):<4} "
                  f"{p_pnl:>12,.2f} {d_pnl:>12,.2f} {diff:>+10,.2f}")

# Trades only in parser (new, never imported)
if only_parser:
    print(f"\n  PARSER-ONLY TRADES (first 15 of {len(only_parser):,} — in .data files but NOT in DB)")
    print(f"  {'Entry Time':<20} {'Dir':<6} {'Qty':<4} {'Entry':>9} {'Exit':>9} {'PnL':>10}")
    print(f"  {'-'*20} {'-'*6} {'-'*4} {'-'*9} {'-'*9} {'-'*10}")
    for t in only_parser[:15]:
        print(f"  {(t['entry_time'] or '')[:19]:<20} {(t.get('side') or '')[:6]:<6} "
              f"{int(t.get('quantity') or 0):<4} {float(t.get('entry_price') or 0):>9.2f} "
              f"{float(t.get('exit_price') or 0):>9.2f} {float(t.get('profit_loss') or 0):>10.2f}")

# Trades only in DB (in DB but not re-generated by parser)
if only_db:
    print(f"\n  DB-ONLY TRADES (first 15 of {len(only_db):,} — in DB but parser did NOT regenerate them)")
    print(f"  {'Entry Time':<20} {'Dir':<6} {'Qty':<4} {'Entry':>9} {'Exit':>9} {'PnL':>10}")
    print(f"  {'-'*20} {'-'*6} {'-'*4} {'-'*9} {'-'*9} {'-'*10}")
    for t in only_db[:15]:
        print(f"  {(t['entry_time'] or '')[:19]:<20} {(t.get('side') or '')[:6]:<6} "
              f"{int(t.get('quantity') or 0):<4} {float(t.get('entry_price') or 0):>9.2f} "
              f"{float(t.get('exit_price') or 0):>9.2f} {float(t.get('profit_loss') or 0):>10.2f}")

# ── Final Verdict ──────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  FINAL VERDICT")
print(SEP)

if match_pct >= 99 and exact_pct >= 98:
    print(f"  ✅ VERIFIED: The database is CONSISTENT with the binary .data files.")
    print(f"  {match_pct:.1f}% of trades matched, {exact_pct:.1f}% were field-for-field identical.")
elif match_pct >= 90:
    print(f"  ⚠️  MOSTLY CONSISTENT: {match_pct:.1f}% match rate, {exact_pct:.1f}% exact.")
    print(f"  Some discrepancies found — investigate the mismatched fields above.")
else:
    print(f"  ❌ SIGNIFICANT DISCREPANCY: Only {match_pct:.1f}% of trades matched.")
    print(f"  The DB may not reflect the current state of the .data files.")

print()
print(f"  Parser trades: {ps.get('n',0):,}  |  DB trades: {ds.get('n',0):,}  |  Diff: {diff_n:+,}")
print(f"  Parser PnL: ${ps.get('total',0):,.2f}  |  DB PnL: ${ds.get('total',0):,.2f}  |  Diff: ${diff_pnl:+,.2f}")

if only_parser:
    print(f"\n  NOTE: {len(only_parser):,} trades exist in .data files but are NOT in the DB.")
    print(f"  These were either filtered as ghosts or never imported. Re-run import to add them.")

if only_db:
    print(f"\n  NOTE: {len(only_db):,} trades are in the DB but were NOT regenerated by the parser.")
    print(f"  Possible reasons: .data files deleted/changed, or ghost-filter settings changed.")

print(SEP)
print(f"\nScratch DB left at: {SCRATCH_DB}")
print("(Delete manually if not needed)")
