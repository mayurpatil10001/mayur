import sqlite3, datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
DB = r"C:\SierraChart\SC results WF\trading_platform.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

# Query all trades for V_SIM16 on Dec 18 (UTC)
print("=== V_SIM16 Trades on Dec 18 UTC ===")
c.execute("""
    SELECT side, entry_time, exit_time, quantity, entry_price, exit_price, profit_loss
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time <= '2025-12-18T22:00:00'
    ORDER BY entry_time ASC
""")
rows = c.fetchall()
print(f"Found {len(rows)} trades total.")

# Show specifically around 02:26 NY
print("\n--- Around 02:26 NY window (07:20-07:35 UTC) ---")
for r in rows:
    e_utc = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc)
    e_ny = e_utc.astimezone(NY_TZ)
    if 2 == e_ny.hour and 20 <= e_ny.minute <= 40:
        print(f"  {e_ny.strftime('%H:%M:%S')} {r[0]:6s} qty={r[3]} px={r[4]}/{r[5]} PnL={r[6]:.2f}")

# Count sides
sides = {}
for r in rows:
    sides[r[0]] = sides.get(r[0], 0) + 1
print(f"\nSummary by side: {sides}")

conn.close()
