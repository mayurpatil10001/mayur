# Walk-Forward Test (WFT) Audit — Stage 4 Production Pipeline

> **Methodology:** Rolling Walk-Forward Test across 562 trading days.
> Training: **252 days** | Test: **63 days** | Total Folds: **5**

> This is **true out-of-sample testing** — the pipeline never sees test data during slot selection.

---

## 1. Out-of-Sample Executive Summary

| Metric | Out-of-Sample Baseline (All Clean Trades) | Out-of-Sample WFT Pipeline | WFT Advantage |
| :--- | ---: | ---: | ---: |
| **Total Realized PnL ($)** | $-3,604,015.50 | **$-287,062.50** | **+$3,316,953.00** |
| **Total Trades Executed** | 50,057 | **806** | **-49,251** |
| **Average PnL / Trade ($)** | $-72.00 | **$-356.16** | **$-284.16** |
| **Win Rate (%)** | 49.98% | **53.72%** | **+3.74%** |
| **Profit Factor** | 0.95 | **0.72** | **-0.24** |
| **Annualized Sharpe Ratio** | -0.17 | **-1.34** | **-1.16** |
| **Max Drawdown ($)** | $-3,934,625.50 | **$-327,395.00** | **+$3,607,230.50** |
| **Best Single Trade ($)** | $95,550.00 | **$21,950.00** | **$-73,600.00** |
| **Worst Single Trade ($)** | $-99,075.00 | **$-30,900.00** | **+$68,175.00** |

| **WFT Folds Profitable** | — | **2 / 5 folds** | **40% of folds profitable** |
| **Avg Slots Selected per Fold** | — | **27.6 slots** | — |

---

## 2. Fold-by-Fold Walk-Forward Results

| Fold | Train Period | Test Period | Slots Selected | OOS Baseline PnL ($) | OOS Pipeline PnL ($) | OOS Pipeline WR (%) | OOS Avg/Trade ($) | OOS Profit Factor | OOS Sharpe |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **1 (LOSS)** | 2023-09-04 to 2024-08-27 | 2024-08-28 to 2024-11-11 | 32 | $-1,629,280.00 | **$-130,210.00** | **40.8%** | **$-1,041.68** | **0.44** | **-3.09** |
| **2 (OK)** | 2024-01-12 to 2024-11-11 | 2024-11-12 to 2025-01-29 | 30 | $-1,153,174.50 | **$20,365.00** | **63.5%** | **$323.25** | **2.33** | **4.21** |
| **3 (LOSS)** | 2024-04-03 to 2025-01-29 | 2025-01-30 to 2025-04-15 | 21 | $628,237.50 | **$-94,937.50** | **60.1%** | **$-416.39** | **0.72** | **-1.26** |
| **4 (LOSS)** | 2024-06-16 to 2025-04-15 | 2025-04-16 to 2025-06-30 | 27 | $-1,015,981.00 | **$-90,947.50** | **44.8%** | **$-557.96** | **0.56** | **-2.68** |
| **5 (OK)** | 2024-08-28 to 2025-06-30 | 2025-07-01 to 2025-09-16 | 28 | $-433,817.50 | **$8,667.50** | **58.1%** | **$38.18** | **1.04** | **0.18** |

---

## 3. Cumulative Out-of-Sample PnL Progression

| Fold | Test Period End | Cumulative WFT PnL ($) | Cumulative Baseline PnL ($) | WFT Advantage ($) |
| :--- | :--- | ---: | ---: | ---: |
| **1** | 2024-11-11 | **$-130,210.00** | $-1,629,280.00 | **+$1,499,070.00** |
| **2** | 2025-01-29 | **$-109,845.00** | $-2,782,454.50 | **+$2,672,609.50** |
| **3** | 2025-04-15 | **$-204,782.50** | $-2,154,217.00 | **+$1,949,434.50** |
| **4** | 2025-06-30 | **$-295,730.00** | $-3,170,198.00 | **+$2,874,468.00** |
| **5** | 2025-09-16 | **$-287,062.50** | $-3,604,015.50 | **+$3,316,953.00** |

---

## 4. In-Sample vs Out-of-Sample Generalization Check

> This validates whether the pipeline truly generalizes or is overfitted.

