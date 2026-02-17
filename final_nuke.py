
import sqlite3
import datetime

def final_nuke():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    print("Performing final thorough cleanup...")
    
    # 1. DELETE everything from previous binary attempts
    # (Matches BIN_ or BS_ prefix)
    cursor.execute("DELETE FROM processed_trades WHERE trade_id LIKE 'BIN_%' OR trade_id LIKE 'BS_%'")
    print(f"Deleted {cursor.rowcount} binary trade records.")
    
    # 2. DELETE bad symbols (CLN, CLH, ESZ etc)
    # Actually, let's keep ES, NQ, FDAX if they are clean, 
    # but the user said CL is messed up. Let's nuke anything starting with CL or containing future dates.
    cursor.execute("DELETE FROM processed_trades WHERE symbol LIKE 'CL%'")
    print(f"Deleted {cursor.rowcount} CL-related records.")
    
    # 3. Future dates
    cursor.execute("DELETE FROM processed_trades WHERE entry_time > '2026-03-01'")
    print(f"Deleted {cursor.rowcount} future dated records.")

    # 4. Clean up Accounts table
    # Remove accounts for CL and Unknown
    cursor.execute("DELETE FROM accounts WHERE base_symbol LIKE 'CL%' OR base_symbol = 'Unknown' OR base_symbol = 'T'")
    print(f"Deleted {cursor.rowcount} accounts from the accounts table.")
    
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    print("Cleanup complete.")

if __name__ == '__main__':
    final_nuke()
