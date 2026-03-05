"""
Reverse-engineer exact open-close pairing from binary.
Dump ALL tags for a close fill (20090793) that we know closes open 20090786.
Look for parent ID 20090786 in any tag.
"""
import struct
import glob
from datetime import datetime

def parse_ts(b):
    if len(b) < 8:
        return None
    try:
        val = struct.unpack('<d', b[:8])[0]
        if 30000 < val < 70000:
            base = datetime(1899, 12, 30)
            return base + __import__('datetime').timedelta(days=val)
    except Exception:
        pass
    return None

def dump_record(d, start, end, label=""):
    """Dump every tag in [start, end) as (tag, length, raw_hex, decoded)."""
    out = []
    pos = start
    while pos + 8 <= end:
        tag = struct.unpack('<I', d[pos:pos+4])[0]
        length = struct.unpack('<I', d[pos+4:pos+8])[0]
        val_start = pos + 8
        val_end = val_start + length
        if val_end > end:
            break
        raw = d[val_start:val_end]
        decoded = None
        if length == 8:
            try:
                q = struct.unpack('<q', raw)[0]
                dbl = struct.unpack('<d', raw)[0]
                if 20000000 <= q <= 21000000 or 20000000 <= int(dbl) <= 21000000:
                    decoded = str(int(q)) if 20000000 <= q <= 21000000 else str(int(dbl))
                elif 30000 < dbl < 70000:
                    decoded = parse_ts(raw)
                else:
                    decoded = "q=%s d=%s" % (q, dbl)
            except Exception:
                decoded = "?"
        if decoded is None and raw:
            try:
                s = raw.decode('utf-8', errors='replace').strip('\x00').strip()
                if s and s.isprintable():
                    decoded = s[:60]
                if decoded is None:
                    decoded = raw.hex()[:40]
            except Exception:
                decoded = raw.hex()[:40]
        if decoded is None:
            decoded = raw.hex()[:40]
        # Check if 20090786 (parent) appears in raw or decoded
        parent_mark = ""
        if b"20090786" in raw or (isinstance(decoded, str) and "20090786" in decoded):
            parent_mark = " <-- PARENT 20090786"
        out.append((tag, length, raw.hex()[:50], decoded, parent_mark))
        pos = val_end
    return out

# Find record that has tag 105 = 20090793 and tag 113 = 24982.25 (fill price) and tag 120 = 2 (CLOSE)
files = sorted(glob.glob(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-1[89]_UTC.V_sim16.data"))
target_internal = 20090793
target_price = 24982.25
parent_oid = "20090786"

for fp in files:
    d = open(fp, 'rb').read()
    n = len(d)
    pos = 0
    rec_start = 0
    current = {}
    while pos + 8 <= n:
        tag = struct.unpack('<I', d[pos:pos+4])[0]
        length = struct.unpack('<I', d[pos+4:pos+8])[0]
        val_start = pos + 8
        val_end = val_start + length
        if val_end > n:
            break
        if tag in (102, 0x66):
            rec_start = pos
            current = {}
        else:
            raw = d[val_start:val_end]
            if tag == 105 and length == 8:
                try:
                    current[105] = struct.unpack('<q', raw)[0]
                except Exception:
                    pass
            if tag == 113 and length == 8:
                try:
                    current[113] = struct.unpack('<d', raw)[0]
                except Exception:
                    pass
            if tag == 120:
                try:
                    current[120] = raw[0] if raw else None
                except Exception:
                    pass
            if tag == 114 and length == 8:
                try:
                    current[114] = struct.unpack('<d', raw)[0]
                except Exception:
                    pass
        pos = val_end
        # Check if this record is our target close
        if current.get(105) == target_internal and current.get(113) == target_price and current.get(120) == 2:
            # Find record extent: from last tag 102 to next tag 102
            rec_end = pos
            # Also get start: go back to previous 102
            rs = rec_start
            for i in range(rs, 0, -1):
                if i + 8 <= n and struct.unpack('<I', d[i:i+4])[0] in (102, 0x66):
                    rec_start = i
                    break
            print("=== CLOSE record 20090793 @ 24982.25 in", fp)
            print("Record span: %d .. %d" % (rec_start, rec_end))
            rows = dump_record(d, rec_start, rec_end, "close")
            for tag, length, hex_, dec, mark in rows:
                print("  tag=%s len=%s %s %s%s" % (tag, length, str(dec)[:50], hex_[:30], mark))
            # Search entire record for bytes that could be parent (20090786 as int64, or as string)
            parent_int = 20090786
            raw_block = d[rec_start:rec_end]
            if struct.pack('<q', parent_int) in raw_block:
                print("  *** FOUND parent 20090786 as int64 in raw block ***")
            if b"20090786" in raw_block:
                print("  *** FOUND '20090786' as string in raw block ***")
            current = {}
            break
    else:
        continue
    break
else:
    print("Target close record not found.")

# Also list all unique tag numbers we see in any fill record (tag 113 present)
print("\n--- All tag numbers in fill records (has 113) ---")
seen_tags = set()
for fp in files:
    d = open(fp, 'rb').read()
    n = len(d)
    pos = 0
    has_113 = False
    while pos + 8 <= n:
        tag = struct.unpack('<I', d[pos:pos+4])[0]
        length = struct.unpack('<I', d[pos+4:pos+8])[0]
        val_end = pos + 8 + length
        if val_end > n:
            break
        if tag == 113:
            has_113 = True
        if tag in (102, 0x66):
            seen_tags.clear()
            has_113 = False
        else:
            seen_tags.add(tag)
        if has_113 and tag in (102, 0x66) and seen_tags:
            pass  # new record, reset
        pos = val_end
# Simpler: scan one file and collect tags between 102 and next 102 when 113 is present
seen = set()
for fp in files[:1]:
    d = open(fp, 'rb').read()
    n = len(d)
    pos = 0
    in_fill = False
    while pos + 8 <= n:
        tag = struct.unpack('<I', d[pos:pos+4])[0]
        length = struct.unpack('<I', d[pos+4:pos+8])[0]
        val_end = pos + 8 + length
        if val_end > n:
            break
        if tag in (102, 0x66):
            if in_fill:
                seen.update(rec_tags)
            rec_tags = set()
            in_fill = False
        else:
            rec_tags.add(tag)
            if tag == 113:
                in_fill = True
        pos = val_end
print("Tags in fill records:", sorted(seen))
