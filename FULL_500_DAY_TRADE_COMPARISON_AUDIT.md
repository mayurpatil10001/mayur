# Full 562 Trading-Day Audit & Pipeline Comparison Report

## Executive Overview

This audit verifies the complete trade dataset stored in `processed_trades` covering **562 distinct trading days** spanning **2023-09-04 to 2025-10-31** across **114 active accounts**.

| Metric | Verified Value | Target Constraint | Status |
| :--- | :--- | :--- | :--- |
| **Start Date** | `2023-09-04` | `2023-09-04` | **100% Match** |
| **End Date** | `2025-10-31` | `2025-10-31` | **100% Match** |
| **Total Trading Days** | **562 Days** | ~500 Days | **Exceeds Target (+62 days)** |
| **Total Processed Trades** | **733,847 Trades** | Full Dataset | **Verified** |
| **Total Active Accounts** | **114 Accounts** | All active | **Verified** |

---

## 1. Timeline & Monthly Breakdown (2023-09 to 2025-10)

The dataset spans 27 calendar months of continuous trading execution:

| Year-Month | Trading Days | Total Trades | Win Rate | Total PnL ($) |
| :--- | :--- | :--- | :--- | :--- |
| **2023-09** | 20 | 469 | 43.50% | $-8,380.00 |
| **2023-10** | 19 | 523 | 43.79% | $-15,030.00 |
| **2023-11** | 22 | 401 | 46.38% | $-3,430.00 |
| **2023-12** | 20 | 338 | 43.79% | $-9,270.00 |
| **2024-01** | 22 | 7,544 | 45.12% | $-31,200.00 |
| **2024-02** | 25 | 14,016 | 46.06% | $-65,320.00 |
| **2024-03** | 25 | 31,420 | 60.27% | $-390.00 |
| **2024-04** | 26 | 51,530 | 60.73% | $-313,660.00 |
| **2024-05** | 27 | 65,131 | 57.19% | $-571,137.54 |
| **2024-06** | 25 | 69,792 | 51.04% | $-1,789,892.38 |
| **2024-07** | 27 | 48,790 | 51.55% | $-2,114,570.00 |
| **2024-08** | 26 | 66,569 | 50.04% | $-1,743,955.00 |
| **2024-09** | 26 | 35,380 | 52.06% | $-1,003,522.50 |
| **2024-10** | 27 | 52,354 | 45.39% | $-2,193,697.50 |
| **2024-11** | 25 | 57,339 | 48.64% | $-2,103,297.50 |
| **2024-12** | 27 | 51,611 | 49.14% | $-2,056,345.00 |
| **2025-01** | 27 | 69,325 | 47.73% | $-2,595,610.00 |
| **2025-02** | 24 | 23,144 | 50.95% | $-432,420.00 |
| **2025-03** | 23 | 12,289 | 51.40% | $-251,510.00 |
| **2025-04** | 2 | 1,106 | 53.89% | $-552.50 |
| **2025-05** | 1 | 390 | 44.36% | $-14,812.50 |
| **2025-06** | 23 | 29,103 | 57.33% | $-662,440.00 |
| **2025-07** | 27 | 29,318 | 53.24% | $-869,875.00 |
| **2025-08** | 15 | 7,797 | 44.80% | $-491,015.00 |
| **2025-09** | 12 | 3,343 | 41.70% | $-226,405.00 |
| **2025-10** | 19 | 4,663 | 56.53% | $-188,465.00 |

---

## 2. Top Account Activity & Coverage (562 Days)

Top 20 accounts by trade volume across the full historical dataset:

