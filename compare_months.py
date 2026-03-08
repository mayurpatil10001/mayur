import os
import glob
import re

folders = {
    'Main': r'D:\SierraChart_Simulated_Feed\TradeActivityLogs',
    'Instance4': r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs'
}

months = ['2025-01', '2025-02', '2025-03']

for label, path in folders.items():
    print(f"\nChecking {label} folder: {path}")
    files = glob.glob(os.path.join(path, '*V_sim16*.data'))
    found = []
    for f in files:
        if any(m in f for m in months) and os.path.getsize(f) > 193:
            found.append(os.path.basename(f))
    print(f"Files with data in {months}: {len(found)}")
    if found:
        print(f"Sample: {sorted(found)[:5]}")
