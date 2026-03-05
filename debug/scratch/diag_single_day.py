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

def extract_fills_deep(file_path):
    with open(file_path, 'rb') as f:
        d = f.read()
    
    offset, file_len = 0, len(d)
    
    # temp state
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
        
        if tag == 102 or tag == 0x66: # new record
            if cur_dt and cur_record:
                if 'qty' in cur_record and cur_record.get('qty', 0) > 0:
                    records.append(cur_record)
            cur_record = {}
            dt = parse_time(d[val_start:val_end])
            if dt: 
                cur_dt = dt
                cur_record['dt'] = cur_dt
                cur_record['ts'] = cur_dt.timestamp()
                cur_record['ny'] = cur_dt.astimezone(NY_TZ)
                
        if cur_dt:
            val_bytes = d[val_start:val_end]
            if length == 8:
                val_dbl = struct.unpack('<d', val_bytes)[0]
            else:
                val_dbl = 0
            if length == 4:
                val_int = struct.unpack('<i', val_bytes)[0]
            else:
                val_int = 0
                
            if b'\x00' in val_bytes:
                val_str = val_bytes.split(b'\x00')[0].decode(errors='ignore')
            else:
                val_str = val_bytes.decode(errors='ignore')

            if tag == 104: cur_record['msg'] = val_str
            elif tag == 130 or tag == 0x82: cur_record['note'] = val_str
            elif tag == 107: cur_record['type'] = val_str
            elif tag == 108: cur_record['qty'] = val_dbl
            elif tag == 109: cur_record['side'] = 'BUY' if val_str in ('1', '\x01') else 'SELL'
            elif tag == 110: cur_record['px'] = val_dbl
            elif tag == 126: cur_record['tag126'] = val_int
            
        offset = val_end
        
    if cur_dt and cur_record and cur_record.get('qty', 0) > 0:
        records.append(cur_record)
        
    # group by exact timestamp to deduplicate
    # In SC, one transaction has multiple records for the same time. The fill is the one with highest tag count / or we just group by (ts, side, qty, px)
    unique = {}
    for r in records:
        sig = (round(r['ts']*2)/2.0, r.get('side'), r.get('qty'), r.get('px'))
        if sig not in unique:
            unique[sig] = r
        else:
            # merge
            for k, v in r.items():
                if k not in unique[sig] or not unique[sig][k]:
                    unique[sig][k] = v
    
    fills = list(unique.values())
    fills.sort(key=lambda x: x['ts'])
    return fills

fills = extract_fills_deep(path)

out = []
def p(s=""): out.append(str(s))

p(f"Extracted {len(fills)} unique fills")
p("Finding ghosts (no tag 0x82 note, or note with no alphanumeric)")

ghosts = []
valid = []
for f in fills:
    note = f.get('note', '').strip()
    import re
    is_ghost = not re.search(r'[A-Za-z0-9]', note)
    if is_ghost:
        ghosts.append(f)
    else:
        valid.append(f)

p(f"Ghosts: {len(ghosts)} fills")
for i, g in enumerate(ghosts):
    t = g['ny'].strftime('%H:%M:%S')
    p(f"  [{i}] NY={t} {g.get('side','?'):4s} qty={g.get('qty',0)} px={g.get('px',0):.2f} tag126={g.get('tag126', '?')} note='{g.get('note','')}' msg='{g.get('msg','')}'")

p("\nChecking Session Balance (NY 18:00 to 17:00)")
session_fills = []
# V_SIM16 2025-12-18 file actually has fills spanning multiple days maybe? No, just one calendar day. 
# 18:00 to 17:00:
# For Dec 18 trading session: starts Dec 17 18:00:00, ends Dec 18 17:00:00
sess_buys_all, sess_sells_all = 0, 0
sess_buys_val, sess_sells_val = 0, 0

for f in fills:
    ny = f['ny']
    # Check if in Dec 18 session
    # Session is >= Dec 17 18:00 and < Dec 18 17:00
    is_session = False
    if ny.date() == datetime.date(2025, 12, 17) and ny.hour >= 18: is_session = True
    if ny.date() == datetime.date(2025, 12, 18) and ny.hour < 17: is_session = True
    
    if is_session:
        q = f.get('qty', 0)
        s = f.get('side', 'BUY')
        if s == 'BUY': sess_buys_all += q
        else: sess_sells_all += q
            
        note = f.get('note', '').strip()
        is_ghost = not re.search(r'[A-Za-z0-9]', note)
        if not is_ghost:
            if s == 'BUY': sess_buys_val += q
            else: sess_sells_val += q

p(f"Session Dec 18 (ALL fills, WITH 'ghosts'): Buys={sess_buys_all}, Sells={sess_sells_all}, Net={sess_buys_all - sess_sells_all}")
p(f"Session Dec 18 (VALID only, NO 'ghosts'): Buys={sess_buys_val}, Sells={sess_sells_val}, Net={sess_buys_val - sess_sells_val}")

p("\nWhat happens right before/after the ghost 04:05:56 (BUY 2)?")
# Let's track Tag 126
for i, f in enumerate(fills):
    if f.get('ny').hour == 4 and f.get('ny').minute == 5 and f.get('ny').second == 56:
        p(f"--- Fills around 04:05 ---")
        for j in range(max(0, i-3), min(len(fills), i+4)):
            fj = fills[j]
            t = fj['ny'].strftime('%H:%M:%S')
            is_g = "" if re.search(r'[A-Za-z0-9]', fj.get('note', '')) else "[G]"
            p(f"  {is_g:3s} {t} {fj.get('side','?'):4s} qty={fj.get('qty',0)} px={fj.get('px',0):.2f} tag126={fj.get('tag126', '?')} note='{fj.get('note','')}'")

p("\nWhat happens right before/after the EXITS at 04:46-04:54?")
for i, f in enumerate(fills):
    if f.get('ny').hour == 4 and f.get('ny').minute == 46 and f.get('ny').second == 8:
        p(f"--- Fills around 04:46 ---")
        for j in range(max(0, i-3), min(len(fills), i+6)):
            fj = fills[j]
            t = fj['ny'].strftime('%H:%M:%S')
            is_g = "" if re.search(r'[A-Za-z0-9]', fj.get('note', '')) else "[G]"
            p(f"  {is_g:3s} {t} {fj.get('side','?'):4s} qty={fj.get('qty',0)} px={fj.get('px',0):.2f} tag126={fj.get('tag126', '?')} note='{fj.get('note','')}'")
            
with open("diag_single.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
