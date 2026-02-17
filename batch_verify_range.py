
import os
import struct
import re
import datetime
import csv
from typing import List, Dict, Tuple
import hashlib

# --- CONFIGURATION ---
ACCOUNT_FILTER = "3Q_sim14"
SYMBOL_FILTER = "CL"
START_DATE = datetime.datetime(2026, 1, 1)
END_DATE = datetime.datetime(2026, 2, 17, 23, 59, 59)
BINARY_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
EXPORT_FILE = r"C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt"
POSITION_LIMIT = 3

def get_md5(data_row: Dict) -> str:
    """Generate MD5 hash for a trade record to detect duplicates."""
    # Using key fields: DateTime, Symbol, price, qty, BuySell
    s = f"{data_row.get('dt')}_{data_row.get('symbol')}_{data_row.get('price')}_{data_row.get('qty')}_{data_row.get('side')}"
    return hashlib.md5(s.encode()).hexdigest()

def is_1700_cross(entry_dt: datetime.datetime, exit_dt: datetime.datetime) -> bool:
    """
    Check if a trade crosses the 17:00 EST mark.
    Simplified: If the date changes between entry and exit, it likely crossed 17:00.
    Exact check: Does it span across ANY 17:00?
    """
    if not entry_dt or not exit_dt: return False
    
    # Check if there is a 17:00 between entry and exit
    curr = entry_dt.replace(hour=17, minute=0, second=0, microsecond=0)
    if curr < entry_dt:
        curr += datetime.timedelta(days=1)
        
    return entry_dt < curr < exit_dt

def is_weekend_hold(entry_dt: datetime.datetime, exit_dt: datetime.datetime) -> bool:
    """Check if held across Friday 17:00 EST."""
    if not entry_dt or not exit_dt: return False
    
    # Iterate through potential Friday 17:00s
    d = entry_dt
    while d < exit_dt:
        if d.weekday() == 4: # Friday
            fri_17 = d.replace(hour=17, minute=0, second=0, microsecond=0)
            if entry_dt < fri_17 < exit_dt:
                return True
        d += datetime.timedelta(days=1)
        d = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return False

def parse_binary_trades(filepath: str, account_filter: str) -> List[Dict]:
    """Heuristic parse using 'Flex-Scan'."""
    if not os.path.exists(filepath):
        return []
        
    trades = []
    with open(filepath, 'rb') as f:
        content = f.read()
    
    b_target = account_filter.encode('utf-8')
    start = 0
    while True:
        idx = content.find(b_target, start)
        if idx == -1: break
        
        window_size = 1024
        limit = min(len(content), idx + window_size)
        chunk = content[idx:limit]
        
        for i in range(len(chunk)-8):
            try:
                price = struct.unpack('<d', chunk[i:i+8])[0]
                if 20.0 < price < 15000.0:
                    trades.append({
                        'price': round(price, 2),
                        'dt': datetime.datetime(1970, 1, 1),
                        'qty': 0,
                        'source': 'BINARY',
                    })
            except: pass
        start = idx + 1
    return trades

