import sys

# Since the times might not match perfectly as text strings due to miliseconds or formatting,
# Let's search by date and look at all rows between 04:00 and 05:00.

path = r'C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt'

out = []
with open(path, 'r', encoding='utf-8') as f:
    orig_header = f.readline()
    headers = orig_header.strip().split('\t')
    
    for line in f:
        # We know 2025-12-18  04:
        if '2025-12-18  04:' in line:
            parts = line.strip('\n').split('\t')
            data = dict(zip(headers, parts))
            if data.get('ActivityType') == 'Fill':
                out.append(f"\nTime: {data.get('DateTime')}")
                for k in ['ActivityType', 'OrderType', 'Quantity', 'Price', 'Buy/Sell', 'IsAutomated', 'Note', 'StatusText', 'InternalOrderID']:
                    if k in data:
                        out.append(f"  {k}: {data[k]}")

with open('diag_export.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
