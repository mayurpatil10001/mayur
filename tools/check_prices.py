import sqlite3

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("Price Ranges for CL trades:")
c.execute("""
    SELECT MIN(entry_price), MAX(entry_price), MIN(exit_price), MAX(exit_price)
    FROM processed_trades
    WHERE symbol LIKE '%CL%'
""")
row = c.fetchone()
print(f"Entry: {row[0]} to {row[1]}")
print(f"Exit: {row[2]} to {row[3]}")

conn.close()
