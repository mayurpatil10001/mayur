
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

c.execute("SELECT date_time FROM sierra_chart_fills LIMIT 10")
print(f"Fills: {c.fetchall()}")

c.execute("SELECT COUNT(*) FROM sierra_chart_fills WHERE date_time LIKE '%T%-%' OR date_time LIKE '%T%+%'")
count = c.fetchone()[0]
print(f"Matches in sierra_chart_fills: {count}")

if count > 0:
    c.execute("SELECT date_time FROM sierra_chart_fills WHERE date_time LIKE '%T%-%' OR date_time LIKE '%T%+%' LIMIT 1")
    print(f"Sample: {c.fetchone()[0]}")

conn.close()
