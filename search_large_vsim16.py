import os
import glob

search_dirs = [
    r'D:\SierraChart_Simulated_Feed',
    r'D:\SierraChart_Delayed_Simulated',
]

print("V_sim16 (any case) files > 100KB:")
for d in search_dirs:
    for root, dirs, files in os.walk(d):
        for f in files:
            if 'V_SIM16'.lower() in f.lower() and f.endswith('.data'):
                path = os.path.join(root, f)
                size = os.path.getsize(path)
                if size > 100000: # 100KB
                    print(f"{path}: {size / 1024 / 1024:.2f} MB")
