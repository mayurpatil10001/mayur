import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Checking pending_fills for V_SIM16...")
c.execute("SELECT COUNT(*), account_name FROM pending_fills GROUP BY account_name")
for r in c.fetchall():
    print(f"Account: {r[1]} | Pending: {r[0]}")

c.execute("SELECT COUNT(*) FROM pending_fills WHERE account_name = 'V_SIM16' COLLATE NOCASE")
print(f"V_SIM16 Specific: {c.fetchone()[0]}")

conn.close()
