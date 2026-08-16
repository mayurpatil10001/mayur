"""
scripts/promote_to_production.py
==================================
Production Promotion Script - Phase 6
Generated: 2026-08-08  |  Updated: 2026-08-08 (Steps A/B/C resolved)

PURPOSE
-------
Promotes clean data (GFRE v3 ghost-cleaned dataset) to processed_trades
in the production trading_platform.db.

SAFETY REQUIREMENTS
-------------------
1. Step 1 (Flagged files):  0 Class B anomalies in 50-file sample               [CLEAR]
2. Step 2/A (ZB/ZN mult):   clean_trades has correct multiplier=1000             [CLEAR]
3. Step 3/B (Jul-09 handler): ORPHANED_CLOSE_POST_GHOST_OPEN in GFE             [CLEAR]
4. Step 4/C (Integrity):    817 cases = Trade Evaluator sim, Step B fixes all   [CLEAR]

AUDIT FINDINGS (updated 2026-08-08, all from computed evidence)
-----------------------------------------------------------------
Step 1: 0/50 Class B cases (50-file sample: top-20 + random-30, seed=42). CLOSED.

Step 2 (original) + Step A (resolution):
  Original finding: processed_trades stores ZB/ZN PnL at mult=1 (3,366 trades).
  Step A finding: clean_trades (trading_platform_clean_v2.db) has CORRECT mult=1000.
  8-trade comparison (4 ZB + 4 ZN): all MATCH@1000. Population avg: ZB=$175, ZN=$87.
  OUTCOME 1: Bug exists only in legacy processed_trades, which is wholesale replaced
  during promotion. The UPDATE SQL fix from the previous report is NOT needed.
  STATUS: CLOSED.

Step 3 (original) + Step B (resolution):
  Root cause: ghost OPEN removed -> CLOSE fills arrive with position=0 -> were
  mis-treated as new OPEN entries, corrupting FIFO. 36,699 orphaned fills across
  991/1000 highest-delta ghost files (dataset-wide scan, errors=0).
  Fix: ORPHANED_CLOSE_POST_GHOST_OPEN guard added to pair_fills_to_trades() in
  ghost_fill_engine.py. Jul-09 re-verified: clean_net=-$7,075 (was -$13,205).
  2 rejected fills correctly logged. Residual delta $1,420 is expected.
  REQUIRED: ghost_fill_cleaner.py --reset to regenerate staging DB with fix.
  STATUS: CLOSED (staging DB must be regenerated).

Step 4 (original) + Step C (resolution):
  Root cause established by direct raw fill inspection of 9 files / 3 accounts.
  All 817 "non-sim" integrity failures are Sierra Chart Trade Evaluator simulation
  sessions. Trade Evaluator fills have note='' (genuinely empty, not parsing error)
  and msgtxt='Trading Evaluator (Filled). Info: Trade simulation fill...'.
  Files have <5 raw fills (below ADAPTIVE_MIN_FILLS=5 bypass threshold), so bypass
  does not trigger. Ghost classifier correctly removes the ghost OPEN. Remaining
  CLOSE fills become orphaned -- same pattern as Step 3. Step B fix resolves all 817.
  STATUS: CLOSED.

Step 5:
  Gap 1 (NQ Jun 10-22): CLOSED -- rollover-week taper (NQM26 expiry Jun 19), not
  an order rejection. Full coverage through Jun 18, taper Jun 19-22, resume Jun 23.
  Gap 2 (IPS_TM_7 after Jul 17): DOCUMENTED -- data gap, not blocking. 552 valid
  files through Jul-17. Corrupted timestamps in 5 files are binary parser artifacts.

USAGE
-----
    python scripts/promote_to_production.py --dry-run   # shows what would happen
    python scripts/promote_to_production.py --confirm   # actually executes

CURRENT STATUS: CONDITIONAL GO
All three original blockers resolved. Required before executing:
  1. Run: python ghost_fill_cleaner.py --reset
     (Regenerates staging DB with ORPHANED_CLOSE fix. Existing DB is pre-fix.)
  2. Run: python scripts/promote_to_production.py --dry-run (confirm gates pass)
  3. Human reviews step5_preproduction_audit_report.md and executes --confirm

DO NOT RUN --confirm until ghost_fill_cleaner.py --reset has completed.
"""
from __future__ import annotations
import sys
import os
import sqlite3
import datetime
import argparse
import pathlib
import csv

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
DB_PATH      = PROJECT_ROOT / "trading_platform.db"
AUDIT_REPORT = PROJECT_ROOT / "docs" / "audits" / "step5_preproduction_audit_report.md"

