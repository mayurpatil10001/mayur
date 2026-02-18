import re
import os

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

words = [b"Bought", b"Sold", b"fill", b"Fill", b"Buy", b"Sell"]
for w in words:
    print(f"{w.decode()}: {data.count(w)}")

matches = list(re.finditer(b"Bought", data))
for i, m in enumerate(matches[:10]):
    print(f"\n--- Bought {i} at {m.start()} ---")
    print(data[m.start():m.start()+150].decode('ascii', errors='ignore'))
