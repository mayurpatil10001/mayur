import sqlite3
import datetime

conn = sqlite3.connect(r"c:\SierraChart\SC results WF\trading_platform.db")
cutoff_str = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
print(f"Cutoff: {cutoff_str}")

# Check statistical mode's exact query fragment:
q = """
SELECT account_name
FROM processed_trades
WHERE symbol = 'NQ'
GROUP BY account_name
HAVING MAX(entry_time) >= ?
"""
accounts = [r[0] for r in conn.execute(q, (cutoff_str,)).fetchall()]
print(f"Accounts matched: {len(accounts)}")
if "TM_5" in accounts:
    print("TM_5 is STILL in recent accounts!")
    
    # Debug why
    print("TM_5 Max entry_time:", conn.execute("SELECT MAX(entry_time) FROM processed_trades WHERE account_name = 'TM_5'").fetchone()[0])
else:
    print("TM_5 is NOT in recent accounts")

if "TM_8" in accounts:
    print("TM_8 is STILL in recent accounts!")
else:
    print("TM_8 is NOT in recent accounts")
