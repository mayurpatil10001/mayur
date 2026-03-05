import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()

print("Searching for any account name matching 'V_sim' in processed_trades:")
cursor.execute("SELECT DISTINCT account_name FROM processed_trades WHERE account_name LIKE '%V_sim%'")
print(cursor.fetchall())

print("\nSearching for any account matching 'V_sim' in sierra_chart_trades:")
cursor.execute("SELECT DISTINCT account FROM sierra_chart_trades WHERE account LIKE '%V_sim%'")
print(cursor.fetchall())

print("\nSearching for any account matching 'V_sim' in trades:")
cursor.execute("SELECT DISTINCT account FROM trades WHERE account LIKE '%V_sim%'")
print(cursor.fetchall())

conn.close()
