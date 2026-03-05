import sys
import os
import asyncio
import struct

# Add project root to path
sys.path.insert(0, os.getcwd())

from trading_platform.services.binary_log_parser import _parse_tag66_timestamp

def audit_grouped(path):
    with open(path, "rb") as f:
        d = f.read()
    
    file_len = len(d)
    offset = 0
    
    # Store events: {timestamp_str: {side: set, qty: max, is_fill: bool}}
    events = {}
    
    current_ts = None
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        val_bytes = d[val_start:val_end]
        
        if tag == 0x66:
            parsed = _parse_tag66_timestamp(val_bytes)
            if parsed: current_ts = parsed.isoformat()
            
        if current_ts:
            if current_ts not in events:
                events[current_ts] = {"sides": set(), "qtys": [], "msgs": []}
            
            e = events[current_ts]
            if tag == 0x6b:
                st = val_bytes.decode(errors='ignore').strip().upper()
                if "BUY" in st or "LONG" in st: e["sides"].add("BUY")
                elif "SELL" in st or "SHORT" in st: e["sides"].add("SELL")
            
            if tag in [108, 114, 126]:
                q = 0
                if length == 4: q = struct.unpack('<i', val_bytes[:4])[0]
                elif length == 8: q = struct.unpack('<d', val_bytes[:8])[0]
                if q > 0: e["qtys"].append(q)
            
            if tag == 104:
                m = val_bytes.decode(errors='ignore').strip()
                e["msgs"].append(m)
        
        offset = val_end

    print(f"Total Unique Timestamps: {len(events)}")
    
    valid_fills = 0
    ghosts = 0
    
    for ts, e in sorted(events.items())[:50]:
        side = list(e["sides"])[0] if e["sides"] else "None"
        max_qty = max(e["qtys"]) if e["qtys"] else 0
        is_real_fill = any("(Filled)" in m or "simulation fill" in m for m in e["msgs"])
        
        if is_real_fill:
            valid_fills += 1
            print(f"[{ts}] FEEDBACK: Valid Fill | Side: {side:5} | Qty: {max_qty:4}")
        else:
            ghosts += 1
            # print(f"[{ts}] FEEDBACK: Noise/Signal | Msg: {e['msgs'][0][:50]}...")

    print(f"\nAudit Summary (First 500 buckets):")
    # ... actually let's just count all
    full_fills = sum(1 for ts, e in events.items() if any("(Filled)" in m or "simulation fill" in m for m in e["msgs"]))
    print(f"Total Logical Fills: {full_fills}")

audit_grouped(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
