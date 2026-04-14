import sqlite3
import time
import datetime

conn = sqlite3.connect(r'c:\SierraChart\SC results WF\trading_platform.db')
c = conn.cursor()

cutoff_dt = datetime.datetime.now() - datetime.timedelta(days=30)
cutoff_str = cutoff_dt.isoformat()

symbol = 'NQ'
min_trades = 100
min_avg_profit = 12.0
min_win_rate = 45.0

print("Testing classic logic query...")
t0 = time.time()
query = """
WITH recent_accounts AS (
    SELECT account_name
    FROM processed_trades
    WHERE symbol = ?
    GROUP BY account_name
    HAVING MAX(entry_time) >= ?
),
time_day_performance AS (
    SELECT 
        account_name,
        symbol,
        printf('%02d:%02d', 
            hour_of_day,
            CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END
        ) as time_slot,
        day_of_week as day_of_week,
        COUNT(*) as total_trades,
        SUM(profit_loss) as total_pnl,
        AVG(profit_loss) as avg_trade,
        SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
        ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate,
        AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END) as avg_winner,
        AVG(CASE WHEN profit_loss <= 0 THEN profit_loss ELSE NULL END) as avg_loser,
        MAX(profit_loss) as largest_winner,
        MIN(profit_loss) as largest_loser,
        CASE WHEN SUM(CASE WHEN profit_loss <= 0 THEN ABS(profit_loss) ELSE 0 END) > 0
                THEN ROUND(SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END) /
                    SUM(CASE WHEN profit_loss <= 0 THEN ABS(profit_loss) ELSE 0 END), 2)
                ELSE 99 END as profit_factor
    FROM processed_trades 
    WHERE symbol = ?
        AND account_name IN (SELECT account_name FROM recent_accounts)
        AND (hour_of_day < 17 OR hour_of_day >= 18)
        AND day_of_week IN (0,1,2,3,4,6)
    GROUP BY 1, 3, 4
    HAVING total_trades >= ?
),
ranked_performance AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY time_slot, day_of_week 
            ORDER BY avg_trade DESC, win_rate DESC
        ) as rank
    FROM time_day_performance
)
SELECT 
    time_slot,
    day_of_week,
    account_name as best_account,
    total_trades,
    total_pnl,
    avg_trade,
    win_rate,
    avg_winner,
    avg_loser,
    largest_winner,
    largest_loser,
    profit_factor
FROM ranked_performance
WHERE rank = 1 
    AND avg_trade > ? 
    AND win_rate >= ?
ORDER BY time_slot, day_of_week
"""
c.execute(query, (symbol, cutoff_str, symbol, min_trades, min_avg_profit, min_win_rate))
rows = c.fetchall()
print(f"Query complete in {time.time() - t0:.2f}s, {len(rows)} rows found")
