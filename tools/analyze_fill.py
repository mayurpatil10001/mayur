import re
import datetime
import os

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.3Q_sim13.data"

print(f"Analyzing {fp}...")
with open(fp, "rb") as f:
    data = f.read()

# 1. Count "Filled" occurrences
filled_count = len(re.findall(rb"Filled", data, re.IGNORECASE))
print(f"Total 'Filled' strings found: {filled_count}")

# 2. Extract a few samples to see the context
print("\nSample Contexts around 'Filled':")
matches = list(re.finditer(rb"Filled", data, re.IGNORECASE))
for m in matches[:5]:
    start = max(0, m.start() - 100)
    end = min(len(data), m.end() + 100)
    print(f"--- Offset {m.start()} ---")
    chunk = data[start:end]
    try:
        print(chunk.decode(errors='ignore'))
    except:
        print(chunk)

# 3. Look for OrderStatus
print("\nScanning for 'OrderStatus'...")
status_matches = list(re.finditer(rb"OrderStatus: Filled", data, re.IGNORECASE))
print(f"'OrderStatus: Filled' count: {len(status_matches)}")

# 4. Look for Price
print("\nScanning for Prices near Filled...")
for m in matches[:3]:
    start = max(0, m.start() - 200)
    end = min(len(data), m.end() + 200)
    chunk = data[start:end]
    price_match = re.search(rb"(?:Price|FillPrice|ParentPrice)[:\s]*([\d\.]+)", chunk)
    if price_match:
        print(f"Found Price: {price_match.group(1)} near Filled at {m.start()}")
    else:
        print(f"NO Price found near Filled at {m.start()}")
