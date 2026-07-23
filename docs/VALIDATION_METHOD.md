# Quantitative Validation Methodology & Train/Test Split Standard

## 1. Objective and Anti-Overfitting Safeguards

This document defines the strict quantitative validation methodology used to evaluate whether time-of-day slot selection (via Benjamini-Hochberg False Discovery Rate correction) exhibits a genuine out-of-sample trading edge or is an artifact of multiple-comparisons data snooping.

To prevent look-ahead bias and data leakage, the following rules are strictly enforced:

1. **Chronological Splitting Only:** Time-series data must never be randomly split (e.g., $k$-fold cross-validation with random shuffling). Data is partitioned chronologically into an in-sample training period and a strictly held-out out-of-sample test period.
2. **Frozen Slot Selection:** Time-bin selection criteria (minimum trades $n \ge 30$, win rate $\ge 50\%$, average PnL $> 0$, and BH-FDR adjusted $p$-value $Q \le 0.05$) are computed **exclusively** on the in-sample training window.
3. **Single Out-of-Sample Evaluation:** The frozen time slots selected during training are evaluated **exactly once** on the held-out test window. Selection criteria are never re-tuned or modified based on test window performance.
4. **Sample Size Caveats:** Any time slot with $n < 100$ total trades is explicitly caveated as statistically unreliable regardless of point estimate performance.

---

## 2. Dataset Partitioning & Date Ranges

The total production database (`processed_trades`) contains **126,991 clean, uncorrupted trades** spanning **597 unique trading days** from **September 4, 2023** to **October 31, 2025**.

```text
  Full Historical Domain: 2023-09-04 to 2025-10-31 (597 Trading Days)
  ┌──────────────────────────────────────────────┬──────────────────────────────────┐
  │ IN-SAMPLE TRAINING WINDOW                    │ OUT-OF-SAMPLE TEST WINDOW        │
  │ 2023-09-04 to 2024-12-31                     │ 2025-01-01 to 2025-10-31         │
  │ 404 Trading Days (~67.7%)                     │ 193 Trading Days (~32.3%)        │
  │ 85,251 Clean Trades                          │ 41,740 Clean Trades              │
  └──────────────────────────────────────────────┴──────────────────────────────────┘
```

### Partition Summary Table

| Partition | Date Range | Trading Days | Trade Count | Percentage of Trades | Purpose |
| :--- | :--- | ---: | ---: | ---: | :--- |
| **In-Sample (Train)** | `2023-09-04` to `2024-12-31` | 404 days | 85,251 | 67.13% | Slot discovery & BH-FDR thresholding |
| **Out-of-Sample (Test)** | `2025-01-01` to `2025-10-31` | 193 days | 41,740 | 32.87% | Frozen strategy performance evaluation |
| **Total Full Sample** | `2023-09-04` to `2025-10-31` | 597 days | 126,991 | 100.00% | Complete history |

---

## 3. Multiple-Comparisons & Permutation Testing Protocol

Testing 5,472 candidate account/time-bin slots creates a high risk of false positive discovery. To quantify this risk:

1. **BH-FDR Multiple Testing Correction:** Benjamini-Hochberg procedure is applied at target false discovery rate $Q = 0.05$ across all candidate slots within each account.
2. **Permutation Shuffle Test ($\ge 1,000$ Iterations):** Trade PnLs are randomly shuffled across time slots within each account while preserving trade counts and slot structure. The complete BH-FDR pipeline is re-run on each noise permutation to establish the null distribution ($H_0$) of top-slot profits, win rates, and profit factors under pure chance.
3. **Spatial & Temporal Autocorrelation Limitation:** Because time-of-day slots across correlated equity index futures (e.g., NQ and ES during 14:00–16:00 NY) are dependent, the independent-test assumption of BH-FDR is partially violated. This limitation is explicitly documented alongside all statistical findings.
