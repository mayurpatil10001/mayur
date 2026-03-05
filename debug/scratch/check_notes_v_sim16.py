import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()

print("Checking sierra_chart_trades for V_sim16 with empty/null notes:")
cursor.execute("""
    SELECT count(*) FROM sierra_chart_trades 
    WHERE account_name = 'V_sim16' 
    AND (note IS NULL OR note = '' OR note = ' ')
""")
count = cursor.fetchone()[0]
print(f"Total trades with empty note: {count}")

cursor.execute("SELECT count(*) FROM sierra_chart_trades WHERE account_name = 'V_sim16'")
total = cursor.fetchone()[0]
print(f"Total trades for V_sim16: {total}")

conn.close()
