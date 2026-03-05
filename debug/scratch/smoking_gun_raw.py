import struct
import datetime
import os

def dump_vsim16_detailed(file_path, start_utc, end_utc):
    print(f"Detailed dump from {file_path}")
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as f:
        data = f.read()

    offset = 0
    file_len = len(data)
    
    current_ts = None
    current_note = ""
    current_msg = ""
    current_side = ""
    current_qty = 0
    current_price = 0
    
    # SC record starts with Tag 102 (0x66)
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', data[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        val_raw = data[val_start:val_end]
        
        if tag == 0x66: # Time - New Record
            # If we had a previous record, print it if in window
            if current_ts and start_utc <= current_ts <= end_utc:
                if "(Filled)" in current_msg or "Trade simulation fill" in current_msg:
                    print(f"TS: {current_ts} | Qty: {current_qty} | Side: {current_side} | Price: {current_price} | Note: [{current_note}] | Msg: {current_msg}")
            
            raw_ts = struct.unpack('<q', val_raw[:8])[0]
            base = datetime.datetime(1899, 12, 30)
            current_ts = base + datetime.timedelta(microseconds=raw_ts)
            current_note = ""
            current_msg = ""
            current_side = ""
            current_qty = 0
            current_price = 0
            
        elif tag == 0x82: # Note
            current_note = val_raw.decode(errors='ignore').strip()
        elif tag == 104: # Message
            msg = val_raw.decode(errors='ignore').strip()
            current_msg += " " + msg
            msg_l = msg.lower()
            if "buy" in msg_l or "bought" in msg_l or "long" in msg_l: current_side = "BUY"
            elif "sell" in msg_l or "sold" in msg_l or "short" in msg_l: current_side = "SELL"
            
            import re
            qm = re.search(r"(?:qty|quantity|size|vol)\s*:?\s*(\d+)", msg_l)
            if qm: current_qty = int(qm.group(1))
            
            pm = re.search(r"(?:lat|price|at|last)[:\s]*([\d]+\.?[\d]*)", msg_l)
            if pm: current_price = float(pm.group(1))
        
        offset = val_end

file_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
# 02:26 NY = 07:26 UTC
# 04:05 NY = 09:05 UTC
# 04:18 NY = 09:18 UTC
start = datetime.datetime(2025, 12, 18, 7, 20, 0)
end = datetime.datetime(2025, 12, 18, 9, 30, 0)
dump_vsim16_detailed(file_path, start, end)
