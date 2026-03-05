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

def check_file(path):
    if not os.path.exists(path):
        return
        
    with open(path, 'rb') as f:
        d = f.read(10000) # Check the very start
    
    offset = 0
    file_len = len(d)
    current_ts = None
    
    print(f"\n--- Checking {os.path.basename(path)} ---")
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        payload = d[val_start:val_end]
        
        if tag == 0x66:
            current_ts = _parse_tag66_timestamp(payload)
        
        if tag == 104 and current_ts:
            text = payload.decode(errors='ignore').strip()
            if "position" in text.lower() or "evaluator" in text.lower():
                print(f"[{current_ts.isoformat()}] {text[:100]}")

        offset += 8 + length

# Check a few different files and dates
files = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data",
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-17_UTC.V_sim16.data",
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.3Q_sim13.data",
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim7.data"
]

for f in files:
    check_file(f)
