import sqlite3
import time

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

symbol = 'NQ'
min_trades = 100
min_avg_profit = 12.0
min_win_rate = 45.0
min_persistence = 60.0

print(f"Testing Persistence Query Optimization...")
t0 = time.time()

query = """
        WITH recent_accounts AS (
            SELECT account_name
            FROM processed_trades
            WHERE symbol = ?
            GROUP BY account_name
            HAVING MAX(entry_time) >= date('now', '-30 days')
        ),
        slot_monthly AS (
            SELECT
                account_name,
                printf('%02d:%02d',
                    hour_of_day,
                    CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                day_of_week,
                strftime('%Y-%m', entry_time) as year_month,
                SUM(profit_loss) as month_pnl
            FROM processed_trades
            WHERE symbol = ?
              AND account_name IN (SELECT account_name FROM recent_accounts)
              AND (hour_of_day < 17 OR hour_of_day >= 18)
              AND day_of_week IN (0,1,2,3,4,6)
            GROUP BY 1,2,3,4
        ),
        slot_stats AS (
            SELECT
                sm.account_name,
                sm.time_slot,
                sm.day_of_week,
                COUNT(*) as total_months,
                SUM(CASE WHEN sm.month_pnl > 0 THEN 1 ELSE 0 END) as profitable_months
            FROM slot_monthly sm
            GROUP BY 1,2,3
        ),
        trade_stats AS (
            SELECT
                account_name,
                printf('%02d:%02d',
                    hour_of_day,
                    CASE WHEN COALESCE(minute_of_hour_ny, 0) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                day_of_week,
                COUNT(*) as total_trades,
                SUM(profit_loss) as total_pnl,
                AVG(profit_loss) as avg_trade,
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
            GROUP BY 1,2,3
            HAVING total_trades >= ?
        ),
        merged AS (
            SELECT
                t.*,
                ROUND((s.profitable_months * 100.0 / CASE WHEN s.total_months = 0 THEN 1 ELSE s.total_months END), 1) as persistence_score
            FROM trade_stats t
            JOIN slot_stats s
              ON s.account_name = t.account_name
             AND s.time_slot = t.time_slot
             AND s.day_of_week = t.day_of_week
        ),
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week
                    ORDER BY persistence_score DESC, avg_trade DESC, win_rate DESC
                ) as rank
            FROM merged
        )
        SELECT *
        FROM ranked
        WHERE rank = 1
          AND avg_trade > ?
          AND win_rate >= ?
          AND persistence_score >= ?
        ORDER BY time_slot, day_of_week
"""

cursor.execute(query, (symbol, symbol, symbol, min_trades, min_avg_profit, min_win_rate, min_persistence))
rows = cursor.fetchall()
print(f"Query returned {len(rows)} rows in {time.time() - t0:.2f}s")
conn.close()
