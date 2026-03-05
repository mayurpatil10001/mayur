import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def dump_trades():
    conn = sqlite3.connect("trading_platform.db")
    c = conn.cursor()
    
    # Check for V_SIM16 trades on 12/18 NY
    # We'll fetch a wider range to be sure.
    c.execute("""
        SELECT trade_id, entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
        FROM processed_trades 
        WHERE account_name = 'V_SIM16'
        ORDER BY entry_time ASC
    """)
    
    rows = c.fetchall()
    print(f"Total trades for V_SIM16: {len(rows)}")
    found = 0
    for r in rows:
        tid, entry, exit, side, qty, pnl, en_px, ex_px = r
        try:
            ts_utc = datetime.datetime.fromisoformat(entry).replace(tzinfo=datetime.timezone.utc)
            ts_ny = ts_utc.astimezone(NY_TZ)
            if "2025-12-18" in ts_ny.strftime('%Y-%m-%d'):
                print(f"{ts_ny.strftime('%H:%M:%S')} -> {datetime.datetime.fromisoformat(exit).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ).strftime('%H:%M:%S')} | {side} {qty} | PnL: ${pnl} | Px: {en_px}/{ex_px}")
                found += 1
        except: pass
    print(f"Trades on 12/18 NY: {found}")
    conn.close()

if __name__ == "__main__":
    dump_trades()
