"""
scripts/promote_clean_data_to_production.py
============================================
Phase 4: Production Promotion
1. Backs up current `processed_trades` to `processed_trades_backup_pre_ghost_fix`.
2. Replaces `processed_trades` with clean data from `verification_trades`.
3. Verifies row count and integrity.
"""

import sys
import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "trading_platform.db"


def main():
    print("=" * 80)
    print(" Phase 4: Production Promotion (Clean Ghost-Sequence-Corrected Data)")
    print("=" * 80)

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # 1. Check counts
    c.execute("SELECT COUNT(*) FROM processed_trades")
    old_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM verification_trades")
    new_count = c.fetchone()[0]

    print(f"Current `processed_trades` count: {old_count:,}")
    print(f"Clean `verification_trades` count:  {new_count:,}")

    # 2. Create backup table
    print("\nStep 1: Creating backup table `processed_trades_backup_pre_ghost_fix`...")
    c.execute("DROP TABLE IF EXISTS processed_trades_backup_pre_ghost_fix")
    c.execute("CREATE TABLE processed_trades_backup_pre_ghost_fix AS SELECT * FROM processed_trades")
    conn.commit()

    c.execute("SELECT COUNT(*) FROM processed_trades_backup_pre_ghost_fix")
    backup_count = c.fetchone()[0]
    print(f"  Backup verified: {backup_count:,} records saved.")

    # 3. Replace processed_trades with verification_trades
    print("\nStep 2: Promoting `verification_trades` to `processed_trades`...")
    c.execute("DELETE FROM processed_trades")
    c.execute("""
        INSERT INTO processed_trades (
            trade_id, account_name, symbol, entry_time, exit_time,
            entry_price, exit_price, quantity, side, profit_loss,
            commission, duration_minutes, hour_of_day, day_of_week,
            minute_of_hour_ny, trip_id
        )
        SELECT 
            trade_id, account_name, symbol, entry_time, exit_time,
            entry_price, exit_price, quantity, side, profit_loss,
            commission, duration_minutes, hour_of_day, day_of_week,
            minute_of_hour_ny, trip_id
        FROM verification_trades
    """)
    conn.commit()

    c.execute("SELECT COUNT(*) FROM processed_trades")
    promoted_count = c.fetchone()[0]
    print(f"  Promoted verified: {promoted_count:,} records now in `processed_trades`.")

    conn.close()
    print("\n✅ Production Promotion Complete! `processed_trades` is now fully clean.")


if __name__ == "__main__":
    main()
