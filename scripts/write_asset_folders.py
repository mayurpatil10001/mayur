"""
scripts/write_asset_folders.py
================================
Reads clean_trades from the SQLite database and writes per-symbol CSVs
into the data_clean/{SYMBOL}/trades/ and audit/ folder structure.

Run after ghost_fill_cleaner.py completes a batch.

Usage:
    python scripts/write_asset_folders.py [--db path/to/db] [--since YYYY-MM-DD]
"""
import os, sys, csv, json, argparse, sqlite3, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from ghost_fill_cleaner import OUTPUT_DB as DB_PATH   # reuse the configured DB path

KNOWN_SYMBOLS = {
    'ES','MES','NQ','MNQ','CL','MCL','FDAX','RTY','M2K','GC','YM','MYM','ZB','SI'
}
OUTPUT_ROOT = 'data_clean'

TRADE_FIELDS = [
    'account', 'symbol', 'base_symbol', 'trade_date', 'entry_time', 'exit_time',
    'direction', 'quantity', 'entry_price', 'exit_price',
    'pnl_dollars', 'pnl_points', 'duration_min', 'entry_note', 'exit_note',
    'source_file', 'imported_at',
]

AUDIT_FIELDS = [
    'file_name', 'account_name', 'trade_date', 'base_symbol',
    'n_raw', 'n_ghosts', 'clean_trades', 'dirty_net', 'clean_net',
    'integrity_ok', 'flag_reason', 'per_symbol_summary',
]


def resolve_symbol_dir(base_sym: str) -> str:
    """Return the data_clean subfolder for this base_symbol."""
    sym = base_sym.upper() if base_sym else 'UNRECOGNIZED'
    if sym not in KNOWN_SYMBOLS:
        sym = 'UNRECOGNIZED'
    return os.path.join(OUTPUT_ROOT, sym)


