import sqlite3

# Check scratch DB
scratch = sqlite3.connect(r'c:\SC_results_WF\scratch_parser_test.db')
print("=== SCRATCH DB: TM_7 variants ===")
for r in scratch.execute("SELECT account_name, symbol, COUNT(*) n FROM processed_trades WHERE account_name LIKE '%TM%7%' GROUP BY account_name, symbol ORDER BY n DESC"):
    print(f"  {r[0]:<30} {r[1]:<8} n={r[2]}")
print(f"\n  Total rows in processed_trades: {scratch.execute('SELECT COUNT(*) FROM processed_trades').fetchone()[0]:,}")
scratch.close()

# Check ORIGINAL DB 
orig = sqlite3.connect(r'c:\SC_results_WF\trading_platform.db')
print("\n=== ORIGINAL DB: TM_7 variants ===")
for r in orig.execute("SELECT account_name, symbol, COUNT(*) n, MIN(entry_time) mn, MAX(entry_time) mx FROM processed_trades WHERE account_name LIKE '%TM%7%' GROUP BY account_name, symbol ORDER BY n DESC"):
    print(f"  {r[0]:<30} {r[1]:<8} n={r[2]}  {r[3][:10]} -> {r[4][:10]}")
orig.close()

# Check import log for save lines
print("\n=== import_debug.log: save/insert lines for TM_7 ===")
with open(r'c:\SC_results_WF\import_debug.log', 'r', errors='ignore') as f:
    lines = f.readlines()
save_lines = [l for l in lines if ('save' in l.lower() or 'insert' in l.lower() or 'wrote' in l.lower() or 'trade' in l.lower()) and 'TM_7' in l.upper()]
print(f"  Found {len(save_lines)} save/insert lines mentioning TM_7")
for l in save_lines[:20]:
    print(f"  {l.rstrip()}")

# Also look at last 50 lines of import log
print("\n=== Last 50 lines of import_debug.log ===")
for l in lines[-50:]:
    print(f"  {l.rstrip()}")
