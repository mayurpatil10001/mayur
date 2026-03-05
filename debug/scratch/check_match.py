import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Final Verification of 02:26 NY (07:26 UTC) LONG Trade:")
# In sierra_chart_trades: trade_type, account, entry_datetime
c.execute("""
    SELECT trade_type, trade_quantity, entry_price, note
    FROM sierra_chart_trades 
    WHERE account = 'V_SIM16' 
      AND entry_datetime LIKE '2025-12-18%'
      AND entry_datetime >= '2025-12-18 07:26:00'
      AND entry_datetime <= '2025-12-18 07:27:00'
""")
rows = c.fetchall()
if not rows:
    print("  No trades found for this exact time in sierra_chart_trades.")
else:
    for r in rows:
        print(f"  {r[0]} qty={r[1]} @ {r[2]} | Note='{r[3]}'")

# In processed_trades: side, quantity, entry_time
c.execute("""
    SELECT entry_time, side, quantity, entry_price
    FROM processed_trades
    WHERE account_name = 'V_SIM16'
      AND entry_time LIKE '2025-12-18T07:26:%'
""")
trades = c.fetchall()
print(f"\nProcessed Trades (FIFO results) starting at 07:26 UTC: {len(trades)}")
for t in trades:
    print(f"  {t[1]} qty={t[2]} @ {t[3]}")

conn.close()
