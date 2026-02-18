import sqlite3

def check_vix_range():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM market_data WHERE symbol = 'VIX'")
    min_date, max_date, count = c.fetchone()
    print(f"Earliest: {min_date}")
    print(f"Latest:   {max_date}")
    print(f"Total:    {count}")
    conn.close()

if __name__ == "__main__":
    check_vix_range()