# ---------------------------------------------------------------------------
# Safety gate thresholds (from audit findings)
# ---------------------------------------------------------------------------
MAX_CLASS_B_ANOMALIES   = 0       # Any unexplained anomaly blocks promotion

# Current audit state (updated 2026-08-08 after Steps A/B/C resolutions)
AUDIT = {
    # Step 1: unchanged
    "step1_class_b_count":       0,
    "step1_total_flagged":    13878,

    # Step 2 -> Step A: clean_trades verified at correct multiplier=1000
    # Bug was in legacy processed_trades only; wholesale replaced at promotion.
    "step2_zb_zn_ok":         True,    # CLOSED: 8/8 trades MATCH@1000 in clean_trades
    "step2_clean_trades_zb":  6760,    # ZB rows in staging
    "step2_clean_trades_zn":  6082,    # ZN rows in staging
    "step2_avg_pnl_zb":       175.06,  # correct dollar range
    "step2_avg_pnl_zn":        87.73,  # correct dollar range

    # Step 3 -> Step B: ORPHANED_CLOSE handler implemented in ghost_fill_engine.py
    # Jul-09 re-verified: clean_net=-7075 (was -13205). 2 rejected fills logged.
    # Dataset-wide: 991/1000 ghost files had orphaned CLOSEs; 36,699 fills affected.
    # REQUIRES: ghost_fill_cleaner.py --reset before staging DB is promotion-ready.
    "step3_conclusion":        "ORPHANED_CLOSE_POST_GHOST_OPEN",
    "step3_handler_in_gfe":   True,    # CLOSED: guard in pair_fills_to_trades()
    "step3_promotion_block":   False,  # CLEAR (but staging DB needs regen)
    "step3_jul09_clean_net":   -7075,  # corrected (was -13205)
    "step3_files_affected":    991,    # from 1000-file scan
    "step3_orphaned_fills":    36699,  # from 1000-file scan

    # Step 4 -> Step C: root cause = Sierra Chart Trade Evaluator sessions
    # All 817 "non-sim" failures are Trade Evaluator fills with empty notes.
    # Step B ORPHANED_CLOSE handler resolves these too. No separate fix needed.
    "step4_total_failed":      1006,
    "step4_non_sim_failed":     817,
    "step4_root_cause":        "SierraChart_TradeEvaluator_sim_sessions",
    "step4_fix":               "Step_B_handler",
    "step4_promotion_block":   False,  # CLEAR

    # Step 5: unchanged
    "step5_nq_gap":            "NO_GAP_ROLLOVER_WEEK_TAPER",
    "step5_tm7_gap":           "CONFIRMED_DATA_GAP_AFTER_2026_07_17",
}


def print_audit_summary():
    """Print the current audit state clearly before any action."""
    print("=" * 80)
    print(" Pre-Production Audit Summary (2026-08-08)")
    print("=" * 80)
    print(f"  Step 1 (Flagged files):  {AUDIT['step1_class_b_count']} Class B cases in 50-file sample - CLEAR")
    print(f"  Step 2 (ZB/ZN mult):     {'OK' if AUDIT['step2_zb_zn_ok'] else 'BLOCKED - ' + str(AUDIT['step2_affected_trades']) + ' trades have wrong PnL'}")
    print(f"  Step 3 (Jul-09):         {AUDIT['step3_conclusion']} - {'BLOCKED (handler needed)' if AUDIT['step3_promotion_block'] else 'CLEAR'}")
    print(f"  Step 4 (Integrity):      {AUDIT['step4_non_sim_failed']:,} non-sim failures - {'BLOCKED' if AUDIT['step4_promotion_block'] else 'CLEAR'}")
    print(f"  Step 5 NQ gap:           {AUDIT['step5_nq_gap']}")
    print(f"  Step 5 TM7 gap:          {AUDIT['step5_tm7_gap']}")
    print()


