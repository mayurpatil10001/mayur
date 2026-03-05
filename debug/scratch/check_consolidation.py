import asyncio
from pathlib import Path
import sqlite3
import re
from trading_platform.services.binary_log_parser import BinaryLogParser

async def check_consolidation():
    parser = BinaryLogParser(db_path="trading_platform.db")
    # I want to find the Feb 25-28 trades for TM_6 and see if Qty is aggregated.
    # Actually V_SIM16 is a better test case if I have the files.
    
    conn = sqlite3.connect("trading_platform.db")
    c = conn.cursor()
    
    # Check if NQ is consolidated for V_SIM16
    c.execute("SELECT account_name, symbol, COUNT(*) FROM processed_trades WHERE account_name='V_SIM16' GROUP BY account_name, symbol")
    print("Database State (Accounts/Symbols):", c.fetchall())
    
    # Check for a specific entry time that was previously splintered
    # e.g. 12/18/2025 04:52:27
    c.execute("SELECT * FROM processed_trades WHERE account_name='V_SIM16' AND entry_time LIKE '2025-12-18T04:52:27%'")
    rows = c.fetchall()
    print(f"Found {len(rows)} trades for 04:52:27 entry.")
    for r in rows:
        print(r)

if __name__ == "__main__":
    asyncio.run(check_consolidation())
