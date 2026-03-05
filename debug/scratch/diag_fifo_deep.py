"""
Deep diagnostic: 
1. Check if trailing stops consistently lack notes (across multiple days)
2. Correct ghost count (fills vs contracts)
3. Show context around each ghost fill
4. Session-by-session (18:00-17:00 NY) verification
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone, SYMBOL_METADATA
import trading_platform.services.binary_log_parser as blp
import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

NY_TZ = ZoneInfo("America/New_York")
LOG_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"

out = []
def p(s=""): out.append(str(s))

def fmt_ny(ts):
    try:
        dt = datetime.datetime.fromisoformat(ts)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(NY_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except: return ts[:19]

# ====================================================================
# Q1: Are trailing stop fills consistently without notes?
# Parse multiple days and check if ghost fills correlate with order type
# ====================================================================
p("=" * 100)
p("Q1: DO TRAILING STOP FILLS CONSISTENTLY LACK TAG 0x82 NOTES?")
p("=" * 100)

# Get all V_sim16 files
v16_files = sorted(glob.glob(os.path.join(LOG_DIR, "TradeActivityLog_*V_sim16*")))
p(f"Total V_SIM16 log files: {len(v16_files)}")

# Parse a sample of recent files (last 20) with and without ghost filter
sample_files = v16_files[-20:]  # Last 20 files
total_ghosts_across_days = 0
ghost_order_types = defaultdict(int)
ghost_details_all = []

for fp in sample_files:
    # Parse with ghost filter
    fills_ok, gc = _parse_file_nitro(fp, target_sym="NQ")
    
    # Parse without ghost filter
    orig = blp._is_ghost_fill
    blp._is_ghost_fill = lambda a,n,t: False
    fills_all, _ = _parse_file_nitro(fp, target_sym="NQ")
    blp._is_ghost_fill = orig
    
    # Find ghost fills by comparing
    ok_sigs = set()
    for f in fills_ok:
        sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
        ok_sigs.add(sig)
    
    day_ghosts = []
    for f in fills_all:
        sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
        if sig not in ok_sigs:
            day_ghosts.append(f)
            # Try to infer order type from msgtxt
            msg = f.get('msgtxt', '').lower()
            if 'trailing' in msg:
                ghost_order_types['Trailing Stop'] += 1
            elif 'market' in msg:
                ghost_order_types['Market'] += 1
            elif 'limit' in msg:
                ghost_order_types['Limit'] += 1
            elif 'stop' in msg:
                ghost_order_types['Stop'] += 1
            else:
                ghost_order_types['Unknown'] += 1
            ghost_details_all.append({
                'file': os.path.basename(fp),
                'time': f['timestamp'],
                'side': f['side'],
                'qty': f['quantity'],
                'price': f['price'],
                'note': f.get('note', ''),
                'msgtxt': f.get('msgtxt', '')[:80],
                'tags': f.get('tags_trace', [])
            })
    
    total_ghosts_across_days += len(day_ghosts)

p(f"\nGhost fills across {len(sample_files)} files: {total_ghosts_across_days}")
p(f"\nGhost fill order type breakdown:")
for otype, cnt in sorted(ghost_order_types.items(), key=lambda x: -x[1]):
    p(f"  {otype}: {cnt}")

p(f"\nAll ghost fill details ({len(ghost_details_all)} total):")
for i, g in enumerate(ghost_details_all):
    p(f"  [{i:>2}] {g['file'][:30]}  NY={fmt_ny(g['time'])}  {g['side']:4s}  qty={g['qty']}  px={g['price']:.2f}")
    p(f"       note='{g['note'][:50]}'")
    p(f"       msg='{g['msgtxt'][:70]}'")
    p(f"       tags={g['tags']}")

# ====================================================================
# Q2: Correct count — fills vs contracts
# ====================================================================
p()
p("=" * 100)
p("Q2: CORRECT GHOST COUNT FOR 2025-12-18")
p("=" * 100)

fp_dec18 = os.path.join(LOG_DIR, "TradeActivityLog_2025-12-18_UTC.V_sim16.data")
fills_ok18, gc18 = _parse_file_nitro(fp_dec18, target_sym="NQ")
orig = blp._is_ghost_fill
blp._is_ghost_fill = lambda a,n,t: False
fills_all18, _ = _parse_file_nitro(fp_dec18, target_sym="NQ")
blp._is_ghost_fill = orig

ok_sigs18 = set()
for f in fills_ok18:
    sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
    ok_sigs18.add(sig)

ghosts18 = []
for f in fills_all18:
    sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
    if sig not in ok_sigs18:
        ghosts18.append(f)

ghosts18.sort(key=lambda x: x.get('ts_val', 0))
total_ghost_contracts = sum(g['quantity'] for g in ghosts18)
p(f"Ghost fill RECORDS: {len(ghosts18)}")
p(f"Ghost fill CONTRACTS: {total_ghost_contracts}")
p(f"Parser reported ghosts removed: {sum(gc18.values())}")
for i, g in enumerate(ghosts18):
    p(f"  [{i}] NY={fmt_ny(g['timestamp'])}  {g['side']:4s}  qty={g['quantity']}  px={g['price']:.2f}  note='{g.get('note','')[:40]}'  msg='{g.get('msgtxt','')[:60]}'")

# ====================================================================
# Q3: Context around each ghost fill (5 fills before and after)
# ====================================================================
p()
p("=" * 100)
p("Q3: CONTEXT AROUND EACH GHOST FILL (5 before, 5 after)")
p("=" * 100)

fills_all18.sort(key=lambda x: x.get('ts_val', 0))
for gi, ghost in enumerate(ghosts18):
    ghost_ts = ghost.get('ts_val', 0)
    ghost_sig = (round(ghost_ts*2)/2.0, ghost['price'], ghost['side'], ghost['quantity'])
    
    # Find index in fills_all18
    ghost_idx = None
    for idx, f in enumerate(fills_all18):
        fsig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
        if fsig == ghost_sig:
            ghost_idx = idx
            break
    
    if ghost_idx is None:
        p(f"\nGhost #{gi}: Could not find in fill list")
        continue
    
    p(f"\n--- Ghost #{gi} at index {ghost_idx} ---")
    start = max(0, ghost_idx - 5)
    end = min(len(fills_all18), ghost_idx + 6)
    for j in range(start, end):
        f = fills_all18[j]
        marker = " <<< GHOST" if j == ghost_idx else ""
        is_ghost = "GHOST" if (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity']) not in ok_sigs18 else "  ok "
        p(f"  [{j:>3}] {is_ghost} NY={fmt_ny(f['timestamp'])}  {f['side']:4s}  qty={f['quantity']}  px={f['price']:.2f}  note='{f.get('note','')[:30]}'  msg='{f.get('msgtxt','')[:50]}'{marker}")

# ====================================================================
# Q4: Session-by-session verification (18:00 to 17:00 NY)
# ====================================================================
p()
p("=" * 100)
p("Q4: SESSION-BY-SESSION FIFO (ALL V_SIM16 FILES)")
p("=" * 100)

# Parse ALL files without ghost filter to get complete fill stream
all_fills_complete = []
for fp in v16_files:
    orig = blp._is_ghost_fill
    blp._is_ghost_fill = lambda a,n,t: False
    fills, _ = _parse_file_nitro(fp, target_sym="NQ")
    blp._is_ghost_fill = orig
    all_fills_complete.extend(fills)

all_fills_complete.sort(key=lambda x: x.get('ts_val', 0))
p(f"Total fills across ALL files (no ghost filter): {len(all_fills_complete)}")

# Bucket fills into sessions (17:00 NY to 17:00 NY)
sessions = defaultdict(list)
for f in all_fills_complete:
    try:
        dt = datetime.datetime.fromisoformat(f['timestamp'])
        if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        ny = dt.astimezone(NY_TZ)
        # Session date: if hour >= 17, belongs to NEXT day
        sd = (ny + datetime.timedelta(days=1)).date() if ny.hour >= 17 else ny.date()
        sessions[sd].append(f)
    except:
        pass

p(f"Total sessions found: {len(sessions)}")
p(f"\nSession summary (showing sessions with fills):")
p(f"{'Session Date':>12} | {'Fills':>5} | {'Buys':>4} | {'Sells':>4} | {'Net':>4}")
p("-" * 50)

session_issues = []
for sd in sorted(sessions.keys()):
    fills = sessions[sd]
    buys = sum(f['quantity'] for f in fills if f['side'] in ('BUY','LONG'))
    sells = sum(f['quantity'] for f in fills if f['side'] in ('SELL','SHORT'))
    net = buys - sells
    flag = " *** IMBALANCED" if net != 0 else ""
    p(f"{sd.isoformat():>12} | {len(fills):>5} | {buys:>4} | {sells:>4} | {net:>+4}{flag}")
    if net != 0:
        session_issues.append((sd, net, len(fills)))

p(f"\nSessions with non-zero net position: {len(session_issues)}")
for sd, net, fc in session_issues:
    p(f"  {sd}: net={net:+d} ({fc} fills)")

# Write output
with open("diag_deep_result.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
print(f"Done. {len(out)} lines written to diag_deep_result.txt")
