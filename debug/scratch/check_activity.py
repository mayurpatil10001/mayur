import csv

fpath = 'C:/SierraChart/SC results WF/1218 nq all activity list.txt'

with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
    headers = f.readline().strip().split('\t')
    for line in f:
        row = dict(zip(headers, line.strip().split('\t')))
        # 04:05 and 04:18 NY time corresponds to 09:05 and 09:18 UTC
        if '2025-12-18  09:0' in row.get('DateTime', '') or '2025-12-18  09:1' in row.get('DateTime', ''):
            dt = row.get('DateTime', '')
            typ = row.get('ActivityType', '')
            qty = row.get('Quantity', '')
            bs = row.get('BuySell', '')
            pos = row.get('PositionQuantity', '')
            note = row.get('Note', '')[:40]
            print(f"{dt} | {typ} | {bs} {qty} | Pos={pos} | {note}")
