"""
Parse the V_SIM16 Dec 18 binary log directly.
Verify: note rate, fills around 02:26 and 04:05, whether ghost is detectable.
"""
import struct
import re
import datetime
import sys
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

LOG_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

def parse_tag66_timestamp(value_bytes):
    if len(value_bytes) < 8:
        return None
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            base = datetime.datetime(1899, 12, 30)
            dt = base + datetime.timedelta(days=val)
            if 2010 <= dt.year <= 2035:
                return dt  # wall-clock/local
    except: pass
    try:
        micros = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000000 <= micros <= 2082758400000000:
            return datetime.datetime.fromtimestamp(micros / 1_000_000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
        if 3400000000000000 <= micros <= 4500000000000000:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(microseconds=micros)
    except: pass
    try:
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=datetime.timezone.utc).replace(tzinfo=None)
    except: pass
    return None

with open(LOG_FILE, "rb") as f:
    data = f.read(200 * 1024 * 1024)

print(f"File size: {len(data)/1024:.0f} KB")

# Parse all fills
fills = []
offset = 0
file_len = len(data)

current_ts_str = None
current_ts_val = 0
current_note = ""
pending_fill = None

while offset < file_len - 8:
    try:
        tag, length = struct.unpack('<II', data[offset:offset+8])
        if tag == 0 or tag > 512 or length > 65536:
            next_ptr = data.find(b'\x66\x00\x00\x00', offset + 1)
            if next_ptr == -1: break
            offset = next_ptr
            continue
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break

        if tag == 0x66:  # Timestamp
            new_dt = parse_tag66_timestamp(data[val_start:val_end])
            if new_dt:
                new_ts_val = new_dt.timestamp()
                if pending_fill and abs(new_ts_val - current_ts_val) > 0.5:
                    fills.append(pending_fill)
                    pending_fill = None
                current_ts_val = new_ts_val
                current_ts_str = new_dt.isoformat()
            current_note = ""

        elif tag == 0x82:  # Note
            val = data[val_start:val_end].decode(errors='ignore').strip()
            if val:
                current_note = (current_note + " " + val).strip()
                if pending_fill:
                    pending_fill['note'] = (pending_fill.get('note','') + " " + val).strip()

        elif tag == 0x68 or tag == 104:  # Message text containing fill info
            s = data[val_start:val_end].decode(errors='ignore')
            # Looking for fill messages
            if 'fill' in s.lower() or 'Fill' in s:
                side = None
                qty = 0
                price = 0.0
                buy_m = re.search(r'\b(BUY|Buy|buy|LONG|Long)\b', s)
                sell_m = re.search(r'\b(SELL|Sell|sell|SHORT|Short)\b', s)
                qty_m = re.search(r'Qty[:\s]*(\d+)', s, re.I) or re.search(r'Quantity[:\s]*(\d+)', s, re.I) or re.search(r'\b(\d+)\s+contracts?\b', s, re.I)
                price_m = re.search(r'(?:Bid|Ask|Price|Fill)[:\s]+([0-9]+(?:\.[0-9]+)?)', s, re.I)
                
                if buy_m: side = 'BUY'
                elif sell_m: side = 'SELL'
                if qty_m: qty = int(qty_m.group(1))
                if price_m: price = float(price_m.group(1))
                
                if side and qty > 0 and price > 0:
                    if pending_fill:
                        fills.append(pending_fill)
                    pending_fill = {
                        'ts': current_ts_str,
                        'ts_val': current_ts_val,
                        'side': side,
                        'qty': qty,
                        'price': price,
                        'note': current_note,
                        'msg': s[:100]
                    }

        offset = val_end
    except: 
        break

if pending_fill:
    fills.append(pending_fill)

print(f"\nTotal raw fills parsed: {len(fills)}")
total_with_notes = sum(1 for f in fills if f.get('note','').strip() and re.search(r'[A-Za-z0-9]', f['note']))
print(f"Fills with notes: {total_with_notes} / {len(fills)} = {total_with_notes/len(fills)*100:.1f}%")

# Show fills around 02:26 and 04:05 NY time
print("\n=== FILLS AROUND KEY TIMES ===")
for f in fills:
    if not f['ts']:
        continue
    try:
        dt = datetime.datetime.fromisoformat(f['ts'])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_ny = dt.astimezone(NY_TZ)
        hhh = dt_ny.hour
        mmm = dt_ny.minute
        # Show 02:20-02:35 and 04:00-04:25 NY
        if (hhh == 2 and 20 <= mmm <= 35) or (hhh == 4 and 0 <= mmm <= 25):
            note_present = "YES" if (f.get('note','').strip() and re.search(r'[A-Za-z0-9]', f['note'])) else "NO_NOTE"
            is_ghost = "GHOST!" if note_present == "NO_NOTE" else "valid"
            print(f"  {dt_ny.strftime('%H:%M:%S')} | {f['side']} {f['qty']} @ {f['price']} | note={note_present} | [{is_ghost}]")
            if f.get('note'):
                print(f"    note text: {f['note'][:60]}")
    except: pass
