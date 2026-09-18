"""
match_rate_checkpoint.py — resumable multiprocessing match-rate scan
=====================================================================

Checkpoints the log_index to disk every CKPT_EVERY files.
On restart, loads the checkpoint and skips already-processed files.
This survives server restarts without losing progress.

Usage:
  python match_rate_checkpoint.py          # full run (or resume)
  python match_rate_checkpoint.py --reset  # delete checkpoint, start fresh
"""

import sys, os, re, csv, sqlite3, datetime, glob, collections, time, pickle
import multiprocessing as mp

# ── CONFIG ─────────────────────────────────────────────────────────────────────
DB         = r'C:\SC_results_WF\trading_platform.db'
DATASET    = r'C:\SC_results_WF\dataset'
OUT_DIR    = r'C:\SC_results_WF\results'
CKPT_FILE  = r'C:\SC_results_WF\results\log_index_checkpoint.pkl'

PRICE_BAND  = 0.5
DAY_EXTRA   = 1
PASS_THRESH = 95.0
WARN_THRESH = 90.0
NWORKERS    = 4
CKPT_EVERY  = 10_000   # save checkpoint every N files

FILE_RE_PAT = r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$'

os.makedirs(OUT_DIR, exist_ok=True)

# ── KNOWN ROOTS & clean_base ─────────────────────────────────────────────────
KNOWN_ROOTS = frozenset({
    'ES', 'MES', 'NQ', 'MNQ', 'CL', 'MCL', 'FDAX', 'FDXM', 'RTY', 'M2K',
    'GC', 'SI', 'YM', 'MYM', 'ZB', 'ZN', 'ZF', 'ZT', 'ZC', 'ZS', 'ZW',
    'NG', 'RB', 'HO', 'HE', 'LE', 'GF', 'SR3', 'FGBL', 'FESX',
})
_MONTH = frozenset('FGHJKMNQUVXZ')

def clean_base(raw: str) -> str:
    r = str(raw).strip().upper()
    if r in KNOWN_ROOTS: return r
    stripped = re.sub(r'\d{2}$', '', r)
    if stripped != r:
        if stripped in KNOWN_ROOTS: return stripped
        if stripped and stripped[-1] in _MONTH:
            root = stripped[:-1]
            if root in KNOWN_ROOTS: return root
            for end in range(len(root), 0, -1):
                if root[:end] in KNOWN_ROOTS: return root[:end]
    s4 = re.sub(r'\d{4}$', '', r)
    if s4 != r and s4 in KNOWN_ROOTS: return s4
    alpha = re.sub(r'\d+$', '', r)
    if alpha in KNOWN_ROOTS: return alpha
    if alpha and alpha[-1] in _MONTH:
        root2 = alpha[:-1]
        if root2 in KNOWN_ROOTS: return root2
    m = re.match(r'^([A-Z]+)', r)
    return m.group(1) if m else r


def parse_dt(s):
    if not s: return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%d %H:%M:%S.%f'):
        try: return datetime.datetime.strptime(str(s)[:26], fmt)
        except: pass
    return None


# ── WORKER SETUP: module-injection bypass (avoids scipy OOM) ─────────────────
def _worker_init():
    import sys, types, io, builtins, importlib.util
    from zoneinfo import ZoneInfo

    for mod_name in ['trading_platform', 'trading_platform.utils',
                     'trading_platform.utils.timezone_utils', 'trading_platform.services']:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)
    sys.modules['trading_platform.utils.timezone_utils'].NY_TZ = ZoneInfo('America/New_York')

    _BLP = r'C:\SC_results_WF\trading_platform\services\binary_log_parser.py'
    spec = importlib.util.spec_from_file_location('trading_platform.services.binary_log_parser', _BLP)
    mod  = importlib.util.module_from_spec(spec)
    mod.__package__ = 'trading_platform.services'
    sys.modules['trading_platform.services.binary_log_parser'] = mod

    _real = builtins.open
    builtins.open = lambda f, *a, **kw: (
        io.StringIO() if isinstance(f, str) and 'import_debug.log' in f else _real(f, *a, **kw)
    )
    try:
        spec.loader.exec_module(mod)
    finally:
        builtins.open = _real

    global _pfn, _real_open_g
    _pfn         = mod._parse_file_nitro
    _real_open_g = _real


