import os
import re
import datetime
import glob

path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs'
target_symbol = 'CL'
days_limit = 30
cutoff_time = (datetime.datetime.now() - datetime.timedelta(days=days_limit)).timestamp()

all_files_raw = glob.glob(os.path.join(path, "*.data"))
all_files = [f for f in all_files_raw if os.path.getmtime(f) >= cutoff_time]

account_files = {}
for f in all_files:
    fname = os.path.basename(f)
    parts = fname.split('.')
    if len(parts) > 1:
        account = parts[-2]
        account = re.sub(r'_UTC$', '', account)
        if account not in account_files:
            account_files[account] = []
        account_files[account].append(f)

detected_accounts = []
for account, files in account_files.items():
    match_found = False
    for f in files:
        if target_symbol in os.path.basename(f).upper():
            match_found = True
            break
    if match_found:
        detected_accounts.append(account)
        continue
    
    # Peek
    files.sort(key=os.path.getmtime, reverse=True)
    recent_files = files[:10]
    found_in_history = False
    for recent_file in recent_files:
        try:
            with open(recent_file, "rb") as bf:
                data = bf.read(100 * 1024)
                pattern_a = rb'\b' + target_symbol.encode() + rb'[FGHJKMNQUVXZ]\d{1,2}\b'
                if re.search(pattern_a, data, re.IGNORECASE):
                    found_in_history = True
                    break
        except: pass
    if found_in_history:
        detected_accounts.append(account)

print(f"Detected Accounts for {target_symbol}: {sorted(detected_accounts)}")
