"""
Verify: Did the ghost filter actually work for V_SIM16 Dec 18?

We'll:
1. Find the binary log file for V_SIM16 on 2025-12-18
2. Parse it manually and count notes vs total fills
3. Check if the 04:05 ghost is present in DB (meaning it wasn't blocked)
"""
import sqlite3
import datetime
import struct
import re
import os
import glob
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

# Step 1: Is there a 04:18 LONG trade in the DB? (The 02:26 BUY should appear as a LONG entry)
conn = sqlite3.connect("trading_platform.db")
c = conn.cursor()

print("=== Checking DB for LONG trades on 12/18 for V_SIM16 ===")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time < '2025-12-19T00:00:00'
      AND side = 'LONG'
    ORDER BY entry_time ASC
""")
long_rows = c.fetchall()
print(f"LONG trades on 12/18 session: {len(long_rows)}")
for r in long_rows:
    entry_dt = datetime.datetime.fromisoformat(r[0]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    exit_dt  = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    e = entry_dt.strftime("%H:%M:%S")
    x = exit_dt.strftime("%H:%M:%S")
    print(f"  {e} -> {x} | LONG qty={r[2]} PnL={r[3]} px={r[4]}/{r[5]}")

print()

# Step 2: Is there a trade at 02:26 entry?
print("=== Checking for 02:26 entry (07:26 UTC = 02:26 NY EST) ===")
# 02:26 NY (EST = UTC-5) = 07:26 UTC
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-18T07:25:00'
      AND entry_time <= '2025-12-18T07:28:00'
    ORDER BY entry_time ASC
""")
rows_226 = c.fetchall()
print(f"Trades with entry 07:25-07:28 UTC (02:25-02:28 NY): {len(rows_226)}")
for r in rows_226:
    entry_dt = datetime.datetime.fromisoformat(r[0]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    exit_dt  = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    print(f"  {entry_dt.strftime('%H:%M:%S')} -> {exit_dt.strftime('%H:%M:%S')} | {r[2]} qty={r[3]} PnL={r[4]}")

print()

# Step 3: Check ALL unique sides on 12/18
c.execute("""
    SELECT side, COUNT(*), SUM(profit_loss) 
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time < '2025-12-19T00:00:00'
    GROUP BY side
""")
print("=== Side breakdown for 12/18 session ===")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]} trades, total PnL={r[2]:.2f}")

conn.close()

# Step 4: Find the 12/18 V_SIM16 binary log file
print()
print("=== Finding binary log file for V_SIM16 2025-12-18 ===")
search_dirs = [
    r"D:\SierraChart_Simulated_Feed\SavedTradeActivity",
    r"D:\SierraChart_Delayed_Simulated\SavedTradeActivity",
    r"C:\SierraChart\SavedTradeActivity",
    r"C:\SierraChart_Simulated\SavedTradeActivity",
]
found_files = []
for d in search_dirs:
    if os.path.exists(d):
        pattern = os.path.join(d, "*2025-12-18*V_SIM16*")
        matches = glob.glob(pattern, recursive=False)
        found_files.extend(matches)
        pattern2 = os.path.join(d, "*V_SIM16*2025-12-18*")
        matches2 = glob.glob(pattern2, recursive=False)
        found_files.extend(matches2)

found_files = list(set(found_files))
print(f"Found {len(found_files)} file(s):")
for f in found_files:
    print(f"  {f}")
