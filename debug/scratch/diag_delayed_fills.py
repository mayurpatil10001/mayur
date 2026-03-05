import sys
import datetime

path = r'C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt'
out = []
target_h = ['08:0', '08:1', '08:2', '08:3', '08:4', '08:5', '09:0']

with open(path, 'r', encoding='utf-8') as f:
    orig_header = f.readline()
    headers = [h.strip() for h in orig_header.split('\t')]
    
    for line in f:
        is_target = False
        for h in target_h:
            if f'2025-12-18  {h}' in line:
                is_target = True
                break
                
        if is_target:
            parts = [p.strip() for p in line.split('\t')]
            if len(parts) < len(headers):
                parts.extend([''] * (len(headers) - len(parts)))
            data = dict(zip(headers, parts))
            
            act_type = data.get('ActivityType', '')
            if act_type in ['Fills', 'Orders', 'Positions']:
                # Filter out spam
                if 'Auto-trade' in data.get('Note', '') and act_type == 'Orders': continue
                
                out.append(f"{data.get('DateTime', '')[:22]} | {act_type:10} | {data.get('OrderType', ''):10} | Q:{data.get('Quantity', ''):3} | S:{data.get('OrderStatus', ''):10} | ID:{data.get('ServiceOrderID', ''):10} | {data.get('Note', '')[:30]}")

with open('diag_delayed_fills.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
