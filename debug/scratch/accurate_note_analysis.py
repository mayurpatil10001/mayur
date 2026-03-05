import os
import struct
import re
import datetime

def analyze_vsim16_dec18_v4():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    if not os.path.exists(data_path): return

    with open(data_path, "rb") as bf:
        d = bf.read()
    
    offset = 0
    fills = []
    current_dt = None
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        
        if tag == 0x66 and length == 8:
            q_val = struct.unpack('<q', d[val_start:val_end])[0]
            if 3000000000000000 < q_val < 4500000000000000:
                current_dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(microseconds=q_val)
        elif tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            if ("trade simulation fill" in s.lower() or "fill: " in s.lower()) and "updated internal position" not in s.lower():
                fills.append({"dt": current_dt, "msg": s})
        offset = val_end
        
    print(f"--- V_SIM16 2025-12-18 Audit ---")
    no_note = [f for f in fills if "AT_NQ_TM" not in f['msg']]
    
    for f in no_note:
        dt_str = f['dt'].strftime("%Y-%m-%d %H:%M:%S") if f['dt'] else "Unknown"
        print(f"TIME: {dt_str} | MSG: {f['msg']}")

    print(f"\n--- Checking for CL (3Q_sim14) ---")
    cl_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-18_UTC.3Q_sim14.data"
    if os.path.exists(cl_path):
        with open(cl_path, "rb") as bf:
            d = bf.read()
        offset = 0
        cl_fills = 0
        cl_no_note = 0
        while offset < len(d) - 8:
            tag, length = struct.unpack('<II', d[offset : offset+8])
            val_start, val_end = offset + 8, offset + 8 + length
            if val_end > len(d): break
            if tag == 0x68:
                s = d[val_start:val_end].decode(errors='ignore').strip()
                if "trade simulation fill" in s.lower():
                    cl_fills += 1
                    if "AT_" not in s: cl_no_note += 1
            offset = val_end
        print(f"Account: 3Q_sim14 | Fills: {cl_fills} | Without Note: {cl_no_note}")

if __name__ == "__main__":
    analyze_vsim16_dec18_v4()
