"""
After fix: check if 02:26 LONG trades appear anywhere in Dec 18 session.
Also look at ALL LONG trades for Dec 18 to understand FIFO pairing.
"""
import sqlite3, datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
DB = r"C:\SierraChart\SC results WF\trading_platform.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

# All LONG trades on Dec 18 session
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time < '2025-12-18T22:00:00'
      AND side = 'LONG'
    ORDER BY entry_time
""")
rows = c.fetchall()
print(f"LONG trades on Dec 18 session: {len(rows)}")
for r in rows:
    e = datetime.datetime.fromisoformat(r[0]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime("%H:%M:%S")
    x = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime("%H:%M:%S")
    print(f"  {e} -> {x} | {r[2]} qty={r[3]} PnL={r[4]} px={r[5]}/{r[6]}")

# Look at trades from 02:00 to 04:30 NY (07:00-09:30 UTC) to see full picture
print("\n=== Trades 02:00-04:30 NY (07:00-09:30 UTC) ===")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-18T07:00:00'
      AND entry_time < '2025-12-18T09:30:00'
    ORDER BY entry_time
""")
rows = c.fetchall()
print(f"Trades in zone: {len(rows)}")
for r in rows:
    e = datetime.datetime.fromisoformat(r[0]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime("%H:%M:%S")
    x = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime("%H:%M:%S")
    flag = " <-- 02:26 area" if "02:2" in e else ""
    flag = " <-- 04:18 area" if "04:18" in e or "04:18" in x else flag
    print(f"  {e} -> {x} | {r[2]} qty={r[3]} PnL={r[4]} px={r[5]}/{r[6]}{flag}")

conn.close()
