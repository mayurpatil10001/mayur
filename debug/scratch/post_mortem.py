import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone

async def drift_post_mortem():
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    file = os.path.join(path, "TradeActivityLog_2026-02-25_UTC.V_sim16.data")
    
    # We need a modified parser that returns GHOSTS too
    import struct
    import re
    from trading_platform.services.binary_log_parser import _is_ghost_fill, _parse_tag66_timestamp, NY_TZ
    
    with open(file, "rb") as f:
        d = f.read()
    
    file_len = len(d)
    offset = 0
    all_fills_including_ghosts = []
    
    pending_fill = None
    current_ts_val = 0
    current_ts_str = ""
    current_note = ""
    current_tag107 = ""
    current_msg = ""

    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        
        if tag == 0x66:
            if pending_fill:
                pending_fill['is_ghost'] = _is_ghost_fill(pending_fill['account_name'], pending_fill['note'], pending_fill['timestamp'])
                all_fills_including_ghosts.append(pending_fill)
                pending_fill = None
                current_note = ""; current_tag107 = ""; current_msg = ""
            
            parsed = _parse_tag66_timestamp(d[val_start:val_end])
            if parsed: current_ts_val, current_ts_str = parsed.timestamp(), parsed.isoformat()
            
        elif tag == 0x82:
            current_note = (current_note + " " + d[val_start:val_end].decode(errors='ignore').strip()).strip()
        elif tag == 107:
            current_tag107 = d[val_start:val_end].decode(errors='ignore').strip()
        elif tag == 104:
            current_msg = d[val_start:val_end].decode(errors='ignore').strip()
            
        elif tag == 0x6b: # Order Side text
            side_text = d[val_start:val_end].decode(errors='ignore').strip().upper()
            side = ""
            if "BUY" in side_text or "LONG" in side_text: side = "BUY"
            elif "SELL" in side_text or "SHORT" in side_text: side = "SELL"
            
            if side and current_ts_str:
                # Basic quantity for the audit
                qty = 1 
                # Try to find decimals in hex if we wanted, but let's just use 1 as default for now 
                # or try to extract it from nearby tags if we wanted.
                # Actually, let's just assume we found side and create a pending_fill
                pending_fill = {
                    "account_name": "V_SIM16", "symbol": "NQ", "price": 0, "side": side,
                    "quantity": 1, "timestamp": current_ts_str, "ts_val": current_ts_val,
                    "note": ""
                }
        
        # Quantity Tags (108, 114, 126)
        if tag in [108, 114, 126] and pending_fill:
            if length == 4: pending_fill['quantity'] = struct.unpack('<i', d[val_start:val_start+4])[0]
            elif length == 8: pending_fill['quantity'] = int(struct.unpack('<d', d[val_start:val_start+8])[0])

        if pending_fill:
            pending_fill['note'] = (current_note + " " + current_tag107 + " " + current_msg).strip()

        offset = val_end

    print(f"Total entries (with ghosts): {len(all_fills_including_ghosts)}")
    
    current_net = 0
    limit = 3
    for f in all_fills_including_ghosts[:100]:
        if f['is_ghost']:
            print(f"[{f['timestamp']}] GHOST {f['side']} {f['quantity']} | (Skipped)")
            continue
            
        qty, side = f['quantity'], f['side']
        intended = (current_net + qty) if side == 'BUY' else (current_net - qty)
        rejection = 0
        if side == 'BUY' and intended > limit: rejection = qty - (limit - current_net)
        elif side == 'SELL' and intended < -limit: rejection = qty - (limit + current_net)
        
        allowed = qty - (rejection if rejection > 0 else 0)
        pre = current_net
        if side == 'BUY': current_net += allowed
        else: current_net -= allowed
        
        rej_str = f" [DRIFT {rejection}]" if (rejection if rejection > 0 else 0) > 0 else ""
        print(f"[{f['timestamp']}] {side:<5} {qty:2d} | Pre: {pre:2d} | Allowed: {allowed:2d} | Post: {current_net:2d}{rej_str}")

if __name__ == "__main__":
    asyncio.run(drift_post_mortem())
