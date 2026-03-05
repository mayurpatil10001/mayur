import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

# Check schema first
c.execute("PRAGMA table_info(processed_trades)")
cols = [r[1] for r in c.fetchall()]
print(f"Columns: {cols}")

print("\nFinal DB Dump for V_SIM16 on Dec 18 (without note):")
# Use only existing columns
valid_cols = [c for c in ['entry_time', 'exit_time', 'side', 'quantity', 'profit_loss', 'entry_price', 'exit_price'] if c in cols]
query = f"SELECT {', '.join(valid_cols)} FROM processed_trades WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12-18%' ORDER BY entry_time ASC"

c.execute(query)
for r in c.fetchall():
    print(f"  {r[0]} | {r[2]:6s} qty={r[3]} | PnL={r[4]:8.2f} | Px={r[5]}/{r[6]}")

conn.close()
