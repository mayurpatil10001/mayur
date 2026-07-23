"""
Performance metrics calculator for trading analysis.

This service calculates comprehensive trading performance metrics including:
- Sharpe ratio, max drawdown, win rate, volatility
- Profit factor and other trading-specific metrics
- Risk-adjusted returns and statistical measures

Requirements: 3.1, 3.4
"""

import math
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from ..models.trading import ProcessedTrade, PerformanceMetrics
from ..utils.validators import ValidationError


@dataclass
class DrawdownPeriod:
    """Represents a drawdown period with start, end, and magnitude."""
    start_date: datetime
    end_date: datetime
    peak_value: float
    trough_value: float
    drawdown_amount: float
    drawdown_percent: float
    duration_days: int


@dataclass
class RiskMetrics:
    """Risk-related performance metrics."""
    value_at_risk_95: float
    value_at_risk_99: float
    expected_shortfall_95: float
    expected_shortfall_99: float
    downside_deviation: float
    sortino_ratio: float          # Annualized Sortino (target: high Sortino = good)
    calmar_ratio: float
    trades_per_week: float        # Trade frequency for real-time model evaluation
    pnl_std_dev: float            # Overall PnL volatility (target: low = good)


class PerformanceMetricsCalculatorError(Exception):
    """Exception raised by performance metrics calculator."""
    pass


