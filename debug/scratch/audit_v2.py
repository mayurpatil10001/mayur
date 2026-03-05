import os
import sys

# Project root for imports
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

import struct
from trading_platform.services.binary_log_parser import _parse_tag66_timestamp, _is_ghost_fill, _to_ny, NY_TZ, _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, ghost_map = _parse_file_nitro(target_fp)
print(f"File: {target_fp}")
print(f"Fills: {len(fills)}, Ghosts: {ghost_map}")
