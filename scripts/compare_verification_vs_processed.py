"""
scripts/compare_verification_vs_processed.py
=============================================
Phase 2: Compare verification_trades (ghost-orphan-fix applied) vs
processed_trades (old data) across key quality and financial metrics.

Outputs: VERIFICATION_VS_PROCESSED_COMPARISON.md
"""
import sys
import os
import sqlite3
import datetime
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
DB_PATH = PROJECT_ROOT / "trading_platform.db"
REPORT_FILE = PROJECT_ROOT / "VERIFICATION_VS_PROCESSED_COMPARISON.md"


def calc_stats(rows):
    """rows = list of (profit_loss, entry_time, exit_time, duration_minutes)"""
    if not rows:
        return {"trades": 0, "total_pnl": 0.0, "win_rate": 0.0, "avg_pnl": 0.0,
                "negative_dur": 0, "inverted": 0, "profit_factor": 0.0}
    pnls = [r[0] for r in rows]
    trades = len(pnls)
    total_pnl = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / trades * 100
    avg_pnl = total_pnl / trades
    pf = (sum(wins) / abs(sum(losses))) if losses else 0.0
    negative_dur = sum(1 for r in rows if r[3] is not None and r[3] < 0)
    inverted = sum(1 for r in rows if r[1] and r[2] and r[1] > r[2])
    return {
        "trades": trades,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "avg_pnl": avg_pnl,
        "profit_factor": pf,
        "negative_dur": negative_dur,
        "inverted": inverted,
    }


def main():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Fetch from processed_trades (OLD)
    print("Fetching processed_trades (OLD)...")
    c.execute("""
        SELECT profit_loss, entry_time, exit_time, duration_minutes
        FROM processed_trades
    """)
    old_rows = c.fetchall()

    # Fetch from verification_trades (NEW/FIXED)
    print("Fetching verification_trades (FIXED)...")
    c.execute("""
        SELECT profit_loss, entry_time, exit_time, duration_minutes
        FROM verification_trades
    """)
    new_rows = c.fetchall()

    # Yearly distribution
    def yearly_breakdown(rows, label):
        yearly = {}
        for r in rows:
            yr = r[1][:4] if r[1] else "??"
            if yr not in yearly:
                yearly[yr] = []
            yearly[yr].append(r[0])
        return yearly

    old_yearly = yearly_breakdown(old_rows, "OLD")
    new_yearly = yearly_breakdown(new_rows, "NEW")

    # Distinct account counts
    c.execute("SELECT COUNT(DISTINCT account_name) FROM processed_trades")
    old_accounts = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT account_name) FROM verification_trades")
    new_accounts = c.fetchone()[0]

    # Per-account summary for accounts present in BOTH tables
    c.execute("""
        SELECT p.account_name,
               COUNT(p.trade_id) as old_count,
               SUM(p.profit_loss) as old_pnl
        FROM processed_trades p
        GROUP BY p.account_name
        ORDER BY old_count DESC
        LIMIT 20
    """)
    old_account_rows = c.fetchall()

    c.execute("""
        SELECT v.account_name,
               COUNT(v.trade_id) as new_count,
               SUM(v.profit_loss) as new_pnl
        FROM verification_trades v
        GROUP BY v.account_name
        ORDER BY new_count DESC
        LIMIT 20
    """)
    new_account_rows = c.fetchall()

    conn.close()

    old_stats = calc_stats(old_rows)
    new_stats = calc_stats(new_rows)

    trades_delta = new_stats["trades"] - old_stats["trades"]
    pnl_delta = new_stats["total_pnl"] - old_stats["total_pnl"]
    wr_delta = new_stats["win_rate"] - old_stats["win_rate"]

    report = f"""# Verification vs Processed Trades Comparison
## Ghost-Orphan-Sequence Fix Impact Analysis (562 Trading Days)

This report compares the **OLD `processed_trades`** (no ghost-orphan purge) against
the **NEW `verification_trades`** (ghost-exit -> orphaned-entry purge ACTIVE).

---

## 1. High-Level Quality & Financial Metrics

| Metric | OLD `processed_trades` | NEW `verification_trades` (Fixed) | Delta |
| :--- | :--- | :--- | :--- |
| **Total Trades** | {old_stats['trades']:,} | {new_stats['trades']:,} | {trades_delta:+,} |
| **Total Realized PnL ($)** | ${old_stats['total_pnl']:,.2f} | ${new_stats['total_pnl']:,.2f} | **${pnl_delta:+,.2f}** |
| **Win Rate (%)** | {old_stats['win_rate']:.2f}% | {new_stats['win_rate']:.2f}% | **{wr_delta:+.2f}%** |
| **Avg PnL / Trade ($)** | ${old_stats['avg_pnl']:.2f} | ${new_stats['avg_pnl']:.2f} | **${new_stats['avg_pnl']-old_stats['avg_pnl']:+.2f}** |
| **Profit Factor** | {old_stats['profit_factor']:.2f} | {new_stats['profit_factor']:.2f} | **{new_stats['profit_factor']-old_stats['profit_factor']:+.2f}** |
| **Inverted Trades (Exit < Entry)** | {old_stats['inverted']} | **{new_stats['inverted']}** | **{new_stats['inverted']-old_stats['inverted']:+d}** |
| **Negative Duration Trades** | {old_stats['negative_dur']} | **{new_stats['negative_dur']}** | **{new_stats['negative_dur']-old_stats['negative_dur']:+d}** |
| **Distinct Accounts** | {old_accounts} | {new_accounts} | {new_accounts-old_accounts:+d} |

---

## 2. Yearly Trade Volume Comparison

| Year | OLD Trades | OLD Total PnL ($) | NEW Trades | NEW Total PnL ($) | Trade Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    all_years = sorted(set(list(old_yearly.keys()) + list(new_yearly.keys())))
    for yr in all_years:
        op = old_yearly.get(yr, [])
        np_ = new_yearly.get(yr, [])
        report += (f"| **{yr}** | {len(op):,} | ${sum(op):,.2f} | "
                   f"{len(np_):,} | ${sum(np_):,.2f} | {len(np_)-len(op):+,} |\n")

    report += f"""
