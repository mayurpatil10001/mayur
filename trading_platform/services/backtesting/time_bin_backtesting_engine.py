"""
Advanced backtesting engine for time-bin trading strategies.

This module provides comprehensive backtesting capabilities with Monte Carlo simulation,
walk-forward analysis, and statistical validation for time-bin based trading strategies.

Requirements: 9.1, 9.2, 9.3
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import json
import pickle
from pathlib import Path

from ..time_bin_analyzer import TimeBin, TimeBinAnalyzer
from ..monte_carlo.monte_carlo_simulator import MonteCarloSimulator
from ..statistical_testing_engine import StatisticalTestingEngine
from ...models.trading import ProcessedTrade

logger = logging.getLogger(__name__)


class BacktestMethod(Enum):
    """Backtesting methodology types."""
    SIMPLE_HISTORICAL = "simple_historical"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    BOOTSTRAP = "bootstrap"
    CROSS_VALIDATION = "cross_validation"


class PerformanceMetric(Enum):
    """Performance metrics for backtesting evaluation."""
    TOTAL_RETURN = "total_return"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    INFORMATION_RATIO = "information_ratio"
    BETA = "beta"
    ALPHA = "alpha"
    VOLATILITY = "volatility"
    VAR_95 = "var_95"
    CVAR_95 = "cvar_95"


@dataclass
class BacktestConfiguration:
    """Configuration for backtesting engine."""
    start_date: date
    end_date: date
    initial_capital: float = 100000.0
    commission_per_trade: float = 1.0
    slippage_bps: int = 1  # basis points
    method: BacktestMethod = BacktestMethod.SIMPLE_HISTORICAL
    
    # Walk-forward specific
    training_days: int = 252  # 1 year
    testing_days: int = 63   # 1 quarter
    rebalance_frequency: int = 21  # monthly
    
    # Monte Carlo specific
    num_simulations: int = 1000
    confidence_levels: List[float] = field(default_factory=lambda: [0.95, 0.99])
    
    # Cross-validation specific
    num_folds: int = 5
    
    # Performance evaluation
    benchmark_symbol: str = "SPY"
    risk_free_rate: float = 0.02  # 2% annual
    target_metrics: List[PerformanceMetric] = field(
        default_factory=lambda: [
            PerformanceMetric.TOTAL_RETURN,
            PerformanceMetric.SHARPE_RATIO,
            PerformanceMetric.MAX_DRAWDOWN,
            PerformanceMetric.WIN_RATE
        ]
    )


@dataclass
class TradeSignal:
    """Trading signal for backtesting."""
    timestamp: datetime
    time_bin: TimeBin
    signal_type: str  # BUY, SELL, HOLD
    confidence: float
    quantity: Optional[int] = None
    price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestTrade:
    """Individual trade in backtesting simulation."""
    entry_time: datetime
    exit_time: Optional[datetime]
    time_bin: TimeBin
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    trade_type: str  # LONG, SHORT
    pnl: Optional[float] = None
    commission: float = 0.0
    slippage: float = 0.0
    is_closed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestPeriodResult:
    """Results for a specific backtesting period."""
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    total_return: float
    num_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_pnl: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    profit_factor: Optional[float]
    win_rate: float
    total_commission: float
    total_slippage: float
    
    # Daily returns for further analysis
    daily_returns: List[float] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)
    
    # Statistical metrics
    statistical_significance: Optional[float] = None
    p_value: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None


@dataclass
class BacktestResult:
    """Complete backtesting results."""
    configuration: BacktestConfiguration
    method: BacktestMethod
    overall_result: BacktestPeriodResult
    period_results: List[BacktestPeriodResult] = field(default_factory=list)
    
    # Monte Carlo specific results
    simulation_results: Optional[List[BacktestPeriodResult]] = None
    percentile_results: Optional[Dict[float, BacktestPeriodResult]] = None
    
    # Walk-forward specific results
    out_of_sample_results: Optional[List[BacktestPeriodResult]] = None
    in_sample_results: Optional[List[BacktestPeriodResult]] = None
    
    # Cross-validation results
    fold_results: Optional[List[BacktestPeriodResult]] = None
    
    # Performance benchmarking
    benchmark_comparison: Optional[Dict[str, Any]] = None
    
    # Execution metadata
    execution_time_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class TimeBinBacktestingEngine:
    """
    Advanced backtesting engine for time-bin trading strategies.
    
    Provides comprehensive backtesting capabilities including historical simulation,
    walk-forward analysis, Monte Carlo simulation, and statistical validation.
    """
    
    def __init__(
        self,
        time_bin_analyzer: TimeBinAnalyzer,
        monte_carlo_simulator: Optional[MonteCarloSimulator] = None,
        statistical_testing: Optional[StatisticalTestingEngine] = None,
        max_workers: int = 4
    ):
        """Initialize the backtesting engine."""
        self.time_bin_analyzer = time_bin_analyzer
        self.monte_carlo_simulator = monte_carlo_simulator or MonteCarloSimulator()
        self.statistical_testing = statistical_testing or StatisticalTestingEngine()
        self.max_workers = max_workers
        
        # Strategy cache
        self.strategy_cache: Dict[str, Any] = {}
        
        # Execution pool
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        logger.info(f"TimeBinBacktestingEngine initialized with {max_workers} workers")
    
    async def run_backtest(
        self,
        strategy_function: Callable[[TimeBin, datetime, Dict[str, Any]], TradeSignal],
        configuration: BacktestConfiguration,
        time_bins: List[TimeBin],
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> BacktestResult:
        """
        Run comprehensive backtesting for a time-bin strategy.
        
        Args:
            strategy_function: Function that generates trading signals
            configuration: Backtesting configuration
            time_bins: List of time-bins to test
            strategy_params: Optional strategy parameters
            
        Returns:
            Complete backtesting results
        """
        start_time = datetime.now()
        strategy_params = strategy_params or {}
        
        try:
            logger.info(f"Starting {configuration.method.value} backtesting from {configuration.start_date} to {configuration.end_date}")
            
            # Load historical data for time-bins
            historical_data = await self._load_historical_data(time_bins, configuration)
            
            # Run backtesting based on method
            if configuration.method == BacktestMethod.SIMPLE_HISTORICAL:
                result = await self._run_historical_backtest(
                    strategy_function, configuration, historical_data, strategy_params
                )
            elif configuration.method == BacktestMethod.WALK_FORWARD:
                result = await self._run_walk_forward_backtest(
                    strategy_function, configuration, historical_data, strategy_params
                )
            elif configuration.method == BacktestMethod.MONTE_CARLO:
                result = await self._run_monte_carlo_backtest(
                    strategy_function, configuration, historical_data, strategy_params
                )
            elif configuration.method == BacktestMethod.BOOTSTRAP:
                result = await self._run_bootstrap_backtest(
                    strategy_function, configuration, historical_data, strategy_params
                )
            elif configuration.method == BacktestMethod.CROSS_VALIDATION:
                result = await self._run_cross_validation_backtest(
                    strategy_function, configuration, historical_data, strategy_params
                )
            else:
                raise ValueError(f"Unknown backtesting method: {configuration.method}")
            
            # Add benchmark comparison if specified
            if configuration.benchmark_symbol:
                result.benchmark_comparison = await self._compare_to_benchmark(
                    result, configuration
                )
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time_seconds = execution_time
            
            logger.info(f"Backtesting completed in {execution_time:.2f} seconds")
            return result
            
        except Exception as e:
            logger.error(f"Backtesting failed: {str(e)}")
            raise
    
    async def _load_historical_data(
        self, 
        time_bins: List[TimeBin], 
        configuration: BacktestConfiguration
    ) -> Dict[TimeBin, List[ProcessedTrade]]:
        """Load historical trade data for time-bins."""
        historical_data = {}
        
        for time_bin in time_bins:
            try:
                # Get trades for the time-bin within the date range
                trades = await self.time_bin_analyzer.get_trades_for_time_bin(
                    time_bin, 
                    start_date=configuration.start_date,
                    end_date=configuration.end_date
                )
                historical_data[time_bin] = trades
                logger.debug(f"Loaded {len(trades)} trades for {time_bin}")
                
            except Exception as e:
                logger.warning(f"Failed to load data for {time_bin}: {str(e)}")
                historical_data[time_bin] = []
        
        return historical_data
    
    async def _run_historical_backtest(
        self,
        strategy_function: Callable,
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        strategy_params: Dict[str, Any]
    ) -> BacktestResult:
        """Run simple historical backtesting."""
        logger.info("Running historical backtesting")
        
        # Generate trading signals
        signals = await self._generate_signals(
            strategy_function, configuration, historical_data, strategy_params
        )
        
        # Simulate trading
        period_result = await self._simulate_trading(
            signals, configuration, historical_data
        )
        
        # Create result
        result = BacktestResult(
            configuration=configuration,
            method=BacktestMethod.SIMPLE_HISTORICAL,
            overall_result=period_result,
            period_results=[period_result]
        )
        
        return result
    
    async def _run_walk_forward_backtest(
        self,
        strategy_function: Callable,
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        strategy_params: Dict[str, Any]
    ) -> BacktestResult:
        """Run walk-forward backtesting."""
        logger.info(f"Running walk-forward backtesting with {configuration.training_days} training days and {configuration.testing_days} testing days")
        
        in_sample_results = []
        out_of_sample_results = []
        
        # Generate date ranges for walk-forward
        date_ranges = self._generate_walk_forward_ranges(configuration)
        
        for i, (train_start, train_end, test_start, test_end) in enumerate(date_ranges):
            logger.debug(f"Walk-forward iteration {i+1}: training {train_start} to {train_end}, testing {test_start} to {test_end}")
            
            # Create configurations for training and testing periods
            train_config = configuration
            train_config.start_date = train_start
            train_config.end_date = train_end
            
            test_config = configuration
            test_config.start_date = test_start
            test_config.end_date = test_end
            
            # Filter historical data for training period
            train_data = self._filter_data_by_date(historical_data, train_start, train_end)
            
            # Generate signals using training data (would typically optimize strategy here)
            train_signals = await self._generate_signals(
                strategy_function, train_config, train_data, strategy_params
            )
            
            # Simulate in-sample performance
            in_sample_result = await self._simulate_trading(
                train_signals, train_config, train_data
            )
            in_sample_results.append(in_sample_result)
            
            # Filter historical data for testing period
            test_data = self._filter_data_by_date(historical_data, test_start, test_end)
            
            # Generate signals for testing period
            test_signals = await self._generate_signals(
                strategy_function, test_config, test_data, strategy_params
            )
            
            # Simulate out-of-sample performance
            out_of_sample_result = await self._simulate_trading(
                test_signals, test_config, test_data
            )
            out_of_sample_results.append(out_of_sample_result)
        
        # Combine all out-of-sample results for overall performance
        overall_result = self._combine_period_results(out_of_sample_results, configuration)
        
        result = BacktestResult(
            configuration=configuration,
            method=BacktestMethod.WALK_FORWARD,
            overall_result=overall_result,
            period_results=out_of_sample_results,
            in_sample_results=in_sample_results,
            out_of_sample_results=out_of_sample_results
        )
        
        return result
    
    async def _run_monte_carlo_backtest(
        self,
        strategy_function: Callable,
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        strategy_params: Dict[str, Any]
    ) -> BacktestResult:
        """Run Monte Carlo backtesting."""
        logger.info(f"Running Monte Carlo backtesting with {configuration.num_simulations} simulations")
        
        simulation_results = []
        
        # Run multiple simulations with bootstrapped data
        for i in range(configuration.num_simulations):
            if i % 100 == 0:
                logger.debug(f"Monte Carlo simulation {i+1}/{configuration.num_simulations}")
            
            # Bootstrap historical data
            bootstrapped_data = self._bootstrap_data(historical_data)
            
            # Generate signals for bootstrapped data
            signals = await self._generate_signals(
                strategy_function, configuration, bootstrapped_data, strategy_params
            )
            
            # Simulate trading
            simulation_result = await self._simulate_trading(
                signals, configuration, bootstrapped_data
            )
            
            simulation_results.append(simulation_result)
        
        # Calculate percentile results
        percentile_results = self._calculate_percentile_results(
            simulation_results, configuration.confidence_levels
        )
        
        # Calculate mean result as overall result
        overall_result = self._calculate_mean_result(simulation_results, configuration)
        
        result = BacktestResult(
            configuration=configuration,
            method=BacktestMethod.MONTE_CARLO,
            overall_result=overall_result,
            simulation_results=simulation_results,
            percentile_results=percentile_results
        )
        
        return result
    
    async def _run_bootstrap_backtest(
        self,
        strategy_function: Callable,
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        strategy_params: Dict[str, Any]
    ) -> BacktestResult:
        """Run bootstrap backtesting."""
        logger.info(f"Running bootstrap backtesting with {configuration.num_simulations} bootstrap samples")
        
        # Similar to Monte Carlo but focuses on statistical significance
        simulation_results = []
        
        for i in range(configuration.num_simulations):
            # Bootstrap with replacement
            bootstrapped_data = self._bootstrap_data(historical_data, replacement=True)
            
            # Generate signals
            signals = await self._generate_signals(
                strategy_function, configuration, bootstrapped_data, strategy_params
            )
            
            # Simulate trading
            result = await self._simulate_trading(
                signals, configuration, bootstrapped_data
            )
            
            simulation_results.append(result)
        
        # Calculate statistical significance
        returns = [r.total_return for r in simulation_results]
        p_value = self.statistical_testing.calculate_p_value(returns)
        
        # Calculate confidence intervals
        confidence_intervals = {}
        for confidence_level in configuration.confidence_levels:
            ci = self._calculate_confidence_interval(returns, confidence_level)
            confidence_intervals[confidence_level] = ci
        
        overall_result = self._calculate_mean_result(simulation_results, configuration)
        overall_result.statistical_significance = 1 - p_value if p_value else None
        overall_result.p_value = p_value
        
        result = BacktestResult(
            configuration=configuration,
            method=BacktestMethod.BOOTSTRAP,
            overall_result=overall_result,
            simulation_results=simulation_results
        )
        
        return result
    
    async def _run_cross_validation_backtest(
        self,
        strategy_function: Callable,
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        strategy_params: Dict[str, Any]
    ) -> BacktestResult:
        """Run cross-validation backtesting."""
        logger.info(f"Running {configuration.num_folds}-fold cross-validation backtesting")
        
        # Split data into folds
        data_folds = self._create_time_series_folds(historical_data, configuration.num_folds)
        
        fold_results = []
        
        for i, (train_data, test_data) in enumerate(data_folds):
            logger.debug(f"Cross-validation fold {i+1}/{configuration.num_folds}")
            
            # Generate signals for training data
            train_signals = await self._generate_signals(
                strategy_function, configuration, train_data, strategy_params
            )
            
            # Generate signals for test data
            test_signals = await self._generate_signals(
                strategy_function, configuration, test_data, strategy_params
            )
            
            # Simulate trading on test data
            fold_result = await self._simulate_trading(
                test_signals, configuration, test_data
            )
            
            fold_results.append(fold_result)
        
        # Calculate overall result as mean of fold results
        overall_result = self._combine_period_results(fold_results, configuration)
        
        result = BacktestResult(
            configuration=configuration,
            method=BacktestMethod.CROSS_VALIDATION,
            overall_result=overall_result,
            fold_results=fold_results
        )
        
        return result
    
    async def _generate_signals(
        self,
        strategy_function: Callable,
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        strategy_params: Dict[str, Any]
    ) -> List[TradeSignal]:
        """Generate trading signals using the strategy function."""
        signals = []
        
        # Create date range for signal generation
        current_date = configuration.start_date
        end_date = configuration.end_date
        
        while current_date <= end_date:
            current_datetime = datetime.combine(current_date, datetime.min.time())
            
            # Generate signals for each time-bin on this date
            for time_bin, trades in historical_data.items():
                try:
                    # Get historical context for strategy function
                    context = {
                        'historical_trades': trades,
                        'current_date': current_date,
                        'configuration': configuration,
                        **strategy_params
                    }
                    
                    # Call strategy function to get signal
                    signal = strategy_function(time_bin, current_datetime, context)
                    
                    if signal and signal.signal_type != 'HOLD':
                        signals.append(signal)
                        
                except Exception as e:
                    logger.warning(f"Strategy function failed for {time_bin} on {current_date}: {str(e)}")
            
            current_date += timedelta(days=1)
        
        logger.debug(f"Generated {len(signals)} trading signals")
        return signals
    
    async def _simulate_trading(
        self,
        signals: List[TradeSignal],
        configuration: BacktestConfiguration,
        historical_data: Dict[TimeBin, List[ProcessedTrade]]
    ) -> BacktestPeriodResult:
        """Simulate trading based on signals."""
        capital = configuration.initial_capital
        open_positions: Dict[TimeBin, BacktestTrade] = {}
        closed_trades = []
        daily_values = []
        
        # Sort signals by timestamp
        signals.sort(key=lambda x: x.timestamp)
        
        for signal in signals:
            try:
                if signal.signal_type == 'BUY' and signal.time_bin not in open_positions:
                    # Open long position
                    trade = self._open_position(signal, capital, configuration)
                    if trade:
                        open_positions[signal.time_bin] = trade
                        capital -= trade.entry_price * trade.quantity + trade.commission + trade.slippage
                
                elif signal.signal_type == 'SELL' and signal.time_bin in open_positions:
                    # Close position
                    open_trade = open_positions[signal.time_bin]
                    closed_trade = self._close_position(
                        open_trade, signal, configuration
                    )
                    if closed_trade:
                        closed_trades.append(closed_trade)
                        capital += closed_trade.exit_price * closed_trade.quantity - closed_trade.commission - closed_trade.slippage
                        del open_positions[signal.time_bin]
                
            except Exception as e:
                logger.warning(f"Failed to process signal {signal}: {str(e)}")
        
        # Close any remaining open positions at the end
        for time_bin, open_trade in open_positions.items():
            # Use last available price or entry price
            exit_signal = TradeSignal(
                timestamp=datetime.combine(configuration.end_date, datetime.max.time()),
                time_bin=time_bin,
                signal_type='SELL',
                confidence=0.5,
                price=open_trade.entry_price  # Use entry price as fallback
            )
            
            closed_trade = self._close_position(open_trade, exit_signal, configuration)
            if closed_trade:
                closed_trades.append(closed_trade)
                capital += closed_trade.exit_price * closed_trade.quantity
        
        # Calculate performance metrics
        result = self._calculate_performance_metrics(
            closed_trades, configuration.initial_capital, capital, configuration
        )
        
        return result
    
    def _open_position(
        self, 
        signal: TradeSignal, 
        available_capital: float, 
        configuration: BacktestConfiguration
    ) -> Optional[BacktestTrade]:
        """Open a trading position."""
        if not signal.price:
            return None
        
        # Calculate position size (simple equal weighting for now)
        position_value = available_capital * 0.1  # 10% per position
        quantity = int(position_value / signal.price)
        
        if quantity == 0:
            return None
        
        # Calculate costs
        commission = configuration.commission_per_trade
        slippage = signal.price * (configuration.slippage_bps / 10000) * quantity
        
        trade = BacktestTrade(
            entry_time=signal.timestamp,
            exit_time=None,
            time_bin=signal.time_bin,
            entry_price=signal.price,
            exit_price=None,
            quantity=quantity,
            trade_type='LONG',
            commission=commission,
            slippage=slippage,
            is_closed=False,
            metadata=signal.metadata.copy()
        )
        
        return trade
    
    def _close_position(
        self, 
        open_trade: BacktestTrade, 
        signal: TradeSignal, 
        configuration: BacktestConfiguration
    ) -> BacktestTrade:
        """Close a trading position."""
        exit_price = signal.price or open_trade.entry_price
        
        # Calculate additional costs
        commission = configuration.commission_per_trade
        slippage = exit_price * (configuration.slippage_bps / 10000) * open_trade.quantity
        
        # Calculate P&L
        pnl = (exit_price - open_trade.entry_price) * open_trade.quantity
        pnl -= (open_trade.commission + commission + open_trade.slippage + slippage)
        
        # Update trade
        open_trade.exit_time = signal.timestamp
        open_trade.exit_price = exit_price
        open_trade.pnl = pnl
        open_trade.commission += commission
        open_trade.slippage += slippage
        open_trade.is_closed = True
        
        return open_trade
    
    def _calculate_performance_metrics(
        self,
        trades: List[BacktestTrade],
        initial_capital: float,
        final_capital: float,
        configuration: BacktestConfiguration
    ) -> BacktestPeriodResult:
        """Calculate comprehensive performance metrics."""
        if not trades:
            return BacktestPeriodResult(
                start_date=configuration.start_date,
                end_date=configuration.end_date,
                initial_capital=initial_capital,
                final_capital=final_capital,
                total_return=0.0,
                num_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_trade_pnl=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                profit_factor=None,
                win_rate=0.0,
                total_commission=0.0,
                total_slippage=0.0
            )
        
        # Basic metrics
        total_return = (final_capital - initial_capital) / initial_capital
        num_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        win_rate = winning_trades / num_trades if num_trades > 0 else 0.0
        
        # P&L metrics
        pnls = [t.pnl for t in trades if t.pnl is not None]
        avg_trade_pnl = statistics.mean(pnls) if pnls else 0.0
        
        # Cost metrics
        total_commission = sum(t.commission for t in trades)
        total_slippage = sum(t.slippage for t in trades)
        
        # Risk metrics
        winning_pnls = [p for p in pnls if p > 0]
        losing_pnls = [p for p in pnls if p < 0]
        
        profit_factor = None
        if losing_pnls:
            total_wins = sum(winning_pnls)
            total_losses = abs(sum(losing_pnls))
            profit_factor = total_wins / total_losses if total_losses > 0 else None
        
        # Calculate drawdown (simplified)
        running_capital = initial_capital
        peak_capital = initial_capital
        max_drawdown = 0.0
        
        for trade in sorted(trades, key=lambda t: t.exit_time or t.entry_time):
            if trade.pnl:
                running_capital += trade.pnl
                peak_capital = max(peak_capital, running_capital)
                drawdown = (peak_capital - running_capital) / peak_capital
                max_drawdown = max(max_drawdown, drawdown)
        
        # Sharpe ratio (simplified daily calculation)
        if len(pnls) > 1:
            daily_return_std = statistics.stdev(pnls)
            if daily_return_std > 0:
                excess_return = avg_trade_pnl - (configuration.risk_free_rate / 252)
                sharpe_ratio = excess_return / daily_return_std * np.sqrt(252)  # Annualized
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = None
        
        # Sortino ratio (using only downside deviation)
        downside_pnls = [p for p in pnls if p < 0]
        sortino_ratio = None
        if downside_pnls and len(downside_pnls) > 1:
            downside_std = statistics.stdev(downside_pnls)
            if downside_std > 0:
                excess_return = avg_trade_pnl - (configuration.risk_free_rate / 252)
                sortino_ratio = excess_return / downside_std * np.sqrt(252)
        
        result = BacktestPeriodResult(
            start_date=configuration.start_date,
            end_date=configuration.end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            num_trades=num_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_trade_pnl=avg_trade_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            profit_factor=profit_factor,
            win_rate=win_rate,
            total_commission=total_commission,
            total_slippage=total_slippage,
            daily_returns=pnls,  # Using trade PnLs as proxy for daily returns
            trades=trades
        )
        
        return result
    
    def _generate_walk_forward_ranges(
        self, 
        configuration: BacktestConfiguration
    ) -> List[Tuple[date, date, date, date]]:
        """Generate date ranges for walk-forward analysis."""
        ranges = []
        
        start_date = configuration.start_date
        end_date = configuration.end_date
        
        current_date = start_date
        
        while current_date < end_date:
            # Training period
            train_start = current_date
            train_end = train_start + timedelta(days=configuration.training_days)
            
            # Testing period
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=configuration.testing_days)
            
            # Make sure we don't go beyond the end date
            if test_end > end_date:
                test_end = end_date
            
            if test_start < end_date:
                ranges.append((train_start, train_end, test_start, test_end))
            
            # Move forward by rebalance frequency
            current_date += timedelta(days=configuration.rebalance_frequency)
        
        return ranges
    
    def _filter_data_by_date(
        self,
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        start_date: date,
        end_date: date
    ) -> Dict[TimeBin, List[ProcessedTrade]]:
        """Filter historical data by date range."""
        filtered_data = {}
        
        for time_bin, trades in historical_data.items():
            filtered_trades = [
                trade for trade in trades
                if start_date <= trade.trade_date.date() <= end_date
            ]
            filtered_data[time_bin] = filtered_trades
        
        return filtered_data
    
    def _bootstrap_data(
        self, 
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        replacement: bool = True
    ) -> Dict[TimeBin, List[ProcessedTrade]]:
        """Bootstrap historical data for Monte Carlo simulation."""
        bootstrapped_data = {}
        
        for time_bin, trades in historical_data.items():
            if not trades:
                bootstrapped_data[time_bin] = []
                continue
            
            if replacement:
                # Bootstrap with replacement
                n_samples = len(trades)
                indices = np.random.choice(len(trades), size=n_samples, replace=True)
                bootstrapped_trades = [trades[i] for i in indices]
            else:
                # Shuffle without replacement
                bootstrapped_trades = trades.copy()
                np.random.shuffle(bootstrapped_trades)
            
            bootstrapped_data[time_bin] = bootstrapped_trades
        
        return bootstrapped_data
    
    def _combine_period_results(
        self, 
        period_results: List[BacktestPeriodResult],
        configuration: BacktestConfiguration
    ) -> BacktestPeriodResult:
        """Combine multiple period results into overall result."""
        if not period_results:
            return BacktestPeriodResult(
                start_date=configuration.start_date,
                end_date=configuration.end_date,
                initial_capital=configuration.initial_capital,
                final_capital=configuration.initial_capital,
                total_return=0.0,
                num_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_trade_pnl=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                profit_factor=None,
                win_rate=0.0,
                total_commission=0.0,
                total_slippage=0.0
            )
        
        # Aggregate metrics
        total_trades = sum(r.num_trades for r in period_results)
        total_winning = sum(r.winning_trades for r in period_results)
        total_losing = sum(r.losing_trades for r in period_results)
        
        # Calculate overall return (compounded)
        cumulative_return = 1.0
        for result in period_results:
            cumulative_return *= (1.0 + result.total_return)
        overall_return = cumulative_return - 1.0
        
        # Average metrics
        avg_metrics = {
            'avg_trade_pnl': statistics.mean([r.avg_trade_pnl for r in period_results if r.num_trades > 0]),
            'max_drawdown': max([r.max_drawdown for r in period_results]),
            'win_rate': total_winning / total_trades if total_trades > 0 else 0.0,
            'total_commission': sum(r.total_commission for r in period_results),
            'total_slippage': sum(r.total_slippage for r in period_results)
        }
        
        # Risk metrics (average of available values)
        sharpe_ratios = [r.sharpe_ratio for r in period_results if r.sharpe_ratio is not None]
        sortino_ratios = [r.sortino_ratio for r in period_results if r.sortino_ratio is not None]
        profit_factors = [r.profit_factor for r in period_results if r.profit_factor is not None]
        
        combined_result = BacktestPeriodResult(
            start_date=configuration.start_date,
            end_date=configuration.end_date,
            initial_capital=configuration.initial_capital,
            final_capital=configuration.initial_capital * (1.0 + overall_return),
            total_return=overall_return,
            num_trades=total_trades,
            winning_trades=total_winning,
            losing_trades=total_losing,
            avg_trade_pnl=avg_metrics['avg_trade_pnl'],
            max_drawdown=avg_metrics['max_drawdown'],
            sharpe_ratio=statistics.mean(sharpe_ratios) if sharpe_ratios else None,
            sortino_ratio=statistics.mean(sortino_ratios) if sortino_ratios else None,
            profit_factor=statistics.mean(profit_factors) if profit_factors else None,
            win_rate=avg_metrics['win_rate'],
            total_commission=avg_metrics['total_commission'],
            total_slippage=avg_metrics['total_slippage']
        )
        
        return combined_result
    
    def _calculate_percentile_results(
        self, 
        simulation_results: List[BacktestPeriodResult],
        confidence_levels: List[float]
    ) -> Dict[float, BacktestPeriodResult]:
        """Calculate percentile results for Monte Carlo simulations."""
        percentile_results = {}
        
        # Sort results by total return
        sorted_results = sorted(simulation_results, key=lambda x: x.total_return)
        
        for confidence_level in confidence_levels:
            # Calculate percentile index
            percentile = (1.0 - confidence_level) / 2.0  # Two-tailed
            lower_idx = int(len(sorted_results) * percentile)
            upper_idx = int(len(sorted_results) * (1.0 - percentile))
            
            # Get percentile results
            lower_result = sorted_results[lower_idx]
            upper_result = sorted_results[upper_idx]
            
            percentile_results[confidence_level] = {
                'lower': lower_result,
                'upper': upper_result
            }
        
        return percentile_results
    
    def _calculate_mean_result(
        self, 
        simulation_results: List[BacktestPeriodResult],
        configuration: BacktestConfiguration
    ) -> BacktestPeriodResult:
        """Calculate mean result from simulations."""
        if not simulation_results:
            return BacktestPeriodResult(
                start_date=configuration.start_date,
                end_date=configuration.end_date,
                initial_capital=configuration.initial_capital,
                final_capital=configuration.initial_capital,
                total_return=0.0,
                num_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_trade_pnl=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                profit_factor=None,
                win_rate=0.0,
                total_commission=0.0,
                total_slippage=0.0
            )
        
        # Calculate mean of all metrics
        mean_result = BacktestPeriodResult(
            start_date=configuration.start_date,
            end_date=configuration.end_date,
            initial_capital=configuration.initial_capital,
            final_capital=statistics.mean([r.final_capital for r in simulation_results]),
            total_return=statistics.mean([r.total_return for r in simulation_results]),
            num_trades=int(statistics.mean([r.num_trades for r in simulation_results])),
            winning_trades=int(statistics.mean([r.winning_trades for r in simulation_results])),
            losing_trades=int(statistics.mean([r.losing_trades for r in simulation_results])),
            avg_trade_pnl=statistics.mean([r.avg_trade_pnl for r in simulation_results]),
            max_drawdown=statistics.mean([r.max_drawdown for r in simulation_results]),
            sharpe_ratio=statistics.mean([r.sharpe_ratio for r in simulation_results if r.sharpe_ratio is not None]) or None,
            sortino_ratio=statistics.mean([r.sortino_ratio for r in simulation_results if r.sortino_ratio is not None]) or None,
            profit_factor=statistics.mean([r.profit_factor for r in simulation_results if r.profit_factor is not None]) or None,
            win_rate=statistics.mean([r.win_rate for r in simulation_results]),
            total_commission=statistics.mean([r.total_commission for r in simulation_results]),
            total_slippage=statistics.mean([r.total_slippage for r in simulation_results])
        )
        
        return mean_result
    
    def _calculate_confidence_interval(
        self, 
        values: List[float], 
        confidence_level: float
    ) -> Tuple[float, float]:
        """Calculate confidence interval for a list of values."""
        if len(values) < 2:
            return (0.0, 0.0)
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Calculate percentile indices
        alpha = 1.0 - confidence_level
        lower_idx = int(n * alpha / 2.0)
        upper_idx = int(n * (1.0 - alpha / 2.0))
        
        lower_bound = sorted_values[max(0, lower_idx)]
        upper_bound = sorted_values[min(n-1, upper_idx)]
        
        return (lower_bound, upper_bound)
    
    def _create_time_series_folds(
        self, 
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        num_folds: int
    ) -> List[Tuple[Dict[TimeBin, List[ProcessedTrade]], Dict[TimeBin, List[ProcessedTrade]]]]:
        """Create time-series folds for cross-validation."""
        # Get all unique dates across all time-bins
        all_dates = set()
        for trades in historical_data.values():
            for trade in trades:
                all_dates.add(trade.trade_date.date())
        
        sorted_dates = sorted(all_dates)
        
        if len(sorted_dates) < num_folds:
            num_folds = len(sorted_dates)
        
        fold_size = len(sorted_dates) // num_folds
        folds = []
        
        for i in range(num_folds):
            # Create test set for this fold
            test_start_idx = i * fold_size
            test_end_idx = min((i + 1) * fold_size, len(sorted_dates))
            test_dates = set(sorted_dates[test_start_idx:test_end_idx])
            
            # Create train set (all other dates)
            train_dates = set(sorted_dates) - test_dates
            
            # Filter data by dates
            train_data = {}
            test_data = {}
            
            for time_bin, trades in historical_data.items():
                train_trades = [t for t in trades if t.trade_date.date() in train_dates]
                test_trades = [t for t in trades if t.trade_date.date() in test_dates]
                
                train_data[time_bin] = train_trades
                test_data[time_bin] = test_trades
            
            folds.append((train_data, test_data))
        
        return folds
    
    async def _compare_to_benchmark(
        self, 
        result: BacktestResult, 
        configuration: BacktestConfiguration
    ) -> Dict[str, Any]:
        """Compare backtest results to benchmark."""
        # This would typically fetch benchmark data and calculate comparison metrics
        # For now, we'll return a placeholder structure
        
        benchmark_comparison = {
            'benchmark_symbol': configuration.benchmark_symbol,
            'strategy_return': result.overall_result.total_return,
            'benchmark_return': None,  # Would be calculated from real benchmark data
            'alpha': None,
            'beta': None,
            'information_ratio': None,
            'tracking_error': None,
            'correlation': None
        }
        
        return benchmark_comparison
    
    def save_results(self, result: BacktestResult, filepath: str) -> None:
        """Save backtesting results to file."""
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(result, f)
            logger.info(f"Backtesting results saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
    
    def load_results(self, filepath: str) -> BacktestResult:
        """Load backtesting results from file."""
        try:
            with open(filepath, 'rb') as f:
                result = pickle.load(f)
            logger.info(f"Backtesting results loaded from {filepath}")
            return result
        except Exception as e:
            logger.error(f"Failed to load results: {str(e)}")
            raise
    
    def __del__(self):
        """Cleanup executor on destruction."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)