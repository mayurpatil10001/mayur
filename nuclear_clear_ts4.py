import sqlite3
import os

def nuclear_clear():
    db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
    if not os.path.exists(db_path):
        print(f"ERROR: DB not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("Pre-clear count for TS_4:", c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name='TS_4'").fetchone()[0])
    
    c.execute("DELETE FROM processed_trades WHERE account_name='TS_4'")
    conn.commit()
    
    print("Post-clear count for TS_4 (Should be 0):", c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name='TS_4'").fetchone()[0])
    conn.close()

if __name__ == "__main__":
    nuclear_clear()
