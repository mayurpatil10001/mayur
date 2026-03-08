import os
import glob

path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs'
files = glob.glob(os.path.join(path, '*V_sim16*.data'))

print(f"Jan-Mar 2025 files for V_sim16 in Instance 4:")
found = False
for f in files:
    fn = os.path.basename(f)
    if any(m in fn for m in ['2025-01', '2025-02', '2025-03']):
        print(f"{fn}: {os.path.getsize(f)} bytes")
        found = True
if not found:
    print("None found.")
