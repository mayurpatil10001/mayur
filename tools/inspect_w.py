
import sqlite3

def check_w_trades():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    cursor.execute("SELECT trade_id, account_name, symbol, entry_price, entry_time FROM processed_trades WHERE symbol='W' LIMIT 10")
    for row in cursor.fetchall():
        print(row)
    conn.close()

if __name__ == '__main__':
    check_w_trades()