def check_static_audit_gates() -> list:
    """Check hardcoded audit findings for promotion blockers.

    All three original blockers are now CLEAR (Steps A/B/C, 2026-08-08):
      Step 2/A: clean_trades ZB/ZN PnL verified at multiplier=1000
      Step 3/B: ORPHANED_CLOSE_POST_GHOST_OPEN guard in ghost_fill_engine.py
      Step 4/C: 817 'non-sim' failures = Trade Evaluator sim, resolved by Step B

    PREREQUISITE: ghost_fill_cleaner.py --reset must be run to regenerate staging DB
    before this script is executed with --confirm. The existing staging DB was
    produced with the pre-fix GFRE and contains corrupt FIFO output.
    """
    failures = []
    if AUDIT["step1_class_b_count"] > MAX_CLASS_B_ANOMALIES:
        failures.append(
            f"Step 1: {AUDIT['step1_class_b_count']} unexplained Class B anomalies "
            f"(threshold: {MAX_CLASS_B_ANOMALIES})"
        )
    if not AUDIT["step2_zb_zn_ok"]:
        failures.append(
            "Step 2: ZB/ZN multiplier not verified in clean_trades. "
            "Run Step A verification before promotion."
        )
    if AUDIT["step3_promotion_block"]:
        failures.append(
            "Step 3: ORPHANED_CLOSE_POST_GHOST_OPEN handler not in ghost_fill_engine.py. "
            "Implement the guard in pair_fills_to_trades() and re-run the cleaner."
        )
    if AUDIT["step4_promotion_block"]:
        failures.append(
            f"Step 4: {AUDIT['step4_non_sim_failed']:,} integrity failures root cause "
            "not documented. Run Step C investigation first."
        )
    # Staging-DB freshness gate: warn if cleaner has not been re-run
    # (cannot enforce programmatically without a run-timestamp in the DB)
    failures.append(
        "PREREQUISITE: Confirm ghost_fill_cleaner.py --reset has been run after "
        "the 2026-08-08 ORPHANED_CLOSE fix before executing --confirm. "
        "The pre-fix staging DB must not be promoted."
    ) if not _staging_db_is_fresh() else None
    return [f for f in failures if f]


def _staging_db_is_fresh() -> bool:
    """Check if staging DB was produced after the ORPHANED_CLOSE fix (2026-08-08).

    Heuristic: if the clean_trades DB does not exist or its mtime predates
    the ghost_fill_engine.py mtime, it is stale.
    """
    import pathlib, os
    clean_db  = pathlib.Path(__file__).parent.parent / "trading_platform_clean_v2.db"
    gfe_path  = pathlib.Path(__file__).parent.parent / \
                "trading_platform" / "services" / "ghost_fill_engine.py"
    if not clean_db.exists():
        return False  # not yet generated
    db_mtime  = clean_db.stat().st_mtime
    gfe_mtime = gfe_path.stat().st_mtime if gfe_path.exists() else 0
    return db_mtime > gfe_mtime  # staging DB newer than engine = re-run after fix


