import struct
import os
import re

def dump_clh26_context(fp):
    with open(fp, "rb") as f:
        data = f.read()
    
    matches = list(re.finditer(b"CLH26", data))
    print(f"Found {len(matches)} matches for CLH26")
    
    for i, m in enumerate(matches[:20]):
        print(f"\n--- CLH26 Match {i} at {m.start()} ---")
        # Go back to start of message tag if possible
        # Messages usually start with 104 (x68)
        start = max(0, m.start() - 100)
        end = min(len(data), m.start() + 200)
        print(data[start:end].decode('ascii', errors='ignore'))

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-06_UTC.TS_4.data"
dump_clh26_context(fp)
