"""
Unit tests for the PerformanceMetricsCalculator service.

Tests all metric calculations including Sharpe ratio, max drawdown, win rate,
volatility, profit factor, and other trading-specific metrics.

This is part of task 5.1: Create performance metrics calculator
Requirements: 3.1, 3.4
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import List

from trading_platform.services.performance_metrics_calculator import (
    PerformanceMetricsCalculator,
    PerformanceMetricsCalculatorError,
    DrawdownPeriod,
    RiskMetrics
)
from trading_platform.models.trading import ProcessedTrade


class TestPerformanceMetricsCalculator:
    """Test suite for PerformanceMetricsCalculator."""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator instance for testing."""
        return PerformanceMetricsCalculator(risk_free_rate=0.02)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for testing."""
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        # Create a mix of winning and losing trades with correct P&L calculations
        # P&L = (exit_price - entry_price) * quantity - commission for LONG
        trade_data = [
            (100.0, 101.0, 'LONG', -1.0),   # (101-100)*1 - 2 = -1
            (200.0, 199.0, 'LONG', -3.0),   # (199-200)*1 - 2 = -3
            (150.0, 152.0, 'LONG', 0.0),    # (152-150)*1 - 2 = 0
            (180.0, 175.0, 'LONG', -7.0),   # (175-180)*1 - 2 = -7
            (120.0, 125.0, 'LONG', 3.0),    # (125-120)*1 - 2 = 3
        ]
        
        for i, (entry_price, exit_price, side, pnl) in enumerate(trade_data):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"TEST_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side=side,
                profit_loss=pnl,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def profitable_trades(self):
        """Create only profitable trades for testing."""
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        for i in range(5):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"PROFIT_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=100.0,
                exit_price=103.0,  # (103-100)*1 - 2 = 1.0 profit
                quantity=1,
                side='LONG',
                profit_loss=1.0,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def losing_trades(self):
        """Create only losing trades for testing."""
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        for i in range(3):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"LOSS_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=100.0,
                exit_price=99.0,  # (99-100)*1 - 2 = -3.0 loss
                quantity=1,
                side='LONG',
                profit_loss=-3.0,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def short_trades(self):
        """Create SHORT trades for testing."""
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        # SHORT trades: P&L = (entry_price - exit_price) * quantity - commission
        trade_data = [
            (100.0, 98.0, 'SHORT', 0.0),    # (100-98)*1 - 2 = 0
            (200.0, 195.0, 'SHORT', 3.0),   # (200-195)*1 - 2 = 3
            (150.0, 155.0, 'SHORT', -7.0),  # (150-155)*1 - 2 = -7
        ]
        
        for i, (entry_price, exit_price, side, pnl) in enumerate(trade_data):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"SHORT_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side=side,
                profit_loss=pnl,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    def test_calculate_performance_metrics_basic(self, calculator, sample_trades):
        """Test basic performance metrics calculation."""
        metrics = calculator.calculate_performance_metrics(
            trades=sample_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        # Verify basic fields
        assert metrics.account_name == "TEST_ACCOUNT"
        assert metrics.symbol == "NQ"
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 1  # Only one positive trade (3.0)
        assert metrics.losing_trades == 4   # Four negative/zero trades
        
        # Verify calculations - actual P&L: -1, -3, 0, -7, 3 = -8
        assert metrics.total_return == -8.0
        assert metrics.win_rate == 0.2  # 1/5
        assert metrics.average_win == 3.0  # Only one win of 3.0
        assert metrics.average_loss == pytest.approx(-2.75, rel=1e-2)  # (-1 + -3 + 0 + -7) / 4
        assert metrics.largest_win == 3.0
        assert metrics.largest_loss == -7.0
        
        # Profit factor = gross profit / gross loss
        expected_profit_factor = 3.0 / 11.0  # 3.0 / (1+3+0+7)
        assert metrics.profit_factor == pytest.approx(expected_profit_factor, rel=1e-3)
    
    def test_calculate_performance_metrics_all_winners(self, calculator, profitable_trades):
        """Test metrics calculation with only winning trades."""
        metrics = calculator.calculate_performance_metrics(
            trades=profitable_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 5
        assert metrics.losing_trades == 0
        assert metrics.win_rate == 1.0
        assert metrics.total_return == 5.0  # 5 trades * 1.0 profit each
        assert metrics.average_win == 1.0
        assert metrics.average_loss == 0.0
        assert metrics.profit_factor == float('inf')  # No losses
        assert metrics.largest_loss == 0.0
    
    def test_calculate_performance_metrics_all_losers(self, calculator, losing_trades):
        """Test metrics calculation with only losing trades."""
        metrics = calculator.calculate_performance_metrics(
            trades=losing_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 3
        assert metrics.win_rate == 0.0
        assert metrics.total_return == -9.0  # 3 trades * -3.0 loss each
        assert metrics.average_win == 0.0
        assert metrics.average_loss == -3.0
        assert metrics.profit_factor == 0.0  # No profits
        assert metrics.largest_win == 0.0
    
    def test_calculate_performance_metrics_short_trades(self, calculator, short_trades):
        """Test metrics calculation with SHORT trades."""
        metrics = calculator.calculate_performance_metrics(
            trades=short_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        # P&L: 0, 3, -7 = -4
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 1  # One positive trade (3.0)
        assert metrics.losing_trades == 2   # Two negative/zero trades
        assert metrics.total_return == -4.0
        assert metrics.win_rate == pytest.approx(1/3, rel=1e-3)
        assert metrics.average_win == 3.0
        assert metrics.average_loss == pytest.approx(-3.5, rel=1e-2)  # (0 + -7) / 2
    
    def test_calculate_volatility(self, calculator):
        """Test volatility calculation."""
        returns = [100.0, -50.0, 200.0, -100.0, 150.0]
        volatility = calculator._calculate_volatility(returns)
        
        expected_volatility = np.std(returns, ddof=1)
        assert volatility == pytest.approx(expected_volatility, rel=1e-6)
    
    def test_calculate_volatility_edge_cases(self, calculator):
        """Test volatility calculation edge cases."""
        # Empty list
        assert calculator._calculate_volatility([]) == 0.0
        
        # Single value
        assert calculator._calculate_volatility([100.0]) == 0.0
        
        # All same values
        assert calculator._calculate_volatility([100.0, 100.0, 100.0]) == 0.0
    
    def test_calculate_sharpe_ratio(self, calculator):
        """Test Sharpe ratio calculation."""
        returns = [100.0, -50.0, 200.0, -100.0, 150.0]
        volatility = np.std(returns, ddof=1)
        
        sharpe = calculator._calculate_sharpe_ratio(returns, volatility)
        
        mean_return = np.mean(returns)
        risk_free_per_trade = calculator.risk_free_rate / 252
        expected_sharpe = (mean_return - risk_free_per_trade) / volatility
        
        assert sharpe == pytest.approx(expected_sharpe, rel=1e-6)
    
    def test_calculate_sharpe_ratio_edge_cases(self, calculator):
        """Test Sharpe ratio calculation edge cases."""
        # Zero volatility
        assert calculator._calculate_sharpe_ratio([100.0, 100.0], 0.0) is None
        
        # Empty returns
        assert calculator._calculate_sharpe_ratio([], 10.0) is None
    
    def test_calculate_max_drawdown(self, calculator):
        """Test maximum drawdown calculation."""
        # Create trades with known drawdown pattern
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        # Create trades with realistic P&L that matches entry/exit prices
        # P&L sequence: +100, +200, -150, -100, +300
        # We need to adjust entry/exit prices to match these P&L values
        trade_data = [
            (100.0, 202.0, 100.0),   # (202-100)*1 - 2 = 100
            (100.0, 302.0, 200.0),   # (302-100)*1 - 2 = 200  
            (100.0, 48.0, -54.0),    # (48-100)*1 - 2 = -54 (close to -50)
            (100.0, 2.0, -100.0),    # (2-100)*1 - 2 = -100
            (100.0, 402.0, 300.0),   # (402-100)*1 - 2 = 300
        ]
        
        for i, (entry_price, exit_price, pnl) in enumerate(trade_data):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"DD_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side='LONG',
                profit_loss=pnl,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        # Cumulative P&L: 100, 300, 246, 146, 446
        # Peak at 300, trough at 146, drawdown = 154
        max_drawdown = calculator._calculate_max_drawdown(trades)
        assert max_drawdown == -154.0  # Negative value by convention
    
    def test_calculate_max_drawdown_no_drawdown(self, calculator, profitable_trades):
        """Test max drawdown with only profitable trades."""
        max_drawdown = calculator._calculate_max_drawdown(profitable_trades)
        assert max_drawdown == 0.0  # No drawdown with only profits
    
    def test_calculate_var(self, calculator):
        """Test Value at Risk calculation."""
        returns = [-100.0, -50.0, 0.0, 50.0, 100.0, 150.0, 200.0]
        
        var_95 = calculator._calculate_var(returns, 0.95)
        var_99 = calculator._calculate_var(returns, 0.99)
        
        # For 95% confidence, we expect 5% worst returns
        # With 7 returns, 5% = 0.35, so index 0 (worst return)
        assert var_95 == -100.0
        
        # For 99% confidence, we expect 1% worst returns
        # With 7 returns, 1% = 0.07, so index 0 (worst return)
        assert var_99 == -100.0
    
    def test_calculate_expected_shortfall(self, calculator):
        """Test Expected Shortfall calculation."""
        returns = [-100.0, -80.0, -50.0, 0.0, 50.0, 100.0, 150.0]
        
        es_95 = calculator._calculate_expected_shortfall(returns, 0.95)
        
        # ES should be the average of returns at or below VaR
        var_95 = calculator._calculate_var(returns, 0.95)
        tail_returns = [r for r in returns if r <= var_95]
        expected_es = np.mean(tail_returns)
        
        assert es_95 == pytest.approx(expected_es, rel=1e-6)
    
    def test_calculate_risk_metrics(self, calculator, sample_trades):
        """Test comprehensive risk metrics calculation."""
        risk_metrics = calculator.calculate_risk_metrics(sample_trades)
        
        assert isinstance(risk_metrics, RiskMetrics)
        assert risk_metrics.value_at_risk_95 is not None
        assert risk_metrics.value_at_risk_99 is not None
        assert risk_metrics.expected_shortfall_95 is not None
        assert risk_metrics.expected_shortfall_99 is not None
        assert risk_metrics.downside_deviation >= 0.0
        assert isinstance(risk_metrics.sortino_ratio, float)
        assert isinstance(risk_metrics.calmar_ratio, float)
    
    def test_calculate_risk_metrics_comprehensive(self, calculator):
        """Test comprehensive risk metrics with known values."""
        # Create trades with predictable risk characteristics
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        # Create trades with known P&L distribution
        pnl_values = [-100, -50, -25, 0, 25, 50, 100, 150, 200]
        
        for i, pnl in enumerate(pnl_values):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            # Calculate exit price to match desired P&L
            entry_price = 100.0
            if pnl >= 0:
                exit_price = entry_price + (pnl + 2.0)  # LONG: (exit-entry)*1 - 2 = pnl
                side = 'LONG'
            else:
                exit_price = entry_price - (pnl + 2.0)  # SHORT: (entry-exit)*1 - 2 = pnl
                side = 'SHORT'
            
            trade = ProcessedTrade(
                trade_id=f"RISK_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side=side,
                profit_loss=pnl,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        risk_metrics = calculator.calculate_risk_metrics(trades)
        
        # VaR 95% should be around the 5th percentile
        assert risk_metrics.value_at_risk_95 <= -50  # Should be one of the worst returns
        
        # VaR 99% should be even worse
        assert risk_metrics.value_at_risk_99 <= risk_metrics.value_at_risk_95
        
        # Expected shortfall should be worse than VaR
        assert risk_metrics.expected_shortfall_95 <= risk_metrics.value_at_risk_95
        assert risk_metrics.expected_shortfall_99 <= risk_metrics.value_at_risk_99
        
        # Downside deviation should only consider negative returns
        negative_returns = [r for r in pnl_values if r < 0]
        expected_downside_dev = np.std(negative_returns) if negative_returns else 0.0
        assert risk_metrics.downside_deviation == pytest.approx(expected_downside_dev, rel=1e-2)
    
    def test_calculate_drawdown_periods(self, calculator):
        """Test drawdown periods calculation."""
        # Create trades with multiple drawdown periods
        base_time = datetime(2024, 1, 1, 9, 30)
        trades = []
        
        # Create trades with realistic P&L that matches entry/exit prices
        # Target P&L: +100, +100, -50, -100, +200, -75, +150
        trade_data = [
            (100.0, 202.0, 100.0),   # (202-100)*1 - 2 = 100
            (100.0, 202.0, 100.0),   # (202-100)*1 - 2 = 100
            (100.0, 52.0, -50.0),    # (52-100)*1 - 2 = -50
            (100.0, 2.0, -100.0),    # (2-100)*1 - 2 = -100
            (100.0, 302.0, 200.0),   # (302-100)*1 - 2 = 200
            (100.0, 27.0, -75.0),    # (27-100)*1 - 2 = -75
            (100.0, 252.0, 150.0),   # (252-100)*1 - 2 = 150
        ]
        
        for i, (entry_price, exit_price, pnl) in enumerate(trade_data):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"DD_{i+1}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side='LONG',
                profit_loss=pnl,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i+1}",
                exit_order_id=f"EXIT_{i+1}"
            )
            trades.append(trade)
        
        # Cumulative P&L: 100, 200, 150, 50, 250, 175, 325
        # Two drawdown periods: 200->50 and 250->175
        drawdown_periods = calculator.calculate_drawdown_periods(trades)
        
        assert len(drawdown_periods) == 2
        
        # First drawdown: 200 -> 50 = 150 drawdown
        first_dd = drawdown_periods[0]
        assert first_dd.peak_value == 200.0
        assert first_dd.trough_value == 50.0
        assert first_dd.drawdown_amount == 150.0
        assert first_dd.drawdown_percent == 75.0  # 150/200 * 100
        
        # Second drawdown: 250 -> 175 = 75 drawdown
        second_dd = drawdown_periods[1]
        assert second_dd.peak_value == 250.0
        assert second_dd.trough_value == 175.0
        assert second_dd.drawdown_amount == 75.0
        assert second_dd.drawdown_percent == 30.0  # 75/250 * 100
    
    def test_calculate_monthly_returns(self, calculator):
        """Test monthly returns calculation."""
        # Create trades across different months
        trades = []
        
        # January trades - use realistic P&L values
        jan_trade1 = ProcessedTrade(
            trade_id="JAN_1",
            account_name="TEST_ACCOUNT",
            symbol="NQ",
            entry_time=datetime(2024, 1, 15, 9, 30),
            exit_time=datetime(2024, 1, 15, 10, 0),
            entry_price=100.0,
            exit_price=103.0,  # (103-100)*1 - 2 = 1.0
            quantity=1,
            side='LONG',
            profit_loss=1.0,
            commission=2.0,
            duration_minutes=30,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY_1",
            exit_order_id="EXIT_1"
        )
        
        jan_trade2 = ProcessedTrade(
            trade_id="JAN_2",
            account_name="TEST_ACCOUNT",
            symbol="NQ",
            entry_time=datetime(2024, 1, 20, 9, 30),
            exit_time=datetime(2024, 1, 20, 10, 0),
            entry_price=100.0,
            exit_price=99.0,  # (99-100)*1 - 2 = -3.0
            quantity=1,
            side='LONG',
            profit_loss=-3.0,
            commission=2.0,
            duration_minutes=30,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY_2",
            exit_order_id="EXIT_2"
        )
        
        # February trade
        feb_trade = ProcessedTrade(
            trade_id="FEB_1",
            account_name="TEST_ACCOUNT",
            symbol="NQ",
            entry_time=datetime(2024, 2, 10, 9, 30),
            exit_time=datetime(2024, 2, 10, 10, 0),
            entry_price=100.0,
            exit_price=107.0,  # (107-100)*1 - 2 = 5.0
            quantity=1,
            side='LONG',
            profit_loss=5.0,
            commission=2.0,
            duration_minutes=30,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY_3",
            exit_order_id="EXIT_3"
        )
        
        trades = [jan_trade1, jan_trade2, feb_trade]
        
        monthly_returns = calculator.calculate_monthly_returns(trades)
        
        assert monthly_returns["2024-01"] == -2.0  # 1.0 + (-3.0) = -2.0
        assert monthly_returns["2024-02"] == 5.0
    
    def test_calculate_rolling_metrics(self, calculator, sample_trades):
        """Test rolling metrics calculation."""
        rolling_metrics = calculator.calculate_rolling_metrics(
            trades=sample_trades,
            window_days=1
        )
        
        # Should have metrics for trades with sufficient history
        assert len(rolling_metrics) >= 2  # At least some rolling windows
        
        for date, rolling_return, rolling_sharpe, rolling_drawdown in rolling_metrics:
            assert isinstance(date, datetime)
            assert isinstance(rolling_return, float)
            assert rolling_sharpe is None or isinstance(rolling_sharpe, float)
            assert isinstance(rolling_drawdown, float)
    
    def test_calculate_rolling_metrics_different_windows(self, calculator, sample_trades):
        """Test rolling metrics with different window sizes."""
        # Test different window sizes
        for window_days in [1, 2, 3]:
            rolling_metrics = calculator.calculate_rolling_metrics(
                trades=sample_trades,
                window_days=window_days
            )
            
            # Larger windows should generally have fewer data points
            # (since we need more history for each calculation)
            assert isinstance(rolling_metrics, list)
            
            # Each metric should have the expected structure
            for metric in rolling_metrics:
                assert len(metric) == 4  # date, return, sharpe, drawdown
                assert isinstance(metric[0], datetime)
                assert isinstance(metric[1], float)
                assert metric[2] is None or isinstance(metric[2], float)
                assert isinstance(metric[3], float)
    
    def test_validate_trades_for_calculation(self, calculator, sample_trades):
        """Test trade validation for calculation."""
        # Valid trades should pass
        assert calculator.validate_trades_for_calculation(sample_trades) is True
        
        # Empty list should fail
        with pytest.raises(PerformanceMetricsCalculatorError):
            calculator.validate_trades_for_calculation([])
    
    def test_validate_trades_missing_fields(self, calculator):
        """Test validation with trades missing required fields."""
        # Create a trade with missing profit_loss
        incomplete_trade = ProcessedTrade(
            trade_id="INCOMPLETE",
            account_name="TEST_ACCOUNT",
            symbol="NQ",
            entry_time=datetime(2024, 1, 1, 9, 30),
            exit_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_price=101.0,
            quantity=1,
            side='LONG',
            profit_loss=-1.0,  # This will be set to None to test validation
            commission=2.0,
            duration_minutes=30,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY_1",
            exit_order_id="EXIT_1"
        )
        
        # Manually set profit_loss to None to test validation
        incomplete_trade.profit_loss = None
        
        with pytest.raises(PerformanceMetricsCalculatorError, match="missing profit_loss"):
            calculator.validate_trades_for_calculation([incomplete_trade])
    
    def test_calculate_performance_metrics_empty_trades(self, calculator):
        """Test error handling for empty trade list."""
        with pytest.raises(PerformanceMetricsCalculatorError):
            calculator.calculate_performance_metrics(
                trades=[],
                account_name="TEST_ACCOUNT",
                symbol="NQ"
            )
    
    def test_calculate_performance_metrics_with_period(self, calculator, sample_trades):
        """Test performance metrics calculation with specific period."""
        # Use a period that includes only first 3 trades
        period_start = sample_trades[0].entry_time
        period_end = sample_trades[2].exit_time
        
        metrics = calculator.calculate_performance_metrics(
            trades=sample_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ",
            period_start=period_start,
            period_end=period_end
        )
        
        # Should only include first 3 trades: -1, -3, 0 = -4
        assert metrics.total_trades == 3
        assert metrics.total_return == -4.0  # -1 + -3 + 0 = -4
        assert metrics.winning_trades == 0  # No positive trades in first 3
        assert metrics.losing_trades == 3   # All first 3 trades are negative/zero
    
    def test_performance_metrics_validation(self, calculator, sample_trades):
        """Test that calculated performance metrics pass validation."""
        metrics = calculator.calculate_performance_metrics(
            trades=sample_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        # The metrics should be valid (no validation errors)
        # This tests the integration with the PerformanceMetrics dataclass validation
        assert metrics.account_name == "TEST_ACCOUNT"
        assert metrics.symbol == "NQ"
        assert 0.0 <= metrics.win_rate <= 1.0
        assert metrics.winning_trades + metrics.losing_trades == metrics.total_trades
        assert metrics.volatility >= 0.0
        assert metrics.max_drawdown <= 0.0  # Should be negative or zero
    
    def test_risk_free_rate_configuration(self):
        """Test calculator with different risk-free rates."""
        calc1 = PerformanceMetricsCalculator(risk_free_rate=0.01)
        calc2 = PerformanceMetricsCalculator(risk_free_rate=0.05)
        
        assert calc1.risk_free_rate == 0.01
        assert calc2.risk_free_rate == 0.05
        
        # Sharpe ratios should be different with different risk-free rates
        returns = [100.0, -50.0, 200.0]
        volatility = np.std(returns, ddof=1)
        
        sharpe1 = calc1._calculate_sharpe_ratio(returns, volatility)
        sharpe2 = calc2._calculate_sharpe_ratio(returns, volatility)
        
        assert sharpe1 != sharpe2
    
    def test_edge_case_single_trade(self, calculator):
        """Test performance metrics with a single trade."""
        single_trade = ProcessedTrade(
            trade_id="SINGLE",
            account_name="TEST_ACCOUNT",
            symbol="NQ",
            entry_time=datetime(2024, 1, 1, 9, 30),
            exit_time=datetime(2024, 1, 1, 10, 0),
            entry_price=100.0,
            exit_price=105.0,  # (105-100)*1 - 2 = 3.0
            quantity=1,
            side='LONG',
            profit_loss=3.0,
            commission=2.0,
            duration_minutes=30,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY_1",
            exit_order_id="EXIT_1"
        )
        
        metrics = calculator.calculate_performance_metrics(
            trades=[single_trade],
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 0
        assert metrics.win_rate == 1.0
        assert metrics.total_return == 3.0
        assert metrics.volatility == 0.0  # Single trade has no volatility
        assert metrics.sharpe_ratio is None  # Can't calculate Sharpe with zero volatility
        assert metrics.max_drawdown == 0.0  # No drawdown with single profitable trade
    
    def test_performance_metrics_properties(self, calculator, sample_trades):
        """Test additional properties of PerformanceMetrics."""
        metrics = calculator.calculate_performance_metrics(
            trades=sample_trades,
            account_name="TEST_ACCOUNT",
            symbol="NQ"
        )
        
        # Test calculated properties
        expected_average_trade = metrics.total_return / metrics.total_trades
        assert metrics.average_trade == pytest.approx(expected_average_trade, rel=1e-6)
        
        # Test expectancy calculation
        expected_expectancy = (metrics.win_rate * metrics.average_win) - ((1 - metrics.win_rate) * abs(metrics.average_loss))
        assert metrics.expectancy == pytest.approx(expected_expectancy, rel=1e-6)
        
        # Test recovery factor
        if metrics.max_drawdown != 0:
            expected_recovery_factor = abs(metrics.total_return / metrics.max_drawdown)
            assert metrics.recovery_factor == pytest.approx(expected_recovery_factor, rel=1e-6)
        else:
            assert metrics.recovery_factor == 0.0


if __name__ == "__main__":
    pytest.main([__file__])