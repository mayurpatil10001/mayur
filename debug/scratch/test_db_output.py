import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

ny_tz = ZoneInfo("America/New_York")

conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

c.execute("""
    SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12-18%' 
    ORDER BY entry_time ASC
""")

rows = c.fetchall()
print(f"Total clean trades on 12/18 UTC: {len(rows)}")
for r in rows:
    try:
        t_in_utc = datetime.fromisoformat(r[0]).replace(tzinfo=ZoneInfo("UTC"))
        t_out_utc = datetime.fromisoformat(r[1]).replace(tzinfo=ZoneInfo("UTC"))
        t_in_ny = t_in_utc.astimezone(ny_tz)
        t_out_ny = t_out_utc.astimezone(ny_tz)
        
        # Only print trades that happened in NY morning
        if t_in_ny.hour < 10:
            print(f"{t_in_ny.strftime('%H:%M:%S')} -> {t_out_ny.strftime('%H:%M:%S')} | {r[2]:5} {r[3]} | ${r[6]:.2f}")
    except Exception as e:
        pass

conn.close()
