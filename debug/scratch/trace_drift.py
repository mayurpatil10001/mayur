import os
import sys
import datetime
import struct

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, _pairs_to_trades, _get_base_symbol_standalone

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

print(f"Tracing Drift for {target_fp}")

# 1. Parse fills
fills, ghost_map = _parse_file_nitro(target_fp)
print(f"Found {len(fills)} total fills.")

# 2. Re-implement drift logic with detailed trace
groups = {}
for f in fills:
    key = (f['account_name'], f['symbol'])
    if key not in groups: groups[key] = []
    groups[key].append(f)

for (acc, specific_sym), group in groups.items():
    if acc != 'V_SIM16': continue
    base_sym = _get_base_symbol_standalone(specific_sym)
    print(f"\nTracing Account: {acc} Symbol: {base_sym}")
    
    group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
    
    # Simple Dedupe
    deduped_group = []
    seen_fill_sigs = set()
    for f in group:
        sig = (round(f.get('ts_val', 0) * 2) / 2.0, f['price'], f['side'], f['quantity'])
        if sig not in seen_fill_sigs:
            deduped_group.append(f)
            seen_fill_sigs.add(sig)
    
    buys, sells = [], []
    limit = 3
    drift_count = 0
    
    for f in deduped_group:
        qty, side, price, ts = f['quantity'], f['side'], f['price'], f['timestamp']
        current_net = sum(b['qty'] for b in buys) - sum(s['qty'] for s in sells)
        
        pre_pos = current_net
        is_blocked = False
        allowed = qty
        
        if side == 'BUY':
            intended = current_net + qty
            if intended > limit:
                allowed = max(0, limit - current_net)
                is_blocked = True
        else:
            intended = current_net - qty
            if intended < -limit:
                allowed = max(0, limit + current_net)
                is_blocked = True
        
        if is_blocked:
            drift_count += 1
            dropped = qty - allowed
            print(f"BLOCK: {ts} | Side {side} | Total {qty} | Allowed {allowed} | PrePos {pre_pos}")
            qty = allowed
            if qty == 0: continue
            
        # Match Fills (FIFO)
        if side == 'BUY':
            while qty > 0 and sells:
                s = sells[0]
                m_qty = min(qty, s['qty'])
                qty -= m_qty
                s['qty'] -= m_qty
                if s['qty'] <= 0: sells.pop(0)
            if qty > 0: buys.append({'qty': qty, 'price': price, 'ts': ts})
        else:
            while qty > 0 and buys:
                b = buys[0]
                m_qty = min(qty, b['qty'])
                qty -= m_qty
                b['qty'] -= m_qty
                if b['qty'] <= 0: buys.pop(0)
            if qty > 0: sells.append({'qty': qty, 'price': price, 'ts': ts})

    print(f"Total Drift Blocked in this file: {drift_count}")
