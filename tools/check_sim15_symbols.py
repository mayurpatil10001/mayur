import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- DISTINCT SYMBOLS FOR 3Q_SIM15 ---")
c.execute("""
    SELECT symbol, MAX(exit_time), COUNT(*) 
    FROM processed_trades 
    WHERE account_name = '3Q_SIM15' 
    GROUP BY symbol
""")
for row in c.fetchall():
    print(f"Symbol: {row[0]} | Last Exit: {row[1]} | Count: {row[2]}")

print("\n--- SAMPLE ROW FROM processed_trades ---")
c.execute("SELECT * FROM processed_trades WHERE account_name = '3Q_SIM15' LIMIT 1")
print(c.fetchone())

conn.close()
