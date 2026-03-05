import struct, datetime, re, os

def _parse_tag66_timestamp(value_bytes):
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(days=val)
    except: pass
    return None

def scan_file(path):
    print(f"Scanning {path}...")
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    current_ts = None
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x66:
            current_ts = _parse_tag66_timestamp(d[val_start:val_end])
        
        # Look for FILL (Tag 101/0x65)
        if tag == 101:
            if current_ts and "2025-12-18T02:26" in current_ts.isoformat():
                # Extract some more info if possible
                # But mostly we just want to know it's there
                print(f"FOUND FILL AT {current_ts.isoformat()}")
        
        offset += 8 + length

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
if os.path.exists(path):
    scan_file(path)
else:
    print("File not found")
