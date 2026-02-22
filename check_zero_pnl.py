import sqlite3

def check_bin(account, dow, time_slot):
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # We need to replicate the time_slot logic from the SQL
    query = """
    SELECT 
        SUM(profit_loss) as total_pnl,
        COUNT(*) as trade_count,
        CAST(SUM(profit_loss) AS FLOAT) / COUNT(*) as avg_profit
    FROM processed_trades
    WHERE account_name = ?
      AND CAST(strftime('%w', entry_time) AS INTEGER) = ?
      AND (
          printf('%02d:%02d', 
            CAST(strftime('%H', entry_time) AS INTEGER), 
            CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
          ) = ?
      )
    """
    
    cursor.execute(query, (account, dow, time_slot))
    row = cursor.fetchone()
    print(f"Results for {account} on {dow} at {time_slot}:")
    print(f"  Total PnL: {row['total_pnl']}")
    print(f"  Trade Count: {row['trade_count']}")
    print(f"  Avg Profit: {row['avg_profit']}")
    conn.close()

if __name__ == "__main__":
    # Check TM_D-R-1_1 on Tuesday (2) at 00:30
    check_bin("TM_D-R-1_1", 2, "00:30")
    # Check TM_D-R-1_2 on Wednesday (3) at 01:00
    check_bin("TM_D-R-1_2", 3, "01:00")
