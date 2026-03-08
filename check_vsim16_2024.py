import os
import glob

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
files = glob.glob(os.path.join(path, '*V_sim16*.data'))

print(f"2024 files for V_sim16 in main folder:")
found = False
for f in files:
    fn = os.path.basename(f)
    if '2024' in fn:
        size = os.path.getsize(f)
        if size > 193:
            print(f"{fn}: {size} bytes")
            found = True
if not found:
    print("None found with data (>193 bytes).")
