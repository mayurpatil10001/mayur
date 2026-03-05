import struct
import datetime
import re

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def _parse_tag66_timestamp(val_bytes: bytes) -> datetime.datetime:
    try:
        tval = struct.unpack('<d', val_bytes)[0]
        base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
        return (base + datetime.timedelta(days=tval)).astimezone(NY_TZ)
    except: return None

def trace_audit(path, target_time="00:07:29"):
    with open(path, "rb") as f:
        d = f.read()
    
    offset = 0
    current_ts_str = ""
    current_ts_val = 0
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        val_bytes = d[val_start:val_end]
        
        if tag == 102 or tag == 0x66:
            new_dt = _parse_tag66_timestamp(val_bytes)
            if new_dt:
                current_ts_str = new_dt.isoformat()
            
        if target_time in current_ts_str:
            print(f"[{current_ts_str}] Off {offset:x} | Tag {tag}: {val_bytes.hex()[:40]}...")
            if tag == 104 or tag == 0x68:
                print(f"  Msg: '{val_bytes.decode(errors='ignore')}'")
            if tag == 0x6b:
                print(f"  Side: '{val_bytes.decode(errors='ignore')}'")

        offset = val_end

trace_audit(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
