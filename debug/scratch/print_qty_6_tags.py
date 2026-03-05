import struct, datetime, re

d = open(r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data', 'rb').read()

file_len = len(d)
i = 0
current_ts = None
current_tags = []

while i < file_len:
    if i + 8 > file_len: break
    tag = struct.unpack('<I', d[i:i+4])[0]
    length = struct.unpack('<I', d[i+4:i+8])[0]
    val_start = i + 8
    val_end = min(val_start + length, file_len)
    
    if tag == 102 or tag == 0x66:
        has_qty_6 = any(t in (108,126) and v == 6.0 for t, _, v in current_tags)
        if current_ts and has_qty_6:
            print(f"\n--- {current_ts} ---")
            for t, lg, v in current_tags:
                print(f"TAG {t} (Len {lg}): {v}")
            break
            
        try:
            tval = struct.unpack('<d', d[val_start:val_end])[0]
            current_ts = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=tval)
        except: pass
        current_tags = []
        
    else:
        v = None
        if tag in (108, 126) and length == 8:
            v = struct.unpack('<d', d[val_start:val_end])[0]
        elif (tag in (108, 126) or tag == 114) and length == 4:
            v = struct.unpack('<i', d[val_start:val_end])[0]
        elif tag in (104, 130, 107, 0x6b, 0x82):
            v = d[val_start:val_end].decode(errors='ignore').strip()
        current_tags.append((tag, length, v))
        
    i += 8 + length
