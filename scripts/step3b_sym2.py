import sqlite3, collections

db = sqlite3.connect('trading_platform_clean_v2.db')
db.row_factory = sqlite3.Row

# Check multi-symbol asset_list
print("Multi-symbol samples:")
for r in db.execute("SELECT asset_list FROM file_audit WHERE asset_list LIKE '%,%' LIMIT 5").fetchall():
    print("  ", repr(r['asset_list']))

# Count unique formats
distinct = db.execute("SELECT DISTINCT asset_list FROM file_audit WHERE asset_list IS NOT NULL LIMIT 20").fetchall()
print("\nDistinct asset_list values (sample):")
for r in distinct:
    print("  ", repr(r['asset_list']))

# Parse by splitting on comma or treating as plain string
def parse_assets(s):
    if not s:
        return []
    # Try comma-separated first
    parts = [p.strip() for p in s.split(',') if p.strip()]
    return parts

sym_excl = collections.Counter()
sym_full = collections.Counter()

for r in db.execute("SELECT asset_list FROM file_audit WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%'").fetchall():
    for s in parse_assets(r['asset_list']):
        sym_excl[s] += 1

for r in db.execute("SELECT asset_list FROM file_audit").fetchall():
    for s in parse_assets(r['asset_list']):
        sym_full[s] += 1

te = sum(sym_excl.values())
tf = sum(sym_full.values())
print(f"\nParsed: excl={te:,}, full={tf:,}")
print()
print(f"{'Symbol':8s}  {'excl':6s}  {'full':7s}  {'excl%':7s}  {'full%':7s}  ratio  flag")
print("-"*65)
for sym, cnt in sym_excl.most_common(20):
    fn = sym_full.get(sym, 0)
    er = cnt / te if te else 0
    fr = fn / tf if tf else 0
    ratio = er / fr if fr else 0
    flag = "*** HIGH" if ratio > 1.5 else ("LOW" if ratio < 0.7 else "ok")
    print(f"{sym:8s}  {cnt:6,}  {fn:7,}  {er:6.1%}  {fr:6.1%}  {ratio:5.2f}x  {flag}")

db.close()
