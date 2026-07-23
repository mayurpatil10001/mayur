import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

# verification_trades status
c.execute('SELECT COUNT(*) FROM verification_trades')
vt = c.fetchone()[0]
print('verification_trades count:', vt)

# processed_trades date range
c.execute('SELECT MIN(entry_time), MAX(entry_time), COUNT(*) FROM processed_trades')
r = c.fetchone()
print('processed_trades date range:', r[0], '->', r[1], '| total:', r[2])

# processed_trades by year
c.execute("SELECT substr(entry_time,1,4) as yr, COUNT(*) FROM processed_trades GROUP BY yr ORDER BY yr")
print('processed_trades by year:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]:,} trades')

# Distinct account count
c.execute("SELECT COUNT(DISTINCT account_name) FROM processed_trades")
print('Distinct accounts:', c.fetchone()[0])

# Check coverage against target range 2023-09-04 to 2025-10-31
c.execute("SELECT COUNT(*) FROM processed_trades WHERE entry_time >= '2023-09-04' AND entry_time <= '2025-10-31'")
in_range = c.fetchone()[0]
print('Trades in target range (2023-09-04 to 2025-10-31):', in_range)

c.execute("SELECT COUNT(*) FROM processed_trades WHERE entry_time < '2023-09-04'")
before = c.fetchone()[0]
print('Trades BEFORE target range:', before)

c.execute("SELECT COUNT(*) FROM processed_trades WHERE entry_time > '2025-10-31'")
after = c.fetchone()[0]
print('Trades AFTER target range:', after)

# Trading days count
c.execute("SELECT COUNT(DISTINCT substr(entry_time,1,10)) FROM processed_trades WHERE entry_time >= '2023-09-04' AND entry_time <= '2025-10-31'")
tdays = c.fetchone()[0]
print('Distinct trading days in target range:', tdays)

conn.close()
