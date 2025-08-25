"""
Temporal pattern analyzer for trading performance analysis.

This service analyzes hour-of-day and day-of-week performance patterns including:
- Statistical significance testing for temporal patterns
- Confidence interval calculations for pattern reliability
- Performance metrics by time periods

Requirements: 3.2, 3.4
"""

import numpy as np
import scipy.stats as stats
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from collections import defaultdict

from ..models.trading import ProcessedTrade
from ..utils.validators import ValidationError


@dataclass
class TemporalPattern:
    """Represents a temporal performance pattern."""
    time_period: int  # Hour (0-23) or day of week (0-6)
    period_type: str  # 'hour' or 'day_of_week'
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    average_pnl: float
    win_rate: float
    volatility: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    statistical_significance: float  # p-value
    is_significant: bool


@dataclass
class TemporalComparison:
    """Comparison between two temporal periods."""
    period_1: int
    period_2: int
    period_type: str
    mean_difference: float
    t_statistic: float
    p_value: float
    is_significant: bool
    confidence_interval_lower: float
    confidence_interval_upper: float


@dataclass
class TemporalAnalysisResult:
    """Complete temporal analysis results."""
    account_name: str
    symbol: str
    analysis_period_start: datetime
    analysis_period_end: datetime
    hourly_patterns: List[TemporalPattern]
    daily_patterns: List[TemporalPattern]
    best_hours: List[int]
    worst_hours: List[int]
    best_days: List[int]
    worst_days: List[int]
    significant_patterns: List[TemporalPattern]
    pattern_comparisons: List[TemporalComparison]


class TemporalAnalysisError(Exception):
    """Exception raised by temporal analysis service."""
    pass


