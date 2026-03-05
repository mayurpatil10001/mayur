import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Final Verification of Dec 18 for V_SIM16:")
c.execute("""
    SELECT side, COUNT(*), SUM(profit_loss)
    FROM processed_trades 
    WHERE account_name = 'V_SIM16'
      AND entry_time >= '2025-12-17T22:00:00' AND entry_time < '2025-12-18T22:00:00'
    GROUP BY side
""")
rows = c.fetchall()
if not rows:
    print("  No trades found for this session.")
else:
    for r in rows:
        print(f"  {r[0]}: {r[1]} trades, PnL={r[2]:.2f}")

c.execute("""
    SELECT entry_time, side, quantity, entry_price
    FROM processed_trades 
    WHERE account_name = 'V_SIM16'
      AND entry_time LIKE '2025-12-18T07:26:%'
""")
match = c.fetchall()
print(f"\n02:26 NY (07:26 UTC) Match: {len(match)} trade(s)")
for m in match:
    print(f"  {m[1]} qty={m[2]} @ {m[3]}")

conn.close()
