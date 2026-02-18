
import sys
import os
import json
import sqlite3
import datetime

# Add project root to path
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser

def verify_structure():
    parser = BinaryLogParser()
    
    # We need to simulate the DB state or just trust the logic
    # Let's inspect the purge_anomalies return value type by traversing the code 
    # or by running it against the dummy data we created earlier if it still exists.
    
    print("Running purge_anomalies on DUMMY_ACC...")
    
    # Ensure dummy data exists (re-insert if needed)
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    # Insert a bad trade for DUMMY_ACC just to be sure we get a non-zero result
    # PnL -500
    bad_tid = "BAD_TRADE_VERIFY"
    c.execute("DELETE FROM processed_trades WHERE trade_id = ?", (bad_tid,))
    
    # Entry 16:55, Exit 18:05 (EOD)
    c.execute("""
        INSERT INTO processed_trades (
            trade_id, account_name, symbol, entry_time, exit_time, 
            profit_loss, commission, entry_price, exit_price, quantity, side, duration_minutes, hour_of_day, day_of_week
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        bad_tid, "DUMMY_ACC", "CL", 
        "2026-02-17T21:55:00", "2026-02-17T23:05:00", # UTC times roughly matching 16:55-18:05 NY
        -500.0, 5.0, 70.0, 69.5, 1, "LONG", 70, 16, 1
    ))
    conn.commit()
    conn.close()
    
    # Run purge
    breakdown = parser.purge_anomalies(account="DUMMY_ACC")
    
    print("\nBreakdown Result:")
    print(json.dumps(breakdown, indent=2))
    
    dummy_stats = breakdown.get("DUMMY_ACC", {})
    eod_stats = dummy_stats.get("eod_1700")
    
    if isinstance(eod_stats, dict) and "count" in eod_stats and "pnl" in eod_stats:
        print("\nSUCCESS: 'eod_1700' is a dictionary with 'count' and 'pnl'.")
        print(f"Count: {eod_stats['count']}, PnL: {eod_stats['pnl']}")
        if eod_stats['pnl'] == -500.0:
             print("SUCCESS: PnL value matches expected -500.0.")
        else:
             print(f"WARNING: PnL value {eod_stats['pnl']} != -500.0 (might depend on exactly what was purged)")
    else:
        print("\nFAILURE: 'eod_1700' structure is incorrect.")
        print(f"Got: {type(eod_stats)} - {eod_stats}")

if __name__ == "__main__":
    verify_structure()
