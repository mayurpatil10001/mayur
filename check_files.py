import os
import glob

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
files = glob.glob(os.path.join(path, '*V_sim16*.data'))

large_files = []
for f in files:
    fn = os.path.basename(f)
    if any(m in fn for m in ['2025-01', '2025-02', '2025-03']):
        size = os.path.getsize(f)
        if size > 193:
            large_files.append((fn, size))

print(f"Found {len(large_files)} Jan-Mar 2025 files for V_sim16 with data (>193 bytes):")
for fn, size in sorted(large_files):
    print(f"{fn}: {size} bytes")
