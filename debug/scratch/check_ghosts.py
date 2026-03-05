
import sys, os
from pathlib import Path
sys.path.insert(0, 'C:/SierraChart/SC results WF')
from trading_platform.services.binary_log_parser import _parse_file_nitro

f = 'D:/SierraChart_Simulated_Feed/TradeActivityLogs/TradeActivityLog_2025-12-18_UTC.V_sim16.data'
fills, _ = _parse_file_nitro(f)
for v in fills:
    if '21:52:07' in v['timestamp']:
        print(f"TS={v['timestamp']} | Q={v['quantity']} | ACC={v['account_name']} | Note='{v['note']}' | Msg={v['msgtxt']}")
    if '21:24:27' in v['timestamp']:
        print(f"TS={v['timestamp']} | Q={v['quantity']} | ACC={v['account_name']} | Note='{v['note']}' | Msg={v['msgtxt']}")
