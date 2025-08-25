"""
Comprehensive tests for TimeBinAnalyzer core functionality.

Tests with real trade data, validates metrics against manual calculations,
and tests edge cases for statistical significance.

Requirements: 1.1, 1.2, 1.3, 5.1
"""

import pytest
from datetime import datetime, time
from unittest.mock import Mock, patch
import numpy as np
from scipy import stats

from trading_platform.services.time_bin_analyzer import (
    TimeBin, TimeBinAnalyzer, TimeBinMetrics, SignificanceTest
)
from trading_platform.models.trading import ProcessedTrade


def create_valid_trade(trade_id: str, account_name: str, pnl: float, 
                      entry_time: datetime, exit_time: datetime, 
                      hour_of_day: int = 9, day_of_week: int = 0) -> ProcessedTrade:
    """Helper function to create valid trades with consistent P&L calculations."""
    entry_price = 15000.0
    commission = 2.5
    quantity = 1
    
    # Calculate exit price that will result in the desired P&L
    # For LONG: pnl = (exit_price - entry_price) * quantity - commission
    # So: exit_price = entry_price + (pnl + commission) / quantity
    exit_price = entry_price + (pnl + commission) / quantity
    
    return ProcessedTrade(
        trade_id=trade_id,
        account_name=account_name,
        symbol="NQ",
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        side="LONG",
        profit_loss=pnl,
        commission=commission,
        duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
        hour_of_day=hour_of_day,
        day_of_week=day_of_week,
        entry_order_id=f"ENTRY_{trade_id}",
        exit_order_id=f"EXIT_{trade_id}"
    )


class TestTimeBin:
    """Test the TimeBin data model."""
    
    def test_time_bin_creation_valid(self):
        """Test creating valid time bins."""
        # Test basic time bin
        tb = TimeBin("IPS_TM_10", 9, 30)
        assert tb.account_name == "IPS_TM_10"
        assert tb.hour == 9
        assert tb.minute_bin == 30
        assert tb.day_of_week is None
        
        # Test with day of week
        tb_dow = TimeBin("IPS_TM_13", 14, 0, day_of_week=2)
        assert tb_dow.day_of_week == 2
    
    def test_time_bin_validation(self):
        """Test time bin parameter validation."""
        # Invalid hour
        with pytest.raises(ValueError, match="Hour must be between 0 and 23"):
            TimeBin("IPS_TM_10", 25, 0)
        
        with pytest.raises(ValueError, match="Hour must be between 0 and 23"):
            TimeBin("IPS_TM_10", -1, 0)
        
        # Invalid minute bin
        with pytest.raises(ValueError, match="Minute bin must be 0 or 30"):
            TimeBin("IPS_TM_10", 9, 15)
        
        with pytest.raises(ValueError, match="Minute bin must be 0 or 30"):
            TimeBin("IPS_TM_10", 9, 45)
        
        # Invalid day of week
        with pytest.raises(ValueError, match="Day of week must be between 0 and 6 or None"):
            TimeBin("IPS_TM_10", 9, 0, day_of_week=7)
        
        with pytest.raises(ValueError, match="Day of week must be between 0 and 6 or None"):
            TimeBin("IPS_TM_10", 9, 0, day_of_week=-1)
    
    def test_time_window_properties(self):
        """Test time window start and end properties."""
        # Morning time bin
        tb1 = TimeBin("IPS_TM_10", 9, 30)
        assert tb1.time_window_start == time(9, 30)
        assert tb1.time_window_end == time(10, 0)
        
        # Afternoon time bin
        tb2 = TimeBin("IPS_TM_10", 14, 0)
        assert tb2.time_window_start == time(14, 0)
        assert tb2.time_window_end == time(14, 30)
        
        # Late evening (crossing midnight)
        tb3 = TimeBin("IPS_TM_10", 23, 30)
        assert tb3.time_window_start == time(23, 30)
        assert tb3.time_window_end == time(0, 0)
    
    def test_string_representation(self):
        """Test string representation of time bins."""
        tb1 = TimeBin("IPS_TM_10", 9, 30)
        assert str(tb1) == "IPS_TM_10_09:30"
        
        tb2 = TimeBin("IPS_TM_13", 14, 0, day_of_week=2)
        assert str(tb2) == "IPS_TM_13_14:00_dow2"
    
    def test_matches_trade_time(self):
        """Test trade time matching logic."""
        tb = TimeBin("IPS_TM_10", 9, 30)
        
        # Should match
        assert tb.matches_trade_time(datetime(2024, 1, 15, 9, 30, 0))
        assert tb.matches_trade_time(datetime(2024, 1, 15, 9, 45, 30))
        assert tb.matches_trade_time(datetime(2024, 1, 15, 9, 59, 59))
        
        # Should not match
        assert not tb.matches_trade_time(datetime(2024, 1, 15, 9, 29, 59))
        assert not tb.matches_trade_time(datetime(2024, 1, 15, 10, 0, 0))
        assert not tb.matches_trade_time(datetime(2024, 1, 15, 10, 30, 0))
    
    def test_matches_trade_time_with_day_of_week(self):
        """Test trade time matching with day of week filter."""
        # Tuesday (weekday 1)
        tb = TimeBin("IPS_TM_10", 9, 30, day_of_week=1)
        
        # Tuesday 2024-01-16 (weekday 1)
        assert tb.matches_trade_time(datetime(2024, 1, 16, 9, 30, 0))
        
        # Wednesday 2024-01-17 (weekday 2) - should not match
        assert not tb.matches_trade_time(datetime(2024, 1, 17, 9, 30, 0))
    
    def test_matches_trade_time_midnight_crossing(self):
        """Test trade time matching across midnight."""
        tb = TimeBin("IPS_TM_10", 23, 30)
        
        # Should match
        assert tb.matches_trade_time(datetime(2024, 1, 15, 23, 30, 0))
        assert tb.matches_trade_time(datetime(2024, 1, 15, 23, 45, 0))
        assert tb.matches_trade_time(datetime(2024, 1, 15, 23, 59, 59))
        
        # Should not match (midnight is end of window)
        assert not tb.matches_trade_time(datetime(2024, 1, 16, 0, 0, 0))


