
import sqlite3

def clean_db():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    # 1. Delete all trades from binary imports
    print("Cleaning binary import trades...")
    cursor.execute("DELETE FROM processed_trades WHERE trade_id LIKE 'BS_%'")
    print(f"Deleted {cursor.rowcount} binary trades.")
    
    # 2. Delete garbage accounts
    print("Cleaning garbage accounts...")
    # Specifically 'W' and anything that shouldn't be there
    cursor.execute("DELETE FROM accounts WHERE base_symbol = 'W' OR name LIKE '%Unknown%'")
    print(f"Deleted {cursor.rowcount} garbage accounts.")
    
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    print("Cleanup successful.")

if __name__ == '__main__':
    clean_db()
