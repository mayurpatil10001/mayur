"""
Account comparison and statistical testing service for trading analysis.

This service provides statistical comparison methods between accounts including:
- Hypothesis testing for performance differences
- Correlation analysis between different assets/accounts
- Statistical significance testing for account performance comparisons

Requirements: 3.3, 3.5
"""

import numpy as np
import scipy.stats as stats
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from collections import defaultdict
import itertools

from ..models.trading import ProcessedTrade, PerformanceMetrics, Account
from ..services.performance_metrics_calculator import PerformanceMetricsCalculator
from ..utils.validators import ValidationError


@dataclass
class AccountComparisonResult:
    """Results of statistical comparison between two accounts."""
    account_1: str
    account_2: str
    symbol_1: str
    symbol_2: str
    comparison_period_start: datetime
    comparison_period_end: datetime
    
    # Basic statistics
    account_1_trades: int
    account_2_trades: int
    account_1_mean_return: float
    account_2_mean_return: float
    account_1_volatility: float
    account_2_volatility: float
    
    # Statistical test results
    mean_difference: float
    t_statistic: float
    p_value: float
    is_significantly_different: bool
    confidence_interval_lower: float
    confidence_interval_upper: float
    
    # Effect size measures
    cohens_d: float
    effect_size_interpretation: str
    
    # Risk-adjusted comparison
    sharpe_ratio_1: Optional[float]
    sharpe_ratio_2: Optional[float]
    sharpe_difference: Optional[float]
    
    # Additional metrics
    variance_ratio: float
    variance_test_p_value: float
    equal_variances: bool


@dataclass
class CorrelationAnalysisResult:
    """Results of correlation analysis between accounts/assets."""
    account_pairs: List[Tuple[str, str]]
    symbol_pairs: List[Tuple[str, str]]
    analysis_period_start: datetime
    analysis_period_end: datetime
    
    # Correlation matrices
    return_correlations: Dict[Tuple[str, str], float]
    correlation_p_values: Dict[Tuple[str, str], float]
    significant_correlations: Dict[Tuple[str, str], bool]
    
    # Portfolio diversification metrics
    average_correlation: float
    max_correlation: float
    min_correlation: float
    diversification_ratio: float


@dataclass
class MultiAccountAnalysisResult:
    """Results of multi-account statistical analysis."""
    accounts: List[str]
    symbols: List[str]
    analysis_period_start: datetime
    analysis_period_end: datetime
    
    # ANOVA results
    f_statistic: float
    anova_p_value: float
    significant_differences: bool
    
    # Post-hoc analysis
    pairwise_comparisons: List[AccountComparisonResult]
    best_performing_account: str
    worst_performing_account: str
    
    # Risk analysis
    most_consistent_account: str
    most_volatile_account: str
    
    # Correlation analysis
    correlation_analysis: CorrelationAnalysisResult


class AccountComparisonError(Exception):
    """Exception raised by account comparison service."""
    pass


