import struct, datetime, os

def _parse_tag66_timestamp(value_bytes):
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(days=val)
    except: pass
    return None

def scan_range(path):
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    first_ts = None
    last_ts = None
    count = 0
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x66:
            ts = _parse_tag66_timestamp(d[val_start:val_end])
            if ts:
                if first_ts is None: first_ts = ts
                last_ts = ts
                count += 1
        
        offset += 8 + length
    
    print(f"File: {os.path.basename(path)}")
    print(f"First TS: {first_ts.isoformat() if first_ts else 'None'}")
    print(f"Last TS:  {last_ts.isoformat() if last_ts else 'None'}")
    print(f"Records:  {count}")

paths = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
]

for p in paths:
    scan_range(p)
