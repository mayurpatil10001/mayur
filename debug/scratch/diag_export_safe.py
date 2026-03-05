import sys

path = r'C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt'
out = []

with open(path, 'r', encoding='utf-8') as f:
    orig_header = f.readline()
    headers = [h.strip() for h in orig_header.split('\t')]
    
    for line in f:
        # Check Dec 18 04:xx or 09:xx
        if '2025-12-18' in line and (line.find(' 04:05:') != -1 or line.find(' 04:18:') != -1 or line.find(' 04:46:') != -1 or line.find(' 09:05:') != -1 or line.find(' 09:18:') != -1 or line.find(' 09:46:') != -1):
            parts = [p.strip() for p in line.split('\t')]
            if len(parts) < len(headers):
                parts.extend([''] * (len(headers) - len(parts)))
            data = dict(zip(headers, parts))
            
            if data.get('ActivityType') == 'Fills':
                out.append(f"\nTime: {data.get('DateTime')}")
                for k in ['ActivityType', 'OrderType', 'Quantity', 'Price', 'BuySell', 'IsAutomated', 'Note', 'StatusText', 'InternalOrderID']:
                    if k in data:
                        out.append(f"  {k}: {data[k]}")

with open('diag_export.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
