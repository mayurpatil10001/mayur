import struct

def investigate_duplicates(path, target_ts="2026-02-25T03:41:53"):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records = []
    while offset < len(data) - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102: # Time
            parsed_dt = None
            if length == 8:
                # SC Binary Time: 8-byte double representing days since 1899-12-30? 
                # Or just Unix timestamp double?
                # Actually, our parser uses _parse_tag66_timestamp which handles various types.
                pass
            
            # For simplicity, let's just search for the bytes in the file if we knew them, 
            # or just continue parsing and look for the TS later.
            pass
        
        offset = val_end

# Instead of full parse, let's search for the text "03:41:53" if it was there? No, it's binary.
# Let's just dump 500 records and filter.

def dump_all_records(path, limit=5000):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records_count = 0
    current_record = []
    
    while offset < len(data) - 8 and records_count < limit:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102:
            if current_record:
                # Print record if it's interesting (e.g. contains 03:41:53)
                is_target = False
                ts_str = ""
                for t, v, l in current_record:
                    if t == 102:
                        from datetime import datetime, timezone
                        try:
                            if l == 8:
                                tval = struct.unpack('<d', v)[0]
                                if tval > 1000000000: # Unix
                                    dt = datetime.fromtimestamp(tval, tz=timezone.utc)
                                    ts_str = dt.isoformat()
                                    if "03:41:53" in ts_str: is_target = True
                        except: pass
                
                if is_target:
                    print(f"\n--- RECORD at {ts_str} ---")
                    for t, v, l in current_record:
                        if t in [100, 104, 107, 108, 114, 126, 130]:
                            val_disp = ""
                            if l == 4: val_disp = f"Int32: {struct.unpack('<i', v)[0]}"
                            elif l == 8: val_disp = f"Float64: {struct.unpack('<d', v)[0]}"
                            else: val_disp = f"Str: {v.decode(errors='ignore')[:50]}"
                            print(f"  Tag {t:3d} (0x{t:02x}) | Len {l} | {val_disp}")
                
                records_count += 1
            current_record = []
            
        if val_end > len(data): break
        current_record.append((tag, data[val_start:val_end], length))
        offset = val_end

dump_all_records(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
