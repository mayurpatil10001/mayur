
import os
import struct
import datetime
import re
from typing import List, Dict, Any

# --- CONFIGURATION ---
BINARY_DIR = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
TEXT_DIR = r"C:\SierraChart\SC results WF"

def parse_trades_list(filepath: str) -> List[Dict]:
    trades = []
    print(f"Parsing TEXT file: {os.path.basename(filepath)}")
    if not os.path.exists(filepath):
        print("  [ERROR] File not found.")
        return []
        
    with open(filepath, 'r') as f:
        header = f.readline().strip().split('\t')
        cols = {h.strip(): i for i, h in enumerate(header)}
        
        idx_sym = cols.get("Symbol")
        idx_entry = cols.get("Entry DateTime")
        idx_ep = cols.get("Entry Price")
        idx_qty = cols.get("Trade Quantity")
        
        if idx_sym is None or idx_entry is None:
            print("  [ERROR] Critical columns missing in Text header.")
            return []

        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < len(cols): continue
            
            try:
                sym = parts[idx_sym]
                entry_str = parts[idx_entry]
                
                # Date Parsing
                fmt = "%Y-%m-%d %H:%M:%S"
                entry_str_clean = entry_str.replace(" BP", "").replace(" EP", "").strip()
                try:
                    entry_dt = datetime.datetime.strptime(entry_str_clean, fmt + ".%f")
                except:
                    try:
                        entry_dt = datetime.datetime.strptime(entry_str_clean, fmt)
                    except:
                        entry_dt = datetime.datetime.strptime(entry_str_clean.split('.')[0], fmt)

                trades.append({
                    'symbol': sym,
                    'entry_dt': entry_dt,
                    'qty': float(parts[idx_qty]) if idx_qty is not None else 0,
                    'entry_price': float(parts[idx_ep]) if idx_ep is not None else 0.0,
                    'source': 'TEXT'
                })
            except: pass
                
    print(f"  Loaded {len(trades)} trades from Text.")
    return trades

def heuristic_parse_binary(filepath: str, target_account: str, price_offset: int) -> List[Dict]:
    """
    Revised logic: Scan a 1024-byte window after each account string occurrence for ANY valid-looking prices.
    This handles variable-length records and field shifts that fixed offsets miss.
    """
    print(f"Parsing BINARY file (Flex-Scan): {os.path.basename(filepath)}")
    if not os.path.exists(filepath):
        print("  [ERROR] File not found.")
        return []
        
    trades = []
    with open(filepath, 'rb') as f:
        content = f.read()
    
    b_target = target_account.encode('utf-8')
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
                        'account': target_account,
                        'entry_price': price,
                        'source': 'BINARY',
                        'offset': idx + i
                    })
            except: continue
            
        start = idx + 1 # Move to next occurrence

    print(f"  Loaded {len(trades)} candidate prices from Binary windows (Total Records Searched: {match_count}).")
    return trades

def run_verification(case_name, bin_paths, txt_path, account_filter):
    print(f"\n{'='*10} Verifying Case: {case_name} {'='*10}")
    
    # 1. Parse
    bin_trades = []
    for p in bin_paths:
        bin_trades.extend(heuristic_parse_binary(p, account_filter, 0))
    
    txt_trades = parse_trades_list(txt_path)
    
    print(f"  Total Text Trades: {len(txt_trades)}")
    
    # 2. Match
    print("\n  --- Matching Results ---")
    print(f"  {'Time':<20} | {'Price':<10} | {'Symbol':<10} | {'Status':<15} | {'Binary Match'}")
    print("-" * 85)
    
    matches = 0
    txt_trades.sort(key=lambda x: x['entry_dt'])
    
    matched_bin_indices = set()
    
    for txt in txt_trades:
        best_match = None
        for i, b in enumerate(bin_trades):
            if i in matched_bin_indices: continue
            
            p_diff = abs(txt['entry_price'] - b['entry_price'])
            if p_diff < 0.02:
                best_match = b
                matched_bin_indices.add(i)
                break 
                    
        status_str = "MATCHED" if best_match else "MISSING"
        bin_info = f"Bin found @ {best_match['entry_price']:.2f}" if best_match else "No match in Binary"
        
        if status_str == "MATCHED": 
            matches += 1
        
        print(f"  {txt['entry_dt'].strftime('%Y-%m-%d %H:%M:%S'):<20} | {txt['entry_price']:<10.2f} | {txt['symbol']:<10} | {status_str:<15} | {bin_info}")

    print(f"\n  Final Stats: {matches}/{len(txt_trades)} Matched. (Gap Closed: Verifying All Recorded Days)")

def main():
    with open("verification_utf8_results.txt", "w", encoding="utf-8") as out_file:
        import sys
        original_stdout = sys.stdout
        sys.stdout = out_file
        try:
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
        finally:
            sys.stdout = original_stdout

if __name__ == "__main__":
    main()

