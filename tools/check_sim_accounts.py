
import sqlite3

def check_accounts():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT account_name FROM processed_trades WHERE account_name LIKE '3Q_SIM%'")
    accounts = [r[0] for r in c.fetchall()]
    print(f"SIM Accounts in DB: {accounts}")
    conn.close()

if __name__ == "__main__":
    check_accounts()
