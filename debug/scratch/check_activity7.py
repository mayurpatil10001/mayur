import sys
sys.path.insert(0, 'C:/SierraChart/SC results WF')
from trading_platform.services.binary_log_parser import _parse_file_nitro

f = 'D:/SierraChart_Simulated_Feed/TradeActivityLogs/TradeActivityLog_2025-12-18_UTC.V_sim16.data'
fills, raw = _parse_file_nitro(f)
for v in fills:
    if '09:18:3' in v['timestamp'] or '09:18:4' in v['timestamp']:
        print(f"TS={v['timestamp']} | SIDE={v.get('side')} QTY={v.get('quantity')} | POS_AFTER={v.get('position_after')} | MSG={v.get('msgtxt')}")
