import os
import glob

base_path = r'D:\SierraChart_Simulated_Feed'
search_pattern = os.path.join(base_path, '**', 'TradeActivityLogs', '*V_sim16*.data')
files = glob.glob(search_pattern, recursive=True)

stats = {}

for f in files:
    parent = os.path.dirname(f)
    size = os.path.getsize(f)
    if size > 193:
        stats[parent] = stats.get(parent, 0) + size

print("Data size for V_sim16 (>193 bytes) per folder:")
for folder, total_size in sorted(stats.items(), key=lambda x: x[1], reverse=True):
    print(f"{folder}: {total_size / 1024 / 1024:.2f} MB")
