import struct, datetime, os, sys

# Set encoding to utf-8 for pipe safety
sys.stdout.reconfigure(encoding='utf-8')

def _parse_tag66_timestamp(value_bytes):
    try:
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
    except: pass
    return None

def dump_detailed(path, start_h, start_m, end_m):
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    current_ts = None
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        payload = d[val_start:val_end]
        
        if tag == 0x66:
            current_ts = _parse_tag66_timestamp(payload)
        
        if current_ts and current_ts.hour == start_h and start_m <= current_ts.minute <= end_m:
            try:
                text = payload.decode(errors='ignore').strip()
            except:
                text = ""
            
            # Print ALL messages in the first few minutes to see the 'Seed'trade
            if tag == 104 or tag == 0x68:
                print(f"[{current_ts.isoformat()}] MSG: {text}")

        offset += 8 + length

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
print("--- RAW MSG DUMP (00:00 - 00:05 UTC) ---")
dump_detailed(path, 0, 0, 5)
