import struct, datetime, os, re
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
LOG_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-01_UTC.V_sim16.data"

def _parse_tag66_timestamp(value_bytes: bytes):
    if len(value_bytes) < 8: return None
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(days=val)
    except: pass
    try:
        micros = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000000 <= micros <= 2082758400000000:
            return datetime.datetime.fromtimestamp(micros / 1_000_000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
    except: pass
    return None

with open(LOG_FILE, 'rb') as f:
    d = f.read()

offset = 0
file_len = len(d)
current_ts_str = ""
count = 0

print(f"Dumping first 1000 records from {os.path.basename(LOG_FILE)}")

while offset < file_len - 8 and count < 1000:
    tag, length = struct.unpack('<II', d[offset : offset+8])
    val_start = offset + 8
    val_end = val_start + length
    if val_end > file_len: break
    
    if tag == 102 or tag == 0x66: # Time
        dt = _parse_tag66_timestamp(d[val_start:val_end])
        if dt: 
            current_ts_str = dt.isoformat()
            
    # Print everything related to V_SIM16 messages
    if tag == 104 or tag == 130 or tag == 0x68:
        try:
            val = d[val_start:val_end].decode(errors='ignore').strip()
            # Clean up binary garbage
            val = "".join(c for c in val if c.isprintable())
            if val:
                print(f"  {current_ts_str} | Tag:{tag:3d} | Val: {val[:120]}")
                count += 1
        except: pass

    offset = val_start + length
