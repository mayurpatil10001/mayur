import os
import sys

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, ghost_map = _parse_file_nitro(target_fp)

found = False
for f in fills:
    if "2025-12-18T09:05:56" in f['timestamp']:
        print(f"Fill TS: {f['timestamp']}")
        print(f"Fill Note: |{f['note']}|")
        found = True

if not found:
    print("Could not find fill at 09:05:56 in fills.")
    # Maybe it was a ghost?
    # but ghost_map was empty.
