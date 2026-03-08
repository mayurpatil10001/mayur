import os
import glob

base_path = r'D:\SierraChart_Simulated_Feed'
search_pattern = os.path.join(base_path, '**', 'TradeActivityLogs', '*V_sim16*.data')
files = glob.glob(search_pattern, recursive=True)

relevant_months = ['2025-01', '2025-02', '2025-03']
found_data = []

for f in files:
    fn = os.path.basename(f)
    if any(m in fn for m in relevant_months):
        size = os.path.getsize(f)
        if size > 193:
            relative_path = f.replace(base_path, "")
            found_data.append((relative_path, size))

if not found_data:
    print("No V_sim16 data found in Jan-Mar 2025 across all instances.")
else:
    print(f"Found {len(found_data)} files with data (>193 bytes):")
    for rp, size in sorted(found_data):
        print(f"{rp}: {size} bytes")
