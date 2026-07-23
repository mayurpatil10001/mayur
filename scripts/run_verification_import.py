"""
scripts/run_verification_import.py
====================================
Task 1 (FIXED): Full re-parse of dataset/*.data into verification_trades.

FIXES APPLIED:
- Ghost-exit → orphaned-entry purge active (Gilad's concern)
- Single-threaded sequential (Windows-safe, no threading deadlocks)
- Parser: binary_log_parser.py (with ghost sequence resync fix)
"""

import sys
import os
import glob
import re
import datetime
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_platform.services.binary_log_parser import (
    _parse_file_nitro,
    _crosses_daily_close_ny,
    NY_TZ
)

DATASET_DIR = PROJECT_ROOT / "dataset"
DB_PATH = PROJECT_ROOT / "trading_platform.db"
AUDIT_LOG_FILE = PROJECT_ROOT / "scripts" / "verification_audit_data.json"

TARGET_START = "2023-09-01"
TARGET_END = "2025-11-01"


def get_target_files() -> List[str]:
    pattern = os.path.join(str(DATASET_DIR), "*.data")
    all_files = sorted(glob.glob(pattern))
    target = []
    for fp in all_files:
        fn = os.path.basename(fp)
        m = re.search(r'(\d{4}-\d{2}-\d{2})', fn)
        if m:
            ds = m.group(1)
            if TARGET_START <= ds <= TARGET_END:
                target.append(fp)
    return target


