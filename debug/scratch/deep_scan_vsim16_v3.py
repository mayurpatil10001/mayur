import struct, datetime, os

def _parse_tag66_timestamp(value_bytes):
    try:
        # AS PER binary_log_parser.py: mills since epoch (Int64)
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
    except: pass
    return None

def deep_scan(path, start_h, start_m, end_h, end_m):
    print(f"Deep scanning {path} for records between {start_h:02}:{start_m:02} and {end_h:02}:{end_m:02} (UTC)...")
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    current_ts = None
    
    while offset < file_len - 8:
        try:
            tag, length = struct.unpack('<II', d[offset:offset+8])
            val_start = offset + 8
            val_end = val_start + length
            if val_end > file_len: break
            
            if tag == 0x66:
                current_ts = _parse_tag66_timestamp(d[val_start:val_end])
            
            if current_ts:
                if (current_ts.hour > start_h or (current_ts.hour == start_h and current_ts.minute >= start_m)) and \
                   (current_ts.hour < end_h or (current_ts.hour == end_h and current_ts.minute <= end_m)):
                    payload = d[val_start:val_end]
                    try:
                        text = payload.decode(errors='ignore').strip()
                    except:
                        text = f"<bytes:{len(payload)}>"
                    
                    if tag == 104 or tag == 0x68: # Msg
                        print(f"[{current_ts.isoformat()}] MSG: {text}")
                    elif tag == 0x82: # Note
                        print(f"[{current_ts.isoformat()}] NOTE: {text}")
                    elif tag == 107: # Order Type
                         print(f"[{current_ts.isoformat()}] TAG 107: {text}")
            
            offset += 8 + length
        except: break

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
deep_scan(path, 2, 20, 2, 30)
