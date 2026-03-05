import os

log_path = 'import_debug.log'
if not os.path.exists(log_path):
    print("Log not found")
else:
    with open(log_path, 'r') as f:
        lines = f.readlines()
        audit_ranges = []
        start = -1
        for i, line in enumerate(lines):
            if "--- RAW FILLS AUDIT FOR V_SIM16 ON 2025-12-18 ---" in line:
                start = i + 1
            if start != -1 and "--- END AUDIT ---" in line:
                audit_ranges.append((start, i + 1))
                start = -1
        
        for i, (s, e) in enumerate(audit_ranges):
            print(f"Audit {i+1}: Lines {s} to {e}")
