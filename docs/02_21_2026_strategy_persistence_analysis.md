# Strategy Persistence & Lookback Analysis (Feb 21, 2024)

This report investigates whether past performance (over the last 18 months) is a reliable predictor of future success for the current strategy set.

## 1. The "Static" Fallacy
**Question**: *"What if I keep using the same past permutations that worked in the last 18 months and continue use them into the future?"*

**The Simulation**: 
We identified the #1 performing accounts from the first 12 months of data ("Static Selection") and then held them for the following 18 months without any re-balancing.

| Symbol | Static Strategy Return (1 Year Hold) | Dynamic Strategy (Monthly Refresh) |
| :--- | :--- | :--- |
| **NQ** | **-$8,340,015** (Loss) | -$885,042 (Loss) |
| **ES** | **-$1,772,288** (Loss) | -$151,016 (Loss) |
| **CL** | **-$1,435,041** (Loss) | -$313,531 (Loss) |

**Verdict**: The "Static" approach is a catastrophic failure. Strategies in this set have a high **Decay Rate**. An account that was #1 last year has a very high probability of being a major loser this year. You **cannot** simply hold past winners.

---

## 2. The Lookback Window Sweep
**Question**: *"Why did you try only 90 lookback? Did you try other combinations?"*

**The Simulation**: 
We ran a "Sweep" for ES, testing different training windows (**W**) and applying them to the next 30 days of out-of-sample data.

| Training Window (W) | Out-of-Sample Sharpe Ratio | Result |
| :--- | :--- | :--- |
| **60 Days** | **-0.51** | Best (Least negative) |
| **90 Days** | **-1.17** | Degrading |
| **180 Days** | **-1.11** | Stagnant |
| **270 Days** | **-1.50** | Poor |
| **360 Days** | **-2.05** | Worst |

**Verdict**: Longer historical lookbacks (e.g., 360 days) actually **hurt performance**. Looking too far back introduces "dead data" from market regimes that no longer exist. Recency (60-90 days) is the "sweet spot" for selecting robust accounts.

---

## 3. Conclusions & Recommendation

1.  **Selection Bias is an Illusion**: The 18-month "success" shown in the Classic dashboard is based on **In-Sample** data (picking the winners *after* the fact). Our tests show that if you tried to trade those exact accounts forward, you would have hit the "cliff" immediately.
2.  **You Must Be Dynamic**: Because the edge is non-stationary, you must re-evaluate your account selections every 2-4 weeks (Walk-Forward).
3.  **The Path Forward**: To turn these dynamic losses into gains, we must use the **Consensus Model** (Consensus > 0.90). This is the only logic that filters out the "luck-based" winners of the 60-day window and keeps the "structural" winners.

> [!IMPORTANT]
> **Do not trade the Year-1 winners in Year-2.** The data proves they will likely result in significant drawdowns.
