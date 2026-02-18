
import asyncio
import os
import sys
import glob

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

async def dry_run_sim14_deduped():
    parser = BinaryLogParser()
    folders = [
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    ]
    
    all_files = []
    for fld in folders:
        if os.path.exists(fld):
            all_files.extend(glob.glob(os.path.join(fld, '*3Q_sim14.data')))
    
    all_files = list(set(all_files))
    all_files.sort()
    
    files_to_scan = []
    for f in all_files:
        if "TradeActivityLog_20" in f:
            match = os.path.basename(f)[17:27]
            if match >= "2024-08-13":
                files_to_scan.append(f)

    count = len(files_to_scan)
    print(f"Dry Run (DEDUPED): Scanning {count} files for SIM14 starting 2024-08-13...")
    
    all_unique_fills = {}
    
    for i, f in enumerate(files_to_scan):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{count} files...")
        try:
            fills = _parse_file_nitro(f, target_sym="CL")
            if fills:
                for f_item in fills:
                    # Global deduplication key (Account, Symbol, Side, Price, Qty, TimestampString)
                    key = (f_item['account_name'], f_item['symbol'], f_item['side'], f_item['price'], f_item['quantity'], f_item['timestamp'])
                    if key not in all_unique_fills:
                        all_unique_fills[key] = f_item
        except: pass

    # Now pair the deduped set
    deduped_fills = list(all_unique_fills.values())
    print(f"\nTotal Deduped Fills: {len(deduped_fills)}")
    
    trades, unpaired = parser._pairs_to_trades(deduped_fills)
    total_qty = sum(f['quantity'] for f in deduped_fills)
    total_comm = sum(t['commission'] for t in trades)
    total_pnl = sum(t['profit_loss'] for t in trades)

    print("\n--- Dry Run Results (DEDUPED) ---")
    print(f"Total Fills (Deduped): {len(deduped_fills)}")
    print(f"Total Filled Quantity: {total_qty}")
    print(f"Total Trades: {len(trades)}")
    print(f"Total Commissions: ${total_comm:.2f}")
    print(f"Total PnL (Net): ${total_pnl:.2f}")
    
    print("\nBenchmarks from Sierra Chart (since 2024-08-13):")
    print("  Filled Qty: 133,542")
    print("  Commissions: $280,350.00")
    print("  Profit/Loss: -$934,120.01")

if __name__ == "__main__":
    asyncio.run(dry_run_sim14_deduped())
