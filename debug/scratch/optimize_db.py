import sqlite3
DB = "trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Creating indexes to optimize dashboard performance...")
try:
    c.execute("CREATE INDEX IF NOT EXISTS idx_trades_acc_sym ON processed_trades (account_name, symbol)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON processed_trades (exit_time)")
    # Super index for dashboard aggregations
    print("Creating super covering index (this might take a few minutes)...")
    c.execute("CREATE INDEX IF NOT EXISTS idx_dashboard_covering ON processed_trades (account_name, symbol, profit_loss, entry_time, exit_time)")
    print("Indexes created.")
except Exception as e:
    print(f"Error creating indexes: {e}")

print("Running ANALYZE...")
c.execute("ANALYZE")
print("Optimization complete.")

conn.commit()
conn.close()
