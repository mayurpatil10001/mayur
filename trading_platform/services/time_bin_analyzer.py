"""
TimeBinAnalyzer core functionality for advanced trading analytics.

This module implements comprehensive time-bin analysis for account/30-minute
time window combinations with statistical significance testing.

Requirements: 1.1, 1.2, 1.3, 5.1
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from scipy import stats
import pandas as pd
from sqlalchemy.orm import Session

from ..models.database import ProcessedTrade as ProcessedTradeORM
from ..database.connection import get_db_session


@dataclass
class SimpleTrade:
    """Simplified trade data for time-bin analysis."""
    trade_id: str
    account_name: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    side: str
    profit_loss: float
    commission: float
    duration_minutes: int
    hour_of_day: int
    day_of_week: int


@dataclass
class TimeBin:
    """Time-bin data model with account/hour/minute_bin structure."""
    
    account_name: str
    hour: int  # 0-23
    minute_bin: int  # 0 or 30 (for 30-minute bins)
    day_of_week: Optional[int] = None  # 0-6, None for all days
    
    def __post_init__(self):
        """Validate time-bin parameters."""
        if not (0 <= self.hour <= 23):
            raise ValueError("Hour must be between 0 and 23")
        
        if self.minute_bin not in [0, 30]:
            raise ValueError("Minute bin must be 0 or 30")
        
        if self.day_of_week is not None and not (0 <= self.day_of_week <= 6):
            raise ValueError("Day of week must be between 0 and 6 or None")
    
    @property
    def time_window_start(self) -> time:
        """Get the start time of this time bin."""
        return time(hour=self.hour, minute=self.minute_bin)
    
    @property
    def time_window_end(self) -> time:
        """Get the end time of this time bin."""
        end_minute = self.minute_bin + 30
        if end_minute >= 60:
            end_hour = (self.hour + 1) % 24
            end_minute = 0
        else:
            end_hour = self.hour
        return time(hour=end_hour, minute=end_minute)
    
    def __str__(self) -> str:
        """String representation of the time bin."""
        day_str = f"_dow{self.day_of_week}" if self.day_of_week is not None else ""
        return f"{self.account_name}_{self.hour:02d}:{self.minute_bin:02d}{day_str}"
    
    def matches_trade_time(self, trade_time: datetime) -> bool:
        """Check if a trade time falls within this time bin."""
        trade_time_only = trade_time.time()
        
        # Check day of week if specified
        if self.day_of_week is not None and trade_time.weekday() != self.day_of_week:
            return False
        
        # Check if trade time falls within the 30-minute window
        start_time = self.time_window_start
        end_time = self.time_window_end
        
        # Handle midnight crossing
        if end_time < start_time:  # Crosses midnight
            return trade_time_only >= start_time or trade_time_only < end_time
        else:
            return start_time <= trade_time_only < end_time


@dataclass
class TimeBinMetrics:
    """Performance metrics for a specific time bin."""
    
    time_bin: TimeBin
    total_trades: int
    win_rate: float
    average_pnl: float
    total_pnl: float
    sharpe_ratio: Optional[float]
    calmar_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: float
    profit_factor: float
    
    # Statistical significance metrics
    confidence_interval_95: Optional[Tuple[float, float]]
    p_value_vs_random: Optional[float]
    statistical_significance: bool
    minimum_sample_size_met: bool
    
    # Additional metrics
    volatility: float
    largest_win: float
    largest_loss: float
    winning_trades: int
    losing_trades: int
    average_win: float
    average_loss: float
    
    @property
    def expectancy(self) -> float:
        """Calculate expectancy (expected value per trade)."""
        if self.total_trades == 0:
            return 0.0
        return (self.win_rate * self.average_win) - ((1 - self.win_rate) * abs(self.average_loss))
    
    @property
    def recovery_factor(self) -> float:
        """Calculate recovery factor (total return / max drawdown)."""
        return abs(self.total_pnl / self.max_drawdown) if self.max_drawdown != 0 else 0.0


@dataclass
class SignificanceTest:
    """Statistical significance test results."""
    
    test_name: str
    p_value: float
    is_significant: bool
    confidence_level: float
    test_statistic: float
    critical_value: float
    interpretation: str


class TimeBinAnalyzer:
    """Core analyzer for time-bin specific trading performance."""
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the analyzer with optional database session."""
        if db_session is None:
            from ..database.database import get_db_context
            self._db_context = get_db_context
            self.db_session = None
        else:
            self.db_session = db_session
            self._db_context = None
        self.minimum_sample_size = 30  # Minimum trades for statistical significance
        self.risk_free_rate = 0.02  # 2% annual risk-free rate for Sharpe calculation
    
    def get_time_bin_trades(self, time_bin: TimeBin) -> List[SimpleTrade]:
        """
        Filter trades by specific time windows.
        
        Requirements: 1.1 - Retrieve trades for specific account/30-minute time bin
        """
        def _process_trades_with_session(session):
            """Process trades with a given session."""
            # Query only the columns that exist in the database
            query = session.query(
                ProcessedTradeORM.id,
                ProcessedTradeORM.trade_id,
                ProcessedTradeORM.account_name,
                ProcessedTradeORM.symbol,
                ProcessedTradeORM.entry_time,
                ProcessedTradeORM.exit_time,
                ProcessedTradeORM.entry_price,
                ProcessedTradeORM.exit_price,
                ProcessedTradeORM.quantity,
                ProcessedTradeORM.side,
                ProcessedTradeORM.profit_loss,
                ProcessedTradeORM.commission,
                ProcessedTradeORM.duration_minutes,
                ProcessedTradeORM.hour_of_day,
                ProcessedTradeORM.day_of_week
            ).filter(
                ProcessedTradeORM.account_name == time_bin.account_name,
                ProcessedTradeORM.hour_of_day == time_bin.hour
            )
            
            # Filter by day of week if specified
            if time_bin.day_of_week is not None:
                query = query.filter(ProcessedTradeORM.day_of_week == time_bin.day_of_week)
            
            # Get all trades and filter by minute bin
            all_trades = query.all()
            
            # Convert to dataclass and filter by exact time window
            filtered_trades = []
            for trade_row in all_trades:
                # Convert row to simple trade dataclass
                trade = SimpleTrade(
                    trade_id=trade_row.trade_id,
                    account_name=trade_row.account_name,
                    symbol=trade_row.symbol,
                    entry_time=trade_row.entry_time,
                    exit_time=trade_row.exit_time,
                    entry_price=trade_row.entry_price,
                    exit_price=trade_row.exit_price,
                    quantity=trade_row.quantity,
                    side=trade_row.side,
                    profit_loss=trade_row.profit_loss,
                    commission=trade_row.commission,
                    duration_minutes=trade_row.duration_minutes,
                    hour_of_day=trade_row.hour_of_day,
                    day_of_week=trade_row.day_of_week
                )
                
                # Check if trade falls within the specific 30-minute window
                if time_bin.matches_trade_time(trade.entry_time):
                    filtered_trades.append(trade)
            
            return filtered_trades
        
        if self.db_session:
            # Use provided session directly
            return _process_trades_with_session(self.db_session)
        else:
            # Use context manager
            with self._db_context() as session:
                return _process_trades_with_session(session)
    
    def calculate_time_bin_metrics(self, trades: List[SimpleTrade]) -> TimeBinMetrics:
        """
        Calculate comprehensive performance metrics for time-bin trades.
        
        Requirements: 1.2, 1.3 - Calculate Sharpe, Calmar, Sortino ratios with statistical significance
        """
        if not trades:
            # Return empty metrics for no trades
            time_bin = TimeBin("", 0, 0)  # Placeholder
            return TimeBinMetrics(
                time_bin=time_bin,
                total_trades=0,
                win_rate=0.0,
                average_pnl=0.0,
                total_pnl=0.0,
                sharpe_ratio=None,
                calmar_ratio=None,
                sortino_ratio=None,
                max_drawdown=0.0,
                profit_factor=0.0,
                confidence_interval_95=None,
                p_value_vs_random=None,
                statistical_significance=False,
                minimum_sample_size_met=False,
                volatility=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                winning_trades=0,
                losing_trades=0,
                average_win=0.0,
                average_loss=0.0
            )
        
        # Extract time bin from first trade
        first_trade = trades[0]
        time_bin = TimeBin(
            account_name=first_trade.account_name,
            hour=first_trade.hour_of_day,
            minute_bin=0 if first_trade.entry_time.minute < 30 else 30
        )
        
        # Basic metrics
        total_trades = len(trades)
        pnl_values = [trade.profit_loss for trade in trades]
        total_pnl = sum(pnl_values)
        average_pnl = total_pnl / total_trades
        
        # Win/loss analysis
        winning_trades = [trade for trade in trades if trade.profit_loss > 0]
        losing_trades = [trade for trade in trades if trade.profit_loss < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = win_count / total_trades
        
        # Calculate averages
        average_win = sum(trade.profit_loss for trade in winning_trades) / win_count if win_count > 0 else 0.0
        average_loss = sum(trade.profit_loss for trade in losing_trades) / loss_count if loss_count > 0 else 0.0
        
        # Profit factor
        gross_profit = sum(trade.profit_loss for trade in winning_trades)
        gross_loss = abs(sum(trade.profit_loss for trade in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        
        # Volatility and risk metrics
        volatility = np.std(pnl_values, ddof=1) if total_trades > 1 else 0.0
        
        # Drawdown calculation
        cumulative_pnl = np.cumsum(pnl_values)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdowns = cumulative_pnl - running_max
        max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0.0
        
        # Largest win/loss
        largest_win = max(pnl_values) if pnl_values else 0.0
        largest_loss = min(pnl_values) if pnl_values else 0.0
        
        # Risk-adjusted ratios
        sharpe_ratio = self._calculate_sharpe_ratio(pnl_values, volatility)
        calmar_ratio = self._calculate_calmar_ratio(total_pnl, max_drawdown, total_trades)
        sortino_ratio = self._calculate_sortino_ratio(pnl_values)
        
        # Statistical significance testing
        sample_size_adequate = total_trades >= self.minimum_sample_size
        confidence_interval = self._calculate_confidence_interval(pnl_values) if sample_size_adequate else None
        p_value = self._test_vs_random_trading(pnl_values) if sample_size_adequate else None
        is_significant = p_value is not None and p_value < 0.05
        
        return TimeBinMetrics(
            time_bin=time_bin,
            total_trades=total_trades,
            win_rate=win_rate,
            average_pnl=average_pnl,
            total_pnl=total_pnl,
            sharpe_ratio=sharpe_ratio,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            confidence_interval_95=confidence_interval,
            p_value_vs_random=p_value,
            statistical_significance=is_significant,
            minimum_sample_size_met=sample_size_adequate,
            volatility=volatility,
            largest_win=largest_win,
            largest_loss=largest_loss,
            winning_trades=win_count,
            losing_trades=loss_count,
            average_win=average_win,
            average_loss=average_loss
        )
    
    def test_statistical_significance(self, metrics: TimeBinMetrics) -> List[SignificanceTest]:
        """
        Add statistical significance testing for time-bin performance.
        
        Requirements: 5.1 - Statistical confidence testing
        """
        tests = []
        
        if not metrics.minimum_sample_size_met:
            return tests
        
        # Get the original trade data for testing
        trades = self.get_time_bin_trades(metrics.time_bin)
        pnl_values = [trade.profit_loss for trade in trades]
        
        # Test 1: One-sample t-test against zero (random trading)
        if len(pnl_values) > 1:
            t_stat, p_value = stats.ttest_1samp(pnl_values, 0)
            tests.append(SignificanceTest(
                test_name="One-sample t-test vs zero",
                p_value=p_value,
                is_significant=p_value < 0.05,
                confidence_level=0.95,
                test_statistic=t_stat,
                critical_value=stats.t.ppf(0.975, len(pnl_values) - 1),
                interpretation=f"Tests if average P&L is significantly different from zero (random trading)"
            ))
        
        # Test 2: Wilcoxon signed-rank test (non-parametric)
        if len(pnl_values) > 5:  # Minimum for Wilcoxon test
            try:
                w_stat, p_value = stats.wilcoxon(pnl_values)
                tests.append(SignificanceTest(
                    test_name="Wilcoxon signed-rank test",
                    p_value=p_value,
                    is_significant=p_value < 0.05,
                    confidence_level=0.95,
                    test_statistic=w_stat,
                    critical_value=0,  # Critical value depends on sample size
                    interpretation="Non-parametric test for median P&L different from zero"
                ))
            except ValueError:
                # Handle case where all values are the same
                pass
        
        # Test 3: Binomial test for win rate
        if metrics.total_trades > 0:
            # Test if win rate is significantly different from 50%
            successes = metrics.winning_trades
            n_trials = metrics.total_trades
            try:
                # Use newer binomtest if available (scipy >= 1.7.0)
                result = stats.binomtest(successes, n_trials, 0.5, alternative='two-sided')
                p_value = result.pvalue
            except AttributeError:
                # Fallback to deprecated binom_test for older scipy versions
                p_value = stats.binom_test(successes, n_trials, 0.5, alternative='two-sided')
            
            tests.append(SignificanceTest(
                test_name="Binomial test for win rate",
                p_value=p_value,
                is_significant=p_value < 0.05,
                confidence_level=0.95,
                test_statistic=successes / n_trials,
                critical_value=0.5,
                interpretation="Tests if win rate is significantly different from 50% (random)"
            ))
        
        return tests
    
    def _calculate_sharpe_ratio(self, pnl_values: List[float], volatility: float) -> Optional[float]:
        """Calculate Sharpe ratio for the time bin."""
        if volatility == 0 or len(pnl_values) == 0:
            return None
        
        # Convert to annualized metrics (assuming daily trading)
        average_return = np.mean(pnl_values)
        # Assume 252 trading days per year
        annualized_return = average_return * 252
        annualized_volatility = volatility * np.sqrt(252)
        
        return (annualized_return - self.risk_free_rate) / annualized_volatility
    
    def _calculate_calmar_ratio(self, total_pnl: float, max_drawdown: float, num_trades: int) -> Optional[float]:
        """Calculate Calmar ratio (annualized return / max drawdown)."""
        if max_drawdown == 0 or num_trades == 0:
            return None
        
        # Annualize the return (assuming daily trading)
        annualized_return = (total_pnl / num_trades) * 252
        return annualized_return / abs(max_drawdown)
    
    def _calculate_sortino_ratio(self, pnl_values: List[float]) -> Optional[float]:
        """Calculate Sortino ratio (return / downside deviation)."""
        if len(pnl_values) == 0:
            return None
        
        average_return = np.mean(pnl_values)
        
        # Calculate downside deviation (only negative returns)
        negative_returns = [pnl for pnl in pnl_values if pnl < 0]
        if len(negative_returns) == 0:
            return float('inf') if average_return > 0 else None
        
        downside_deviation = np.std(negative_returns, ddof=1)
        if downside_deviation == 0:
            return None
        
        # Annualize
        annualized_return = average_return * 252
        annualized_downside_dev = downside_deviation * np.sqrt(252)
        
        return (annualized_return - self.risk_free_rate) / annualized_downside_dev
    
    def _calculate_confidence_interval(self, pnl_values: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval for average P&L."""
        if len(pnl_values) < 2:
            return (0.0, 0.0)
        
        mean_pnl = np.mean(pnl_values)
        std_error = stats.sem(pnl_values)  # Standard error of the mean
        
        # Calculate confidence interval
        alpha = 1 - confidence
        degrees_freedom = len(pnl_values) - 1
        t_critical = stats.t.ppf(1 - alpha/2, degrees_freedom)
        
        margin_error = t_critical * std_error
        
        return (mean_pnl - margin_error, mean_pnl + margin_error)
    
    def _test_vs_random_trading(self, pnl_values: List[float]) -> float:
        """Test if performance is significantly different from random trading."""
        if len(pnl_values) < 2:
            return 1.0
        
        # One-sample t-test against zero (random trading expectation)
        t_stat, p_value = stats.ttest_1samp(pnl_values, 0)
        return p_value
    
    def analyze_time_bin(self, time_bin: TimeBin) -> Tuple[TimeBinMetrics, List[SignificanceTest]]:
        """
        Complete analysis of a time bin including metrics and significance tests.
        
        Returns tuple of (metrics, significance_tests)
        """
        trades = self.get_time_bin_trades(time_bin)
        metrics = self.calculate_time_bin_metrics(trades)
        significance_tests = self.test_statistical_significance(metrics)
        
        return metrics, significance_tests
    
    def compare_time_bins(self, time_bin1: TimeBin, time_bin2: TimeBin) -> Dict[str, Any]:
        """
        Compare performance between two time bins with statistical testing.
        
        Requirements: 5.1 - Statistical comparison between time windows
        """
        # Get trades for both time bins
        trades1 = self.get_time_bin_trades(time_bin1)
        trades2 = self.get_time_bin_trades(time_bin2)
        
        if not trades1 or not trades2:
            return {
                "error": "Insufficient data for comparison",
                "time_bin1_trades": len(trades1),
                "time_bin2_trades": len(trades2)
            }
        
        # Calculate metrics for both
        metrics1 = self.calculate_time_bin_metrics(trades1)
        metrics2 = self.calculate_time_bin_metrics(trades2)
        
        # Statistical comparison
        pnl1 = [trade.profit_loss for trade in trades1]
        pnl2 = [trade.profit_loss for trade in trades2]
        
        # Two-sample t-test
        t_stat, p_value = stats.ttest_ind(pnl1, pnl2)
        
        # Mann-Whitney U test (non-parametric)
        u_stat, u_p_value = stats.mannwhitneyu(pnl1, pnl2, alternative='two-sided')
        
        return {
            "time_bin1": {
                "time_bin": time_bin1,
                "metrics": metrics1
            },
            "time_bin2": {
                "time_bin": time_bin2,
                "metrics": metrics2
            },
            "statistical_comparison": {
                "t_test": {
                    "statistic": t_stat,
                    "p_value": p_value,
                    "significant": p_value < 0.05,
                    "interpretation": "Parametric test for difference in means"
                },
                "mann_whitney_u": {
                    "statistic": u_stat,
                    "p_value": u_p_value,
                    "significant": u_p_value < 0.05,
                    "interpretation": "Non-parametric test for difference in distributions"
                }
            },
            "performance_difference": {
                "average_pnl_diff": metrics1.average_pnl - metrics2.average_pnl,
                "win_rate_diff": metrics1.win_rate - metrics2.win_rate,
                "sharpe_diff": (metrics1.sharpe_ratio or 0) - (metrics2.sharpe_ratio or 0)
            }
        }