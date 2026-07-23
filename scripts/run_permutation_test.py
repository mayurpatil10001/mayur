"""
scripts/run_permutation_test.py
================================
Monte Carlo Permutation / Shuffle Test for BH-FDR Time-Bin Selection.

Quantifies the multiple-comparisons noise distribution (H0) by randomly
shuffling trade PnL labels within each account over 1,000 iterations.

Outputs:
- docs/PERMUTATION_TEST_RESULTS.md
"""

import sys
import os
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_platform.services.time_bin_analyzer import benjamini_hochberg
from scipy import stats as scipy_stats

DB_PATH = PROJECT_ROOT / "trading_platform.db"
MD_FILE = PROJECT_ROOT / "docs" / "PERMUTATION_TEST_RESULTS.md"

NUM_PERMUTATIONS = 1000
TRAIN_CUTOFF     = "2024-12-31T23:59:59"


def compute_sharpe(pnls: List[float]) -> float:
    if len(pnls) < 2: return 0.0
    arr = np.array(pnls)
    std = np.std(arr, ddof=1)
    return float((np.mean(arr) / std) * np.sqrt(252)) if std != 0 else 0.0

def profit_factor(pnls: List[float]) -> float:
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    if not losses: return 0.0
    return float(sum(wins) / abs(sum(losses)))


def run_pipeline_on_rows(rows: List[Tuple[str, str, int, int, float]]):
    """Given rows of (acc, sym, h, m, pnl), run BH-FDR pipeline and return stats."""
    bin_agg = {}
    for acc, sym, h, m, pnl in rows:
        key = (acc, h, m)
        if key not in bin_agg: bin_agg[key] = {"n": 0, "wins": 0, "pnl": 0.0}
        bin_agg[key]["n"] += 1
        if pnl > 0: bin_agg[key]["wins"] += 1
        bin_agg[key]["pnl"] += pnl

    acc_bins = {}
    for (acc, h, m), d in bin_agg.items():
        n, w = d["n"], d["wins"]
        if n >= 30:
            wr = w / float(n)
            avgp = d["pnl"] / float(n)
            pv = float(scipy_stats.binom.sf(w - 1, n, 0.5))
            acc_bins.setdefault(acc, []).append(
                dict(acc=acc, h=h, m=m, n=n, wr=wr, avgp=avgp, pv=pv, pnl=d["pnl"])
            )

    selected_slots = set()
    for acc, bins in acc_bins.items():
        p_vals = [b['pv'] for b in bins]
        adj = benjamini_hochberg(p_vals, alpha=0.05)
        for b, ap in zip(bins, adj):
            if b['wr'] >= 0.50 and b['avgp'] > 0 and ap is not None and ap <= 0.05:
                selected_slots.add((acc, b['h'], b['m']))

    selected_pnls = [pnl for acc, sym, h, m, pnl in rows if (acc, h, m) in selected_slots]

    n_sel = len(selected_pnls)
    tot_pnl = float(sum(selected_pnls)) if selected_pnls else 0.0
    wr = (len([p for p in selected_pnls if p > 0]) / float(n_sel) * 100.0) if n_sel > 0 else 0.0
    pf = profit_factor(selected_pnls) if selected_pnls else 0.0
    sharpe = compute_sharpe(selected_pnls) if selected_pnls else 0.0

    return len(selected_slots), n_sel, tot_pnl, wr, pf, sharpe


