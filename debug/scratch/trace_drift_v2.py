import os
import sys
import datetime
import struct

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

# Correctly import from the module
import trading_platform.services.binary_log_parser as blp
from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

print(f"Tracing Drift for {target_fp}")

# 1. Parse fills using the production parser
importer = blp.BinaryLogImporter()
fills, pc = _parse_file_nitro(target_fp)
print(f"File Parsing Complete. Found {len(fills)} potential fills.")

# 2. Re-implement drift logic with detailed trace
groups = {}
for f in fills:
    key = (f['account_name'], f['symbol'])
    if key not in groups: groups[key] = []
    groups[key].append(f)

for (acc, specific_sym), group in groups.items():
    if acc.upper() != 'V_SIM16': continue
    base_sym = _get_base_symbol_standalone(specific_sym)
    print(f"\nMT TRACE | Account: {acc} Symbol: {base_sym}")
    
    group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
    
    # Simple Dedupe (Mirroring Production)
    deduped_group = []
    seen_fill_sigs = set()
    for f in group:
        # Match production dedupe (500ms)
        sig = (round(f.get('ts_val', 0) * 2) / 2.0, f['price'], f['side'], f['quantity'])
        if sig not in seen_fill_sigs:
            deduped_group.append(f)
            seen_fill_sigs.add(sig)
    
    buys, sells = [], []
    limit = 3
    drift_count = 0
    total_rejections = 0
    
    print(f"--- Fills Sorted ({len(deduped_group)}) ---")
    for f in deduped_group:
        qty, side, price, ts = f['quantity'], f['side'].upper(), f['price'], f['timestamp']
        
        # Calculate current net (Matched Long - Matched Short)
        current_net = sum(b['qty'] for b in buys) - sum(s['qty'] for s in sells)
        
        intended = current_net + qty if side == 'BUY' else current_net - qty
        
        is_blocked = False
        allowed = qty
        
        if side == 'BUY':
            if intended > limit:
                allowed = max(0, limit - current_net)
                is_blocked = True
        else:
            if intended < -limit:
                allowed = max(0, limit + current_net)
                is_blocked = True
        
        if is_blocked:
            total_rejections += 1
            dropped = qty - allowed
            if dropped > 0:
                print(f"CLIP: {ts} {side} {qty} -> {allowed} | Pos: {current_net}")
            qty = allowed
            if qty == 0: continue
            
        # Match (Mirroring pairs_to_trades logic)
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

    print(f"Done. Rejections: {total_rejections}")
