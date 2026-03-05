import os
import struct
import re
import datetime

def check_3q_sim14_bad_fills():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-18_UTC.3Q_sim14.data"
    if not os.path.exists(data_path): return

    with open(data_path, "rb") as bf: d = bf.read()
    
    offset = 0
    fills = []
    while offset < len(d) - 16:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            if "trade simulation fill" in s.lower():
                fills.append(s)
        offset = val_end
        
    print(f"3Q_sim14 Audit:")
    # Check if ANY fill lacks 'AutoTrader'
    bad = [f for f in fills if "AutoTrader" not in f]
    print(f"Total fills: {len(fills)} | Fills without 'AutoTrader' tag: {len(bad)}")
    if bad:
        for b in bad[:5]: print(f"  - {b}")

if __name__ == "__main__":
    check_3q_sim14_bad_fills()
