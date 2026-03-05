"""
SC-First Import: Use Sierra Chart trade list as source of truth.

Flow:
  1. Wipe account from DB (e.g. V_SIM16)
  2. Import from SC Activity export FILE (Open/Close pairing = SC-exact trades)
  3. Optionally run purge (multi-day, EOD, outliers) on aligned trades only

No paste. File-based only. Uses paths from app_settings / project.

Usage:
  python run_sc_first_import.py [--file PATH] [--account NAME] [--purge]

  --file     Path to ALLTradeActivityLogExport (tab). Default: ALLTradeActivityLogExport_vsim16 11052025-12192025.txt
  --account  Account to wipe before import (default V_SIM16). Import uses accounts in file.
  --purge    Run purge_anomalies after import (multi-day, EOD, outliers)
"""
import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from trading_platform.services.trade_import_service import TradeImportService
from trading_platform.services.binary_log_parser import BinaryLogParser

DEFAULT_FILE = os.path.join(ROOT, "ALLTradeActivityLogExport_vsim16 11052025-12192025.txt")
DEFAULT_ACCOUNT = "V_SIM16"
DB_PATH = os.path.join(ROOT, "trading_platform.db")


def wipe_account(account: str) -> tuple:
    """Remove account from processed_trades and pending_fills. Returns (pt_deleted, pf_deleted)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM processed_trades WHERE UPPER(account_name) = ?", (account.upper(),))
    pt = c.rowcount
    c.execute("DELETE FROM pending_fills WHERE UPPER(account_name) = ?", (account.upper(),))
    pf = c.rowcount
    conn.commit()
    conn.close()
    return pt, pf


def main():
    ap = argparse.ArgumentParser(description="SC-first import: wipe, import from file, optional purge")
    ap.add_argument("--file", default=DEFAULT_FILE, help="Path to ALLTradeActivityLogExport (tab)")
    ap.add_argument("--account", default=DEFAULT_ACCOUNT, help="Account to wipe before import")
    ap.add_argument("--purge", action="store_true", help="Run purge_anomalies after import")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        print(f"File not found: {args.file}")
        return 2

    print(f"\n--- SC-FIRST IMPORT ---")
    print(f"File: {args.file}")
    print(f"Account to wipe: {args.account}")

    # 1. Wipe
    print(f"\n1. Wiping {args.account}...")
    pt, pf = wipe_account(args.account)
    print(f"   Deleted: {pt} processed_trades, {pf} pending_fills")

    # 2. Import from file (Open/Close = SC-exact)
    print(f"\n2. Importing from SC Activity export (Open/Close pairing)...")
    with open(args.file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    svc = TradeImportService(db_path=DB_PATH)
    result = svc.import_trades(content)
    print(f"   New trades: {result.new_trades}")
    print(f"   Duplicates: {result.duplicates}")
    if result.errors:
        for e in result.errors[:10]:
            print(f"   Error: {e}")
        if len(result.errors) > 10:
            print(f"   ... and {len(result.errors) - 10} more errors")

    # 3. Optional purge
    if args.purge and result.new_trades > 0:
        print(f"\n3. Running purge (multi-day, EOD, outliers)...")
        parser = BinaryLogParser(db_path=DB_PATH)
        breakdown = parser.purge_anomalies(account=[args.account], purge_overnight=True)
        for acc, data in breakdown.items():
            print(f"   {acc}: {data}")

    # 4. Summary
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM processed_trades WHERE UPPER(account_name) = ?",
        (args.account.upper(),),
    )
    total = c.fetchone()[0]
    conn.close()
    print(f"\n--- DONE: {total} trades for {args.account} ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
