import sqlite3
from collections import defaultdict

conn = sqlite3.connect('trading_platform.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Permutations to check
# 1: V_sim16, Mon (1), 09:30
# 2: TM_1, Thu (4), 14:00

query = """
WITH CalculatedSlots AS (
    SELECT 
        entry_time, 
        account_name, 
        profit_loss, 
        CAST(strftime('%w', entry_time) AS INTEGER) as dow,
        printf('%02d:%02d', 
            CAST(strftime('%H', entry_time) AS INTEGER), 
            CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
        ) as slot
    FROM processed_trades 
    WHERE symbol = 'NQ' 
      AND entry_time >= '2025-10-01'
)
SELECT * FROM CalculatedSlots
WHERE (
    (account_name = 'V_sim16' AND dow = 1 AND slot = '09:30')
    OR 
    (account_name = 'TM_1' AND dow = 4 AND slot = '14:00')
)
ORDER BY ABS(profit_loss) DESC 
LIMIT 50
"""

results = cursor.execute(query).fetchall()

print(f"{'Time':<20} | {'Account':<12} | {'PnL':<10} | {'Slot':<5} | {'DoW'}")
print("-" * 60)
for r in results:
    is_outlier = " [OUTLIER]" if abs(r['profit_loss']) > 5000 else ""
    print(f"{r['entry_time']:<20} | {r['account_name']:<12} | {r['profit_loss']:>10.2f} | {r['slot']:<5} | {r['dow']}{is_outlier}")

conn.close()
