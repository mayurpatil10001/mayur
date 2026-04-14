import sqlite3
import datetime

conn = sqlite3.connect(r"c:\SierraChart\SC results WF\trading_platform\database.db")
c = conn.cursor()

cutoff_dt = datetime.datetime.now() - datetime.timedelta(days=30)
cutoff_str = cutoff_dt.isoformat()

print(f"Cutoff str: {cutoff_str}")

c.execute("SELECT account_name FROM processed_trades WHERE symbol = 'NQ' GROUP BY account_name HAVING MAX(entry_time) >= ?", (cutoff_str,))
accounts = [r[0] for r in c.fetchall()]
print(f"Accounts: {len(accounts)}")
if "TM_5" in accounts or "TM_8" in accounts:
    print("WARNING: TM_5 or TM_8 is in recent accounts!")
else:
    print("TM_5 and TM_8 are NOT in recent accounts")
