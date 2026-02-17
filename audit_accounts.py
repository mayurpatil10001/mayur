
import sqlite3
import pandas as pd

def audit_accounts():
    conn = sqlite3.connect('trading_platform.db')
    
    query = """
    SELECT 
        account_name,
        symbol,
        COUNT(*) as db_trade_count,
        SUM(profit_loss) as db_total_pnl,
        MAX(entry_time) as last_trade_time
    FROM processed_trades
    GROUP BY account_name, symbol
    ORDER BY account_name, symbol
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Format for readability
    pd.options.display.float_format = '{:,.2f}'.format
    
    print("\n=== ACCOUNT AUDIT REPORT ===")
    print("Compare these numbers with your Sierra Chart 'Period Stats' or 'Trade List' summary.\n")
    print(df.to_string(index=False))
    print("\n============================")
    print("If 'db_trade_count' or 'db_total_pnl' does not match Sierra Chart, please Re-Import that account.")

if __name__ == "__main__":
    audit_accounts()
