import sqlite3
import os
import sys
import asyncio
from typing import List, Optional

# Add path
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser

async def clean_n_import():
    db_path = 'trading_platform.db'
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM processed_trades")
    conn.commit()
    conn.close()
    print("Database cleared.")

    parser = BinaryLogParser()
    path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    print(f"Importing TS_4 from {path}...")
    await parser.run_import([path], filter_symbol=None, account_filter=["TS_4"])
    print(f"Import Complete: {parser.message}")
    print(f"Final Count: {parser.stats['found']}")

    # Final DB Check
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT symbol, COUNT(*) FROM processed_trades GROUP BY symbol")
    print("\n--- Final Counts ---")
    for row in c.fetchall():
        print(row)
    conn.close()

if __name__ == "__main__":
    asyncio.run(clean_n_import())
