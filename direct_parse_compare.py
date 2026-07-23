"""
direct_parse_compare.py
========================
Directly calls _parse_file_nitro + _pairs_to_trades on a small sample
of TM_7 .data files and compares the output trade-by-trade against
what's stored in processed_trades for the same dates.

This bypasses run_import() parallelism issues and lets us verify the 
parser output matches the DB with full field-level detail.
"""

import sys, io, sqlite3
sys.path.insert(0, r"c:\SC_results_WF")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import re, glob

# ── Config ─────────────────────────────────────────────────────────────────────
DATASET_DIR = r"c:\SC_results_WF\dataset"
ORIG_DB     = r"c:\SC_results_WF\trading_platform.db"
ACCOUNT     = "TM_7"
# Test on a specific 2-week window where we know DB has data
TEST_FROM   = "2024-03-13"
TEST_TO     = "2024-03-29"

SEP  = "="*88

# ── Import project internals ────────────────────────────────────────────────────
from trading_platform.services import binary_log_parser as blp
# Access private functions directly
_parse_file_nitro = blp._parse_file_nitro
_to_ny            = blp._to_ny

# Also get _pairs_to_trades and _aggregate_trades from BinaryLogParser class
from trading_platform.services.binary_log_parser import BinaryLogParser
parser_inst = BinaryLogParser(db_path=ORIG_DB)
_pairs_to_trades  = parser_inst._pairs_to_trades
_aggregate_trades = parser_inst._aggregate_trades

print(f"\n{SEP}")
print(f"  DIRECT PARSE COMPARE  |  TM_7 / NQ  |  {TEST_FROM} → {TEST_TO}")
print(f"  Method: _parse_file_nitro + _pairs_to_trades (no parallel, no DB write)")
print(SEP)

# ── STEP 1: Collect TM_7 files in test window ──────────────────────────────────
print(f"\n[1/4] Collecting TM_7 .data files...")
from_dt = datetime.strptime(TEST_FROM, "%Y-%m-%d")
to_dt   = datetime.strptime(TEST_TO,   "%Y-%m-%d")

tm7_files = []
for f in sorted(Path(DATASET_DIR).glob("*.TM_7.data")):
    m = re.search(r'(\d{4}-\d{2}-\d{2})', f.name)
    if not m:
        continue
    try:
        fdate = datetime.strptime(m.group(1), "%Y-%m-%d")
    except:
        continue
    if from_dt <= fdate <= to_dt:
        tm7_files.append(str(f))

print(f"      Files (exact .TM_7.data only): {len(tm7_files)}")
for f in tm7_files[:5]:
    print(f"      {Path(f).name}  ({Path(f).stat().st_size:,} bytes)")
if len(tm7_files) > 5:
    print(f"      ... and {len(tm7_files)-5} more")

# ── STEP 2: Parse each file using the project's exact pipeline ─────────────────
print(f"\n[2/4] Running _parse_file_nitro on each file...")
all_fills  = []
all_ghosts = []
file_stats = {}

for fpath in tm7_files:
    fname = Path(fpath).name
    try:
        fills, ghosts = _parse_file_nitro(fpath)
        file_stats[fname] = {"fills": len(fills), "ghosts": len(ghosts)}
        all_fills.extend(fills)
        all_ghosts.extend(ghosts)
    except Exception as e:
        file_stats[fname] = {"fills": 0, "ghosts": 0, "error": str(e)}
        print(f"      ERROR {fname}: {e}")

total_fills  = sum(s["fills"]  for s in file_stats.values())
total_ghosts = sum(s["ghosts"] for s in file_stats.values())
print(f"      Total fills extracted: {total_fills:,}")
print(f"      Total ghosts dropped:  {total_ghosts:,}")

if not all_fills:
    print(f"\n  WARNING: 0 fills extracted! Trying without account filter...")
    # Try IPS_TM_7 files as well to see if anything parses
    for f in sorted(Path(DATASET_DIR).glob("*IPS_TM_7*.data")):
        m = re.search(r'(\d{4}-\d{2}-\d{2})', f.name)
        if not m: continue
        try:
            fdate = datetime.strptime(m.group(1), "%Y-%m-%d")
        except: continue
        if from_dt <= fdate <= to_dt:
            try:
                fills, ghosts = _parse_file_nitro(str(f))
                print(f"      IPS_TM_7 {f.name}: {len(fills)} fills, {len(ghosts)} ghosts")
                all_fills.extend(fills)
                all_ghosts.extend(ghosts)
            except Exception as e:
                print(f"      IPS_TM_7 ERROR {f.name}: {e}")

# ── STEP 3: Pair fills into round-trip trades ──────────────────────────────────
print(f"\n[3/4] Pairing fills into trades via _pairs_to_trades...")
if all_fills:
    try:
        parsed_trades = _pairs_to_trades(all_fills)
        print(f"      Paired trades: {len(parsed_trades):,}")
    except Exception as e:
        print(f"      ERROR in _pairs_to_trades: {e}")
        parsed_trades = []
    
    if not parsed_trades:
        # Try _aggregate_trades
        try:
            parsed_trades = _aggregate_trades(all_fills)
            print(f"      _aggregate_trades: {len(parsed_trades):,}")
        except Exception as e2:
            print(f"      ERROR in _aggregate_trades: {e2}")
            parsed_trades = []
else:
    parsed_trades = []
    print(f"      No fills to pair.")

