# UI Status Indicators (Account Health)

The Recommendation Matrix uses small colored dots (status indicators) next to account names to represent the current "Health Score" of that strategy based on its performance over the **last 30 days**.

## Indicator Meanings

| Indicator | Status | Description |
| :--- | :--- | :--- |
| 🟢 Green | **STABLE** | The account is performing as expected. Its 30-day average profit is >= 90% of its historical baseline. |
| 🟠 Orange | **DRIFTING** | The account is still profitable but its 30-day average profit has dropped below 90% of its historical baseline. Monitor for further drift. |
| 🔴 Red | **CRITICAL** | The account has an average P&L < 0 over the last 30 days. This indicates a significant performance breakdown. |
| 🔵 Blue | **NEW / NO DATA** | No trade data found for this account in the last 30 days. These accounts are usually physically excluded from the matrix. |

## Freshness Gate

The matrix automatically enforces a **Double-Layered 30-day Freshness Gate**. 
1. **Database Layer**: Accounts without any trades in the last 30 days for the selected symbol are excluded via SQL CTE filters in the matrix generation query.
2. **Application Layer**: A hard fail-safe identifies stale accounts (including `TM_5`, `TM_8`) in the Python logic and removes them from the data structure before it is served to the frontend.

This ensures you are only viewing strategies that are currently active and being traded in the live environment.

## Visual Blur / Grayscale

When using the **Best Bins** filter, accounts that do not meet the risk/reward threshold for your selected account size will be dimmed.
- High-performing bins remain in full color.
- Filtered bins are rendered in **35% opacity grayscale** to clean up the view and focus your attention on the highest-expectancy setups.
