import sqlite3, requests, time, datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
DB = r"C:\SierraChart\SC results WF\trading_platform.db"

# COMPLETE WIPE
print("Isolating Dec 18: Comprehensive wipe...")
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("DELETE FROM processed_trades WHERE account_name = 'V_SIM16' COLLATE NOCASE")
c.execute("DELETE FROM pending_fills WHERE account_name = 'V_SIM16' COLLATE NOCASE")
c.execute("DELETE FROM position_state WHERE account_name = 'V_SIM16' COLLATE NOCASE")
conn.commit()
conn.close()

# User requested 120 days
target_days = 120

print(f"Triggering import for V_SIM16 with {target_days} days lookback...")
resp = requests.post("http://localhost:8000/api/system/import-start", json={
    "paths": [
        r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
        r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
    ],
    "accounts": ["V_SIM16"],
    "days": target_days
}, timeout=30)
print(f"Triggered: {resp.status_code} {resp.json()}")

# Wait for completion
for i in range(30): 
    time.sleep(5)
    try:
        s = requests.get("http://localhost:8000/api/system/import-status", timeout=10).json()
        if not s.get("running", False): break
        print(f"  [{ (i+1)*5 }s] {s.get('message')}")
    except: pass

# Local Verification
print("\n=== ISOLATION VERIFICATION ===")
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""
    SELECT side, COUNT(*), SUM(profit_loss)
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time LIKE '2025-12-18%'
    GROUP BY side
""")
for r in c.fetchall():
     print(f"  {r[0]}: {r[1]} trades, PnL={r[2]:.2f}")

c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12-18T07:26:%'")
print(f"07:26 UTC trades: {c.fetchone()[0]}")

conn.close()
