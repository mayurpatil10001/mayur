import requests, time, sqlite3, datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
DB = r"C:\SierraChart\SC results WF\trading_platform.db"

# Poll until import done
for i in range(90):
    time.sleep(5)
    try:
        s = requests.get("http://localhost:8000/api/system/import-status", timeout=10).json()
        running = s.get("running", False)
        msg = s.get("message", "")
        progress = s.get("progress", 0)
        print(f"  [{(i+1)*5}s] running={running} pct={progress}% msg={msg[:70]}")
        if not running:
            break
    except Exception as e:
        print(f"  error: {e}")

print("\n--- Import complete. Verifying DB ---")
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16'")
total = c.fetchone()[0]
print(f"Total V_SIM16: {total}")

# The 02:26 NY trade = 07:26 UTC
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-18T07:20:00'
      AND entry_time <= '2025-12-18T07:35:00'
    ORDER BY entry_time
""")
rows = c.fetchall()
print(f"\n02:26 NY window (07:20-07:35 UTC): {len(rows)} trade(s)")
for r in rows:
    e = datetime.datetime.fromisoformat(r[0]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime("%H:%M:%S")
    x = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime("%H:%M:%S")
    print(f"  {e} -> {x} | {r[2]} qty={r[3]} PnL={r[4]} px={r[5]}/{r[6]}")

c.execute("""
    SELECT side, COUNT(*), SUM(profit_loss)
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time < '2025-12-18T22:00:00'
    GROUP BY side
""")
print("\nDec 18 session breakdown:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]} trades, PnL={r[2]:.2f}")

conn.close()
