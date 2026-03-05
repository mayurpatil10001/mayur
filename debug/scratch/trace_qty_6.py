import struct, datetime, re

d = open(r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data', 'rb').read()

file_len = len(d)
i = 0
current_ts = None
pending_fill = None

while i < file_len:
    if i + 8 > file_len: break
    tag = struct.unpack('<I', d[i:i+4])[0]
    length = struct.unpack('<I', d[i+4:i+8])[0]
    val_start = i + 8
    val_end = min(val_start + length, file_len)
    
    if tag == 102 or tag == 0x66:
        if pending_fill and pending_fill.get('quantity') == 6:
            print(f"FOUND QTY 6 at {current_ts}!")
            print(pending_fill)
            break
            
        try:
            tval = struct.unpack('<d', d[val_start:val_end])[0]
            current_ts = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=tval)
        except: pass
        
    elif tag == 104 or tag == 0x68:
        s = d[val_start:val_end].decode(errors='ignore').strip()
        s_lower = s.lower()
        
        if ("trade simulation fill" in s_lower or "fill: " in s_lower or "(filled)" in s_lower) and "updated internal position" not in s_lower:
            qty = 1
            qm = re.search(r"(?:qty|quantity|size|fill qty|q:|vol)\s*:?\s*(\d+)", s_lower)
            if qm: qty = int(qm.group(1))
            
            if not pending_fill:
                pending_fill = {'quantity': qty, 'from_msg': True, 'log': [(current_ts, 'create', qty, s)]}
            else:
                old_qty = pending_fill['quantity']
                if qty > pending_fill['quantity']: 
                    pending_fill['quantity'] = qty
                pending_fill['log'].append((current_ts, 'update_msg', qty, old_qty, s))
                
    elif tag in [108, 114, 126] and pending_fill:
        try:
            v = struct.unpack('<i', d[val_start:val_start+4])[0] if length == 4 else int(struct.unpack('<d', d[val_start:val_start+8])[0])
            old_qty = pending_fill['quantity']
            if 0 < v < 500: 
                pending_fill['quantity'] = max(pending_fill.get('quantity', 0), v)
            pending_fill['log'].append((current_ts, 'update_tag', v, old_qty))
        except: pass

    i += 8 + length
