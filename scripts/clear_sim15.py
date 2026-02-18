
import sqlite3

def clear_sim15():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    print("Deleting existing trades for 3Q_SIM15...")
    c.execute("DELETE FROM processed_trades WHERE account_name = '3Q_SIM15'")
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    print(f"Deleted {deleted} trades for 3Q_SIM15.")

if __name__ == "__main__":
    clear_sim15()
