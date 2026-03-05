import re

log_path = 'import_debug.log'
target_time = '2025-12-18T02:26'

print(f"Searching for {target_time} for V_SIM16...")
with open(log_path, 'r') as f:
    for line in f:
        if target_time in line and 'V_SIM16' in line.upper():
            print(line.strip())
        elif 'FOUND CANDIDATE' in line and target_time in line:
             print(line.strip())
        elif 'GHOST:' in line and target_time in line:
             print(line.strip())