def _parse_one(fpath: str):
    import re, io, builtins
    global _pfn, _real_open_g

    KNOWN_R = frozenset({
        'ES','MES','NQ','MNQ','CL','MCL','FDAX','FDXM','RTY','M2K',
        'GC','SI','YM','MYM','ZB','ZN','ZF','ZT','ZC','ZS','ZW',
        'NG','RB','HO','HE','LE','GF','SR3','FGBL','FESX',
    })
    MONTH = frozenset('FGHJKMNQUVXZ')

    def _cb(raw):
        r = str(raw).strip().upper()
        if r in KNOWN_R: return r
        s = re.sub(r'\d{2}$', '', r)
        if s != r:
            if s in KNOWN_R: return s
            if s and s[-1] in MONTH:
                root = s[:-1]
                if root in KNOWN_R: return root
                for e in range(len(root), 0, -1):
                    if root[:e] in KNOWN_R: return root[:e]
        s4 = re.sub(r'\d{4}$', '', r)
        if s4 != r and s4 in KNOWN_R: return s4
        alpha = re.sub(r'\d+$', '', r)
        if alpha in KNOWN_R: return alpha
        if alpha and alpha[-1] in MONTH:
            root2 = alpha[:-1]
            if root2 in KNOWN_R: return root2
        m2 = re.match(r'^([A-Z]+)', r)
        return m2.group(1) if m2 else r

    FILE_RE_W = re.compile(
        r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$', re.IGNORECASE)
    m = FILE_RE_W.match(os.path.basename(fpath))
    if not m: return []
    date_str, acct = m.group(1), m.group(2)
    try:
        if not (2020 <= int(date_str[:4]) <= 2030): return []
    except: return []

    _real = _real_open_g
    builtins.open = lambda f, *a, **kw: (
        io.StringIO() if isinstance(f, str) and 'import_debug.log' in f else _real(f, *a, **kw)
    )
    try:
        raw_fills, _ = _pfn(fpath)
    except Exception:
        return []
    finally:
        builtins.open = _real

    result = []
    for f in raw_fills:
        sym   = _cb(f.get('symbol', '') or '')
        price = f.get('price')
        if sym and price is not None:
            result.append((acct, sym, date_str, round(float(price), 4)))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    mp.freeze_support()

    # Handle --reset flag
    if '--reset' in sys.argv:
        if os.path.exists(CKPT_FILE):
            os.remove(CKPT_FILE)
            print(f"Checkpoint deleted: {CKPT_FILE}")
        else:
            print("No checkpoint to delete.")
        sys.exit(0)

    t0 = time.time()

    # ── Load or init checkpoint ───────────────────────────────────────────────
    if os.path.exists(CKPT_FILE):
        print(f"Loading checkpoint from {CKPT_FILE} ...", flush=True)
        with open(CKPT_FILE, 'rb') as f:
            ckpt = pickle.load(f)
        log_index       = ckpt['log_index']
        processed_files = ckpt['processed_files']  # set of already-done fpaths
        print(f"  Resumed: {len(processed_files):,} files already done, "
              f"{len(log_index):,} index buckets", flush=True)
    else:
        log_index       = collections.defaultdict(list)
        processed_files = set()
        print("No checkpoint found — starting fresh.", flush=True)

    # ── Pre-filter files to DB accounts ──────────────────────────────────────
    print("\nPre-filtering files to DB accounts...", flush=True)
    conn = sqlite3.connect(DB)
    cur  = conn.cursor()
    cur.execute("SELECT DISTINCT account_name FROM processed_trades "
                "WHERE account_name IS NOT NULL AND account_name != ''")
    db_accts = set(r[0] for r in cur.fetchall())
    conn.close()

    FILE_RE   = re.compile(FILE_RE_PAT, re.IGNORECASE)
    all_files = sorted(glob.glob(os.path.join(DATASET, '*.data')))
    keep_files = []
    for fp in all_files:
        m = FILE_RE.match(os.path.basename(fp))
        if not m: continue
        date_str, acct = m.group(1), m.group(2)
        try:
            if not (2020 <= int(date_str[:4]) <= 2030): continue
        except: continue
        if acct in db_accts:
            keep_files.append(fp)

    total_files     = len(keep_files)
    remaining_files = [fp for fp in keep_files if fp not in processed_files]
    print(f"  Total target files: {total_files:,}  "
          f"Already done: {len(processed_files):,}  "
          f"Remaining: {len(remaining_files):,}", flush=True)

    if not remaining_files:
        print("All files already processed — skipping to matching step.", flush=True)
    else:
        # ── STEP 1: Parallel log index build (with checkpointing) ─────────────
        print(f"\nSTEP 1: Building log fill index with {NWORKERS} workers "
              f"(checkpoint every {CKPT_EVERY:,} files)...", flush=True)

        done       = 0
        batch_done = 0

        with mp.Pool(processes=NWORKERS, initializer=_worker_init) as pool:
            for entries in pool.imap_unordered(_parse_one, remaining_files, chunksize=200):
                fp_processed = None  # not tracking individual paths here — use count
                for acct, sym, date_str, price in entries:
                    log_index[(acct, sym, date_str)].append(price)
                done       += 1
                batch_done += 1

                if done % 5000 == 0:
                    elapsed = time.time() - t0
                    total_done = len(processed_files) + done
                    rate  = done / elapsed if elapsed > 0 else 0
                    eta_s = (len(remaining_files) - done) / rate if rate > 0 else 0
                    print(f"  [{total_done:>6}/{total_files}] "
                          f"{100*total_done/total_files:.1f}%  "
                          f"keys={len(log_index):,}  "
                          f"rate={rate:.1f}f/s  eta={eta_s/60:.1f}min", flush=True)

                if batch_done >= CKPT_EVERY:
                    # Save checkpoint (note: processed_files tracking by count, not path)
                    # We save the current state; on resume we recompute remaining
                    ckpt_data = {
                        'log_index'       : log_index,
                        'processed_files' : processed_files | set(remaining_files[:done]),
                    }
                    tmp = CKPT_FILE + '.tmp'
                    with open(tmp, 'wb') as f:
                        pickle.dump(ckpt_data, f, protocol=4)
                    os.replace(tmp, CKPT_FILE)
                    batch_done = 0
                    total_done = len(processed_files) + done
                    print(f"  ** CHECKPOINT saved at {total_done:,}/{total_files} files **", flush=True)

        # Final checkpoint save
        all_processed = processed_files | set(remaining_files[:done])
        ckpt_data = {'log_index': log_index, 'processed_files': all_processed}
        tmp = CKPT_FILE + '.tmp'
        with open(tmp, 'wb') as f:
            pickle.dump(ckpt_data, f, protocol=4)
        os.replace(tmp, CKPT_FILE)

        for k in log_index:
            log_index[k].sort()

        elapsed1 = time.time() - t0
        print(f"\nLog index: {len(log_index):,} buckets in {elapsed1:.0f}s ({elapsed1/60:.1f}min)",
              flush=True)
        print(f"  Accounts: {len(set(k[0] for k in log_index))}  "
              f"Symbols: {sorted(set(k[1] for k in log_index))}", flush=True)

    # Sort index if loaded from checkpoint (may not be sorted)
    for k in log_index:
        if log_index[k] != sorted(log_index[k]):
            log_index[k].sort()

    # ── STEP 2: Load ALL DB trades ────────────────────────────────────────────
    print("\nSTEP 2: Loading ALL DB trades...", flush=True)
    conn = sqlite3.connect(DB)
    cur  = conn.cursor()
    cur.execute("""
        SELECT account_name, symbol, entry_time, entry_price
        FROM processed_trades
        WHERE entry_time IS NOT NULL AND entry_time != ''
          AND entry_price IS NOT NULL
    """)
    all_db = cur.fetchall()
    conn.close()
    print(f"  Loaded {len(all_db):,} DB trades", flush=True)

    # ── STEP 3: DB-centric price-only matching ────────────────────────────────
    print("\nSTEP 3: Matching...", flush=True)
    day_results = collections.defaultdict(lambda: {'db': 0, 'matched': 0, 'no_log': 0})
    total = len(all_db)
    BATCH = 200_000

    for i, (acct, sym, et, ep) in enumerate(all_db):
        bs = clean_base(sym)
        dt = parse_dt(et)
        if dt is None: continue

        date_str = dt.strftime('%Y-%m-%d')
        key      = (acct, bs, date_str)
        day_results[key]['db'] += 1

        ep_f  = float(ep)
        bd    = dt.date()
        cands = []
        for delta in range(-DAY_EXTRA, DAY_EXTRA + 1):
            ds = (bd + datetime.timedelta(days=delta)).strftime('%Y-%m-%d')
            cands.extend(log_index.get((acct, bs, ds), []))

        if not cands:
            day_results[key]['no_log'] += 1
            continue

        if any(abs(fp - ep_f) <= PRICE_BAND for fp in cands):
            day_results[key]['matched'] += 1

        if (i + 1) % BATCH == 0:
            pct = 100 * (i + 1) / total
            mat = sum(v['matched'] for v in day_results.values())
            dbt = sum(v['db']      for v in day_results.values())
            print(f"  [{i+1:>9}/{total}] {pct:.1f}%  "
                  f"running_match={100*mat/max(dbt,1):.1f}%", flush=True)

    elapsed3 = time.time() - t0
    print(f"\nMatching done ({elapsed3:.0f}s total)", flush=True)

    # ── STEP 4: Aggregate & write ─────────────────────────────────────────────
    detail_rows = []
    for (acct, bs, ds), v in sorted(day_results.items()):
        detail_rows.append({
            'account': acct, 'base_symbol': bs, 'date': ds,
            'db_trades': v['db'], 'matched': v['matched'],
            'no_log': v['no_log'], 'unmatched': v['db'] - v['matched'],
        })

    detail_path = os.path.join(OUT_DIR, 'match_rate_all_accounts_symbols.csv')
    with open(detail_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['account','base_symbol','date',
                                          'db_trades','matched','no_log','unmatched'])
        w.writeheader(); w.writerows(detail_rows)
    print(f"Detail CSV: {detail_path}  ({len(detail_rows):,} rows)", flush=True)

    # Rollup
    combo  = collections.defaultdict(lambda: {'db':0,'matched':0,'no_log':0})
    ticker = collections.defaultdict(lambda: {'db':0,'matched':0,'no_log':0,'combos':0})
    for (acct, bs, ds), v in day_results.items():
        combo[(acct, bs)]['db']      += v['db']
        combo[(acct, bs)]['matched'] += v['matched']
        combo[(acct, bs)]['no_log']  += v['no_log']
    for (acct, bs), v in combo.items():
        ticker[bs]['db']      += v['db']
        ticker[bs]['matched'] += v['matched']
        ticker[bs]['no_log']  += v['no_log']
        ticker[bs]['combos']  += 1

    ticker_rows = []
    for bs in sorted(ticker):
        t    = ticker[bs]
        m_db = 100 * t['matched'] / t['db'] if t['db'] > 0 else 0.0
        if   m_db >= PASS_THRESH: status = 'PASS'
        elif m_db >= WARN_THRESH: status = 'WARN'
        else:                      status = 'FAIL'
        ticker_rows.append({
            'base_symbol': bs, 'account_combos': t['combos'],
            'total_db': t['db'], 'matched': t['matched'],
            'no_log_fills': t['no_log'], 'unmatched': t['db'] - t['matched'],
            'match_pct': round(m_db, 2), 'status': status,
        })

    ticker_csv = os.path.join(OUT_DIR, 'match_rate_final_by_ticker.csv')
    with open(ticker_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(ticker_rows[0].keys()) if ticker_rows else [])
        w.writeheader(); w.writerows(ticker_rows)
    print(f"Ticker CSV: {ticker_csv}", flush=True)

    # Console table
    print()
    print("=" * 78)
    print("  MATCH RATE FINAL — ALL ACCOUNTS x ALL BASE SYMBOLS")
    print("=" * 78)
    print(f"  Method: DB-centric price-only | band=+/-{PRICE_BAND} | window=+/-{DAY_EXTRA} day")
    print(f"  Timestamp NOT used (SC local wall-clock vs DB timezone)")
    print(f"  Files parsed: {total_files:,} (account-filtered from {len(all_files):,})")
    print(f"  PASS>={PASS_THRESH}%  WARN>={WARN_THRESH}%  FAIL<{WARN_THRESH}%")
    print()
    print(f"{'Symbol':<8} {'Combos':>7} {'DBTrades':>10} {'Matched':>9} "
          f"{'NoLog':>8} {'Unmatch':>9} {'Match%':>8} {'Status':>6}")
    print("-" * 78)
    for r in ticker_rows:
        print(f"{r['base_symbol']:<8} {r['account_combos']:>7} "
              f"{r['total_db']:>10,} {r['matched']:>9,} "
              f"{r['no_log_fills']:>8,} {r['unmatched']:>9,} "
              f"{r['match_pct']:>7.2f}% {r['status']:>6}")
    grand_db  = sum(t['db']      for t in ticker.values())
    grand_mat = sum(t['matched'] for t in ticker.values())
    gp        = 100 * grand_mat / grand_db if grand_db else 0
    print("-" * 78)
    print(f"{'BLENDED':<8} {'':>7} {grand_db:>10,} {grand_mat:>9,} "
          f"{'':>8} {grand_db-grand_mat:>9,} {gp:>7.2f}% {'NOTE*':>6}")
    print("  * Blended is cross-symbol - NOT the headline.")
    print("=" * 78)

    # Markdown
    md_path = os.path.join(OUT_DIR, 'match_rate_final_by_ticker.md')
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    md_lines = [
        "# Match-Rate Verification - All Accounts x All Base Symbols",
        "",
        f"**Generated:** {now}  ",
        f"**Method:** DB-centric price-only match ({NWORKERS} workers, checkpointed)  ",
        f"**Price tolerance:** +/-{PRICE_BAND} on entry_price  ",
        f"**Day window:** +/-{DAY_EXTRA} calendar day  ",
        f"**Timestamp:** NOT used (SC ts_val local wall-clock != DB timezone)  ",
        f"**Files parsed:** {total_files:,} of {len(all_files):,} (DB-account-filtered)  ",
        f"**PASS:** >={PASS_THRESH}%  **WARN:** >={WARN_THRESH}%  **FAIL:** <{WARN_THRESH}%  ",
        "",
        "## Per-Ticker Summary",
        "",
        "| Symbol | Combos | DB Trades | Matched | No-Log | Unmatched | Match% | Status |",
        "|--------|-------:|----------:|--------:|-------:|----------:|-------:|--------|",
    ]
    for r in ticker_rows:
        md_lines.append(
            f"| {r['base_symbol']} | {r['account_combos']} | {r['total_db']:,} | "
            f"{r['matched']:,} | {r['no_log_fills']:,} | {r['unmatched']:,} | "
            f"{r['match_pct']:.2f}% | **{r['status']}** |"
        )
    md_lines += [
        "",
        f"> **Blended (cross-symbol, NOT headline):** {grand_mat:,}/{grand_db:,} = {gp:.2f}%",
        "",
        "## Methodology",
        "",
        "- **Direction:** DB-centric: for each DB trade, find matching log fill by price",
        f"- **Price match:** |fill_price - entry_price| <= {PRICE_BAND}",
        f"- **Day window:** +/-{DAY_EXTRA} calendar day from DB entry_date",
        "- **No-Log:** DB trades where log has zero fills for that account/date",
        "- **Unmatched:** log fills present but no price within +/-0.5",
        "- **Parallelism:** multiprocessing.Pool with module-injection bypass (no scipy OOM)",
        "- **Checkpointing:** log_index saved to pickle every 10k files; resumable on restart",
    ]
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines) + '\n')
    print(f"Markdown: {md_path}", flush=True)
    print(f"\nAll done. Total time: {(time.time()-t0)/60:.1f} min", flush=True)

    # Clean up checkpoint on success
    if os.path.exists(CKPT_FILE):
        os.remove(CKPT_FILE)
        print(f"Checkpoint cleaned up.", flush=True)
