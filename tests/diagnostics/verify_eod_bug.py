import sqlite3
import datetime
from zoneinfo import ZoneInfo

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
NY_TZ = ZoneInfo("America/New_York")

def to_ny(iso_str):
    dt = datetime.datetime.fromisoformat(iso_str)
    # Assume input is UTC if it came from the logs we've been seeing
    # Actually, my parser doesn't add Z, but it's UTC wall clock.
    return dt.replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)

conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- CHECKING FOR TRADES CROSSING UTC 17:00-18:00 ---")
c.execute("SELECT trade_id, entry_time, exit_time FROM processed_trades WHERE time(entry_time) < '17:00:00' AND time(exit_time) >= '18:00:00' LIMIT 5")
rows = c.fetchall()
print(f"Found {len(rows)} trades that cross UTC 17-18.")
for row in rows:
    entry_ny = to_ny(row[1])
    exit_ny = to_ny(row[2])
    print(f"ID: {row[0]} | UTC: {row[1]} -> {row[2]} | NY: {entry_ny.strftime('%H:%M')} -> {exit_ny.strftime('%H:%M')}")

conn.close()
