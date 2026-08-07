"""
ghost_fill_cleaner.py
=====================
Resumable, checkpointed ghost-fill cleaner for the full dataset.
Dataset location : C:\\SC_results_WF\\dataset\\
Checkpoint file  : .gfre_checkpoint.json   (same dir as this script)
Output DB        : trading_platform_clean_v2.db (project root)

Usage
-----
  # First run OR resume after any interruption:
  python ghost_fill_cleaner.py

  # Force restart from zero (wipes checkpoint + output DB):
  python ghost_fill_cleaner.py --reset

  # Dry-run: scan files, print plan, don't process:
  python ghost_fill_cleaner.py --dry-run

Rules
-----
  - NEVER writes to trading_platform.db / processed_trades.
  - All output goes to trading_platform_clean_v2.db (staging only).
  - Checkpoint is saved after EVERY batch, so only the in-progress
    batch is lost on an unexpected crash.
  - Resume is automatic: already-completed files are skipped.
"""

import sys, os, glob, re, json, time, signal, sqlite3, datetime
import concurrent.futures
import argparse

# Force UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = SCRIPT_DIR  # script lives at project root

DATASET_DIR    = os.path.join(PROJECT_ROOT, "dataset")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, ".gfre_checkpoint.json")
OUTPUT_DB      = os.path.join(PROJECT_ROOT, "trading_platform_clean_v2.db")

sys.path.insert(0, PROJECT_ROOT)

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, pair_fills_to_trades, verify_sequence
)

# ── Constants ────────────────────────────────────────────────────────────────
DATE_RE      = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')
BATCH_SIZE   = 50
MAX_WORKERS  = max(1, (os.cpu_count() or 4) - 1)
GFRE_VERSION = "v2"

# Accounts with non-standard instrument scaling (audited separately)
EXCLUDE_ACCOUNTS = {
    "T-S_production", "Tsufim-Prod", "Unset", "Depth",
    "A_production_14_16_19", "A_production_16", "A_production_19",
}

# Review flag threshold: |clean_net - dirty_net| / max(|dirty_net|, 500) > 15%
FLAG_THRESH = 0.15

# Absolute PnL plausibility ceilings (FIX v3 — August 2026)
# Derived from: max_qty=50, realistic worst-day point ranges per symbol:
#   CL  : $1,000/pt x 200 pt range x 50 lots = $10,000,000  -> cap $5,000,000
#   NQ  : $20/pt    x 3,000 pt range x 50    = $3,000,000   -> cap $2,000,000
#   ES  : $50/pt    x 1,000 pt range x 50    = $2,500,000   -> cap $2,000,000
#   FDAX: EUR25/pt  x 2,000 pt range x 50    = EUR2,500,000 -> cap $2,000,000
# A single trade with |pnl_dollars| > ABSOLUTE_TRADE_PNL_CEILING is impossible.
# A file with |clean_net| > ABSOLUTE_FILE_PNL_CEILING is impossible.
# These ceilings catch corrupted-price fills that affect BOTH dirty and clean
# streams (so relative delta == 0%) — the gap that let the billion-dollar
# values through undetected in the prior run.
ABSOLUTE_TRADE_PNL_CEILING = 2_000_000.0   # $2M per single round-trip trade
ABSOLUTE_FILE_PNL_CEILING  = 10_000_000.0  # $10M aggregate per daily file

_stop_requested = False

def _handle_sigint(sig, frame):
    global _stop_requested
    print("\n\n[!] Ctrl+C detected. Finishing current batch, then saving checkpoint...")
    _stop_requested = True

signal.signal(signal.SIGINT, _handle_sigint)

# ── Database setup ───────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS clean_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account         TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    base_symbol     TEXT,
    trade_date      TEXT,
    entry_time      TEXT,
    exit_time       TEXT,
    direction       TEXT,
    quantity        INTEGER,
    entry_price     REAL,
    exit_price      REAL,
    pnl_dollars     REAL,
    pnl_points      REAL,
    duration_min    REAL,
    entry_note      TEXT,
    exit_note       TEXT,
    gfre_version    TEXT DEFAULT 'v2',
    source_file     TEXT,
    imported_at     TEXT
);

