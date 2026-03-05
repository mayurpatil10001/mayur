import sys

path = r'C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt'
out = []

with open(path, 'r', encoding='utf-8') as f:
    orig_header = f.readline()
    headers = [h.strip() for h in orig_header.split('\t')]
    
    for line in f:
        if ('2025-12-18  09:05:4' in line or '2025-12-18  09:05:5' in line) and 'Fills' in line:
            parts = [p.strip() for p in line.split('\t')]
            if len(parts) < len(headers):
                parts.extend([''] * (len(headers) - len(parts)))
            data = dict(zip(headers, parts))
            
            if data.get('ActivityType') == 'Fills':
                out.append(f"\nTarget: {data.get('DateTime')}")
                for k in ['ActivityType', 'OrderType', 'Quantity', 'Price', 'BuySell', 'IsAutomated', 'Note', 'StatusText', 'InternalOrderID']:
                    if k in data:
                        out.append(f"  {k}: {data[k]}")

with open('diag_alltypes2.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
