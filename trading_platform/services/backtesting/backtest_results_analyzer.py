"""
Advanced analyzer for backtesting results with statistical analysis and visualization.

This module provides comprehensive analysis capabilities for backtesting results,
including performance attribution, risk analysis, and statistical validation.

Requirements: 9.2, 9.3, 10.2
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import statistics
import numpy as np
import pandas as pd
from scipy import stats
import json
from pathlib import Path

from .time_bin_backtesting_engine import (
    BacktestResult, BacktestPeriodResult, BacktestTrade, 
    BacktestConfiguration, PerformanceMetric, BacktestMethod
)
from ..time_bin_analyzer import TimeBin
from ..statistical_testing_engine import StatisticalTestingEngine

logger = logging.getLogger(__name__)


class AnalysisType(Enum):
    """Types of backtesting analysis."""
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    RISK_DECOMPOSITION = "risk_decomposition"
    TRADE_ANALYSIS = "trade_analysis"
    TEMPORAL_ANALYSIS = "temporal_analysis"
    STATISTICAL_VALIDATION = "statistical_validation"
    COMPARATIVE_ANALYSIS = "comparative_analysis"
    SENSITIVITY_ANALYSIS = "sensitivity_analysis"
    REGIME_ANALYSIS = "regime_analysis"


class RiskMetric(Enum):
    """Risk metrics for analysis."""
    VALUE_AT_RISK = "value_at_risk"
    CONDITIONAL_VAR = "conditional_var"
    MAXIMUM_DRAWDOWN = "maximum_drawdown"
    DOWNSIDE_DEVIATION = "downside_deviation"
    BETA = "beta"
    CORRELATION = "correlation"
    TRACKING_ERROR = "tracking_error"
    INFORMATION_RATIO = "information_ratio"


@dataclass
class PerformanceAttribution:
    """Performance attribution analysis results."""
    time_bin_contributions: Dict[TimeBin, float]
    temporal_contributions: Dict[str, float]  # by hour, day, month
    trade_type_contributions: Dict[str, float]
    risk_adjusted_contributions: Dict[TimeBin, float]
    
    # Top performers
    best_time_bins: List[Tuple[TimeBin, float]]
    worst_time_bins: List[Tuple[TimeBin, float]]
    
    # Consistency metrics
    consistency_score: float
    reliability_score: float


@dataclass
class RiskDecomposition:
    """Risk decomposition analysis results."""
    total_risk: float
    systematic_risk: float
    idiosyncratic_risk: float
    
    # Risk contributions by component
    time_bin_risk_contributions: Dict[TimeBin, float]
    temporal_risk_contributions: Dict[str, float]
    
    # Risk metrics
    value_at_risk: Dict[float, float]  # confidence level -> VaR
    conditional_var: Dict[float, float]  # confidence level -> CVaR
    maximum_drawdown_analysis: Dict[str, Any]
    
    # Correlation analysis
    correlation_matrix: Optional[pd.DataFrame] = None
    risk_concentration: float = 0.0


@dataclass
class TradeAnalysis:
    """Detailed trade analysis results."""
    trade_statistics: Dict[str, Any]
    win_loss_analysis: Dict[str, Any]
    holding_period_analysis: Dict[str, Any]
    size_analysis: Dict[str, Any]
    timing_analysis: Dict[str, Any]
    
    # Trade patterns
    entry_patterns: Dict[str, Any]
    exit_patterns: Dict[str, Any]
    seasonal_patterns: Dict[str, Any]
    
    # Quality metrics
    trade_quality_score: float
    execution_quality_score: float


@dataclass
class TemporalAnalysis:
    """Temporal performance analysis results."""
    daily_performance: Dict[date, float]
    weekly_performance: Dict[str, float]
    monthly_performance: Dict[str, float]
    hourly_performance: Dict[int, float]
    
    # Seasonality
    seasonal_patterns: Dict[str, Any]
    calendar_effects: Dict[str, Any]
    
    # Trends
    performance_trends: Dict[str, Any]
    regime_changes: List[Dict[str, Any]]


@dataclass
class StatisticalValidation:
    """Statistical validation of backtesting results."""
    significance_tests: Dict[str, Any]
    distribution_analysis: Dict[str, Any]
    outlier_analysis: Dict[str, Any]
    autocorrelation_analysis: Dict[str, Any]
    
    # Robustness tests
    bootstrap_results: Optional[Dict[str, Any]] = None
    monte_carlo_validation: Optional[Dict[str, Any]] = None
    
    # Model validation
    overfitting_tests: Dict[str, Any] = field(default_factory=dict)
    stability_tests: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparativeAnalysis:
    """Comparative analysis between multiple backtests."""
    strategy_comparisons: Dict[str, Any]
    benchmark_comparisons: Dict[str, Any]
    peer_analysis: Dict[str, Any]
    
    # Rankings
    performance_rankings: List[Tuple[str, float]]
    risk_adjusted_rankings: List[Tuple[str, float]]
    
    # Statistical tests
    significance_tests: Dict[str, Any]


@dataclass
class SensitivityAnalysis:
    """Sensitivity analysis for backtesting parameters."""
    parameter_sensitivity: Dict[str, Any]
    stress_test_results: Dict[str, Any]
    scenario_analysis: Dict[str, Any]
    
    # Stability metrics
    parameter_stability: Dict[str, float]
    robustness_score: float


@dataclass
class ComprehensiveAnalysis:
    """Complete analysis results for backtesting."""
    backtest_result: BacktestResult
    analysis_timestamp: datetime
    
    performance_attribution: Optional[PerformanceAttribution] = None
    risk_decomposition: Optional[RiskDecomposition] = None
    trade_analysis: Optional[TradeAnalysis] = None
    temporal_analysis: Optional[TemporalAnalysis] = None
    statistical_validation: Optional[StatisticalValidation] = None
    comparative_analysis: Optional[ComparativeAnalysis] = None
    sensitivity_analysis: Optional[SensitivityAnalysis] = None
    
    # Summary scores
    overall_quality_score: float = 0.0
    recommendation: str = ""
    key_insights: List[str] = field(default_factory=list)


class BacktestResultsAnalyzer:
    """
    Advanced analyzer for backtesting results.
    
    Provides comprehensive analysis including performance attribution, risk decomposition,
    statistical validation, and comparative analysis capabilities.
    """
    
    def __init__(
        self,
        statistical_testing: Optional[StatisticalTestingEngine] = None,
        risk_free_rate: float = 0.02
    ):
        """Initialize the analyzer."""
        self.statistical_testing = statistical_testing or StatisticalTestingEngine()
        self.risk_free_rate = risk_free_rate
        
        # Analysis cache
        self.analysis_cache: Dict[str, ComprehensiveAnalysis] = {}
        
        logger.info("BacktestResultsAnalyzer initialized")
    
    async def analyze_comprehensive(
        self,
        backtest_result: BacktestResult,
        analysis_types: Optional[List[AnalysisType]] = None,
        benchmark_results: Optional[List[BacktestResult]] = None,
        cache_key: Optional[str] = None
    ) -> ComprehensiveAnalysis:
        """
        Perform comprehensive analysis of backtesting results.
        
        Args:
            backtest_result: Backtesting results to analyze
            analysis_types: Types of analysis to perform (default: all)
            benchmark_results: Additional results for comparative analysis
            cache_key: Optional cache key for results
            
        Returns:
            Comprehensive analysis results
        """
        if cache_key and cache_key in self.analysis_cache:
            logger.info(f"Returning cached analysis for {cache_key}")
            return self.analysis_cache[cache_key]
        
        if analysis_types is None:
            analysis_types = list(AnalysisType)
        
        logger.info(f"Starting comprehensive analysis with {len(analysis_types)} analysis types")
        
        analysis = ComprehensiveAnalysis(
            backtest_result=backtest_result,
            analysis_timestamp=datetime.now()
        )
        
        # Perform requested analyses
        try:
            if AnalysisType.PERFORMANCE_ATTRIBUTION in analysis_types:
                analysis.performance_attribution = await self.analyze_performance_attribution(backtest_result)
            
            if AnalysisType.RISK_DECOMPOSITION in analysis_types:
                analysis.risk_decomposition = await self.analyze_risk_decomposition(backtest_result)
            
            if AnalysisType.TRADE_ANALYSIS in analysis_types:
                analysis.trade_analysis = await self.analyze_trades(backtest_result)
            
            if AnalysisType.TEMPORAL_ANALYSIS in analysis_types:
                analysis.temporal_analysis = await self.analyze_temporal_patterns(backtest_result)
            
            if AnalysisType.STATISTICAL_VALIDATION in analysis_types:
                analysis.statistical_validation = await self.validate_statistical_significance(backtest_result)
            
            if AnalysisType.COMPARATIVE_ANALYSIS in analysis_types and benchmark_results:
                analysis.comparative_analysis = await self.analyze_comparative_performance(
                    backtest_result, benchmark_results
                )
            
            if AnalysisType.SENSITIVITY_ANALYSIS in analysis_types:
                analysis.sensitivity_analysis = await self.analyze_sensitivity(backtest_result)
            
            # Calculate overall quality score and generate insights
            analysis.overall_quality_score = self._calculate_overall_quality_score(analysis)
            analysis.recommendation = self._generate_recommendation(analysis)
            analysis.key_insights = self._extract_key_insights(analysis)
            
            # Cache results if key provided
            if cache_key:
                self.analysis_cache[cache_key] = analysis
            
            logger.info("Comprehensive analysis completed successfully")
            return analysis
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed: {str(e)}")
            raise
    
    async def analyze_performance_attribution(
        self, 
        backtest_result: BacktestResult
    ) -> PerformanceAttribution:
        """Analyze performance attribution across time-bins and temporal dimensions."""
        logger.debug("Analyzing performance attribution")
        
        # Collect all trades from all periods
        all_trades = []
        for period_result in backtest_result.period_results:
            all_trades.extend(period_result.trades)
        
        if not all_trades:
            all_trades = backtest_result.overall_result.trades
        
        # Time-bin contributions
        time_bin_pnl = {}
        for trade in all_trades:
            if trade.time_bin not in time_bin_pnl:
                time_bin_pnl[trade.time_bin] = 0.0
            time_bin_pnl[trade.time_bin] += trade.pnl or 0.0
        
        total_pnl = sum(time_bin_pnl.values())
        time_bin_contributions = {
            tb: pnl / total_pnl if total_pnl != 0 else 0.0
            for tb, pnl in time_bin_pnl.items()
        }
        
        # Temporal contributions
        hourly_pnl = {}
        daily_pnl = {}
        monthly_pnl = {}
        
        for trade in all_trades:
            if not trade.entry_time:
                continue
            
            hour = trade.entry_time.hour
            day = trade.entry_time.strftime('%A')
            month = trade.entry_time.strftime('%B')
            
            hourly_pnl[hour] = hourly_pnl.get(hour, 0.0) + (trade.pnl or 0.0)
            daily_pnl[day] = daily_pnl.get(day, 0.0) + (trade.pnl or 0.0)
            monthly_pnl[month] = monthly_pnl.get(month, 0.0) + (trade.pnl or 0.0)
        
        temporal_contributions = {
            'hourly': {h: pnl / total_pnl if total_pnl != 0 else 0.0 for h, pnl in hourly_pnl.items()},
            'daily': {d: pnl / total_pnl if total_pnl != 0 else 0.0 for d, pnl in daily_pnl.items()},
            'monthly': {m: pnl / total_pnl if total_pnl != 0 else 0.0 for m, pnl in monthly_pnl.items()}
        }
        
        # Trade type contributions
        long_pnl = sum(trade.pnl or 0.0 for trade in all_trades if trade.trade_type == 'LONG')
        short_pnl = sum(trade.pnl or 0.0 for trade in all_trades if trade.trade_type == 'SHORT')
        
        trade_type_contributions = {
            'LONG': long_pnl / total_pnl if total_pnl != 0 else 0.0,
            'SHORT': short_pnl / total_pnl if total_pnl != 0 else 0.0
        }
        
        # Risk-adjusted contributions (Sharpe ratio weighting)
        risk_adjusted_contributions = {}
        for time_bin, pnl in time_bin_pnl.items():
            tb_trades = [t for t in all_trades if t.time_bin == time_bin]
            if len(tb_trades) > 1:
                tb_returns = [t.pnl or 0.0 for t in tb_trades]
                mean_return = statistics.mean(tb_returns)
                std_return = statistics.stdev(tb_returns) if len(tb_returns) > 1 else 1.0
                sharpe = mean_return / std_return if std_return > 0 else 0.0
                risk_adjusted_contributions[time_bin] = sharpe * (pnl / total_pnl if total_pnl != 0 else 0.0)
            else:
                risk_adjusted_contributions[time_bin] = pnl / total_pnl if total_pnl != 0 else 0.0
        
        # Best and worst performers
        sorted_contributors = sorted(time_bin_contributions.items(), key=lambda x: x[1], reverse=True)
        best_time_bins = sorted_contributors[:5]
        worst_time_bins = sorted_contributors[-5:]
        
        # Consistency and reliability scores
        time_bin_returns = {}
        for time_bin in time_bin_pnl.keys():
            tb_trades = [t for t in all_trades if t.time_bin == time_bin]
            time_bin_returns[time_bin] = [t.pnl or 0.0 for t in tb_trades]
        
        # Consistency score (based on return stability)
        consistency_scores = []
        for tb, returns in time_bin_returns.items():
            if len(returns) > 1:
                mean_return = statistics.mean(returns)
                std_return = statistics.stdev(returns)
                consistency = 1.0 - (std_return / abs(mean_return) if mean_return != 0 else 1.0)
                consistency_scores.append(max(0.0, min(1.0, consistency)))
        
        consistency_score = statistics.mean(consistency_scores) if consistency_scores else 0.0
        
        # Reliability score (based on win rate consistency)
        reliability_scores = []
        for tb, returns in time_bin_returns.items():
            if len(returns) > 0:
                win_rate = len([r for r in returns if r > 0]) / len(returns)
                reliability_scores.append(win_rate)
        
        reliability_score = statistics.mean(reliability_scores) if reliability_scores else 0.0
        
        return PerformanceAttribution(
            time_bin_contributions=time_bin_contributions,
            temporal_contributions=temporal_contributions,
            trade_type_contributions=trade_type_contributions,
            risk_adjusted_contributions=risk_adjusted_contributions,
            best_time_bins=best_time_bins,
            worst_time_bins=worst_time_bins,
            consistency_score=consistency_score,
            reliability_score=reliability_score
        )
    
    async def analyze_risk_decomposition(
        self, 
        backtest_result: BacktestResult
    ) -> RiskDecomposition:
        """Analyze risk decomposition and calculate risk metrics."""
        logger.debug("Analyzing risk decomposition")
        
        # Collect returns data
        all_trades = []
        for period_result in backtest_result.period_results:
            all_trades.extend(period_result.trades)
        
        if not all_trades:
            all_trades = backtest_result.overall_result.trades
        
        if not all_trades:
            return RiskDecomposition(
                total_risk=0.0,
                systematic_risk=0.0,
                idiosyncratic_risk=0.0,
                time_bin_risk_contributions={},
                temporal_risk_contributions={},
                value_at_risk={},
                conditional_var={},
                maximum_drawdown_analysis={}
            )
        
        # Calculate returns
        returns = [trade.pnl or 0.0 for trade in all_trades]
        
        # Total risk (volatility)
        total_risk = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        # Time-bin specific risk analysis
        time_bin_returns = {}
        for trade in all_trades:
            if trade.time_bin not in time_bin_returns:
                time_bin_returns[trade.time_bin] = []
            time_bin_returns[trade.time_bin].append(trade.pnl or 0.0)
        
        # Calculate time-bin risk contributions
        time_bin_risk_contributions = {}
        total_variance = 0.0
        
        for time_bin, tb_returns in time_bin_returns.items():
            if len(tb_returns) > 1:
                tb_variance = statistics.variance(tb_returns)
                time_bin_risk_contributions[time_bin] = tb_variance
                total_variance += tb_variance
            else:
                time_bin_risk_contributions[time_bin] = 0.0
        
        # Normalize risk contributions
        if total_variance > 0:
            time_bin_risk_contributions = {
                tb: risk / total_variance 
                for tb, risk in time_bin_risk_contributions.items()
            }
        
        # Systematic vs idiosyncratic risk (simplified)
        # Systematic risk approximated as correlation-driven component
        systematic_risk = total_risk * 0.7  # Simplified assumption
        idiosyncratic_risk = total_risk * 0.3
        
        # VaR and CVaR calculations
        confidence_levels = [0.95, 0.99]
        value_at_risk = {}
        conditional_var = {}
        
        sorted_returns = sorted(returns)
        
        for confidence in confidence_levels:
            var_index = int((1 - confidence) * len(sorted_returns))
            var_value = sorted_returns[var_index] if var_index < len(sorted_returns) else 0.0
            value_at_risk[confidence] = var_value
            
            # CVaR (Expected Shortfall)
            tail_returns = sorted_returns[:var_index+1]
            cvar_value = statistics.mean(tail_returns) if tail_returns else 0.0
            conditional_var[confidence] = cvar_value
        
        # Maximum drawdown analysis
        running_max = 0.0
        running_sum = 0.0
        max_drawdown = 0.0
        drawdown_periods = []
        current_drawdown_start = None
        
        for i, ret in enumerate(returns):
            running_sum += ret
            if running_sum > running_max:
                running_max = running_sum
                if current_drawdown_start is not None:
                    # End of drawdown period
                    drawdown_periods.append({
                        'start_index': current_drawdown_start,
                        'end_index': i-1,
                        'magnitude': max_drawdown
                    })
                    current_drawdown_start = None
            else:
                if current_drawdown_start is None:
                    current_drawdown_start = i
                drawdown = (running_max - running_sum) / running_max if running_max > 0 else 0.0
                max_drawdown = max(max_drawdown, drawdown)
        
        maximum_drawdown_analysis = {
            'max_drawdown': max_drawdown,
            'num_drawdown_periods': len(drawdown_periods),
            'avg_drawdown_length': statistics.mean([
                p['end_index'] - p['start_index'] + 1 
                for p in drawdown_periods
            ]) if drawdown_periods else 0,
            'drawdown_periods': drawdown_periods
        }
        
        # Temporal risk contributions
        hourly_returns = {}
        for trade in all_trades:
            if trade.entry_time:
                hour = trade.entry_time.hour
                if hour not in hourly_returns:
                    hourly_returns[hour] = []
                hourly_returns[hour].append(trade.pnl or 0.0)
        
        temporal_risk_contributions = {}
        for hour, h_returns in hourly_returns.items():
            if len(h_returns) > 1:
                temporal_risk_contributions[f'hour_{hour}'] = statistics.stdev(h_returns)
            else:
                temporal_risk_contributions[f'hour_{hour}'] = 0.0
        
        # Risk concentration (Herfindahl index for time-bins)
        risk_weights = list(time_bin_risk_contributions.values())
        if risk_weights:
            risk_concentration = sum(w**2 for w in risk_weights)
        else:
            risk_concentration = 0.0
        
        return RiskDecomposition(
            total_risk=total_risk,
            systematic_risk=systematic_risk,
            idiosyncratic_risk=idiosyncratic_risk,
            time_bin_risk_contributions=time_bin_risk_contributions,
            temporal_risk_contributions=temporal_risk_contributions,
            value_at_risk=value_at_risk,
            conditional_var=conditional_var,
            maximum_drawdown_analysis=maximum_drawdown_analysis,
            risk_concentration=risk_concentration
        )
    
    async def analyze_trades(self, backtest_result: BacktestResult) -> TradeAnalysis:
        """Perform detailed trade analysis."""
        logger.debug("Analyzing trade patterns")
        
        # Collect all trades
        all_trades = []
        for period_result in backtest_result.period_results:
            all_trades.extend(period_result.trades)
        
        if not all_trades:
            all_trades = backtest_result.overall_result.trades
        
        if not all_trades:
            return TradeAnalysis(
                trade_statistics={},
                win_loss_analysis={},
                holding_period_analysis={},
                size_analysis={},
                timing_analysis={},
                entry_patterns={},
                exit_patterns={},
                seasonal_patterns={},
                trade_quality_score=0.0,
                execution_quality_score=0.0
            )
        
        # Basic trade statistics
        pnls = [trade.pnl or 0.0 for trade in all_trades]
        trade_statistics = {
            'total_trades': len(all_trades),
            'winning_trades': len([p for p in pnls if p > 0]),
            'losing_trades': len([p for p in pnls if p < 0]),
            'neutral_trades': len([p for p in pnls if p == 0]),
            'win_rate': len([p for p in pnls if p > 0]) / len(pnls) if pnls else 0.0,
            'avg_winner': statistics.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0.0,
            'avg_loser': statistics.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0.0,
            'largest_winner': max(pnls) if pnls else 0.0,
            'largest_loser': min(pnls) if pnls else 0.0,
            'avg_trade': statistics.mean(pnls) if pnls else 0.0
        }
        
        # Win/Loss analysis
        winning_streaks = []
        losing_streaks = []
        current_win_streak = 0
        current_loss_streak = 0
        
        for pnl in pnls:
            if pnl > 0:
                current_win_streak += 1
                if current_loss_streak > 0:
                    losing_streaks.append(current_loss_streak)
                    current_loss_streak = 0
            elif pnl < 0:
                current_loss_streak += 1
                if current_win_streak > 0:
                    winning_streaks.append(current_win_streak)
                    current_win_streak = 0
            # Neutral trades don't affect streaks
        
        # Add final streaks
        if current_win_streak > 0:
            winning_streaks.append(current_win_streak)
        if current_loss_streak > 0:
            losing_streaks.append(current_loss_streak)
        
        win_loss_analysis = {
            'max_winning_streak': max(winning_streaks) if winning_streaks else 0,
            'max_losing_streak': max(losing_streaks) if losing_streaks else 0,
            'avg_winning_streak': statistics.mean(winning_streaks) if winning_streaks else 0.0,
            'avg_losing_streak': statistics.mean(losing_streaks) if losing_streaks else 0.0,
            'profit_factor': abs(trade_statistics['avg_winner'] / trade_statistics['avg_loser']) if trade_statistics['avg_loser'] != 0 else float('inf')
        }
        
        # Holding period analysis
        holding_periods = []
        for trade in all_trades:
            if trade.entry_time and trade.exit_time:
                holding_period = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # hours
                holding_periods.append(holding_period)
        
        holding_period_analysis = {
            'avg_holding_period_hours': statistics.mean(holding_periods) if holding_periods else 0.0,
            'median_holding_period_hours': statistics.median(holding_periods) if holding_periods else 0.0,
            'min_holding_period_hours': min(holding_periods) if holding_periods else 0.0,
            'max_holding_period_hours': max(holding_periods) if holding_periods else 0.0,
            'holding_period_std': statistics.stdev(holding_periods) if len(holding_periods) > 1 else 0.0
        }
        
        # Position size analysis
        quantities = [trade.quantity for trade in all_trades]
        position_values = [trade.entry_price * trade.quantity for trade in all_trades]
        
        size_analysis = {
            'avg_quantity': statistics.mean(quantities) if quantities else 0.0,
            'avg_position_value': statistics.mean(position_values) if position_values else 0.0,
            'max_position_value': max(position_values) if position_values else 0.0,
            'min_position_value': min(position_values) if position_values else 0.0,
            'position_size_consistency': 1.0 - (statistics.stdev(position_values) / statistics.mean(position_values)) if position_values and statistics.mean(position_values) > 0 else 0.0
        }
        
        # Timing analysis
        entry_hours = [trade.entry_time.hour for trade in all_trades if trade.entry_time]
        exit_hours = [trade.exit_time.hour for trade in all_trades if trade.exit_time]
        
        timing_analysis = {
            'preferred_entry_hours': self._calculate_hour_distribution(entry_hours),
            'preferred_exit_hours': self._calculate_hour_distribution(exit_hours),
            'intraday_vs_overnight': self._analyze_intraday_vs_overnight(all_trades)
        }
        
        # Entry and exit patterns
        entry_patterns = self._analyze_entry_patterns(all_trades)
        exit_patterns = self._analyze_exit_patterns(all_trades)
        
        # Seasonal patterns
        seasonal_patterns = self._analyze_seasonal_patterns(all_trades)
        
        # Quality scores
        trade_quality_score = self._calculate_trade_quality_score(trade_statistics, win_loss_analysis)
        execution_quality_score = self._calculate_execution_quality_score(all_trades)
        
        return TradeAnalysis(
            trade_statistics=trade_statistics,
            win_loss_analysis=win_loss_analysis,
            holding_period_analysis=holding_period_analysis,
            size_analysis=size_analysis,
            timing_analysis=timing_analysis,
            entry_patterns=entry_patterns,
            exit_patterns=exit_patterns,
            seasonal_patterns=seasonal_patterns,
            trade_quality_score=trade_quality_score,
            execution_quality_score=execution_quality_score
        )
    
    async def analyze_temporal_patterns(
        self, 
        backtest_result: BacktestResult
    ) -> TemporalAnalysis:
        """Analyze temporal performance patterns."""
        logger.debug("Analyzing temporal patterns")
        
        # Collect daily performance data
        daily_performance = {}
        for period_result in backtest_result.period_results:
            # Group trades by date
            daily_trades = {}
            for trade in period_result.trades:
                if trade.entry_time:
                    trade_date = trade.entry_time.date()
                    if trade_date not in daily_trades:
                        daily_trades[trade_date] = []
                    daily_trades[trade_date].append(trade)
            
            # Calculate daily P&L
            for date, trades in daily_trades.items():
                daily_pnl = sum(trade.pnl or 0.0 for trade in trades)
                if date in daily_performance:
                    daily_performance[date] += daily_pnl
                else:
                    daily_performance[date] = daily_pnl
        
        # Weekly performance (by day of week)
        weekly_performance = {}
        for date, pnl in daily_performance.items():
            day_name = date.strftime('%A')
            if day_name not in weekly_performance:
                weekly_performance[day_name] = []
            weekly_performance[day_name].append(pnl)
        
        # Average weekly performance
        weekly_avg_performance = {
            day: statistics.mean(pnls) if pnls else 0.0
            for day, pnls in weekly_performance.items()
        }
        
        # Monthly performance
        monthly_performance = {}
        for date, pnl in daily_performance.items():
            month_key = f"{date.year}-{date.month:02d}"
            if month_key not in monthly_performance:
                monthly_performance[month_key] = 0.0
            monthly_performance[month_key] += pnl
        
        # Hourly performance
        hourly_performance = {}
        for period_result in backtest_result.period_results:
            for trade in period_result.trades:
                if trade.entry_time:
                    hour = trade.entry_time.hour
                    if hour not in hourly_performance:
                        hourly_performance[hour] = []
                    hourly_performance[hour].append(trade.pnl or 0.0)
        
        # Average hourly performance
        hourly_avg_performance = {
            hour: statistics.mean(pnls) if pnls else 0.0
            for hour, pnls in hourly_performance.items()
        }
        
        # Seasonality analysis
        seasonal_patterns = self._analyze_seasonality(daily_performance)
        
        # Calendar effects
        calendar_effects = self._analyze_calendar_effects(daily_performance)
        
        # Performance trends
        performance_trends = self._analyze_performance_trends(daily_performance)
        
        # Regime changes (simplified)
        regime_changes = self._detect_regime_changes(daily_performance)
        
        return TemporalAnalysis(
            daily_performance=daily_performance,
            weekly_performance=weekly_avg_performance,
            monthly_performance=monthly_performance,
            hourly_performance=hourly_avg_performance,
            seasonal_patterns=seasonal_patterns,
            calendar_effects=calendar_effects,
            performance_trends=performance_trends,
            regime_changes=regime_changes
        )
    
    async def validate_statistical_significance(
        self, 
        backtest_result: BacktestResult
    ) -> StatisticalValidation:
        """Validate statistical significance of backtesting results."""
        logger.debug("Validating statistical significance")
        
        # Collect returns data
        all_trades = []
        for period_result in backtest_result.period_results:
            all_trades.extend(period_result.trades)
        
        if not all_trades:
            all_trades = backtest_result.overall_result.trades
        
        returns = [trade.pnl or 0.0 for trade in all_trades]
        
        if len(returns) < 2:
            return StatisticalValidation(
                significance_tests={},
                distribution_analysis={},
                outlier_analysis={},
                autocorrelation_analysis={}
            )
        
        # Significance tests
        significance_tests = {}
        
        # T-test against zero (is performance significantly different from zero?)
        t_stat, p_value = stats.ttest_1samp(returns, 0.0)
        significance_tests['t_test_vs_zero'] = {
            't_statistic': t_stat,
            'p_value': p_value,
            'is_significant': p_value < 0.05
        }
        
        # Sharpe ratio significance test
        if len(returns) > 1:
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
            
            # Approximate Sharpe ratio confidence interval
            n = len(returns)
            sharpe_se = np.sqrt((1 + 0.5 * sharpe_ratio**2) / n)
            sharpe_ci_lower = sharpe_ratio - 1.96 * sharpe_se
            sharpe_ci_upper = sharpe_ratio + 1.96 * sharpe_se
            
            significance_tests['sharpe_ratio_test'] = {
                'sharpe_ratio': sharpe_ratio,
                'standard_error': sharpe_se,
                'confidence_interval_95': (sharpe_ci_lower, sharpe_ci_upper),
                'is_significantly_positive': sharpe_ci_lower > 0
            }
        
        # Distribution analysis
        distribution_analysis = {}
        
        # Normality test
        shapiro_stat, shapiro_p = stats.shapiro(returns[:5000])  # Shapiro-Wilk limited to 5000 samples
        distribution_analysis['normality_test'] = {
            'shapiro_wilk_statistic': shapiro_stat,
            'shapiro_wilk_p_value': shapiro_p,
            'is_normal': shapiro_p > 0.05
        }
        
        # Distribution moments
        distribution_analysis['moments'] = {
            'mean': statistics.mean(returns),
            'variance': statistics.variance(returns),
            'skewness': stats.skew(returns),
            'kurtosis': stats.kurtosis(returns),
            'excess_kurtosis': stats.kurtosis(returns) - 3  # Normal distribution has kurtosis of 3
        }
        
        # Outlier analysis
        outlier_analysis = self._analyze_outliers(returns)
        
        # Autocorrelation analysis
        autocorrelation_analysis = self._analyze_autocorrelation(returns)
        
        # Overfitting tests (simplified)
        overfitting_tests = {
            'sample_size_adequacy': len(returns) >= 30,
            'degrees_of_freedom': len(returns) - 2,  # Simplified
            'overfitting_risk': 'LOW' if len(returns) >= 100 else 'MEDIUM' if len(returns) >= 30 else 'HIGH'
        }
        
        # Stability tests
        stability_tests = self._analyze_stability(returns)
        
        return StatisticalValidation(
            significance_tests=significance_tests,
            distribution_analysis=distribution_analysis,
            outlier_analysis=outlier_analysis,
            autocorrelation_analysis=autocorrelation_analysis,
            overfitting_tests=overfitting_tests,
            stability_tests=stability_tests
        )
    
    async def analyze_comparative_performance(
        self,
        primary_result: BacktestResult,
        benchmark_results: List[BacktestResult]
    ) -> ComparativeAnalysis:
        """Compare performance against benchmarks and other strategies."""
        logger.debug(f"Analyzing comparative performance against {len(benchmark_results)} benchmarks")
        
        # Extract performance metrics for comparison
        primary_metrics = self._extract_performance_metrics(primary_result)
        
        strategy_comparisons = {}
        benchmark_comparisons = {}
        
        for i, benchmark_result in enumerate(benchmark_results):
            benchmark_metrics = self._extract_performance_metrics(benchmark_result)
            comparison_key = f"benchmark_{i}"
            
            # Calculate relative performance
            relative_performance = {}
            for metric, value in primary_metrics.items():
                benchmark_value = benchmark_metrics.get(metric, 0.0)
                if benchmark_value != 0:
                    relative_performance[metric] = (value - benchmark_value) / abs(benchmark_value)
                else:
                    relative_performance[metric] = value
            
            benchmark_comparisons[comparison_key] = {
                'primary_metrics': primary_metrics,
                'benchmark_metrics': benchmark_metrics,
                'relative_performance': relative_performance
            }
        
        # Performance rankings
        all_results = [primary_result] + benchmark_results
        
        # Rank by total return
        returns = [(i, result.overall_result.total_return) for i, result in enumerate(all_results)]
        performance_rankings = sorted(returns, key=lambda x: x[1], reverse=True)
        
        # Rank by risk-adjusted return (Sharpe ratio)
        sharpe_ratios = []
        for i, result in enumerate(all_results):
            sharpe = result.overall_result.sharpe_ratio
            if sharpe is not None:
                sharpe_ratios.append((i, sharpe))
            else:
                sharpe_ratios.append((i, 0.0))
        
        risk_adjusted_rankings = sorted(sharpe_ratios, key=lambda x: x[1], reverse=True)
        
        # Statistical significance tests
        significance_tests = {}
        
        primary_returns = [t.pnl or 0.0 for period in primary_result.period_results for t in period.trades]
        if not primary_returns:
            primary_returns = [t.pnl or 0.0 for t in primary_result.overall_result.trades]
        
        for i, benchmark_result in enumerate(benchmark_results):
            benchmark_returns = [t.pnl or 0.0 for period in benchmark_result.period_results for t in period.trades]
            if not benchmark_returns:
                benchmark_returns = [t.pnl or 0.0 for t in benchmark_result.overall_result.trades]
            
            if len(primary_returns) > 1 and len(benchmark_returns) > 1:
                # Two-sample t-test
                t_stat, p_value = stats.ttest_ind(primary_returns, benchmark_returns)
                significance_tests[f"vs_benchmark_{i}"] = {
                    't_statistic': t_stat,
                    'p_value': p_value,
                    'is_significantly_different': p_value < 0.05,
                    'primary_better': t_stat > 0
                }
        
        # Peer analysis (simplified)
        peer_analysis = {
            'percentile_rank_return': self._calculate_percentile_rank(
                primary_result.overall_result.total_return,
                [r.overall_result.total_return for r in benchmark_results]
            ),
            'percentile_rank_sharpe': self._calculate_percentile_rank(
                primary_result.overall_result.sharpe_ratio or 0.0,
                [r.overall_result.sharpe_ratio or 0.0 for r in benchmark_results]
            )
        }
        
        return ComparativeAnalysis(
            strategy_comparisons=strategy_comparisons,
            benchmark_comparisons=benchmark_comparisons,
            peer_analysis=peer_analysis,
            performance_rankings=performance_rankings,
            risk_adjusted_rankings=risk_adjusted_rankings,
            significance_tests=significance_tests
        )
    
    async def analyze_sensitivity(
        self, 
        backtest_result: BacktestResult
    ) -> SensitivityAnalysis:
        """Analyze sensitivity to parameters and market conditions."""
        logger.debug("Analyzing parameter sensitivity")
        
        # This would typically require running multiple backtests with different parameters
        # For now, we'll analyze the robustness of the current results
        
        # Collect performance data
        returns = []
        for period_result in backtest_result.period_results:
            returns.extend([t.pnl or 0.0 for t in period_result.trades])
        
        if not returns:
            returns = [t.pnl or 0.0 for t in backtest_result.overall_result.trades]
        
        # Parameter stability analysis (simplified)
        parameter_stability = {
            'return_stability': self._calculate_return_stability(returns),
            'performance_consistency': self._calculate_performance_consistency(backtest_result),
            'regime_sensitivity': self._calculate_regime_sensitivity(returns)
        }
        
        # Stress test results (simplified scenarios)
        stress_test_results = {
            'high_volatility_impact': self._estimate_high_volatility_impact(returns),
            'market_crash_scenario': self._estimate_market_crash_impact(returns),
            'low_liquidity_impact': self._estimate_low_liquidity_impact(backtest_result)
        }
        
        # Scenario analysis
        scenario_analysis = {
            'best_case_scenario': max(returns) if returns else 0.0,
            'worst_case_scenario': min(returns) if returns else 0.0,
            'median_scenario': statistics.median(returns) if returns else 0.0,
            'tail_risk_scenarios': self._analyze_tail_risk_scenarios(returns)
        }
        
        # Overall robustness score
        robustness_score = self._calculate_robustness_score(
            parameter_stability, stress_test_results, scenario_analysis
        )
        
        return SensitivityAnalysis(
            parameter_sensitivity={},  # Would be populated with actual parameter sweeps
            stress_test_results=stress_test_results,
            scenario_analysis=scenario_analysis,
            parameter_stability=parameter_stability,
            robustness_score=robustness_score
        )
    
    # Helper methods
    def _calculate_hour_distribution(self, hours: List[int]) -> Dict[int, float]:
        """Calculate distribution of trades by hour."""
        if not hours:
            return {}
        
        hour_counts = {}
        for hour in hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        total_count = len(hours)
        return {hour: count / total_count for hour, count in hour_counts.items()}
    
    def _analyze_intraday_vs_overnight(self, trades: List[BacktestTrade]) -> Dict[str, Any]:
        """Analyze intraday vs overnight trade performance."""
        intraday_pnl = []
        overnight_pnl = []
        
        for trade in trades:
            if trade.entry_time and trade.exit_time:
                if trade.entry_time.date() == trade.exit_time.date():
                    intraday_pnl.append(trade.pnl or 0.0)
                else:
                    overnight_pnl.append(trade.pnl or 0.0)
        
        return {
            'intraday_avg_pnl': statistics.mean(intraday_pnl) if intraday_pnl else 0.0,
            'overnight_avg_pnl': statistics.mean(overnight_pnl) if overnight_pnl else 0.0,
            'intraday_trade_count': len(intraday_pnl),
            'overnight_trade_count': len(overnight_pnl),
            'intraday_win_rate': len([p for p in intraday_pnl if p > 0]) / len(intraday_pnl) if intraday_pnl else 0.0,
            'overnight_win_rate': len([p for p in overnight_pnl if p > 0]) / len(overnight_pnl) if overnight_pnl else 0.0
        }
    
    def _analyze_entry_patterns(self, trades: List[BacktestTrade]) -> Dict[str, Any]:
        """Analyze entry timing patterns."""
        # Simplified entry pattern analysis
        entry_hours = [t.entry_time.hour for t in trades if t.entry_time]
        
        return {
            'preferred_entry_times': self._calculate_hour_distribution(entry_hours),
            'early_session_entries': len([h for h in entry_hours if 9 <= h <= 11]),
            'mid_session_entries': len([h for h in entry_hours if 12 <= h <= 14]),
            'late_session_entries': len([h for h in entry_hours if 15 <= h <= 16])
        }
    
    def _analyze_exit_patterns(self, trades: List[BacktestTrade]) -> Dict[str, Any]:
        """Analyze exit timing patterns."""
        # Simplified exit pattern analysis
        exit_hours = [t.exit_time.hour for t in trades if t.exit_time]
        
        return {
            'preferred_exit_times': self._calculate_hour_distribution(exit_hours),
            'early_session_exits': len([h for h in exit_hours if 9 <= h <= 11]),
            'mid_session_exits': len([h for h in exit_hours if 12 <= h <= 14]),
            'late_session_exits': len([h for h in exit_hours if 15 <= h <= 16])
        }
    
    def _analyze_seasonal_patterns(self, trades: List[BacktestTrade]) -> Dict[str, Any]:
        """Analyze seasonal trading patterns."""
        monthly_pnl = {}
        quarterly_pnl = {}
        
        for trade in trades:
            if trade.entry_time and trade.pnl is not None:
                month = trade.entry_time.month
                quarter = (month - 1) // 3 + 1
                
                if month not in monthly_pnl:
                    monthly_pnl[month] = []
                monthly_pnl[month].append(trade.pnl)
                
                if quarter not in quarterly_pnl:
                    quarterly_pnl[quarter] = []
                quarterly_pnl[quarter].append(trade.pnl)
        
        return {
            'monthly_performance': {
                month: statistics.mean(pnls) if pnls else 0.0
                for month, pnls in monthly_pnl.items()
            },
            'quarterly_performance': {
                quarter: statistics.mean(pnls) if pnls else 0.0
                for quarter, pnls in quarterly_pnl.items()
            }
        }
    
    def _calculate_trade_quality_score(
        self, 
        trade_stats: Dict[str, Any], 
        win_loss_analysis: Dict[str, Any]
    ) -> float:
        """Calculate overall trade quality score."""
        # Composite score based on multiple factors
        win_rate_score = min(trade_stats['win_rate'] / 0.6, 1.0)  # Target 60% win rate
        profit_factor_score = min(win_loss_analysis.get('profit_factor', 0) / 2.0, 1.0)  # Target 2.0 profit factor
        consistency_score = 1.0 - min(win_loss_analysis.get('max_losing_streak', 0) / 5.0, 1.0)  # Penalize long losing streaks
        
        return (win_rate_score + profit_factor_score + consistency_score) / 3.0
    
    def _calculate_execution_quality_score(self, trades: List[BacktestTrade]) -> float:
        """Calculate execution quality score based on costs and slippage."""
        if not trades:
            return 0.0
        
        # Analyze commission and slippage as percentage of trade value
        total_costs = sum(t.commission + t.slippage for t in trades)
        total_value = sum(t.entry_price * t.quantity for t in trades)
        
        if total_value == 0:
            return 0.0
        
        cost_ratio = total_costs / total_value
        
        # Lower cost ratio = higher execution quality
        # Assume good execution has costs < 0.1% of trade value
        execution_score = max(0.0, 1.0 - cost_ratio / 0.001)
        
        return min(execution_score, 1.0)
    
    def _analyze_seasonality(self, daily_performance: Dict[date, float]) -> Dict[str, Any]:
        """Analyze seasonal performance patterns."""
        monthly_returns = {}
        quarterly_returns = {}
        
        for date, pnl in daily_performance.items():
            month = date.month
            quarter = (month - 1) // 3 + 1
            
            if month not in monthly_returns:
                monthly_returns[month] = []
            monthly_returns[month].append(pnl)
            
            if quarter not in quarterly_returns:
                quarterly_returns[quarter] = []
            quarterly_returns[quarter].append(pnl)
        
        return {
            'monthly_seasonality': {
                month: {
                    'avg_return': statistics.mean(returns),
                    'volatility': statistics.stdev(returns) if len(returns) > 1 else 0.0,
                    'trade_days': len(returns)
                }
                for month, returns in monthly_returns.items()
            },
            'quarterly_seasonality': {
                quarter: {
                    'avg_return': statistics.mean(returns),
                    'volatility': statistics.stdev(returns) if len(returns) > 1 else 0.0,
                    'trade_days': len(returns)
                }
                for quarter, returns in quarterly_returns.items()
            }
        }
    
    def _analyze_calendar_effects(self, daily_performance: Dict[date, float]) -> Dict[str, Any]:
        """Analyze calendar effects on performance."""
        day_of_week_returns = {}
        month_end_returns = []
        month_start_returns = []
        
        for date, pnl in daily_performance.items():
            # Day of week effect
            day_name = date.strftime('%A')
            if day_name not in day_of_week_returns:
                day_of_week_returns[day_name] = []
            day_of_week_returns[day_name].append(pnl)
            
            # Month-end/start effects
            if date.day <= 3:  # First 3 days of month
                month_start_returns.append(pnl)
            elif date.day >= 28:  # Last few days of month
                month_end_returns.append(pnl)
        
        return {
            'day_of_week_effects': {
                day: statistics.mean(returns) if returns else 0.0
                for day, returns in day_of_week_returns.items()
            },
            'month_end_effect': statistics.mean(month_end_returns) if month_end_returns else 0.0,
            'month_start_effect': statistics.mean(month_start_returns) if month_start_returns else 0.0
        }
    
    def _analyze_performance_trends(self, daily_performance: Dict[date, float]) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        if len(daily_performance) < 10:
            return {}
        
        # Sort by date
        sorted_performance = sorted(daily_performance.items())
        returns = [pnl for _, pnl in sorted_performance]
        
        # Calculate rolling averages
        window = min(20, len(returns) // 4)  # 20-day or quarter of data
        rolling_avg = []
        
        for i in range(window, len(returns)):
            avg = statistics.mean(returns[i-window:i])
            rolling_avg.append(avg)
        
        # Simple trend analysis
        if len(rolling_avg) >= 2:
            trend_slope = (rolling_avg[-1] - rolling_avg[0]) / len(rolling_avg)
            is_trending_up = trend_slope > 0
        else:
            trend_slope = 0.0
            is_trending_up = False
        
        return {
            'trend_slope': trend_slope,
            'is_trending_up': is_trending_up,
            'recent_performance': statistics.mean(returns[-10:]) if len(returns) >= 10 else 0.0,
            'early_performance': statistics.mean(returns[:10]) if len(returns) >= 10 else 0.0
        }
    
    def _detect_regime_changes(self, daily_performance: Dict[date, float]) -> List[Dict[str, Any]]:
        """Detect potential regime changes in performance."""
        # Simplified regime change detection
        if len(daily_performance) < 20:
            return []
        
        sorted_performance = sorted(daily_performance.items())
        returns = [pnl for _, pnl in sorted_performance]
        
        # Look for significant changes in volatility
        window = 10
        regime_changes = []
        
        for i in range(window, len(returns) - window):
            before_vol = statistics.stdev(returns[i-window:i]) if len(returns[i-window:i]) > 1 else 0.0
            after_vol = statistics.stdev(returns[i:i+window]) if len(returns[i:i+window]) > 1 else 0.0
            
            if before_vol > 0 and after_vol / before_vol > 2.0:  # Volatility doubled
                regime_changes.append({
                    'date': sorted_performance[i][0],
                    'type': 'volatility_increase',
                    'magnitude': after_vol / before_vol
                })
            elif after_vol > 0 and before_vol / after_vol > 2.0:  # Volatility halved
                regime_changes.append({
                    'date': sorted_performance[i][0],
                    'type': 'volatility_decrease',
                    'magnitude': before_vol / after_vol
                })
        
        return regime_changes
    
    def _analyze_outliers(self, returns: List[float]) -> Dict[str, Any]:
        """Analyze outliers in returns."""
        if len(returns) < 4:
            return {'num_outliers': 0, 'outlier_threshold': 0.0}
        
        # Use IQR method to detect outliers
        q1 = np.percentile(returns, 25)
        q3 = np.percentile(returns, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = [r for r in returns if r < lower_bound or r > upper_bound]
        
        return {
            'num_outliers': len(outliers),
            'outlier_percentage': len(outliers) / len(returns) * 100,
            'outlier_threshold': 1.5 * iqr,
            'extreme_outliers': [r for r in outliers if r < q1 - 3 * iqr or r > q3 + 3 * iqr],
            'largest_positive_outlier': max([r for r in outliers if r > upper_bound], default=0.0),
            'largest_negative_outlier': min([r for r in outliers if r < lower_bound], default=0.0)
        }
    
    def _analyze_autocorrelation(self, returns: List[float]) -> Dict[str, Any]:
        """Analyze autocorrelation in returns."""
        if len(returns) < 10:
            return {'lag_1_correlation': 0.0}
        
        # Calculate lag-1 autocorrelation
        lag_1_corr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        
        # Test for significance
        n = len(returns)
        se = 1.0 / np.sqrt(n)  # Standard error for white noise
        is_significant = abs(lag_1_corr) > 1.96 * se
        
        return {
            'lag_1_correlation': lag_1_corr,
            'is_significant': is_significant,
            'standard_error': se,
            'interpretation': 'momentum' if lag_1_corr > 0.1 else 'mean_reversion' if lag_1_corr < -0.1 else 'random_walk'
        }
    
    def _analyze_stability(self, returns: List[float]) -> Dict[str, Any]:
        """Analyze stability of returns over time."""
        if len(returns) < 20:
            return {'stability_score': 0.0}
        
        # Split returns into halves and compare
        mid_point = len(returns) // 2
        first_half = returns[:mid_point]
        second_half = returns[mid_point:]
        
        first_mean = statistics.mean(first_half)
        second_mean = statistics.mean(second_half)
        first_std = statistics.stdev(first_half) if len(first_half) > 1 else 0.0
        second_std = statistics.stdev(second_half) if len(second_half) > 1 else 0.0
        
        # Stability metrics
        mean_stability = 1.0 - abs(first_mean - second_mean) / (abs(first_mean) + abs(second_mean) + 1e-8)
        vol_stability = 1.0 - abs(first_std - second_std) / (first_std + second_std + 1e-8)
        
        stability_score = (mean_stability + vol_stability) / 2.0
        
        return {
            'stability_score': max(0.0, min(1.0, stability_score)),
            'mean_drift': second_mean - first_mean,
            'volatility_change': second_std - first_std,
            'is_stable': stability_score > 0.7
        }
    
    def _extract_performance_metrics(self, result: BacktestResult) -> Dict[str, float]:
        """Extract key performance metrics from backtest result."""
        overall = result.overall_result
        
        return {
            'total_return': overall.total_return,
            'sharpe_ratio': overall.sharpe_ratio or 0.0,
            'max_drawdown': overall.max_drawdown,
            'win_rate': overall.win_rate,
            'profit_factor': overall.profit_factor or 0.0,
            'avg_trade_pnl': overall.avg_trade_pnl,
            'num_trades': float(overall.num_trades),
            'sortino_ratio': overall.sortino_ratio or 0.0
        }
    
    def _calculate_percentile_rank(self, value: float, benchmark_values: List[float]) -> float:
        """Calculate percentile rank of value among benchmarks."""
        if not benchmark_values:
            return 50.0  # Default to median
        
        values_below = len([v for v in benchmark_values if v < value])
        return (values_below / len(benchmark_values)) * 100
    
    def _calculate_return_stability(self, returns: List[float]) -> float:
        """Calculate return stability metric."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if abs(mean_return) < 1e-8:
            return 0.0
        
        # Coefficient of variation (inverse stability)
        cv = std_return / abs(mean_return)
        stability = 1.0 / (1.0 + cv)  # Normalize to 0-1
        
        return min(1.0, max(0.0, stability))
    
    def _calculate_performance_consistency(self, result: BacktestResult) -> float:
        """Calculate performance consistency across periods."""
        if len(result.period_results) < 2:
            return 1.0  # Single period is perfectly consistent
        
        period_returns = [p.total_return for p in result.period_results]
        
        if len(period_returns) < 2:
            return 1.0
        
        mean_return = statistics.mean(period_returns)
        std_return = statistics.stdev(period_returns)
        
        if abs(mean_return) < 1e-8:
            return 0.0
        
        # Consistency as inverse of relative volatility
        consistency = 1.0 / (1.0 + std_return / abs(mean_return))
        
        return min(1.0, max(0.0, consistency))
    
    def _calculate_regime_sensitivity(self, returns: List[float]) -> float:
        """Calculate sensitivity to market regime changes."""
        # Simplified regime sensitivity based on return autocorrelation
        if len(returns) < 10:
            return 0.5  # Default moderate sensitivity
        
        # High autocorrelation suggests regime sensitivity
        lag_1_corr = abs(np.corrcoef(returns[:-1], returns[1:])[0, 1])
        sensitivity = min(1.0, lag_1_corr * 2.0)  # Scale to 0-1
        
        return sensitivity
    
    def _estimate_high_volatility_impact(self, returns: List[float]) -> float:
        """Estimate impact of high volatility regime."""
        if not returns:
            return 0.0
        
        # Find high volatility periods (returns > 2 std devs)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0
        threshold = 2.0 * std_return
        
        high_vol_returns = [r for r in returns if abs(r) > threshold]
        
        if not high_vol_returns:
            return 0.0  # No impact if no high volatility periods
        
        # Average performance during high volatility
        avg_high_vol_return = statistics.mean(high_vol_returns)
        avg_normal_return = statistics.mean([r for r in returns if abs(r) <= threshold])
        
        # Impact as relative performance difference
        if abs(avg_normal_return) > 1e-8:
            impact = (avg_high_vol_return - avg_normal_return) / abs(avg_normal_return)
        else:
            impact = avg_high_vol_return
        
        return impact
    
    def _estimate_market_crash_impact(self, returns: List[float]) -> float:
        """Estimate impact of market crash scenario."""
        if not returns:
            return 0.0
        
        # Simulate crash as worst 5% of returns
        sorted_returns = sorted(returns)
        crash_threshold_idx = max(1, int(len(sorted_returns) * 0.05))
        crash_returns = sorted_returns[:crash_threshold_idx]
        
        if not crash_returns:
            return min(returns) if returns else 0.0
        
        return statistics.mean(crash_returns)
    
    def _estimate_low_liquidity_impact(self, result: BacktestResult) -> float:
        """Estimate impact of low liquidity conditions."""
        # Simplified estimate based on slippage costs
        all_trades = []
        for period_result in result.period_results:
            all_trades.extend(period_result.trades)
        
        if not all_trades:
            all_trades = result.overall_result.trades
        
        if not all_trades:
            return 0.0
        
        # Average slippage as proxy for liquidity impact
        total_slippage = sum(t.slippage for t in all_trades)
        total_value = sum(t.entry_price * t.quantity for t in all_trades)
        
        if total_value == 0:
            return 0.0
        
        # Liquidity impact as percentage of trade value
        liquidity_impact = total_slippage / total_value
        
        # Estimate low liquidity scenario (2x normal slippage)
        return liquidity_impact * 2.0
    
    def _analyze_tail_risk_scenarios(self, returns: List[float]) -> Dict[str, float]:
        """Analyze tail risk scenarios."""
        if not returns:
            return {}
        
        sorted_returns = sorted(returns)
        n = len(sorted_returns)
        
        return {
            'worst_1_percent': statistics.mean(sorted_returns[:max(1, n//100)]),
            'worst_5_percent': statistics.mean(sorted_returns[:max(1, n//20)]),
            'worst_10_percent': statistics.mean(sorted_returns[:max(1, n//10)]),
            'best_1_percent': statistics.mean(sorted_returns[-max(1, n//100):]),
            'best_5_percent': statistics.mean(sorted_returns[-max(1, n//20):]),
            'best_10_percent': statistics.mean(sorted_returns[-max(1, n//10):])
        }
    
    def _calculate_robustness_score(
        self,
        parameter_stability: Dict[str, float],
        stress_test_results: Dict[str, Any],
        scenario_analysis: Dict[str, Any]
    ) -> float:
        """Calculate overall robustness score."""
        # Combine various robustness metrics
        stability_score = statistics.mean(parameter_stability.values()) if parameter_stability else 0.0
        
        # Stress test resilience (higher is better for negative scenarios)
        stress_resilience = 0.5  # Default moderate resilience
        
        # Scenario range (smaller range indicates more robustness)
        if 'best_case_scenario' in scenario_analysis and 'worst_case_scenario' in scenario_analysis:
            scenario_range = abs(scenario_analysis['best_case_scenario'] - scenario_analysis['worst_case_scenario'])
            median_scenario = abs(scenario_analysis.get('median_scenario', 0.0))
            
            if median_scenario > 0:
                range_score = 1.0 / (1.0 + scenario_range / median_scenario)
            else:
                range_score = 0.5
        else:
            range_score = 0.5
        
        # Combine scores
        robustness_score = (stability_score + stress_resilience + range_score) / 3.0
        
        return min(1.0, max(0.0, robustness_score))
    
    def _calculate_overall_quality_score(self, analysis: ComprehensiveAnalysis) -> float:
        """Calculate overall quality score for the strategy."""
        scores = []
        
        # Performance quality
        if analysis.performance_attribution:
            scores.append(analysis.performance_attribution.consistency_score)
            scores.append(analysis.performance_attribution.reliability_score)
        
        # Trade quality
        if analysis.trade_analysis:
            scores.append(analysis.trade_analysis.trade_quality_score)
            scores.append(analysis.trade_analysis.execution_quality_score)
        
        # Statistical validity
        if analysis.statistical_validation:
            significance_tests = analysis.statistical_validation.significance_tests
            if 't_test_vs_zero' in significance_tests:
                scores.append(1.0 if significance_tests['t_test_vs_zero']['is_significant'] else 0.5)
        
        # Robustness
        if analysis.sensitivity_analysis:
            scores.append(analysis.sensitivity_analysis.robustness_score)
        
        return statistics.mean(scores) if scores else 0.5
    
    def _generate_recommendation(self, analysis: ComprehensiveAnalysis) -> str:
        """Generate recommendation based on analysis."""
        score = analysis.overall_quality_score
        
        if score >= 0.8:
            return "STRONG_BUY: Strategy shows excellent performance with high statistical significance and robustness."
        elif score >= 0.7:
            return "BUY: Strategy demonstrates good performance with acceptable risk characteristics."
        elif score >= 0.6:
            return "HOLD: Strategy shows moderate performance. Consider optimization or additional validation."
        elif score >= 0.4:
            return "WEAK_HOLD: Strategy has mixed results. Significant improvements needed."
        else:
            return "SELL: Strategy shows poor performance and high risk. Not recommended for live trading."
    
    def _extract_key_insights(self, analysis: ComprehensiveAnalysis) -> List[str]:
        """Extract key insights from comprehensive analysis."""
        insights = []
        
        # Performance insights
        if analysis.performance_attribution:
            pa = analysis.performance_attribution
            if pa.best_time_bins:
                best_tb = pa.best_time_bins[0]
                insights.append(f"Best performing time-bin: {best_tb[0]} with {best_tb[1]:.2%} contribution")
            
            if pa.consistency_score > 0.8:
                insights.append("Strategy shows high performance consistency across time-bins")
            elif pa.consistency_score < 0.4:
                insights.append("Strategy performance is highly variable across time-bins")
        
        # Risk insights
        if analysis.risk_decomposition:
            rd = analysis.risk_decomposition
            if rd.risk_concentration > 0.7:
                insights.append("High risk concentration detected - consider diversification")
            
            if rd.maximum_drawdown_analysis.get('max_drawdown', 0) > 0.2:
                insights.append("Strategy experiences significant drawdowns - implement risk controls")
        
        # Trade insights
        if analysis.trade_analysis:
            ta = analysis.trade_analysis
            stats = ta.trade_statistics
            
            if stats.get('win_rate', 0) > 0.7:
                insights.append("High win rate indicates good signal quality")
            elif stats.get('win_rate', 0) < 0.4:
                insights.append("Low win rate suggests signal quality issues")
            
            profit_factor = ta.win_loss_analysis.get('profit_factor', 0)
            if profit_factor > 2.0:
                insights.append("Excellent profit factor indicates strong risk-reward balance")
        
        # Statistical insights
        if analysis.statistical_validation:
            sv = analysis.statistical_validation
            if 't_test_vs_zero' in sv.significance_tests:
                if sv.significance_tests['t_test_vs_zero']['is_significant']:
                    insights.append("Strategy performance is statistically significant")
                else:
                    insights.append("Strategy performance lacks statistical significance")
        
        return insights[:5]  # Return top 5 insights