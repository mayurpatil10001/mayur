import sys
sys.path.insert(0, 'C:/SierraChart/SC results WF')
from trading_platform.services.binary_log_parser import _parse_file_nitro

f = 'D:/SierraChart_Simulated_Feed/TradeActivityLogs/TradeActivityLog_2025-12-18_UTC.V_sim16.data'
res = _parse_file_nitro(f)
fills = res[0]
for f in fills:
    ts = f.get('timestamp', '')
    if ts.startswith('2025-12-18'):
        time_part = ts[11:16]
        if '02:' <= time_part[:3] <= '05:':
            print(f"{ts[11:23]} | {f.get('side')} {f.get('quantity')} | PA={f.get('position_after')} | G={f.get('suggests_ghost', False)} | {f.get('note', '')[:10]}")
