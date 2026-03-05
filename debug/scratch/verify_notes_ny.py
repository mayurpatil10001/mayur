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

def verify_all_vsim16_notes():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    with open(data_path, "rb") as bf: d = bf.read()
    
    offset = 0
    current_dt = None
    fills = []
    
    while offset < len(d) - 16:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        
        if tag == 0x66:
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt: current_dt = dt
        elif tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            if ("trade simulation fill" in s.lower() or "fill: " in s.lower()):
                fills.append({"dt": current_dt, "msg": s})
        offset = val_end

    print(f"--- V_SIM16 Dec 18 Audit [Times in NY] ---")
    for f in fills:
        if not f['dt']: continue
        # Convert UTC to NY (subtract 5 hours)
        ny_dt = f['dt'] - datetime.timedelta(hours=5)
        
        has_note = "AT_NQ_TM" in f['msg']
        
        # User targets (NY):
        # 04:05 (missing note)
        # 10:29 (missing note)
        # 16:58 (EOD - missing note but valid)
        
        if not has_note:
            print(f"NO-NOTE | {ny_dt.strftime('%H:%M:%S')} | {f['msg'][:100]}")
        elif ny_dt.hour == 4 and ny_dt.minute == 5:
            print(f"   NOTE | {ny_dt.strftime('%H:%M:%S')} | {f['msg'][:100]}")

if __name__ == "__main__":
    verify_all_vsim16_notes()
