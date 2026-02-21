
import sqlite3
import os

db_path = 'trading_platform.db'
if not os.path.exists(db_path):
    print("DB not found")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    # 1. Create a temporary table with cleaned daily data
    print("Creating temporary table...")
    c.execute("DROP TABLE IF EXISTS market_data_clean")
    c.execute("""
    CREATE TABLE market_data_clean AS
    SELECT 
        MIN(id) as id,
        symbol,
        substr(date, 1, 10) as date,
        AVG(open_price) as open_price,
        AVG(high_price) as high_price,
        AVG(low_price) as low_price,
        AVG(close_price) as close_price,
        SUM(volume) as volume,
        AVG(adjusted_close) as adjusted_close,
        MIN(created_timestamp) as created_timestamp
    FROM market_data
    GROUP BY symbol, substr(date, 1, 10)
    """)
    print(f"Aggregated {c.rowcount} raw records into daily records")

    # 2. Clear original table
    print("Clearing original table...")
    c.execute("DELETE FROM market_data")

    # 3. Insert cleaned data back
    print("Restoring cleaned data...")
    c.execute("""
    INSERT INTO market_data (id, symbol, date, open_price, high_price, low_price, close_price, volume, adjusted_close, created_timestamp)
    SELECT id, symbol, date, open_price, high_price, low_price, close_price, volume, adjusted_close, created_timestamp
    FROM market_data_clean
    """)
    print(f"Restored {c.rowcount} records")

    # 4. Cleanup
    c.execute("DROP TABLE market_data_clean")
    
    conn.commit()
    print("Successfully cleaned market_data table")
except Exception as e:
    conn.rollback()
    print(f"Error: {e}")
finally:
    conn.close()
