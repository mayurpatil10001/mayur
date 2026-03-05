import os
import glob
from trading_platform.services.binary_log_parser import _parse_file_nitro

log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

fills = []
for file in files:
    f, _ = _parse_file_nitro(file)
    fills.extend(f)

for f in fills:
    ts = f.get('timestamp', '')
    if '2025-12-18T06:' in ts or '2025-12-18T07:' in ts:
        print(f"[{ts}] {f.get('side', '')} {f.get('quantity', 0)} @ {f.get('price')} | Ghost={f.get('is_ghost', False)}")
