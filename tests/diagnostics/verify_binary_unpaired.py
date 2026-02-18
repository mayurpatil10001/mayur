
import os
import sys

# Add path to services to import parser
sys.path.append(os.path.join(os.getcwd(), 'trading_platform', 'services'))

from binary_log_parser import BinaryLogParser, _parse_file_nitro

def check_unpaired():
    # Use a file we know exists
    target_file = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data"
    
    # ... (rest same until call)
    print(f"Analyzing file: {target_file}")
    
    parser = BinaryLogParser("temp.db")
    fills = _parse_file_nitro(target_file)
    print(f"Extracted {len(fills)} fills.")
    
    # Sort and Pair
    fills.sort(key=lambda x: x['timestamp'])
    
    trades, unpaired_count = parser._pairs_to_trades(fills)
    
    print(f"Formed {len(trades)} trades.")
    print(f"UNPAIRED FILLS: {unpaired_count}")
    
    if unpaired_count > 0:
        print("\n--- ORPHAN ANALYSIS ---")
        # To identify orphans, we need to run the pairing logic locally or access the leftovers
        # _pairs_to_trades internal shuffle...
        # Let's simple-sim it here
        
        groups = {}
        for f in fills:
            key = (f['account_name'], f['symbol'])
            if key not in groups: groups[key] = []
            groups[key].append(f)
            
        for key, group in groups.items():
            group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
            buys, sells = [], []
            orphans = []
            
            for f in group:
                qty, side = f['quantity'], f['side']
                if side in ('BUY', 'LONG'):
                    # Match with sells? No, usually FIFO is strictly time-based?
                    # The parser logic separates buys and sells then matches.
                    # Let's reproduce the parser logic exactly
                    pass
            
            # actually let's just use the `buys` and `sells` leftovers from a copy of the logic
            # Re-implementing simplified version for display
            
            # The parser logic:
            # buys waiting for sells, sells waiting for buys.
            # If we have leftovers in buys/sells lists, those are orphans.
            
            # Copied logic:
            buys = []
            sells = []
            
            for f in group:
                # ... (logic)
                qty = f['quantity']
                # ...
                # Skip re-implementation, just print the logic output if I can?
                # No, I can't access local vars of the function.
                pass

        # Let's just dump the raw fills that FAILED to pair.
        # Actually simplest way:
        # The orphan count is just `sum(b['qty']) + sum(s['qty'])`
        # We can reproduce the loop to find them.
        
        buys = []
        sells = []
        # Re-run pairing on this group
        # Assuming single group for this test file
        group = fills # Since we only parsed one file/account usually
        group.sort(key=lambda x: x.get('timestamp', ''))
        
        # This simple loop matches buys to sells purely FIFO
        matched_qty = 0
        
        # Separate buckets
        b_bucket = []
        s_bucket = []
        
        for f in group:
            if f['side'] in ('BUY', 'LONG'):
                b_bucket.append(f)
            else:
                s_bucket.append(f)
                
        # Now simplistic matching
        while b_bucket and s_bucket:
            b = b_bucket[0]
            s = s_bucket[0]
            
            q = min(b['quantity'], s['quantity'])
            b['quantity'] -= q
            s['quantity'] -= q
            matched_qty += q
            
            if b['quantity'] <= 0: b_bucket.pop(0)
            if s['quantity'] <= 0: s_bucket.pop(0)
            
        print(f"\nLeftover BUYS: {len(b_bucket)} fills")
        for b in b_bucket[:5]:
            print(f"  {b['timestamp']} {b['symbol']} Buy {b['quantity']} @ {b['price']}")
            
        print(f"\nLeftover SELLS: {len(s_bucket)} fills")
        for s in s_bucket[:5]:
            print(f"  {s['timestamp']} {s['symbol']} Sell {s['quantity']} @ {s['price']}")
            
        print("\nObservation:")
        if b_bucket and not s_bucket:
            print("  -> Missing SELLS. System saw opens but no closes.")
        elif s_bucket and not b_bucket:
            print("  -> Missing BUYS. System saw closes but no opens.")
        else:
            print("  -> Mixed mess. Likely crossing trades or partial data.")
             

if __name__ == "__main__":
    check_unpaired()