---

## 3. Top Account Trade Count Comparison

| Account Name | OLD Trades | OLD PnL ($) | NEW Trades | NEW PnL ($) | Trade Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    # Build lookup dict for new accounts
    new_account_dict = {r[0]: (r[1], r[2]) for r in new_account_rows}
    for r in old_account_rows:
        acc, old_ct, old_pnl = r
        new_ct, new_pnl = new_account_dict.get(acc, (0, 0.0))
        delta = (new_ct or 0) - (old_ct or 0)
        report += (f"| **{acc}** | {old_ct:,} | ${old_pnl:,.2f} | "
                   f"{new_ct or 0:,} | ${new_pnl or 0:,.2f} | {delta:+,} |\n")

    report += f"""
---

## 4. Ghost-Orphan Fix Impact Summary

| Fix Applied | Description |
| :--- | :--- |
| **Ghost Exit Detected** | Ghost fill tagged `suggests_ghost=True` |
| **Previous Behavior** | Ghost exit was silently skipped (`continue`) — orphaned entry leg remained in memory |
| **New Behavior** | Ghost exit now ALSO purges matching orphaned open_legs entries and updates `running_position` |
| **Sequence Corruption Prevention** | Next real trade entry is no longer misidentified as an exit against a stranded position |

---

## 5. Conclusion

- **Total Trade Count Change:** {trades_delta:+,} trades
- **Total PnL Impact:** ${pnl_delta:+,.2f}
- **Data Quality (Inverted/Negative Duration Trades):** {new_stats['inverted']} inverted | {new_stats['negative_dur']} negative-duration
"""

    with open(str(REPORT_FILE), "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written: {REPORT_FILE}")
    print(f"\nSummary:")
    print(f"  OLD trades: {old_stats['trades']:,} | PnL: ${old_stats['total_pnl']:,.2f} | WR: {old_stats['win_rate']:.2f}%")
    print(f"  NEW trades: {new_stats['trades']:,} | PnL: ${new_stats['total_pnl']:,.2f} | WR: {new_stats['win_rate']:.2f}%")
    print(f"  Delta:      {trades_delta:+,} trades | PnL: ${pnl_delta:+,.2f} | WR: {wr_delta:+.2f}%")


if __name__ == "__main__":
    main()
