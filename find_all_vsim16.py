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
        if any(m in fn for m in ['2023', '2024', '2025-01', '2025-02', '2025-03']):
            results.append((f, os.path.getsize(f)))

print(f"Historical V_sim16 files found:")
results.sort(key=lambda x: x[1], reverse=True)
for f, s in results[:50]:
    print(f"{f}: {s} bytes")
