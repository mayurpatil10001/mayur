
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

print("Adding indexes to processed_trades...")
c.execute("CREATE INDEX IF NOT EXISTS idx_proc_trades_entry_time ON processed_trades(entry_time)")
c.execute("CREATE INDEX IF NOT EXISTS idx_proc_trades_symbol ON processed_trades(symbol)")

print("Adding indexes to market_data...")
c.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_date ON market_data(symbol, date)")

conn.commit()
conn.close()
print("Done")
