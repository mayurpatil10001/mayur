import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Fills from PASTE specifically on 2026-02-24:")
# The paste import adds trades. Let's look for any trade that entered on the 24th.
cursor.execute("""
    SELECT count(*) 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND entry_time >= '2026-02-24T00:00:00'
""")
count_entries = cursor.fetchone()[0]
print(f"Trades ENTERING today: {count_entries}")

print("\nTrades EXITING today (but entered earlier):")
cursor.execute("""
    SELECT count(*) 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND entry_time < '2026-02-24T00:00:00'
      AND exit_time >= '2026-02-24T00:00:00'
""")
count_exits = cursor.fetchone()[0]
print(f"Trades exiting today (entered earlier): {count_exits}")

if count_entries > 0:
    print("\nSample of trades entering today:")
    cursor.execute("""
        SELECT entry_time, exit_time, symbol, side, profit_loss 
        FROM processed_trades 
        WHERE account_name = 'V_SIM16' 
          AND entry_time >= '2026-02-24T00:00:00'
        ORDER BY entry_time ASC
        LIMIT 5
    """)
    for r in cursor.fetchall():
        print(dict(r))

conn.close()
