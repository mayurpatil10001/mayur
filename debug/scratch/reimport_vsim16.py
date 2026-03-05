"""
Wipe V_SIM16 from DB, then call API /import-start to re-import, then verify.
"""
import requests, sqlite3, datetime, time
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
DB_PATH = r"C:\SierraChart\SC results WF\trading_platform.db"

# Step 1: Wipe
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("DELETE FROM processed_trades WHERE account_name = 'V_SIM16'")
c.execute("DELETE FROM pending_fills WHERE account_name = 'V_SIM16' COLLATE NOCASE")
conn.commit()
c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16'")
print(f"After wipe: {c.fetchone()[0]} V_SIM16 trades")
conn.close()

# Step 2: Trigger API import (background task)
resp = requests.post(
    "http://localhost:8000/api/v1/system/import-start",
    json={
        "paths": [
            r"D:\SierraChart_Simulated_Feed\SavedTradeActivity",
            r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
            r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
            r"D:\SierraChart_Delayed_Simulated\SavedTradeActivity"
        ],
        "accounts": ["V_SIM16"],
        "days": 2000
    },
    timeout=30
)
print(f"API trigger: {resp.status_code} -> {resp.json()}")

# Step 3: Poll until import is done
print("Waiting for import to complete...")
for i in range(60):
    time.sleep(5)
    try:
        s = requests.get("http://localhost:8000/api/v1/system/import-status", timeout=10).json()
        running = s.get("running", False)
        progress = s.get("progress", 0)
        msg = s.get("message", "")
        print(f"  [{i*5}s] running={running}, progress={progress}%, msg={msg[:50]}")
        if not running:
            break
    except Exception as e:
        print(f"  status check error: {e}")

# Step 4: Verify
print("\n=== VERIFICATION ===")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16'")
print(f"Total V_SIM16: {c.fetchone()[0]}")

# 02:26 LONG trade check
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-18T07:20:00'
      AND entry_time <= '2025-12-18T07:35:00'
    ORDER BY entry_time ASC
""")
rows = c.fetchall()
print(f"\n02:26 NY window (07:20-07:35 UTC): {len(rows)} trade(s)")
for r in rows:
    entry_dt = datetime.datetime.fromisoformat(r[0]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    exit_dt  = datetime.datetime.fromisoformat(r[1]).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
    print(f"  {entry_dt.strftime('%H:%M:%S')} -> {exit_dt.strftime('%H:%M:%S')} | {r[2]} qty={r[3]} PnL={r[4]} | Px:{r[5]}/{r[6]}")

# Dec 18 session breakdown
c.execute("""
    SELECT side, COUNT(*), SUM(profit_loss)
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00'
      AND entry_time < '2025-12-18T22:00:00'
    GROUP BY side
""")
print("\nDec 18 breakdown:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]} trades, PnL={r[2]:.2f}")
    
conn.close()
