import sqlite3

conn = sqlite3.connect('trading_platform.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

query = """
        WITH stats AS (
            SELECT 
                account_name, 
                symbol, 
                COUNT(*) as trade_count,
                COALESCE(SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END), 0) as winning_trades,
                COALESCE(SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END), 0) as losing_trades,
                COALESCE(SUM(profit_loss), 0) as total_pnl,
                COALESCE(AVG(profit_loss), 0) as avg_pnl,
                MIN(entry_time) as first_trade,
                MAX(exit_time) as last_trade
            FROM processed_trades 
            GROUP BY account_name, symbol
        ),
        timing AS (
            SELECT 
                account_name,
                base_symbol,
                day_of_week as best_day,
                hour_of_day as best_hour,
                ROW_NUMBER() OVER (PARTITION BY account_name, base_symbol ORDER BY average_profit_loss DESC) as rn
            FROM temporal_performance
        )
        SELECT 
            s.account_name as name,
            s.symbol as base_symbol,
            s.trade_count,
            s.winning_trades,
            s.losing_trades,
            s.total_pnl,
            s.avg_pnl,
            s.first_trade as first_trade_date,
            s.last_trade as last_trade_date,
            t.best_day as best_day_of_week,
            t.best_hour as best_hour_of_day
        FROM stats s
        LEFT JOIN timing t ON s.account_name = t.account_name AND s.symbol = t.base_symbol AND t.rn = 1
        ORDER BY s.account_name, s.symbol
"""

try:
    cursor.execute(query)
    rows = cursor.fetchall()
    print(f"System Query found {len(rows)} rows.")
except Exception as e:
    print(f"SQL Error: {e}")
conn.close()
