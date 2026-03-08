import re

path = r'D:\SierraChart_Simulated_Feed\SavedTradeActivity\NQ_V_sim16_20240101-20250716.txt'
dates = []
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
        if match:
            dates.append(match.group(1))

if dates:
    print(f"Min date in file: {min(dates)}")
    print(f"Max date in file: {max(dates)}")
    print(f"Total lines with dates: {len(dates)}")
else:
    print("No dates found.")
