
import sqlite3

def inspect_trades():
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    for account in ['TM_6', 'TM_3']:
        print(f"\n--- Checking Account: {account} ---")
        
        # Check count
        cursor.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = ?", (account,))
        count = cursor.fetchone()[0]
        print(f"Total trades: {count}")
        
        if count == 0:
            continue
            
        # Get last 5 trades
        cursor.execute("""
            SELECT * FROM processed_trades 
            WHERE account_name = ? 
            ORDER BY entry_time DESC 
            LIMIT 5
        """, (account,))
        
        rows = cursor.fetchall()
        print("Last 5 trades:")
        for row in rows:
            print(f"  Entry: {row['entry_time']}, Exit: {row['exit_time']}, Qty: {row['quantity']}, PnL: {row['profit_loss']}, ExitPrice: {row['exit_price']}, Symbol: {row['symbol']}")

        # distinct symbols
        cursor.execute("SELECT DISTINCT symbol FROM processed_trades WHERE account_name = ?", (account,))
        symbols = [r[0] for r in cursor.fetchall()]
        print(f"Symbols: {symbols}")

    conn.close()

if __name__ == "__main__":
    inspect_trades()
