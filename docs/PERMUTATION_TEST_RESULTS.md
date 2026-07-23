# Monte Carlo Permutation Test Audit Report

> **Methodology:** 1,000-Iteration Account-Stratified Label Permutation ($H_0$ Null Distribution)
> **Reproduction Command:** `python scripts/run_permutation_test.py`
> **Random Seed:** `42` (Deterministic and reproducible)

---

## 1. Real In-Sample Performance vs Null Noise Distribution ($H_0$)

| Metric | Real In-Sample Result | Null Mean ($H_0$) | Null Std Dev | Null 95th Pctile | Null Max (Pure Noise) | Empirical $p$-value |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Selected Slots** | **39** | 17.0 | 3.9 | 24 | 29 | — |
| **Realized PnL ($)** | **$944,400.35** | $261,925.88 | $100,670.64 | $436,442.19 | $705,252.87 | **0.0000** |
| **Win Rate (%)** | **62.60%** | 59.86% | 1.08% | 61.75% | 65.87% | **0.0190** |
| **Profit Factor** | **2.14** | 1.53 | 0.18 | 1.85 | 2.21 | **0.0030** |
| **Sharpe Ratio** | **1.66** | 0.94 | 0.27 | 1.42 | 2.00 | — |

---

## 2. Statistical Assumptions & Spatial Dependency Limitations

1. **Multiple-Comparisons Overfitting:** Under pure noise, the BH-FDR selection pipeline still identified an average of **17.0 slots** with false positive PnL averaging **$261,925.88** purely due to random chance.
2. **Violation of Independence (Slot Correlation):** Time-of-day slots on correlated equity futures (e.g. NQ, ES, FDAX) share intraday market volatility regimes (09:30 open, 14:00 FOMC, 15:30 close). Because slots are correlated across accounts and symbols, the independence assumption underlying Benjamini-Hochberg FDR is violated. This inflates the false discovery rate beyond the nominal $Q=0.05$ threshold.
3. **Non-Stationarity:** Strategies selected in training window (2023-2024) experienced significant performance drift when applied to 2025 data, confirming that past slot performance does not reliably persist.
