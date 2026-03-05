import sys
import datetime as dt
from pathlib import Path
import re

def load_sc_trades(file_path):
    trades = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
        for line in lines[1:]:
            if not line.strip() or 'Total:' in line: continue
            parts = line.strip().split('\t')
            if len(parts) < 10: continue
            
            def clean_ts(ts_str):
                ts_str = ts_str.replace(' BP', '').replace(' EP', '').strip()
                ts_str = re.sub(' +', ' ', ts_str)
                # SC is in NY Time. Convert to UTC (NY+5h)
                # Note: This is an approximation. If it's DST, it might be 4h.
                # In Feb, it's 5h.
                t = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
                return t + dt.timedelta(hours=5)

            try:
                trades.append({
                    'entry_dt': clean_ts(parts[2]),
                    'exit_dt': clean_ts(parts[3]),
                    'entry_price': float(parts[4]),
                    'exit_price': float(parts[5]),
                    'qty': int(parts[6]),
                    'side': parts[1]
                })
            except Exception as e:
                pass
    return trades

def load_internal_trades(file_path):
    trades = []
    fifo_map_open = {} 
    
    with open(file_path, 'r') as f:
        for line in f:
            if '|' not in line: continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 6: continue
            
            ts_str = parts[0] # Now contains YYYY-MM-DD HH:MM:SS.mmm
            try:
                full_dt = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
            except: continue
            
            fifo_info = parts[5]
            if not fifo_info: continue
            
            matches = re.findall(r'FIFO_(\d+)_(\w+)\((\d+)\)', fifo_info)
            for f_id, f_type, f_qty in matches:
                f_id = int(f_id)
                if f_type == 'ENTRY':
                    fifo_map_open[f_id] = {
                        'entry_ts': full_dt,
                        'entry_price': float(parts[4]),
                        'qty': int(f_qty),
                        'side': parts[1]
                    }
                elif f_type == 'EXIT':
                    if f_id in fifo_map_open:
                        entry = fifo_map_open[f_id]
                        trades.append({
                            'entry_dt': entry['entry_ts'],
                            'exit_dt': full_dt,
                            'entry_price': entry['entry_price'],
                            'exit_price': float(parts[4]),
                            'qty': int(f_qty),
                            'side': entry['side']
                        })
    return trades

def compare():
    sc_file = r"C:\SierraChart\SC results WF\docs\SC screenshots 2026-12-08\nq_tm6_0225-0228 trade list.txt"
    internal_file = r"C:\SierraChart\SC results WF\trade_sequence_report.txt"
    
    sc_trades = load_sc_trades(sc_file)
    internal_trades = load_internal_trades(internal_file)
    
    print(f"Total SC Trades: {len(sc_trades)}")
    print(f"Total Internal FIFO Trades: {len(internal_trades)}")
    
    matches_strict = 0
    used_internal = set()
    
    for idx_sc, sc in enumerate(sc_trades):
        for idx_it, it in enumerate(internal_trades):
            if idx_it in used_internal: continue
            
            # Time tolerance: 2 seconds
            if abs((sc['entry_dt'] - it['entry_dt']).total_seconds()) < 2.0 and \
               abs((sc['exit_dt'] - it['exit_dt']).total_seconds()) < 2.0 and \
               abs(sc['entry_price'] - it['entry_price']) < 0.1 and \
               abs(sc['exit_price'] - it['exit_price']) < 0.1 and \
               sc['qty'] == it['qty']:
                matches_strict += 1
                used_internal.add(idx_it)
                break

    print(f"Strict Matches (Time window/Price/Qty): {matches_strict}")
    if len(sc_trades) > 0:
        print(f"Strict Match Rate: {(matches_strict/len(sc_trades))*100:.2f}%")

if __name__ == "__main__":
    compare()
