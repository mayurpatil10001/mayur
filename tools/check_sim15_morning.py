from trading_platform.services.binary_log_parser import _parse_file_nitro
import datetime

fp = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-16_UTC.3Q_sim15.data'
fills = _parse_file_nitro(fp, "CL")

print(f"--- FILLS AROUND 04:40-04:50 UTC IN {fp} ---")
for f in fills:
    if "2026-02-16T04:4" in f['timestamp']:
        print(f"Fill: {f['timestamp']} | {f['side']} | {f['price']} | {f['symbol']} | Qty: {f['quantity']}")
