
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'trading_platform', 'services'))
from binary_log_parser import BinaryLogParser, _parse_file_nitro

def check_stateful():
    base_path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    files = [
        os.path.join(base_path, "TradeActivityLog_2026-02-16_UTC.3Q_sim14.data"),
        os.path.join(base_path, "TradeActivityLog_2026-02-17_UTC.3Q_sim14.data"),
    ]
    
    # Use real DB since code now connects to self.db_path
    # We will use "temp_stateful.db" to avoid messing up prod
    DB_NAME = "temp_stateful.db"
    
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS pending_fills (  id INTEGER PRIMARY KEY AUTOINCREMENT,  account_name TEXT, symbol TEXT,   side TEXT,   entry_time TEXT,   price REAL,   quantity INTEGER,   source_file TEXT,   created_at DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()
    
    parser = BinaryLogParser(DB_NAME)
    
    print("--- STATEFUL RUN ---")
    
    total_trades = 0
    total_unpaired = 0
    
    for f in files:
        print(f"\nProcessing {os.path.basename(f)}...")
        fills = _parse_file_nitro(f)
        fills.sort(key=lambda x: x['timestamp'])
        
        # Enable state persistence
        trades, unpaired = parser._pairs_to_trades(fills, persist_state=True)
        print(f"  Trades: {len(trades)}, Unpaired (carried forward): {unpaired}")
        total_trades += len(trades)
        total_unpaired = unpaired # Unpaired at end is strictly the leftovers
        
    print(f"\nTotal Trades Generated: {total_trades}")
    print(f"Final Unpaired Stuck: {total_unpaired}")
    
    # Check pending
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    rows = c.execute("SELECT COUNT(*) FROM pending_fills").fetchone()[0]
    print(f"Rows in pending_fills table: {rows}")
    conn.close()
    
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

if __name__ == "__main__":
    check_stateful()
