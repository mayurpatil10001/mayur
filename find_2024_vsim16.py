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
        fn = os.path.basename(f)
        if '2024' in fn:
            size = os.path.getsize(f)
            if size > 1000:
                results.append((f, size))

results.sort(key=lambda x: x[1], reverse=True)
print(f"2024 V_sim16 files > 1KB:")
for f, s in results:
    print(f"{f}: {s} bytes")
