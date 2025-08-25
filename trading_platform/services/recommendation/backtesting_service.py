"""
Backtesting service for recommendation validation and strategy comparison.

This service implements comprehensive backtesting framework for recommendation
accuracy across different strategies with performance tracking and comparison.

Requirements: 6.1, 6.3
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from scipy import stats

from ...models.trading import ProcessedTrade, TradingRecommendation, PerformanceMetrics
from .recommendation_service import StrategyType, StrategyResult, RecommendationContext, RecommendationService


@dataclass
class BacktestResult:
    """Result from backtesting a single strategy."""
    strategy_type: StrategyType
    total_recommendations: int
    correct_predictions: int
    accuracy: float
    total_return: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    volatility: float
    avg_trade_return: float
    best_trade: float
    worst_trade: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_winning_trade: float
    avg_losing_trade: float
    execution_time: float
    confidence_intervals: Dict[str, Tuple[float, float]]
    statistical_significance: Dict[str, float]


@dataclass
class StrategyComparisonResult:
    """Result from comparing two strategies."""
    strategy_a: StrategyType
    strategy_b: StrategyType
    strategy_a_performance: BacktestResult
    strategy_b_performance: BacktestResult
    
    # Comparison metrics
    accuracy_difference: float
    return_difference: float
    risk_difference: float
    sharpe_difference: float
    
    # Statistical tests
    t_test_pvalue: float
    wilcoxon_pvalue: float
    chi_square_pvalue: float
    
    # Preference scoring
    preference_score: float  # Positive favors strategy_a, negative favors strategy_b
    statistical_significance: str  # 'significant', 'not_significant', 'inconclusive'
    
    sample_size: int
    comparison_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BacktestConfiguration:
    """Configuration for backtesting."""
    start_date: datetime
    end_date: datetime
    walk_forward_window: int = 30  # Days
    min_trades_required: int = 10
    confidence_level: float = 0.95
    enable_walk_forward: bool = True
    strategies_to_test: List[StrategyType] = field(default_factory=lambda: [
        StrategyType.STATISTICAL, StrategyType.MACHINE_LEARNING, StrategyType.MONTE_CARLO
    ])
    parallel_execution: bool = True
    detailed_logging: bool = True


@dataclass
class ConfidenceScoring:
    """Confidence scoring based on historical accuracy."""
    strategy_type: StrategyType
    base_confidence: float
    historical_accuracy: float
    recent_accuracy: float  # Last 30 days
    confidence_adjustment: float
    final_confidence: float
    sample_size: int
    last_updated: datetime = field(default_factory=datetime.now)


class BacktestingService:
    """
    Comprehensive backtesting service for recommendation validation.
    
    This service provides backtesting framework for recommendation accuracy
    across different strategies with performance tracking, comparison, and
    confidence scoring based on historical accuracy.
    """
    
    def __init__(self, 
                 recommendation_service: Optional[RecommendationService] = None,
                 enable_caching: bool = True,
                 cache_duration_hours: int = 24):
        """
        Initialize the backtesting service.
        
        Args:
            recommendation_service: Recommendation service for generating predictions
            enable_caching: Enable caching of backtest results
            cache_duration_hours: Cache duration in hours
        """
        self.logger = logging.getLogger(__name__)
        self.recommendation_service = recommendation_service or RecommendationService()
        
        # Caching configuration
        self.enable_caching = enable_caching
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.backtest_cache: Dict[str, Tuple[datetime, Any]] = {}
        
        # Historical performance tracking
        self.strategy_performance_history: Dict[StrategyType, List[BacktestResult]] = {
            strategy: [] for strategy in StrategyType
        }
        
        # Confidence scoring
        self.confidence_scores: Dict[StrategyType, ConfidenceScoring] = {}
        
        # Strategy switching logic
        self.strategy_switching_enabled = True
        self.switching_threshold = 0.1  # 10% performance difference
        self.current_best_strategy = StrategyType.ENSEMBLE
    
    def run_backtest(self, 
                     config: BacktestConfiguration,
                     historical_trades: List[ProcessedTrade]) -> Dict[StrategyType, BacktestResult]:
        """
        Run comprehensive backtesting across all strategies.
        
        Args:
            config: Backtesting configuration
            historical_trades: Historical trade data for backtesting
            
        Returns:
            Dictionary mapping strategy types to backtest results
        """
        if not historical_trades:
            raise ValueError("No historical trades provided for backtesting")
        
        self.logger.info(f"Starting backtest from {config.start_date} to {config.end_date}")
        
        # Filter trades by date range
        filtered_trades = [
            trade for trade in historical_trades
            if config.start_date <= trade.entry_time <= config.end_date
        ]
        
        if len(filtered_trades) < config.min_trades_required:
            raise ValueError(f"Insufficient trades ({len(filtered_trades)}) for backtesting")
        
        # Run backtesting for each strategy
        backtest_results = {}
        
        if config.parallel_execution:
            backtest_results = self._run_backtest_parallel(config, filtered_trades)
        else:
            backtest_results = self._run_backtest_sequential(config, filtered_trades)
        
        # Update historical performance tracking
        for strategy_type, result in backtest_results.items():
            self.strategy_performance_history[strategy_type].append(result)
        
        # Update confidence scores
        self._update_confidence_scores(backtest_results)
        
        return backtest_results
    
    def _run_backtest_parallel(self, 
                              config: BacktestConfiguration,
                              trades: List[ProcessedTrade]) -> Dict[StrategyType, BacktestResult]:
        """Run backtesting in parallel for better performance."""
        backtest_results = {}
        
        with ThreadPoolExecutor(max_workers=len(config.strategies_to_test)) as executor:
            # Submit backtest tasks for each strategy
            future_to_strategy = {
                executor.submit(self._backtest_single_strategy, strategy, config, trades): strategy
                for strategy in config.strategies_to_test
            }
            
            # Collect results
            for future in as_completed(future_to_strategy):
                strategy_type = future_to_strategy[future]
                try:
                    result = future.result()
                    backtest_results[strategy_type] = result
                except Exception as e:
                    self.logger.error(f"Backtest failed for strategy {strategy_type.value}: {e}")
                    # Create fallback result
                    backtest_results[strategy_type] = self._create_fallback_result(strategy_type, str(e))
        
        return backtest_results
    
    def _run_backtest_sequential(self, 
                                config: BacktestConfiguration,
                                trades: List[ProcessedTrade]) -> Dict[StrategyType, BacktestResult]:
        """Run backtesting sequentially."""
        backtest_results = {}
        
        for strategy_type in config.strategies_to_test:
            try:
                result = self._backtest_single_strategy(strategy_type, config, trades)
                backtest_results[strategy_type] = result
            except Exception as e:
                self.logger.error(f"Backtest failed for strategy {strategy_type.value}: {e}")
                backtest_results[strategy_type] = self._create_fallback_result(strategy_type, str(e))
        
        return backtest_results
    
    def _backtest_single_strategy(self, 
                                 strategy_type: StrategyType,
                                 config: BacktestConfiguration,
                                 trades: List[ProcessedTrade]) -> BacktestResult:
        """
        Backtest a single strategy against historical data.
        
        Args:
            strategy_type: Strategy to backtest
            config: Backtesting configuration
            trades: Historical trades for backtesting
            
        Returns:
            BacktestResult with performance metrics
        """
        import time
        start_time = time.time()
        
        self.logger.info(f"Backtesting strategy: {strategy_type.value}")
        
        # Group trades by account and symbol
        trade_groups = {}
        for trade in trades:
            key = (trade.account_name, trade.symbol)
            if key not in trade_groups:
                trade_groups[key] = []
            trade_groups[key].append(trade)
        
        # Track predictions and outcomes
        predictions = []
        actual_outcomes = []
        trade_returns = []
        
        total_recommendations = 0
        correct_predictions = 0
        
        # Walk-forward analysis if enabled
        if config.enable_walk_forward:
            predictions, actual_outcomes, trade_returns = self._walk_forward_backtest(
                strategy_type, config, trade_groups
            )
        else:
            predictions, actual_outcomes, trade_returns = self._simple_backtest(
                strategy_type, config, trade_groups
            )
        
        # Calculate performance metrics
        if not predictions:
            return self._create_fallback_result(strategy_type, "No predictions generated")
        
        # Calculate accuracy
        correct_predictions = sum(1 for pred, actual in zip(predictions, actual_outcomes) 
                                if (pred == 'TRADE' and actual > 0) or (pred == 'AVOID' and actual <= 0))
        accuracy = correct_predictions / len(predictions) if predictions else 0.0
        
        # Calculate financial metrics
        total_return = sum(trade_returns)
        winning_trades = sum(1 for ret in trade_returns if ret > 0)
        losing_trades = sum(1 for ret in trade_returns if ret < 0)
        win_rate = winning_trades / len(trade_returns) if trade_returns else 0.0
        
        avg_winning_trade = np.mean([ret for ret in trade_returns if ret > 0]) if winning_trades > 0 else 0.0
        avg_losing_trade = np.mean([ret for ret in trade_returns if ret < 0]) if losing_trades > 0 else 0.0
        
        profit_factor = abs(avg_winning_trade * winning_trades / (avg_losing_trade * losing_trades)) if losing_trades > 0 and avg_losing_trade != 0 else float('inf')
        
        # Calculate risk metrics
        returns_array = np.array(trade_returns) if trade_returns else np.array([0])
        volatility = np.std(returns_array)
        
        # Calculate maximum drawdown
        cumulative_returns = np.cumsum(returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = running_max - cumulative_returns
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
        
        # Calculate Sharpe ratio (assuming risk-free rate of 0)
        sharpe_ratio = np.mean(returns_array) / volatility if volatility > 0 else 0.0
        
        # Calculate confidence intervals
        confidence_intervals = self._calculate_confidence_intervals(
            returns_array, config.confidence_level
        )
        
        # Statistical significance tests
        statistical_significance = self._calculate_statistical_significance(
            returns_array, predictions, actual_outcomes
        )
        
        execution_time = time.time() - start_time
        
        return BacktestResult(
            strategy_type=strategy_type,
            total_recommendations=len(predictions),
            correct_predictions=correct_predictions,
            accuracy=accuracy,
            total_return=total_return,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            avg_trade_return=np.mean(returns_array),
            best_trade=np.max(returns_array) if len(returns_array) > 0 else 0.0,
            worst_trade=np.min(returns_array) if len(returns_array) > 0 else 0.0,
            total_trades=len(trade_returns),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_winning_trade=avg_winning_trade,
            avg_losing_trade=avg_losing_trade,
            execution_time=execution_time,
            confidence_intervals=confidence_intervals,
            statistical_significance=statistical_significance
        )
    
    def _walk_forward_backtest(self, 
                              strategy_type: StrategyType,
                              config: BacktestConfiguration,
                              trade_groups: Dict[Tuple[str, str], List[ProcessedTrade]]) -> Tuple[List[str], List[float], List[float]]:
        """
        Perform walk-forward backtesting.
        
        Args:
            strategy_type: Strategy to test
            config: Backtesting configuration
            trade_groups: Trades grouped by account and symbol
            
        Returns:
            Tuple of (predictions, actual_outcomes, trade_returns)
        """
        predictions = []
        actual_outcomes = []
        trade_returns = []
        
        # Walk forward through time
        current_date = config.start_date
        window_size = timedelta(days=config.walk_forward_window)
        
        while current_date + window_size <= config.end_date:
            window_end = current_date + window_size
            
            # For each account/symbol combination
            for (account_name, symbol), account_trades in trade_groups.items():
                # Get trades in current window
                window_trades = [
                    trade for trade in account_trades
                    if current_date <= trade.entry_time < window_end
                ]
                
                if len(window_trades) < 2:  # Need at least 2 trades for analysis
                    continue
                
                # Use first part for training context, last trade for prediction
                training_trades = window_trades[:-1]
                test_trade = window_trades[-1]
                
                # Create recommendation context
                context = RecommendationContext(
                    account_name=account_name,
                    symbol=symbol,
                    current_time=test_trade.entry_time,
                    hour_of_day=test_trade.hour_of_day,
                    day_of_week=test_trade.day_of_week,
                    historical_trades=training_trades,
                    risk_tolerance=0.5
                )
                
                # Generate prediction using specific strategy
                try:
                    if strategy_type == StrategyType.STATISTICAL:
                        strategy_result = self.recommendation_service._execute_statistical_strategy(context)
                    elif strategy_type == StrategyType.MACHINE_LEARNING:
                        strategy_result = self.recommendation_service._execute_ml_strategy(context)
                    elif strategy_type == StrategyType.MONTE_CARLO:
                        strategy_result = self.recommendation_service._execute_monte_carlo_strategy(context)
                    else:
                        continue  # Skip ensemble for individual strategy testing
                    
                    # Record prediction and actual outcome
                    predictions.append(strategy_result.recommendation)
                    actual_outcomes.append(test_trade.profit_loss)
                    
                    # Only include return if strategy recommended trading
                    if strategy_result.recommendation == 'TRADE':
                        trade_returns.append(test_trade.profit_loss)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to generate prediction for {strategy_type.value}: {e}")
                    continue
            
            # Move to next window
            current_date += timedelta(days=1)
        
        return predictions, actual_outcomes, trade_returns
    
    def _simple_backtest(self, 
                        strategy_type: StrategyType,
                        config: BacktestConfiguration,
                        trade_groups: Dict[Tuple[str, str], List[ProcessedTrade]]) -> Tuple[List[str], List[float], List[float]]:
        """
        Perform simple backtesting without walk-forward analysis.
        
        Args:
            strategy_type: Strategy to test
            config: Backtesting configuration
            trade_groups: Trades grouped by account and symbol
            
        Returns:
            Tuple of (predictions, actual_outcomes, trade_returns)
        """
        predictions = []
        actual_outcomes = []
        trade_returns = []
        
        for (account_name, symbol), account_trades in trade_groups.items():
            # Sort trades by time
            sorted_trades = sorted(account_trades, key=lambda t: t.entry_time)
            
            # Use first 70% for training, last 30% for testing
            split_index = int(len(sorted_trades) * 0.7)
            training_trades = sorted_trades[:split_index]
            test_trades = sorted_trades[split_index:]
            
            if len(training_trades) < config.min_trades_required or len(test_trades) < 1:
                continue
            
            # Generate predictions for test trades
            for test_trade in test_trades:
                context = RecommendationContext(
                    account_name=account_name,
                    symbol=symbol,
                    current_time=test_trade.entry_time,
                    hour_of_day=test_trade.hour_of_day,
                    day_of_week=test_trade.day_of_week,
                    historical_trades=training_trades,
                    risk_tolerance=0.5
                )
                
                try:
                    if strategy_type == StrategyType.STATISTICAL:
                        strategy_result = self.recommendation_service._execute_statistical_strategy(context)
                    elif strategy_type == StrategyType.MACHINE_LEARNING:
                        strategy_result = self.recommendation_service._execute_ml_strategy(context)
                    elif strategy_type == StrategyType.MONTE_CARLO:
                        strategy_result = self.recommendation_service._execute_monte_carlo_strategy(context)
                    else:
                        continue
                    
                    predictions.append(strategy_result.recommendation)
                    actual_outcomes.append(test_trade.profit_loss)
                    
                    if strategy_result.recommendation == 'TRADE':
                        trade_returns.append(test_trade.profit_loss)
                
                except Exception as e:
                    self.logger.warning(f"Failed to generate prediction: {e}")
                    continue
        
        return predictions, actual_outcomes, trade_returns
    
    def compare_strategies(self, 
                          backtest_results: Dict[StrategyType, BacktestResult]) -> List[StrategyComparisonResult]:
        """
        Compare strategies and generate comparison results with statistical tests.
        
        Args:
            backtest_results: Results from backtesting multiple strategies
            
        Returns:
            List of strategy comparison results
        """
        if len(backtest_results) < 2:
            return []
        
        comparisons = []
        strategy_types = list(backtest_results.keys())
        
        # Generate pairwise comparisons
        for i, strategy_a in enumerate(strategy_types):
            for strategy_b in strategy_types[i+1:]:
                result_a = backtest_results[strategy_a]
                result_b = backtest_results[strategy_b]
                
                # Calculate differences
                accuracy_diff = result_a.accuracy - result_b.accuracy
                return_diff = result_a.total_return - result_b.total_return
                risk_diff = result_a.volatility - result_b.volatility
                sharpe_diff = result_a.sharpe_ratio - result_b.sharpe_ratio
                
                # Statistical tests
                t_test_pvalue = self._perform_t_test(result_a, result_b)
                wilcoxon_pvalue = self._perform_wilcoxon_test(result_a, result_b)
                chi_square_pvalue = self._perform_chi_square_test(result_a, result_b)
                
                # Calculate preference score
                preference_score = (
                    accuracy_diff * 0.3 +
                    (return_diff / max(abs(result_a.total_return), abs(result_b.total_return), 1)) * 0.4 +
                    (-risk_diff / max(result_a.volatility, result_b.volatility, 1)) * 0.2 +
                    sharpe_diff * 0.1
                )
                
                # Determine statistical significance
                significance_threshold = 0.05
                if min(t_test_pvalue, wilcoxon_pvalue) < significance_threshold:
                    statistical_significance = 'significant'
                elif max(t_test_pvalue, wilcoxon_pvalue) > 0.1:
                    statistical_significance = 'not_significant'
                else:
                    statistical_significance = 'inconclusive'
                
                comparison = StrategyComparisonResult(
                    strategy_a=strategy_a,
                    strategy_b=strategy_b,
                    strategy_a_performance=result_a,
                    strategy_b_performance=result_b,
                    accuracy_difference=accuracy_diff,
                    return_difference=return_diff,
                    risk_difference=risk_diff,
                    sharpe_difference=sharpe_diff,
                    t_test_pvalue=t_test_pvalue,
                    wilcoxon_pvalue=wilcoxon_pvalue,
                    chi_square_pvalue=chi_square_pvalue,
                    preference_score=preference_score,
                    statistical_significance=statistical_significance,
                    sample_size=min(result_a.total_recommendations, result_b.total_recommendations)
                )
                
                comparisons.append(comparison)
        
        return comparisons
    
    def generate_strategy_performance_report(self, 
                                           backtest_results: Dict[StrategyType, BacktestResult],
                                           comparisons: List[StrategyComparisonResult]) -> Dict[str, Any]:
        """
        Generate comprehensive strategy performance report.
        
        Args:
            backtest_results: Backtest results for all strategies
            comparisons: Strategy comparison results
            
        Returns:
            Dictionary containing comprehensive performance report
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_strategies_tested': len(backtest_results),
                'total_comparisons': len(comparisons),
                'best_strategy': None,
                'worst_strategy': None
            },
            'individual_performance': {},
            'strategy_comparisons': [],
            'recommendations': []
        }
        
        # Individual strategy performance
        best_sharpe = float('-inf')
        worst_sharpe = float('inf')
        best_strategy = None
        worst_strategy = None
        
        for strategy_type, result in backtest_results.items():
            performance_data = {
                'strategy': strategy_type.value,
                'accuracy': result.accuracy,
                'total_return': result.total_return,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'volatility': result.volatility,
                'total_trades': result.total_trades,
                'execution_time': result.execution_time,
                'confidence_intervals': result.confidence_intervals,
                'statistical_significance': result.statistical_significance
            }
            
            report['individual_performance'][strategy_type.value] = performance_data
            
            # Track best and worst strategies
            if result.sharpe_ratio > best_sharpe:
                best_sharpe = result.sharpe_ratio
                best_strategy = strategy_type.value
            
            if result.sharpe_ratio < worst_sharpe:
                worst_sharpe = result.sharpe_ratio
                worst_strategy = strategy_type.value
        
        report['summary']['best_strategy'] = best_strategy
        report['summary']['worst_strategy'] = worst_strategy
        
        # Strategy comparisons
        for comparison in comparisons:
            comparison_data = {
                'strategy_a': comparison.strategy_a.value,
                'strategy_b': comparison.strategy_b.value,
                'accuracy_difference': comparison.accuracy_difference,
                'return_difference': comparison.return_difference,
                'risk_difference': comparison.risk_difference,
                'sharpe_difference': comparison.sharpe_difference,
                'preference_score': comparison.preference_score,
                'statistical_significance': comparison.statistical_significance,
                'sample_size': comparison.sample_size,
                'p_values': {
                    't_test': comparison.t_test_pvalue,
                    'wilcoxon': comparison.wilcoxon_pvalue,
                    'chi_square': comparison.chi_square_pvalue
                }
            }
            
            report['strategy_comparisons'].append(comparison_data)
        
        # Generate recommendations
        recommendations = []
        
        # Recommend best performing strategy
        if best_strategy:
            recommendations.append(f"Best performing strategy: {best_strategy} (Sharpe ratio: {best_sharpe:.3f})")
        
        # Identify significant differences
        significant_comparisons = [c for c in comparisons if c.statistical_significance == 'significant']
        if significant_comparisons:
            for comp in significant_comparisons:
                if comp.preference_score > 0.1:
                    recommendations.append(
                        f"{comp.strategy_a.value} significantly outperforms {comp.strategy_b.value} "
                        f"(preference score: {comp.preference_score:.3f})"
                    )
        
        # Risk-adjusted recommendations
        low_risk_strategies = [
            (strategy, result) for strategy, result in backtest_results.items()
            if result.max_drawdown < 0.1 and result.sharpe_ratio > 0.5
        ]
        
        if low_risk_strategies:
            best_low_risk = max(low_risk_strategies, key=lambda x: x[1].sharpe_ratio)
            recommendations.append(
                f"Best low-risk strategy: {best_low_risk[0].value} "
                f"(Max drawdown: {best_low_risk[1].max_drawdown:.3f}, Sharpe: {best_low_risk[1].sharpe_ratio:.3f})"
            )
        
        report['recommendations'] = recommendations
        
        return report
    
    def update_confidence_scoring(self, 
                                 strategy_type: StrategyType,
                                 recent_accuracy: float,
                                 sample_size: int) -> ConfidenceScoring:
        """
        Update confidence scoring for a strategy based on recent performance.
        
        Args:
            strategy_type: Strategy to update
            recent_accuracy: Recent accuracy (0.0 to 1.0)
            sample_size: Number of recent predictions
            
        Returns:
            Updated confidence scoring
        """
        # Get historical accuracy
        historical_results = self.strategy_performance_history.get(strategy_type, [])
        historical_accuracy = np.mean([r.accuracy for r in historical_results]) if historical_results else 0.5
        
        # Base confidence starts at 0.5
        base_confidence = 0.5
        
        # Adjust based on historical performance
        historical_adjustment = (historical_accuracy - 0.5) * 0.3
        
        # Adjust based on recent performance (weighted more heavily)
        recent_adjustment = (recent_accuracy - 0.5) * 0.5
        
        # Sample size adjustment (more samples = more confidence)
        sample_adjustment = min(0.1, sample_size / 100 * 0.1)
        
        # Calculate final confidence
        confidence_adjustment = historical_adjustment + recent_adjustment + sample_adjustment
        final_confidence = max(0.1, min(0.9, base_confidence + confidence_adjustment))
        
        confidence_scoring = ConfidenceScoring(
            strategy_type=strategy_type,
            base_confidence=base_confidence,
            historical_accuracy=historical_accuracy,
            recent_accuracy=recent_accuracy,
            confidence_adjustment=confidence_adjustment,
            final_confidence=final_confidence,
            sample_size=sample_size
        )
        
        # Store updated confidence scoring
        self.confidence_scores[strategy_type] = confidence_scoring
        
        return confidence_scoring
    
    def implement_strategy_switching(self, 
                                   performance_data: Dict[StrategyType, float]) -> StrategyType:
        """
        Implement strategy switching logic based on recent performance.
        
        Args:
            performance_data: Recent performance scores for each strategy
            
        Returns:
            Recommended strategy to use
        """
        if not self.strategy_switching_enabled or not performance_data:
            return self.current_best_strategy
        
        # Find best performing strategy
        best_strategy = max(performance_data.items(), key=lambda x: x[1])
        best_strategy_type, best_performance = best_strategy
        
        # Get current strategy performance
        current_performance = performance_data.get(self.current_best_strategy, 0.0)
        
        # Check if switching threshold is met
        performance_improvement = best_performance - current_performance
        
        if performance_improvement > self.switching_threshold:
            self.logger.info(
                f"Switching from {self.current_best_strategy.value} to {best_strategy_type.value} "
                f"(improvement: {performance_improvement:.3f})"
            )
            self.current_best_strategy = best_strategy_type
        
        return self.current_best_strategy
    
    def _update_confidence_scores(self, backtest_results: Dict[StrategyType, BacktestResult]):
        """Update confidence scores based on backtest results."""
        for strategy_type, result in backtest_results.items():
            self.update_confidence_scoring(
                strategy_type=strategy_type,
                recent_accuracy=result.accuracy,
                sample_size=result.total_recommendations
            )
    
    def _calculate_confidence_intervals(self, 
                                      returns: np.ndarray,
                                      confidence_level: float) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence intervals for various metrics."""
        if len(returns) < 2:
            return {}
        
        alpha = 1 - confidence_level
        
        # Mean return confidence interval
        mean_return = np.mean(returns)
        std_error = stats.sem(returns)
        t_critical = stats.t.ppf(1 - alpha/2, len(returns) - 1)
        mean_ci = (
            mean_return - t_critical * std_error,
            mean_return + t_critical * std_error
        )
        
        # Sharpe ratio confidence interval (approximate)
        sharpe = mean_return / np.std(returns) if np.std(returns) > 0 else 0
        sharpe_std_error = np.sqrt((1 + sharpe**2/2) / len(returns))
        sharpe_ci = (
            sharpe - t_critical * sharpe_std_error,
            sharpe + t_critical * sharpe_std_error
        )
        
        return {
            'mean_return': mean_ci,
            'sharpe_ratio': sharpe_ci
        }
    
    def _calculate_statistical_significance(self, 
                                          returns: np.ndarray,
                                          predictions: List[str],
                                          actual_outcomes: List[float]) -> Dict[str, float]:
        """Calculate statistical significance tests."""
        if len(returns) < 2:
            return {}
        
        # Test if mean return is significantly different from zero
        t_stat, t_pvalue = stats.ttest_1samp(returns, 0)
        
        # Test if predictions are better than random
        correct_predictions = sum(1 for pred, actual in zip(predictions, actual_outcomes) 
                                if (pred == 'TRADE' and actual > 0) or (pred == 'AVOID' and actual <= 0))
        
        # Binomial test for accuracy vs random (50%)
        binom_pvalue = stats.binom_test(correct_predictions, len(predictions), 0.5)
        
        return {
            'mean_return_t_test': t_pvalue,
            'accuracy_binomial_test': binom_pvalue
        }
    
    def _perform_t_test(self, result_a: BacktestResult, result_b: BacktestResult) -> float:
        """Perform t-test between two strategy results."""
        # Since we don't have individual trade returns, use approximation
        # based on total return and number of trades
        if result_a.total_trades < 2 or result_b.total_trades < 2:
            return 1.0  # No significant difference
        
        # Approximate individual returns
        returns_a = np.random.normal(
            result_a.avg_trade_return, 
            result_a.volatility, 
            result_a.total_trades
        )
        returns_b = np.random.normal(
            result_b.avg_trade_return, 
            result_b.volatility, 
            result_b.total_trades
        )
        
        try:
            _, pvalue = stats.ttest_ind(returns_a, returns_b)
            return pvalue
        except:
            return 1.0
    
    def _perform_wilcoxon_test(self, result_a: BacktestResult, result_b: BacktestResult) -> float:
        """Perform Wilcoxon rank-sum test between two strategy results."""
        # Similar approximation as t-test
        if result_a.total_trades < 2 or result_b.total_trades < 2:
            return 1.0
        
        returns_a = np.random.normal(
            result_a.avg_trade_return, 
            result_a.volatility, 
            min(result_a.total_trades, 100)  # Limit size for performance
        )
        returns_b = np.random.normal(
            result_b.avg_trade_return, 
            result_b.volatility, 
            min(result_b.total_trades, 100)
        )
        
        try:
            _, pvalue = stats.ranksums(returns_a, returns_b)
            return pvalue
        except:
            return 1.0
    
    def _perform_chi_square_test(self, result_a: BacktestResult, result_b: BacktestResult) -> float:
        """Perform chi-square test for independence of strategy performance."""
        # Test win/loss distribution
        observed = np.array([
            [result_a.winning_trades, result_a.losing_trades],
            [result_b.winning_trades, result_b.losing_trades]
        ])
        
        if np.any(observed < 5):  # Chi-square requires minimum expected frequency
            return 1.0
        
        try:
            _, pvalue, _, _ = stats.chi2_contingency(observed)
            return pvalue
        except:
            return 1.0
    
    def _create_fallback_result(self, strategy_type: StrategyType, error_message: str) -> BacktestResult:
        """Create a fallback result when backtesting fails."""
        return BacktestResult(
            strategy_type=strategy_type,
            total_recommendations=0,
            correct_predictions=0,
            accuracy=0.0,
            total_return=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            volatility=0.0,
            avg_trade_return=0.0,
            best_trade=0.0,
            worst_trade=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_winning_trade=0.0,
            avg_losing_trade=0.0,
            execution_time=0.0,
            confidence_intervals={},
            statistical_significance={'error': error_message}
        )
    
    def run_comprehensive_backtest(self, 
                                  trades: List[ProcessedTrade],
                                  config: BacktestConfiguration) -> Dict[StrategyType, BacktestResult]:
        """
        Run comprehensive backtesting across all strategies.
        
        This is the main entry point for backtesting that orchestrates the entire process.
        
        Args:
            trades: Historical trade data for backtesting
            config: Backtesting configuration
            
        Returns:
            Dictionary mapping strategy types to backtest results
        """
        if not trades:
            raise ValueError("No trades provided for backtesting")
        
        # Check cache first
        cache_key = self._generate_cache_key(trades, config)
        if self.enable_caching and cache_key in self.backtest_cache:
            cache_time, cached_result = self.backtest_cache[cache_key]
            if datetime.now() - cache_time < self.cache_duration:
                self.logger.info("Returning cached backtest results")
                return cached_result
        
        # Run the actual backtesting
        results = self.run_backtest(config, trades)
        
        # Cache results
        if self.enable_caching:
            self.backtest_cache[cache_key] = (datetime.now(), results)
        
        return results
    
    def _generate_cache_key(self, trades: List[ProcessedTrade], config: BacktestConfiguration) -> str:
        """Generate cache key for backtest results."""
        import hashlib
        
        # Create a hash based on trades and config
        trade_hash = hashlib.md5(
            str([(t.trade_id, t.profit_loss, t.entry_time) for t in trades[:10]]).encode()
        ).hexdigest()[:8]
        
        config_hash = hashlib.md5(
            f"{config.start_date}{config.end_date}{config.walk_forward_window}".encode()
        ).hexdigest()[:8]
        
        return f"backtest_{trade_hash}_{config_hash}"
    
    def _backtest_single_strategy(self, 
                                 strategy_type: StrategyType,
                                 trades: List[ProcessedTrade],
                                 config: BacktestConfiguration) -> BacktestResult:
        """
        Backtest a single strategy against historical data.
        
        Args:
            strategy_type: Strategy to backtest
            trades: Historical trades for backtesting
            config: Backtesting configuration
            
        Returns:
            BacktestResult with performance metrics
        """
        import time
        start_time = time.time()
        
        self.logger.info(f"Backtesting strategy: {strategy_type.value}")
        
        # Group trades by account and symbol
        trade_groups = {}
        for trade in trades:
            key = (trade.account_name, trade.symbol)
            if key not in trade_groups:
                trade_groups[key] = []
            trade_groups[key].append(trade)
        
        # Track predictions and outcomes
        if config.enable_walk_forward:
            predictions, actual_outcomes, trade_returns = self._walk_forward_backtest(
                strategy_type, config, trade_groups
            )
        else:
            predictions, actual_outcomes, trade_returns = self._simple_backtest(
                strategy_type, config, trade_groups
            )
        
        # Calculate performance metrics
        if not predictions:
            return self._create_fallback_result(strategy_type, "No predictions generated")
        
        # Calculate accuracy
        correct_predictions = sum(1 for pred, actual in zip(predictions, actual_outcomes) 
                                if (pred == 'TRADE' and actual > 0) or (pred == 'AVOID' and actual <= 0))
        accuracy = correct_predictions / len(predictions) if predictions else 0.0
        
        # Calculate financial metrics
        total_return = sum(trade_returns)
        winning_trades = sum(1 for ret in trade_returns if ret > 0)
        losing_trades = sum(1 for ret in trade_returns if ret < 0)
        win_rate = winning_trades / len(trade_returns) if trade_returns else 0.0
        
        avg_winning_trade = np.mean([ret for ret in trade_returns if ret > 0]) if winning_trades > 0 else 0.0
        avg_losing_trade = np.mean([ret for ret in trade_returns if ret < 0]) if losing_trades > 0 else 0.0
        
        profit_factor = abs(avg_winning_trade * winning_trades / (avg_losing_trade * losing_trades)) if losing_trades > 0 and avg_losing_trade != 0 else float('inf')
        
        # Calculate risk metrics
        returns_array = np.array(trade_returns) if trade_returns else np.array([0])
        volatility = np.std(returns_array)
        
        # Calculate maximum drawdown
        cumulative_returns = np.cumsum(returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = running_max - cumulative_returns
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
        
        # Calculate Sharpe ratio (assuming risk-free rate of 0)
        sharpe_ratio = np.mean(returns_array) / volatility if volatility > 0 else 0.0
        
        # Calculate confidence intervals
        confidence_intervals = self._calculate_confidence_intervals(
            returns_array, config.confidence_level
        )
        
        # Statistical significance tests
        statistical_significance = self._calculate_statistical_significance(
            returns_array, predictions, actual_outcomes
        )
        
        execution_time = time.time() - start_time
        
        return BacktestResult(
            strategy_type=strategy_type,
            total_recommendations=len(predictions),
            correct_predictions=correct_predictions,
            accuracy=accuracy,
            total_return=total_return,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            avg_trade_return=np.mean(returns_array),
            best_trade=np.max(returns_array) if len(returns_array) > 0 else 0.0,
            worst_trade=np.min(returns_array) if len(returns_array) > 0 else 0.0,
            total_trades=len(trade_returns),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_winning_trade=avg_winning_trade,
            avg_losing_trade=avg_losing_trade,
            execution_time=execution_time,
            confidence_intervals=confidence_intervals,
            statistical_significance=statistical_significance
        )
    
    def _generate_strategy_prediction(self, 
                                    strategy_type: StrategyType,
                                    context: RecommendationContext) -> str:
        """
        Generate prediction for a specific strategy.
        
        Args:
            strategy_type: Strategy to use for prediction
            context: Recommendation context
            
        Returns:
            Prediction ('TRADE' or 'AVOID')
        """
        try:
            if strategy_type == StrategyType.STATISTICAL:
                result = self.recommendation_service._execute_statistical_strategy(context)
            elif strategy_type == StrategyType.MACHINE_LEARNING:
                result = self.recommendation_service._execute_ml_strategy(context)
            elif strategy_type == StrategyType.MONTE_CARLO:
                result = self.recommendation_service._execute_monte_carlo_strategy(context)
            else:
                raise ValueError(f"Unknown strategy type: {strategy_type}")
            
            return result.recommendation
            
        except Exception as e:
            self.logger.warning(f"Strategy prediction failed for {strategy_type.value}: {e}")
            return 'AVOID'  # Conservative fallback
    
    def get_confidence_score(self, strategy_type: StrategyType) -> float:
        """
        Get confidence score for a strategy.
        
        Args:
            strategy_type: Strategy to get confidence for
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if strategy_type in self.confidence_scores:
            return self.confidence_scores[strategy_type].final_confidence
        return 0.5  # Default confidence
    
    def get_strategy_switching_recommendation(self) -> Dict[str, Any]:
        """
        Get strategy switching recommendation.
        
        Returns:
            Dictionary with switching recommendation details
        """
        return {
            'current_best_strategy': self.current_best_strategy.value,
            'switching_enabled': self.strategy_switching_enabled,
            'switching_threshold': self.switching_threshold,
            'confidence_scores': {
                strategy.value: self.get_confidence_score(strategy)
                for strategy in StrategyType
            }
        }
    
    def _run_parallel_backtests(self, 
                               trades: List[ProcessedTrade],
                               config: BacktestConfiguration) -> Dict[StrategyType, BacktestResult]:
        """
        Run backtests in parallel for better performance.
        
        Args:
            trades: Historical trades
            config: Backtest configuration
            
        Returns:
            Dictionary of backtest results
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=len(config.strategies_to_test)) as executor:
            # Submit backtest tasks
            future_to_strategy = {
                executor.submit(self._backtest_single_strategy, strategy, trades, config): strategy
                for strategy in config.strategies_to_test
            }
            
            # Collect results
            for future in as_completed(future_to_strategy):
                strategy_type = future_to_strategy[future]
                try:
                    result = future.result()
                    results[strategy_type] = result
                except Exception as e:
                    self.logger.error(f"Parallel backtest failed for {strategy_type.value}: {e}")
                    results[strategy_type] = self._create_fallback_result(strategy_type, str(e))
        
        return results
    
    def _calculate_confidence_intervals(self, 
                                      returns: np.ndarray,
                                      confidence_level: float) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence intervals for various metrics."""
        if len(returns) < 2:
            return {'mean': (0.0, 0.0), 'std': (0.0, 0.0)}
        
        alpha = 1 - confidence_level
        
        # Mean return confidence interval
        mean_return = np.mean(returns)
        std_error = stats.sem(returns)
        t_critical = stats.t.ppf(1 - alpha/2, len(returns) - 1)
        mean_ci = (
            mean_return - t_critical * std_error,
            mean_return + t_critical * std_error
        )
        
        # Standard deviation confidence interval
        std_return = np.std(returns)
        std_ci = (
            max(0.0, std_return - t_critical * std_error),
            std_return + t_critical * std_error
        )
        
        return {
            'mean': mean_ci,
            'std': std_ci
        }
    
    def _calculate_statistical_significance(self, 
                                          returns: np.ndarray,
                                          predictions: List[str] = None,
                                          actual_outcomes: List[float] = None) -> Dict[str, float]:
        """Calculate statistical significance tests."""
        if len(returns) < 2:
            return {'t_test_pvalue': 1.0, 'normality_test_pvalue': 1.0}
        
        # Test if mean return is significantly different from zero
        try:
            t_stat, t_pvalue = stats.ttest_1samp(returns, 0)
        except:
            t_pvalue = 1.0
        
        # Test for normality
        try:
            if len(returns) >= 8:  # Shapiro-Wilk requires at least 3 samples, but more reliable with 8+
                _, normality_pvalue = stats.shapiro(returns)
            else:
                normality_pvalue = 1.0
        except:
            normality_pvalue = 1.0
        
        result = {
            't_test_pvalue': t_pvalue,
            'normality_test_pvalue': normality_pvalue
        }
        
        # Test prediction accuracy if available
        if predictions and actual_outcomes and len(predictions) == len(actual_outcomes):
            try:
                correct_predictions = sum(1 for pred, actual in zip(predictions, actual_outcomes) 
                                        if (pred == 'TRADE' and actual > 0) or (pred == 'AVOID' and actual <= 0))
                
                # Binomial test for accuracy vs random (50%)
                binom_pvalue = stats.binom_test(correct_predictions, len(predictions), 0.5)
                result['accuracy_binomial_test'] = binom_pvalue
            except:
                result['accuracy_binomial_test'] = 1.0
        
        return result
    
    def _perform_t_test(self, result_a: BacktestResult, result_b: BacktestResult) -> float:
        """Perform t-test between two strategy results."""
        # Since we don't have individual trade returns, use approximation
        # based on total return and number of trades
        if result_a.total_trades < 2 or result_b.total_trades < 2:
            return 1.0  # No significant difference
        
        # Approximate individual returns
        try:
            returns_a = np.random.normal(
                result_a.avg_trade_return, 
                max(result_a.volatility, 0.1), 
                result_a.total_trades
            )
            returns_b = np.random.normal(
                result_b.avg_trade_return, 
                max(result_b.volatility, 0.1), 
                result_b.total_trades
            )
            
            _, pvalue = stats.ttest_ind(returns_a, returns_b)
            return pvalue
        except:
            return 1.0
    
    def _perform_wilcoxon_test(self, result_a: BacktestResult, result_b: BacktestResult) -> float:
        """Perform Wilcoxon rank-sum test between two strategy results."""
        # Similar approximation as t-test
        if result_a.total_trades < 2 or result_b.total_trades < 2:
            return 1.0
        
        try:
            returns_a = np.random.normal(
                result_a.avg_trade_return, 
                max(result_a.volatility, 0.1), 
                min(result_a.total_trades, 100)  # Limit size for performance
            )
            returns_b = np.random.normal(
                result_b.avg_trade_return, 
                max(result_b.volatility, 0.1), 
                min(result_b.total_trades, 100)
            )
            
            _, pvalue = stats.ranksums(returns_a, returns_b)
            return pvalue
        except:
            return 1.0
    
    def _perform_chi_square_test(self, result_a: BacktestResult, result_b: BacktestResult) -> float:
        """Perform chi-square test for independence of strategy performance."""
        # Test win/loss distribution
        try:
            observed = np.array([
                [max(result_a.winning_trades, 1), max(result_a.losing_trades, 1)],
                [max(result_b.winning_trades, 1), max(result_b.losing_trades, 1)]
            ])
            
            if np.any(observed < 5):  # Chi-square requires minimum expected frequency
                return 1.0
            
            _, pvalue, _, _ = stats.chi2_contingency(observed)
            return pvalue
        except:
            return 1.0