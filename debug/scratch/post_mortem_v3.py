import struct
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def _is_ghost_fill(note):
    note_u = note.strip()
    if note_u: return False
    return True

def post_mortem(path, limit=200):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records = []
    current_tags = {"tags": set(), "ts": "Unknown"}
    
    while offset < len(data) - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102 or tag == 0x66: # Start of record
            if "side" in current_tags or "qty" in current_tags:
                records.append(current_tags)
                if len(records) >= limit: break
            
            current_tags = {"tags": {tag}, "ts": "Unknown"}
            if length == 8:
                try:
                    tval = struct.unpack('<d', data[val_start:val_start+8])[0]
                    if 30000 < tval < 80000:
                        base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
                        current_tags["ts"] = (base + datetime.timedelta(days=tval)).astimezone(NY_TZ).isoformat()
                except: pass
        
        if current_tags is not None:
            current_tags["tags"].add(tag)
            if tag in [107, 0x6b]:
                try:
                    st = data[val_start:val_end].decode(errors='ignore').strip().upper()
                    if "BUY" in st or "LONG" in st: current_tags["side"] = "BUY"
                    elif "SELL" in st or "SHORT" in st: current_tags["side"] = "SELL"
                except: pass
            
            if tag in [108, 114, 126]:
                try:
                    if length == 4: current_tags["qty"] = struct.unpack('<i', data[val_start:val_end])[0]
                    elif length == 8: current_tags["qty"] = int(struct.unpack('<d', data[val_start:val_end])[0])
                except: pass
                
            if tag in [0x82, 130, 104, 107]:
                try:
                    note_part = data[val_start:val_end].decode(errors='ignore').strip()
                    current_tags["note"] = (current_tags.get("note", "") + " " + note_part).strip()
                except: pass
            
        offset = val_end

    print(f"Auditing first {len(records)} records:")
    current_net = 0
    limit_val = 3
    for r in records:
        if "side" not in r or "qty" not in r: continue
        
        is_ghost = _is_ghost_fill(r.get("note", ""))
        ts = r.get("ts", "Unknown")
        side = r["side"]
        qty = r["qty"]
        
        # Drift logic
        intended = (current_net + qty) if side == 'BUY' else (current_net - qty)
        rejection = 0
        if side == 'BUY' and intended > limit_val: rejection = qty - (limit_val - current_net)
        elif side == 'SELL' and intended < -limit_val: rejection = qty - (limit_val + current_net)
        
        allowed = qty - (rejection if rejection > 0 else 0)
        pre = current_net
        if side == 'BUY': current_net += allowed
        else: current_net -= allowed
        
        rej_str = f" [REJECTED {rejection}]" if (rejection if rejection > 0 else 0) > 0 else ""
        ghost_str = " GHOST" if is_ghost else ""
        print(f"[{ts}] {side:<5} {qty:2d}{ghost_str} | Pre: {pre:2d} | Allowed: {allowed:2d} | Post: {current_net:2d}{rej_str}")

post_mortem(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
