import os
import glob
from collections import Counter

search_dirs = [
    r'D:\SierraChart_Simulated_Feed',
    r'D:\SierraChart_Delayed_Simulated'
]

account_stats = Counter()
account_examples = {}

for d in search_dirs:
    pattern = os.path.join(d, '**', 'TradeActivityLogs', '*.data')
    files = glob.glob(pattern, recursive=True)
    for f in files:
        fn = os.path.basename(f)
        if any(m in fn for m in ['2025-01', '2025-02', '2025-03']):
            size = os.path.getsize(f)
            if size > 5000: # Files larger than 5KB likely have trades
                try:
                    parts = fn.split('.')
                    if len(parts) > 1:
                        acc = parts[-2].replace('_UTC', '')
                        account_stats[acc] += size
                        if acc not in account_examples:
                            account_examples[acc] = f
                except:
                    pass

print("Accounts with significant data in Jan-Mar 2025:")
for acc, total_size in account_stats.most_common(20):
    print(f"{acc}: {total_size / 1024 / 1024:.2f} MB (Example: {account_examples[acc]})")