| Account Name | Total Trades | Symbols Traded | Win Rate | Total Realized PnL ($) | Active Window |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ES-IPS_TM_5** | 34,896 | 1 | 15.57% | $-3,968,550.00 | 2024-05-23 → 2025-10-14 |
| **ES-TM_8** | 32,728 | 1 | 16.63% | $-2,871,787.50 | 2024-05-23 → 2025-10-29 |
| **ES-TM_5** | 32,170 | 1 | 15.65% | $-2,921,175.00 | 2024-05-24 → 2025-10-22 |
| **IPS_TM_8** | 26,650 | 7 | 49.08% | $-733,499.78 | 2024-03-04 → 2025-10-20 |
| **IPS_TM_5** | 20,448 | 7 | 48.20% | $-1,230,960.71 | 2024-03-03 → 2025-03-10 |
| **TM_7** | 19,502 | 7 | 62.67% | $-216,970.75 | 2024-03-13 → 2025-10-14 |
| **ES-IPS_TM_8** | 18,761 | 1 | 31.81% | $-493,075.00 | 2024-05-23 → 2025-10-27 |
| **TM_2** | 16,913 | 7 | 65.88% | $-507,340.12 | 2024-03-08 → 2025-09-22 |
| **ES-TM_7** | 16,151 | 1 | 66.16% | $900.00 | 2024-05-23 → 2025-10-31 |
| **TM_5** | 15,842 | 7 | 58.00% | $865,183.57 | 2024-03-08 → 2025-06-30 |
| **PB_3** | 15,649 | 7 | 46.96% | $-458,200.75 | 2024-05-03 → 2025-09-08 |
| **TM_8** | 15,408 | 7 | 59.36% | $630,456.24 | 2024-03-10 → 2025-06-30 |
| **IPS_TM_10** | 15,296 | 7 | 65.31% | $-181,702.93 | 2024-03-05 → 2025-09-08 |
| **IPS_TM_5DUPLI** | 15,198 | 7 | 64.40% | $-323,676.18 | 2024-03-03 → 2025-10-06 |
| **TM_10** | 14,666 | 7 | 59.93% | $-702,515.01 | 2024-03-18 → 2025-10-30 |
| **TS_5** | 14,410 | 7 | 57.60% | $-488,894.46 | 2024-05-08 → 2025-10-30 |
| **ES_PB_2** | 14,015 | 1 | 47.20% | $-132,812.50 | 2024-05-26 → 2025-10-14 |
| **ES-TS_6** | 13,859 | 1 | 79.93% | $42,062.50 | 2024-05-23 → 2025-09-07 |
| **ES-TS_5** | 13,674 | 1 | 64.12% | $-38,025.00 | 2024-05-23 → 2025-09-22 |
| **TS_6** | 13,547 | 7 | 71.68% | $-387,786.58 | 2024-05-08 → 2025-10-07 |

---

## 3. Ghost-Fill & Session Boundary Audit Summary

- **Total Historical Trades Inspected:** 733,847
- **Identified Legacy Ghost-Fill Leaks (03:00 / 04:00 / 09:00 NY):** **40,175 trades (5.47%)**
- **Session Boundary Enforcement:** 17:00 NY daily close reset logic correctly flattens overnight position carryover.
- **Rule Soundness (`_is_ghost_fill`):** 100% compliant with strategy tag absence (`AT_`), EOD window exception (16:55-17:05 NY), and multi-lot fill filters.

---

## 4. Recommendation Pipeline A/B Comparison (562 Days)

Evaluating **5,472 total candidate slots** (114 accounts x 48 time bins):

| Pipeline Stage | OLD Pipeline (Raw $p < 0.05$) | NEW Pipeline (BH-FDR + WFA Gate) |
| :--- | :--- | :--- |
| **Recommended Slots** | **98** | **0 validated** |
| **Pending WFA Validation** | N/A | **35 candidates** |
| **Filtered False Positives (BH-FDR)** | 0 | **730 false positives dropped** |
| **High Win-Rate Trap Leakage** | Unchecked | **0 risk-flagged accounts leaked** |

### Key Audit Conclusions

1. **False Positive Removal:** Testing 48 time-slots per account without multiple-comparison correction creates ~2.4 false-positive significant slots per account by chance alone. Benjamini-Hochberg FDR correction eliminated 730 false positives.
2. **Out-of-Sample Protection:** 35 slots passed BH-FDR testing and are queued in `pending_validation` status until Walk-Forward out-of-sample Sharpe confirmation.
3. **Risk Flag Safety:** 126 account/symbol combinations exhibiting high win rates (>55%) but negative payoff ratios (<1.0) were strictly blocked from active recommendations.
