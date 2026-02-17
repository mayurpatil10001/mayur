
import sqlite3

def check_tm3_fills():
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # We look for trades for TM_3 around the screenshot time: 2026-02-13 ~15:46
    # The user screenshot showed entry at 15:46:33.586
    
    print("Searching for TM_3 trades around 2026-02-13 15:46...")
    
    query = """
    SELECT * FROM processed_trades 
    WHERE account_name LIKE '%TM_3%'
      AND entry_time LIKE '2026-02-13T15:46%'
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} matching trades.")
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"  Entry: {row['entry_time']} @ {row['entry_price']}")
        print(f"  Exit:  {row['exit_time']} @ {row['exit_price']}")
        print(f"  Qty: {row['quantity']}, PnL: {row['profit_loss']}")
        print("-" * 30)

    conn.close()

if __name__ == "__main__":
    check_tm3_fills()