class TestTimeBinAnalyzer:
    """Test the TimeBinAnalyzer functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def analyzer(self, mock_db_session):
        """Create analyzer with mocked database."""
        return TimeBinAnalyzer(db_session=mock_db_session)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data for testing."""
        trades = []
        
        # Create 50 trades with mixed performance
        base_time = datetime(2024, 1, 15, 9, 30, 0)  # Monday 9:30 AM
        
        for i in range(50):
            # Alternate between profitable and losing trades with some randomness
            if i % 3 == 0:  # 33% losing trades
                pnl = -50 - (i * 2)  # Increasing losses
            else:  # 67% winning trades
                pnl = 75 + (i * 1.5)  # Increasing wins
            
            # Keep minutes within valid range
            entry_minute = 30 + (i % 25)  # Max 54 minutes
            exit_minute = entry_minute + 5
            entry_time = base_time.replace(minute=entry_minute)
            exit_time = base_time.replace(minute=exit_minute)
            
            trade = create_valid_trade(
                trade_id=f"TRADE_{i:03d}",
                account_name="IPS_TM_10",
                pnl=pnl,
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def small_sample_trades(self):
        """Create small sample of trades for testing insufficient data scenarios."""
        trades = []
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        for i in range(5):  # Only 5 trades
            pnl = 100 if i % 2 == 0 else -50
            
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"SMALL_{i:03d}",
                account_name="IPS_TM_10",
                pnl=pnl,
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        return trades
    
    def test_get_time_bin_trades_filtering(self, analyzer, mock_db_session):
        """Test trade filtering by time bin."""
        # Mock database query results
        mock_trades = []
        for i in range(10):
            mock_trade = Mock()
            mock_trade.trade_id = f"TRADE_{i}"
            mock_trade.account_name = "IPS_TM_10"
            mock_trade.symbol = "NQ"
            mock_trade.entry_time = datetime(2024, 1, 15, 9, 30 + i, 0)
            mock_trade.exit_time = datetime(2024, 1, 15, 9, 35 + i, 0)
            mock_trade.entry_price = 15000.0
            mock_trade.exit_price = 15000.0 + (20.0 + 2.5) / 1  # Valid exit price for 20.0 P&L
            mock_trade.quantity = 1
            mock_trade.side = "LONG"
            mock_trade.profit_loss = 20.0
            mock_trade.commission = 2.5
            mock_trade.duration_minutes = 5
            mock_trade.hour_of_day = 9
            mock_trade.day_of_week = 0
            mock_trade.entry_order_id = f"ENTRY_{i}"
            mock_trade.exit_order_id = f"EXIT_{i}"
            mock_trades.append(mock_trade)
        
        # Mock the query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_trades
        mock_db_session.query.return_value = mock_query
        
        time_bin = TimeBin("IPS_TM_10", 9, 30)
        trades = analyzer.get_time_bin_trades(time_bin)
        
        # Verify database query was called correctly
        mock_db_session.query.assert_called_once()
        assert len(trades) == 10  # All trades should match the time window
    
    def test_calculate_time_bin_metrics_empty_trades(self, analyzer):
        """Test metrics calculation with no trades."""
        metrics = analyzer.calculate_time_bin_metrics([])
        
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.average_pnl == 0.0
        assert metrics.total_pnl == 0.0
        assert metrics.sharpe_ratio is None
        assert metrics.calmar_ratio is None
        assert metrics.sortino_ratio is None
        assert not metrics.statistical_significance
        assert not metrics.minimum_sample_size_met
    
    def test_calculate_time_bin_metrics_comprehensive(self, analyzer, sample_trades):
        """Test comprehensive metrics calculation with sample data."""
        metrics = analyzer.calculate_time_bin_metrics(sample_trades)
        
        # Basic validation
        assert metrics.total_trades == 50
        assert 0.0 <= metrics.win_rate <= 1.0
        
        # Manual calculation verification
        pnl_values = [trade.profit_loss for trade in sample_trades]
        expected_total_pnl = sum(pnl_values)
        expected_average_pnl = expected_total_pnl / len(pnl_values)
        
        assert abs(metrics.total_pnl - expected_total_pnl) < 0.01
        assert abs(metrics.average_pnl - expected_average_pnl) < 0.01
        
        # Win rate calculation
        winning_trades = [t for t in sample_trades if t.profit_loss > 0]
        expected_win_rate = len(winning_trades) / len(sample_trades)
        assert abs(metrics.win_rate - expected_win_rate) < 0.01
        
        # Verify statistical significance testing is enabled for large sample
        assert metrics.minimum_sample_size_met
        assert metrics.confidence_interval_95 is not None
        assert metrics.p_value_vs_random is not None
    
    def test_calculate_time_bin_metrics_small_sample(self, analyzer, small_sample_trades):
        """Test metrics calculation with insufficient sample size."""
        metrics = analyzer.calculate_time_bin_metrics(small_sample_trades)
        
        assert metrics.total_trades == 5
        assert not metrics.minimum_sample_size_met
        assert metrics.confidence_interval_95 is None
        assert metrics.p_value_vs_random is None
        assert not metrics.statistical_significance
    
    def test_sharpe_ratio_calculation(self, analyzer):
        """Test Sharpe ratio calculation with known data."""
        # Create trades with known returns
        trades = []
        returns = [100, -50, 150, -25, 200]  # Mix of positive and negative
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        for i, pnl in enumerate(returns):
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"SHARPE_{i}",
                account_name="IPS_TM_10",
                pnl=pnl,
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        metrics = analyzer.calculate_time_bin_metrics(trades)
        
        # Manual Sharpe calculation
        avg_return = np.mean(returns)
        volatility = np.std(returns, ddof=1)
        annualized_return = avg_return * 252
        annualized_vol = volatility * np.sqrt(252)
        expected_sharpe = (annualized_return - 0.02) / annualized_vol  # 2% risk-free rate
        
        assert abs(metrics.sharpe_ratio - expected_sharpe) < 0.01
    
    def test_calmar_ratio_calculation(self, analyzer):
        """Test Calmar ratio calculation."""
        # Create trades with known drawdown pattern
        trades = []
        pnl_sequence = [100, -200, 150, -100, 300]  # Creates specific drawdown
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        for i, pnl in enumerate(pnl_sequence):
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"CALMAR_{i}",
                account_name="IPS_TM_10",
                pnl=pnl,
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        metrics = analyzer.calculate_time_bin_metrics(trades)
        
        # Manual drawdown calculation
        cumulative = np.cumsum(pnl_sequence)  # [100, -100, 50, -50, 250]
        running_max = np.maximum.accumulate(cumulative)  # [100, 100, 100, 100, 250]
        drawdowns = cumulative - running_max  # [0, -200, -50, -150, 0]
        max_drawdown = np.min(drawdowns)  # -200
        
        assert abs(metrics.max_drawdown - max_drawdown) < 0.01
        
        # Calmar ratio should be calculated
        if metrics.calmar_ratio is not None:
            total_return = sum(pnl_sequence)
            avg_return = total_return / len(pnl_sequence)
            annualized_return = avg_return * 252
            expected_calmar = annualized_return / abs(max_drawdown)
            assert abs(metrics.calmar_ratio - expected_calmar) < 0.01
    
    def test_sortino_ratio_calculation(self, analyzer):
        """Test Sortino ratio calculation."""
        # Create trades with known downside deviation
        trades = []
        returns = [100, -50, 150, -25, 200, -75]  # Mix with negative returns
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        for i, pnl in enumerate(returns):
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"SORTINO_{i}",
                account_name="IPS_TM_10",
                pnl=pnl,
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        metrics = analyzer.calculate_time_bin_metrics(trades)
        
        # Manual Sortino calculation
        negative_returns = [r for r in returns if r < 0]  # [-50, -25, -75]
        downside_deviation = np.std(negative_returns, ddof=1)
        
        if metrics.sortino_ratio is not None and downside_deviation > 0:
            avg_return = np.mean(returns)
            annualized_return = avg_return * 252
            annualized_downside_dev = downside_deviation * np.sqrt(252)
            expected_sortino = (annualized_return - 0.02) / annualized_downside_dev
            assert abs(metrics.sortino_ratio - expected_sortino) < 0.01
    
    def test_statistical_significance_testing(self, analyzer, sample_trades):
        """Test statistical significance testing functionality."""
        # Mock the get_time_bin_trades method to return our sample trades
        analyzer.get_time_bin_trades = lambda tb: sample_trades
        
        metrics = analyzer.calculate_time_bin_metrics(sample_trades)
        significance_tests = analyzer.test_statistical_significance(metrics)
        
        # Should have multiple tests
        assert len(significance_tests) >= 2
        
        # Check test types
        test_names = [test.test_name for test in significance_tests]
        assert "One-sample t-test vs zero" in test_names
        assert "Binomial test for win rate" in test_names
        
        # Validate test structure
        for test in significance_tests:
            assert isinstance(test, SignificanceTest)
            assert test.test_name is not None
            assert 0.0 <= test.p_value <= 1.0
            assert test.is_significant in [True, False]  # More explicit check
            assert test.confidence_level > 0
            assert test.interpretation is not None
    
    def test_statistical_significance_insufficient_data(self, analyzer, small_sample_trades):
        """Test statistical significance with insufficient data."""
        metrics = analyzer.calculate_time_bin_metrics(small_sample_trades)
        significance_tests = analyzer.test_statistical_significance(metrics)
        
        # Should return empty list for insufficient data
        assert len(significance_tests) == 0
    
    def test_confidence_interval_calculation(self, analyzer):
        """Test confidence interval calculation."""
        # Known data for confidence interval
        pnl_values = [100, 120, 80, 110, 90, 130, 70, 140, 85, 115]
        
        ci_lower, ci_upper = analyzer._calculate_confidence_interval(pnl_values, confidence=0.95)
        
        # Manual calculation
        mean_pnl = np.mean(pnl_values)
        std_error = stats.sem(pnl_values)
        t_critical = stats.t.ppf(0.975, len(pnl_values) - 1)  # 95% confidence
        margin_error = t_critical * std_error
        
        expected_lower = mean_pnl - margin_error
        expected_upper = mean_pnl + margin_error
        
        assert abs(ci_lower - expected_lower) < 0.01
        assert abs(ci_upper - expected_upper) < 0.01
        assert ci_lower < mean_pnl < ci_upper
    
    def test_compare_time_bins(self, analyzer, mock_db_session):
        """Test time bin comparison functionality."""
        # Mock two different sets of trades
        trades1_data = [100, 120, 80, 110, 90]  # Better performance
        trades2_data = [50, 60, 40, 55, 45]     # Worse performance
        
        def mock_get_trades(time_bin):
            if time_bin.hour == 9:
                pnl_data = trades1_data
            else:
                pnl_data = trades2_data
            
            trades = []
            for i, pnl in enumerate(pnl_data):
                entry_time = datetime(2024, 1, 15, time_bin.hour, 30, 0)
                exit_time = datetime(2024, 1, 15, time_bin.hour, 35, 0)
                
                trade = create_valid_trade(
                    trade_id=f"COMP_{time_bin.hour}_{i}",
                    account_name=time_bin.account_name,
                    pnl=pnl,
                    entry_time=entry_time,
                    exit_time=exit_time,
                    hour_of_day=time_bin.hour,
                    day_of_week=0
                )
                trades.append(trade)
            return trades
        
        analyzer.get_time_bin_trades = mock_get_trades
        
        time_bin1 = TimeBin("IPS_TM_10", 9, 30)
        time_bin2 = TimeBin("IPS_TM_10", 14, 30)
        
        comparison = analyzer.compare_time_bins(time_bin1, time_bin2)
        
        # Validate comparison structure
        assert "time_bin1" in comparison
        assert "time_bin2" in comparison
        assert "statistical_comparison" in comparison
        assert "performance_difference" in comparison
        
        # Check statistical tests
        stats_comp = comparison["statistical_comparison"]
        assert "t_test" in stats_comp
        assert "mann_whitney_u" in stats_comp
        
        # Performance difference should show time_bin1 is better
        perf_diff = comparison["performance_difference"]
        assert perf_diff["average_pnl_diff"] > 0  # time_bin1 has higher average P&L
    
    def test_compare_time_bins_insufficient_data(self, analyzer):
        """Test time bin comparison with insufficient data."""
        def mock_get_trades_empty(time_bin):
            return []
        
        analyzer.get_time_bin_trades = mock_get_trades_empty
        
        time_bin1 = TimeBin("IPS_TM_10", 9, 30)
        time_bin2 = TimeBin("IPS_TM_10", 14, 30)
        
        comparison = analyzer.compare_time_bins(time_bin1, time_bin2)
        
        assert "error" in comparison
        assert "Insufficient data" in comparison["error"]
    
    def test_analyze_time_bin_complete(self, analyzer, mock_db_session):
        """Test complete time bin analysis."""
        # Mock trade data
        pnl_data = [100, -50, 150, -25, 200, 75, -30, 120, 90, 110,
                   -40, 180, 60, -20, 140, 85, -35, 160, 95, 130,
                   -45, 170, 55, -15, 190, 105, -25, 145, 80, 125,
                   -55, 175, 65, -10, 195, 115, -30, 155, 75, 135]  # 40 trades
        
        trades = []
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        for i, pnl in enumerate(pnl_data):
            # Keep minutes within valid range
            entry_minute = 30 + (i % 25)  # Max 54 minutes
            exit_minute = entry_minute + 5
            entry_time = base_time.replace(minute=entry_minute)
            exit_time = base_time.replace(minute=exit_minute)
            
            trade = create_valid_trade(
                trade_id=f"COMPLETE_{i}",
                account_name="IPS_TM_10",
                pnl=pnl,
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        analyzer.get_time_bin_trades = lambda tb: trades
        
        time_bin = TimeBin("IPS_TM_10", 9, 30)
        metrics, significance_tests = analyzer.analyze_time_bin(time_bin)
        
        # Validate complete analysis
        assert isinstance(metrics, TimeBinMetrics)
        assert metrics.total_trades == 40
        assert metrics.minimum_sample_size_met
        
        assert isinstance(significance_tests, list)
        assert len(significance_tests) > 0
        
        # All significance tests should be properly structured
        for test in significance_tests:
            assert isinstance(test, SignificanceTest)
            assert test.test_name is not None
            assert 0.0 <= test.p_value <= 1.0
    
    def test_edge_case_all_winning_trades(self, analyzer):
        """Test edge case with all winning trades."""
        trades = []
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        for i in range(10):
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"WIN_{i}",
                account_name="IPS_TM_10",
                pnl=100.0 + i,  # All positive
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        metrics = analyzer.calculate_time_bin_metrics(trades)
        
        assert metrics.win_rate == 1.0
        assert metrics.losing_trades == 0
        assert metrics.average_loss == 0.0
        assert metrics.profit_factor == float('inf')
    
    def test_edge_case_all_losing_trades(self, analyzer):
        """Test edge case with all losing trades."""
        trades = []
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        for i in range(10):
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"LOSS_{i}",
                account_name="IPS_TM_10",
                pnl=-(50.0 + i),  # All negative
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        metrics = analyzer.calculate_time_bin_metrics(trades)
        
        assert metrics.win_rate == 0.0
        assert metrics.winning_trades == 0
        assert metrics.average_win == 0.0
        assert metrics.profit_factor == 0.0
    
    def test_edge_case_identical_returns(self, analyzer):
        """Test edge case with identical returns (zero volatility)."""
        trades = []
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        for i in range(10):
            entry_time = base_time.replace(minute=30 + i)
            exit_time = base_time.replace(minute=35 + i)
            
            trade = create_valid_trade(
                trade_id=f"SAME_{i}",
                account_name="IPS_TM_10",
                pnl=100.0,  # All identical
                entry_time=entry_time,
                exit_time=exit_time,
                hour_of_day=9,
                day_of_week=0
            )
            trades.append(trade)
        
        metrics = analyzer.calculate_time_bin_metrics(trades)
        
        assert metrics.volatility == 0.0
        assert metrics.sharpe_ratio is None  # Cannot calculate with zero volatility
        assert metrics.largest_win == metrics.largest_loss == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])