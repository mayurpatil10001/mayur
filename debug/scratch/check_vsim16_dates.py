import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

conn = sqlite3.connect("trading_platform.db")
c = conn.cursor()

# Total count
c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16'")
total = c.fetchone()[0]
print(f"Total V_SIM16 trades: {total}")

# Date range
c.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE account_name = 'V_SIM16'")
r = c.fetchone()
print(f"Min entry_time: {r[0]}")
print(f"Max entry_time: {r[1]}")

# Most recent 10, converting to NY
c.execute("SELECT entry_time, exit_time FROM processed_trades WHERE account_name = 'V_SIM16' ORDER BY entry_time DESC LIMIT 10")
rows = c.fetchall()
print("\nMost recent 10 (DB -> NY):")
for row in rows:
    entry_str = row[0]
    try:
        dt = datetime.datetime.fromisoformat(entry_str).replace(tzinfo=datetime.timezone.utc)
        dt_ny = dt.astimezone(NY_TZ)
        fmt = dt_ny.strftime("%Y-%m-%d %H:%M:%S")
        print(f"  DB: {entry_str}  ->  NY: {fmt}")
    except Exception as e:
        print(f"  ERROR: {entry_str} ({e})")

# Specifically check Dec 2025 entries
print("\nSearching for Dec 2025 entries (entry_time LIKE '2025-12%'):")
c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12%'")
dec_count = c.fetchone()[0]
print(f"  Dec 2025 count: {dec_count}")

# All distinct year-months
c.execute("SELECT SUBSTR(entry_time, 1, 7), COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16' GROUP BY SUBSTR(entry_time, 1, 7) ORDER BY 1 DESC LIMIT 20")
print("\nMost recent 20 year-months:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} trades")

conn.close()
