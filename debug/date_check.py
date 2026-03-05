import sqlite3

def check():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT account_name, symbol, count(*) FROM processed_trades WHERE entry_time LIKE '2025-12-18%' GROUP BY 1, 2")
    rows = c.fetchall()
    print("Data found on 2025-12-18:")
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    check()
