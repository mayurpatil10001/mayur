import os

fills_path = '/tmp/vsim16_dec18_clean_fills.txt'

def simulate_fifo(fills):
    buys = [] # [{'qty': q, 'time': t}]
    sells = []
    trades = []
    
    for line in fills:
        if 'TIMESTAMP' in line or '---' in line: continue
        ts, sym, side, qty, price = [x.strip() for x in line.split('|')]
        qty = int(qty)
        
        if side == 'BUY':
            while qty > 0 and sells:
                s = sells[0]
                match_qty = min(qty, s['qty'])
                trades.append(f"LONG TRADE: Entry {s['time']} (SELL), Exit {ts} (BUY), Qty {match_qty}")
                qty -= match_qty
                s['qty'] -= match_qty
                if s['qty'] <= 0: sells.pop(0)
            if qty > 0:
                buys.append({'qty': qty, 'time': ts})
        else: # SELL
            while qty > 0 and buys:
                b = buys[0]
                match_qty = min(qty, b['qty'])
                trades.append(f"LONG TRADE: Entry {b['time']} (BUY), Exit {ts} (SELL), Qty {match_qty}")
                qty -= match_qty
                b['qty'] -= match_qty
                if b['qty'] <= 0: buys.pop(0)
            if qty > 0:
                sells.append({'qty': qty, 'time': ts})
    
    return trades, buys, sells

with open(fills_path, 'r') as f:
    fills = f.readlines()

trades, remaining_buys, remaining_sells = simulate_fifo(fills)

print("--- RECONSTRUCTED TRADES ---")
for t in trades:
    print(t)

print("\n--- REMAINING OPEN POSITIONS ---")
for b in remaining_buys:
    print(f"OPEN BUY: {b['time']}, Qty {b['qty']}")
for s in remaining_sells:
    print(f"OPEN SELL: {s['time']}, Qty {s['qty']}")
