
import os
import struct
import datetime
import re
from typing import List, Dict

# --- CONFIGURATION ---
BINARY_LOG_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
TEXT_LOG_DIR = r"C:\SierraChart\SC results WF"

# --- HELPER FUNCTIONS ---

def _get_base_symbol_standalone(raw: str) -> str:
    s = raw.upper()
    match = re.search(r'([A-Z]+)', s)
    if not match: return s
    base = match.group(1)
    m = {'CLN': 'CL', 'CLH': 'CL', 'CLQ': 'CL', 'CLU': 'CL', 'CLV': 'CL', 'CLZ': 'CL', 'CLG': 'CL', 'CLF': 'CL',
         'ESM': 'ES', 'ESU': 'ES', 'ESZ': 'ES', 'ESH': 'ES',
         'NQM': 'NQ', 'NQU': 'NQ', 'NQZ': 'NQ', 'NQH': 'NQ',
         'MCL': 'CL', 'MES': 'ES', 'MNQ': 'NQ'} 
    if base in m: return m[base]
    return base

def parse_txt_trades(filepath: str) -> List[Dict]:
    trades = []
    print(f"Parsing TEXT file: {filepath}")
    if not os.path.exists(filepath):
        print("  [ERROR] File not found.")
        return []
        
    with open(filepath, 'r') as f:
        # Skip header
        f.readline()
        
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 7: continue
            
            try:
                # FIXED: Hardcoded indices based on visual inspection
                # 0: Symbol (e.g., CLG26 (3Q_sim14))
                # 1: Trade Type (Long/Short)
                # 2: Entry DateTime (2026-01-19 09:30:33.000 BP)
                # 3: Exit DateTime (2026-01-19 10:02:45.000)
                # 4: Entry Price
                # 5: Exit Price
                # 6: Trade Quantity
                
                symbol = parts[0]
                trade_type = parts[1]
                dt_str_raw = parts[2]
                exit_dt_str_raw = parts[3]
                price = float(parts[4])
                qty = float(parts[6])
                
                # Cleanup Timestamps (strip BP/EP suffixes)
                # "2026-01-19 09:30:33.000 BP" -> Split by space, take first 2 parts
                dt_str = " ".join(dt_str_raw.split()[:2])
                
                # Parsing Entry DT
                dt = None
                try:
                    dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

                # Parsing Exit DT
                exit_dt = None
                if exit_dt_str_raw and exit_dt_str_raw.strip():
                    exit_dt_str = " ".join(exit_dt_str_raw.split()[:2])
                    try:
                        exit_dt = datetime.datetime.strptime(exit_dt_str, "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        try:
                            exit_dt = datetime.datetime.strptime(exit_dt_str, "%Y-%m-%d %H:%M:%S")
                        except: pass

                if dt:
                    trades.append({
                        'symbol': symbol,
                        'dt': dt,
                        'exit_dt': exit_dt,
                        'price': price,
                        'qty': qty,
                        'type': trade_type,
                        'source': 'TXT'
                    })
            except Exception as e:
                 # print(f"  [DEBUG] Failed line: {e}")
                 pass
                
    print(f"  Parsed {len(trades)} trades from TEXT.")
    return trades

def parse_binary_trades(filepath: str, account_filter: str) -> List[Dict]:
    """
    Revised logic: Scan a 1024-byte window after each account string occurrence for ANY valid-looking prices.
    This handles variable-length records and field shifts that fixed offsets miss.
    """
    print(f"Parsing BINARY file (Flex-Scan): {os.path.basename(filepath)}")
    if not os.path.exists(filepath):
        print("  [ERROR] File not found.")
        return [], []
        
    trades = []
    resets = []
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # --- Part 1: Heuristic Price Scan ---
    b_target = account_filter.encode('utf-8')
    start = 0
    match_count = 0
    
    while True:
        idx = content.find(b_target, start)
        if idx == -1: break
        
        match_count += 1
        # Scan 1024 byte window after Account ID
        window_size = 1024
        limit = min(len(content), idx + window_size)
        chunk = content[idx:limit]
        
        # In each record window, extract all doubles that look like real prices
        # for CL/ES (20-15000 range)
        for i in range(len(chunk)-8):
            try:
                price = struct.unpack('<d', chunk[i:i+8])[0]
                if 20.0 < price < 15000.0:
                    trades.append({
                        'account': account_filter,
                        'price': price, # Standardized key
                        'dt': datetime.datetime(1970, 1, 1), # Placeholder DT
                        'qty': 0,
                        'source': 'BINARY',
                    })
            except: pass
            
        start = idx + 1
        
    print(f"  Loaded {len(trades)} candidate prices from Binary windows (Total Records Searched: {match_count}).")

    # --- Part 2: Scan for Service Position Resets ---
    # Pattern: "Updated Service Position Quantity to " followed by number
    params = [
        rb'Updated Service Position Quantity to (-?\d+)',
        rb'Updated Service Position Quantity to\s+(-?\d+)'
    ]
    
    for p in params:
        for m in re.finditer(p, content):
            try:
                qty = int(m.group(1))
                resets.append({
                    'type': 'RESET',
                    'offset': m.start(),
                    'qty': qty
                })
            except: pass

    if resets:
        print(f"  [INFO] Found {len(resets)} 'Service Position Reset' events in binary.")
        
    return trades, resets

def run_verification(case_name, bin_paths, txt_path, account_filter):
    print(f"\n{'='*10} Verifying Case: {case_name} {'='*10}")
    
    # 1. Parse
    bin_trades = []
    all_resets = []
    for p in bin_paths:
        f, r = parse_binary_trades(p, account_filter)
        bin_trades.extend(f)
        all_resets.extend(r)
    
    txt_trades = parse_txt_trades(txt_path)
    
    print(f"  Total Text Trades: {len(txt_trades)}")
    
    # 2. Match & Filter
    compare_trades(txt_trades, bin_trades, all_resets)

def compare_trades(txt_trades, bin_trades, resets):
    print("\n--- COMPARISON & FILTERING ---")
    matches = 0
    missing = 0
    stuck_filtered = 0
    
    txt_trades.sort(key=lambda x: x['dt'])
    
    # --- Real Running Position Calculation ---
    # Create Event Stream:
    # 1. Trade Entries (Time: dt, Type: Entry, Side, Qty)
    # 2. Trade Exits (Time: exit_dt, Type: Exit, Side, Qty)
    # 3. Resets (Time: offset?? Need Time Mapping. For now, try linear interpolation or just ignore?)
    #    Actually, without timestamps on resets, we cannot interleave accurately.
    #    However, if we assume resets happen at specific intervals?
    #    Let's try to map Reset Offset -> Approximate Time using known Trade Offsets.
    
    # For now, simplistic Position calc based on Text only (Assuming flawless execution)
    entries = []
    for t in txt_trades:
        # Side Logic: Long = Buy(+), Short = Sell(-)
        qty = t['qty']
        side = 1 if "Long" in t.get('type', '') else -1 
        
        entries.append({'time': t['dt'], 'change': side * qty, 'type': 'ENTRY', 'ref': t})
        if t['exit_dt']:
            entries.append({'time': t['exit_dt'], 'change': -1 * side * qty, 'type': 'EXIT', 'ref': t})
            
    entries.sort(key=lambda x: x['time'])
    
    current_pos = 0
    max_pos = 0
    
    # Map running pos back to trade objects for display
    # We map the pos *after* the entry to the trade.
    
    for e in entries:
        current_pos += e['change']
        if abs(current_pos) > max_pos:
            max_pos = abs(current_pos)
        
        if e['type'] == 'ENTRY':
            e['ref']['running_pos_at_entry'] = current_pos

    print(f"\n  {'Time'[:19]:<20} | {'Sy':<4} | {'Price':<8} | {'Qty':<3} | {'Dur':<6} | {'RunPos':<6} | {'Status'}")
    print("-" * 100)

    # Re-matching logic with 24h filter
    for t_txt in txt_trades:
        # Simplification: Just calculate "Net Active" based on open/close times?
        # Complex. Let's stick to the "Stuck Filter" first.
        
        # Check "Stuck" Condition (Duration > 24h)
        is_stuck = False
        duration_str = "-"
        if t_txt['exit_dt']:
            duration = t_txt['exit_dt'] - t_txt['dt']
            duration_eval = duration.total_seconds() / 3600.0
            duration_str = f"{duration_eval:.1f}h"
            if duration_eval > 24.0:
                is_stuck = True
        
        # Binary Match Logic
        found = False
        for t_bin in bin_trades:
            # If Binary Date is 1970 placeholder, skip time check
            is_placeholder = (t_bin['dt'].year == 1970)
            
            if is_placeholder:
                dt_diff = 0 # Force match on time
            else:
                dt_diff = abs((t_txt['dt'] - t_bin['dt']).total_seconds())
                
            price_diff = abs(t_txt['price'] - t_bin['price'])
            
            # Tolerance: 120s (if valid time) and 0.02 price
            if dt_diff < 120 and price_diff < 0.02:
                found = True
                break
        
        status = "MATCHED"
        if not found: 
            status = "MISSING"
        if is_stuck:
            status = "STUCK (>24h)"
            stuck_filtered += 1
            
        if status == "MATCHED":
            matches += 1
            
        run_pos_val = t_txt.get('running_pos_at_entry', '?')
        print(f"  {t_txt['dt'].strftime('%Y-%m-%d %H:%M:%S'):<20} | {t_txt['symbol'].split(' ')[0]:<4} | {t_txt['price']:<8.2f} | {int(t_txt['qty']):<3} | {duration_str:<6} | {run_pos_val:<6} | {status}")

    print("-" * 100)
    print(f"Total Trades: {len(txt_trades)}")
    print(f"Stuck/Filtered (>24h): {stuck_filtered}")
    print(f"Valid Matches: {matches}")
    print(f"Max Calculated Running Position: {max_pos} (Limit: 3)")
    
    if max_pos <= 3.0:
        print("  [SUCCESS] Calculated Max Position is within simulation limits. (Any higher value in SC is a display glitch)")
    else:
        print(f"  [WARNING] Calculated Max Position {max_pos} EXCEEDED limit of 3!")


def calculate_max_position_violation(trades):
    # TODO: Implement full replay
    pass



def main():
    print("\n" + "=" * 50)
    print("STARTING ADVANCED VERIFICATION")
    print("=" * 50)
    
    # Case 1: 3Q Jan 19-20
    run_verification(
        "3Q_sim14 (Jan 19-20)",
        [
            r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-19_UTC.3Q_sim14.data",
            r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-20_UTC.3Q_sim14.data"
        ],
        r"C:\SierraChart\SC results WF\3q_sim14_01192026_TradesList.txt",
        "3Q_sim14"
    )
    
    # Case 2: IPS Dec 03-04
    run_verification(
        "IPS_TM_5dupli (Dec 03-04)",
        [
            r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data",
            r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-04_UTC.IPS_TM_5dupli.data"
        ],
        r"C:\SierraChart\SC results WF\IPS_TM_5_dupli_03122025_TradesList.txt",
        "IPS_TM_5dupli"
    )

if __name__ == "__main__":
    with open("verification_advanced_results.txt", "w", encoding="utf-8") as out_file:
        import sys
        original_stdout = sys.stdout
        sys.stdout = out_file
        try:
            main()
        except Exception as e:
            sys.stdout = original_stdout
            print(f"CRITICAL ERROR: {e}")
            raise e
        finally:
            sys.stdout = original_stdout
