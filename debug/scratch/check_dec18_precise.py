import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

conn = sqlite3.connect("trading_platform.db")
c = conn.cursor()

# Specifically search for 12/18 entries (UTC range that maps to NY 12/18)
# 12/18/2025 00:00 NY = 12/18/2025 05:00 UTC
# 12/19/2025 00:00 NY = 12/19/2025 05:00 UTC
# But after 17:00 NY on 12/17 -> 12/17 22:00 UTC, session belongs to 12/18 NY

# So UTC range: 2025-12-17T22:00:00 to 2025-12-18T22:00:00
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time <= '2025-12-18T22:00:00'
    ORDER BY entry_time ASC
""")
rows = c.fetchall()
print(f"Trades with entry_time in 12/18 UTC window: {len(rows)}")
print()
for r in rows:
    entry_str = r[0]
    exit_str = r[1]
    try:
        entry_dt = datetime.datetime.fromisoformat(entry_str).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        exit_dt = datetime.datetime.fromisoformat(exit_str).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        print(f"{entry_dt.strftime('%H:%M:%S')} -> {exit_dt.strftime('%H:%M:%S')} | {r[2]} {r[3]} | PnL: {r[4]} | Px: {r[5]}/{r[6]}")
    except Exception as e:
        print(f"ERROR: {e} | {entry_str}")

conn.close()
