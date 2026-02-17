
import os
import glob
import json
import asyncio
import datetime
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

async def run_test_import():
    base_dir = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    account = "3Q_sim14"
    start_date = "2026-02-09"
    end_date = "2026-02-13"
    
    print(f"Searching for logs for {account} between {start_date} and {end_date}...")
    
    # Generate expected filenames or glob them
    # Pattern: TradeActivityLog_YYYY-MM-DD_UTC.3Q_sim14.data
    files = []
    
    current = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    
    while current <= end:
        ds = current.strftime("%Y-%m-%d")
        pat = os.path.join(base_dir, f"TradeActivityLog_{ds}_UTC.{account}.data")
        if os.path.exists(pat):
            files.append(pat)
        else:
            # Try wildcards just in case
            g_pat = os.path.join(base_dir, f"TradeActivityLog_{ds}*.{account}.data")
            found = glob.glob(g_pat)
            files.extend(found)
        current += datetime.timedelta(days=1)
        
    print(f"Found {len(files)} files: {[os.path.basename(f) for f in files]}")
    
    if not files:
        print("No files found.")
        return

    parser = BinaryLogParser()
    
    # 1. Parse Files (Parallel mimics real run, but here we can just loop async)
    all_fills = []
    for fp in files:
        print(f"Parsing {os.path.basename(fp)}...")
        fills = _parse_file_nitro(fp, "CL") # Filter for CL as requested
        print(f"  > Found {len(fills)} fills")
        all_fills.extend(fills)
        
    # 2. Reconstruct Trades
    print(f"Reconstructing trades from {len(all_fills)} total fills...")
    trades = parser._pairs_to_trades(all_fills)
    
    print(f"Generated {len(trades)} raw aggregated trades.")
    
    # --- "SHIELD" LOGIC (Post-Process Filters) ---
    filtered_trades = []
    removed_overnight = 0
    removed_date_range = 0
    
    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1) # Include full end day
    
    for t in trades:
        # Parse Times
        et_str = t['entry_time']
        xt_str = t['exit_time']
        et = datetime.datetime.fromisoformat(et_str)
        xt = datetime.datetime.fromisoformat(xt_str)
        
        # 1. Date Range Filter (Strict)
        if not (start_dt <= et < end_dt):
            removed_date_range += 1
            continue
            
        # 2. Overnight Filter (Day Mismatch)
        # User Rule: "trades can not start in 1 day and continue into the next day"
        if et.date() != xt.date():
            removed_overnight += 1
            print(f"Dropping Overnight: {t['entry_time']} -> {t['exit_time']} | PnL: {t['pnl']}")
            continue
            
        filtered_trades.append(t)
        
    print(f"--- SHIELD REPORT ---")
    print(f"Removed {removed_date_range} trades outside date range.")
    print(f"Removed {removed_overnight} overnight trades.")
    print(f"Remaining Trades: {len(filtered_trades)}")

    # 3. Save to JSON and Calc Stats
    trades = filtered_trades # Swap to filtered list
    
    out_file = "test_import_results.json"
    with open(out_file, "w") as f:
        json.dump(trades, f, indent=2)
        
    print(f"Results saved to {out_file}")
    
    # 4. Print Summary
    total_pnl = sum(t['net_profit'] for t in trades)
    print(f"Total P&L: {total_pnl}")
    print(f"Total Trades: {len(trades)}")
    if trades:
        print("Sample Trade:")
        print(json.dumps(trades[0], indent=2))

if __name__ == "__main__":
    asyncio.run(run_test_import())
