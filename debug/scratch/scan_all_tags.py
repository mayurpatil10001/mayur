"""Scan binary: list every tag number that appears in records that have tag 113 (FillPrice)."""
import struct
import glob
from collections import defaultdict

files = sorted(glob.glob(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"))
# In one file, collect all tags in "fill" records (record that contains tag 113)
tag_values = defaultdict(list)  # tag -> list of (raw_hex_or_str, decoded) for first 3 occurrences
for fp in files[:1]:
    d = open(fp, 'rb').read()
    n = len(d)
    pos = 0
    rec_has_113 = False
    rec_tags = {}
    while pos + 8 <= n:
        tag = struct.unpack('<I', d[pos:pos+4])[0]
        length = struct.unpack('<I', d[pos+4:pos+8])[0]
        val_start = pos + 8
        val_end = val_start + length
        if val_end > n:
            break
        raw = d[val_start:val_end]
        if tag in (102, 0x66):
            if rec_has_113:
                for t, (r, dec) in rec_tags.items():
                    if len(tag_values[t]) < 5:
                        tag_values[t].append((r.hex()[:50] if len(r) < 20 else r.hex()[:30], dec))
            rec_has_113 = False
            rec_tags = {}
        else:
            dec = None
            if length == 8:
                try:
                    q = struct.unpack('<q', raw)[0]
                    dbl = struct.unpack('<d', raw)[0]
                    if tag == 105:
                        dec = str(int(q))
                    elif tag == 113:
                        dec = dbl
                        rec_has_113 = True
                    elif tag == 125:
                        dec = dbl
                    else:
                        dec = "q=%s d=%s" % (q, dbl)
                except Exception:
                    dec = raw.hex()[:30]
            if dec is None and raw:
                try:
                    s = raw.decode('utf-8', errors='replace').strip('\x00').strip()
                    if s:
                        dec = s[:50]
                except Exception:
                    pass
            if dec is None:
                dec = raw.hex()[:30]
            rec_tags[tag] = (raw, dec)
        pos = val_end
    if rec_has_113:
        for t, (r, dec) in rec_tags.items():
            if len(tag_values[t]) < 5:
                tag_values[t].append((r.hex()[:50] if len(r) < 20 else r.hex()[:30], dec))

print("Tags in fill records (has 113), with sample values:")
for tag in sorted(tag_values.keys()):
    samples = tag_values[tag][:2]
    print("  tag %s (%s): %s" % (tag, hex(tag) if tag < 256 else tag, samples))
