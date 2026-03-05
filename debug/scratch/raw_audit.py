import struct
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

file_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"

with open(file_path, "rb") as f:
    d = f.read()

file_len = len(d)
i = 0
record_count = 0

print(f"File size: {file_len}")

while i < file_len and record_count < 20:
    if i + 4 > file_len: break
    tag = struct.unpack('<I', d[i:i+4])[0]
    i += 4
    length = struct.unpack('<I', d[i:i+4])[0]
    i += 4
    
    val_start = i
    val_end = min(i + length, file_len)
    
    if tag == 102 or tag == 0x66:
        record_count += 1
        print(f"\n--- RECORD {record_count} ---")
        try:
            tval = struct.unpack('<d', d[val_start:val_end])[0]
            base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
            ms = datetime.timedelta(days=tval)
            dt_utc = base + ms
            print(f"  TAG {tag} (Time): {dt_utc.astimezone(NY_TZ)}")
        except Exception as e:
            print(f"  TAG {tag} (Time): unpack failed {e}")
    else:
        if tag in (108, 126): # Quantities
            if length == 8: 
                val = struct.unpack('<d', d[val_start:val_end])[0]
                print(f"  TAG {tag} (Qty): {val}")
        elif tag in (104, 130, 107, 0x6b): # Strings / message
            val = d[val_start:val_end].decode(errors='ignore').strip()
            print(f"  TAG {tag} (String): {val}")
            
    i += length
