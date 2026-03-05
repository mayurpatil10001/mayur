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

def dec17_check():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-17_UTC.V_sim16.data"
    if not os.path.exists(data_path): return

    with open(data_path, "rb") as bf: d = bf.read()
    offset = 0
    current_dt = None
    records = []
    curr_tags = {}
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        if tag == 0x66:
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt != current_dt:
                if curr_tags: records.append({"dt": current_dt, "tags": curr_tags})
                current_dt = dt
                curr_tags = {}
        if tag == 0x68: curr_tags[0x68] = d[val_start:val_end].decode(errors='ignore').strip()
        elif tag == 0x82: curr_tags[0x82] = d[val_start:val_end].decode(errors='ignore').strip()
        offset = val_end

    print(f"--- V_SIM16 Ghost Trades Audit (Dec 17) ---")
    for r in records:
        msg = r['tags'].get(0x68, "")
        if "simulation fill" in msg.lower():
            note = r['tags'].get(0x82, "")
            ny_dt = r['dt'] - datetime.timedelta(hours=5) if r['dt'] else None
            if ny_dt and ny_dt.day == 17:
                if not note:
                    print(f"GHOST: {ny_dt.strftime('%H:%M:%S')} | {msg[:80]}")

if __name__ == "__main__":
    dec17_check()
