
import os
import sys

# Add path to services to import parser
sys.path.append(os.path.join(os.getcwd(), 'trading_platform', 'services'))

from binary_log_parser import BinaryLogParser, _parse_file_nitro

def check_multiday():
    base_path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    files = [
        os.path.join(base_path, "TradeActivityLog_2026-02-16_UTC.3Q_sim14.data"),
        os.path.join(base_path, "TradeActivityLog_2026-02-17_UTC.3Q_sim14.data"),
    ]
    
    parser = BinaryLogParser("temp.db")
    
    # 1. Parse Individually
    print("--- INDIVIDUAL ---")
    orphans = 0
    for f in files:
        fills = _parse_file_nitro(f)
        fills.sort(key=lambda x: x['timestamp'])
        _, count = parser._pairs_to_trades(fills)
        print(f"File {os.path.basename(f)}: UNPAIRED = {count}")
        orphans += count
    
    print(f"Total isolated orphans: {orphans}")
    
    # 2. Parse Combined
    print("\n--- COMBINED ---")
    all_fills = []
    for f in files:
        all_fills.extend(_parse_file_nitro(f))
    
    all_fills.sort(key=lambda x: x['timestamp']) # GLOBAL sort
    
    combined_trades, combined_count = parser._pairs_to_trades(all_fills)
    print(f"Combined Fills: {len(all_fills)}")
    print(f"Combined Trades Formed: {len(combined_trades)}")
    print(f"Combined UNPAIRED = {combined_count}")

if __name__ == "__main__":
    check_multiday()
