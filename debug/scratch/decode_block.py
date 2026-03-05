import struct, datetime, os
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
LOG_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

def _parse_tag66_timestamp(value_bytes: bytes):
    if len(value_bytes) < 8: return None
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            base = datetime.datetime(1899, 12, 30)
            dt = base + datetime.timedelta(days=val)
            if 2010 <= dt.year <= 2035: return dt
    except: pass
    try:
        micros = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000000 <= micros <= 2082758400000000:
            return datetime.datetime.fromtimestamp(micros / 1_000_000.0, tz=timezone.utc).replace(tzinfo=None)
    except: pass
    return None

with open(LOG_FILE, 'rb') as f:
    d = f.read()

offset = 0
file_len = len(d)
current_ts_str = ""

print(f"Dumping records for V_SIM16 around 04:05-04:06 NY (09:05-09:06 UTC)")

while offset < file_len - 8:
    tag, length = struct.unpack('<II', d[offset : offset+8])
    val_start = offset + 8
    val_end = val_start + length
    if val_end > file_len: break
    
    if tag == 102 or tag == 0x66: # Time
        dt = _parse_tag66_timestamp(d[val_start:val_end])
        if dt:
            current_ts_str = dt.strftime('%H:%M:%S.%f')
        
    # Check 04:05 NY (or 09:05 UTC)
    if "04:05:" in current_ts_str or "09:05:" in current_ts_str:
        try:
            val = d[val_start:val_end].decode(errors='ignore').strip()
            # Clean up binary garbage
            val = "".join(c for c in val if c.isprintable())
            tag_hex = hex(tag)
            if val:
                print(f"  {current_ts_str} | Tag: {tag:3d} ({tag_hex:4s}) | Len: {length:3d} | Val: {val}")
        except: pass

    offset = val_start + length
