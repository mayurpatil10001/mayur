import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def check_trades():
    conn = sqlite3.connect("trading_platform.db")
    c = conn.cursor()
    
    # Query for 12/18 UTC window (05:00 UTC to 23:00 UTC covers the whole NY day)
    c.execute("""
        SELECT entry_time, exit_time, quantity, profit_loss, hour_of_day, side
        FROM processed_trades 
        WHERE account_name = 'V_SIM16' 
        AND entry_time >= '2025-12-18T05:00:00'
        AND entry_time <= '2025-12-18T23:59:59'
        ORDER BY entry_time ASC
    """)
    
    rows = c.fetchall()
    print(f"Trades found: {len(rows)}")
    for entry, exit, qty, pnl, hour, side in rows:
        e_utc = datetime.datetime.fromisoformat(entry).replace(tzinfo=datetime.timezone.utc)
        x_utc = datetime.datetime.fromisoformat(exit).replace(tzinfo=datetime.timezone.utc)
        e_ny = e_utc.astimezone(NY_TZ)
        x_ny = x_utc.astimezone(NY_TZ)
        
        print(f"{e_ny.strftime('%H:%M:%S')} -> {x_ny.strftime('%H:%M:%S')} | {side} {qty} | ${pnl} (h_db={hour})")

    conn.close()

if __name__ == "__main__":
    check_trades()
