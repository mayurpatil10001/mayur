import asyncio
import sqlite3
import os
import sys
from trading_platform.services.binary_log_parser import BinaryLogParser

async def run_clean_reimport():
    parser = BinaryLogParser()
    db_path = parser.db_path
    
    account = "V_SIM16"
    
    # 1. SHOW CURRENT (GHOSTED) STATE
    print("\n--- CURRENT STATE (BEFORE CLEANUP) ---")
    parser.get_reconciliation_report(account)
    
    # 2. PURGE OLD DATA
    print(f"\nPurging existing trades for {account} from database...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM processed_trades WHERE account_name = ?", (account,))
    c.execute("DELETE FROM pending_fills WHERE account_name = ?", (account,))
    conn.commit()
    conn.close()
    
    # 3. RUN NEW BINARY IMPORT
    log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    print(f"Starting Note-Strict Binary Import from {log_dir}...")
    
    # We pass the directory path to the importer
    await parser.run_import(
        paths=[log_dir],
        account_filter=[account],
        days_lookback=90 # Last 3 months to be safe and fast
    )
    
    # 4. SHOW NEW (CLEAN) STATE
    print("\n--- CLEAN STATE (AFTER NOTE-STRICT IMPORT) ---")
    parser.get_reconciliation_report(account)

if __name__ == "__main__":
    # Ensure the root dir is in path for imports
    sys.path.append(os.getcwd())
    asyncio.run(run_clean_reimport())
