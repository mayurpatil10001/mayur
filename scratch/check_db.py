import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

print("Indexes on processed_trades:")
for row in conn.execute("PRAGMA index_list('processed_trades')"):
    print(row)
    idx_name = row[1]
    print(f"  Columns in {idx_name}:")
    for col in conn.execute(f"PRAGMA index_info('{idx_name}')"):
        print(f"    {col}")

print("\nTable size:")
print(conn.execute("SELECT COUNT(*) FROM processed_trades").fetchone())

conn.close()
