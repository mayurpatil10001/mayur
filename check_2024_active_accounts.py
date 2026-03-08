import os
import glob
from collections import Counter

path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
files = glob.glob(os.path.join(path, '*2024*.data'))

acc_2024 = Counter()
for f in files:
    fn = os.path.basename(f)
    try:
        acc = fn.split('.')[-2].replace('_UTC', '')
        acc_2024[acc] += os.path.getsize(f)
    except: pass

print("Top accounts in 2024 by data size (main folder):")
for acc, size in acc_2024.most_common(20):
    print(f"{acc}: {size / 1024 / 1024:.2f} MB")
