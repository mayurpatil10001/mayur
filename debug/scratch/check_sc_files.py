import os
import glob
import datetime

paths = [
    r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
    r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs',
    r'D:\SierraChart_Simulated_Feed\TradeActivityLogs',
    r'D:\SierraChart_Delayed_Simulated\TradeActivityLogs'
]

for p in paths:
    print(f"\nChecking path: {p}")
    if not os.path.exists(p):
        print("Path does not exist")
        continue
    
    files = glob.glob(os.path.join(p, "*.data")) + glob.glob(os.path.join(p, "*.DATA"))
    if not files:
        print("No .data files found")
        continue
    
    # Sort by mtime
    files.sort(key=os.path.getmtime, reverse=True)
    
    print(f"Total files: {len(files)}")
    print("Top 5 most recent files:")
    for f in files[:5]:
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f))
        print(f"{os.path.basename(f)} | Size: {os.path.getsize(f)} | Mtime: {mtime}")
