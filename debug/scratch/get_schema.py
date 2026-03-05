import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

def dump_table(name):
    print(f"\nTABLE: {name}")
    c.execute(f"PRAGMA table_info({name})")
    for r in c.fetchall():
        print(f"  {r[1]} ({r[2]})")

dump_table("sierra_chart_trades")
dump_table("processed_trades")
dump_table("pending_fills")
dump_table("position_state")

conn.close()
