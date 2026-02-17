import sqlite3
import os

def check_counts():
    db_path = 'trading_platform.db'
    if not os.path.exists(db_path):
        print("DB Not found")
        return
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute("SELECT account_name, COUNT(*) FROM processed_trades GROUP BY account_name")
    rows = c.fetchall()
    print("--- Database Contents by Account ---")
    if not rows:
        print("Database is empty.")
    for acc, count in rows:
        print(f"{acc}: {count} trades")
    
    c.execute("SELECT COUNT(*) FROM processed_trades")
    print(f"\nTotal trades in DB: {c.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    check_counts()
