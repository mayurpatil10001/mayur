import struct
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def deep_audit_ts(path, target_ts="2026-02-25T03:30:56.354859"):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records = []
    current_record = []
    
    while offset < len(data) - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102 or tag == 0x66:
            if current_record:
                # Check TS
                tval = struct.unpack('<d', current_record[0][1])[0]
                base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
                ts = (base + datetime.timedelta(days=tval)).astimezone(NY_TZ).isoformat()
                
                if target_ts in ts:
                    print(f"\n--- RECORD at {ts} (Offset {offset:x}) ---")
                    for t, v, l in current_record:
                        disp = ""
                        if l == 4: disp = f"Int32: {struct.unpack('<i', v)[0]}"
                        elif l == 8: 
                            try: disp = f"Double: {struct.unpack('<d', v)[0]}"
                            except: disp = f"Hex: {v.hex()}"
                        else: disp = f"Str: {v.decode(errors='ignore').strip()[:100]}"
                        print(f"  Tag {t:3d} (0x{t:02x}) | Len {l} | {disp}")
            
            current_record = []
            
        if val_end > len(data): break
        current_record.append((tag, data[val_start:val_end], length))
        offset = val_end

deep_audit_ts(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
