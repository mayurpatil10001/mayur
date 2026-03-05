import struct, datetime, os

def _parse_tag66_timestamp(value_bytes):
    try:
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
    except: pass
    return None

def dump_ts(path, count=50):
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    found = 0
    
    while offset < file_len - 8 and found < count:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x66:
            ts = _parse_tag66_timestamp(d[val_start:val_end])
            if ts:
                print(f"[{found}] {ts.isoformat()}")
                found += 1
        
        offset += 8 + length

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
dump_ts(path)
