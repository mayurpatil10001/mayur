import struct, datetime, os

def _parse_tag66_timestamp(value_bytes):
    try:
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
    except: pass
    return None

def dump_detailed(path, limit=100):
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    current_ts = None
    found = 0
    
    while offset < file_len - 8 and found < limit:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        payload = d[val_start:val_end]
        
        if tag == 0x66:
            current_ts = _parse_tag66_timestamp(payload)
        
        ts_str = current_ts.isoformat() if current_ts else "NO_TS"
        
        try:
            text = payload.decode(errors='ignore').strip()
        except:
            text = ""

        hex_val = payload.hex()
        
        print(f"[{ts_str}] Tag {tag:<3} | Len {length:<4} | {text:<30} | {hex_val}")
        found += 1
        
        offset += 8 + length

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
dump_detailed(path, 150)