def save_trades_to_verification_table(conn: sqlite3.Connection, trades: List[Dict]) -> int:
    c = conn.cursor()
    inserted = 0
    for t in trades:
        try:
            t1_utc = datetime.datetime.fromisoformat(t['entry_time']).replace(tzinfo=datetime.timezone.utc)
            t2_utc = datetime.datetime.fromisoformat(t['exit_time']).replace(tzinfo=datetime.timezone.utc)
            duration = int((t2_utc - t1_utc).total_seconds() / 60.0)
            t1_ny = t1_utc.astimezone(NY_TZ)
            hour, dow, minute_ny = t1_ny.hour, t1_ny.weekday(), t1_ny.minute
        except Exception:
            duration, hour, dow, minute_ny = 0, 0, 0, 0

        side = "LONG" if "LONG" in t['side'].upper() or "BUY" in t['side'].upper() else "SHORT"
        acc = t['account'].upper()
        sym = t['symbol'].upper()
        sig = f"{acc}_{sym}_{side}_{t['entry_time']}_{t['exit_time']}_{t['entry_price']}_{t['exit_price']}_{t['quantity']}"
        tid = "T" + hashlib.md5(sig.encode()).hexdigest()[:12]

        c.execute("""
            INSERT OR REPLACE INTO verification_trades (
                trade_id, account_name, symbol, entry_time, exit_time,
                entry_price, exit_price, quantity, side,
                profit_loss, commission, duration_minutes,
                hour_of_day, day_of_week, minute_of_hour_ny, trip_id, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tid, acc, sym, t['entry_time'], t['exit_time'],
            t['entry_price'], t['exit_price'], t['quantity'], side,
            t['profit_loss'], t['commission'], duration,
            hour, dow, minute_ny, t.get('trip_id', ''), t.get('source_file', '')
        ))
        inserted += 1
    conn.commit()
    return inserted


def main():
    print("=" * 80)
    print(" TASK 1 (FIXED): Full Re-Parse into `verification_trades` (Single-Threaded)")
    print(" Parser: Ghost-Exit -> Orphaned-Entry Purge Fix ACTIVE")
    print("=" * 80)

    target_files = get_target_files()
    print(f"Target files: {len(target_files):,} files ({TARGET_START} to {TARGET_END})")

    all_unique_fills = {}
    all_ghosts = []
    files_ok = 0
    files_failed = 0

    # Phase 1: Sequential single-threaded parsing
    print("\nPhase 1: Parsing files sequentially (no threading, Windows-safe)...")
    for idx, fp in enumerate(target_files):
        if (idx + 1) % 1000 == 0 or idx == 0:
            print(
                f"  Progress: {idx+1:,}/{len(target_files):,} "
                f"({(idx+1)/len(target_files)*100:.1f}%) | "
                f"fills: {len(all_unique_fills):,}",
                flush=True
            )

        try:
            res_fills, res_ghosts = _parse_file_nitro(fp)
            files_ok += 1

            if isinstance(res_ghosts, list):
                for g in res_ghosts:
                    g['source_file'] = os.path.basename(fp)
                    all_ghosts.append(g)

            if isinstance(res_fills, list):
                for f in res_fills:
                    if not isinstance(f, dict):
                        continue
                    ts_val = f.get('ts_val', 0) or 0
                    ts_bucket = round(ts_val * 2) / 2.0
                    msg_hash = hash(f.get('msgtxt', ''))
                    inst_path = os.path.dirname(f.get('file_path', 'default'))
                    key = (
                        inst_path, f.get('account_name'), f.get('symbol'),
                        f.get('side'), f.get('price'), f.get('quantity'),
                        ts_bucket, msg_hash
                    )
                    f['source_file'] = os.path.basename(fp)
                    if key not in all_unique_fills:
                        all_unique_fills[key] = f
                    else:
                        if all_unique_fills[key].get('suggests_ghost') and not f.get('suggests_ghost'):
                            all_unique_fills[key] = f
        except Exception as ex:
            files_failed += 1

    print(f"\nPhase 1 complete: {files_ok:,} ok | {files_failed:,} failed")
    print(f"  Total unique fills: {len(all_unique_fills):,}")
    print(f"  Ghost fills dropped (parser-level): {len(all_ghosts):,}")

    # Phase 2: FIFO Pairing with fixed parser (ghost orphan purge active)
    print("\nPhase 2: Pairing fills into round-trip trades (Ghost-Orphan Purge Active)...")
    all_fills_list = sorted(all_unique_fills.values(), key=lambda x: x.get('ts_val', 0))

    from trading_platform.services.binary_log_parser import BinaryLogParser
    parser = BinaryLogParser(db_path=str(DB_PATH))
    trades, unpaired, pos_warnings = parser._pairs_to_trades(all_fills_list, persist_state=False)
    print(f"  Raw round-trip trades paired: {len(trades):,}")
    print(f"  Unpaired fill qty: {unpaired:,}")
    print(f"  Position warnings: {len(pos_warnings):,}")

    # Phase 3: Session-boundary filter
    print("\nPhase 3: Filtering session-boundary crossing trades...")
    valid_trades = []
    sb_dropped = []
    for t in trades:
        try:
            e_dt = datetime.datetime.fromisoformat(t['entry_time'])
            x_dt = datetime.datetime.fromisoformat(t['exit_time'])
            if _crosses_daily_close_ny(e_dt, x_dt):
                sb_dropped.append(t)
            else:
                valid_trades.append(t)
        except Exception:
            valid_trades.append(t)

    print(f"  Session-boundary trades dropped: {len(sb_dropped):,}")
    print(f"  Valid trades remaining: {len(valid_trades):,}")

    # Phase 4: Aggregate split fills
    print("\nPhase 4: Aggregating split fills into single trades...")
    aggregated = parser._aggregate_trades(valid_trades)
    print(f"  Final aggregated trades: {len(aggregated):,}")

    # Phase 5: Save to verification_trades
    print("\nPhase 5: Saving to verification_trades table...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.cursor().execute("DELETE FROM verification_trades")
    conn.commit()
    saved = save_trades_to_verification_table(conn, aggregated)
    conn.close()
    print(f"  Saved {saved:,} trades to verification_trades.")

    # Audit log
    audit = {
        "parser_fix": "ghost_exit_orphan_purge_active",
        "processing_mode": "single_threaded_sequential",
        "total_files_found": len(target_files),
        "files_ok": files_ok,
        "files_failed": files_failed,
        "total_fills_extracted": len(all_unique_fills),
        "total_ghost_fills_at_parser": len(all_ghosts),
        "unpaired_fill_qty": unpaired,
        "position_warnings": len(pos_warnings),
        "session_boundary_trades_dropped": len(sb_dropped),
        "total_verification_trades": saved,
        "ghost_sample": all_ghosts[:500],
    }
    with open(str(AUDIT_LOG_FILE), "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, default=str)

    print(f"\nAudit log written to {AUDIT_LOG_FILE}")
    print("\nTask 1 COMPLETE - verification_trades populated with ghost-sequence-corrected data.")


if __name__ == "__main__":
    main()
