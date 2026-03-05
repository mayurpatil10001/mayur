import struct

def search_quantities(path, limit=10):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records = []
    while offset < len(data) - 8 and len(records) < limit:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102:
            if any(t in [108, 114, 126] for t, v in records):
                print(f"\n--- RECORD ---")
                for t, v in records:
                    if t in [108, 114, 126]:
                        val = 0
                        if len(v) == 4: val = struct.unpack('<i', v)[0]
                        elif len(v) == 8: val = struct.unpack('<d', v)[0]
                        print(f"  Tag {t} | Val: {val}")
            records = []
            
        if val_end > len(data): break
        records.append((tag, data[val_start:val_end]))
        offset = val_end

search_quantities(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
