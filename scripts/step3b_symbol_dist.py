import sqlite3, json, collections

db = sqlite3.connect('trading_platform_clean_v2.db')
db.row_factory = sqlite3.Row

# Sample asset_list format
rows = db.execute('SELECT asset_list FROM file_audit WHERE asset_list IS NOT NULL LIMIT 5').fetchall()
print('asset_list samples:')
for r in rows:
    print(' ', repr(r['asset_list']))
print()

sym_excl = collections.Counter()
sym_full = collections.Counter()

for r in db.execute('SELECT asset_list FROM file_audit WHERE integrity_ok=0 AND flag_reason NOT LIKE "%rejected_fills%"').fetchall():
    try:
        assets = json.loads(r['asset_list'])
        for s in assets:
            sym_excl[s] += 1
    except Exception:
        try:
            import ast
            assets = ast.literal_eval(r['asset_list'] or '[]')
            for s in assets:
                sym_excl[s] += 1
        except Exception:
            pass

for r in db.execute('SELECT asset_list FROM file_audit').fetchall():
    try:
        assets = json.loads(r['asset_list'])
        for s in assets:
            sym_full[s] += 1
    except Exception:
        try:
            import ast
            assets = ast.literal_eval(r['asset_list'] or '[]')
            for s in assets:
                sym_full[s] += 1
        except Exception:
            pass

te = sum(sym_excl.values())
tf = sum(sym_full.values())
print(f'Parsed: excl={te}, full={tf}')
print()
print(f'{"Sym":8s}  {"excl":6s}  {"full":7s}  {"excl%":7s}  {"full%":7s}  ratio  flag')
print('-'*65)
for sym, cnt in sym_excl.most_common(20):
    fn = sym_full.get(sym, 0)
    er = cnt / te if te else 0
    fr = fn / tf if tf else 0
    ratio = er / fr if fr else 0
    flag = '*** HIGH' if ratio > 1.5 else ('LOW' if ratio < 0.7 else 'ok')
    print(f'{sym:8s}  {cnt:6,}  {fn:7,}  {er:6.1%}  {fr:6.1%}  {ratio:5.2f}x  {flag}')

# bypass_mode
print()
print('bypass_mode distribution:')
total_excl = 3708
total_full = 61706
bp_excl = db.execute('SELECT bypass_mode, COUNT(*) n FROM file_audit WHERE integrity_ok=0 AND flag_reason NOT LIKE "%rejected_fills%" GROUP BY bypass_mode').fetchall()
bp_full = {r['bypass_mode']: r['n'] for r in db.execute('SELECT bypass_mode, COUNT(*) n FROM file_audit GROUP BY bypass_mode').fetchall()}
for r in bp_excl:
    fn = bp_full.get(r['bypass_mode'], 1)
    er = r['n'] / total_excl
    fr = fn / total_full
    ratio = er / fr if fr else 0
    flag = '*** HIGH' if ratio > 1.5 else ('LOW' if ratio < 0.7 else 'ok')
    print(f'  bypass={r["bypass_mode"]}: excl={r["n"]:,} ({er:.1%}) full={fn:,} ({fr:.1%}) ratio={ratio:.2f}x  {flag}')

db.close()
print()
print('DONE')
