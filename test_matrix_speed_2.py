import sqlite3
import time

conn = sqlite3.connect(r'c:\SierraChart\SC results WF\trading_platform.db')
c = conn.cursor()

symbol = 'NQ'

print("Testing persistence query...")
t0 = time.time()
persistence_query = """
WITH slot_monthly AS (
    SELECT
        account_name,
        printf('%02d:%02d',
            hour_of_day,
            CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END
        ) as time_slot,
        day_of_week,
        strftime('%Y-%m', entry_time) as ym,
        SUM(profit_loss) as month_pnl
    FROM processed_trades
    WHERE symbol = ?
        AND (hour_of_day < 17 OR hour_of_day >= 18)
        AND day_of_week IN (0,1,2,3,4,6)
    GROUP BY 1,2,3,4
)
SELECT
    account_name,
    time_slot,
    day_of_week,
    COUNT(*) as total_months,
    SUM(CASE WHEN month_pnl > 0 THEN 1 ELSE 0 END) as profitable_months
FROM slot_monthly
GROUP BY 1,2,3
"""
c.execute(persistence_query, (symbol,))
print(f"Persistence query complete in {time.time() - t0:.2f}s")

print("Testing recent queries...")
t0 = time.time()
recent_query = """
SELECT 
    account_name,
    printf('%02d:%02d', 
        hour_of_day,
        CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END
    ) as time_slot,
    day_of_week as day_of_week,
    AVG(profit_loss) as recent_avg_pnl,
    COUNT(*) as recent_n
FROM processed_trades 
WHERE symbol = ? AND entry_time >= date('now', '-30 days')
    AND (hour_of_day < 17 OR hour_of_day >= 18)
    AND day_of_week IN (0,1,2,3,4,6)
GROUP BY 1, 2, 3
"""
c.execute(recent_query, (symbol,))
print(f"Recent query complete in {time.time() - t0:.2f}s")
