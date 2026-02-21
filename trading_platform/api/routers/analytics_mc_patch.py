
@router.get("/monte-carlo/{account_name}")
async def run_monte_carlo(
    account_name: str,
    simulations: int = Query(10000, ge=100, le=50000),
    time_horizon_days: int = Query(30, ge=1, le=365),
    confidence_level: float = Query(0.95, ge=0.5, le=0.999),
):
    """
    Run a Monte Carlo simulation for the specified account or symbol.
    If 'account_name' is a symbol (e.g., NQ, ES), it aggregates the 'best per slot' trades (Matrix logic).
    Otherwise, it treats it as a specific account name.
    """
    import numpy as np
    import sqlite3
    from pathlib import Path
    from datetime import datetime
    from collections import defaultdict

    try:
        db_path = Path("trading_platform.db")
        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database not found")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if input is a known Symbol
        cursor.execute("SELECT count(*) FROM processed_trades WHERE symbol = ?", (account_name,))
        symbol_count = cursor.fetchone()[0]

        trades = []
        is_symbol = False

        if symbol_count > 0:
            is_symbol = True
            # Fetch all trades for symbol, preserving time/day info
            cursor.execute('''
                SELECT 
                    account_name, 
                    profit_loss, 
                    entry_time,
                    printf('%02d:%02d', 
                        CAST(strftime('%H', entry_time) AS INTEGER), 
                        CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                    ) as time_slot,
                    CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
                FROM processed_trades 
                WHERE symbol = ? 
                ORDER BY entry_time ASC
            ''', (account_name,))
            rows = cursor.fetchall()

            # Determine Best Account per Slot (Classic Logic: best Average Trade)
            slot_stats = defaultdict(lambda: defaultdict(list))
            for r in rows:
                key = (r['time_slot'], r['day_of_week'])
                slot_stats[key][r['account_name']].append(r['profit_loss'])

            best_accounts = {}
            for key, accounts in slot_stats.items():
                best_acct = None
                best_avg = -float('inf')
                for acct, pnls in accounts.items():
                    if len(pnls) < 1: continue
                    avg = sum(pnls) / len(pnls)
                    if avg > best_avg:
                        best_avg = avg
                        best_acct = acct
                best_accounts[key] = best_acct

            # Filter trades to only include those from the best account for that slot
            trades = [float(r['profit_loss']) for r in rows if best_accounts.get((r['time_slot'], r['day_of_week'])) == r['account_name']]
            
            # Determine date range from the rows we just fetched
            if rows:
                # rows is list of Row objects, need to parse entry_time
                start_dt = datetime.fromisoformat(rows[0]['entry_time'])
                end_dt = datetime.fromisoformat(rows[-1]['entry_time'])
                days_history = (end_dt - start_dt).days or 1
            else:
                days_history = 1

        else:
            # Treat as specific Account Name
            cursor.execute("SELECT profit_loss, entry_time FROM processed_trades WHERE account_name = ? ORDER BY entry_time ASC", (account_name,))
            rows = cursor.fetchall()
            trades = [float(r['profit_loss']) for r in rows]
            
            if rows:
                start_dt = datetime.fromisoformat(rows[0]['entry_time'])
                end_dt = datetime.fromisoformat(rows[-1]['entry_time'])
                days_history = (end_dt - start_dt).days or 1
            else:
                days_history = 1

        conn.close()

        if not trades:
            # Fallback for empty or unknown
            return APIResponse(status="error", message=f"No trades found for {account_name}", data=None)

        # Calculate trades per day frequency
        trades_per_day = len(trades) / max(1, days_history)
        trades_horizon = int(trades_per_day * time_horizon_days)
        if trades_horizon < 10: trades_horizon = 10 # Minimum floor

        # Monte Carlo Simulation (Vectorized)
        pnl_array = np.array(trades)
        
        # Generate random indices: (simulations, trades_horizon)
        # We sample WITH replacement
        rng = np.random.default_rng()
        random_indices = rng.integers(0, len(pnl_array), size=(simulations, trades_horizon))
        
        # Lookup PnLs
        simulated_pnls = pnl_array[random_indices]
        
        # Sum across horizon
        simulated_totals = np.sum(simulated_pnls, axis=1)
        
        # Metrics
        mean_return = float(np.mean(simulated_totals))
        std_dev = float(np.std(simulated_totals))
        
        # Percentiles
        percentiles_to_calc = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_values = np.percentile(simulated_totals, percentiles_to_calc)
        percentiles_dict = {str(p): float(v) for p, v in zip(percentiles_to_calc, percentile_values)}
        
        # VaR (Value at Risk) - Loss at confidence level
        # If confidence is 0.95, we look at 5th percentile
        var_percentile = (1 - confidence_level) * 100
        var_value = float(np.percentile(simulated_totals, var_percentile))
        
        # Probability of Loss
        prob_loss = float(np.mean(simulated_totals < 0)) * 100

        result = {
            "account_name": account_name,
            "num_simulations": simulations,
            "time_horizon_days": time_horizon_days,
            "expected_return": mean_return,
            "expected_volatility": std_dev,
            "probability_of_loss": prob_loss,
            "var_estimates": {
                f"{int(confidence_level*100)}%": var_value
            },
            "percentiles": percentiles_dict,
            "sample_paths": np.column_stack((np.zeros(min(100, simulations)), np.cumsum(simulated_pnls[:100], axis=1))).tolist()
        }

        return APIResponse(
            status="success",
            message="Monte Carlo simulation completed",
            data=result
        )

    except Exception as e:
        logger.error(f"Monte Carlo error: {e}")
        return APIResponse(status="error", message=str(e), data=None)
