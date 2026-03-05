import struct
import datetime
import re

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5))

def _parse_tag66_timestamp(val_bytes: bytes) -> datetime.datetime:
    try:
        tval = struct.unpack('<d', val_bytes)[0]
        base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
        return (base + datetime.timedelta(days=tval)).astimezone(NY_TZ)
    except: return None

def trace_audit(path, limit=20):
    with open(path, "rb") as f:
        d = f.read()
    
    offset = 0
    records = []
    
    current_ts_val = 0
    current_ts_str = ""
    
    pending_fill = None
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        val_bytes = d[val_start:val_end]
        
        if tag == 102 or tag == 0x66:
            new_dt = _parse_tag66_timestamp(val_bytes)
            new_ts_val = new_dt.timestamp() if new_dt else 0
            
            if pending_fill and new_ts_val != current_ts_val:
                print(f"FLUSHING: {pending_fill}")
                pending_fill = None
            
            if new_dt:
                current_ts_val = new_ts_val
                current_ts_str = new_dt.isoformat()
            
            print(f"\n--- RECORD at {current_ts_str} (Off {offset:x}) ---")
            
        if tag == 0x6b:
            st = val_bytes.decode(errors='ignore').strip().upper()
            print(f"  TAG 0x6b (Side): '{st}'")
            if any(x in st for x in ["BUY", "LONG"]):
                if not pending_fill: pending_fill = {"acc": "V_SIM16", "side": "BUY", "ts": current_ts_str}
                else: pending_fill["side"] = "BUY"
            elif any(x in st for x in ["SELL", "SHORT"]):
                if not pending_fill: pending_fill = {"acc": "V_SIM16", "side": "SELL", "ts": current_ts_str}
                else: pending_fill["side"] = "SELL"

        if tag == 104:
            msg = val_bytes.decode(errors='ignore').strip()
            print(f"  TAG 104 (Msg): '{msg[:100]}'")
            if "filled" in msg.lower() or "simulation fill" in msg.lower():
                if not pending_fill: pending_fill = {"acc": "V_SIM16", "side": "UNKNOWN", "ts": current_ts_str}
                pending_fill["confirmed"] = True

        if tag in [108, 114, 126]:
            q = 0
            if length == 4: q = struct.unpack('<i', val_bytes)[0]
            elif length == 8: q = struct.unpack('<d', val_bytes)[0]
            print(f"  TAG {tag} (Qty): {q}")
            if pending_fill: pending_fill["qty"] = q

        offset = val_end
        if len(records) > limit: break

trace_audit(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