def run_batch_verification():
    print(f"--- BATCH VERIFICATION ---")
    print(f"Account: {ACCOUNT_FILTER}")
    print(f"Range: {START_DATE.date()} to {END_DATE.date()}")
    
    # 1. Parse Export File (Source of Truth for trade identity)
    print(f"\n[1/3] Parsing Trade Activity Export...")
    raw_fills = []
    if not os.path.exists(EXPORT_FILE):
        print(f"  [ERROR] Export file not found: {EXPORT_FILE}")
        return

    with open(EXPORT_FILE, 'r') as f:
        # reader = csv.DictReader(f, delimiter='\t')
        # Manually parse to handle potential header issues or empty lines
        header = f.readline().strip().split('\t')
        try:
            idx_type = header.index('ActivityType')
            idx_dt = header.index('DateTime')
            idx_side = header.index('BuySell')
            idx_price = header.index('FillPrice')
            idx_qty = header.index('FilledQuantity')
            idx_symbol = header.index('Symbol')
            idx_acc = header.index('TradeAccount')
        except ValueError as e:
            print(f"  [ERROR] Missing expected column in export: {e}")
            return

        for line in f:
            parts = line.split('\t')
            if len(parts) <= max(idx_type, idx_dt, idx_side, idx_price, idx_qty, idx_symbol, idx_acc):
                continue
                
            if parts[idx_type] != 'Fills': continue
            if parts[idx_acc] != ACCOUNT_FILTER: continue
            
            symbol_raw = parts[idx_symbol]
            if SYMBOL_FILTER not in symbol_raw: continue
            
            try:
                dt_str = parts[idx_dt].strip()
                # "2026-01-02  01:02:53.532212" -> replace double space
                dt_str = " ".join(dt_str.split())
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
                
                if not (START_DATE <= dt <= END_DATE): continue
                
                price = float(parts[idx_price]) if parts[idx_price] else 0.0
                qty = float(parts[idx_qty]) if parts[idx_qty] else 0.0
                side = parts[idx_side]
                
                raw_fills.append({
                    'dt': dt,
                    'side': side,
                    'price': round(price, 2),
                    'qty': qty,
                    'symbol': symbol_raw,
                    'md5': "" # Placeholder
                })
            except Exception as e:
                # print(f"DEBUG: Failed to parse fill row: {e}")
                continue

    print(f"  Found {len(raw_fills)} total fills in export for {SYMBOL_FILTER} in date range.")

    # 2. Pair Fills into Trades (FIFO)
    print(f"\n[2/3] Reconstructing Trades and applying Shield Filters...")
    
    trades = []
    open_lots = [] # List of (entry_dt, price, side, qty)
    
    stats = {
        'total_found': 0,
        'dropped_dupes': 0,
        'dropped_1700': 0,
        'dropped_24h': 0,
        'dropped_weekend': 0,
        'net_imported': 0,
        'suspicious_pos': 0
    }
    
    # Process fills to build trades
    # Note: This is an approximation. SC Trades map entry fills to exit fills.
    # We'll use a simple FIFO matcher for this audit.
    
    hashes = set()
    
    # For stats purposes, we count "Trades" as closed cycles or open lots?
    # Usually, the user wants "Trades" (Round-trips).
    
    for fill in raw_fills:
        # Check Deduplication
        f_hash = get_md5(fill)
        if f_hash in hashes:
            stats['dropped_dupes'] += 1
            continue
        hashes.add(f_hash)
        
        # FIFO matching
        match_found = False
        opp_side = 'Sell' if fill['side'] == 'Buy' else 'Buy'
        
        # Check if this fill closes an existing lot
        for i, lot in enumerate(open_lots):
            if lot['side'] == opp_side:
                # Close this lot (simplified 1:1 or partial)
                entry_dt = lot['dt']
                exit_dt = fill['dt']
                entry_price = lot['price']
                exit_price = fill['price']
                
                duration = (exit_dt - entry_dt).total_seconds() / 3600.0
                
                # Apply Shield Rules
                is_dropped = False
                if duration > 24.0:
                    stats['dropped_24h'] += 1
                    is_dropped = True
                    if stats['dropped_24h'] <= 3:
                        print(f"    [DEBUG] Dropped (24h): {entry_dt} -> {exit_dt} (Duration: {duration:.1f}h)")
                elif is_1700_cross(entry_dt, exit_dt):
                    stats['dropped_1700'] += 1
                    is_dropped = True
                    if stats['dropped_1700'] <= 3:
                        print(f"    [DEBUG] Dropped (17:00 Cross): {entry_dt} -> {exit_dt}")
                elif is_weekend_hold(entry_dt, exit_dt):
                    stats['dropped_weekend'] += 1
                    is_dropped = True
                    if stats['dropped_weekend'] <= 3:
                        print(f"    [DEBUG] Dropped (Weekend): {entry_dt} -> {exit_dt}")
                
                if not is_dropped:
                    trades.append({
                        'entry_dt': entry_dt,
                        'exit_dt': exit_dt,
                        'price': entry_price,
                        'exit_price': exit_price,
                        'qty': fill['qty'], # Simplified
                        'side': lot['side']
                    })
                
                open_lots.pop(i)
                match_found = True
                break
        
        if not match_found:
            open_lots.append(fill)

    stats['total_found'] = len(trades) + stats['dropped_24h'] + stats['dropped_1700'] + stats['dropped_weekend']
    stats['net_imported'] = len(trades)
    
    # 3. Cross-verify with Binary
    print(f"\n[3/3] Cross-verifying with Binary Logs...")
    
    # Load all binary prices for the range
    all_bin_prices = set()
    binary_files = [f for f in os.listdir(BINARY_DIR) if ACCOUNT_FILTER in f and "2026" in f]
    for bfile in binary_files:
        # Check file date
        match = re.search(r'(\d{4}-\d{2}-\d{2})', bfile)
        if match:
            f_dt = datetime.datetime.strptime(match.group(1), "%Y-%m-%d")
            if START_DATE.date() <= f_dt.date() <= END_DATE.date():
                bin_trades = parse_binary_trades(os.path.join(BINARY_DIR, bfile), ACCOUNT_FILTER)
                for bt in bin_trades:
                    all_bin_prices.add(bt['price'])
    
    print(f"  Loaded {len(all_bin_prices)} unique candidate prices from binary logs.")
    
    match_count = 0
    missing = []
    for t in trades:
        # Check entry or exit price in binary
        if t['price'] in all_bin_prices or t['exit_price'] in all_bin_prices:
            match_count += 1
        else:
            missing.append(t)

    # RE-ESTABLISH RUNNING POSITION TO FIND BREACHES
    print(f"\n[INFO] Validating Running Position (Limit: {POSITION_LIMIT})...")
    curr_pos = 0.0
    max_pos = 0.0
    for fill in raw_fills:
        qty = fill['qty']
        if fill['side'] == 'Sell': qty = -qty
        curr_pos += qty
        if abs(curr_pos) > max_pos:
            max_pos = abs(curr_pos)
        if abs(curr_pos) > POSITION_LIMIT:
            stats['suspicious_pos'] += 1

    # --- REPORT ---
    print("\n" + "="*40)
    print("      IMPORT STATISTICS REPORT")
    print("="*40)
    print(f"{'Metric':<25} {'Count':<10} {'%':<10}")
    print("-" * 40)
    total = stats['total_found'] or 1
    print(f"{'Total Trades Found':<25} {stats['total_found']:<10} 100%")
    print(f"{'Dropped: Duplicates':<25} {stats['dropped_dupes']:<10} {(stats['dropped_dupes']/total*100):.1f}%")
    print(f"{'Dropped: 17:00 Cross':<25} {stats['dropped_1700']:<10} {(stats['dropped_1700']/total*100):.1f}%")
    print(f"{'Dropped: Duration > 24h':<25} {stats['dropped_24h']:<10} {(stats['dropped_24h']/total*100):.1f}%")
    print(f"{'Dropped: Weekend Hold':<25} {stats['dropped_weekend']:<10} {(stats['dropped_weekend']/total*100):.1f}%")
    print("-" * 40)
    print(f"{'NET IMPORTED':<25} {stats['net_imported']:<10} {(stats['net_imported']/total*100):.1f}%")
    print("="*40)
    print(f"\n[INTEGRITY] Binary Reconciliation: {match_count}/{len(trades)} matches ({(match_count/max(1,len(trades))*100):.1f}%)")
    print(f"[RE-AUDIT] Max Running Position detected: {max_pos}")
    if stats['suspicious_pos'] > 0:
        print(f"  [SUSPICIOUS] Found {stats['suspicious_pos']} fills violating 3-lot limit.")
    else:
        print(f"  [CLEAR] No position limit breaches found.")

if __name__ == "__main__":
    run_batch_verification()
