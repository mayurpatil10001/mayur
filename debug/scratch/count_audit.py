import os

log_path = 'import_debug.log'
if not os.path.exists(log_path):
    print("Log not found")
else:
    with open(log_path, 'r') as f:
        lines = f.readlines()
        in_audit = False
        count = 0
        for line in lines:
            if "--- RAW FILLS AUDIT FOR V_SIM16 ON 2025-12-18 ---" in line:
                in_audit = True
            if in_audit:
                count += 1
            if in_audit and "--- END AUDIT ---" in line:
                in_audit = False
                print(f"Audit section has {count} lines")
                # Reset for next run if multiple
                count = 0
