import struct
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo('America/New_York')
path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data'

def parse_time(b):
    if len(b) >= 8:
        val = struct.unpack('<q', b[:8])[0]
        if 0 < val < 1e16:
            return datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=val)
    return None

def extract_all_messages(file_path):
    with open(file_path, 'rb') as f: d = f.read()
    offset, file_len = 0, len(d)
    cur_dt = None
    cur_record = {}
    records = []
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        if tag == 0 or length > 65536:
            nxt = d.find(b'\x66\x00\x00\x00', offset+1)
            if nxt == -1: break
            offset = nxt
            continue
            
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        
        if tag == 102 or tag == 0x66: 
            if cur_dt: records.append(cur_record)
            cur_record = {}
            dt = parse_time(d[val_start:val_end])
            if dt: 
                cur_dt = dt
                cur_record['ts'] = cur_dt.timestamp()
                cur_record['ny'] = cur_dt.astimezone(NY_TZ)
                
        if cur_dt:
            val_bytes = d[val_start:val_end]
            if length == 8: val_dbl = struct.unpack('<d', val_bytes)[0]
            else: val_dbl = 0
                
            if b'\x00' in val_bytes: val_str = val_bytes.split(b'\x00')[0].decode(errors='ignore')
            else: val_str = val_bytes.decode(errors='ignore')

            if tag == 104: cur_record['msg'] = val_str
            elif tag == 130 or tag == 0x82: cur_record['note'] = val_str
            elif tag == 108: cur_record['qty'] = int(val_dbl)
            elif tag == 109: cur_record['side'] = 'BUY' if val_str in ('1', '\x01') else 'SELL'
            elif tag == 110: cur_record['px'] = val_dbl
            elif tag == 126: cur_record['tag126'] = int(struct.unpack('<i', val_bytes)[0]) if length == 4 else 0
            
        offset = val_end
        
    if cur_dt: records.append(cur_record)
        
    unique = {}
    for r in records:
        sig = (round(r['ts']*2)/2.0, r.get('side'), r.get('qty'), r.get('px'), r.get('msg', '')[:10])
        if sig not in unique: unique[sig] = r
        else:
            for k, v in r.items():
                if k not in unique[sig] or not unique[sig][k]: unique[sig][k] = v
    
    fills = list(unique.values())
    fills.sort(key=lambda x: x['ts'])
    return fills

all_recs = extract_all_messages(path)

out = []
def p(s=''): out.append(str(s))

p(f"Time         | S | Qty | Px       | Msg")
p('-' * 90)

for f in all_recs:
    ny = f['ny']
    # 02:18 to 04:09 NY time
    if ny.date().day == 18:
        if (ny.hour == 2 and ny.minute >= 18) or ny.hour == 3 or (ny.hour == 4 and ny.minute <= 9):
            qty = f.get('qty', 0)
            side = 'B' if f.get('side') == 'BUY' else 'S'
            msg = f.get('msg', '') or ''
            msg = msg.strip()[:60]
            px = f.get('px', 0)
            
            p(f"{ny.strftime('%H:%M:%S')} | {side:1} | {qty:3} | {px:8.2f} | {msg:60}")

with open('diag_all_msgs.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
