import csv

fpath = 'C:/SierraChart/SC results WF/1218 nq all activity list.txt'

with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
    headers = f.readline().strip().split('\t')
    for line in f:
        row = dict(zip(headers, line.strip().split('\t')))
        dt = row.get('DateTime', '')
        if '12-18  04:05:5' in dt or '12-18  04:18:3' in dt or '12-18  04:18:4' in dt:
            typ = row.get('ActivityType', '')
            qty = row.get('Quantity', '')
            bs = row.get('BuySell', '')
            pos = row.get('PositionQuantity', '')
            note = row.get('Note', '')[:40]
            print(f"{dt} | {typ} | {bs} {qty} | Pos={pos} | {note}")