class AccountComparisonService:
    """
    Provides statistical comparison and analysis between trading accounts.
    
    This service implements comprehensive statistical testing to compare
    account performance, analyze correlations, and provide insights for
    trading optimization decisions.
    """
    
    def __init__(self, significance_level: float = 0.05, confidence_level: float = 0.95):
        """
        Initialize the account comparison service.
        
        Args:
            significance_level: Alpha level for statistical tests (default 0.05)
            confidence_level: Confidence level for intervals (default 0.95)
        """
        self.significance_level = significance_level
        self.confidence_level = confidence_level
        self.performance_calculator = PerformanceMetricsCalculator()
    
    def compare_two_accounts(
        self,
        trades_1: List[ProcessedTrade],
        trades_2: List[ProcessedTrade],
        account_1: str,
        account_2: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> AccountComparisonResult:
        """
        Perform comprehensive statistical comparison between two accounts.
        
        Args:
            trades_1: Trades from first account
            trades_2: Trades from second account
            account_1: Name of first account
            account_2: Name of second account
            period_start: Start of comparison period
            period_end: End of comparison period
            
        Returns:
            AccountComparisonResult with detailed comparison statistics
            
        Raises:
            AccountComparisonError: If comparison fails
        """
        if not trades_1 or not trades_2:
            raise AccountComparisonError("Both accounts must have trades for comparison")
        
        try:
            # Filter trades by period
            filtered_trades_1 = self._filter_trades_by_period(trades_1, period_start, period_end)
            filtered_trades_2 = self._filter_trades_by_period(trades_2, period_start, period_end)
            
            if not filtered_trades_1 or not filtered_trades_2:
                raise AccountComparisonError("No trades found in specified period for one or both accounts")
            
            # Determine comparison period
            if period_start is None:
                period_start = min(
                    min(t.entry_time for t in filtered_trades_1),
                    min(t.entry_time for t in filtered_trades_2)
                )
            if period_end is None:
                period_end = max(
                    max(t.exit_time for t in filtered_trades_1),
                    max(t.exit_time for t in filtered_trades_2)
                )
            
            # Extract returns for statistical analysis
            returns_1 = [t.profit_loss for t in filtered_trades_1]
            returns_2 = [t.profit_loss for t in filtered_trades_2]
            
            # Basic statistics
            mean_1 = np.mean(returns_1)
            mean_2 = np.mean(returns_2)
            std_1 = np.std(returns_1, ddof=1)
            std_2 = np.std(returns_2, ddof=1)
            
            # Two-sample t-test
            t_stat, p_value = stats.ttest_ind(returns_1, returns_2, equal_var=False)
            mean_diff = mean_1 - mean_2
            
            # Confidence interval for mean difference
            n1, n2 = len(returns_1), len(returns_2)
            se_diff = np.sqrt(std_1**2/n1 + std_2**2/n2)
            
            # Welch's t-test degrees of freedom
            df = (std_1**2/n1 + std_2**2/n2)**2 / ((std_1**2/n1)**2/(n1-1) + (std_2**2/n2)**2/(n2-1))
            t_critical = stats.t.ppf((1 + self.confidence_level) / 2, df)
            margin_error = t_critical * se_diff
            
            # Effect size (Cohen's d)
            pooled_std = np.sqrt(((n1-1)*std_1**2 + (n2-1)*std_2**2) / (n1+n2-2))
            cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0.0
            effect_size_interpretation = self._interpret_effect_size(abs(cohens_d))
            
            # Variance test (F-test)
            f_stat = std_1**2 / std_2**2 if std_2 > 0 else 1.0
            variance_p_value = 2 * min(
                stats.f.cdf(f_stat, n1-1, n2-1),
                1 - stats.f.cdf(f_stat, n1-1, n2-1)
            )
            equal_variances = bool(variance_p_value > self.significance_level)
            
            # Calculate Sharpe ratios
            sharpe_1 = self.performance_calculator._calculate_sharpe_ratio(returns_1, std_1)
            sharpe_2 = self.performance_calculator._calculate_sharpe_ratio(returns_2, std_2)
            sharpe_diff = None
            if sharpe_1 is not None and sharpe_2 is not None:
                sharpe_diff = sharpe_1 - sharpe_2
            
            # Get symbols
            symbol_1 = filtered_trades_1[0].symbol if filtered_trades_1 else "Unknown"
            symbol_2 = filtered_trades_2[0].symbol if filtered_trades_2 else "Unknown"
            
            return AccountComparisonResult(
                account_1=account_1,
                account_2=account_2,
                symbol_1=symbol_1,
                symbol_2=symbol_2,
                comparison_period_start=period_start,
                comparison_period_end=period_end,
                account_1_trades=len(filtered_trades_1),
                account_2_trades=len(filtered_trades_2),
                account_1_mean_return=mean_1,
                account_2_mean_return=mean_2,
                account_1_volatility=std_1,
                account_2_volatility=std_2,
                mean_difference=mean_diff,
                t_statistic=t_stat,
                p_value=p_value,
                is_significantly_different=bool(p_value < self.significance_level),
                confidence_interval_lower=mean_diff - margin_error,
                confidence_interval_upper=mean_diff + margin_error,
                cohens_d=cohens_d,
                effect_size_interpretation=effect_size_interpretation,
                sharpe_ratio_1=sharpe_1,
                sharpe_ratio_2=sharpe_2,
                sharpe_difference=sharpe_diff,
                variance_ratio=f_stat,
                variance_test_p_value=variance_p_value,
                equal_variances=equal_variances
            )
            
        except Exception as e:
            raise AccountComparisonError(f"Failed to compare accounts: {e}")
    
    def analyze_correlations(
        self,
        account_trades: Dict[str, List[ProcessedTrade]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        min_overlapping_days: int = 30
    ) -> CorrelationAnalysisResult:
        """
        Analyze correlations between multiple accounts/assets.
        
        Args:
            account_trades: Dictionary mapping account names to their trades
            period_start: Start of analysis period
            period_end: End of analysis period
            min_overlapping_days: Minimum overlapping trading days required
            
        Returns:
            CorrelationAnalysisResult with correlation analysis
            
        Raises:
            AccountComparisonError: If correlation analysis fails
        """
        if len(account_trades) < 2:
            raise AccountComparisonError("Need at least 2 accounts for correlation analysis")
        
        try:
            # Filter trades by period for all accounts
            filtered_account_trades = {}
            for account, trades in account_trades.items():
                filtered_trades = self._filter_trades_by_period(trades, period_start, period_end)
                if filtered_trades:
                    filtered_account_trades[account] = filtered_trades
            
            if len(filtered_account_trades) < 2:
                raise AccountComparisonError("Need at least 2 accounts with trades in the specified period")
            
            # Determine analysis period
            all_trades = [trade for trades in filtered_account_trades.values() for trade in trades]
            if period_start is None:
                period_start = min(t.entry_time for t in all_trades)
            if period_end is None:
                period_end = max(t.exit_time for t in all_trades)
            
            # Create daily returns for each account
            daily_returns = self._calculate_daily_returns(filtered_account_trades, period_start, period_end)
            
            # Filter accounts with sufficient data
            accounts_with_data = [
                account for account, returns in daily_returns.items()
                if len(returns) >= min_overlapping_days
            ]
            
            if len(accounts_with_data) < 2:
                raise AccountComparisonError(f"Need at least 2 accounts with {min_overlapping_days} days of data")
            
            # Calculate correlations
            account_pairs = list(itertools.combinations(accounts_with_data, 2))
            return_correlations = {}
            correlation_p_values = {}
            significant_correlations = {}
            
            for account_1, account_2 in account_pairs:
                # Get overlapping dates
                dates_1 = set(daily_returns[account_1].keys())
                dates_2 = set(daily_returns[account_2].keys())
                overlapping_dates = sorted(dates_1.intersection(dates_2))
                
                if len(overlapping_dates) < min_overlapping_days:
                    continue
                
                # Extract returns for overlapping dates
                returns_1 = [daily_returns[account_1][date] for date in overlapping_dates]
                returns_2 = [daily_returns[account_2][date] for date in overlapping_dates]
                
                # Calculate correlation
                correlation, p_value = stats.pearsonr(returns_1, returns_2)
                
                pair_key = (account_1, account_2)
                return_correlations[pair_key] = correlation
                correlation_p_values[pair_key] = p_value
                significant_correlations[pair_key] = bool(p_value < self.significance_level)
            
            # Calculate summary statistics
            correlations = list(return_correlations.values())
            avg_correlation = np.mean(correlations) if correlations else 0.0
            max_correlation = max(correlations) if correlations else 0.0
            min_correlation = min(correlations) if correlations else 0.0
            
            # Calculate diversification ratio
            diversification_ratio = self._calculate_diversification_ratio(correlations)
            
            # Get symbols
            symbols = list(set(trade.symbol for trades in filtered_account_trades.values() for trade in trades))
            symbol_pairs = [(symbols[i], symbols[j]) for i in range(len(symbols)) for j in range(i+1, len(symbols))]
            
            return CorrelationAnalysisResult(
                account_pairs=account_pairs,
                symbol_pairs=symbol_pairs,
                analysis_period_start=period_start,
                analysis_period_end=period_end,
                return_correlations=return_correlations,
                correlation_p_values=correlation_p_values,
                significant_correlations=significant_correlations,
                average_correlation=avg_correlation,
                max_correlation=max_correlation,
                min_correlation=min_correlation,
                diversification_ratio=diversification_ratio
            )
            
        except Exception as e:
            raise AccountComparisonError(f"Failed to analyze correlations: {e}")
    
    def perform_multi_account_analysis(
        self,
        account_trades: Dict[str, List[ProcessedTrade]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> MultiAccountAnalysisResult:
        """
        Perform comprehensive multi-account statistical analysis.
        
        Args:
            account_trades: Dictionary mapping account names to their trades
            period_start: Start of analysis period
            period_end: End of analysis period
            
        Returns:
            MultiAccountAnalysisResult with comprehensive analysis
            
        Raises:
            AccountComparisonError: If analysis fails
        """
        if len(account_trades) < 3:
            raise AccountComparisonError("Need at least 3 accounts for multi-account analysis")
        
        try:
            # Filter trades by period
            filtered_account_trades = {}
            for account, trades in account_trades.items():
                filtered_trades = self._filter_trades_by_period(trades, period_start, period_end)
                if filtered_trades:
                    filtered_account_trades[account] = filtered_trades
            
            if len(filtered_account_trades) < 3:
                raise AccountComparisonError("Need at least 3 accounts with trades in the specified period")
            
            # Determine analysis period
            all_trades = [trade for trades in filtered_account_trades.values() for trade in trades]
            if period_start is None:
                period_start = min(t.entry_time for t in all_trades)
            if period_end is None:
                period_end = max(t.exit_time for t in all_trades)
            
            # Prepare data for ANOVA
            account_returns = []
            account_labels = []
            
            for account, trades in filtered_account_trades.items():
                returns = [t.profit_loss for t in trades]
                account_returns.extend(returns)
                account_labels.extend([account] * len(returns))
            
            # Perform one-way ANOVA
            groups = [
                [t.profit_loss for t in trades]
                for trades in filtered_account_trades.values()
            ]
            f_stat, anova_p_value = stats.f_oneway(*groups)
            significant_differences = bool(anova_p_value < self.significance_level)
            
            # Pairwise comparisons (post-hoc analysis)
            pairwise_comparisons = []
            accounts = list(filtered_account_trades.keys())
            
            for i, account_1 in enumerate(accounts):
                for account_2 in accounts[i+1:]:
                    comparison = self.compare_two_accounts(
                        filtered_account_trades[account_1],
                        filtered_account_trades[account_2],
                        account_1,
                        account_2,
                        period_start,
                        period_end
                    )
                    pairwise_comparisons.append(comparison)
            
            # Identify best and worst performing accounts
            account_means = {
                account: np.mean([t.profit_loss for t in trades])
                for account, trades in filtered_account_trades.items()
            }
            best_account = max(account_means, key=account_means.get)
            worst_account = min(account_means, key=account_means.get)
            
            # Identify most consistent and volatile accounts
            account_volatilities = {
                account: np.std([t.profit_loss for t in trades], ddof=1)
                for account, trades in filtered_account_trades.items()
            }
            most_consistent_account = min(account_volatilities, key=account_volatilities.get)
            most_volatile_account = max(account_volatilities, key=account_volatilities.get)
            
            # Correlation analysis
            correlation_analysis = self.analyze_correlations(
                filtered_account_trades, period_start, period_end, min_overlapping_days=5
            )
            
            # Get symbols
            symbols = list(set(trade.symbol for trades in filtered_account_trades.values() for trade in trades))
            
            return MultiAccountAnalysisResult(
                accounts=accounts,
                symbols=symbols,
                analysis_period_start=period_start,
                analysis_period_end=period_end,
                f_statistic=f_stat,
                anova_p_value=anova_p_value,
                significant_differences=significant_differences,
                pairwise_comparisons=pairwise_comparisons,
                best_performing_account=best_account,
                worst_performing_account=worst_account,
                most_consistent_account=most_consistent_account,
                most_volatile_account=most_volatile_account,
                correlation_analysis=correlation_analysis
            )
            
        except Exception as e:
            raise AccountComparisonError(f"Failed to perform multi-account analysis: {e}")
    
    def test_performance_hypothesis(
        self,
        trades_1: List[ProcessedTrade],
        trades_2: List[ProcessedTrade],
        hypothesis: str = "two_sided",
        expected_difference: float = 0.0
    ) -> Dict[str, float]:
        """
        Test specific hypotheses about performance differences.
        
        Args:
            trades_1: Trades from first group
            trades_2: Trades from second group
            hypothesis: Type of test ("two_sided", "greater", "less")
            expected_difference: Expected difference under null hypothesis
            
        Returns:
            Dictionary with test results
            
        Raises:
            AccountComparisonError: If hypothesis test fails
        """
        if not trades_1 or not trades_2:
            raise AccountComparisonError("Both groups must have trades for hypothesis testing")
        
        try:
            returns_1 = [t.profit_loss for t in trades_1]
            returns_2 = [t.profit_loss for t in trades_2]
            
            # Adjust returns by expected difference
            adjusted_returns_1 = [r - expected_difference for r in returns_1]
            
            # Perform appropriate test based on hypothesis
            if hypothesis == "two_sided":
                t_stat, p_value = stats.ttest_ind(adjusted_returns_1, returns_2, equal_var=False)
            elif hypothesis == "greater":
                t_stat, p_value_two_sided = stats.ttest_ind(adjusted_returns_1, returns_2, equal_var=False)
                p_value = p_value_two_sided / 2 if t_stat > 0 else 1 - p_value_two_sided / 2
            elif hypothesis == "less":
                t_stat, p_value_two_sided = stats.ttest_ind(adjusted_returns_1, returns_2, equal_var=False)
                p_value = p_value_two_sided / 2 if t_stat < 0 else 1 - p_value_two_sided / 2
            else:
                raise AccountComparisonError(f"Unknown hypothesis type: {hypothesis}")
            
            # Calculate additional statistics
            mean_diff = np.mean(returns_1) - np.mean(returns_2)
            effect_size = self._calculate_effect_size(returns_1, returns_2)
            
            return {
                "t_statistic": t_stat,
                "p_value": p_value,
                "mean_difference": mean_diff,
                "effect_size": effect_size,
                "is_significant": bool(p_value < self.significance_level),
                "hypothesis": hypothesis,
                "expected_difference": expected_difference
            }
            
        except Exception as e:
            raise AccountComparisonError(f"Failed to test hypothesis: {e}")
    
    def _filter_trades_by_period(
        self,
        trades: List[ProcessedTrade],
        period_start: Optional[datetime],
        period_end: Optional[datetime]
    ) -> List[ProcessedTrade]:
        """Filter trades by time period."""
        if period_start is None and period_end is None:
            return trades
        
        filtered = []
        for trade in trades:
            if period_start and trade.entry_time < period_start:
                continue
            if period_end and trade.entry_time > period_end:
                continue
            filtered.append(trade)
        
        return filtered
    
    def _calculate_daily_returns(
        self,
        account_trades: Dict[str, List[ProcessedTrade]],
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Dict[str, float]]:
        """Calculate daily returns for each account."""
        daily_returns = {}
        
        for account, trades in account_trades.items():
            account_daily_returns = defaultdict(float)
            
            for trade in trades:
                trade_date = trade.exit_time.date()
                account_daily_returns[trade_date] += trade.profit_loss
            
            daily_returns[account] = dict(account_daily_returns)
        
        return daily_returns
    
    def _interpret_effect_size(self, cohens_d: float) -> str:
        """Interpret Cohen's d effect size."""
        if cohens_d < 0.2:
            return "negligible"
        elif cohens_d < 0.5:
            return "small"
        elif cohens_d < 0.8:
            return "medium"
        else:
            return "large"
    
    def _calculate_effect_size(self, returns_1: List[float], returns_2: List[float]) -> float:
        """Calculate Cohen's d effect size."""
        n1, n2 = len(returns_1), len(returns_2)
        mean_diff = np.mean(returns_1) - np.mean(returns_2)
        
        # Pooled standard deviation
        s1, s2 = np.std(returns_1, ddof=1), np.std(returns_2, ddof=1)
        pooled_std = np.sqrt(((n1-1)*s1**2 + (n2-1)*s2**2) / (n1+n2-2))
        
        return mean_diff / pooled_std if pooled_std > 0 else 0.0
    
    def _calculate_diversification_ratio(self, correlations: List[float]) -> float:
        """Calculate portfolio diversification ratio."""
        if not correlations:
            return 1.0
        
        # Simple diversification ratio based on average correlation
        avg_correlation = np.mean(correlations)
        n_assets = len(correlations) + 1  # Number of assets (approximate)
        
        # Diversification ratio = 1 / sqrt(1 + (n-1) * avg_correlation)
        return 1.0 / np.sqrt(1 + (n_assets - 1) * avg_correlation)
    
    def validate_trades_for_comparison(
        self,
        account_trades: Dict[str, List[ProcessedTrade]]
    ) -> bool:
        """
        Validate that trades are suitable for account comparison.
        
        Args:
            account_trades: Dictionary of account trades to validate
            
        Returns:
            True if trades are valid for comparison
            
        Raises:
            AccountComparisonError: If validation fails
        """
        if not account_trades:
            raise AccountComparisonError("Account trades dictionary cannot be empty")
        
        if len(account_trades) < 2:
            raise AccountComparisonError("Need at least 2 accounts for comparison")
        
        for account, trades in account_trades.items():
            if not trades:
                raise AccountComparisonError(f"Account {account} has no trades")
            
            # Validate each trade has required fields
            for i, trade in enumerate(trades):
                if not hasattr(trade, 'profit_loss') or trade.profit_loss is None:
                    raise AccountComparisonError(f"Trade {i} in account {account} missing profit_loss")
                
                if not hasattr(trade, 'entry_time') or trade.entry_time is None:
                    raise AccountComparisonError(f"Trade {i} in account {account} missing entry_time")
                
                if not hasattr(trade, 'exit_time') or trade.exit_time is None:
                    raise AccountComparisonError(f"Trade {i} in account {account} missing exit_time")
                
                if not hasattr(trade, 'account_name') or trade.account_name != account:
                    raise AccountComparisonError(f"Trade {i} account name mismatch")
        
        return True