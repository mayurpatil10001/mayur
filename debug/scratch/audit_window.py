import struct
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def _parse_tag66_timestamp(val_bytes: bytes) -> datetime.datetime:
    try:
        tval = struct.unpack('<d', val_bytes)[0]
        base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
        ms = datetime.timedelta(days=tval)
        dt_utc = base + ms
        return dt_utc.astimezone(NY_TZ)
    except:
        return None

def analyze_time_window(file_path: str):
    with open(file_path, "rb") as f:
        d = f.read()

    file_len = len(d)
    i = 0
    records = []
    
    current_rec = {}
    current_ts = None
    
    while i < file_len and len(records) < 50:
        if i + 4 > file_len: break
        tag = struct.unpack('<I', d[i:i+4])[0]
        i += 4
        if i + 4 > file_len: break
        length = struct.unpack('<I', d[i:i+4])[0]
        i += 4
        
        val_start = i
        val_end = i + length
        i += length
        
        if tag == 102 or tag == 0x66:
            if current_rec and current_ts:
                records.append((current_ts, dict(current_rec)))
                    
            dt = _parse_tag66_timestamp(d[val_start:val_end])
            current_ts = dt
            if current_ts:
                if current_ts.year < 2000:
                    current_ts = None
            current_rec = {"tags": []}
            continue
            
        if current_ts:
            val = None
            if tag in (108, 126): # Quantities
                if length == 8: val = struct.unpack('<d', d[val_start:val_end])[0]
            elif tag in (104, 130, 107, 0x6b): # Strings / message
                val = d[val_start:val_end].decode(errors='ignore').strip()
            if val is not None:
                current_rec["tags"].append((tag, val))
                
    if current_rec and current_ts and len(records) < 50:
        records.append((current_ts, dict(current_rec)))

    for ts, rec in records:
        print(f"\n--- {ts.isoformat()} ---")
        for tag, val in rec["tags"]:
            print(f"  TAG {tag}: {val}")

analyze_time_window(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
