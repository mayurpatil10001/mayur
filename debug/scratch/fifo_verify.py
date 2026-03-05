import os
import sys
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, NY_TZ

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills_clean, _ = _parse_file_nitro(target_fp)
v_clean = [f for f in fills_clean if f['account_name'] == 'V_SIM16']
v_clean.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# The user tells me: 
# "if you remove that ghost trade service order id 36783140 then it will be ok"
# and: "we buy 3, send stop for 3 (open order) and 2 or 3 limit sell (open orders) 
#        so all positions are 3"
# 
# This means the strategy pattern is:
#   BUY 3 -> opens 3 long
#   SELL 1 (limit) -> partial close
#   SELL 2 (stop) -> close remaining
#   OR BUY 3 -> opens 3 short (direction flip) 
#
# The raw fill trace I computed is WRONG because I'm just adding/subtracting
# without matching. In reality, SC matches fills FIFO to determine OPEN position.
#
# The user's Trades list shows max openQty=3 at all times.
# 
# Let me verify: In the user's SC fill list (first screenshot), 
# the fills match EXACTLY our parser output (minus the ghost at 36783140).
#
# What the user wants me to understand:
# 1. Ghost fills (no note) create phantom positions
# 2. These phantom positions then cause the FIFO pairing to go haywire
# 3. If we remove ghosts, FIFO pairing stays clean at max 3
#
# So the "drift" isn't about capping at 3 - it's about removing ghosts.
# Without ghosts, there should be NO drift at all.

# Let me verify: Simulate FIFO matching and check if position ever exceeds 3
# after removing ghosts

print("=== FIFO POSITION MATCHING (Ghost fills removed) ===")
print()

buys = []  # [{qty, price, time}]
sells = [] # [{qty, price, time}]

max_long = 0
max_short = 0
violations = 0

for f in v_clean:
    side = f['side']
    qty = f['quantity']
    ts = f['timestamp']
    
    try:
        dt_utc = datetime.datetime.fromisoformat(ts).replace(tzinfo=ZoneInfo("UTC"))
        dt_ny = dt_utc.astimezone(NY_TZ)
        ny_str = dt_ny.strftime("%H:%M:%S")
    except:
        ny_str = "???"
    
    if side == 'BUY':
        # First close any pending sells (FIFO)
        while qty > 0 and sells:
            s = sells[0]
            match_qty = min(qty, s['qty'])
            qty -= match_qty
            s['qty'] -= match_qty
            if s['qty'] <= 0: sells.pop(0)
        # Remaining qty opens new long
        if qty > 0:
            buys.append({'qty': qty, 'time': ts})
    else:
        # First close any pending buys (FIFO)
        while qty > 0 and buys:
            b = buys[0]
            match_qty = min(qty, b['qty'])
            qty -= match_qty
            b['qty'] -= match_qty
            if b['qty'] <= 0: buys.pop(0)
        # Remaining qty opens new short
        if qty > 0:
            sells.append({'qty': qty, 'time': ts})
    
    open_long = sum(b['qty'] for b in buys)
    open_short = sum(s['qty'] for s in sells)
    open_pos = open_long - open_short  # net, but only one side should be non-zero
    
    max_long = max(max_long, open_long)
    max_short = max(max_short, open_short)
    
    if open_long > 3 or open_short > 3:
        violations += 1
        flag = "VIOLATION!"
        print(f"  {ts[:23]} | NY:{ny_str} | {side:5} Qty:{f['quantity']} | OpenLong:{open_long} OpenShort:{open_short} | {flag}")

print(f"\nMax Open Long: {max_long}")
print(f"Max Open Short: {max_short}")
print(f"Violations (open > 3): {violations}")
print(f"\nIf violations = 0, the user is RIGHT: ghost removal is sufficient, no drift guard needed.")
