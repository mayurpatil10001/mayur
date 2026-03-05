import os, re, datetime

fills_path = '/tmp/vsim16_dec18_clean_fills.txt'

def analyze_net_position(fills):
    pos = 0
    print(f"{'TIMESTAMP':<30} | {'CHANGE':<10} | {'NET POS':<10}")
    print("-" * 55)
    for line in fills:
        if 'TIMESTAMP' in line or '---' in line: continue
        parts = [x.strip() for x in line.split('|')]
        if len(parts) < 5: continue
        ts, sym, side, qty, price = parts
        qty = int(qty)
        
        if side == 'BUY':
            pos += qty
        else:
            pos -= qty
        
        print(f"{ts:<30} | {side+' '+str(qty):<10} | {pos:<10}")

with open(fills_path, 'r') as f:
    fills = f.readlines()

analyze_net_position(fills)
