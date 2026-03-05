import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Earliest 10 Processed Trades for V_SIM16 (90-day import):")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
    ORDER BY entry_time ASC 
    LIMIT 10
""")
for r in c.fetchall():
    print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]} | ${r[4]}")

print("\nEarliest Fills for V_SIM16 (before any processing):")
# I'll check first few fills to see if it starts with a SELL
# I'll check the 'sierra_chart_trades' table if it holds raw fills, 
# or I'll check raw database if I have a pending_fills table.
# Wait, processed_trades is the output. I need to see the INPUT fills.

conn.close()
