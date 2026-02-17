
import sqlite3

def check_open_trades():
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n--- Columns in processed_trades ---")
    cursor.execute("PRAGMA table_info(processed_trades)")
    for col in cursor.fetchall():
        print(f"{col['name']} ({col['type']})")
        
    print("\n--- Recent Trades for TM_6 (NQ) ---")
    # Fetch recent trades, specifically looking for ones with 0 pnl or empty fields
    # Note: SQLite stores datetime strings, so sorting by entry_time works
    query = """
    SELECT * FROM processed_trades 
    WHERE account_name = 'TM_6' AND symbol LIKE '%NQ%'
    ORDER BY entry_time DESC
    LIMIT 20
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if not rows:
        print("No trades found for TM_6 and NQ")
    
    col_names = [description[0] for description in cursor.description]
    print("\t".join(col_names))
    
    for row in rows:
        print("\t".join(str(row[col]) for col in col_names))

    print("\n--- POTENTIAL OPEN TRADES (Quantity > 0, PnL=0 or NULL Exit) ---")
    # Check for suspicious trades
    # - null exit_time (if that field exists and is nullable)
    # - 0 exit_price
    # - weird PnL
    
    check_query = """
    SELECT * FROM processed_trades 
    WHERE account_name = 'TM_6' AND symbol LIKE '%NQ%'
    AND (
        exit_time IS NULL 
        OR exit_time = '' 
        OR exit_price IS NULL 
        OR exit_price = 0 
        OR profit_loss = 0
    )
    """
    cursor.execute(check_query)
    suspicious = cursor.fetchall()
    
    if suspicious:
        print(f"Found {len(suspicious)} suspicious trades:")
        for row in suspicious:
            print(f"ID: {row['id']}, Entry: {row['entry_time']}, Exit: {row['exit_time']}, PnL: {row['profit_loss']}, ExitPrice: {row['exit_price']}")
    else:
        print("No suspicious open/incomplete trades found.")

    conn.close()

if __name__ == "__main__":
    check_open_trades()
