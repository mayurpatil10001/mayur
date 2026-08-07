"""
scripts/promote_to_production.py
==================================
Production Promotion Script - Phase 6
Generated: 2026-08-08

PURPOSE
-------
Promotes clean data (GFRE v3 ghost-cleaned dataset) to processed_trades
in the production trading_platform.db.

SAFETY REQUIREMENTS (all must pass before promotion is allowed)
---------------------------------------------------------------
1. Step 1 (Flagged files):  0 Class B anomalies in 50-file sample
2. Step 2 (ZB/ZN mult):     CURRENTLY BLOCKED - confirmed multiplier bug
3. Step 3 (Jul-09 cascade): Classifier handles orphaned CLOSEs correctly (CLEAR)
4. Step 4 (Sim integrity):  817 non-sim failures require investigation (BLOCKED)

AUDIT FINDINGS SUMMARY (from step5_close_open_items, 2026-08-08)
-----------------------------------------------------------------
Step 1: 0/50 Class B cases. 50/50 Class A (ghost fills present and dropped).
        Total 13,878 flagged files estimated ~100% Class A.
        NOTE: Billion-dollar PnL deltas in TS_5/TS_6/IPS_TM_11 are a SEPARATE
        unit-conversion issue in PnL storage, not a GFRE classification bug.

Step 2: ZB/ZN multiplier CONFIRMED BUGGY.
        processed_trades stores ZB/ZN PnL at multiplier=1 (raw price-delta),
        not multiplier=1000 as CME spec requires.
        Examples: LONG 1x @ 117.03125->117.06250, expected=$-31.25, actual=$+0.03
        This is a BLOCKING defect. 1,672 ZB + 1,694 ZN = 3,366 affected trades.
        Fix: recompute profit_loss for all ZB/ZN trades using multiplier=1000.

Step 3: Jul-09 IPS_TM_7 NQ cascade definitively traced.
        Ghost IDX=28: BUY 2x @ 29764.75 OC=OPEN, note=EMPTY (ghost OPEN).
        This ghost OPEN removal causes 2 real CLOSE fills (IDX=48,49 SELL at
        23:23/23:30) to become ORPHANED - they pair against a LONG position
        the GFRE removed, so clean FIFO ends with 2 unpaired CLOSEs.
        CONCLUSION: ORPHANED_CLOSE_AFTER_GHOST_OPEN.
        Delta: dirty=$-5,655 vs clean=$-13,205 (delta=$-7,550).
        HANDLING: The Jul-09 file produces correct ghost removal but the 2
        orphaned CLOSEs should be logged as ORPHANED_CLOSE_POST_GHOST_OPEN,
        not counted as additional ghost fills. The clean_trades PnL for this
        file is incorrect by $7,550 until the orphaned-CLOSE handler is added.
        This is NOT a classifier bug (the ghost OPEN is correctly identified).
        It IS a gap in how unpaired CLOSEs are handled post-removal.
        ACTION REQUIRED: Add ORPHANED_CLOSE handling rule before promotion.

Step 4: Sim-account integrity failure explanation PARTIALLY CONFIRMED.
        Total integrity failures: 1,006 (2.6% of files, not 17.4% as README states).
        Sim-pattern accounts: 189/1,006 (18.8%).
        Non-sim accounts: 817/1,006 (81.2%) - README explanation DOES NOT HOLD.
        Top non-sim failures: ES-TM_9 (114), TM_9 (94), ES-TM_1 (61), etc.
        Sample pattern: most non-sim failures have raw_fills=1-6, clean=0, bypass=1
        with note_coverage=0.0. This is the bypass mode issue, not overnight carry.
        817 non-sim failures block promotion until root cause is documented.

Step 5: Gap 1 (NQ Jun 10-22): NO ACTUAL GAP FOUND. NQ accounts show full coverage
        across the window (10 accounts, 251-611 fills per day through Jun 18).
        Jun 19 dropped to 27 fills (7 accounts) and Jun 22 to 11 fills (4 accounts).
        This aligns with NQM26->NQU26 rollover week (Jun 19 expiry).
        CONCLUSION: Not an order rejection gap - it was a rollover-week taper.

        Gap 2 (IPS_TM_7 after Jul 17): CONFIRMED DATA GAP.
        Last valid IPS_TM_7 file: 2026-07-17. No valid files after that date.
        5 files found with corrupted timestamps (23677-07-17, 33376-05-01, etc.)
        indicating binary log parser timestamp corruption, not actual Jul-2026 files.
        CONCLUSION: IPS_TM_7 account stopped producing logs after Jul 17, 2026.
        The account was deactivated or renamed (ES-IPS_TM_7 continues independently).

USAGE
-----
    python scripts/promote_to_production.py --dry-run   # shows what would happen
    python scripts/promote_to_production.py --confirm   # actually executes

DO NOT RUN --confirm without explicit sign-off after ZB/ZN and Step 4 are fixed.

CURRENT STATUS: NO-GO
Blocking items:
  - Step 2: ZB/ZN multiplier bug must be fixed in processed_trades (3,366 trades)
  - Step 3: Orphaned-CLOSE handling rule must be implemented in GFRE
  - Step 4: 817 non-sim integrity failures must be root-caused and documented
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
MAX_NON_SIM_FAILURES    = 50      # >50 non-sim integrity failures = blocked
ZB_ZN_MULTIPLIER_FIXED  = False   # Set True after ZB/ZN PnL recompute is run
ORPHANED_CLOSE_HANDLED  = False   # Set True after GFRE orphaned-CLOSE rule added
STEP4_EXPLAINED         = False   # Set True after non-sim failures root-caused

# Current audit state (hardcoded from 2026-08-08 run)
AUDIT = {
    "step1_class_b_count":       0,
    "step1_total_flagged":    13878,
    "step2_zb_zn_ok":         False,   # CONFIRMED BUG
    "step2_affected_trades":   3366,
    "step3_conclusion":        "ORPHANED_CLOSE_AFTER_GHOST_OPEN",
    "step3_promotion_block":   True,   # until handler added
    "step4_total_failed":      1006,
    "step4_non_sim_failed":     817,
    "step4_promotion_block":   True,   # until root-caused
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
    """Check hardcoded audit findings for promotion blockers."""
    failures = []
    if AUDIT["step1_class_b_count"] > MAX_CLASS_B_ANOMALIES:
        failures.append(
            f"Step 1: {AUDIT['step1_class_b_count']} unexplained Class B anomalies "
            f"(threshold: {MAX_CLASS_B_ANOMALIES})"
        )
    if not AUDIT["step2_zb_zn_ok"]:
        failures.append(
            f"Step 2: ZB/ZN multiplier bug confirmed. "
            f"{AUDIT['step2_affected_trades']:,} trades have PnL stored at "
            f"multiplier=1 instead of 1000. Recompute required before promotion."
        )
    if AUDIT["step3_promotion_block"]:
        failures.append(
            f"Step 3: Orphaned-CLOSE-after-ghost-OPEN handler not yet implemented. "
            f"Jul-09 IPS_TM_7 NQ has 2 orphaned CLOSE fills creating $7,550 PnL error. "
            f"Add ORPHANED_CLOSE_POST_GHOST_OPEN rule to GFRE, re-run affected files."
        )
    if AUDIT["step4_promotion_block"]:
        failures.append(
            f"Step 4: {AUDIT['step4_non_sim_failed']:,} integrity failures in non-sim accounts "
            f"not explained by overnight carry. Root cause must be documented."
        )
    return failures


def check_db_safety_gates(conn: sqlite3.Connection) -> tuple:
    """Run runtime DB safety checks. Returns (failures, warnings) lists."""
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
    print(f"  Current processed_trades rows: {current_count:,}")

    if current_count == 0:
        failures.append("FATAL: processed_trades is empty — nothing to back up or promote from.")
        return failures, warnings

    # Check ZB/ZN PnL magnitude as a quick sanity
    c.execute("""
        SELECT AVG(ABS(profit_loss)) FROM processed_trades
        WHERE symbol LIKE 'ZB%' OR symbol LIKE 'ZN%'
    """)
    bond_avg_pnl = c.fetchone()[0] or 0
    if bond_avg_pnl < 1.0:
        failures.append(
            f"FATAL: ZB/ZN average |PnL| = {bond_avg_pnl:.4f} — "
            f"this confirms multiplier bug (should be ~hundreds of dollars). "
            f"Run ZB/ZN PnL recompute script before promoting."
        )
    else:
        print(f"  ZB/ZN avg |PnL| = {bond_avg_pnl:.2f} - OK")

    # Row count sanity
    data_clean_dir = PROJECT_ROOT / "data_clean"
    if "verification_trades" in tables:
        c.execute("SELECT COUNT(*) FROM verification_trades")
        vt_count = c.fetchone()[0]
        print(f"  verification_trades rows: {vt_count:,}")
        if vt_count < current_count * 0.5:
            failures.append(
                f"FATAL: verification_trades ({vt_count:,}) < 50% of "
                f"processed_trades ({current_count:,}). Refusing to overwrite."
            )
        elif vt_count < current_count * 0.9:
            warnings.append(
                f"WARNING: verification_trades ({vt_count:,}) is "
                f"{100*(1 - vt_count/current_count):.1f}% smaller than "
                f"processed_trades. Review before confirming."
            )

    # PnL aggregate sanity
    c.execute("SELECT SUM(profit_loss) FROM processed_trades")
    prod_pnl = c.fetchone()[0] or 0
    print(f"  processed_trades total PnL: ${prod_pnl:,.2f}")

    if not AUDIT_REPORT.exists():
        warnings.append(
            f"WARNING: Audit report not found at {AUDIT_REPORT}. "
            "Run step5_close_open_items.py first."
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
    """Perform the actual promotion. dry_run=True shows plan only."""
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in c.fetchall()}

    # Determine source
    if "verification_trades" in tables:
        source_table = "verification_trades"
        c.execute(f"SELECT COUNT(*) FROM {source_table}")
        source_count = c.fetchone()[0]
        print(f"  Source: {source_table} ({source_count:,} rows)")
    else:
        print("  ERROR: No promotion source found.")
        print("  Expected 'verification_trades' table or data_clean/ directory.")
        return False

    if dry_run:
        print("  [DRY-RUN] Steps that WOULD execute:")
        print(f"    1. CREATE TABLE processed_trades_backup_TIMESTAMP AS SELECT * FROM processed_trades")
        print(f"    2. DELETE FROM processed_trades ({source_count:,} rows would be replaced)")
        print(f"    3. INSERT INTO processed_trades SELECT ... FROM {source_table}")
        print(f"    4. Verify row count: {source_count:,}")
        print(f"    5. Spot-check aggregate PnL")
        return True

    # Step 1: Backup
    backup_table = create_backup(conn, dry_run=False)

    # Step 2: Replace
    print(f"  Replacing processed_trades from {source_table}...")

    # Find common columns
    c.execute("PRAGMA table_info(processed_trades)")
    pt_cols = {r[1] for r in c.fetchall()}
    c.execute(f"PRAGMA table_info({source_table})")
    src_cols = {r[1] for r in c.fetchall()}
    common_cols = sorted(pt_cols & src_cols - {"rowid"})
    cols_str = ", ".join(common_cols)

    c.execute("DELETE FROM processed_trades")
    c.execute(f"INSERT INTO processed_trades ({cols_str}) SELECT {cols_str} FROM {source_table}")
    conn.commit()

    # Step 3: Verify
    c.execute("SELECT COUNT(*) FROM processed_trades")
    promoted_count = c.fetchone()[0]
    c.execute("SELECT SUM(profit_loss) FROM processed_trades")
    total_pnl = c.fetchone()[0] or 0

    print(f"  Promoted: {promoted_count:,} rows now in processed_trades.")
    print(f"  Total PnL: ${total_pnl:,.2f}")

    if promoted_count != source_count:
        print(f"  WARNING: Row count mismatch! Expected {source_count:,}, got {promoted_count:,}")
        return False

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
            print("To fix:")
            if not AUDIT["step2_zb_zn_ok"]:
                print("  ZB/ZN: Run a PnL recompute: UPDATE processed_trades SET profit_loss = ...")
                print("         ... WHERE symbol LIKE 'ZB%' OR symbol LIKE 'ZN%'")
                print("         using the correct multiplier=1000 formula.")
            if AUDIT["step3_promotion_block"]:
                print("  Jul-09: Add ORPHANED_CLOSE_POST_GHOST_OPEN handling in ghost_fill_engine.py")
                print("          then re-run ghost_fill_cleaner.py on IPS_TM_7 files.")
            if AUDIT["step4_promotion_block"]:
                print("  Step 4: Investigate top non-sim integrity-failure accounts:")
                print("          ES-TM_9 (114), TM_9 (94), ES-TM_1 (61), ES-TM_2 (52), ES-TM_10 (45)")
                print("          These have bypass=1 and note_coverage=0.0 — NOT sim accounts.")
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
