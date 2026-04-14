import sqlite3
import time
from datetime import datetime, timedelta

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

symbol = 'NQ'
print(f"Testing Combined Stats Logic...")
t0 = time.time()

# 1. Get Matrix (Simulate internal call)
cursor.execute("""
        WITH recent_accounts AS (
            SELECT account_name
            FROM processed_trades
            WHERE symbol = ?
            GROUP BY account_name
            HAVING MAX(entry_time) >= date('now', '-30 days')
        ),
        time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', hour_of_day, CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END) as time_slot,
                day_of_week as day_of_week,
                COUNT(*) as total_trades,
                AVG(profit_loss) as avg_trade,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades 
            WHERE symbol = ?
              AND account_name IN (SELECT account_name FROM recent_accounts)
            GROUP BY 1, 2, 3
            HAVING total_trades >= 100
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY time_slot, day_of_week ORDER BY avg_trade DESC, win_rate DESC) as rank
            FROM time_day_performance
        )
        SELECT time_slot, day_of_week, account_name as best_account
        FROM ranked_performance
        WHERE rank = 1 AND avg_trade > 12.0 AND win_rate >= 45.0
""", (symbol, symbol))
matrix_rows = cursor.fetchall()
rec_lookup = {f"{r['time_slot']}_{r['day_of_week']}": r['best_account'] for r in matrix_rows}
print(f"  Matrix part took {time.time() - t0:.2f}s")

# 2. Get All Trades
t1 = time.time()
cursor.execute("""
        SELECT 
            printf('%02d:%02d', hour_of_day, CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END) as time_slot,
            day_of_week as day_of_week,
            account_name,
            profit_loss
        FROM processed_trades 
        WHERE symbol = ?
""", (symbol,))
all_trades = cursor.fetchall()
print(f"  Fetching all trades ({len(all_trades)}) took {time.time() - t1:.2f}s")

# 3. Filter
t2 = time.time()
recommended_trades = []
for trade in all_trades:
    key = f"{trade['time_slot']}_{trade['day_of_week']}"
    if rec_lookup.get(key) == trade['account_name']:
        recommended_trades.append(trade)
print(f"  Filtering {len(recommended_trades)} trades took {time.time() - t2:.2f}s")
print(f"Total Combined Stats simulation took {time.time() - t0:.2f}s")

conn.close()
