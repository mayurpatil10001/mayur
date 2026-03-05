from trading_platform.services.binary_log_parser import _parse_file_nitro
import os

fp = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-24_UTC.V_SIM16.data'
if os.path.exists(fp):
    fills = _parse_file_nitro(fp)
    print(f"Total fills in {os.path.basename(fp)}: {len(fills)}")
    if fills:
        print("Last 5 fills:")
        for f in fills[-5:]:
            print(f)
else:
    print("File not found")
