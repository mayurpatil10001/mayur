
import sqlite3

def deduplicate_trades():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    print("Finding duplicates...")
    cursor.execute("""
    SELECT entry_time, account_name, symbol, profit_loss, COUNT(*) 
    FROM processed_trades 
    GROUP BY entry_time, account_name, symbol, profit_loss 
    HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    print(f"Found {len(duplicates)} unique sets of duplicates.")
    
    if not duplicates:
        print("No duplicates to remove.")
        conn.close()
        return

    # Create a temporary table with unique rows (excluding trade_id)
    print("Creating temporary unique table...")
    # Group by the content columns that define a unique trade event
    cursor.execute("""
    CREATE TABLE processed_trades_new AS 
    SELECT * FROM processed_trades 
    GROUP BY account_name, symbol, entry_time, profit_loss, entry_price, quantity
    """)
    
    # Check counts
    cursor.execute("SELECT COUNT(*) FROM processed_trades")
    old_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM processed_trades_new")
    new_count = cursor.fetchone()[0]
    
    print(f"Old count: {old_count}")
    print(f"New count: {new_count}")
    print(f"Removed: {old_count - new_count} rows.")
    
    # Replace old table
    print("Replacing old table...")
    cursor.execute("DROP TABLE processed_trades")
    cursor.execute("ALTER TABLE processed_trades_new RENAME TO processed_trades")
    
    # Re-create index (check if it existed)
    print("Re-creating index...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON processed_trades(symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_time ON processed_trades(entry_time)")
    
    conn.commit()
    conn.close()
    print("De-duplication complete.")

if __name__ == "__main__":
    deduplicate_trades()
