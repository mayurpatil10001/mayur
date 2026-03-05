import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def check_pending():
    conn = sqlite3.connect("trading_platform.db")
    c = conn.cursor()
    
    # Check for V_SIM16 pending fills around 12/18
    c.execute("""
        SELECT entry_time, side, price, quantity, symbol 
        FROM pending_fills 
        WHERE account_name = 'V_SIM16'
        ORDER BY entry_time ASC
    """)
    
    rows = c.fetchall()
    print(f"Total pending fills: {len(rows)}")
    for entry, side, price, qty, sym in rows:
        try:
            ts_utc = datetime.datetime.fromisoformat(entry).replace(tzinfo=datetime.timezone.utc)
            ts_ny = ts_utc.astimezone(NY_TZ)
            if "2025-12-18" in ts_ny.strftime('%Y-%m-%d'):
                print(f"{ts_ny.strftime('%H:%M:%S')} | {side} {qty} @ {price} | {sym}")
        except: pass
    conn.close()

if __name__ == "__main__":
    check_pending()
