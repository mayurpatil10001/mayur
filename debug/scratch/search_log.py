import os

log_path = 'import_debug.log'
if not os.path.exists(log_path):
    print("Log not found")
else:
    with open(log_path, 'r') as f:
        found = False
        lines = f.readlines()
        for i, line in enumerate(lines):
            if "--- RAW FILLS AUDIT FOR V_SIM16 ON 2025-12-18 ---" in line:
                print("".join(lines[i:i+200]))
                found = True
        if not found:
            print("Audit section not found in log")
