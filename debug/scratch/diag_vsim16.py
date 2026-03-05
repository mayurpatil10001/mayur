"""Read-only diagnostic: compare DB trades for V_SIM16 against SC screenshot data."""
import sqlite3
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
IL_TZ = ZoneInfo("Asia/Jerusalem")

db_path = "trading_platform.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=" * 80)
print("DIAGNOSTIC: V_SIM16 trade data in processed_trades")
print("=" * 80)

# 1. Total count
total = conn.execute("SELECT COUNT(*) FROM processed_trades WHERE UPPER(account_name) = 'V_SIM16'").fetchone()[0]
print(f"\nTotal V_SIM16 trades in DB: {total}")

# 2. Symbol breakdown
print("\nSymbol breakdown:")
rows = conn.execute("""
    SELECT symbol, COUNT(*) as cnt, MIN(entry_time) as first_trade, MAX(entry_time) as last_trade
    FROM processed_trades WHERE UPPER(account_name) = 'V_SIM16'
    GROUP BY symbol
""").fetchall()
for r in rows:
    print(f"  {r['symbol']:10s}  count={r['cnt']:6d}  first={r['first_trade']}  last={r['last_trade']}")

# 3. First 10 trades on 2025-12-18 (UTC string match)
print("\n--- First 10 trades where entry_time starts with '2025-12-18' (raw UTC from DB) ---")
rows = conn.execute("""
    SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss
    FROM processed_trades
    WHERE UPPER(account_name) = 'V_SIM16' AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC LIMIT 10
""").fetchall()
for i, r in enumerate(rows):
    # Show raw UTC, NY conversion, and Israel conversion
    try:
        dt_raw = datetime.datetime.fromisoformat(r['entry_time'])
        if dt_raw.tzinfo is None:
            dt_utc = dt_raw.replace(tzinfo=datetime.timezone.utc)
        else:
            dt_utc = dt_raw
        dt_ny = dt_utc.astimezone(NY_TZ)
        dt_il = dt_utc.astimezone(IL_TZ)
        tz_info = f"  NY={dt_ny.strftime('%H:%M:%S')}  IL={dt_il.strftime('%H:%M:%S')}"
    except:
        tz_info = ""
    print(f"  [{i}] UTC={r['entry_time'][:19]}  {r['side']:5s}  qty={r['quantity']}  entry_px={r['entry_price']:.2f}  exit_px={r['exit_price']:.2f}  pnl={r['profit_loss']:+.2f}{tz_info}")

dec18_count = conn.execute("""
    SELECT COUNT(*) FROM processed_trades
    WHERE UPPER(account_name) = 'V_SIM16' AND entry_time LIKE '2025-12-18%'
""").fetchone()[0]
print(f"\n  Total trades on 2025-12-18 (UTC): {dec18_count}")

# 4. SC screenshot reference: first trade is SHORT at ~00:14:42 NY, entry_px ~24986.25, exit_px ~24982.25, pnl ~75.80
# Let's search for ANY trade near that price range on that date
print("\n--- Searching for trades with entry_price near 24986 (within 5 pts) on 2025-12-18 ---")
rows = conn.execute("""
    SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss
    FROM processed_trades
    WHERE UPPER(account_name) = 'V_SIM16' 
    AND entry_time LIKE '2025-12-18%'
    AND entry_price BETWEEN 24981 AND 24991
    ORDER BY entry_time ASC LIMIT 10
""").fetchall()
if rows:
    for r in rows:
        print(f"  {r['entry_time'][:19]}  {r['side']:5s}  qty={r['quantity']}  entry_px={r['entry_price']:.2f}  exit_px={r['exit_price']:.2f}  pnl={r['profit_loss']:+.2f}")
else:
    print("  No trades found near 24986 on 2025-12-18!")

# 5. Check the Performance History popup query
# The popup fetches from /api/v1/trades/?account_name=V_SIM16&symbol=NQ...
# Let me check what the API would return
print("\n--- What the API returns: account_name='V_SIM16' with symbol LIKE 'NQ%' ---")
rows = conn.execute("""
    SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss
    FROM processed_trades
    WHERE UPPER(account_name) = UPPER('V_SIM16') AND symbol LIKE 'NQ' || '%'
    AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r['entry_time'][:19]}  {r['side']:5s}  qty={r['quantity']}  entry_px={r['entry_price']:.2f}  exit_px={r['exit_price']:.2f}  pnl={r['profit_loss']:+.2f}")

# 6. Check the frontend date filter
# The popup uses From: 12/18/2025 and To: 12/18/2025
# But the raw API might use start_date/end_date
# Let's check what handleViewRecent actually sends
print("\n--- How the frontend constructs the URL (need to check Monitoring.tsx) ---")
print("  Will check separately.")

# 7. Check if timestamps are shifted - compare earliest entries across all dates
print("\n--- 5 earliest V_SIM16 trades (any date) ---")
rows = conn.execute("""
    SELECT entry_time, side, entry_price, exit_price, profit_loss
    FROM processed_trades WHERE UPPER(account_name) = 'V_SIM16'
    ORDER BY entry_time ASC LIMIT 5
""").fetchall()
for r in rows:
    print(f"  {r['entry_time'][:19]}  {r['side']:5s}  entry_px={r['entry_price']:.2f}  exit_px={r['exit_price']:.2f}  pnl={r['profit_loss']:+.2f}")

conn.close()
