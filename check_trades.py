
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("SELECT entry_time FROM processed_trades")
rows = c.fetchall()
bad_rows = [r[0] for r in rows if '-' in r[0].split('T')[-1] or '+' in r[0].split('T')[-1]]
print(f"Found {len(bad_rows)} rows with timezone offsets")
if bad_rows:
    print(f"Sample: {bad_rows[0]}")
conn.close()
