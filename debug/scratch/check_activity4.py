import csv

fpath = 'C:/SierraChart/SC results WF/1218 nq all activity list.txt'

with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
    headers = f.readline().strip().split('\t')
    for line in f:
        row = dict(zip(headers, line.strip().split('\t')))
        dt = row.get('DateTime', '')
        if ('04:05:5' in dt or '04:18:3' in dt or '04:18:4' in dt) and row.get('ActivityType') in ('Positions', 'Fills'):
            print(f"{dt} | {row.get('ActivityType')} | {row.get('BuySell')} {row.get('Quantity')} | Pos={row.get('PositionQuantity')} | {row.get('Note')[:40]}")
