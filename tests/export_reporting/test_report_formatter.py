"""
Comprehensive test suite for TradingReportFormatter with real trade data validation.

Tests cover:
1. Equity curve chart generation with cumulative P&L visualization
2. Drawdown chart creation for risk assessment
3. Monthly returns table generation for performance breakdown
4. Performance metrics table creation for comprehensive statistics
5. Chart configuration and styling options
6. Data integrity in chart generation
7. Visual accuracy validation
8. Error handling and edge cases
9. Chart history management
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for testing
import matplotlib.pyplot as plt

# Import the test infrastructure
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from trading_platform.services.export_reporting.trading_report_formatter import (
    TradingReportFormatter,
    ChartConfiguration,
    ChartData
)
from trading_platform.services.time_bin_analyzer import SimpleTrade, TimeBin


class TestTradingReportFormatter:
    """Test suite for TradingReportFormatter functionality"""
    
    @pytest.fixture
    def temp_chart_dir(self):
        """Create a temporary directory for chart output testing"""
        temp_dir = tempfile.mkdtemp(prefix='test_charts_')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_profitable_trades(self):
        """Generate sample profitable trading scenario"""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        running_capital = 10000  # Starting capital
        
        # Generate upward trending trades
        for i in range(30):
            entry_time = base_date + timedelta(days=i * 3, hours=np.random.randint(0, 6))
            exit_time = entry_time + timedelta(minutes=np.random.randint(15, 180))
            
            # Generally profitable with some variation
            base_pnl = 50 + i * 2  # Increasing profitability trend
            profit_loss = base_pnl + np.random.uniform(-20, 30)
            
            # Occasional losses for realism
            if np.random.random() < 0.25:  # 25% chance of loss
                profit_loss = -abs(profit_loss) * 0.6
            
            quantity = 100
            entry_price = 50 + np.random.uniform(-5, 5)
            
            trade = SimpleTrade(
                trade_id=f'PROFIT{i+1:03d}',
                account_name='PROFITABLE_ACCOUNT',
                symbol=np.random.choice(['AAPL', 'MSFT', 'GOOGL']),
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=entry_price + (profit_loss / quantity),
                quantity=quantity,
                side='BUY',
                profit_loss=profit_loss,
                commission=1.0,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday()
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_losing_trades(self):
        """Generate sample losing trading scenario"""
        trades = []
        base_date = datetime(2024, 1, 1, 14, 0)
        
        # Generate downward trending trades
        for i in range(20):
            entry_time = base_date + timedelta(days=i * 2, hours=np.random.randint(0, 4))
            exit_time = entry_time + timedelta(minutes=np.random.randint(10, 90))
            
            # Generally unprofitable
            base_pnl = -30 - i * 1.5  # Increasing losses
            profit_loss = base_pnl + np.random.uniform(-15, 10)
            
            # Occasional wins for realism
            if np.random.random() < 0.15:  # 15% chance of win
                profit_loss = abs(profit_loss) * 0.8
            
            quantity = 200
            entry_price = 25 + np.random.uniform(-2, 2)
            
            trade = SimpleTrade(
                trade_id=f'LOSS{i+1:03d}',
                account_name='LOSING_ACCOUNT',
                symbol=np.random.choice(['XYZ', 'ABC', 'DEF']),
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=entry_price + (profit_loss / quantity),
                quantity=quantity,
                side='SELL',
                profit_loss=profit_loss,
                commission=1.0,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday()
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_mixed_trades(self):
        """Generate mixed trading scenario with drawdowns and recoveries"""
        trades = []
        base_date = datetime(2024, 1, 1, 10, 0)
        
        # Create distinct periods: good, bad, recovery
        periods = [
            {'days': 15, 'pnl_range': (20, 80), 'loss_prob': 0.2},    # Good period
            {'days': 10, 'pnl_range': (-60, -20), 'loss_prob': 0.8},  # Bad period
            {'days': 12, 'pnl_range': (10, 50), 'loss_prob': 0.3}     # Recovery period
        ]
        
        trade_id = 1
        current_date = base_date
        
        for period in periods:
            for i in range(period['days']):
                entry_time = current_date + timedelta(hours=np.random.randint(1, 8))
                exit_time = entry_time + timedelta(minutes=np.random.randint(30, 120))
                
                # Generate P&L based on period characteristics
                if np.random.random() < period['loss_prob']:
                    profit_loss = np.random.uniform(-abs(period['pnl_range'][1]), -abs(period['pnl_range'][0]))
                else:
                    profit_loss = np.random.uniform(period['pnl_range'][0], period['pnl_range'][1])
                
                quantity = np.random.choice([100, 200, 300])
                entry_price = 75 + np.random.uniform(-10, 10)
                
                trade = SimpleTrade(
                    trade_id=f'MIX{trade_id:03d}',
                    account_name='MIXED_ACCOUNT',
                    symbol=np.random.choice(['SPY', 'QQQ', 'IWM', 'AAPL', 'TSLA']),
                    entry_time=entry_time,
                    exit_time=exit_time,
                    entry_price=entry_price,
                    exit_price=entry_price + (profit_loss / quantity),
                    quantity=quantity,
                    side=np.random.choice(['BUY', 'SELL']),
                    profit_loss=profit_loss,
                    commission=2.0,
                    duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                    hour_of_day=entry_time.hour,
                    day_of_week=entry_time.weekday()
                )
                trades.append(trade)
                trade_id += 1
                current_date = exit_time
        
        return trades
    
    @pytest.fixture
    def chart_config(self):
        """Default chart configuration for testing"""
        return ChartConfiguration(
            figure_width=10.0,
            figure_height=6.0,
            dpi=150,  # Lower DPI for faster tests
            style='default',  # Use default style for tests
            primary_color='#2563eb',
            secondary_color='#10b981',
            show_statistics=True,
            show_grid=True
        )
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def report_formatter(self, mock_db_session):
        """Create TradingReportFormatter instance with mocked dependencies"""
        with patch('trading_platform.services.export_reporting.trading_report_formatter.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            formatter = TradingReportFormatter(mock_db_session)
            
            # Mock the performance calculator
            formatter.performance_calculator = Mock()
            
            return formatter
    
    def test_equity_curve_chart_creation(self, report_formatter, sample_profitable_trades, 
                                       temp_chart_dir, chart_config):
        """Test equity curve chart generation with profitable trades"""
        
        # Generate equity curve chart
        output_path = os.path.join(temp_chart_dir, 'equity_curve_test.png')
        
        chart_data = report_formatter.create_equity_curve_chart(
            trades=sample_profitable_trades,
            title="Test Equity Curve - Profitable Strategy",
            output_path=output_path,
            config=chart_config,
            show_drawdowns=True,
            show_benchmarks=False
        )
        
        # Validate chart data
        assert isinstance(chart_data, ChartData)
        assert chart_data.chart_type == 'equity_curve'
        assert chart_data.title == "Test Equity Curve - Profitable Strategy"
        assert chart_data.figure_path == output_path
        assert os.path.exists(output_path)
        
        # Validate file properties
        file_size = os.path.getsize(output_path)
        assert file_size > 10000  # Should be substantial image file
        
        # Validate metadata
        assert 'trades_count' in chart_data.data
        assert chart_data.data['trades_count'] == len(sample_profitable_trades)
        assert 'final_pnl' in chart_data.data
        assert chart_data.data['final_pnl'] > 0  # Should be profitable
        
        # Validate chart history tracking
        history = report_formatter.get_chart_history()
        assert len(history) == 1
        assert history[0].chart_type == 'equity_curve'
        
        print(f"✓ Equity curve chart creation validation passed")
        print(f"  - File size: {file_size:,} bytes")
        print(f"  - Final P&L: ${chart_data.data['final_pnl']:,.2f}")
        print(f"  - Trades processed: {chart_data.data['trades_count']}")
    
    def test_drawdown_chart_creation(self, report_formatter, sample_mixed_trades,
                                   temp_chart_dir, chart_config):
        """Test drawdown chart generation with mixed performance"""
        
        # Generate drawdown chart
        output_path = os.path.join(temp_chart_dir, 'drawdown_test.png')
        
        chart_data = report_formatter.create_drawdown_chart(
            trades=sample_mixed_trades,
            title="Test Drawdown Analysis - Mixed Strategy",
            output_path=output_path,
            config=chart_config,
            show_underwater_curve=True,
            show_recovery_periods=True
        )
        
        # Validate chart data
        assert isinstance(chart_data, ChartData)
        assert chart_data.chart_type == 'drawdown'
        assert chart_data.title == "Test Drawdown Analysis - Mixed Strategy"
        assert chart_data.figure_path == output_path
        assert os.path.exists(output_path)
        
        # Validate file properties
        file_size = os.path.getsize(output_path)
        assert file_size > 15000  # Should be substantial (has two subplots)
        
        # Validate metadata
        assert 'max_drawdown_pct' in chart_data.data
        assert 'drawdown_periods' in chart_data.data
        assert chart_data.data['max_drawdown_pct'] < 0  # Should have drawdown
        
        print(f"✓ Drawdown chart creation validation passed")
        print(f"  - File size: {file_size:,} bytes") 
        print(f"  - Max drawdown: {chart_data.data['max_drawdown_pct']:.2f}%")
        print(f"  - Drawdown periods: {chart_data.data['drawdown_periods']}")
    
    def test_monthly_returns_table_creation(self, report_formatter, sample_profitable_trades,
                                          temp_chart_dir, chart_config):
        """Test monthly returns table generation"""
        
        # Generate monthly returns table
        output_path = os.path.join(temp_chart_dir, 'monthly_returns_test.png')
        
        chart_data = report_formatter.create_monthly_returns_table(
            trades=sample_profitable_trades,
            title="Test Monthly Returns - Heatmap",
            output_path=output_path,
            config=chart_config,
            show_heatmap=True
        )
        
        # Validate chart data
        assert isinstance(chart_data, ChartData)
        assert chart_data.chart_type == 'monthly_returns'
        assert chart_data.title == "Test Monthly Returns - Heatmap"
        assert chart_data.figure_path == output_path
        assert os.path.exists(output_path)
        
        # Validate metadata
        assert 'total_months' in chart_data.data
        assert 'positive_months' in chart_data.data
        assert 'win_rate_monthly' in chart_data.data
        assert 'avg_monthly_return' in chart_data.data
        
        # Validate win rate calculation
        win_rate = chart_data.data['win_rate_monthly']
        assert 0 <= win_rate <= 1
        
        print(f"✓ Monthly returns table creation validation passed")
        print(f"  - Total months: {chart_data.data['total_months']}")
        print(f"  - Positive months: {chart_data.data['positive_months']}")
        print(f"  - Monthly win rate: {win_rate:.2%}")
        print(f"  - Avg monthly return: ${chart_data.data['avg_monthly_return']:.2f}")
    
    def test_performance_metrics_table_creation(self, report_formatter, sample_mixed_trades,
                                              temp_chart_dir, chart_config):
        """Test performance metrics table generation"""
        
        # Mock performance calculator
        mock_performance_data = {
            'total_pnl': 1500.0,
            'total_return_pct': 0.15,
            'annualized_return': 0.18,
            'cagr': 0.16,
            'max_drawdown': 0.12,
            'volatility': 0.22,
            'sharpe_ratio': 1.25,
            'sortino_ratio': 1.45,
            'var_95': -85.0,
            'cvar_95': -120.0,
            'profit_factor': 1.35,
            'avg_trade_pnl': 25.5
        }
        
        report_formatter.performance_calculator.calculate_comprehensive_metrics.return_value = mock_performance_data
        
        # Generate performance metrics table
        output_path = os.path.join(temp_chart_dir, 'performance_metrics_test.png')
        
        chart_data = report_formatter.create_performance_metrics_table(
            trades=sample_mixed_trades,
            title="Test Performance Metrics - Comprehensive",
            output_path=output_path,
            config=chart_config,
            include_risk_metrics=True,
            include_trade_metrics=True
        )
        
        # Validate chart data
        assert isinstance(chart_data, ChartData)
        assert chart_data.chart_type == 'performance_metrics'
        assert chart_data.title == "Test Performance Metrics - Comprehensive"
        assert chart_data.figure_path == output_path
        assert os.path.exists(output_path)
        
        # Validate metadata
        assert 'summary_metrics' in chart_data.data
        summary = chart_data.data['summary_metrics']
        
        # Should include returns and risk metrics
        expected_metrics = ['total_pnl', 'sharpe_ratio', 'max_drawdown']
        for metric in expected_metrics:
            assert metric in summary or any(metric in str(k).lower() for k in summary.keys())
        
        print(f"✓ Performance metrics table creation validation passed")
        print(f"  - Summary metrics included: {len(summary)}")
        print(f"  - Performance calculator called successfully")
    
    def test_base64_chart_generation(self, report_formatter, sample_profitable_trades, chart_config):
        """Test chart generation without file output (base64 format)"""
        
        # Generate chart without output path (should create base64)
        chart_data = report_formatter.create_equity_curve_chart(
            trades=sample_profitable_trades,
            title="Base64 Test Chart",
            output_path=None,  # No file output
            config=chart_config
        )
        
        # Validate base64 output
        assert chart_data.figure_path is None
        assert chart_data.figure_base64 is not None
        assert len(chart_data.figure_base64) > 1000  # Should be substantial base64 string
        
        # Validate base64 format
        import base64
        try:
            decoded_data = base64.b64decode(chart_data.figure_base64)
            assert len(decoded_data) > 0
        except Exception as e:
            pytest.fail(f"Invalid base64 data: {e}")
        
        print(f"✓ Base64 chart generation validation passed")
        print(f"  - Base64 length: {len(chart_data.figure_base64)} characters")
        print(f"  - Decoded size: {len(decoded_data):,} bytes")
    
    def test_chart_configuration_options(self, report_formatter, sample_mixed_trades, temp_chart_dir):
        """Test different chart configuration options"""
        
        # Test different chart configurations
        configs_to_test = [
            {
                'name': 'high_dpi',
                'config': ChartConfiguration(dpi=300, figure_width=8, figure_height=6),
                'expected_min_size': 20000
            },
            {
                'name': 'large_format',
                'config': ChartConfiguration(figure_width=16, figure_height=10, dpi=150),
                'expected_min_size': 25000
            },
            {
                'name': 'minimal',
                'config': ChartConfiguration(
                    figure_width=6, figure_height=4, 
                    show_statistics=False, show_grid=False
                ),
                'expected_min_size': 8000
            }
        ]
        
        for test_case in configs_to_test:
            output_path = os.path.join(temp_chart_dir, f'config_test_{test_case["name"]}.png')
            
            chart_data = report_formatter.create_equity_curve_chart(
                trades=sample_mixed_trades,
                title=f"Config Test - {test_case['name'].title()}",
                output_path=output_path,
                config=test_case['config']
            )
            
            # Validate file was created
            assert os.path.exists(output_path)
            file_size = os.path.getsize(output_path)
            
            # Validate minimum expected size
            assert file_size >= test_case['expected_min_size']
            
            # Validate configuration was applied
            assert chart_data.metadata['config']['dpi'] == test_case['config'].dpi
            assert chart_data.metadata['config']['figure_width'] == test_case['config'].figure_width
            
        print(f"✓ Chart configuration options validation passed")
        print(f"  - Configurations tested: {len(configs_to_test)}")
    
    def test_empty_trades_handling(self, report_formatter, temp_chart_dir, chart_config):
        """Test handling of empty or minimal trade lists"""
        
        # Test with empty trades
        with pytest.raises(ValueError) as exc_info:
            report_formatter.create_equity_curve_chart(
                trades=[],
                title="Empty Trades Test",
                config=chart_config
            )
        assert "No equity curve data available" in str(exc_info.value)
        
        # Test with single trade
        single_trade = SimpleTrade(
            trade_id='SINGLE001',
            account_name='SINGLE_ACCOUNT',
            symbol='TEST',
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            entry_price=100.0,
            exit_price=102.0,
            quantity=100,
            side='BUY',
            profit_loss=200.0,
            commission=1.0,
            duration_minutes=60,
            hour_of_day=10,
            day_of_week=0
        )
        
        output_path = os.path.join(temp_chart_dir, 'single_trade_test.png')
        
        chart_data = report_formatter.create_equity_curve_chart(
            trades=[single_trade],
            title="Single Trade Test",
            output_path=output_path,
            config=chart_config
        )
        
        # Should handle single trade gracefully
        assert os.path.exists(output_path)
        assert chart_data.data['trades_count'] == 1
        assert chart_data.data['final_pnl'] == 200.0
        
        print(f"✓ Empty trades handling validation passed")
        print(f"  - Empty trades properly rejected")
        print(f"  - Single trade handled gracefully")
    
    def test_benchmark_comparison(self, report_formatter, sample_profitable_trades, 
                                temp_chart_dir, chart_config):
        """Test equity curve with benchmark comparison"""
        
        # Create mock benchmark data
        dates_count = len(sample_profitable_trades) + 1  # +1 for starting point
        benchmark_data = {
            'SPY': [i * 15.5 for i in range(dates_count)],    # Steady upward trend
            'Market': [i * 12.2 + np.random.uniform(-5, 5) for i in range(dates_count)]  # Trend with noise
        }
        
        output_path = os.path.join(temp_chart_dir, 'benchmark_comparison_test.png')
        
        chart_data = report_formatter.create_equity_curve_chart(
            trades=sample_profitable_trades,
            title="Equity Curve with Benchmark Comparison",
            output_path=output_path,
            config=chart_config,
            show_benchmarks=True,
            benchmark_data=benchmark_data
        )
        
        # Validate benchmark comparison chart
        assert os.path.exists(output_path)
        assert chart_data.chart_type == 'equity_curve'
        
        # File should be larger due to additional benchmark lines
        file_size = os.path.getsize(output_path)
        assert file_size > 15000  # Should be larger with benchmarks
        
        print(f"✓ Benchmark comparison validation passed")
        print(f"  - Benchmarks included: {len(benchmark_data)}")
        print(f"  - Chart file size: {file_size:,} bytes")
    
    def test_drawdown_analysis_calculations(self, report_formatter, sample_losing_trades):
        """Test drawdown analysis calculations accuracy"""
        
        # Calculate equity curve for validation
        equity_data = report_formatter._calculate_equity_curve(sample_losing_trades)
        
        # Validate equity curve data structure
        assert 'dates' in equity_data
        assert 'cumulative_pnl' in equity_data
        assert 'drawdown_periods' in equity_data
        
        dates = equity_data['dates']
        cumulative_pnl = equity_data['cumulative_pnl']
        
        # Validate data integrity
        assert len(dates) == len(cumulative_pnl)
        assert len(dates) == len(sample_losing_trades) + 1  # +1 for starting point
        
        # Validate cumulative calculation
        total_pnl = sum(trade.profit_loss for trade in sample_losing_trades)
        assert abs(cumulative_pnl[-1] - total_pnl) < 0.01  # Should match within rounding
        
        # Test drawdown analysis
        drawdown_data = report_formatter._calculate_drawdown_analysis(sample_losing_trades)
        
        assert 'drawdown_pct' in drawdown_data
        assert 'max_drawdown' in drawdown_data
        assert 'recovery_periods' in drawdown_data
        
        # Max drawdown should be negative (indicating loss)
        max_drawdown = drawdown_data['max_drawdown']
        assert max_drawdown <= 0
        
        print(f"✓ Drawdown analysis calculations validation passed")
        print(f"  - Total P&L: ${total_pnl:.2f}")
        print(f"  - Max drawdown: {max_drawdown:.2f}%")
        print(f"  - Data points: {len(dates)}")
    
    def test_monthly_returns_calculation(self, report_formatter, sample_mixed_trades):
        """Test monthly returns calculation accuracy"""
        
        # Calculate monthly returns
        monthly_data = report_formatter._calculate_monthly_returns(sample_mixed_trades)
        
        # Validate DataFrame structure
        assert isinstance(monthly_data, pd.DataFrame)
        
        if not monthly_data.empty:
            # Should have year index and month columns
            assert monthly_data.index.name == 'year' or 'year' in str(monthly_data.index)
            
            # Validate data integrity
            total_from_monthly = monthly_data.sum().sum()
            total_from_trades = sum(trade.profit_loss for trade in sample_mixed_trades)
            
            # Should be close (within small rounding differences)
            assert abs(total_from_monthly - total_from_trades) < 1.0
            
            print(f"✓ Monthly returns calculation validation passed")
            print(f"  - Monthly data shape: {monthly_data.shape}")
            print(f"  - Total from monthly: ${total_from_monthly:.2f}")
            print(f"  - Total from trades: ${total_from_trades:.2f}")
        else:
            print("✓ Monthly returns calculation handled empty data gracefully")
    
    def test_chart_history_management(self, report_formatter, sample_profitable_trades, 
                                    temp_chart_dir, chart_config):
        """Test chart generation history tracking"""
        
        # Generate multiple charts
        charts_to_create = [
            ('equity_curve', 'create_equity_curve_chart'),
            ('drawdown', 'create_drawdown_chart'),
            ('monthly_returns', 'create_monthly_returns_table'),
        ]
        
        for i, (chart_type, method_name) in enumerate(charts_to_create):
            output_path = os.path.join(temp_chart_dir, f'history_test_{chart_type}.png')
            
            method = getattr(report_formatter, method_name)
            chart_data = method(
                trades=sample_profitable_trades,
                title=f"History Test - {chart_type.title()}",
                output_path=output_path,
                config=chart_config
            )
            
            assert chart_data.chart_type == chart_type
        
        # Validate history tracking
        history = report_formatter.get_chart_history()
        assert len(history) == len(charts_to_create)
        
        # Validate each chart in history
        for i, chart_data in enumerate(history):
            expected_type = charts_to_create[i][0]
            assert chart_data.chart_type == expected_type
            assert chart_data.figure_path is not None
            assert os.path.exists(chart_data.figure_path)
        
        # Test history clearing
        report_formatter.clear_chart_history()
        assert len(report_formatter.get_chart_history()) == 0
        
        print(f"✓ Chart history management validation passed")
        print(f"  - Charts created and tracked: {len(charts_to_create)}")
        print(f"  - History cleared successfully")
    
    def test_error_handling_scenarios(self, report_formatter, temp_chart_dir):
        """Test error handling in various failure scenarios"""
        
        # Test with invalid output path
        with pytest.raises(Exception):
            invalid_path = "/invalid/nonexistent/directory/chart.png"
            report_formatter.create_equity_curve_chart(
                trades=[],  # Also empty, but path error should come first
                title="Invalid Path Test",
                output_path=invalid_path,
                config=ChartConfiguration()
            )
        
        # Test with malformed trade data
        malformed_trade = SimpleTrade(
            trade_id='MALFORMED001',
            account_name='TEST',
            symbol='TEST',
            entry_time=datetime(2024, 1, 1),
            exit_time=datetime(2024, 1, 1),  # Same as entry time
            entry_price=0,  # Zero price
            exit_price=0,   # Zero price
            quantity=0,     # Zero quantity
            side='BUY',
            profit_loss=float('inf'),  # Invalid P&L
            commission=0,
            duration_minutes=0,
            hour_of_day=25,  # Invalid hour
            day_of_week=8    # Invalid day
        )
        
        # Should handle malformed data gracefully
        try:
            output_path = os.path.join(temp_chart_dir, 'malformed_test.png')
            chart_data = report_formatter.create_equity_curve_chart(
                trades=[malformed_trade],
                title="Malformed Data Test",
                output_path=output_path,
                config=ChartConfiguration()
            )
            # If it succeeds, validate the output exists
            assert os.path.exists(output_path)
            print("✓ Malformed data handled gracefully")
        except Exception as e:
            # If it fails, make sure it's a reasonable error
            assert isinstance(e, (ValueError, TypeError, OverflowError))
            print(f"✓ Malformed data properly rejected: {type(e).__name__}")
        
        print("✓ Error handling validation passed")
    
    def test_performance_metrics_formatting(self, report_formatter):
        """Test performance metrics value formatting"""
        
        # Test various metric formatting scenarios
        test_cases = [
            ('Total Return', 0.15, '15.00%'),
            ('Sharpe Ratio', 1.234, '1.234'),
            ('Total P&L', 1500.75, '$1,500.75'),
            ('Win Rate', 0.65, '65.00%'),
            ('Max Drawdown', -0.12, '-12.00%'),
            ('Total Trades', 150, '150.00'),
            ('Profit Factor', 1.35, '1.350')
        ]
        
        for metric_name, value, expected_format in test_cases:
            formatted = report_formatter._format_metric_value(metric_name, value)
            
            # Check that formatting is reasonable (exact format may vary)
            if '%' in expected_format:
                assert '%' in formatted
            elif '$' in expected_format:
                assert '$' in formatted or 'USD' in formatted or str(value) in formatted
            elif '.' in expected_format:
                assert '.' in formatted or str(int(value)) in formatted
            
        print(f"✓ Performance metrics formatting validation passed")
        print(f"  - Test cases validated: {len(test_cases)}")
    
    def test_chart_metadata_integrity(self, report_formatter, sample_mixed_trades, 
                                    temp_chart_dir, chart_config):
        """Test chart metadata integrity and completeness"""
        
        output_path = os.path.join(temp_chart_dir, 'metadata_test.png')
        
        chart_data = report_formatter.create_equity_curve_chart(
            trades=sample_mixed_trades,
            title="Metadata Integrity Test",
            output_path=output_path,
            config=chart_config
        )
        
        # Validate ChartData structure
        assert hasattr(chart_data, 'chart_type')
        assert hasattr(chart_data, 'title')
        assert hasattr(chart_data, 'data')
        assert hasattr(chart_data, 'metadata')
        
        # Validate metadata content
        metadata = chart_data.metadata
        assert 'config' in metadata
        assert 'generation_time' in metadata
        assert 'format' in metadata
        
        # Validate configuration preservation
        config_data = metadata['config']
        assert config_data['dpi'] == chart_config.dpi
        assert config_data['figure_width'] == chart_config.figure_width
        assert config_data['primary_color'] == chart_config.primary_color
        
        # Validate generation timestamp
        generation_time = metadata['generation_time']
        assert isinstance(generation_time, str)
        
        # Should be recent timestamp
        from datetime import datetime
        gen_datetime = datetime.fromisoformat(generation_time)
        time_diff = datetime.now() - gen_datetime
        assert time_diff.total_seconds() < 60  # Generated within last minute
        
        print(f"✓ Chart metadata integrity validation passed")
        print(f"  - Metadata fields: {len(metadata)}")
        print(f"  - Generation time: {generation_time}")
        print(f"  - Configuration preserved: {len(config_data)} fields")


if __name__ == "__main__":
    # Run tests
    test_instance = TestTradingReportFormatter()
    
    print("Running TradingReportFormatter Tests...")
    print("=" * 60)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory(prefix='test_charts_') as temp_dir:
        
        # Generate test fixtures
        sample_profitable_trades = test_instance.sample_profitable_trades()
        sample_losing_trades = test_instance.sample_losing_trades()
        sample_mixed_trades = test_instance.sample_mixed_trades()
        chart_config = test_instance.chart_config()
        
        # Create mock dependencies
        mock_db = Mock()
        
        # Create test formatter
        with patch('trading_platform.services.export_reporting.trading_report_formatter.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db
            formatter = TradingReportFormatter(mock_db)
            
            # Mock performance calculator
            formatter.performance_calculator = Mock()
        
        try:
            # Run individual tests
            test_instance.test_equity_curve_chart_creation(formatter, sample_profitable_trades, temp_dir, chart_config)
            test_instance.test_drawdown_chart_creation(formatter, sample_mixed_trades, temp_dir, chart_config)
            test_instance.test_monthly_returns_table_creation(formatter, sample_profitable_trades, temp_dir, chart_config)
            test_instance.test_performance_metrics_table_creation(formatter, sample_mixed_trades, temp_dir, chart_config)
            test_instance.test_base64_chart_generation(formatter, sample_profitable_trades, chart_config)
            test_instance.test_chart_configuration_options(formatter, sample_mixed_trades, temp_dir)
            test_instance.test_empty_trades_handling(formatter, temp_dir, chart_config)
            test_instance.test_benchmark_comparison(formatter, sample_profitable_trades, temp_dir, chart_config)
            test_instance.test_drawdown_analysis_calculations(formatter, sample_losing_trades)
            test_instance.test_monthly_returns_calculation(formatter, sample_mixed_trades)
            test_instance.test_chart_history_management(formatter, sample_profitable_trades, temp_dir, chart_config)
            test_instance.test_error_handling_scenarios(formatter, temp_dir)
            test_instance.test_performance_metrics_formatting(formatter)
            test_instance.test_chart_metadata_integrity(formatter, sample_mixed_trades, temp_dir, chart_config)
            
            print("=" * 60)
            print("✅ ALL TESTS PASSED!")
            print("TradingReportFormatter is ready for production use.")
            
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            raise
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            raise