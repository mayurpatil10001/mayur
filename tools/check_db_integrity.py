
import sqlite3

def check_all_bad_trades():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    print("Checking for incomplete trades across ALL accounts...")
    
    # Check for null exit times or weird PnL
    # SQLite exit_time is stored as string ISO format.
    cursor.execute("""
        SELECT count(*) FROM processed_trades 
        WHERE exit_time IS NULL 
           OR exit_time = ''
           OR exit_price IS NULL
           OR exit_price = 0
    """)
    bad_count = cursor.fetchone()[0]
    
    print(f"Found {bad_count} potentially incomplete/bad trades in the database.")
    
    if bad_count > 0:
        cursor.execute("""
            SELECT id, account_name, symbol, entry_time, exit_time 
            FROM processed_trades 
            WHERE exit_time IS NULL OR exit_time = ''
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"BAD TRADE: {row}")

    conn.close()

if __name__ == "__main__":
    check_all_bad_trades()
