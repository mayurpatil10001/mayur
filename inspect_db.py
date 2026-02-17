
import sqlite3

def list_tables():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables: {tables}")
    
    for table in tables:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in cursor.fetchall()]
            print(f"  {table}: {cols}")
        except:
            pass
    conn.close()

if __name__ == '__main__':
    list_tables()