CREATE TABLE IF NOT EXISTS file_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file     TEXT UNIQUE NOT NULL,
    account         TEXT,
    trade_date      TEXT,
    processed_at    TEXT,
    total_raw_fills INTEGER,
    ghost_fills     INTEGER,
    bypass_mode     INTEGER,
    note_coverage   REAL,
    dirty_trades    INTEGER,
    clean_trades    INTEGER,
    dirty_net       REAL,
    clean_net       REAL,
    pnl_delta       REAL,
    pnl_delta_pct   REAL,
    integrity_ok    INTEGER,
    integrity_notes TEXT,
    flagged         INTEGER,
    flag_reason     TEXT,
    asset_list      TEXT
);

CREATE INDEX IF NOT EXISTS idx_clean_trades_account ON clean_trades(account);
CREATE INDEX IF NOT EXISTS idx_clean_trades_date    ON clean_trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_clean_trades_symbol  ON clean_trades(base_symbol);
CREATE INDEX IF NOT EXISTS idx_file_audit_account   ON file_audit(account);
"""

def init_db(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.executescript(SCHEMA)
    con.commit()
    return con

# ── Checkpoint ───────────────────────────────────────────────────────────────
def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                cp = json.load(f)
            return cp
        except Exception:
            pass
    return {
        "version": GFRE_VERSION,
        "started_at": datetime.datetime.utcnow().isoformat(),
        "last_updated": None,
        "total_files": 0,
        "completed_files": [],       # list of basename strings
        "stats": {
            "files_processed": 0,
            "total_raw_fills": 0,
            "total_ghost_fills": 0,
            "total_clean_trades": 0,
            "total_dirty_trades": 0,
            "flagged_files": 0,
            "integrity_failures": 0,
        }
    }

def save_checkpoint(cp: dict):
    cp["last_updated"] = datetime.datetime.utcnow().isoformat()
    tmp = CHECKPOINT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cp, f, indent=2)
    os.replace(tmp, CHECKPOINT_PATH)

# ── File enumeration ─────────────────────────────────────────────────────────
def enumerate_files() -> list:
    """Return list of (basename, account, date_str, filepath) for all valid files."""
    results = []
    for fp in sorted(glob.glob(os.path.join(DATASET_DIR, "*.data"))):
        fname = os.path.basename(fp)
        m = DATE_RE.match(fname)
        if not m:
            continue
        date_str, acct = m.group(1), m.group(2)
        try:
            yr = int(date_str[:4])
            if yr < 2020 or yr > 2030:
                continue
        except ValueError:
            continue
        if acct in EXCLUDE_ACCOUNTS:
            continue
        results.append((fname, acct, date_str, fp))
    return results

# ── Per-file worker (runs in thread pool) ────────────────────────────────────
def _process_file(fp: str):
    """
    Full pipeline for one file. Returns a dict of results.
    Never raises — catches all exceptions and returns error flag.
    Imports are local so they always resolve inside ThreadPoolExecutor threads.
    """
    import sys as _sys, os as _os
    _root = _os.path.dirname(_os.path.abspath(__file__))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    from trading_platform.services.binary_log_parser import _parse_file_nitro as _pfn
    from trading_platform.services.ghost_fill_engine import (
        GhostFillEngine as _GFE,
        get_rejected_fills as _get_rejected,
        clear_rejected_fills as _clr_rejected,
    )
    import collections as _col, json as _json

    fname    = _os.path.basename(fp)
    m        = DATE_RE.match(fname)
    acct     = m.group(2) if m else "unknown"
    date_str = m.group(1) if m else "unknown"

    try:
        raw, _ = _pfn(fp)
    except Exception as e:
        return {"file": fname, "account": acct, "date": date_str,
                "error": f"parse_error: {e}", "ok": False,
                "n_raw": 0, "n_ghosts": 0, "n_bypass": 0, "note_coverage": 0.0,
                "dirty_trades": [], "clean_trades": [],
                "dirty_net": 0.0, "clean_net": 0.0,
                "integrity_ok": True, "integrity_notes": f"parse_error: {e}",
                "flagged": True, "flag_reason": f"parse_error: {e}",
                "assets": []}

    if not raw:
        return {
            "file": fname, "account": acct, "date": date_str,
            "n_raw": 0, "n_ghosts": 0, "n_bypass": 0, "note_coverage": 0.0,
            "dirty_trades": [], "clean_trades": [],
            "dirty_net": 0.0, "clean_net": 0.0,
            "integrity_ok": True, "integrity_notes": "",
            "flagged": False, "flag_reason": "",
            "assets": [], "ok": True,
        }

    try:
        _clr_rejected()   # reset per-file rejected list before parsing
        fills = _GFE.from_dicts(raw)
        n_raw = len(fills)

        # ---- Dirty run: per-symbol FIFO, no ghost filter -------------------
        # Group by base_symbol and run pair_fills_to_trades independently so
        # that cross-symbol contamination is absent from the dirty baseline too.
        dirty_net   = 0.0
        _dirty_sym  = _col.defaultdict(list)
        for f in list(fills):
            f.suggests_ghost = False
            _dirty_sym[f.base_symbol].append(f)
        _dirty_fills_count = 0
        for _bs, _sf in _dirty_sym.items():
            _sf_s = sorted(_sf, key=lambda _f: (_f.ts_val, _f.position_order))
            from trading_platform.services.ghost_fill_engine import pair_fills_to_trades as _pft
            _dt, _ = _pft(_sf_s)
            dirty_net += sum(_t.pnl_dollars for _t in _dt)
            _dirty_fills_count += len(_dt)

        # ---- Clean run: full per-symbol engine (v3) ------------------------
        _clr_rejected()   # clear again before clean run's from_dicts
        fills2        = _GFE.from_dicts(raw)
        _engine       = _GFE()
        _clean_result = _engine.process(fills2)
        c_trades      = _clean_result.trades
        c_unpaired    = _clean_result.unpaired_fills
        clean_net     = sum(_t.pnl_dollars for _t in c_trades)
        int_ok        = _clean_result.integrity_ok
        int_notes     = "; ".join(_clean_result.notes[-6:])   # last 6 summary lines
        n_ghosts      = _clean_result.ghost_fills_dropped
        bypass        = _clean_result.bypass_mode
        nc            = sum(sr.note_rate * sr.total_fills
                           for sr in _clean_result.per_symbol.values()) / n_raw \
                        if n_raw else 0.0

        # Per-symbol summary for audit (JSON)
        per_sym_summary = _json.dumps(
            {bs: sr.as_dict() for bs, sr in _clean_result.per_symbol.items()},
            separators=(',', ':')
        )

        # ---- Relative flag threshold (original) -------------------------
        delta     = clean_net - dirty_net
        denom     = max(abs(dirty_net), 500.0)
        delta_pct = abs(delta) / denom
        flagged   = delta_pct > FLAG_THRESH
        flag_reason = "delta={:+,.0f} ({:.0%})".format(delta, delta_pct) if flagged else ""
        if not int_ok:
            flagged = True
            flag_reason = (flag_reason + " | integrity_fail").strip(" | ")

        # ---- Absolute PnL ceiling check (FIX v3) -------------------------
        worst_trade_pnl = max((abs(_t.pnl_dollars) for _t in c_trades), default=0.0)
        if worst_trade_pnl > ABSOLUTE_TRADE_PNL_CEILING:
            flagged = True
            flag_reason = (flag_reason + " | IMPOSSIBLE_TRADE_PNL={:,.0f}".format(
                worst_trade_pnl)).strip(" | ")
        if abs(clean_net) > ABSOLUTE_FILE_PNL_CEILING:
            flagged = True
            flag_reason = (flag_reason + " | IMPOSSIBLE_FILE_NET={:,.0f}".format(
                clean_net)).strip(" | ")

        # ---- Collect rejected_fills produced by this file's is_valid() ---
        rejected    = _get_rejected()
        _clr_rejected()
        n_rejected  = len(rejected)

        # Collect asset list from per_symbol keys
        assets = sorted(_clean_result.per_symbol.keys())
        if n_rejected:
            flag_reason = (flag_reason + " | rejected_fills={}".format(n_rejected)).strip(" | ")
            flagged = True

        # Serialize clean trades for DB insertion
        clean_rows = []
        for t in c_trades:
            clean_rows.append({
                "account":      acct,
                "symbol":       getattr(t, "symbol", ""),
                "base_symbol":  t.base_symbol,
                "trade_date":   date_str,
                "entry_time":   str(t.entry_time),
                "exit_time":    str(t.exit_time),
                "direction":    t.direction,
                "quantity":     t.quantity,
                "entry_price":  t.entry_price,
                "exit_price":   t.exit_price,
                "pnl_dollars":  t.pnl_dollars,
                "pnl_points":   getattr(t, "pnl_points", None),
                "duration_min": getattr(t, "duration_min", None),
                "entry_note":   getattr(t, "entry_note", ""),
                "exit_note":    getattr(t, "exit_note", ""),
                "source_file":  fname,
                "imported_at":  datetime.datetime.utcnow().isoformat(),
            })

        return {
            "file": fname, "account": acct, "date": date_str,
            "n_raw": n_raw, "n_ghosts": n_ghosts, "n_bypass": int(bypass),
            "note_coverage": round(nc, 3),
            "dirty_trades": [], "clean_trades": clean_rows,
            "dirty_net": round(dirty_net, 2), "clean_net": round(clean_net, 2),
            "pnl_delta": round(delta, 2), "pnl_delta_pct": round(delta_pct, 4),
            "integrity_ok": int_ok, "integrity_notes": int_notes,
            "flagged": flagged, "flag_reason": flag_reason,
            "assets": assets, "ok": True,
            "per_symbol_summary": per_sym_summary,
        }

    except Exception as e:
        import traceback as _tb
        _clr_rejected()
        return {"file": fname, "account": acct, "date": date_str,
                "error": "process_error: {}".format(e),
                "n_raw": 0, "n_ghosts": 0, "n_bypass": 0, "note_coverage": 0.0,
                "dirty_trades": [], "clean_trades": [],
                "dirty_net": 0.0, "clean_net": 0.0,
                "integrity_ok": False, "integrity_notes": "process_error: {}".format(e),
                "flagged": True, "flag_reason": "process_error: {}".format(e),
                "assets": [], "ok": True,
                "per_symbol_summary": "{}"}


def _base_symbol(raw: str) -> str:
    """Resolve contract code to base symbol (e.g. NQU25 -> NQ)."""
    SYMBOL_MAP = {
        "CLN": "CL", "CLH": "CL", "CLQ": "CL", "CLU": "CL", "CLV": "CL", "CLZ": "CL",
        "ESM": "ES", "ESU": "ES", "ESZ": "ES", "ESH": "ES",
        "NQM": "NQ", "NQU": "NQ", "NQZ": "NQ", "NQH": "NQ",
    }
    KNOWN = {"ES","MES","NQ","MNQ","CL","MCL","FDAX","RTY","M2K","GC","SI","YM","MYM","ZB"}
    s = (raw or "").upper()
    base = re.match(r'([A-Z]+)', s)
    if not base:
        return s
    b = base.group(1)
    if b in SYMBOL_MAP:
        return SYMBOL_MAP[b]
    for p in KNOWN:
        if b.startswith(p):
            return p
    return b

# ── DB write helpers ─────────────────────────────────────────────────────────
TRADE_COLS = [
    "account","symbol","base_symbol","trade_date","entry_time","exit_time",
    "direction","quantity","entry_price","exit_price","pnl_dollars","pnl_points",
    "duration_min","entry_note","exit_note","gfre_version","source_file","imported_at"
]
AUDIT_COLS = [
    "source_file","account","trade_date","processed_at","total_raw_fills",
    "ghost_fills","bypass_mode","note_coverage","dirty_trades","clean_trades",
    "dirty_net","clean_net","pnl_delta","pnl_delta_pct","integrity_ok",
    "integrity_notes","flagged","flag_reason","asset_list"
]

def write_batch_to_db(con: sqlite3.Connection, results: list):
    now = datetime.datetime.utcnow().isoformat()
    trade_rows = []
    audit_rows = []

    for r in results:
        if not r.get("ok"):
            continue

        # Audit record
        audit_rows.append((
            r["file"], r.get("account",""), r.get("date",""), now,
            r.get("n_raw", 0), r.get("n_ghosts", 0), r.get("n_bypass", 0),
            r.get("note_coverage", 0.0),
            len(r.get("dirty_trades", [])), len(r.get("clean_trades", [])),
            r.get("dirty_net", 0.0), r.get("clean_net", 0.0),
            r.get("pnl_delta", 0.0), r.get("pnl_delta_pct", 0.0),
            int(r.get("integrity_ok", True)),
            r.get("integrity_notes", ""),
            int(r.get("flagged", False)),
            r.get("flag_reason", ""),
            ",".join(r.get("assets", [])),
        ))

        # Trade rows
        for t in r.get("clean_trades", []):
            trade_rows.append((
                t["account"], t["symbol"], t["base_symbol"], t["trade_date"],
                t["entry_time"], t["exit_time"], t["direction"], t["quantity"],
                t["entry_price"], t["exit_price"], t["pnl_dollars"], t.get("pnl_points"),
                t.get("duration_min"), t.get("entry_note",""), t.get("exit_note",""),
                GFRE_VERSION, t["source_file"], t["imported_at"],
            ))

    con.executemany(
        f"INSERT OR IGNORE INTO file_audit ({','.join(AUDIT_COLS)}) VALUES ({','.join(['?']*len(AUDIT_COLS))})",
        audit_rows
    )
    if trade_rows:
        con.executemany(
            f"INSERT INTO clean_trades ({','.join(TRADE_COLS)}) VALUES ({','.join(['?']*len(TRADE_COLS))})",
            trade_rows
        )
    con.commit()

# ── Progress bar ─────────────────────────────────────────────────────────────
def _bar(done, total, width=40) -> str:
    pct  = done / total if total > 0 else 0
    fill = int(width * pct)
    return f"[{'#'*fill}{'-'*(width-fill)}] {pct:5.1%}  {done:,}/{total:,}"

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Resumable ghost-fill cleaner")
    parser.add_argument("--reset",   action="store_true", help="Wipe checkpoint and output DB, start fresh")
    parser.add_argument("--dry-run", action="store_true", help="Enumerate files and print plan, then exit")
    parser.add_argument("--status",  action="store_true", help="Show current progress from checkpoint and exit")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"Thread workers (default {MAX_WORKERS})")
    parser.add_argument("--batch",   type=int, default=BATCH_SIZE,  help=f"Files per batch (default {BATCH_SIZE})")
    args = parser.parse_args()

    # ── Status check ─────────────────────────────────────────────────────────
    if args.status:
        if not os.path.exists(CHECKPOINT_PATH):
            print("No checkpoint found — cleaning has not started yet.")
            print(f"Run:  python ghost_fill_cleaner.py")
            return
        cp   = load_checkpoint()
        s    = cp["stats"]
        done = len(cp["completed_files"])
        total_f = cp.get("total_files", 0)
        pct  = 100 * done / total_f if total_f > 0 else 0
        bar  = _bar(done, total_f)

        print("=" * 60)
        print("  Ghost Fill Cleaner — STATUS")
        print("=" * 60)
        print(f"  Progress      : {bar}  ({pct:.1f}%)")
        print(f"  Files done    : {done:,} / {total_f:,}")
        print(f"  Files left    : {max(0, total_f - done):,}")
        print()
        print(f"  Raw fills seen     : {s['total_raw_fills']:,}")
        print(f"  Ghost fills removed: {s['total_ghost_fills']:,}  "
              f"({100*s['total_ghost_fills']/max(s['total_raw_fills'],1):.2f}%)")
        print(f"  Clean trades out   : {s['total_clean_trades']:,}")
        print(f"  Flagged files      : {s['flagged_files']}  (>15% PnL delta)")
        print(f"  Integrity failures : {s['integrity_failures']}")
        print()
        print(f"  Checkpoint     : {CHECKPOINT_PATH}")
        print(f"  Output DB      : {OUTPUT_DB}")
        print(f"  Last updated   : {cp.get('last_updated', 'unknown')} UTC")
        print()

        # DB row counts if available
        if os.path.exists(OUTPUT_DB):
            try:
                con = sqlite3.connect(OUTPUT_DB)
                n_trades = con.execute("SELECT COUNT(*) FROM clean_trades").fetchone()[0]
                n_audit  = con.execute("SELECT COUNT(*) FROM file_audit").fetchone()[0]
                n_flagged= con.execute("SELECT COUNT(*) FROM file_audit WHERE flagged=1").fetchone()[0]
                con.close()
                print(f"  DB clean_trades: {n_trades:,} rows")
                print(f"  DB file_audit  : {n_audit:,} rows  ({n_flagged} flagged)")
            except Exception as e:
                print(f"  DB read error: {e}")

        if done >= total_f and total_f > 0:
            print()
            print("  STATUS: COMPLETE — all files processed.")
        else:
            print()
            print("  STATUS: IN PROGRESS (or paused)")
            print("  Resume : python ghost_fill_cleaner.py")
        return

    # ── Reset if requested ────────────────────────────────────────────────────
    if args.reset:
        for path in [CHECKPOINT_PATH, OUTPUT_DB]:
            if os.path.exists(path):
                os.remove(path)
                print(f"  Removed: {path}")
        print("Reset complete. Run 'python ghost_fill_cleaner.py' to start fresh.\n")
        return

    # ── Enumerate all files ──────────────────────────────────────────────────
    print("Scanning dataset directory...")
    all_files = enumerate_files()
    total     = len(all_files)
    print(f"  Found {total:,} valid files in {DATASET_DIR}")

    if args.dry_run:
        from collections import Counter
        acct_counts = Counter(acct for _, acct, _, _ in all_files)
        month_counts = Counter(d[:7] for _, _, d, _ in all_files)
        print(f"\nDRY RUN — Batch plan:")
        print(f"  Total files : {total:,}")
        print(f"  Accounts    : {len(acct_counts)}")
        print(f"  Date range  : {min(d for _,_,d,_ in all_files)} to {max(d for _,_,d,_ in all_files)}")
        print(f"  Workers     : {args.workers}")
        print(f"  Batch size  : {args.batch}")
        print(f"  Est. runtime: 3.2–6.0 hr @ 4.5 files/sec (measured)")
        print(f"\nTop 10 accounts by file count:")
        for acct, cnt in acct_counts.most_common(10):
            print(f"    {acct:<35} {cnt:>5} files")
        return

    # ── Load checkpoint ───────────────────────────────────────────────────────
    cp = load_checkpoint()
    done_set  = set(cp.get("completed_files", []))
    stats     = cp["stats"]

    # Files still to process
    pending = [(fname, acct, d, fp) for fname, acct, d, fp in all_files
               if fname not in done_set]

    already_done = total - len(pending)
    print(f"  Already done: {already_done:,}  |  Pending: {len(pending):,}")
    if not pending:
        print("\nAll files already processed. Nothing to do.")
        print(f"  Use --reset to start over.")
        return

    cp["total_files"] = total

    # ── Init DB ───────────────────────────────────────────────────────────────
    con = init_db(OUTPUT_DB)
    print(f"  Output DB   : {OUTPUT_DB}")
    print(f"  Checkpoint  : {CHECKPOINT_PATH}")
    print(f"  Workers     : {args.workers}  |  Batch size: {args.batch}")
    print(f"\nStarting... (press Ctrl+C to pause and save checkpoint)\n")

    t_start    = time.perf_counter()
    files_this_session = 0
    flagged_files = []
    integrity_fails = []

    # ── Main loop ─────────────────────────────────────────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        for batch_idx in range(0, len(pending), args.batch):
            if _stop_requested:
                break

            batch = pending[batch_idx: batch_idx + args.batch]
            fps_batch = [fp for _, _, _, fp in batch]

            # Submit all files in batch
            futs = {executor.submit(_process_file, fp): fp for fp in fps_batch}
            results = []
            for fut in concurrent.futures.as_completed(futs):
                results.append(fut.result())

            # Write this batch atomically
            write_batch_to_db(con, results)

            # Update checkpoint
            batch_fnames = [fname for fname, _, _, _ in batch]
            cp["completed_files"].extend(batch_fnames)
            done_set.update(batch_fnames)

            # Accumulate stats
            for r in results:
                if not r.get("ok"):
                    continue
                stats["files_processed"]    += 1
                stats["total_raw_fills"]    += r.get("n_raw", 0)
                stats["total_ghost_fills"]  += r.get("n_ghosts", 0)
                stats["total_clean_trades"] += len(r.get("clean_trades", []))
                stats["total_dirty_trades"] += len(r.get("dirty_trades", []))
                if r.get("flagged"):
                    stats["flagged_files"] += 1
                    flagged_files.append((r["file"], r["flag_reason"]))
                if not r.get("integrity_ok", True):
                    stats["integrity_failures"] += 1
                    integrity_fails.append((r["file"], r.get("integrity_notes","")))

            files_this_session += len(batch)
            save_checkpoint(cp)

            # Progress display
            elapsed    = time.perf_counter() - t_start
            done_total = already_done + files_this_session
            fps_rate   = files_this_session / elapsed if elapsed > 0 else 0
            remaining  = (total - done_total) / fps_rate if fps_rate > 0 else 0
            eta_str    = f"{remaining/3600:.1f}h" if remaining > 3600 else f"{remaining/60:.0f}m"

            pct_complete = done_total / total * 100 if total > 0 else 0
            ghost_pct    = 100 * stats["total_ghost_fills"] / max(stats["total_raw_fills"], 1)

            print(
                f"\r{_bar(done_total, total)}  "
                f"{fps_rate:.1f}f/s  ETA:{eta_str}  "
                f"Ghosts:{stats['total_ghost_fills']:,}({ghost_pct:.1f}%)  "
                f"Flags:{stats['flagged_files']}",
                end="", flush=True
            )

    # ── Session complete ───────────────────────────────────────────────────────
    elapsed_total = time.perf_counter() - t_start
    print(f"\n\n{'='*70}")

    if _stop_requested:
        print(f"PAUSED (checkpoint saved)")
    else:
        print(f"COMPLETE")

    print(f"{'='*70}")
    print(f"  Session time          : {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")
    print(f"  Files this session    : {files_this_session:,}")
    print(f"  Total done            : {len(cp['completed_files']):,} / {total:,}")
    print(f"  Raw fills processed   : {stats['total_raw_fills']:,}")
    print(f"  Ghost fills removed   : {stats['total_ghost_fills']:,}  "
          f"({100*stats['total_ghost_fills']/max(stats['total_raw_fills'],1):.2f}%)")
    print(f"  Clean trades written  : {stats['total_clean_trades']:,}")
    print(f"  Flagged files (>15%)  : {stats['flagged_files']}")
    print(f"  Integrity failures    : {stats['integrity_failures']}")
    print(f"  Output DB             : {OUTPUT_DB}")
    print(f"  Checkpoint            : {CHECKPOINT_PATH}")

    if flagged_files:
        print(f"\n--- Flagged Files (last session, {len(flagged_files)}) ---")
        for fname, reason in flagged_files[:20]:
            print(f"  {fname}: {reason}")
        if len(flagged_files) > 20:
            print(f"  ... and {len(flagged_files)-20} more (see file_audit table)")

    if integrity_fails:
        print(f"\n--- Integrity Failures (last session, {len(integrity_fails)}) ---")
        for fname, notes in integrity_fails[:10]:
            print(f"  {fname}: {notes[:120]}")

    if _stop_requested:
        print(f"\nResume anytime with: python ghost_fill_cleaner.py")
    else:
        print(f"\nAll files processed.")
        print(f"Next step: review flagged files, then promote with explicit sign-off.")

    con.close()


if __name__ == "__main__":
    main()
