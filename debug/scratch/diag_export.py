import sys
path = r'C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt'

out = []
with open(path, 'r', encoding='utf-8') as f:
    header_line = f.readline().strip()
    headers = header_line.split('\t')
    
    # We want to dump all fills for 2025-12-18 around 04:05 to 04:20
    for line in f:
        if '2025-12-18  04:05:' in line or '2025-12-18  04:18:' in line:
            parts = line.strip('\n').split('\t')
            data = dict(zip(headers, parts))
            if data.get('ActivityType') == 'Fill':
                out.append(f"\nTime: {data.get('DateTime')}")
                # Print specific interesting fields
                for k in ['ActivityType', 'OrderType', 'Quantity', 'Price', 'Buy/Sell', 'IsAutomated', 'Note', 'StatusText', 'InternalOrderID']:
                    if k in data:
                        out.append(f"  {k}: {data[k]}")

with open('diag_export.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
