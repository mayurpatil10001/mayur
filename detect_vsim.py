import os
import glob
from collections import Counter

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
files = glob.glob(os.path.join(path, '*.data'))

vsim_detect = Counter()
for f in files:
    fn = os.path.basename(f)
    if 'V_SIM' in fn:
        try:
            acc = fn.split('.')[-2].replace('_UTC', '')
            vsim_detect[acc] += os.path.getsize(f)
        except: pass

print("V_SIM account distribution by total data size:")
for acc, size in vsim_detect.most_common():
    print(f"{acc}: {size / 1024 / 1024:.2f} MB")
