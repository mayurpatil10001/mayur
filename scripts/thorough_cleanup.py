
import sqlite3

def thorough_cleanup():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    # 1. Clean processed_trades
    print("Cleaning processed_trades...")
    cursor.execute("DELETE FROM processed_trades WHERE symbol IN ('CL', 'T', 'Unknown')")
    print(f"  Deleted {cursor.rowcount} records from processed_trades.")
    
    # 2. Clean accounts
    print("Cleaning accounts...")
    cursor.execute("DELETE FROM accounts WHERE base_symbol IN ('CL', 'T', 'Unknown')")
    print(f"  Deleted {cursor.rowcount} records from accounts.")
    
    # 3. Clean sierra_chart_trades (if it contains similar info)
    print("Cleaning sierra_chart_trades...")
    try:
        cursor.execute("DELETE FROM sierra_chart_trades WHERE symbol IN ('CL', 'T', 'Unknown')")
        print(f"  Deleted {cursor.rowcount} records from sierra_chart_trades.")
    except Exception as e:
        print(f"  Note: sierra_chart_trades doesn't have symbol column or failed: {e}")

    conn.commit()
    conn.close()
    print("Cleanup finished.")

if __name__ == '__main__':
    thorough_cleanup()
