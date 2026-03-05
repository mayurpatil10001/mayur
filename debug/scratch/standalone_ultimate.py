import sys, os, datetime, glob, struct, re
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_tag66_timestamp
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def _is_ghost_fill_local(acc, note, ts_str):
    acc_u = acc.upper()
    if not acc_u.startswith("V_"): return False
    if note and len(note.strip()) > 0: return False
    return True

def parse_ultimate(fp, account_filter):
    with open(fp, 'rb') as f: d = f.read()
    offset, file_len = 0, len(d)
    current_ts_val, current_ts_str, current_note = 0, "", ""
    raw_candidates = []
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        
        if tag == 102 or tag == 0x66:
            dt = _parse_tag66_timestamp(d[val_start:val_end])
            if dt:
                 current_ts_val, current_ts_str = dt.timestamp(), dt.isoformat()
        
        elif tag == 0x82: # Note
            val = d[val_start:val_end].decode(errors='ignore').strip()
            if val: current_note = val

        elif tag == 104 or tag == 0x68: # Msg
            txt = d[val_start:val_end].decode(errors='ignore').lower()
            if "fill" in txt or "filled" in txt:
                side = "BUY" if any(x in txt for x in ["buy","bought","long"]) else "SELL"
                if any(x in txt for x in ["sell","sold","short"]): side = "SELL"
                px_m = re.search(r"(?:price|at)[:\s]*([\d]+\.?[\d]*)", txt)
                qty_m = re.search(r"(?:qty|size)[:\s]*(\d+)", txt)
                if px_m:
                    p_val = float(px_m.group(1))
                    qty = int(qty_m.group(1)) if qty_m else 1
                    raw_candidates.append({
                        "timestamp": current_ts_str, "ts_val": current_ts_val,
                        "side": side, "price": p_val, "quantity": qty,
                        "note": current_note, "msgtxt": txt, "file_path": fp
                    })
        offset = val_start + length
    return raw_candidates

PATHS = [r"D:\SierraChart_Simulated_Feed\TradeActivityLogs", r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"]
# Focus ONLY on Dec 18 UTC for speed
target_dates = ["2025-12-18"]
all_fills = []

for p in PATHS:
    for d in target_dates:
        f = os.path.join(p, f"TradeActivityLog_{d}_UTC.V_sim16.data")
        if os.path.exists(f): all_fills.extend(parse_ultimate(f, ["V_SIM16"]))

all_unique_fills = {}
for f in all_fills:
    is_ghost = _is_ghost_fill_local("V_SIM16", f.get('note',''), f.get('timestamp'))
    f['suggests_ghost'] = is_ghost
    ts_bucket = round(f['ts_val'] * 10) / 10.0 # 100ms
    instance = os.path.dirname(f['file_path'])
    key = (instance, f['side'], f['price'], f['quantity'], ts_bucket, f['msgtxt'])
    if key not in all_unique_fills:
        all_unique_fills[key] = f
    elif all_unique_fills[key]['suggests_ghost'] and not is_ghost:
        all_unique_fills[key] = f

final_fills = sorted([f for f in all_unique_fills.values() if not f['suggests_ghost']], key=lambda x: x['ts_val'])

print(f"\n--- DEC 18 UTC RAW FILL TRACE (n={len(final_fills)}) ---")
net = 0
for i, f in enumerate(final_fills):
    side, qty = f.get('side',''), f.get('quantity', 0)
    if side == 'BUY': net += qty
    else: net -= qty
    
    dt = datetime.datetime.fromisoformat(f['timestamp']).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    
    # Print a few to prove it's working
    if i < 10 or (dt.hour == 2 and 26 <= dt.minute <= 27) or i > len(final_fills) - 10:
        found_target = " [TARGET 02:26] " if (dt.hour == 2 and 26 <= dt.minute <= 27) else ""
        print(f"  {dt.strftime('%m/%d %H:%M:%S')} | {side:5s} {qty:2d} | Net: {net:+d} | Note: {f['note'][:30]}{found_target}")

print(f"\nFinal net position for Dec 18 UTC file: {net:+d}")
