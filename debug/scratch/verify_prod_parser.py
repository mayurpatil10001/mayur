import asyncio
import sys
from pathlib import Path
from trading_platform.services.binary_log_parser import BinaryLogParser
import sqlite3

async def test_prod_import():
    db_path = "test_import.db"
    if Path(db_path).exists(): Path(db_path).unlink()
    
    parser = BinaryLogParser(db_path=db_path)
    # Using the same range as the report
    paths = [r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"]
    
    print("Running Production-Grade Import Task...")
    await parser.run_import(
        paths=paths,
        account_filter=["TM_6"],
        days_lookback=14 # Feb 25 is within 14 days of March 4
    )
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name='TM_6' AND symbol='NQ'")
    count = c.fetchone()[0]
    
    print(f"Total NQ trades imported for TM_6: {count}")
    print(f"Report match expected: 82")
    
    if count == 82:
        print("✅ SUCCESS: Production Parser matches Validated Report exactly!")
    else:
        print(f"⚠️ MISMATCH: Expected 82, got {count}. Checking logs...")

if __name__ == "__main__":
    asyncio.run(test_prod_import())
