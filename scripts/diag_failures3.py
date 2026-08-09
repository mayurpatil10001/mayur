import sqlite3

db = sqlite3.connect('trading_platform_clean_v2.db')
db.row_factory = sqlite3.Row

oldest_all = db.execute('SELECT MIN(trade_date) FROM file_audit').fetchone()[0]
newest_all = db.execute('SELECT MAX(trade_date) FROM file_audit').fetchone()[0]

year_fails = db.execute(
    "SELECT substr(trade_date,1,4) as yr, COUNT(*) as n FROM file_audit "
    "WHERE integrity_ok=0 AND ghost_fills=0 AND (flag_reason IS NULL OR flag_reason='') "
    "GROUP BY yr ORDER BY yr"
).fetchall()

year_all = db.execute(
    "SELECT substr(trade_date,1,4) as yr, COUNT(*) as n, "
    "SUM(CASE WHEN integrity_ok=0 THEN 1 ELSE 0 END) as fails "
    "FROM file_audit GROUP BY yr ORDER BY yr"
).fetchall()

print(f'Dataset date range: {oldest_all} -> {newest_all}')
print()
print('Year | total_files | all_integrity_fails | pure_natural_fail | rate')
print('-'*75)
yr_map = {}
for r in year_fails:
    yr_map[r['yr']] = r['n']

for r in year_all:
    pfail = yr_map.get(r['yr'], 0)
    pct = pfail/r['n']*100 if r['n'] > 0 else 0
    print(f"  {r['yr']}  {r['n']:8,}  {r['fails']:8,}  {pfail:8,}  {pct:.1f}%")

total_pure = sum(yr_map.values())
total_files = db.execute('SELECT COUNT(*) FROM file_audit').fetchone()[0]
print()
print(f'Total pure natural failures: {total_pure:,} / {total_files:,} ({total_pure/total_files*100:.2f}%)')

# Top accounts with pure natural failures
top_accts = db.execute(
    "SELECT account, COUNT(*) as n FROM file_audit "
    "WHERE integrity_ok=0 AND ghost_fills=0 AND (flag_reason IS NULL OR flag_reason='') "
    "GROUP BY account ORDER BY n DESC LIMIT 10"
).fetchall()
print()
print('Top accounts: pure natural failures')
for r in top_accts:
    print(f"  {r['account']:30s}: {r['n']:5,}")

# The specific 2-fill pattern count
twofill = db.execute(
    "SELECT COUNT(*) FROM file_audit "
    "WHERE integrity_ok=0 AND ghost_fills=0 AND total_raw_fills=2 "
    "AND (flag_reason IS NULL OR flag_reason='')"
).fetchone()[0]
print()
print(f'2-fill pure natural failures: {twofill:,}')

db.close()
