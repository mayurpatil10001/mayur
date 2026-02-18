
import sqlite3
import datetime
from zoneinfo import ZoneInfo
import os
import sys

# Add path for imports
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser

def create_dummy_trades():
    db_path = 'trading_platform.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. Clear existing trades for a dummy account to avoid noise
    dummy_acc = "DUMMY_ACC"
    c.execute("DELETE FROM processed_trades WHERE account_name = ?", (dummy_acc,))
    conn.commit()
    
    # 2. Insert BAD trade (EOD violation)
    # Entry: 16:55 NY (before 17:00)
    # Exit: 18:05 NY (after 18:00)
    # PnL: -150.0
    
    ny_tz = ZoneInfo("America/New_York")
    base_date = datetime.datetime.now(ny_tz).date()
    
    t1_ny = datetime.datetime.combine(base_date, datetime.time(16, 55), tzinfo=ny_tz)
    t2_ny = datetime.datetime.combine(base_date, datetime.time(18, 5), tzinfo=ny_tz)
    
    t1_utc = t1_ny.astimezone(datetime.timezone.utc)
    t2_utc = t2_ny.astimezone(datetime.timezone.utc)
    
    bad_tid = "BAD_TRADE_001"
    
    c.execute("""
        INSERT INTO processed_trades (
            trade_id, account_name, symbol, entry_time, exit_time, 
            entry_price, exit_price, quantity, side, 
            profit_loss, commission, duration_minutes,
            hour_of_day, day_of_week
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        bad_tid, dummy_acc, "CL", 
        t1_utc.isoformat(), t2_utc.isoformat(),
        70.00, 69.90, 1, "LONG", 
        -100.0, 5.0, 70, 
        t1_ny.hour, t1_ny.weekday()
    ))
    
    # 3. Insert GOOD trade
    # Entry: 15:00 NY
    # Exit: 15:30 NY
    good_tid = "GOOD_TRADE_001"
    t3_ny = datetime.datetime.combine(base_date, datetime.time(15, 0), tzinfo=ny_tz)
    t4_ny = datetime.datetime.combine(base_date, datetime.time(15, 30), tzinfo=ny_tz)
    t3_utc = t3_ny.astimezone(datetime.timezone.utc)
    t4_utc = t4_ny.astimezone(datetime.timezone.utc)

    c.execute("""
        INSERT INTO processed_trades (
            trade_id, account_name, symbol, entry_time, exit_time, 
            entry_price, exit_price, quantity, side, 
            profit_loss, commission, duration_minutes,
            hour_of_day, day_of_week
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        good_tid, dummy_acc, "CL", 
        t3_utc.isoformat(), t4_utc.isoformat(),
        70.00, 70.10, 1, "LONG", 
        100.0, 5.0, 30, 
        t3_ny.hour, t3_ny.weekday()
    ))
    
    conn.commit()
    conn.close()
    print(f"Inserted dummy trades for {dummy_acc}. BAD trade PnL = -100.0. GOOD trade PnL = 100.0.")

async def run_verification():
    create_dummy_trades()
    
    parser = BinaryLogParser()
    print("Running purge_anomalies...")
    
    # Run purge - removed await because purge_anomalies is synchronous
    parser.purge_anomalies(account="DUMMY_ACC")
    
    # Verify DB
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("SELECT trade_id FROM processed_trades WHERE account_name = 'DUMMY_ACC'")
    remaining = [r[0] for r in c.fetchall()]
    conn.close()
    
    print(f"Remaining trades in DB: {remaining}")
    
    if "BAD_TRADE_001" not in remaining and "GOOD_TRADE_001" in remaining:
        print("SUCCESS: Bad trade purged, good trade kept.")
    else:
        print("FAILURE: Purge logic incorrect.")

    # Check Log
    print("Checking log output...")
    try:
        with open("import_debug.log", "r") as f:
            lines = f.readlines()
            # Look for recent logs
            found_log = False
            for line in reversed(lines):
                 if "PURGE DUMMY_ACC" in line:
                     print(f"Found Log Line: {line.strip()}")
                     found_log = True
                     # Check for the formatted PnL string we expect
                     # Formatted as: ($pnl) e.g. ($-100.00)
                     if "($-100.00)" in line: 
                         print("SUCCESS: PnL logged correctly.")
                     else:
                         print("FAILURE: PnL NOT logged correctly (value mismatch).")
                     break
            if not found_log:
                print("FAILURE: No log line found for DUMMY_ACC.")
    except Exception as e:
        print(f"Error reading log: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_verification())
