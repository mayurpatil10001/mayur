# Verification vs Processed Trades Comparison
## Ghost-Orphan-Sequence Fix Impact Analysis (562 Trading Days)

This report compares the **OLD `processed_trades`** (no ghost-orphan purge) against
the **NEW `verification_trades`** (ghost-exit -> orphaned-entry purge ACTIVE).

---

## 1. High-Level Quality & Financial Metrics

| Metric | OLD `processed_trades` | NEW `verification_trades` (Fixed) | Delta |
| :--- | :--- | :--- | :--- |
| **Total Trades** | 733,847 | 126,991 | -606,856 |
| **Total Realized PnL ($)** | $-19,755,589.92 | $-6,030,920.04 | **$+13,724,669.88** |
| **Win Rate (%)** | 51.72% | 48.58% | **-3.14%** |
| **Avg PnL / Trade ($)** | $-26.92 | $-47.49 | **$-20.57** |
| **Profit Factor** | 0.84 | 0.94 | **+0.11** |
| **Inverted Trades (Exit < Entry)** | 0 | **220** | **+220** |
| **Negative Duration Trades** | 0 | **220** | **+220** |
| **Distinct Accounts** | 114 | 116 | +2 |

---

## 2. Yearly Trade Volume Comparison

| Year | OLD Trades | OLD Total PnL ($) | NEW Trades | NEW Total PnL ($) | Trade Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2023** | 1,731 | $-36,110.00 | 1,047 | $-27,520.00 | -684 |
| **2024** | 551,476 | $-13,986,987.42 | 87,529 | $-4,738,791.54 | -463,947 |
| **2025** | 180,640 | $-5,732,492.50 | 38,415 | $-1,264,608.50 | -142,225 |

---

## 3. Top Account Trade Count Comparison

| Account Name | OLD Trades | OLD PnL ($) | NEW Trades | NEW PnL ($) | Trade Delta |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ES-IPS_TM_5** | 34,896 | $-3,968,550.00 | 3,896 | $-112,937.50 | -31,000 |
| **ES-TM_8** | 32,728 | $-2,871,787.50 | 4,509 | $-322,350.00 | -28,219 |
| **ES-TM_5** | 32,170 | $-2,921,175.00 | 4,465 | $212,462.50 | -27,705 |
| **IPS_TM_8** | 26,650 | $-733,499.78 | 2,720 | $-996,270.61 | -23,930 |
| **IPS_TM_5** | 20,448 | $-1,230,960.71 | 1,914 | $-268,533.11 | -18,534 |
| **TM_7** | 19,502 | $-216,970.75 | 0 | $0.00 | -19,502 |
| **ES-IPS_TM_8** | 18,761 | $-493,075.00 | 2,720 | $-2,131,975.00 | -16,041 |
| **TM_2** | 16,913 | $-507,340.12 | 2,443 | $-32,391.26 | -14,470 |
| **ES-TM_7** | 16,151 | $900.00 | 0 | $0.00 | -16,151 |
| **TM_5** | 15,842 | $865,183.57 | 1,782 | $287,251.00 | -14,060 |
| **PB_3** | 15,649 | $-458,200.75 | 2,387 | $-306,728.94 | -13,262 |
| **TM_8** | 15,408 | $630,456.24 | 0 | $0.00 | -15,408 |
| **IPS_TM_10** | 15,296 | $-181,702.93 | 1,881 | $-299,315.35 | -13,415 |
| **IPS_TM_5DUPLI** | 15,198 | $-323,676.18 | 1,897 | $-425,159.22 | -13,301 |
| **TM_10** | 14,666 | $-702,515.01 | 2,007 | $-396,994.24 | -12,659 |
| **TS_5** | 14,410 | $-488,894.46 | 0 | $0.00 | -14,410 |
| **ES_PB_2** | 14,015 | $-132,812.50 | 1,862 | $-900,787.50 | -12,153 |
| **ES-TS_6** | 13,859 | $42,062.50 | 0 | $0.00 | -13,859 |
| **ES-TS_5** | 13,674 | $-38,025.00 | 0 | $0.00 | -13,674 |
| **TS_6** | 13,547 | $-387,786.58 | 0 | $0.00 | -13,547 |

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

- **Total Trade Count Change:** -606,856 trades
- **Total PnL Impact:** $+13,724,669.88
- **Data Quality (Inverted/Negative Duration Trades):** 220 inverted | 220 negative-duration