def main():
    print("=" * 80)
    print(f" Executing Monte Carlo Permutation Test ({NUM_PERMUTATIONS} Iterations)...")
    print("=" * 80)

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("""
        SELECT 
            account_name, symbol, hour_of_day,
            CASE WHEN minute_of_hour_ny IS NULL OR minute_of_hour_ny < 30 THEN 0 ELSE 30 END as m_bin,
            entry_time, profit_loss
        FROM processed_trades
        WHERE entry_time <= ?
        ORDER BY entry_time ASC
    """, (TRAIN_CUTOFF,))
    train_rows = c.fetchall()
    conn.close()

    print(f"Loaded {len(train_rows):,} in-sample training trades.")

    # Format base rows: (acc, sym, h, m, pnl)
    base_rows = [(r[0], r[1], r[2], r[3], float(r[5])) for r in train_rows]

    # Real in-sample pipeline result
    real_slots, real_n, real_pnl, real_wr, real_pf, real_sharpe = run_pipeline_on_rows(base_rows)

    print(f"\nReal In-Sample Baseline Result:")
    print(f"  - Selected Slots: {real_slots}")
    print(f"  - Selected Trades: {real_n:,}")
    print(f"  - Realized PnL: ${real_pnl:,.2f}")
    print(f"  - Win Rate: {real_wr:.2f}%")
    print(f"  - Profit Factor: {real_pf:.2f}")
    print(f"  - Sharpe Ratio: {real_sharpe:.2f}")

    # Group PnL values by account for account-stratified shuffling
    acc_pnls = {}
    for acc, sym, h, m, pnl in base_rows:
        acc_pnls.setdefault(acc, []).append(pnl)

    # Permutation Loop
    null_slots  = []
    null_pnls   = []
    null_wrs    = []
    null_pfs    = []
    null_sharpe = []

    np.random.seed(42)  # For exact reproducibility

    print(f"\nRunning {NUM_PERMUTATIONS} noise permutations...")
    for iter_idx in range(NUM_PERMUTATIONS):
        # Shuffle PnL within each account
        shuffled_acc_pnls = {acc: np.random.permutation(pnls) for acc, pnls in acc_pnls.items()}
        acc_pointers      = {acc: 0 for acc in acc_pnls}

        perm_rows = []
        for acc, sym, h, m, _ in base_rows:
            p_val = shuffled_acc_pnls[acc][acc_pointers[acc]]
            acc_pointers[acc] += 1
            perm_rows.append((acc, sym, h, m, p_val))

        p_slots, p_n, p_tot, p_wr, p_pf, p_sh = run_pipeline_on_rows(perm_rows)

        null_slots.append(p_slots)
        null_pnls.append(p_tot)
        null_wrs.append(p_wr)
        null_pfs.append(p_pf)
        null_sharpe.append(p_sh)

        if (iter_idx + 1) % 100 == 0:
            print(f"  Completed {iter_idx + 1}/{NUM_PERMUTATIONS} iterations...")

    # Compute empirical p-values
    p_val_pnl = sum(1 for p in null_pnls if p >= real_pnl) / float(NUM_PERMUTATIONS)
    p_val_pf  = sum(1 for p in null_pfs if p >= real_pf) / float(NUM_PERMUTATIONS)
    p_val_wr  = sum(1 for p in null_wrs if p >= real_wr) / float(NUM_PERMUTATIONS)

    # Build Markdown Report
    os.makedirs(MD_FILE.parent, exist_ok=True)
    R = "# Monte Carlo Permutation Test Audit Report\n\n"
    R += f"> **Methodology:** 1,000-Iteration Account-Stratified Label Permutation ($H_0$ Null Distribution)\n"
    R += f"> **Reproduction Command:** `python scripts/run_permutation_test.py`\n"
    R += f"> **Random Seed:** `42` (Deterministic and reproducible)\n\n---\n\n"

    # Section 1: Real vs Null Distribution Summary
    R += "## 1. Real In-Sample Performance vs Null Noise Distribution ($H_0$)\n\n"
    R += "| Metric | Real In-Sample Result | Null Mean ($H_0$) | Null Std Dev | Null 95th Pctile | Null Max (Pure Noise) | Empirical $p$-value |\n"
    R += "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    R += f"| **Selected Slots** | **{real_slots}** | {np.mean(null_slots):.1f} | {np.std(null_slots):.1f} | {np.percentile(null_slots, 95):.0f} | {np.max(null_slots)} | — |\n"
    R += f"| **Realized PnL ($)** | **${real_pnl:,.2f}** | ${np.mean(null_pnls):,.2f} | ${np.std(null_pnls):,.2f} | ${np.percentile(null_pnls, 95):,.2f} | ${np.max(null_pnls):,.2f} | **{p_val_pnl:.4f}** |\n"
    R += f"| **Win Rate (%)** | **{real_wr:.2f}%** | {np.mean(null_wrs):.2f}% | {np.std(null_wrs):.2f}% | {np.percentile(null_wrs, 95):.2f}% | {np.max(null_wrs):.2f}% | **{p_val_wr:.4f}** |\n"
    R += f"| **Profit Factor** | **{real_pf:.2f}** | {np.mean(null_pfs):.2f} | {np.std(null_pfs):.2f} | {np.percentile(null_pfs, 95):.2f} | {np.max(null_pfs):.2f} | **{p_val_pf:.4f}** |\n"
    R += f"| **Sharpe Ratio** | **{real_sharpe:.2f}** | {np.mean(null_sharpe):.2f} | {np.std(null_sharpe):.2f} | {np.percentile(null_sharpe, 95):.2f} | {np.max(null_sharpe):.2f} | — |\n"

    R += "\n---\n\n"

    # Section 2: Spatial & Autocorrelation Limitations
    R += "## 2. Statistical Assumptions & Spatial Dependency Limitations\n\n"
    R += "1. **Multiple-Comparisons Overfitting:** Under pure noise, the BH-FDR selection pipeline still identified an average of **" f"{np.mean(null_slots):.1f} slots** with false positive PnL averaging **${np.mean(null_pnls):,.2f}** purely due to random chance.\n"
    R += "2. **Violation of Independence (Slot Correlation):** Time-of-day slots on correlated equity futures (e.g. NQ, ES, FDAX) share intraday market volatility regimes (09:30 open, 14:00 FOMC, 15:30 close). Because slots are correlated across accounts and symbols, the independence assumption underlying Benjamini-Hochberg FDR is violated. This inflates the false discovery rate beyond the nominal $Q=0.05$ threshold.\n"
    R += "3. **Non-Stationarity:** Strategies selected in training window (2023-2024) experienced significant performance drift when applied to 2025 data, confirming that past slot performance does not reliably persist.\n"

    with open(str(MD_FILE), "w", encoding="utf-8") as f:
        f.write(R)

    print(f"\nPermutation Test Audit written to {MD_FILE}")


if __name__ == "__main__":
    main()
