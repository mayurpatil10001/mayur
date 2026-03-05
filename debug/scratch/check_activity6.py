import csv

fpath = 'C:/SierraChart/SC results WF/1218 nq all activity list.txt'
outpath = 'C:/SierraChart/SC results WF/out_utf8.txt'

with open(fpath, 'r', encoding='utf-8', errors='ignore') as f, open(outpath, 'w', encoding='utf-8') as outf:
    headers = f.readline().strip().split('\t')
    for line in f:
        row = dict(zip(headers, line.strip().split('\t')))
        dt = row.get('DateTime', '')
        # Only print from 02:20 to 04:30
        if ('02:2' in dt or '03:' in dt or '04:0' in dt or '04:1' in dt or '04:2' in dt) and row.get('ActivityType') in ('Positions', 'Fills'):
             outf.write(f"{dt} | {row.get('ActivityType')[:3]} | {row.get('BuySell')[:1]}{row.get('Quantity')[:2]} | P={row.get('PositionQuantity')} | ID={row.get('InternalOrderID')} | {row.get('Note')[:30]}\n")
