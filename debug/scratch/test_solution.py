import sys, os, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_platform.services.binary_log_parser import _parse_file_nitro
import trading_platform.services.binary_log_parser as blp

NY_TZ = ZoneInfo("America/New_York")
TARGET = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

# Test 1: Baseline (current rule)
fills_current, _ = _parse_file_nitro(TARGET, target_sym="NQ")

# Test 2: Keep everything
orig = blp._is_ghost_fill
blp._is_ghost_fill = lambda a, n, t: False
fills_all, _ = _parse_file_nitro(TARGET, target_sym="NQ")
blp._is_ghost_fill = orig

# Test 3: Proposed new rule
def _is_ghost_fill_proposed(acc, note, ts_str, pf):
    import re
    note_u = note.strip()
    if re.search(r'[A-Za-z0-9]', note_u): return False
    
    # EOD
    try:
        dt = datetime.datetime.fromisoformat(ts_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        ny = dt.astimezone(NY_TZ)
        if (ny.hour == 16 and ny.minute >= 55) or (ny.hour == 17 and ny.minute <= 5):
            return False
    except: pass
    
    # New Evaluator rule
    msg = pf.get('msgtxt', '').lower()
    if 'trading evaluator' in msg or 'trade simulation' in msg:
        return False
        
    return True

# Monkey patch parser to pass 'pf' to our custom ghost rule
import trading_platform.services.binary_log_parser
old_parse = trading_platform.services.binary_log_parser._is_ghost_fill

def hook_is_ghost(acc, note, ts_str):
    # This is tricky because parser doesn't pass 'pf' natively to __is_ghost_fill
    return True # We will do it post-parse manually instead

trading_platform.services.binary_log_parser._is_ghost_fill = hook_is_ghost

def check_balance(fills, label):
    # Calculate balance exactly from 2025-12-17 18:00 to 2025-12-18 17:00
    session_start = datetime.datetime(2025, 12, 17, 18, 0, 0, tzinfo=NY_TZ)
    session_end = datetime.datetime(2025, 12, 18, 17, 0, 0, tzinfo=NY_TZ)
    
    b, s = 0, 0
    for f in fills:
        try:
            dt = datetime.datetime.fromisoformat(f['timestamp'])
            if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
            ny = dt.astimezone(NY_TZ)
            if session_start <= ny < session_end:
                if f['side'] in ('BUY', 'LONG'): b += f['quantity']
                elif f['side'] in ('SELL', 'SHORT'): s += f['quantity']
        except: pass
    
    print(f"{label:30} -> Buys: {b:4.0f}, Sells: {s:4.0f} | Net: {b-s:+4.0f}")

print("=== V_SIM16 2025-12-18 Session Balance Test ===")
print("Reporting fills matched manually within 18:00 to 17:00 NY time.")

check_balance(fills_current, "Baseline (Current Rule)")
check_balance(fills_all, "All Fills (No Ghost Filter)")

# Manually apply new rule to ALL fills
fills_proposed = []
import re
for f in fills_all:
    note = f.get('note', '')
    is_ghost = True
    if re.search(r'[A-Za-z0-9]', note): is_ghost = False
    else:
        # Check EOD
        try:
            dt = datetime.datetime.fromisoformat(f['timestamp'])
            if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
            ny = dt.astimezone(NY_TZ)
            if (ny.hour == 16 and ny.minute >= 55) or (ny.hour == 17 and ny.minute <= 5):
                is_ghost = False
        except: pass
        
        # Check msg
        msg = f.get('msgtxt', '').lower()
        if 'trading evaluator' in msg or 'trade simulation' in msg:
            is_ghost = False
            
    if not is_ghost:
        fills_proposed.append(f)

check_balance(fills_proposed, "Proposed Rule (Evaluator Msg)")
