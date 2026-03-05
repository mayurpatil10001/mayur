import os
import glob
import re

def list_accounts():
    base_path = "D:/SierraChart_Simulated_Feed/TradeActivityLogs"
    files = glob.glob(os.path.join(base_path, "*.data"))
    accounts = set()
    for fp in files:
        fn = os.path.basename(fp)
        m = re.search(r'\.([^.]+)\.data$', fn)
        if m:
            accounts.add(m.group(1).upper())
    
    print(f"Total files: {len(files)}")
    print(f"Total unique accounts: {len(accounts)}")
    print("Sample accounts:", sorted(list(accounts))[:20])
    
    cl_accs = [a for a in accounts if "CL" in a]
    print("CL accounts:", cl_accs)
    
    tm_accs = [a for a in accounts if "TM_" in a]
    print("TM accounts:", tm_accs)

list_accounts()
