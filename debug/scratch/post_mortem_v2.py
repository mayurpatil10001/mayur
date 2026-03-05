import struct
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def _is_ghost_fill(note):
    # Simplified version for the audit
    note_u = note.strip()
    if note_u: return False
    return True

def post_mortem(path, limit=100):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records = []
    current_tags = {}
    
    while offset < len(data) - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102: # Start of record
            if current_tags:
                # Flush previous
                records.append(current_tags)
                if len(records) >= limit: break
            current_tags = {"tags": set(), "ts": None}
            # Time decode
            if length == 8:
                tval = struct.unpack('<d', data[val_start:val_end])[0]
                if tval > 30000:
                    base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
                    current_tags["ts"] = (base + datetime.timedelta(days=tval)).astimezone(NY_TZ).isoformat()
        
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

    print(f"Auditing first {len(records)} records:")
    current_net = 0
    limit_val = 3
    for r in records:
        if "side" not in r or "qty" not in r: continue
        
        is_ghost = _is_ghost_fill(r.get("note", ""))
        ts = r.get("ts", "Unknown")
        side = r["side"]
        qty = r["qty"]
        
        if is_ghost:
            print(f"[{ts}] GHOST {side} {qty} | Note: '{r.get('note','')[:30]}...' | SKIPPED")
            continue
            
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
        print(f"[{ts}] {side:<5} {qty:2d} | Pre: {pre:2d} | Allowed: {allowed:2d} | Post: {current_net:2d}{rej_str}")

post_mortem(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
