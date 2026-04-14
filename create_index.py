import sqlite3
import time

print("Starting index creation...")
start = time.time()
try:
    conn = sqlite3.connect(r'c:\SierraChart\SC results WF\trading_platform.db')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_matrix_freshness ON processed_trades(symbol, account_name, entry_time)")
    conn.commit()
    print(f"Index created in {time.time() - start:.2f}s")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