# ── STEP 4: Load DB trades for same date window ────────────────────────────────
print(f"\n[4/4] Loading DB trades for {TEST_FROM} → {TEST_TO}...")
conn = sqlite3.connect(ORIG_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
    SELECT account_name, symbol, side, entry_time, exit_time,
           entry_price, exit_price, quantity, profit_loss, commission,
           duration_minutes, hour_of_day, day_of_week
    FROM processed_trades
    WHERE account_name = 'TM_7' AND symbol = 'NQ'
      AND entry_time >= ? AND entry_time < ?
    ORDER BY entry_time
""", (TEST_FROM, TEST_TO + "T23:59:59"))
db_trades = [dict(r) for r in cur.fetchall()]
conn.close()
print(f"      DB trades (TM_7/NQ): {len(db_trades):,}")

# ── Inspect fill sample ─────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  FILL-LEVEL INSPECTION")
print(SEP)

if all_fills:
    print(f"\n  First 15 fills from parser:")
    print(f"  {'Timestamp':<22} {'Side':<5} {'Price':>9} {'Qty':<4} {'OpenClose':<10} {'Note'}")
    print(f"  {'-'*22} {'-'*5} {'-'*9} {'-'*4} {'-'*10} {'-'*20}")
    for f in all_fills[:15]:
        ts  = str(f.get("timestamp") or f.get("ts") or "?")[:19]
        sid = f.get("side", "?")
        pr  = f.get("price", 0)
        qty = f.get("quantity", 0)
        oc  = f.get("open_close", "?")
        nt  = str(f.get("note", ""))[:25]
        print(f"  {ts:<22} {str(sid):<5} {float(pr):>9.2f} {int(qty):<4} {str(oc):<10} {nt}")

    # Symbol distribution
    syms = defaultdict(int)
    for f in all_fills:
        syms[f.get("symbol", "?")] += 1
    print(f"\n  Symbol distribution in fills:")
    for s, c in sorted(syms.items(), key=lambda x: -x[1])[:10]:
        print(f"    {s}: {c:,}")
else:
    print(f"\n  ⚠️  No fills were extracted from TM_7 .data files in this date range.")
    print(f"  This means either:")
    print(f"    1. The binary .data files have 0 valid fills (all were ghosts)")
    print(f"    2. The file format uses a different binary structure")
    print(f"    3. The TM_7 NQ trades in the DB came from a different source")

# ── Compare to DB ───────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  COMPARISON SUMMARY")
print(SEP)
print(f"  Parser extracted fills:   {len(all_fills):,}")
print(f"  Parser-paired trades:     {len(parsed_trades):,}")
print(f"  DB trades (same window):  {len(db_trades):,}")

print(f"\n  DB sample (first 15):")
print(f"  {'Entry Time':<20} {'Dir':<6} {'Qty':<4} {'Entry':>9} {'Exit':>9} {'PnL':>10}")
print(f"  {'-'*20} {'-'*6} {'-'*4} {'-'*9} {'-'*9} {'-'*10}")
for t in db_trades[:15]:
    print(f"  {(t['entry_time'] or '')[:19]:<20} {(t['side'] or '')[:6]:<6} "
          f"{int(t.get('quantity') or 0):<4} {float(t.get('entry_price') or 0):>9.2f} "
          f"{float(t.get('exit_price') or 0):>9.2f} {float(t.get('profit_loss') or 0):>10.2f}")

if parsed_trades:
    print(f"\n  Parser-generated sample (first 15):")
    print(f"  {'Entry Time':<20} {'Dir':<6} {'Qty':<4} {'Entry':>9} {'Exit':>9} {'PnL':>10}")
    print(f"  {'-'*20} {'-'*6} {'-'*4} {'-'*9} {'-'*9} {'-'*10}")
    for t in parsed_trades[:15]:
        et = str(t.get("entry_time") or t.get("entry_datetime") or "?")[:19]
        xt = str(t.get("exit_time") or t.get("exit_datetime") or "?")[:19]
        sd = t.get("side", t.get("trade_type", "?"))
        ep = float(t.get("entry_price", 0))
        xp = float(t.get("exit_price", 0))
        pl = float(t.get("profit_loss", t.get("pnl", 0)))
        qty = int(t.get("quantity", 0))
        print(f"  {et:<20} {str(sd)[:6]:<6} {qty:<4} {ep:>9.2f} {xp:>9.2f} {pl:>10.2f}")

# ── Root cause analysis ─────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  ROOT CAUSE ANALYSIS")
print(SEP)
print(f"  File count in test window: {len(tm7_files)}")
print(f"  Fills from parser:         {total_fills}")
print(f"  Ghosts dropped:            {total_ghosts}")
if tm7_files and total_fills == 0:
    print()
    print("  DIAGNOSIS: The parser read the TM_7 .data files but extracted 0 fills.")
    print("  This means either:")
    print("  A) The binary .data files contain activity with no FILLED status records")
    print("     (e.g., all positions are managed by Sierra Chart and stored differently)")
    print("  B) The ghost filter is dropping all fills (strict 'Trading Evaluator' rule)")
    print("  C) The account_filter only matches files named *.TM_7.data (not IPS_TM_7)")
    print()
    print("  The trades in the DB likely came from IPS_TM_7 files (which pass all NQ fills")
    print("  to TM_7's account) rather than the plain TM_7 .data files.")
    print()
    print("  NEXT STEP: Run the same parse on IPS_TM_7 files and check if those fills")
    print("  match the TM_7 NQ trades in the DB.")
print(SEP)