class TemporalAnalysisService:
    """
    Analyzes temporal patterns in trading performance.
    
    This service provides comprehensive analysis of time-based trading patterns
    including statistical significance testing and confidence intervals.
    """
    
    def __init__(self, confidence_level: float = 0.95, significance_threshold: float = 0.05):
        """
        Initialize the temporal analysis service.
        
        Args:
            confidence_level: Confidence level for intervals (default 95%)
            significance_threshold: P-value threshold for significance (default 0.05)
        """
        self.confidence_level = confidence_level
        self.significance_threshold = significance_threshold
    
    def analyze_temporal_patterns(
        self,
        trades: List[ProcessedTrade],
        account_name: str,
        symbol: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> TemporalAnalysisResult:
        """
        Perform comprehensive temporal pattern analysis.
        
        Args:
            trades: List of processed trades to analyze
            account_name: Account name for the analysis
            symbol: Symbol for the analysis
            period_start: Start of analysis period (defaults to first trade)
            period_end: End of analysis period (defaults to last trade)
            
        Returns:
            TemporalAnalysisResult with complete analysis
            
        Raises:
            TemporalAnalysisError: If analysis fails
        """
        if not trades:
            raise TemporalAnalysisError("Cannot analyze temporal patterns for empty trade list")
        
        try:
            # Filter trades by period if specified
            filtered_trades = self._filter_trades_by_period(trades, period_start, period_end)
            
            if not filtered_trades:
                raise TemporalAnalysisError("No trades found in specified period")
            
            # Determine analysis period
            if period_start is None:
                period_start = min(t.entry_time for t in filtered_trades)
            if period_end is None:
                period_end = max(t.exit_time for t in filtered_trades)
            
            # Analyze hourly patterns
            hourly_patterns = self._analyze_hourly_patterns(filtered_trades)
            
            # Analyze daily patterns
            daily_patterns = self._analyze_daily_patterns(filtered_trades)
            
            # Identify best and worst periods
            best_hours = self._identify_best_periods(hourly_patterns)
            worst_hours = self._identify_worst_periods(hourly_patterns)
            best_days = self._identify_best_periods(daily_patterns)
            worst_days = self._identify_worst_periods(daily_patterns)
            
            # Find significant patterns
            significant_patterns = [p for p in hourly_patterns + daily_patterns if p.is_significant]
            
            # Perform pattern comparisons
            pattern_comparisons = self._compare_patterns(filtered_trades)
            
            return TemporalAnalysisResult(
                account_name=account_name,
                symbol=symbol,
                analysis_period_start=period_start,
                analysis_period_end=period_end,
                hourly_patterns=hourly_patterns,
                daily_patterns=daily_patterns,
                best_hours=best_hours,
                worst_hours=worst_hours,
                best_days=best_days,
                worst_days=worst_days,
                significant_patterns=significant_patterns,
                pattern_comparisons=pattern_comparisons
            )
            
        except Exception as e:
            raise TemporalAnalysisError(f"Failed to analyze temporal patterns: {e}")
    
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
    
    def _analyze_hourly_patterns(self, trades: List[ProcessedTrade]) -> List[TemporalPattern]:
        """Analyze performance patterns by hour of day."""
        hourly_data = defaultdict(list)
        
        # Group trades by hour
        for trade in trades:
            hourly_data[trade.hour_of_day].append(trade.profit_loss)
        
        patterns = []
        for hour in range(24):
            if hour not in hourly_data:
                # Create empty pattern for hours with no trades
                patterns.append(TemporalPattern(
                    time_period=hour,
                    period_type='hour',
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    total_pnl=0.0,
                    average_pnl=0.0,
                    win_rate=0.0,
                    volatility=0.0,
                    confidence_interval_lower=0.0,
                    confidence_interval_upper=0.0,
                    statistical_significance=1.0,
                    is_significant=False
                ))
                continue
            
            pnl_data = hourly_data[hour]
            pattern = self._calculate_pattern_metrics(hour, 'hour', pnl_data)
            patterns.append(pattern)
        
        return patterns
    
    def _analyze_daily_patterns(self, trades: List[ProcessedTrade]) -> List[TemporalPattern]:
        """Analyze performance patterns by day of week."""
        daily_data = defaultdict(list)
        
        # Group trades by day of week
        for trade in trades:
            daily_data[trade.day_of_week].append(trade.profit_loss)
        
        patterns = []
        for day in range(7):
            if day not in daily_data:
                # Create empty pattern for days with no trades
                patterns.append(TemporalPattern(
                    time_period=day,
                    period_type='day_of_week',
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    total_pnl=0.0,
                    average_pnl=0.0,
                    win_rate=0.0,
                    volatility=0.0,
                    confidence_interval_lower=0.0,
                    confidence_interval_upper=0.0,
                    statistical_significance=1.0,
                    is_significant=False
                ))
                continue
            
            pnl_data = daily_data[day]
            pattern = self._calculate_pattern_metrics(day, 'day_of_week', pnl_data)
            patterns.append(pattern)
        
        return patterns
    
    def _calculate_pattern_metrics(
        self,
        time_period: int,
        period_type: str,
        pnl_data: List[float]
    ) -> TemporalPattern:
        """Calculate metrics for a temporal pattern."""
        if not pnl_data:
            return TemporalPattern(
                time_period=time_period,
                period_type=period_type,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0.0,
                average_pnl=0.0,
                win_rate=0.0,
                volatility=0.0,
                confidence_interval_lower=0.0,
                confidence_interval_upper=0.0,
                statistical_significance=1.0,
                is_significant=False
            )
        
        # Basic statistics
        total_trades = len(pnl_data)
        winning_trades = sum(1 for pnl in pnl_data if pnl > 0)
        losing_trades = total_trades - winning_trades
        total_pnl = sum(pnl_data)
        average_pnl = np.mean(pnl_data)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        volatility = np.std(pnl_data, ddof=1) if len(pnl_data) > 1 else 0.0
        
        # Confidence interval for mean
        if len(pnl_data) > 1:
            confidence_interval = stats.t.interval(
                self.confidence_level,
                len(pnl_data) - 1,
                loc=average_pnl,
                scale=stats.sem(pnl_data)
            )
            ci_lower, ci_upper = confidence_interval
        else:
            ci_lower = ci_upper = average_pnl
        
        # Statistical significance test (one-sample t-test against zero)
        if len(pnl_data) > 1:
            t_stat, p_value = stats.ttest_1samp(pnl_data, 0)
            is_significant = p_value < self.significance_threshold
        else:
            p_value = 1.0
            is_significant = False
        
        return TemporalPattern(
            time_period=time_period,
            period_type=period_type,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            average_pnl=average_pnl,
            win_rate=win_rate,
            volatility=volatility,
            confidence_interval_lower=ci_lower,
            confidence_interval_upper=ci_upper,
            statistical_significance=p_value,
            is_significant=is_significant
        )
    
    def _identify_best_periods(self, patterns: List[TemporalPattern]) -> List[int]:
        """Identify the best performing time periods."""
        # Filter patterns with trades and sort by average P&L
        patterns_with_trades = [p for p in patterns if p.total_trades > 0]
        if not patterns_with_trades:
            return []
        
        # Sort by average P&L descending
        sorted_patterns = sorted(patterns_with_trades, key=lambda p: p.average_pnl, reverse=True)
        
        # Return top 3 periods or all if less than 3
        top_count = min(3, len(sorted_patterns))
        return [p.time_period for p in sorted_patterns[:top_count] if p.average_pnl > 0]
    
    def _identify_worst_periods(self, patterns: List[TemporalPattern]) -> List[int]:
        """Identify the worst performing time periods."""
        # Filter patterns with trades and sort by average P&L
        patterns_with_trades = [p for p in patterns if p.total_trades > 0]
        if not patterns_with_trades:
            return []
        
        # Sort by average P&L ascending
        sorted_patterns = sorted(patterns_with_trades, key=lambda p: p.average_pnl)
        
        # Return bottom 3 periods or all if less than 3
        bottom_count = min(3, len(sorted_patterns))
        return [p.time_period for p in sorted_patterns[:bottom_count] if p.average_pnl < 0]
    
    def _compare_patterns(self, trades: List[ProcessedTrade]) -> List[TemporalComparison]:
        """Compare performance between different temporal periods."""
        comparisons = []
        
        # Compare hourly patterns
        hourly_data = defaultdict(list)
        for trade in trades:
            hourly_data[trade.hour_of_day].append(trade.profit_loss)
        
        # Compare significant hours
        hours_with_data = [h for h in hourly_data.keys() if len(hourly_data[h]) >= 5]  # Minimum 5 trades
        
        for i, hour1 in enumerate(hours_with_data):
            for hour2 in hours_with_data[i+1:]:
                comparison = self._compare_two_periods(
                    hour1, hour2, 'hour',
                    hourly_data[hour1], hourly_data[hour2]
                )
                if comparison:
                    comparisons.append(comparison)
        
        # Compare daily patterns
        daily_data = defaultdict(list)
        for trade in trades:
            daily_data[trade.day_of_week].append(trade.profit_loss)
        
        days_with_data = [d for d in daily_data.keys() if len(daily_data[d]) >= 5]  # Minimum 5 trades
        
        for i, day1 in enumerate(days_with_data):
            for day2 in days_with_data[i+1:]:
                comparison = self._compare_two_periods(
                    day1, day2, 'day_of_week',
                    daily_data[day1], daily_data[day2]
                )
                if comparison:
                    comparisons.append(comparison)
        
        return comparisons
    
    def _compare_two_periods(
        self,
        period1: int,
        period2: int,
        period_type: str,
        data1: List[float],
        data2: List[float]
    ) -> Optional[TemporalComparison]:
        """Compare two temporal periods using t-test."""
        if len(data1) < 2 or len(data2) < 2:
            return None
        
        # Perform two-sample t-test
        t_stat, p_value = stats.ttest_ind(data1, data2, equal_var=False)
        
        # Calculate mean difference
        mean_diff = np.mean(data1) - np.mean(data2)
        
        # Calculate confidence interval for the difference
        n1, n2 = len(data1), len(data2)
        s1, s2 = np.std(data1, ddof=1), np.std(data2, ddof=1)
        
        # Welch's t-test degrees of freedom
        se_diff = np.sqrt(s1**2/n1 + s2**2/n2)
        df = (s1**2/n1 + s2**2/n2)**2 / ((s1**2/n1)**2/(n1-1) + (s2**2/n2)**2/(n2-1))
        
        # Confidence interval
        t_critical = stats.t.ppf((1 + self.confidence_level) / 2, df)
        margin_error = t_critical * se_diff
        
        return TemporalComparison(
            period_1=period1,
            period_2=period2,
            period_type=period_type,
            mean_difference=mean_diff,
            t_statistic=t_stat,
            p_value=p_value,
            is_significant=p_value < self.significance_threshold,
            confidence_interval_lower=mean_diff - margin_error,
            confidence_interval_upper=mean_diff + margin_error
        )
    
    def get_trading_recommendations(
        self,
        analysis_result: TemporalAnalysisResult,
        current_time: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Generate trading recommendations based on temporal analysis.
        
        Args:
            analysis_result: Results from temporal analysis
            current_time: Current time for recommendations (defaults to now)
            
        Returns:
            Dictionary with recommendations
        """
        if current_time is None:
            current_time = datetime.now()
        
        current_hour = current_time.hour
        current_day = current_time.weekday()
        
        recommendations = {}
        
        # Hour-based recommendation
        if current_hour in analysis_result.best_hours:
            recommendations['hour'] = f"FAVORABLE: Hour {current_hour} is historically profitable"
        elif current_hour in analysis_result.worst_hours:
            recommendations['hour'] = f"CAUTION: Hour {current_hour} has historically poor performance"
        else:
            recommendations['hour'] = f"NEUTRAL: Hour {current_hour} shows average performance"
        
        # Day-based recommendation
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        current_day_name = day_names[current_day]
        
        if current_day in analysis_result.best_days:
            recommendations['day'] = f"FAVORABLE: {current_day_name} is historically profitable"
        elif current_day in analysis_result.worst_days:
            recommendations['day'] = f"CAUTION: {current_day_name} has historically poor performance"
        else:
            recommendations['day'] = f"NEUTRAL: {current_day_name} shows average performance"
        
        # Overall recommendation
        hour_favorable = current_hour in analysis_result.best_hours
        day_favorable = current_day in analysis_result.best_days
        hour_unfavorable = current_hour in analysis_result.worst_hours
        day_unfavorable = current_day in analysis_result.worst_days
        
        if hour_favorable and day_favorable:
            recommendations['overall'] = "STRONG BUY: Both hour and day patterns are favorable"
        elif hour_favorable or day_favorable:
            recommendations['overall'] = "BUY: One temporal pattern is favorable"
        elif hour_unfavorable and day_unfavorable:
            recommendations['overall'] = "STRONG AVOID: Both hour and day patterns are unfavorable"
        elif hour_unfavorable or day_unfavorable:
            recommendations['overall'] = "CAUTION: One temporal pattern is unfavorable"
        else:
            recommendations['overall'] = "NEUTRAL: No strong temporal patterns detected"
        
        return recommendations
    
    def validate_trades_for_analysis(self, trades: List[ProcessedTrade]) -> bool:
        """
        Validate that trades are suitable for temporal analysis.
        
        Args:
            trades: List of trades to validate
            
        Returns:
            True if trades are valid for analysis
            
        Raises:
            TemporalAnalysisError: If validation fails
        """
        if not trades:
            raise TemporalAnalysisError("Trade list cannot be empty")
        
        # Check for required temporal fields
        for i, trade in enumerate(trades):
            if not hasattr(trade, 'hour_of_day') or trade.hour_of_day is None:
                raise TemporalAnalysisError(f"Trade {i} missing hour_of_day")
            
            if not hasattr(trade, 'day_of_week') or trade.day_of_week is None:
                raise TemporalAnalysisError(f"Trade {i} missing day_of_week")
            
            if not hasattr(trade, 'profit_loss') or trade.profit_loss is None:
                raise TemporalAnalysisError(f"Trade {i} missing profit_loss")
            
            # Validate temporal field ranges
            if not (0 <= trade.hour_of_day <= 23):
                raise TemporalAnalysisError(f"Trade {i} has invalid hour_of_day: {trade.hour_of_day}")
            
            if not (0 <= trade.day_of_week <= 6):
                raise TemporalAnalysisError(f"Trade {i} has invalid day_of_week: {trade.day_of_week}")
        
        return True