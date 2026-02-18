
import asyncio
import os
import sys
import glob

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

async def dry_run_fuzzy():
    parser = BinaryLogParser()
    folders = [
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    ]
    
    all_files = []
    for fld in folders:
        if os.path.exists(fld):
            all_f = glob.glob(os.path.join(fld, '*3Q_sim14.data'))
            all_files.extend([f for f in all_f if os.path.basename(f)[17:27] >= "2024-08-13"])
    
    all_files = sorted(list(set(all_files)))
    print(f"Dry Run (FUZZY): Scanning {len(all_files)} files...")
    
    unique_fills = {}
    
    for i, f in enumerate(all_files):
        try:
            fills = _parse_file_nitro(f, target_sym="CL")
            for fill in fills:
                # Fuzzy Key: Round timestamp to seconds
                ts_fuzzy = fill['timestamp'][:19]
                key = (fill['account_name'], fill['symbol'], fill['side'], fill['price'], fill['quantity'], ts_fuzzy)
                if key not in unique_fills:
                    unique_fills[key] = fill
        except: pass

    deduped = list(unique_fills.values())
    trades, _ = parser._pairs_to_trades(deduped)
    
    qty = sum(f['quantity'] for f in deduped)
    comm = sum(t['commission'] for t in trades)
    pnl = sum(t['profit_loss'] for t in trades)

    print("\n--- Dry Run Results (FUZZY) ---")
    print(f"Total Fills: {len(deduped)}")
    print(f"Total Filled Qty: {qty}")
    print(f"Total Comm: ${comm:.2f}")
    print(f"Total PnL: ${pnl:.2f}")
    
    print("\nBenchmarks (SC):")
    print("  Qty: 133,542 | Comm: $280,350.00 | PnL: -$934,120.01")

if __name__ == "__main__":
    asyncio.run(dry_run_fuzzy())