def write_trades(db: sqlite3.Connection, since: str = None):
    """Write per-symbol per-(account+date) CSV trade files."""
    q = "SELECT {} FROM clean_trades".format(', '.join(TRADE_FIELDS))
    params = []
    if since:
        q += " WHERE trade_date >= ?"
        params.append(since)
    q += " ORDER BY base_symbol, account, trade_date, entry_time"

    # Group by (base_symbol, account, trade_date)
    rows_by_key = collections.defaultdict(list)
    cur = db.execute(q, params)
    for row in cur.fetchall():
        d = dict(zip(TRADE_FIELDS, row))
        key = (d['base_symbol'] or 'UNRECOGNIZED', d['account'], d['trade_date'])
        rows_by_key[key].append(d)

    files_written = 0
    symbols_seen = set()
    for (base_sym, account, trade_date), rows in sorted(rows_by_key.items()):
        sym_dir = resolve_symbol_dir(base_sym)
        trades_dir = os.path.join(sym_dir, 'trades')
        os.makedirs(trades_dir, exist_ok=True)

        # safe filename
        acct_safe = account.replace('/', '_').replace('\\', '_')
        fname = '{}_{}_{}.csv'.format(base_sym, acct_safe, trade_date)
        fpath = os.path.join(trades_dir, fname)

        with open(fpath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=TRADE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        files_written += 1
        symbols_seen.add(base_sym)

    return files_written, symbols_seen


def write_audits(db: sqlite3.Connection, since: str = None):
    """Write per-symbol audit JSON files from file_audit table."""
    # Use actual column names from the DB schema
    sel_cols = [
        'source_file', 'account', 'trade_date',
        'total_raw_fills', 'ghost_fills', 'clean_trades',
        'dirty_net', 'clean_net', 'integrity_ok',
        'flagged', 'flag_reason', 'asset_list',
    ]

    q = "SELECT {} FROM file_audit".format(', '.join(sel_cols))
    params = []
    if since:
        q += " WHERE trade_date >= ?"
        params.append(since)

    cur = db.execute(q, params)
    rows = cur.fetchall()

    # Group records by (base_symbol, account, trade_date)
    audit_records = collections.defaultdict(list)
    for row in rows:
        d = dict(zip(sel_cols, row))
        assets = [a.strip() for a in (d.get('asset_list') or '').split(',') if a.strip()]
        if not assets:
            assets = ['UNRECOGNIZED']
        for bs in assets:
            record = {
                'file_name':       d['source_file'],
                'account':         d['account'],
                'trade_date':      d['trade_date'],
                'base_symbol':     bs,
                'total_raw_fills': d['total_raw_fills'],
                'ghost_fills':     d['ghost_fills'],
                'clean_trades':    d['clean_trades'],
                'dirty_net':       d['dirty_net'],
                'clean_net':       d['clean_net'],
                'integrity_ok':    bool(d['integrity_ok']),
                'flagged':         bool(d['flagged']),
                'flag_reason':     d['flag_reason'],
            }
            audit_records[(bs, d['account'], d['trade_date'])].append(record)

    files_written = 0
    for (bs, account, trade_date), records in sorted(audit_records.items()):
        sym_dir = resolve_symbol_dir(bs)
        audit_dir = os.path.join(sym_dir, 'audit')
        os.makedirs(audit_dir, exist_ok=True)
        acct_safe = account.replace('/', '_').replace('\\', '_')
        fname = '{}_{}_{}.json'.format(bs, acct_safe, trade_date)
        fpath = os.path.join(audit_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2)
        files_written += 1

    return files_written



def print_per_symbol_summary(db: sqlite3.Connection):
    """Print per-symbol aggregate summary from clean_trades."""
    q = """
        SELECT base_symbol,
               COUNT(DISTINCT account) as accounts,
               COUNT(*) as trades,
               SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN pnl_dollars <= 0 THEN 1 ELSE 0 END) as losses,
               SUM(pnl_dollars) as net_pnl,
               MIN(pnl_dollars) as worst_trade,
               MAX(pnl_dollars) as best_trade
        FROM clean_trades
        GROUP BY base_symbol
        ORDER BY base_symbol
    """
    print()
    print('=' * 78)
    print('  PER-SYMBOL FINAL SUMMARY (from clean_trades)')
    print('=' * 78)
    print('{:12s}  {:>8s}  {:>8s}  {:>6s}  {:>6s}  {:>18s}  {:>14s}  {:>14s}'.format(
        'Symbol', 'Accounts', 'Trades', 'Wins', 'Losses', 'Net PnL', 'Worst Trade', 'Best Trade'))
    print('-' * 78)

    any_impossible = False
    for row in db.execute(q).fetchall():
        bs, accounts, trades, wins, losses, net, worst, best = row
        # Flag only if a SINGLE TRADE exceeds the plausibility ceiling
        worst_single = max(abs(worst or 0), abs(best or 0))
        flag = ''
        if worst_single > 2_000_000:
            flag = '  !!! IMPOSSIBLE SINGLE TRADE !!!'
            any_impossible = True
        print('{:12s}  {:>8d}  {:>8d}  {:>6d}  {:>6d}  {:>18,.2f}  {:>14,.2f}  {:>14,.2f}{}'.format(
            bs or 'UNKNOWN', accounts, trades, wins or 0, losses or 0,
            net or 0, worst or 0, best or 0, flag))
    print('-' * 78)
    if any_impossible:
        print('  !!! IMPOSSIBLE VALUES REMAIN — DO NOT PROMOTE TO PRODUCTION !!!')
    else:
        print('  All symbols: no impossible values detected.')
    print()


def main():
    parser = argparse.ArgumentParser(description='Write per-asset clean data folders')
    parser.add_argument('--db', default=DB_PATH, help='SQLite database path')
    parser.add_argument('--since', default=None, help='Only write records since YYYY-MM-DD')
    parser.add_argument('--summary-only', action='store_true',
                        help='Print per-symbol summary only, do not write files')
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print('ERROR: database not found:', args.db)
        sys.exit(1)

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    if args.summary_only:
        print_per_symbol_summary(db)
        db.close()
        return

    print('Writing asset folders from:', args.db)
    if args.since:
        print('  Filtering to trade_date >=', args.since)

    n_trade_files, syms = write_trades(db, args.since)
    print('  Trade files written : {:,}  (symbols: {})'.format(
        n_trade_files, ', '.join(sorted(syms))))

    n_audit_files = write_audits(db, args.since)
    print('  Audit files written : {:,}'.format(n_audit_files))

    print_per_symbol_summary(db)
    db.close()


if __name__ == '__main__':
    main()
