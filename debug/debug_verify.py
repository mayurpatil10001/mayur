import sys
sys.path.append(r"c:\SierraChart\SC results WF\trading_platform\services")
import binary_log_parser as blp
import os

files = [
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-01-19_UTC.3Q_sim14.data",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.ES-IPS_TM_5dupl.data"
]

print("Checking binary files...")
for f in files:
    if not os.path.exists(f):
        print(f"MISSING: {f}")
    else:
        size = os.path.getsize(f)
        print(f"FOUND: {f} ({size} bytes)")
        
        try:
            fills = blp._parse_file_nitro(f)
            print(f"  -> Generated {len(fills)} raw fills")
            if len(fills) > 0:
                print(f"  -> First fill: {fills[0]}")
        except Exception as e:
            print(f"  -> ERROR: {e}")
