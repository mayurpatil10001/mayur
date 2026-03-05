import struct
import datetime
import os
from zoneinfo import ZoneInfo
NY_TZ = ZoneInfo('America/New_York')

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data'

def parse_time(b):
    if len(b) >= 8:
        val = struct.unpack('<q', b[:8])[0]
        if 0 < val < 1e16:
            return datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=val)
    return None

def extract_fills(file_path):
    with open(file_path, 'rb') as f:
        d = f.read()
    
    offset, file_len = 0, len(d)
    
    cur_dt = None
    cur_record = {}
    records = []
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        if tag == 0 or tag > 512 or length > 65536:
            nxt = d.find(b'\x66\x00\x00\x00', offset+1)
            if nxt == -1: break
            offset = nxt
            continue
            
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        
        if tag == 102 or tag == 0x66: 
            if cur_dt and cur_record:
                if 'qty' in cur_record and cur_record.get('qty', 0) > 0:
                    records.append(cur_record)
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
            if length == 4: val_int = struct.unpack('<i', val_bytes)[0]
            else: val_int = 0
                
            if b'\x00' in val_bytes: val_str = val_bytes.split(b'\x00')[0].decode(errors='ignore')
            else: val_str = val_bytes.decode(errors='ignore')

            if tag == 104: cur_record['msg'] = val_str
            elif tag == 130 or tag == 0x82: cur_record['note'] = val_str
            elif tag == 108: cur_record['qty'] = val_dbl
            elif tag == 109: cur_record['side'] = 'BUY' if val_str in ('1', '\x01') else 'SELL'
            elif tag == 110: cur_record['px'] = val_dbl
            elif tag == 126: cur_record['tag126'] = val_int
            
        offset = val_end
        
    if cur_dt and cur_record and cur_record.get('qty', 0) > 0:
        records.append(cur_record)
        
    unique = {}
    for r in records:
        sig = (round(r['ts']*2)/2.0, r.get('side'), r.get('qty'), r.get('px'))
        if sig not in unique:
            unique[sig] = r
        else:
            for k, v in r.items():
                if k not in unique[sig] or not unique[sig][k]:
                    unique[sig][k] = v
    
    fills = list(unique.values())
    fills.sort(key=lambda x: x['ts'])
    return fills

fills = extract_fills(path)

out = []
def p(s=""): out.append(str(s))

p("=== EXACT SESSION BALANCE FOR DEC 18 ===")
p("Session Window: 2025-12-17 18:00:00 to 2025-12-18 17:00:00 (NY Time)")

buys, sells = 0, 0
buys_ghost, sells_ghost = 0, 0
buys_noghost, sells_noghost = 0, 0

session_start = NY_TZ.localize(datetime.datetime(2025, 12, 17, 18, 0, 0))
session_end = NY_TZ.localize(datetime.datetime(2025, 12, 18, 17, 0, 0))

import re
for f in fills:
    ny = f['ny']
    if session_start <= ny < session_end:
        q = int(f.get('qty', 0))
        s = f.get('side')
        
        if s == 'BUY': buys += q
        else: sells += q
        
        note = f.get('note', '').strip()
        is_ghost = not re.search(r'[A-Za-z0-9]', note)
        
        if is_ghost:
            if s == 'BUY': buys_ghost += q
            else: sells_ghost += q
        else:
            if s == 'BUY': buys_noghost += q
            else: sells_noghost += q

p(f"All Fills in Window    -> Buys: {buys}, Sells: {sells}, Net: {buys - sells}")
p(f"Valid Fills ONLY       -> Buys: {buys_noghost}, Sells: {sells_noghost}, Net: {buys_noghost - sells_noghost}")
p(f"Ghost Fills ONLY       -> Buys: {buys_ghost}, Sells: {sells_ghost}, Net: {buys_ghost - sells_ghost}")

# Now let's calculate exact balance from START to END of the actual file (since Sierra might split files at 17:00 or 00:00 UTC)
p("\n=== OVERALL FILE BALANCE ===")
file_buys, file_sells = 0, 0
file_buys_noghost, file_sells_noghost = 0, 0

for f in fills:
    q = int(f.get('qty', 0))
    s = f.get('side')
    
    if s == 'BUY': file_buys += q
    else: file_sells += q
    
    note = f.get('note', '').strip()
    is_ghost = not re.search(r'[A-Za-z0-9]', note)
    
    if not is_ghost:
        if s == 'BUY': file_buys_noghost += q
        else: file_sells_noghost += q

p(f"Total Fills in File    -> Buys: {file_buys}, Sells: {file_sells}, Net: {file_buys - file_sells}")
p(f"Total Valid Fills ONLY -> Buys: {file_buys_noghost}, Sells: {file_sells_noghost}, Net: {file_buys_noghost - file_sells_noghost}")

with open("diag_balance.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
