import os
import struct
import re
import datetime

def get_sc_time(value_bytes):
    if len(value_bytes) < 8: return None
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=val)
    except: pass
    return None

def analyze_vsim16_dec18_v2():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        return

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
        
        if tag == 0x66: # Time
            dt = get_sc_time(d[val_start:val_end])
            if dt: current_dt = dt
        elif tag == 0x68: # Message
            s = d[val_start:val_end].decode(errors='ignore').strip()
            s_lower = s.lower()
            if ("trade simulation fill" in s_lower or "fill: " in s_lower) and "updated internal position" not in s_lower:
                fills.append({"dt": current_dt, "msg": s})
        offset = val_end
        
    print(f"--- FILLS WITHOUT NOTE: V_SIM16 2025-12-18 ---")
    no_note = [f for f in fills if "AT_NQ_TM" not in f['msg']]
    for f in no_note:
        dt_str = f['dt'].strftime("%Y-%m-%d %H:%M:%S") if f['dt'] else "Unknown"
        print(f"{dt_str} | {f['msg']}")

def check_other_accounts():
    data_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    accounts = ['3Q_sim14', '3Q_sim15', 'TM_6', 'IPS_TM_13']
    
    print(f"\n--- SCANNING OTHER ACCOUNTS FOR 'NOTE-LESS' FILLS ---")
    for acc in accounts:
        pattern = os.path.join(data_dir, f"*_{acc}.data")
        import glob
        files = glob.glob(pattern)
        if not files: continue
        
        # Check one recent file for each
        files.sort(reverse=True)
        fp = files[0]
        
        with open(fp, "rb") as bf:
            d = bf.read()
            
        fills_count = 0
        no_note_count = 0
        
        offset = 0
        while offset < len(d) - 8:
            tag, length = struct.unpack('<II', d[offset : offset+8])
            val_start = offset + 8
            val_end = val_start + length
            if val_end > len(d): break
            if tag == 0x68:
                s = d[val_start:val_end].decode(errors='ignore').strip()
                if ("trade simulation fill" in s.lower() or "fill: " in s.lower()) and "updated internal position" not in s.lower():
                    fills_count += 1
                    # Generic strategy note pattern check?
                    # 3Q accounts usually have 'AT_' notes or similar?
                    # Let's see what notes they DO have
                    if "AT_" not in s:
                        no_note_count += 1
            offset = val_end
            
        print(f"Account: {acc} | File: {os.path.basename(fp)}")
        print(f"  Total Fills: {fills_count} | Without 'AT_' Note: {no_note_count}")

if __name__ == "__main__":
    analyze_vsim16_dec18_v2()
    check_other_accounts()
