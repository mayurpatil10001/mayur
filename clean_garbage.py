
import sqlite3
import datetime

def clean_db():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    # 1. Delete trades with symbols that are obviously wrong
    # (Accounts like '3Q_sim13' were incorrectly set as symbols)
    cursor.execute("DELETE FROM processed_trades WHERE symbol = 'Unknown' OR symbol LIKE 'V_%' OR symbol LIKE 'sim%' OR symbol LIKE '3Q%'")
    deleted_symbols = cursor.rowcount
    
    # 2. Delete trades with dates in the future
    now_str = datetime.datetime.now().isoformat()
    # Check for anything > 2026-03 (just to be safe)
    cursor.execute("DELETE FROM processed_trades WHERE entry_time > '2026-03-01'")
    deleted_future = cursor.rowcount
    
    # 3. Delete trades with very short trade_ids if they look like garbage
    # (Standard binary IDs start with BIN_)
    # Actually, the user might want a full wipe of binary data to be safe?
    # cursor.execute("DELETE FROM processed_trades WHERE trade_id LIKE 'BIN_%'")
    
    conn.commit()
    conn.close()
    
    print(f"Cleaned up {deleted_symbols} records with bad symbols.")
    print(f"Cleaned up {deleted_future} records with future dates.")

if __name__ == '__main__':
    clean_db()
