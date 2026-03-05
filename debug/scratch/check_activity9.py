import sys, struct, datetime
sys.path.insert(0, 'C:/SierraChart/SC results WF')

fpath = 'D:/SierraChart_Simulated_Feed/TradeActivityLogs/TradeActivityLog_2025-12-18_UTC.V_sim16.data'
with open(fpath, 'rb') as f:
    d = f.read()

offset = 0
file_len = len(d)
current_tags = {}

while offset < file_len - 8:
    tag, length = struct.unpack('<II', d[offset : offset+8])
    if tag == 0 or tag > 512 or length > 65536: 
        offset += 1
        continue
    
    val_start = offset + 8
    val_end = val_start + length
    
    if tag == 102 or tag == 0x66:
        dt = ''
        if length == 8:
            ts = struct.unpack('<d', d[val_start:val_end])[0]
            if ts > 0:
                base = datetime.datetime(1899, 12, 30)
                td = datetime.timedelta(days=ts)
                dt = str(base + td)
                current_tags['dt'] = dt
                if '09:18:46.901' in dt or '09:18:31.102' in dt:
                    print("==== NEW RECORD ====", dt)
    
    if '09:18:46.901' in current_tags.get('dt', '') or '09:18:31.102' in current_tags.get('dt', ''):
        if tag == 125:
            val = struct.unpack('<d', d[val_start:val_end])[0]
            print(f"  Tag 125 [PositionQuantity]: {val}")
        if tag == 104 or tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore')
            print(f"  Tag {tag} [Msg]: {s[:30]}")
        if tag == 111:
            print(f"  Tag 111 [ActivityType]: {struct.unpack('<B', d[val_start:val_end])[0]}")
            
    offset += 8 + length
