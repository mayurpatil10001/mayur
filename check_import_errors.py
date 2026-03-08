import os

log_file = 'import_debug.log'
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print("Last 20 errors/messages related to NQ or V_sim16 in import_debug.log:")
    count = 0
    for line in reversed(lines):
        if 'V_sim16' in line or 'NQ' in line:
            print(line.strip())
            count += 1
            if count >= 20:
                break
else:
    print("import_debug.log not found.")
