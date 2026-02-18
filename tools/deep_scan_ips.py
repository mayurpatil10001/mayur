
import struct
import os

def deep_scan_ips():
    f = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data"
    target_account = b"IPS_TM_5dupli"
    # Some missing trades from text file
    missing_targets = [58.89, 59.05, 59.34, 59.53, 59.41]
    
    with open(f, 'rb') as f:
        content = f.read()
    
    print(f"File size: {len(content)}")
    
    # Let's find every occurrence of the account string
    account_indices = []
    start = 0
    while True:
        idx = content.find(target_account, start)
        if idx == -1: break
        account_indices.append(idx)
        start = idx + 1
    
    print(f"Found {len(account_indices)} account string occurrences.")
    
    # For each missing target price, find if it exists near ANY account record
    for p in missing_targets:
        found_near = []
        # First, find ALL occurrences of the price as a double
        price_indices = []
        for i in range(len(content)-8):
            val = struct.unpack('<d', content[i:i+8])[0]
            if abs(val - p) < 0.0001:
                price_indices.append(i)
        
        if not price_indices:
            print(f"Price {p} NOT FOUND anywhere in file.")
            continue
            
        print(f"Price {p} found at {len(price_indices)} offsets.")
        
        # Check proximity to account string
        for price_idx in price_indices:
            # Find nearest account index
            # (We look for the account string that PRECEDES the price, usually within a few hundred bytes)
            for acc_idx in account_indices:
                diff = price_idx - acc_idx
                if 0 < diff < 1000:
                    found_near.append(diff)
        
        if found_near:
            print(f"  Price {p} is near account records at relative offsets: {sorted(list(set(found_near)))}")
        else:
            print(f"  Price {p} is NOT near any account records (within +1000 bytes).")

if __name__ == "__main__":
    deep_scan_ips()
