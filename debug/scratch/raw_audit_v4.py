import struct, datetime, re

d = open(r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data', 'rb').read()

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

records = []
i = 0
file_len = len(d)
current_ts = None
current_msg = ''
current_qty = 0
current_side = ''

while i < file_len:
    if i + 8 > file_len: break
    tag = struct.unpack('<I', d[i:i+4])[0]
    i += 4
    length = struct.unpack('<I', d[i:i+4])[0]
    i += 4
    
    val_start = i
    val_end = min(val_start + length, file_len)
    i = val_end
    
    if tag == 102 or tag == 0x66:
        if current_msg and current_ts and current_ts.hour == 8 and current_ts.minute <= 6:
            print(f'{current_ts.strftime("%H:%M:%S")} | Side={current_side} | Qty={current_qty} | Msg={current_msg[:120]}')
        
        try:
            tval = struct.unpack('<d', d[val_start:val_end])[0]
            current_ts = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=tval)
        except: pass
        current_msg = ''
        current_qty = 0
        current_side = ''
    else:
        if tag == 104 or tag == 130:
            current_msg += d[val_start:val_end].decode(errors='ignore').strip()
        elif tag == 108 or tag == 126:
            if length == 8: current_qty = struct.unpack('<d', d[val_start:val_end])[0]
        elif tag == 0x6b:
            current_side = d[val_start:val_end].decode(errors='ignore').strip()

if current_msg and current_ts and current_ts.hour == 8 and current_ts.minute <= 6:
    print(f'{current_ts.strftime("%H:%M:%S")} | Side={current_side} | Qty={current_qty} | Msg={current_msg[:120]}')
