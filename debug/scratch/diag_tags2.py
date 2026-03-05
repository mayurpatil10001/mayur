import struct
import datetime
import os
from zoneinfo import ZoneInfo
NY_TZ = ZoneInfo('America/New_York')

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data'
with open(path, 'rb') as f:
    d = f.read()

def parse_time(b):
    if len(b) >= 8:
        val = struct.unpack('<q', b[:8])[0]
        if 0 < val < 1e16:
            return datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=val)
    return None

offset, file_len, cur_dt = 0, len(d), None
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
        dt = parse_time(d[val_start:val_end])
        if dt: cur_dt = dt
        
    if cur_dt:
        ny = cur_dt.astimezone(NY_TZ)
        if (ny.hour == 4 and ny.minute == 5 and ny.second >= 56) or (ny.hour == 4 and ny.minute >= 18 and ny.second >= 0):
            val_bytes = d[val_start:val_end]
            val_str = val_bytes.split(b'\x00')[0].decode(errors='ignore') if b'\x00' in val_bytes else val_bytes.decode(errors='ignore')
            val_dbl = struct.unpack('<d', val_bytes)[0] if length == 8 else 0
            val_int = struct.unpack('<i', val_bytes)[0] if length == 4 else 0
            
            if tag in (126, 127):
                print(f"{ny.strftime('%H:%M:%S.%f')} TAG {tag} int={val_int} dbl={val_dbl} str='{val_str}'")
            elif tag == 104:
                print(f"{ny.strftime('%H:%M:%S.%f')} TAG 104 msg='{val_str}'")
            elif tag == 130 or tag == 0x82:
                print(f"{ny.strftime('%H:%M:%S.%f')} TAG {tag} note='{val_str}'")
            elif tag == 107:
                print(f"{ny.strftime('%H:%M:%S.%f')} TAG 107 type='{val_str}'")
            elif tag == 108:
                print(f"{ny.strftime('%H:%M:%S.%f')} TAG 108 qty='{val_dbl}'")
    offset = val_end
