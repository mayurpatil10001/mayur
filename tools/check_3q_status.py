import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- LATEST TRADES FOR ALL 3Q ACCOUNTS ---")
c.execute("""
    SELECT account_name, MAX(entry_time), COUNT(*) 
    FROM processed_trades 
    WHERE account_name LIKE '3Q_SIM%' 
    GROUP BY account_name
""")
for row in c.fetchall():
    print(row)

print("\n--- SAMPLE SIM14 TRADES FOR TODAY ---")
c.execute("SELECT entry_time, exit_time, symbol, profit_loss FROM processed_trades WHERE account_name = '3Q_SIM14' AND entry_time LIKE '2026-02-17%' LIMIT 5")
for row in c.fetchall():
    print(row)

conn.close()
