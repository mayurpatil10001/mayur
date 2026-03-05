import os
import struct
import re
import datetime

def get_sc_time_v3(value_bytes):
    if len(value_bytes) >= 8:
        try:
            q_val = struct.unpack('<q', value_bytes[:8])[0]
            if 3000000000000000 < q_val < 4500000000000000:
                return datetime.datetime(1899, 12, 30) + datetime.timedelta(microseconds=q_val)
        except: pass
    return None

def correct_ghost_scan():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    with open(data_path, "rb") as bf: d = bf.read()
    
    offset = 0
    current_dt = None
    
    records = []
    current_record_tags = {}
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        
        if tag == 0x66: # New Timestamp = Start of new set of tags (roughly)
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt != current_dt:
                # Close previous record
                if current_record_tags:
                    records.append({"dt": current_dt, "tags": current_record_tags})
                current_dt = dt
                current_record_tags = {}
        
        val = d[val_start:val_end]
        if tag == 0x68:
            current_record_tags[0x68] = val.decode(errors='ignore').strip()
        elif tag == 0x82:
            current_record_tags[0x82] = val.decode(errors='ignore').strip()
            
        offset = val_end

    print(f"--- Corrected Audit for V_SIM16 Dec 18 (Using Tag 0x82) ---")
    ghost_fills = []
    for r in records:
        msg = r['tags'].get(0x68, "")
        if "simulation fill" in msg.lower():
            note = r['tags'].get(0x82, "")
            ny_dt = r['dt'] - datetime.timedelta(hours=5) if r['dt'] else None
            
            if not note:
                ghost_fills.append({"dt": ny_dt, "msg": msg})
    
    for gf in ghost_fills:
        dt_str = gf['dt'].strftime("%H:%M:%S") if gf['dt'] else "?"
        print(f"GHOST (No Note) | NY: {dt_str} | Msg: {gf['msg']}")
        
    print(f"\nTotal Ghost Fills Found: {len(ghost_fills)}")

if __name__ == "__main__":
    correct_ghost_scan()
