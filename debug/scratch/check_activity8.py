import sys, struct
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
    
    if tag == 102 or tag == 0x66: # new record
        dt = ''
        if length == 8:
            import datetime
            ts = struct.unpack('<d', d[val_start:val_end])[0]
            if ts > 0:
                base = datetime.datetime(1899, 12, 30)
                td = datetime.timedelta(days=ts)
                dt = str(base + td)
                current_tags['dt'] = dt
                if 1:
                    if '09:18:31' in dt or '09:18:46' in dt:
                        print("==== NEW RECORD ====", dt)
                        # dump previous
                        for k, v in current_tags.items():
                            if k != 'dt': print(f"Tag {k}: {v}")
    
    # record values
    if '09:18:31' in current_tags.get('dt', '') or '09:18:46' in current_tags.get('dt', ''):
        if length == 8:
            val = struct.unpack('<d', d[val_start:val_end])[0]
            current_tags[tag] = val
        if length == 4:
            val = struct.unpack('<i', d[val_start:val_end])[0]
            current_tags[tag] = val
        if length == 1:
            val = d[val_start]
            current_tags[tag] = val
            
    offset += 8 + length
