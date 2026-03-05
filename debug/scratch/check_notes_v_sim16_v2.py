import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()

print("Checking sierra_chart_trades for V_sim16 with empty/null notes:")
cursor.execute("""
    SELECT count(*) FROM sierra_chart_trades 
    WHERE account = 'V_sim16' 
    AND (note IS NULL OR note = '' OR note = ' ')
""")
count = cursor.fetchone()[0]
print(f"Total trades with empty note: {count}")

cursor.execute("SELECT count(*) FROM sierra_chart_trades WHERE account = 'V_sim16'")
total = cursor.fetchone()[0]
print(f"Total trades for V_sim16: {total}")

print("\nChecking 'trades' table for V_sim16 with empty/null notes:")
# First check columns for 'trades' table to be sure
cursor.execute("PRAGMA table_info(trades)")
trades_cols = [col[1] for col in cursor.fetchall()]
print(f"Columns in 'trades': {trades_cols}")

account_col = 'account_name' if 'account_name' in trades_cols else 'account' if 'account' in trades_cols else None

if account_col:
    cursor.execute(f"""
        SELECT count(*) FROM trades 
        WHERE {account_col} = 'V_sim16' 
        AND (notes IS NULL OR notes = '' OR notes = ' ')
    """)
    count_t = cursor.fetchone()[0]
    print(f"Total trades with empty notes: {count_t}")
else:
    print("Could not find account column in 'trades' table.")

conn.close()
