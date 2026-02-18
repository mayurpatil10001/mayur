
import asyncio
import os
import sys
import glob

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

async def dry_run_sim14():
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
    print(f"Dry Run: Scanning {count} files for SIM14 starting 2024-08-13...")
    
    stats = {
        "fills": 0,
        "qty": 0,
        "trades": 0,
        "pnl": 0.0,
        "comm": 0.0
    }
    
    for i, f in enumerate(files_to_scan):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{count} files...")
        try:
            # We want CL trades
            fills = _parse_file_nitro(f, target_sym="CL")
            if fills:
                stats["fills"] += len(fills)
                stats["qty"] += sum(fill['quantity'] for fill in fills)
                
                trades, _ = parser._pairs_to_trades(fills)
                stats["trades"] += len(trades)
                stats["pnl"] += sum(t['profit_loss'] for t in trades)
                stats["comm"] += sum(t['commission'] for t in trades)
        except Exception as e:
            # print(f"Error in {f}: {e}")
            pass

    print("\n--- Dry Run Results for SIM14 ---")
    print(f"Total Files Scanned: {count}")
    print(f"Total Raw Fills: {stats['fills']}")
    print(f"Total Filled Quantity: {stats['qty']}")
    print(f"Total Trades: {stats['trades']}")
    print(f"Total Commissions: ${stats['comm']:.2f}")
    print(f"Total PnL (Net): ${stats['pnl']:.2f}")
    
    print("\nBenchmarks from Sierra Chart (since 2024-08-13):")
    print("  Filled Qty: 133,542")
    print("  Commissions: $280,350.00")
    print("  Profit/Loss: -$934,120.01")

if __name__ == "__main__":
    asyncio.run(dry_run_sim14())
