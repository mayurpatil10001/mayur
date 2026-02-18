
import sqlite3

def check_account_trades():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    print("--- Symbol W ---")
    cursor.execute("SELECT trade_id, account_name, symbol, entry_price, entry_time FROM processed_trades WHERE symbol='W' LIMIT 5")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Symbol CL ---")
    cursor.execute("SELECT trade_id, account_name, symbol, entry_price, entry_time FROM processed_trades WHERE symbol='CL' LIMIT 5")
    for row in cursor.fetchall():
        print(row)
    conn.close()

if __name__ == '__main__':
    check_account_trades()
