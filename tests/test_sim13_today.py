import os
import sys

# Add the project path to sys.path
sys.path.append(r'c:\SierraChart\SC results WF')

from trading_platform.services.binary_log_parser import _parse_file_nitro

fp = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim13.data'
fills = _parse_file_nitro(fp, 'CL')
print(f"Total fills found in file: {len(fills)}")
for f in fills[:5]:
    print(f)
