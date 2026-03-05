import struct
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def post_mortem(path, start_offset=0x110000, limit=200):
    with open(path, "rb") as f:
        f.seek(start_offset)
        data = f.read()
    
    offset = 0
    records = []
    current_tags = {"tags": set(), "ts": "Unknown"}
    
    while offset < len(data) - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        # In SC binary, records don't always start with Tag 102. 
        # But fills usually follow a pattern.
        # Let's use Tag 103 (Symbol) or Tag 104 as a potential separator if 102 is missing?
        # Actually, let's just collect everything and group by Tag 104 "Fill" presence.
        
        if tag == 102 or tag == 0x66: # Start of record
            if "side" in current_tags or "qty" in current_tags:
                records.append(current_tags)
                if len(records) >= limit: break
            current_tags = {"tags": {tag}, "ts": "Unknown"}
            if length == 8:
                try:
                    tval = struct.unpack('<d', data[val_start:val_start+8])[0]
                    if tval > 30000:
                        base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
                        current_tags["ts"] = (base + datetime.timedelta(days=tval)).astimezone(NY_TZ).isoformat()
                except: pass
        
        if current_tags is not None:
            current_tags["tags"].add(tag)
            if tag in [107, 0x6b]:
                st = data[val_start:val_end].decode(errors='ignore').strip().upper()
                if "BUY" in st or "LONG" in st: current_tags["side"] = "BUY"
                elif "SELL" in st or "SHORT" in st: current_tags["side"] = "SELL"
            
            if tag in [108, 114, 126]:
                if length == 4: current_tags["qty"] = struct.unpack('<i', data[val_start:val_end])[0]
                elif length == 8: current_tags["qty"] = int(struct.unpack('<d', data[val_start:val_end])[0])
                
            if tag in [0x82, 130, 104, 107]:
                note_part = data[val_start:val_end].decode(errors='ignore').strip()
                current_tags["note"] = (current_tags.get("note", "") + " " + note_part).strip()
            
        offset = val_end

    print(f"Auditing results for {len(records)} records from offset {start_offset:x}:")
    current_net = 0
    limit_val = 3
    for r in records:
        if "side" not in r or "qty" not in r: continue
        ts = r.get("ts", "Unknown")
        side = r["side"]
        qty = r["qty"]
        note = r.get("note", "")
        is_ghost = not bool(note.strip())
        
        intended = (current_net + qty) if side == 'BUY' else (current_net - qty)
        rej = 0
        if side == 'BUY' and intended > limit_val: rej = qty - (limit_val - current_net)
        elif side == 'SELL' and intended < -limit_val: rej = qty - (limit_val + current_net)
        
        allowed = qty - (rej if rej > 0 else 0)
        pre = current_net
        if side == 'BUY': current_net += allowed
        else: current_net -= allowed
        
        rej_str = f" [REJECTED {rej}]" if (rej if rej > 0 else 0) > 0 else ""
        ghost_str = " (GHOST)" if is_ghost else ""
        print(f"[{ts}] {side:<5} {qty:2d}{ghost_str}{rej_str:12} | Pre: {pre:2d} | Post: {current_net:2d} | Note: '{note[:30]}...'")

post_mortem(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