def check_db_safety_gates(conn: sqlite3.Connection) -> tuple:
    """Run runtime DB safety checks. Returns (failures, warnings) lists.

    NOTE: ZB/ZN PnL check is now done against clean_trades in the staging DB
    (trading_platform_clean_v2.db), not against the legacy processed_trades in
    trading_platform.db. Legacy processed_trades intentionally has the mult=1 bug;
    it will be wholesale replaced by clean_trades during promotion.
    """
    failures = []
    warnings = []
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in c.fetchall()}

    if "processed_trades" not in tables:
        failures.append("FATAL: processed_trades table does not exist.")
        return failures, warnings

    c.execute("SELECT COUNT(*) FROM processed_trades")
    current_count = c.fetchone()[0]
    print(f"  Current processed_trades rows (legacy): {current_count:,}")

    if current_count == 0:
        failures.append("FATAL: processed_trades is empty — nothing to back up.")
        return failures, warnings

    # Check ZB/ZN PnL in STAGING DB (clean_trades), not legacy processed_trades.
    # Legacy processed_trades has mult=1 bug — expected and will be replaced.
    # clean_trades must have correct multiplier ($175/$87 verified in Step A).
    staging_db_path = PROJECT_ROOT / "trading_platform_clean_v2.db"
    if staging_db_path.exists():
        try:
            sconn = sqlite3.connect(str(staging_db_path), timeout=30)
            sc = sconn.cursor()
            sc.execute("""
                SELECT AVG(ABS(pnl_dollars)) FROM clean_trades
                WHERE base_symbol IN ('ZB','ZN')
            """)
            bond_avg_pnl = sc.fetchone()[0] or 0
            sconn.close()
            if bond_avg_pnl < 1.0:
                failures.append(
                    f"FATAL: ZB/ZN avg |pnl_dollars| in clean_trades = {bond_avg_pnl:.4f} "
                    f"(expected ~$100-500). Staging DB may have multiplier bug or not "
                    f"been regenerated after the Step B fix."
                )
            else:
                print(f"  clean_trades ZB/ZN avg |pnl_dollars| = {bond_avg_pnl:.2f} - OK")
        except Exception as e:
            warnings.append(f"WARNING: Could not query clean_trades ZB/ZN PnL: {e}")
    else:
        failures.append(
            f"FATAL: Staging DB not found: {staging_db_path}. "
            "Run ghost_fill_cleaner.py --reset first."
        )

    # Row count sanity: clean_trades must be much larger than legacy processed_trades
    if staging_db_path.exists():
        try:
            sconn = sqlite3.connect(str(staging_db_path), timeout=30)
            sc = sconn.cursor()
            sc.execute("SELECT COUNT(*) FROM clean_trades")
            ct_count = sc.fetchone()[0]
            sconn.close()
            print(f"  clean_trades rows (staging): {ct_count:,}")
            if ct_count < current_count * 0.5:
                failures.append(
                    f"FATAL: clean_trades ({ct_count:,}) < 50% of current "
                    f"processed_trades ({current_count:,}). Refusing to overwrite."
                )
        except Exception as e:
            warnings.append(f"WARNING: Could not query clean_trades count: {e}")

    # PnL aggregate of legacy DB (informational only)
    c.execute("SELECT SUM(profit_loss) FROM processed_trades")
    prod_pnl = c.fetchone()[0] or 0
    print(f"  legacy processed_trades total PnL: ${prod_pnl:,.2f} (will be replaced)")

    if not AUDIT_REPORT.exists():
        warnings.append(
            f"WARNING: Audit report not found at {AUDIT_REPORT}."
        )

    return failures, warnings


def create_backup(conn: sqlite3.Connection, dry_run: bool) -> str:
    """Create a timestamped backup of processed_trades."""
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_table = f"processed_trades_backup_{ts}"
    if dry_run:
        print(f"  [DRY-RUN] Would create backup: {backup_table}")
        return backup_table
    c = conn.cursor()
    print(f"  Creating backup table: {backup_table} ...")
    c.execute(f"DROP TABLE IF EXISTS {backup_table}")
    c.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM processed_trades")
    conn.commit()
    c.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = c.fetchone()[0]
    print(f"  Backup verified: {backup_count:,} rows saved to {backup_table}.")
    return backup_table


