import os
import glob

search_dirs = [
    r'D:\SierraChart_Simulated_Feed',
    r'D:\SierraChart_Delayed_Simulated'
]

results = []
for d in search_dirs:
    pattern = os.path.join(d, '**', '*V_sim16*.data')
    files = glob.glob(pattern, recursive=True)
    for f in files:
        results.append((f, os.path.getsize(f)))

results.sort(key=lambda x: x[1], reverse=True)
print(f"Top 50 V_sim16 data files by size:")
for f, s in results[:50]:
    print(f"{f}: {s} bytes")
