"""
Step 0 — Data Inspection Before Any Code Change
Inspect the staging DB and raw binary files to understand:
1. Which accounts/dates produce impossible PnL
2. Actual fill quantity distribution across the dataset
3. Actual price distributions per symbol
4. What the raw parser output looks like for known-bad accounts
"""
import sys, os, sqlite3, re, struct, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

DB = 'trading_platform_clean_v2.db'

print('=' * 70)
print('SECTION A: Files with |dirty_net| > $1M')
print('=' * 70)
con = sqlite3.connect(DB)

rows = con.execute('''
    SELECT account, trade_date,
           total_raw_fills, ghost_fills,
           dirty_trades, clean_trades,
           ROUND(dirty_net, 2)  AS dirty_net,
           ROUND(clean_net, 2)  AS clean_net,
           flag_reason
    FROM file_audit
    WHERE ABS(dirty_net) > 1000000
    ORDER BY ABS(dirty_net) DESC
    LIMIT 30
''').fetchall()

print('Rank  Account                   Date         raw  ghosts  d_trd  c_trd   dirty_net              clean_net')
print('-' * 110)
for i, r in enumerate(rows, 1):
    acct, date, raw, gh, dt, ct, dn, cn, fr = r
    acct = str(acct or '')[:24]
    date = str(date or '')[:12]
    dn_s = '{:,.0f}'.format(dn) if dn is not None else 'N/A'
    cn_s = '{:,.0f}'.format(cn) if cn is not None else 'N/A'
    print(str(i).rjust(4) + '  ' + acct.ljust(24) + '  ' + date.ljust(12) +
          str(raw or 0).rjust(5) + str(gh or 0).rjust(8) +
          str(dt or 0).rjust(7) + str(ct or 0).rjust(7) +
          '  ' + dn_s.rjust(20) + '  ' + cn_s.rjust(20))

print()
print('=' * 70)
print('SECTION B: Per-account aggregate (top 20 by |dirty_net|)')
print('=' * 70)
rows2 = con.execute('''
    SELECT account,
           COUNT(*)             AS files,
           SUM(total_raw_fills) AS raw,
           SUM(ghost_fills)     AS ghosts,
           SUM(clean_trades)    AS c_trades,
           ROUND(SUM(dirty_net), 2) AS dirty_net,
           ROUND(SUM(clean_net), 2) AS clean_net,
           SUM(flagged)         AS flagged
    FROM file_audit
    GROUP BY account
    ORDER BY ABS(SUM(dirty_net)) DESC
    LIMIT 20
''').fetchall()

print('Account                    files    raw    ghosts  trades     dirty_net_total        clean_net_total  flagged')
print('-' * 115)
for r in rows2:
    acct, files, raw, gh, ct, dn, cn, fl = r
    acct = str(acct or '')[:24]
    dn_s = '{:,.0f}'.format(dn) if dn is not None else 'N/A'
    cn_s = '{:,.0f}'.format(cn) if cn is not None else 'N/A'
    print(acct.ljust(26) +
          str(files or 0).rjust(6) +
          str(raw or 0).rjust(8) +
          str(gh or 0).rjust(9) +
          str(ct or 0).rjust(8) +
          '  ' + dn_s.rjust(22) +
          '  ' + cn_s.rjust(22) +
          str(fl or 0).rjust(9))

print()
print('=' * 70)
print('SECTION C: Quantity distribution across ALL clean_trades')
print('=' * 70)
q_rows = con.execute('''
    SELECT quantity, COUNT(*) as cnt
    FROM clean_trades
    GROUP BY quantity
    ORDER BY quantity
''').fetchall()
total_trades = sum(r[1] for r in q_rows)
print('Qty   Count         % of all trades')
print('-' * 45)
cumulative = 0
for qty, cnt in q_rows:
    pct = 100.0 * cnt / total_trades if total_trades > 0 else 0
    cumulative += cnt
    cum_pct = 100.0 * cumulative / total_trades if total_trades > 0 else 0
    bar = '#' * min(40, int(pct / 2))
    print(str(qty).rjust(4) + '  ' + str(cnt).rjust(10) + '  ' +
          ('{:.2f}%'.format(pct)).rjust(8) + '  cum=' +
          ('{:.1f}%'.format(cum_pct)).rjust(6) + '  ' + bar)
    if qty > 200:
        remaining = [(r[0], r[1]) for r in q_rows if r[0] > qty]
        if remaining:
            print('  ... ' + str(len(remaining)) + ' more quantity values above ' + str(qty))
        break

print()
print('=' * 70)
print('SECTION D: Price distribution per base_symbol in clean_trades')
print('=' * 70)
sym_rows = con.execute('''
    SELECT base_symbol,
           COUNT(*) cnt,
           MIN(entry_price)   p_min,
           MAX(entry_price)   p_max,
           AVG(entry_price)   p_avg,
           MIN(exit_price)    x_min,
           MAX(exit_price)    x_max
    FROM clean_trades
    WHERE entry_price > 0
    GROUP BY base_symbol
    ORDER BY cnt DESC
''').fetchall()
print('Symbol   Trades   EntryPmin       EntryPmax     EntryPavg    ExitPmin     ExitPmax')
print('-' * 90)
for r in sym_rows:
    sym, cnt, pmin, pmax, pavg, xmin, xmax = r
    sym = str(sym or 'UNK')[:8]
    print(sym.ljust(9) + str(cnt).rjust(7) +
          '{:>16,.2f}'.format(pmin or 0) +
          '{:>16,.2f}'.format(pmax or 0) +
          '{:>14,.2f}'.format(pavg or 0) +
          '{:>14,.2f}'.format(xmin or 0) +
          '{:>14,.2f}'.format(xmax or 0))

print()
print('=' * 70)
print('SECTION E: Max single-trade PnL observed (top outliers)')
print('=' * 70)
outliers = con.execute('''
    SELECT account, base_symbol, trade_date, direction, quantity,
           ROUND(entry_price, 2) ep,
           ROUND(exit_price, 2)  xp,
           ROUND(pnl_dollars, 2) pnl,
           source_file
    FROM clean_trades
    WHERE ABS(pnl_dollars) > 500000
    ORDER BY ABS(pnl_dollars) DESC
    LIMIT 30
''').fetchall()
print('Account                Symbol  Date         Dir  Qty    Entry       Exit        PnL_dollars')
print('-' * 100)
for r in outliers:
    acct, sym, date, dire, qty, ep, xp, pnl, sf = r
    acct = str(acct or '')[:22]
    sym  = str(sym or '')[:7]
    date = str(date or '')[:12]
    dire = str(dire or '')[:5]
    print(acct.ljust(23) + sym.ljust(8) + date.ljust(13) +
          (dire or '').ljust(6) + str(qty or 0).rjust(4) +
          '{:>12,.2f}'.format(ep or 0) +
          '{:>12,.2f}'.format(xp or 0) +
          '{:>18,.2f}'.format(pnl or 0))

con.close()
print()
print('Done.')
