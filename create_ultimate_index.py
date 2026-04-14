import sqlite3
import time

print("Starting ultimate covering index creation...")
start = time.time()
try:
    conn = sqlite3.connect(r'c:\SierraChart\SC results WF\trading_platform.db')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_matrix_ultimate ON processed_trades(symbol, hour_of_day, day_of_week, account_name, entry_time, profit_loss, minute_of_hour_ny)")
    conn.commit()
    print(f"Index created in {time.time() - start:.2f}s")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
