import os, glob, datetime

PATHS = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
]

print("Scanning for V_SIM16 activity records on Dec 18 2025...")
results = []
for p in PATHS:
    if not os.path.isdir(p): continue
    files = glob.glob(os.path.join(p, "*.data"))
    for f in files:
        # Check if filename contains 2025-12-18
        if "2025-12-18" in os.path.basename(f):
            # Check if file size > 0
            if os.path.getsize(f) > 500:
                # Let's see if this file belongs to V_SIM16 internally
                # (even if not in filename)
                with open(f, 'rb') as fd:
                    d = fd.read(10000)
                    if b"V_SIM16" in d or b"v_sim16" in d:
                        results.append(f)

print(f"Found {len(results)} files for Dec 18 with V_SIM16 content:")
for r in results:
    print(f"  {r} ({os.path.getsize(r)} bytes)")
