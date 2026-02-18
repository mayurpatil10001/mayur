import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add path for imports
sys.path.append(os.getcwd())
from trading_platform.services.processed_trade_parser import SierraChartProcessedTradeParser

def get_offset(dt):
    # Simplified DST offset for ET (Standard: -5, DST: -4)
    # DST starts 2nd Sunday in March, ends 1st Sunday in Nov
    year = dt.year
    march_2nd_sunday = datetime(year, 3, 1) + timedelta(days=(6 - datetime(year, 3, 1).weekday() + 7) % 7 + 7)
    nov_1st_sunday = datetime(year, 11, 1) + timedelta(days=(6 - datetime(year, 11, 1).weekday() + 7) % 7)
    
    if march_2nd_sunday <= dt < nov_1st_sunday:
        return 4 # UTC is +4 hours ahead of EDT
    else:
        return 5 # UTC is +5 hours ahead of EST

def clean_and_reimport():
    db_path = 'trading_platform.db'
    file_path = Path('CL_TS_4.txt')
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return

    print(f"1. Clearing existing TS_4/CL trades from {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get count before delete
    c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL'")
    before_count = c.fetchone()[0]
    print(f"   Trades before delete: {before_count}")
    
    # Delete
    c.execute("DELETE FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL'")
    deleted_count = c.rowcount
    conn.commit()
    print(f"   Deleted {deleted_count} trades.")
    
    print(f"2. Parsing {file_path}...")
    parser = SierraChartProcessedTradeParser()
    try:
        raw_trades = parser.parse_file(file_path)
        print(f"   Parsed {len(raw_trades)} raw trades from file.")
    except Exception as e:
        print(f"   Error parsing file: {e}")
        return

    print("3. Converting and inserting into DB...")
    processed_count = 0
    skipped_count = 0
    
    for raw in raw_trades:
        try:
            # Convert to processed trade
            # Note: The parser's convert_to_processed_trade handles basic conversion
            # But duplicate check logic is usually inside the loop or DB constraints
            
            # We must handle timezone carefully. 
            # Sierra Chart file is in Local Time (ET).
            # DB expects UTC.
            # We add offset to convert Local -> UTC.
            
            entry_offset = get_offset(raw.entry_datetime)
            exit_offset = get_offset(raw.exit_datetime)
            
            entry_utc = raw.entry_datetime + timedelta(hours=entry_offset)
            exit_utc = raw.exit_datetime + timedelta(hours=exit_offset)
            
            # Reconstruct Trade ID to be deterministic based on UTC time and price
            # Using specific fields to match unique trade
            trade_id = f"TS_4_CL_{entry_utc.strftime('%Y%m%d_%H%M%S')}_{int(raw.entry_price*100)}_{int(raw.profit_loss*100)}_{raw.trade_quantity}"
            
            duration_minutes = int((exit_utc - entry_utc).total_seconds() / 60)
            
            # Insert
            c.execute("""
            INSERT INTO processed_trades (
                trade_id, account_name, symbol,
                entry_time, exit_time,
                entry_price, exit_price,
                quantity, side, profit_loss, commission,
                duration_minutes, hour_of_day, day_of_week
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                'TS_4', # Force correct account name
                'CL',   # Force correct symbol
                entry_utc.isoformat(),
                exit_utc.isoformat(),
                raw.entry_price,
                raw.exit_price,
                raw.trade_quantity,
                "LONG" if raw.trade_type.lower() in ["long", "buy"] else "SHORT",
                raw.profit_loss,
                raw.commission,
                duration_minutes,
                entry_utc.hour,
                entry_utc.weekday()
            ))
            processed_count += 1
            
        except sqlite3.IntegrityError:
            print(f"   Duplicate trade skipped: {raw.entry_datetime} {raw.entry_price}")
            skipped_count += 1
        except Exception as e:
            print(f"   Error inserting trade: {e}")
            skipped_count += 1

    conn.commit()
    conn.close()
    
    print("4. Verification")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(profit_loss) FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL'")
    final_res = c.fetchone()
    print(f"   Final DB Count: {final_res[0]}")
    print(f"   Final DB PnL: {final_res[1]}")
    conn.close()

if __name__ == "__main__":
    clean_and_reimport()
