"""
Dump ALL V_SIM16 trades for Dec 18, 2025 (NY time) in chronological order
with explanation of what is happening.
"""
import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
conn = sqlite3.connect("trading_platform.db")
c = conn.cursor()

# The 12/18 trading session (NY):
# Session STARTS at 17:00 NY on 12/17 = 22:00 UTC on 12/17
# Session ENDS at 17:00 NY on 12/18 = 22:00 UTC on 12/18
UTC_START = "2025-12-17T22:00:00"
UTC_END   = "2025-12-18T22:00:00"

c.execute("""
    SELECT trade_id, entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= ?
      AND entry_time < ?
    ORDER BY entry_time ASC, exit_time ASC
""", (UTC_START, UTC_END))

rows = c.fetchall()
print(f"=== V_SIM16 Session Trades for Dec 18, 2025 (NY) ===")
print(f"Total trades in session: {len(rows)}")
print(f"{'#':>4}  {'Entry(NY)':>10}  {'Exit(NY)':>10}  {'Side':>6}  {'Qty':>4}  {'Entry Px':>10}  {'Exit Px':>10}  {'PnL':>10}")
print("-" * 90)

total_pnl = 0.0
for i, r in enumerate(rows, 1):
    tid, entry_str, exit_str, side, qty, pnl, epx, xpx = r
    entry_dt = datetime.datetime.fromisoformat(entry_str).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    exit_dt  = datetime.datetime.fromisoformat(exit_str).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    e = entry_dt.strftime("%H:%M:%S")
    x = exit_dt.strftime("%H:%M:%S")
    
    # Flag anything related to the 02:26 / 04:05 / 04:18 window
    flag = ""
    if "02:2" in e or "04:05" in e or "04:18" in x or "04:18" in e:
        flag = " <-- KEY"
    if "04:05" in x:
        flag = " <-- GHOST CLOSE?"
    
    print(f"{i:>4}  {e:>10}  {x:>10}  {side:>6}  {qty:>4}  {epx:>10}  {xpx:>10}  {pnl:>10.2f}{flag}")
    total_pnl += pnl

print("-" * 90)
print(f"Total PnL for session: ${total_pnl:.2f}")
conn.close()