def run_promotion(conn: sqlite3.Connection, dry_run: bool) -> bool:
    """Perform the actual promotion. dry_run=True shows plan only.

    Source: clean_trades in trading_platform_clean_v2.db (3.24M rows, GFRE v3 output)
    Target: processed_trades in trading_platform.db (will be backed up then replaced)

    The staging DB (trading_platform_clean_v2.db) must have been regenerated AFTER
    the 2026-08-08 ORPHANED_CLOSE fix. Use _staging_db_is_fresh() to verify.
    """
    staging_db_path = PROJECT_ROOT / "trading_platform_clean_v2.db"

    if not staging_db_path.exists():
        print(f"  ERROR: Staging DB not found: {staging_db_path}")
        print("  Run: python ghost_fill_cleaner.py --reset")
        return False

    # Connect to staging DB to get source count and column list
    sconn = sqlite3.connect(str(staging_db_path), timeout=60)
    sc = sconn.cursor()
    sc.execute("SELECT COUNT(*) FROM clean_trades")
    source_count = sc.fetchone()[0]
    sc.execute("PRAGMA table_info(clean_trades)")
    src_col_info = sc.fetchall()  # [(cid, name, type, notnull, dflt, pk), ...]
    src_cols = [r[1] for r in src_col_info]
    print(f"  Source: clean_trades in trading_platform_clean_v2.db ({source_count:,} rows)")

    # Get target schema
    c = conn.cursor()
    c.execute("PRAGMA table_info(processed_trades)")
    pt_col_info = c.fetchall()
    pt_cols = {r[1] for r in pt_col_info}

    # Map clean_trades columns → processed_trades columns.
    # FIX v3.3: corrected account→account_name; use base_symbol for the
    # 'symbol' column (not the raw contract-code 'symbol' field), so that
    # ZB/ZN post-check WHERE symbol IN ('ZB','ZN') works correctly.
    COLUMN_MAP = {
        "pnl_dollars":   "profit_loss",
        "entry_time":    "entry_time",
        "exit_time":     "exit_time",
        "entry_price":   "entry_price",
        "exit_price":    "exit_price",
        "quantity":      "quantity",
        "direction":     "side",
        "account":       "account_name",   # FIX: was "account", target col is account_name
        "base_symbol":   "symbol",         # FIX: use base_symbol (ZB) not raw symbol (ZBM24)
        "trade_date":    "trade_date",
    }
    # Columns to explicitly skip (raw symbol = full contract code, superseded by base_symbol→symbol)
    SKIP_SRC_COLS = {"symbol", "id"}

    if dry_run:
        print("  [DRY-RUN] Steps that WOULD execute:")
        print(f"    1. Backup: CREATE TABLE processed_trades_backup_TIMESTAMP AS SELECT * FROM processed_trades")
        print(f"    2. Replace: DELETE FROM processed_trades (current legacy rows)")
        print(f"    3. Insert: {source_count:,} rows from clean_trades (GFRE v3.3)")
        print(f"    4. Verify row count matches {source_count:,}")
        print(f"    5. Spot-check ZB/ZN avg|profit_loss| > $1 in promoted data")

        # Show mapping preview
        print(f"  Column mapping preview:")
        for sc_name in src_cols:
            if sc_name in SKIP_SRC_COLS:
                continue
            target_name = COLUMN_MAP.get(sc_name, sc_name)
            if target_name in pt_cols:
                print(f"    {sc_name:25s} -> {target_name}")
        sconn.close()
        return True

    # --- Step 1: Backup ---
    backup_table = create_backup(conn, dry_run=False)

    # --- Step 2: Build INSERT using mapped columns ---
    insert_target_cols = []
    select_src_exprs   = []
    for sc_name in src_cols:
        if sc_name in SKIP_SRC_COLS:
            continue
        target_name = COLUMN_MAP.get(sc_name, sc_name)
        if target_name in pt_cols:
            select_src_exprs.append(sc_name)
            insert_target_cols.append(target_name)

    if not insert_target_cols:
        print("  ERROR: No common columns found between clean_trades and processed_trades.")
        sconn.close()
        return False

    print(f"  Columns to transfer ({len(insert_target_cols)}): {', '.join(insert_target_cols)}")

    # --- Step 3: Transfer (in a transaction — rollback if verify fails) ---
    print(f"  Replacing processed_trades from clean_trades...")
    c.execute(f"ATTACH DATABASE '{staging_db_path}' AS staging")
    c.execute("BEGIN")
    c.execute("DELETE FROM processed_trades")
    target_col_str = ", ".join(insert_target_cols)
    c.execute(
        f"INSERT INTO processed_trades ({target_col_str}) "
        f"SELECT {', '.join(select_src_exprs)} FROM staging.clean_trades"
    )

    # --- Step 4: Verify BEFORE committing ---
    c.execute("SELECT COUNT(*) FROM processed_trades")
    promoted_count = c.fetchone()[0]
    c.execute("SELECT SUM(profit_loss) FROM processed_trades")
    total_pnl = c.fetchone()[0] or 0
    # FIX: symbol column now holds base symbol (ZB/ZN), so this filter works correctly
    c.execute("SELECT AVG(ABS(profit_loss)) FROM processed_trades WHERE symbol IN ('ZB','ZN')")
    zb_zn_check = c.fetchone()[0] or 0

    print(f"  Promoted: {promoted_count:,} rows now in processed_trades.")
    print(f"  Total PnL: ${total_pnl:,.2f}")
    print(f"  ZB/ZN avg |profit_loss|: ${zb_zn_check:.2f} (must be > $1)")

    if promoted_count != source_count:
        print(f"  CRITICAL: Row count mismatch ({promoted_count:,} != {source_count:,}). Rolling back.")
        conn.rollback()
        c.execute("DETACH DATABASE staging")
        sconn.close()
        return False

    if zb_zn_check < 1.0:
        print(f"  CRITICAL: ZB/ZN avg |profit_loss| = {zb_zn_check:.4f} (expected ~$100-500). Rolling back.")
        conn.rollback()
        c.execute("DETACH DATABASE staging")
        sconn.close()
        return False

    # All checks passed — commit
    conn.commit()
    c.execute("DETACH DATABASE staging")
    sconn.close()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Promote GFRE v3 clean data to processed_trades (production).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without modifying the DB.")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually execute the promotion (requires explicit flag).")
    parser.add_argument("--skip-audit-gate", action="store_true",
                        help="Skip audit-based gates (DANGEROUS - use only for debugging).")
    parser.add_argument("--skip-db-gate", action="store_true",
                        help="Skip DB runtime gates (DANGEROUS).")
    parser.add_argument("--db", type=str, default=str(DB_PATH),
                        help=f"Path to database (default: trading_platform.db)")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("ERROR: Must specify either --dry-run or --confirm.")
        print("  --dry-run  = show what would happen, no changes made")
        print("  --confirm  = actually execute (requires sign-off on audit findings)")
        sys.exit(1)

    db_path = pathlib.Path(args.db)
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)

    print_audit_summary()
    print(f"Database: {db_path}")
    print(f"Mode:     {'DRY-RUN (no changes)' if args.dry_run else 'LIVE PROMOTION'}")
    print()

    # --- Static audit gates ---
    if not args.skip_audit_gate:
        print("Checking audit-based safety gates...")
        audit_failures = check_static_audit_gates()
        if audit_failures:
            print("\nAUDIT GATES FAILED - Promotion BLOCKED:")
            for f in audit_failures:
                print(f"  * {f}")
            print()
            print("Required action:")
            print("  Run: python ghost_fill_cleaner.py --reset")
            print("       (Regenerates staging DB with ORPHANED_CLOSE fix applied)")
            print("  Then re-run: python scripts/promote_to_production.py --dry-run")
            if not args.dry_run:
                sys.exit(3)
            else:
                print("\n[DRY-RUN continuing despite failures to show what would happen]\n")
    else:
        print("  WARNING: Audit gates SKIPPED (--skip-audit-gate).")

    # --- DB runtime gates ---
    conn = sqlite3.connect(str(db_path), timeout=60)
    if not args.skip_db_gate:
        print("\nChecking DB runtime safety gates...")
        db_failures, db_warnings = check_db_safety_gates(conn)
        for w in db_warnings:
            print(f"  {w}")
        if db_failures:
            print("\nDB SAFETY GATES FAILED:")
            for f in db_failures:
                print(f"  * {f}")
            conn.close()
            sys.exit(4)
        print("  DB gates passed.")
    else:
        print("  WARNING: DB gates SKIPPED (--skip-db-gate).")

    # --- Execute ---
    print("\nProceeding with promotion...")
    success = run_promotion(conn, dry_run=args.dry_run)
    conn.close()

    if success:
        if args.dry_run:
            print("\nDry-run complete. No changes were made.")
            print("Address the blocking items above, then run with --confirm.")
        else:
            print("\nPromotion complete. processed_trades is now GFRE v3 clean.")
    else:
        print("\nPromotion failed. See errors above.")
        sys.exit(5)


if __name__ == "__main__":
    main()
