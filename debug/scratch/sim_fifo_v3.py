import os

fills_path = '/tmp/vsim16_dec18_clean_fills.txt'

def simulate_fifo(fills):
    buys = [] # [{'qty': q, 'time': t}]
    sells = []
    trades = []
    
    for line in fills:
        if 'TIMESTAMP' in line or '---' in line: continue
        parts = [x.strip() for x in line.split('|')]
        if len(parts) < 5: continue
        ts, sym, side, qty, price = parts
        qty = int(qty)
        
        if side == 'BUY':
            while qty > 0 and sells:
                s = sells[0]
                match_qty = min(qty, s['qty'])
                trades.append(f"SHORT: Entry {s['time']} (SELL), Exit {ts} (BUY), Qty {match_qty}")
                qty -= match_qty
                s['qty'] -= match_qty
                if s['qty'] <= 0: sells.pop(0)
            if qty > 0:
                buys.append({'qty': qty, 'time': ts})
        else: # SELL
            while qty > 0 and buys:
                b = buys[0]
                match_qty = min(qty, b['qty'])
                trades.append(f"LONG: Entry {b['time']} (BUY), Exit {ts} (SELL), Qty {match_qty}")
                qty -= match_qty
                b['qty'] -= match_qty
                if b['qty'] <= 0: buys.pop(0)
            if qty > 0:
                sells.append({'qty': qty, 'time': ts})
    
    return trades, buys, sells

with open(fills_path, 'r') as f:
    fills = f.readlines()

trades, remaining_buys, remaining_sells = simulate_fifo(fills)

print("--- RECONSTRUCTED TRADES (01:00 to 05:00 UTC) ---")
for t in trades:
    if "2025-12-18T01:" in t or "2025-12-18T02:" in t or "2025-12-18T03:" in t or "2025-12-18T04:" in t:
        print(t)
