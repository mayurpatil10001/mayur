import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add path for imports
sys.path.append(os.getcwd())
try:
    from trading_platform.services.processed_trade_parser import SierraChartProcessedTradeParser
except ImportError:
    # Fallback if running from root
    sys.path.append(str(Path(os.getcwd()).parent))
    from trading_platform.services.processed_trade_parser import SierraChartProcessedTradeParser

def get_offset(dt):
    # Simplified DST offset for ET (Standard: -5, DST: -4)
    year = dt.year
    march_2nd_sunday = datetime(year, 3, 1) + timedelta(days=(6 - datetime(year, 3, 1).weekday() + 7) % 7 + 7)
    nov_1st_sunday = datetime(year, 11, 1) + timedelta(days=(6 - datetime(year, 11, 1).weekday() + 7) % 7)
    
    if march_2nd_sunday <= dt < nov_1st_sunday:
        return 4 
    else:
        return 5 

def clean_and_reimport():
    db_path = 'trading_platform.db'
    file_path = Path('CL_TS_4.txt')
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return

    print(f"1. NUKING TS_4/CL data from {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Nuclear option: Delete by account and symbol explicit match
    c.execute("DELETE FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL'")
    deleted_count = c.rowcount
    
    # Also delete any that might have different symbol casing or variations if needed, but strict is safer
    conn.commit()
    print(f"   Deleted {deleted_count} trades via SQL.")
    
    print(f"2. Parsing {file_path}...")
    parser = SierraChartProcessedTradeParser()
    try:
        raw_trades = parser.parse_file(file_path)
        print(f"   Parsed {len(raw_trades)} raw trades from file.")
    except Exception as e:
        print(f"   Error parsing file: {e}")
        return

    print("3. Inserting FRESH trades...")
    processed_count = 0
    skipped_count = 0
    
    # Prepare batch insert
    trades_data = []
    
    for raw in raw_trades:
        try:
            # Timezone Conversion: Local (ET) -> UTC
            entry_offset = get_offset(raw.entry_datetime)
            exit_offset = get_offset(raw.exit_datetime)
            
            entry_utc = raw.entry_datetime + timedelta(hours=entry_offset)
            exit_utc = raw.exit_datetime + timedelta(hours=exit_offset)
            
            # Deterministic ID to prevent duplicates if re-run
            # We use 100 multiplier for price to avoid float errors in ID
            trade_id = f"TS_4_CL_{entry_utc.strftime('%Y%m%d_%H%M%S')}_{int(raw.entry_price*100)}_{int(raw.profit_loss*100)}_{raw.trade_quantity}"
            
            duration_minutes = int((exit_utc - entry_utc).total_seconds() / 60)
            
            # Tuple for bulk insert
            trades_data.append((
                trade_id,
                'TS_4', 
                'CL',
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
            
        except Exception as e:
            print(f"   Error processing trade: {e}")
            skipped_count += 1

    # Batch Insert
    c.executemany("""
    INSERT OR REPLACE INTO processed_trades (
        trade_id, account_name, symbol,
        entry_time, exit_time,
        entry_price, exit_price,
        quantity, side, profit_loss, commission,
        duration_minutes, hour_of_day, day_of_week
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, trades_data)
    
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
