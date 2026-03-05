import sqlite3

DB = "trading_platform.db"

QUERY = """
    WITH stats AS (
        SELECT 
            account_name, 
            symbol, 
            COUNT(*) as trade_count,
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(profit_loss) as total_pnl,
            AVG(profit_loss) as avg_pnl,
            MAX(exit_time) as last_trade_date,
            MIN(entry_time) as first_trade_date
        FROM processed_trades 
        GROUP BY account_name, symbol
    ),
    timing AS (
        SELECT 
            account_name,
            base_symbol,
            day_of_week,
            hour_of_day,
            ROW_NUMBER() OVER (PARTITION BY account_name, base_symbol ORDER BY average_profit_loss DESC) as rn
        FROM temporal_performance
    )
    SELECT 
        s.*,
        t.day_of_week as best_day_of_week,
        t.hour_of_day as best_hour_of_day
    FROM stats s
    LEFT JOIN timing t ON s.account_name = t.account_name AND s.symbol = t.base_symbol AND t.rn = 1
    ORDER BY s.account_name, s.symbol
"""

def check_plan():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    print("--- EXPLAIN QUERY PLAN ---")
    try:
        c.execute("EXPLAIN QUERY PLAN " + QUERY)
        for row in c.fetchall():
            print(row)
    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_plan()
