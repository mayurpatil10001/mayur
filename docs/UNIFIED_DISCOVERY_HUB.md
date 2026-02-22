# Unified Discovery Hub

The Unified Discovery Hub (located in the **Discovery Explorer** page) is a one-stop "Edge Factory" that consolidates all trading research workflows. It integrates multiple ranking logics and view modes to streamline the identification and validation of trading edges.

## Key Features

### 1. Multi-Logic Ranking
You can now switch between different methodologies for identifying top-performing edges:
- **Persistence (Default):** Ranks accounts based on monthly P&L consistency (win rate of months). Ideal for long-term stable edges.
- **Classic:** Ranks by average profit per trade and total PnL. Ideal for identifying "heavy hitters."
- **Statistical:** Ranks by Expected Value (EV = Avg Trade * Win Rate). Focuses on statistical edge quality.
- **Ensemble:** Uses a multi-window weighted approach to find edges that perform consistently across different lookbacks (30d, 90d, All-Time).

### 2. Flexible View Modes
- **List View:** A detailed table of all identified edges with metrics like Persistence Bar, Total PnL, Total Trades, and Average Profit.
- **Matrix View:** A high-density grid showing time slots vs. days of the week. This allows you to visually identify geographic or temporal clusters of edges.

### 3. Integrated Research Workflow
- **Multi-Selection:** Select multiple edges from either the List or Matrix view. Selections are synchronized between views.
- **Portfolio Backtest:** Click "Backtest Selection" to instantly simulate the combined performance of your selected edges. View equity curves and portfolio metrics (Sharpe, Sortino, PF).
- **Walk-Forward Validation:** Run rolling window simulations directly on your discovery results to verify if the identified edges hold up "out-of-sample."

## How to Use

1. **Discover:** Select your preferred **Ranking Logic** and **Symbol** at the top of the Explorer.
2. **Explore:** Toggle to **Matrix View** to find clusters of profitability.
3. **Select:** Click cells in the Matrix or checkboxes in the List to build your "All-Star Team."
4. **Validate:** Use the right-hand panel to run a **Static Backtest** or a **Walk-Forward Analysis** on your selection.
5. **Analyze:** Review the metrics grid and Equity Curve to confirm the edge's robustness before deployment.
