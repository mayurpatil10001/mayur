import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Source files for V_SIM16 on Dec 18 according to sierra_chart_trades:")
c.execute("""
    SELECT DISTINCT file_path 
    FROM sierra_chart_trades 
    WHERE account_name = 'V_SIM16' 
      AND timestamp LIKE '2025-12-18%'
""")
for r in c.fetchall():
    print(f"  {r[0]}")

conn.close()
