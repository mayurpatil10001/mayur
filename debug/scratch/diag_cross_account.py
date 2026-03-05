"""
Cross-account ghost fill research.
Samples 8 diverse accounts, parses 5 recent files each,
compares session balance WITH and WITHOUT ghost filter.
Also checks if trailing stop fills are consistently tag-0x82-free.
"""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_platform.services.binary_log_parser import _parse_file_nitro
import trading_platform.services.binary_log_parser as blp
import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

NY_TZ = ZoneInfo("America/New_York")
LOG_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"

out = []
def p(s=""): out.append(str(s))

# Representative accounts from different types
SAMPLE_ACCOUNTS = [
    "V_SIM16",      # V_ type (original issue)
    "TM_10",        # TM type (high file count)
    "3Q_SIM14",     # 3Q type
    "3Q_SIM15",     # 3Q type (previously verified)
    "IPS_TM_10",    # IPS type
    "TS_4",         # TS type
    "PB_1",         # PB type
    "TM_2",         # Another TM
]

FILES_PER_ACCOUNT = 5  # Last 5 files per account

def get_session_date(ts_str):
    try:
        dt = datetime.datetime.fromisoformat(ts_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        ny = dt.astimezone(NY_TZ)
        return (ny + datetime.timedelta(days=1)).date() if ny.hour >= 17 else ny.date()
    except: return None

def analyze_account(acc_name):
    """Analyze ghost impact for one account."""
    # Find files
    pattern = os.path.join(LOG_DIR, f"TradeActivityLog_*.{acc_name}.data")
    files = sorted(glob.glob(pattern))
    if not files:
        # Try case-insensitive
        all_files = glob.glob(os.path.join(LOG_DIR, "TradeActivityLog_*.data"))
        files = sorted([f for f in all_files if acc_name.lower() in os.path.basename(f).lower()])
    
    if not files:
        return {"account": acc_name, "error": "No files found"}
    
    sample = files[-FILES_PER_ACCOUNT:]  # Last N files
    
    # Detect symbol from filename
    sym = "NQ"  # default
    bn = os.path.basename(sample[0]).upper()
    if "ES-" in acc_name.upper() or "ES_" in acc_name.upper():
        sym = "ES"
    elif "CL-" in acc_name.upper():
        sym = "CL"
    
    total_fills_with_ghost = 0
    total_fills_no_ghost = 0
    ghost_fills = []
    session_balance_with = defaultdict(lambda: {"buys": 0, "sells": 0})
    session_balance_no = defaultdict(lambda: {"buys": 0, "sells": 0})
    
    for fp in sample:
        # WITH ghost filter
        fills_ok, gc = _parse_file_nitro(fp, target_sym=sym)
        total_fills_no_ghost += len(fills_ok)
        
        # WITHOUT ghost filter
        orig = blp._is_ghost_fill
        blp._is_ghost_fill = lambda a, n, t: False
        fills_all, _ = _parse_file_nitro(fp, target_sym=sym)
        blp._is_ghost_fill = orig
        total_fills_with_ghost += len(fills_all)
        
        # Session balance for both
        for f in fills_ok:
            sd = get_session_date(f['timestamp'])
            if sd:
                if f['side'] in ('BUY', 'LONG'):
                    session_balance_no[sd]["buys"] += f['quantity']
                else:
                    session_balance_no[sd]["sells"] += f['quantity']
        
        for f in fills_all:
            sd = get_session_date(f['timestamp'])
            if sd:
                if f['side'] in ('BUY', 'LONG'):
                    session_balance_with[sd]["buys"] += f['quantity']
                else:
                    session_balance_with[sd]["sells"] += f['quantity']
        
        # Identify ghost fills
        ok_sigs = set()
        for f in fills_ok:
            sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
            ok_sigs.add(sig)
        for f in fills_all:
            sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
            if sig not in ok_sigs:
                ghost_fills.append(f)
    
    # Count imbalanced sessions
    imbalanced_with = 0
    imbalanced_no = 0
    for sd in session_balance_with:
        b = session_balance_with[sd]
        if b["buys"] != b["sells"]: imbalanced_with += 1
    for sd in session_balance_no:
        b = session_balance_no[sd]
        if b["buys"] != b["sells"]: imbalanced_no += 1
    
    return {
        "account": acc_name,
        "files_sampled": len(sample),
        "fills_with_ghost_filter": total_fills_no_ghost,
        "fills_no_ghost_filter": total_fills_with_ghost,
        "ghost_fills_removed": total_fills_with_ghost - total_fills_no_ghost,
        "ghost_details": ghost_fills,
        "sessions_total_no_ghost": len(session_balance_no),
        "sessions_imbalanced_no_ghost": imbalanced_no,
        "sessions_total_with_ghost": len(session_balance_with),
        "sessions_imbalanced_with_ghost": imbalanced_with,
    }

# === RUN ANALYSIS ===
p("=" * 110)
p("CROSS-ACCOUNT GHOST FILL RESEARCH")
p(f"Sampling {FILES_PER_ACCOUNT} recent files per account, {len(SAMPLE_ACCOUNTS)} accounts")
p("=" * 110)

results = []
for acc in SAMPLE_ACCOUNTS:
    p(f"\nAnalyzing {acc}...")
    r = analyze_account(acc)
    results.append(r)
    if "error" in r:
        p(f"  ERROR: {r['error']}")
        continue
    p(f"  Files: {r['files_sampled']}")
    p(f"  Fills (with ghost filter): {r['fills_with_ghost_filter']}")
    p(f"  Fills (no ghost filter):   {r['fills_no_ghost_filter']}")
    p(f"  Ghost fills removed:       {r['ghost_fills_removed']}")
    p(f"  Sessions (no ghost): {r['sessions_total_no_ghost']} total, {r['sessions_imbalanced_no_ghost']} imbalanced")
    p(f"  Sessions (w/ ghost): {r['sessions_total_with_ghost']} total, {r['sessions_imbalanced_with_ghost']} imbalanced")

# === SUMMARY TABLE ===
p()
p("=" * 110)
p("SUMMARY TABLE")
p("=" * 110)
p(f"{'Account':>16} | {'Files':>5} | {'Fills(filt)':>11} | {'Fills(all)':>10} | {'Ghosts':>6} | {'Sess(filt)':>10} | {'Imbal(filt)':>11} | {'Sess(all)':>9} | {'Imbal(all)':>10}")
p("-" * 110)
for r in results:
    if "error" in r:
        p(f"{r['account']:>16} | ERROR: {r['error']}")
        continue
    p(f"{r['account']:>16} | {r['files_sampled']:>5} | {r['fills_with_ghost_filter']:>11} | {r['fills_no_ghost_filter']:>10} | {r['ghost_fills_removed']:>6} | {r['sessions_total_no_ghost']:>10} | {r['sessions_imbalanced_no_ghost']:>11} | {r['sessions_total_with_ghost']:>9} | {r['sessions_imbalanced_with_ghost']:>10}")

# === GHOST FILL DETAILS (message analysis) ===
p()
p("=" * 110)
p("GHOST FILL MESSAGE ANALYSIS (all accounts combined)")
p("=" * 110)

all_ghost_msgs = defaultdict(int)
all_ghost_sides = defaultdict(int)
ghost_with_evaluator = 0
ghost_without_evaluator = 0

for r in results:
    if "error" in r: continue
    for g in r.get("ghost_details", []):
        msg = g.get('msgtxt', '')
        if 'Trading Evaluator' in msg or 'Trade simulation' in msg:
            ghost_with_evaluator += 1
        else:
            ghost_without_evaluator += 1
        all_ghost_sides[g['side']] += g['quantity']
        # Categorize by message pattern
        if 'trailing' in msg.lower():
            all_ghost_msgs['Has "trailing" in msg'] += 1
        elif 'Trading Evaluator' in msg:
            all_ghost_msgs['Has "Trading Evaluator" in msg'] += 1
        elif 'Trade simulation' in msg:
            all_ghost_msgs['Has "Trade simulation" in msg'] += 1
        elif msg.strip():
            all_ghost_msgs[f'Other msg: {msg[:40]}'] += 1
        else:
            all_ghost_msgs['Empty message'] += 1

p(f"Ghost fills with 'Trading Evaluator/Trade simulation' msg: {ghost_with_evaluator}")
p(f"Ghost fills WITHOUT evaluator msg: {ghost_without_evaluator}")
p(f"\nGhost fill side breakdown (by contracts):")
for side, qty in all_ghost_sides.items():
    p(f"  {side}: {qty} contracts")
p(f"\nGhost fill message patterns:")
for pat, cnt in sorted(all_ghost_msgs.items(), key=lambda x: -x[1]):
    p(f"  {cnt:>4}x  {pat}")

# === KEY QUESTION: Does removing ghost filter fix balance? ===
p()
p("=" * 110)
p("KEY QUESTION: Does removing ghost filter fix session balance?")
p("=" * 110)
for r in results:
    if "error" in r: continue
    acc = r['account']
    fix_pct = 0
    if r['sessions_imbalanced_no_ghost'] > 0:
        fix_pct = (1 - r['sessions_imbalanced_with_ghost'] / r['sessions_imbalanced_no_ghost']) * 100
    p(f"  {acc:>16}: Imbalanced sessions: {r['sessions_imbalanced_no_ghost']} (with filter) -> {r['sessions_imbalanced_with_ghost']} (without filter)  [{fix_pct:+.0f}% improvement]")

with open("cross_account_result.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
print(f"Done. {len(out)} lines written to cross_account_result.txt")
