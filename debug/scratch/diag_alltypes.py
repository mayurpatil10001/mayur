import sys

path = r'C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt'
out = []

with open(path, 'r', encoding='utf-8') as f:
    orig_header = f.readline()
    headers = [h.strip() for h in orig_header.split('\t')]
    
    for line in f:
        # Check Dec 18 09:05 roughly
        if '2025-12-18  09:05:5' in line or '2025-12-18  09:05:4' in line or '2025-12-18  09:18:3' in line:
            parts = [p.strip() for p in line.split('\t')]
            if len(parts) < len(headers):
                parts.extend([''] * (len(headers) - len(parts)))
            data = dict(zip(headers, parts))
            
            # Print ALL activity types for this minute
            out.append(f"\nType: {data.get('ActivityType')} | Time: {data.get('DateTime')}")
            for k in ['OrderType', 'Quantity', 'Price', 'BuySell', 'IsAutomated', 'Note', 'StatusText']:
                if k in data:
                    out.append(f"  {k}: {data[k]}")

with open('diag_alltypes.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
