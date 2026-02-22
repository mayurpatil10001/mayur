# Proven Edges Analysis Report (Feb 21, 2024)

This report identifies the specific **(Account + Time Slot)** combinations that demonstrate the highest level of monthly consistency in the database. 

## 1. What is the difference in Logic?

| Metric | Current "Classic" Logic | Proposed "Persistence" Logic |
| :--- | :--- | :--- |
| **Observation** | Snapshot of a 90-day window. | Tracking **every month** since inception. |
| **Criterion** | "Who made the most money lately?" | "Who wins most consistently at this hour?" |
| **Sample Size** | Global account trades > 100. | **Local slot trades > 200** total. |
| **Success Check** | Avg Profit > $12. | **Profitable in > 70% of months** traded locally. |

**Why this matters**: Persistence filters out "lucky months." It ensures that a permutation like **V_sim16** isn't just winning because of a fluke spike, but because its edge in that specific 30-min bin is structurally sound.

---

## 2. Top "Proven" High-Persistence Edges

These are the permutations that meet the strict criteria: **Total Trades > 200** per slot and **>70% Monthly Consistency**.

### NQ (Nasdaq)
| Account | Time Slot | Total PnL | Persistence (Months Profitable) |
| :--- | :--- | :--- | :--- |
| **V_sim16** | **02:00** | $34,170 | **88%** |
| **V_sim16** | **16:00** | $61,349 | **73%** |
| **TM_D-R-1_2** | **19:00** | $22,122 | **75%** |
| **V_sim16** | **13:00** | $23,375 | **73%** |
| **TM_D-R-1_1** | **11:00** | $17,936 | **70%** |

### ES (S&P 500)
| Account | Time Slot | Total PnL | Persistence (Months Profitable) |
| :--- | :--- | :--- | :--- |
| **TM_6** | **09:30** | $57,567 | **73%** |
| **IPS_TM_13** | **11:00** | $21,572 | **77%** |

---

## 3. Recommendation

To achieve the goal of "identifying which permutation to use when," we should default the dashboard to **Persistence Mode**. 

Notice that **V_sim16 at 11:30 (NQ)** is missing from the 70% list in *this* specific query range, but it appeared as 100% in the last 9 months. This highlights why we need the **Persistence Factor** to rank them.

> [!IMPORTANT]
> The **Global Edge** selection logic I am implementing now will prioritize these specific "Proven Winners" first. If no account meets the high-persistence threshold for a slot, that slot remains "Unrecommended" (Safe mode).
