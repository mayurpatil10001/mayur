from trading_platform.services.binary_log_parser import _parse_file_nitro
import datetime

fp = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim15.data'
fills = _parse_file_nitro(fp, "CL")

print(f"--- FILLS IN {fp} ---")
# Count fills per hour
hours = {}
for f in fills:
    dt = datetime.datetime.fromisoformat(f['timestamp'])
    h = dt.strftime('%Y-%m-%d %H')
    hours[h] = hours.get(h, 0) + 1

for h in sorted(hours.keys()):
    print(f"{h}: {hours[h]} fills")

# Show all fills in this file
for f in fills:
    print(f"Fill: {f['timestamp']} | {f['side']} | {f['price']} | {f['symbol']}")