| Metric | In-Sample (Stage 4 Production) | Out-of-Sample WFT | Generalization Gap |
| :--- | ---: | ---: | ---: |
| **Total Realized PnL ($)** | $2,008,054.86 | **$-287,062.50** | **$-2,295,117.36** |
| **Avg PnL / Trade ($)** | $224.29 | **$-356.16** | **$-580.45** |
| **Win Rate (%)** | $63.59 | **$53.72** | **$-9.87** |
| **Profit Factor** | $1.77 | **$0.72** | **$-1.05** |
| **Sharpe Ratio** | $1.36 | **$-1.34** | **$-2.70** |

---

## 5. Best and Worst Performing Folds

### Best Fold: Fold 2 (Test: 2024-11-12 to 2025-01-29)

- **Out-of-Sample PnL:** $20,365.00
- **Win Rate:** 63.5%
- **Avg PnL / Trade:** $323.25
- **Profit Factor:** 2.33
- **Slots Selected in Training:** 30

### Worst Fold: Fold 1 (Test: 2024-08-28 to 2024-11-11)

- **Out-of-Sample PnL:** $-130,210.00
- **Win Rate:** 40.8%
- **Avg PnL / Trade:** $-1,041.68
- **Profit Factor:** 0.44
- **Slots Selected in Training:** 32

---

## 6. Monthly Out-of-Sample PnL Distribution

| Month | Trades | Total PnL ($) | Win Rate (%) | Avg PnL/Trade ($) |
| :--- | ---: | ---: | ---: | ---: |
| **2024-01** | 243 | **$6,280.00** | 58.4% | $25.84 |
| **2024-02** | 1,163 | **$30,885.00** | 63.1% | $26.56 |
| **2024-03** | 1,402 | **$129,715.00** | 64.0% | $92.52 |
| **2024-04** | 2,141 | **$223,950.00** | 58.9% | $104.60 |
| **2024-05** | 1,008 | **$-66,084.38** | 56.6% | $-65.56 |
| **2024-06** | 254 | **$91,361.74** | 69.3% | $359.69 |
| **2024-07** | 86 | **$34,337.50** | 62.8% | $399.27 |
| **2024-08** | 589 | **$188,642.50** | 72.8% | $320.28 |
| **2024-09** | 63 | **$84,732.50** | 68.3% | $1,344.96 |
| **2024-10** | 111 | **$24,600.00** | 55.9% | $221.62 |
| **2024-11** | 88 | **$-83,740.00** | 62.5% | $-951.59 |
| **2024-12** | 189 | **$98,275.00** | 70.4% | $519.97 |
| **2025-01** | 49 | **$57,782.50** | 75.5% | $1,179.23 |
| **2025-02** | 75 | **$106,297.50** | 57.3% | $1,417.30 |
| **2025-03** | 176 | **$123,207.50** | 72.7% | $700.04 |
| **2025-04** | 491 | **$550,352.50** | 71.7% | $1,120.88 |
| **2025-05** | 110 | **$62,230.00** | 64.5% | $565.73 |
| **2025-06** | 230 | **$19,197.50** | 69.1% | $83.47 |
| **2025-07** | 106 | **$81,975.00** | 75.5% | $773.35 |
| **2025-08** | 148 | **$62,597.50** | 66.2% | $422.96 |
| **2025-09** | 73 | **$35,535.00** | 71.2% | $486.78 |
| **2025-10** | 158 | **$145,925.00** | 72.8% | $923.58 |

---

## 7. Statistical Significance of Out-of-Sample Results

- **One-sample t-test** (H0: mean OOS PnL = 0):
  - t-statistic: **-2.3885**
  - p-value: **0.017146**
  - Result: **Statistically significant (p < 0.05)** - OOS returns are NOT due to chance.

- **Total OOS Trades:** 806
- **Mean OOS PnL:** $-356.16 per trade
- **Std Dev OOS PnL:** $4233.31 per trade
---

## 8. Final WFT Verdict

| Question | Answer |
| :--- | :--- |
| Does the pipeline work out-of-sample? | **NO - Total OOS PnL: $-287,062.50** |
| How many folds were profitable? | **2 out of 5 folds (40%)** |
| Out-of-sample Win Rate? | **53.72%** |
| Out-of-sample Profit Factor? | **0.72** |
| Out-of-sample Avg/Trade? | **$-356.16** |
