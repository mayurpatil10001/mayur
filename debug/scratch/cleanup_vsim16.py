import sqlite3
import os

def cleanup_vsim16():
    db_path = 'trading_platform.db'
    if not os.path.exists(db_path):
        print("DB not found")
        return
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("Cleaning up V_SIM16 data for a fresh import...")
    # Delete from processed_trades
    c.execute("DELETE FROM processed_trades WHERE account_name='V_SIM16'")
    print(f"Deleted {c.rowcount} trades.")
    
    # Delete from pending_fills
    c.execute("DELETE FROM pending_fills WHERE account_name='V_SIM16'")
    print(f"Deleted {c.rowcount} pending fills.")
    
    conn.commit()
    conn.close()
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_vsim16()
