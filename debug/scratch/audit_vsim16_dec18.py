import os
import struct
import re
import datetime

def get_sc_time_v3(value_bytes):
    if len(value_bytes) >= 8:
        try:
            # Entry 1: SCDateTime (double)
            val = struct.unpack('<d', value_bytes[:8])[0]
            if 30000 < val < 70000:
                base = datetime.datetime(1899, 12, 30)
                return base + datetime.timedelta(days=val)
            
            # Entry 2: Int64 Microseconds
            micros = struct.unpack('<q', value_bytes[:8])[0]
            if 1262304000000000 <= micros <= 2082758400000000:
                return datetime.datetime.fromtimestamp(micros / 1_000_000, tz=datetime.timezone.utc).replace(tzinfo=None)
        except: pass
    return None

def analyze_vsim16_dec18_v3():
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
        
        if tag == 0x66:
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt: current_dt = dt
        elif tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            if ("trade simulation fill" in s.lower() or "fill: " in s.lower()) and "updated internal position" not in s.lower():
                fills.append({"dt": current_dt, "msg": s})
        offset = val_end
        
    print(f"--- V_SIM16 2025-12-18 Detailed Audit ---")
    no_note = [f for f in fills if "AT_NQ_TM" not in f['msg']]
    
    # User's specific targets:
    # 04:05 (missing note)
    # 10:29 (missing note)
    # 16:58 (EOD - missing note but valid)
    
    for f in no_note:
        dt_str = f['dt'].strftime("%Y-%m-%d %H:%M:%S") if f['dt'] else "Unknown"
        # Extract price for easier comparison
        pm = re.search(r"(?:price|at|last)[:\s]*([\d]+\.?[\d]*)", f['msg'].lower())
        price = pm.group(1) if pm else "?"
        print(f"TIME: {dt_str} | PRICE: {price} | MSG: {f['msg']}")

if __name__ == "__main__":
    analyze_vsim16_dec18_v3()
