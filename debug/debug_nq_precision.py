import sqlite3

def run_query():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    
    print("--- Checking for microsecond precision in entry_time ---")
    c.execute("SELECT entry_time FROM processed_trades WHERE symbol = 'NQ' AND entry_time LIKE '%.%' LIMIT 5")
    for row in c.fetchall():
        print(row)
        
    print("\n--- Checking for potential collisions (same second, different trade) ---")
    # This is harder to check in DB if they were already ignored during import.
    # But we can check if there are many trades in the same second.
    c.execute("""
        SELECT substr(entry_time, 1, 19) as sec, count(*) 
        FROM processed_trades 
        WHERE account_name = 'TM_7' AND symbol = 'NQ'
        GROUP BY sec
        HAVING count(*) > 1
        ORDER BY count(*) DESC
        LIMIT 10
    """)
    for row in c.fetchall():
        print(f"Second: {row[0]}, Count: {row[1]}")

    conn.close()

if __name__ == "__main__":
    run_query()
