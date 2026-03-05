import re
from collections import defaultdict

log_file = r'logs\import_clipping.log'
target_date = '2026-02-25'

stats = defaultdict(int)
sequences = []

with open(log_file, 'r') as f:
    for line in f:
        if target_date in line and 'V_SIM16' in line:
            m = re.search(r'\[([^\]]+)\].*Side: (BUY|SELL) \| Total Qty: (\d+) \| Allowed: (\d+) \| Dropped: (\d+) \| Pre-Pos: (-?\d+)', line)
            if m:
                ts, side, total, allowed, dropped, pre_pos = m.groups()
                sequences.append({
                    'ts': ts,
                    'side': side,
                    'total': int(total),
                    'allowed': int(allowed),
                    'dropped': int(dropped),
                    'pre_pos': int(pre_pos)
                })

print(f"Summary for {target_date} V_SIM16:")
print(f"Total Blocked Entries: {len(sequences)}")

# Print the last 20 sequences to see the state
for s in sequences[-20:]:
    print(f"{s['ts']} | {s['side']} | Tot:{s['total']} | Allow:{s['allowed']} | Drop:{s['dropped']} | Pre:{s['pre_pos']}")

# Count by hour
hourly = defaultdict(int)
for s in sequences:
    hour = s['ts'].split('T')[1].split(':')[0]
    hourly[hour] += 1

print("\nBlocked counts by hour:")
for h in sorted(hourly.keys()):
    print(f"{h}:00 -> {hourly[h]}")
