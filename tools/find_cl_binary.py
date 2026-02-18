import re
import os

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-06_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

# Search for the "Trading Evaluator" bid/ask pattern
pattern = rb"Bid: ([\d\.]+)\s+Ask: ([\d\.]+)\s+Last: ([\d\.]+)"
matches = list(re.finditer(pattern, data))
print(f"Found {len(matches)} evaluator price blocks")

for i, m in enumerate(matches):
    prices = [p.decode() for p in m.groups()]
    last = float(prices[2])
    if 20 <= last <= 200: # CL Price range
        print(f"\n--- Probable CL Fill at {m.start()} ---")
        context = data[max(0, m.start()-200):m.end()+100].decode('ascii', errors='ignore')
        print(context)
        if i > 500: break # Just find one

print("Search complete.")
