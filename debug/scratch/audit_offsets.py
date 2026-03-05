import struct
from datetime import datetime, timedelta, timezone

def audit_offsets(path, limit=500):
    with open(path, "rb") as f:
        d = f.read()
    
    offset = 0
    ts_count = 0
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        
        if tag == 102 or tag == 0x66:
            tval = struct.unpack('<d', d[val_start:val_start+8])[0]
            dt = datetime(1899, 12, 30, tzinfo=timezone.utc) + timedelta(days=tval)
            print(f"{offset:06x}: {dt.isoformat()} (val: {tval})")
            ts_count += 1
            if ts_count >= limit: break
            
        offset = val_end

audit_offsets(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
