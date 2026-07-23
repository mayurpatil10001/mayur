import sqlite3
import time

print("Starting agg index creation...")
start = time.time()
try:
    conn = sqlite3.connect(r'c:\SierraChart\SC results WF\trading_platform.db')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_matrix_agg ON processed_trades(symbol, day_of_week, hour_of_day, account_name)")
    conn.commit()
    print(f"Index created in {time.time() - start:.2f}s")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
