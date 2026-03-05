import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
conn = sqlite3.connect("trading_platform.db")
c = conn.cursor()

# 02:26 NY on 12/18 = 07:26 UTC
# But wait - NY is UTC-5 in winter (EST). So 02:26 NY = 07:26 UTC. Let me check both.
# Actually let me just search all trades on 12/18 that start between 02:20-02:30 NY
# 02:20 NY = 07:20 UTC, 02:30 NY = 07:30 UTC
print("Searching for trades starting 02:20-02:30 NY on 12/18...")
c.execute("""
    SELECT trade_id, entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-18T07:20:00'
      AND entry_time <= '2025-12-18T07:31:00'
    ORDER BY entry_time ASC
""")
rows = c.fetchall()
print(f"  Found: {len(rows)}")

# Also search specifically around 02:26
print("\nSearching entry_time range wide (all 12/18 dates)...")
c.execute("""
    SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16'
      AND entry_time LIKE '2025-12-18%'
""")
cnt = c.fetchone()[0]
print(f"  Direct UTC date 2025-12-18 match: {cnt} trades")

# The 02:26 trade might be from previous day 12/17 UTC
# 12/18 02:26 NY - if DST is off (EST = UTC-5), then 02:26 NY = 07:26 UTC
# But log files use SCDateTime which was local. Let checking if stored as UTC
# Let me look at what UTC time corresponds to the 02:26 NY entry time
c.execute("""
    SELECT trade_id, entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time <= '2025-12-18T10:00:00'
    ORDER BY entry_time ASC
    LIMIT 30
""")
rows = c.fetchall()
print(f"\nAll trades 12/17 22:00 UTC -> 12/18 10:00 UTC ({len(rows)} trades):")
for r in rows:
    entry_dt = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    exit_dt = datetime.datetime.fromisoformat(r[2]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    e = entry_dt.strftime("%H:%M:%S")
    x = exit_dt.strftime("%H:%M:%S")
    print(f"  {e} -> {x} | {r[3]} qty={r[4]} PnL={r[5]}")

conn.close()