class PerformanceMetricsCalculator:
    """
    Calculates comprehensive trading performance metrics from processed trades.
    
    This calculator provides all standard trading metrics including risk-adjusted
    returns, drawdown analysis, and statistical measures required for trading
    optimization decisions.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize the performance calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe ratio calculation (default 2%)
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_performance_metrics(
        self,
        trades: List[ProcessedTrade],
        account_name: str,
        symbol: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics for a set of trades.
        
        Args:
            trades: List of processed trades to analyze
            account_name: Account name for the metrics
            symbol: Symbol for the metrics
            period_start: Start of analysis period (defaults to first trade)
            period_end: End of analysis period (defaults to last trade)
            
        Returns:
            PerformanceMetrics object with all calculated metrics
            
        Raises:
            PerformanceMetricsCalculatorError: If calculation fails
        """
        if not trades:
            raise PerformanceMetricsCalculatorError("Cannot calculate metrics for empty trade list")
        
        try:
            # Sort trades by entry time
            sorted_trades = sorted(trades, key=lambda t: t.entry_time)
            
            # Determine analysis period
            if period_start is None:
                period_start = sorted_trades[0].entry_time
            if period_end is None:
                period_end = sorted_trades[-1].exit_time
            
            # Filter trades within period
            period_trades = [
                t for t in sorted_trades 
                if period_start <= t.entry_time <= period_end
            ]
            
            if not period_trades:
                raise PerformanceMetricsCalculatorError("No trades found in specified period")
            
            # Calculate basic metrics
            total_trades = len(period_trades)
            winning_trades = sum(1 for t in period_trades if t.profit_loss > 0)
            losing_trades = total_trades - winning_trades
            
            # Calculate returns and P&L
            total_return = sum(t.profit_loss for t in period_trades)
            wins = [t.profit_loss for t in period_trades if t.profit_loss > 0]
            losses = [t.profit_loss for t in period_trades if t.profit_loss <= 0]
            
            # Basic statistics
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            average_win = sum(wins) / len(wins) if wins else 0.0
            average_loss = sum(losses) / len(losses) if losses else 0.0
            largest_win = max(wins) if wins else 0.0
            largest_loss = min(losses) if losses else 0.0
            
            # Profit factor
            gross_profit = sum(wins) if wins else 0.0
            gross_loss = abs(sum(losses)) if losses else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
            
            # Calculate volatility and Sharpe ratio
            returns = [t.profit_loss for t in period_trades]
            volatility = self._calculate_volatility(returns)
            sharpe_ratio = self._calculate_sharpe_ratio(returns, volatility)

            # Calculate maximum drawdown
            max_drawdown = self._calculate_max_drawdown(period_trades)

            # --- Win/loss magnitude metrics ---
            # win_loss_ratio: average win divided by the absolute value of average loss.
            # A value < 1 means losses are on average larger than wins.
            if wins and losses:
                win_loss_ratio: Optional[float] = average_win / abs(average_loss)
            else:
                win_loss_ratio = None  # Cannot compute when one side is empty

            # payoff_adjusted_expectancy: the true per-trade expected value when
            # both win probability AND magnitude are accounted for.
            # Formula: E[P&L] = win_rate * E[win] + (1 - win_rate) * E[loss]
            # (average_loss is already negative, so no sign change needed)
            if wins and losses:
                payoff_adjusted_expectancy: Optional[float] = (
                    win_rate * average_win + (1.0 - win_rate) * average_loss
                )
            elif wins:
                payoff_adjusted_expectancy = average_win  # 100% win rate
            else:
                payoff_adjusted_expectancy = average_loss  # 0% win rate

            # risk_flag: True when win_rate is high (>55%) but losses dominate
            # in magnitude (win_loss_ratio < 1.0). This flags the "high win-rate
            # trap" where frequent small wins mask occasional large losses.
            risk_flag: bool = (
                win_rate > 0.55
                and win_loss_ratio is not None
                and win_loss_ratio < 1.0
            )

            return PerformanceMetrics(
                account_name=account_name,
                symbol=symbol,
                period_start=period_start,
                period_end=period_end,
                total_return=total_return,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                average_win=average_win,
                average_loss=average_loss,
                profit_factor=profit_factor,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                volatility=volatility,
                largest_win=largest_win,
                largest_loss=largest_loss,
                win_loss_ratio=win_loss_ratio,
                payoff_adjusted_expectancy=payoff_adjusted_expectancy,
                risk_flag=risk_flag,
            )
            
        except Exception as e:
            raise PerformanceMetricsCalculatorError(f"Failed to calculate performance metrics: {e}")
    
    def calculate_risk_metrics(self, trades: List[ProcessedTrade]) -> RiskMetrics:
        """
        Calculate advanced risk metrics for a set of trades.

        Sortino ratio is annualized so high-frequency, consistent accounts
        score higher than low-frequency ones with the same per-trade mean.
        Formula: (mean_pnl / downside_dev) * sqrt(trades_per_year)

        Args:
            trades: List of processed trades to analyze

        Returns:
            RiskMetrics object with risk-related calculations
        """
        if not trades:
            raise PerformanceMetricsCalculatorError("Cannot calculate risk metrics for empty trade list")

        returns = [t.profit_loss for t in trades]
        negative_returns = [r for r in returns if r < 0]

        # Value at Risk calculations
        var_95 = self._calculate_var(returns, 0.95)
        var_99 = self._calculate_var(returns, 0.99)

        # Expected Shortfall (Conditional VaR)
        es_95 = self._calculate_expected_shortfall(returns, 0.95)
        es_99 = self._calculate_expected_shortfall(returns, 0.99)

        # Downside deviation (volatility of negative returns only)
        downside_deviation = float(np.std(negative_returns)) if negative_returns else 0.0

        # --- Annualized Sortino (core target metric) ---
        # Determine span of trades to compute trades-per-year annualization factor
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        span_days = max((sorted_trades[-1].exit_time - sorted_trades[0].entry_time).days, 1)
        total_trades = len(trades)
        trades_per_year = (total_trades / span_days) * 252  # 252 trading days
        trades_per_week = (total_trades / span_days) * 5    # 5 trading days per week
        annualization_factor = float(np.sqrt(max(trades_per_year, 1)))

        mean_return = float(np.mean(returns))
        # Annualized Sortino: per-trade Sortino scaled to annual frequency
        per_trade_sortino = mean_return / downside_deviation if downside_deviation > 0 else 0.0
        sortino_ratio = per_trade_sortino * annualization_factor

        # PnL standard deviation (low = good for our target)
        pnl_std_dev = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0

        # Calmar ratio (return / max drawdown)
        max_drawdown = abs(self._calculate_max_drawdown(trades))
        calmar_ratio = mean_return / max_drawdown if max_drawdown > 0 else 0.0

        return RiskMetrics(
            value_at_risk_95=var_95,
            value_at_risk_99=var_99,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            downside_deviation=downside_deviation,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            trades_per_week=round(trades_per_week, 2),
            pnl_std_dev=pnl_std_dev,
        )
    
    def calculate_drawdown_periods(self, trades: List[ProcessedTrade]) -> List[DrawdownPeriod]:
        """
        Calculate all drawdown periods from a series of trades.
        
        Args:
            trades: List of processed trades sorted by time
            
        Returns:
            List of DrawdownPeriod objects representing all drawdown periods
        """
        if not trades:
            return []
        
        # Sort trades by exit time to get chronological P&L
        sorted_trades = sorted(trades, key=lambda t: t.exit_time)
        
        # Calculate cumulative P&L
        cumulative_pnl = []
        running_total = 0.0
        
        for trade in sorted_trades:
            running_total += trade.profit_loss
            cumulative_pnl.append((trade.exit_time, running_total))
        
        # Find drawdown periods
        drawdown_periods = []
        peak_value = cumulative_pnl[0][1]
        peak_date = cumulative_pnl[0][0]
        in_drawdown = False
        
        for date, value in cumulative_pnl[1:]:
            if value > peak_value:
                # New peak - end any current drawdown
                if in_drawdown:
                    # Find the trough (minimum value during drawdown)
                    trough_idx = None
                    trough_value = peak_value
                    
                    for i, (dd_date, dd_value) in enumerate(cumulative_pnl):
                        if dd_date >= peak_date and dd_date <= date:
                            if dd_value < trough_value:
                                trough_value = dd_value
                                trough_idx = i
                    
                    if trough_idx is not None:
                        trough_date = cumulative_pnl[trough_idx][0]
                        drawdown_amount = peak_value - trough_value
                        drawdown_percent = (drawdown_amount / peak_value * 100) if peak_value != 0 else 0.0
                        duration_days = (date - peak_date).days
                        
                        drawdown_periods.append(DrawdownPeriod(
                            start_date=peak_date,
                            end_date=date,
                            peak_value=peak_value,
                            trough_value=trough_value,
                            drawdown_amount=drawdown_amount,
                            drawdown_percent=drawdown_percent,
                            duration_days=duration_days
                        ))
                
                # Update peak
                peak_value = value
                peak_date = date
                in_drawdown = False
            else:
                # Value below peak - we're in drawdown
                in_drawdown = True
        
        return drawdown_periods
    
    def calculate_monthly_returns(self, trades: List[ProcessedTrade]) -> Dict[str, float]:
        """
        Calculate monthly returns from trades.
        
        Args:
            trades: List of processed trades
            
        Returns:
            Dictionary mapping month strings (YYYY-MM) to monthly returns
        """
        if not trades:
            return {}
        
        monthly_returns = {}
        
        for trade in trades:
            month_key = trade.exit_time.strftime('%Y-%m')
            if month_key not in monthly_returns:
                monthly_returns[month_key] = 0.0
            monthly_returns[month_key] += trade.profit_loss
        
        return monthly_returns
    
    def calculate_rolling_metrics(
        self,
        trades: List[ProcessedTrade],
        window_days: int = 30
    ) -> List[Tuple[datetime, float, float, float]]:
        """
        Calculate rolling performance metrics over a specified window.
        
        Args:
            trades: List of processed trades sorted by time
            window_days: Rolling window size in days
            
        Returns:
            List of tuples (date, rolling_return, rolling_sharpe, rolling_drawdown)
        """
        if not trades or window_days <= 0:
            return []
        
        sorted_trades = sorted(trades, key=lambda t: t.exit_time)
        rolling_metrics = []
        
        for i, trade in enumerate(sorted_trades):
            # Get trades within the rolling window
            window_start = trade.exit_time - timedelta(days=window_days)
            window_trades = [
                t for t in sorted_trades[:i+1]
                if t.exit_time >= window_start
            ]
            
            if len(window_trades) < 2:  # Need at least 2 trades for meaningful metrics
                continue
            
            # Calculate rolling metrics
            returns = [t.profit_loss for t in window_trades]
            rolling_return = sum(returns)
            rolling_volatility = self._calculate_volatility(returns)
            rolling_sharpe = self._calculate_sharpe_ratio(returns, rolling_volatility)
            rolling_drawdown = self._calculate_max_drawdown(window_trades)
            
            rolling_metrics.append((
                trade.exit_time,
                rolling_return,
                rolling_sharpe,
                rolling_drawdown
            ))
        
        return rolling_metrics
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate volatility (standard deviation) of returns."""
        if len(returns) < 2:
            return 0.0
        
        return float(np.std(returns, ddof=1))  # Use sample standard deviation
    
    def _calculate_sharpe_ratio(self, returns: List[float], volatility: float) -> Optional[float]:
        """Calculate Sharpe ratio."""
        if not returns or volatility == 0:
            return None
        
        mean_return = np.mean(returns)
        # Convert annual risk-free rate to per-trade rate (approximate)
        risk_free_per_trade = self.risk_free_rate / 252  # Assuming 252 trading days per year
        
        excess_return = mean_return - risk_free_per_trade
        return float(excess_return / volatility)
    
    def _calculate_max_drawdown(self, trades: List[ProcessedTrade]) -> float:
        """Calculate maximum drawdown from trades."""
        if not trades:
            return 0.0
        
        # Sort trades by exit time
        sorted_trades = sorted(trades, key=lambda t: t.exit_time)
        
        # Calculate cumulative P&L
        cumulative_pnl = 0.0
        peak = 0.0
        max_drawdown = 0.0
        
        for trade in sorted_trades:
            cumulative_pnl += trade.profit_loss
            
            # Update peak if we have a new high
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            
            # Calculate current drawdown
            current_drawdown = peak - cumulative_pnl
            
            # Update max drawdown if current is worse
            if current_drawdown > max_drawdown:
                max_drawdown = current_drawdown
        
        return -max_drawdown  # Return as negative value (conventional)
    
    def _calculate_var(self, returns: List[float], confidence_level: float) -> float:
        """Calculate Value at Risk at specified confidence level."""
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int((1 - confidence_level) * len(sorted_returns))
        
        if index >= len(sorted_returns):
            index = len(sorted_returns) - 1
        
        return sorted_returns[index]
    
    def _calculate_expected_shortfall(self, returns: List[float], confidence_level: float) -> float:
        """Calculate Expected Shortfall (Conditional VaR) at specified confidence level."""
        if not returns:
            return 0.0
        
        var = self._calculate_var(returns, confidence_level)
        tail_returns = [r for r in returns if r <= var]
        
        return np.mean(tail_returns) if tail_returns else 0.0
    
    def validate_trades_for_calculation(self, trades: List[ProcessedTrade]) -> bool:
        """
        Validate that trades are suitable for performance calculation.
        
        Args:
            trades: List of trades to validate
            
        Returns:
            True if trades are valid for calculation
            
        Raises:
            PerformanceMetricsCalculatorError: If validation fails
        """
        if not trades:
            raise PerformanceMetricsCalculatorError("Trade list cannot be empty")
        
        # Check for required fields
        for i, trade in enumerate(trades):
            if not hasattr(trade, 'profit_loss') or trade.profit_loss is None:
                raise PerformanceMetricsCalculatorError(f"Trade {i} missing profit_loss")
            
            if not hasattr(trade, 'entry_time') or trade.entry_time is None:
                raise PerformanceMetricsCalculatorError(f"Trade {i} missing entry_time")
            
            if not hasattr(trade, 'exit_time') or trade.exit_time is None:
                raise PerformanceMetricsCalculatorError(f"Trade {i} missing exit_time")
            
            # Validate time order
            if trade.exit_time <= trade.entry_time:
                raise PerformanceMetricsCalculatorError(f"Trade {i} has invalid time order")
        
        # Check for chronological order
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        if sorted_trades != trades:
            # This is just a warning, not an error
            pass
        
        return True