from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone
import datetime

f = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim15.data"
fills = _parse_file_nitro(f, "CL")

print(f"Found {len(fills)} fills for SIM15 Feb 17.")
for i, fill in enumerate(fills[:5]):
    print(f"Fill {i}: {fill['timestamp']} | Side: {fill['side']} | Price: {fill['price']} | Sym: {fill['symbol']}")

# Check if they have tag 102
# I will check if timestamps are all identical
timestamps = set(f['timestamp'] for f in fills)
print(f"Unique timestamps: {len(timestamps)}")
if len(timestamps) == 1:
    print(f"WARNING: All fills have the same timestamp: {list(timestamps)[0]}")
