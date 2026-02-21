
import sqlite3
import os

dbs = [
    r"c:\SierraChart\SC results WF\trading_platform.db",
    r"c:\SierraChart\SC results WF\trading_platform\database.db",
    r"c:\SierraChart\SC results WF\debug\trading_platform_all.db"
]

for db_path in dbs:
    if not os.path.exists(db_path):
        continue
    
    print(f"--- DB: {db_path} ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables: {tables}")
        
        if 'accounts' in tables:
            cursor.execute("SELECT name FROM accounts")
            accs = [r[0] for r in cursor.fetchall()]
            print(f"Accounts: {accs}")
            
        if 'processed_trades' in tables:
            cursor.execute("SELECT count(*) FROM processed_trades")
            print(f"Total trades: {cursor.fetchone()[0]}")
            
            cursor.execute("SELECT account_name, count(*) FROM processed_trades GROUP BY account_name")
            for acc, count in cursor.fetchall():
                print(f" - Account {acc}: {count} trades")
                
            cursor.execute("SELECT symbol, count(*) FROM processed_trades GROUP BY symbol")
            for sym, count in cursor.fetchall():
                print(f" - Symbol {sym}: {count} trades")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
