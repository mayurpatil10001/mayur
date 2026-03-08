import os
import glob
import re

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
files = glob.glob(os.path.join(path, '*V_sim16*.data'))

dates = []
for f in files:
    if os.path.getsize(f) > 193:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', f)
        if match:
            dates.append(match.group(1))

if dates:
    print(f"Main folder V_sim16 data range: {min(dates)} to {max(dates)}")
    print(f"Total files with data in main folder: {len(dates)}")
else:
    print("No V_sim16 data files found in main folder.")
