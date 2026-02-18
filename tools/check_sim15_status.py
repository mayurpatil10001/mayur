
import sqlite3

def check_sim15():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) 
        FROM processed_trades 
        WHERE account_name = '3Q_SIM15' 
        AND entry_time >= '2026-02-07'
    """)
    res = c.fetchone()
    print(f"SIM15 trades since Feb 7: {res[0] if res else 0}")
    conn.close()

if __name__ == "__main__":
    check_sim15()
