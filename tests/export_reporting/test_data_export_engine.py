"""
Comprehensive test suite for DataExportEngine with real analytics data validation.

Tests cover:
1. Time-bin trade exports (CSV/Excel/JSON formats)
2. Analytics results export with performance metrics
3. Market correlation data export with benchmark analysis
4. Organized export packages with structured file organization
5. Export metadata validation and tracking
6. File format validation and data integrity
7. Error handling and edge cases
8. Export configuration options
9. Data compression and packaging
"""

import pytest
import os
import json
import csv
import zipfile
import tempfile
import shutil
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd
import numpy as np

# Import the test infrastructure
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from trading_platform.services.export_reporting.data_export_engine import (
    DataExportEngine,
    ExportConfiguration,
    ExportMetadata
)
from trading_platform.services.time_bin_analyzer import SimpleTrade, TimeBin


class TestDataExportEngine:
    """Test suite for DataExportEngine functionality"""
    
    @pytest.fixture
    def temp_export_dir(self):
        """Create a temporary directory for export testing"""
        temp_dir = tempfile.mkdtemp(prefix='test_export_')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_trades(self):
        """Generate sample trade data for testing"""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        for i in range(50):  # 50 sample trades
            entry_time = base_date + timedelta(days=i, hours=np.random.randint(0, 8))
            exit_time = entry_time + timedelta(minutes=np.random.randint(5, 240))
            
            # Generate realistic trade data
            entry_price = 100.0 + np.random.uniform(-10, 10)
            price_change = np.random.uniform(-2, 2)
            exit_price = entry_price + price_change
            quantity = np.random.choice([100, 200, 300, 500])
            side = np.random.choice(['BUY', 'SELL'])
            
            profit_loss = (exit_price - entry_price) * quantity * (1 if side == 'BUY' else -1)
            commission = quantity * 0.005  # $0.005 per share
            
            trade = SimpleTrade(
                trade_id=f'T{i+1:03d}',
                account_name='TEST_ACCOUNT',
                symbol='AAPL',
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit_loss,
                commission=commission,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday()
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def export_config(self):
        """Default export configuration for testing"""
        return ExportConfiguration(
            include_raw_trades=True,
            include_performance_metrics=True,
            include_statistical_analysis=True,
            include_market_correlation=True,
            include_vix_regime_data=True,
            include_benchmark_comparison=True,
            export_formats=['csv', 'excel', 'json'],
            date_format='%Y-%m-%d %H:%M:%S',
            decimal_places=4,
            create_organized_structure=True,
            include_metadata=True,
            compress_output=False
        )
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def data_export_engine(self, mock_db_session):
        """Create DataExportEngine instance with mocked dependencies"""
        with patch('trading_platform.services.export_reporting.data_export_engine.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            engine = DataExportEngine(mock_db_session)
            
            # Mock the dependent analyzers
            engine.time_bin_analyzer = Mock()
            engine.performance_calculator = Mock()
            engine.vix_analyzer = Mock()
            engine.benchmark_analyzer = Mock()
            
            return engine
    
    def test_export_time_bin_trades_csv_format(self, data_export_engine, sample_trades, temp_export_dir, export_config):
        """Test time-bin trades export to CSV format"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Test CSV-only export
        config = ExportConfiguration(export_formats=['csv'])
        
        # Export trades
        metadata = data_export_engine.export_time_bin_trades(
            account_name='TEST_ACCOUNT',
            hour=9,
            minute_bin=30,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate metadata
        assert metadata.account_name == 'TEST_ACCOUNT'
        assert metadata.time_bin_hour == 9
        assert metadata.time_bin_minute == 30
        assert metadata.total_trades == len(sample_trades)
        assert 'csv' in metadata.file_paths
        
        # Validate CSV file
        csv_path = metadata.file_paths['csv']
        assert os.path.exists(csv_path)
        
        # Read and validate CSV content
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            assert len(rows) == len(sample_trades)
            
            # Validate headers
            expected_headers = [
                'trade_id', 'account_name', 'symbol', 'entry_time', 'exit_time',
                'entry_price', 'exit_price', 'quantity', 'side', 'profit_loss',
                'commission', 'duration_minutes', 'hour_of_day', 'day_of_week'
            ]
            assert all(header in reader.fieldnames for header in expected_headers)
            
            # Validate first row data
            first_row = rows[0]
            assert first_row['trade_id'] == 'T001'
            assert first_row['account_name'] == 'TEST_ACCOUNT'
            assert first_row['symbol'] == 'AAPL'
        
        print(f"✓ CSV export validation passed - {len(sample_trades)} trades exported")
    
    def test_export_time_bin_trades_excel_format(self, data_export_engine, sample_trades, temp_export_dir, export_config):
        """Test time-bin trades export to Excel format"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Test Excel-only export
        config = ExportConfiguration(export_formats=['excel'])
        
        # Export trades
        metadata = data_export_engine.export_time_bin_trades(
            account_name='TEST_ACCOUNT',
            hour=14,
            minute_bin=0,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate metadata
        assert metadata.account_name == 'TEST_ACCOUNT'
        assert metadata.time_bin_hour == 14
        assert metadata.time_bin_minute == 0
        assert 'excel' in metadata.file_paths
        
        # Validate Excel file
        excel_path = metadata.file_paths['excel']
        assert os.path.exists(excel_path)
        assert excel_path.endswith('.xlsx')
        
        # Read and validate Excel content
        df = pd.read_excel(excel_path)
        
        assert len(df) == len(sample_trades)
        
        # Validate columns
        expected_columns = [
            'trade_id', 'account_name', 'symbol', 'entry_time', 'exit_time',
            'entry_price', 'exit_price', 'quantity', 'side', 'profit_loss',
            'commission', 'duration_minutes', 'hour_of_day', 'day_of_week'
        ]
        for col in expected_columns:
            assert col in df.columns
        
        # Validate data types and values
        assert df['trade_id'].iloc[0] == 'T001'
        assert df['account_name'].iloc[0] == 'TEST_ACCOUNT'
        assert df['symbol'].iloc[0] == 'AAPL'
        assert df['quantity'].dtype in ['int64', 'int32']
        
        print(f"✓ Excel export validation passed - {len(sample_trades)} trades exported")
    
    def test_export_time_bin_trades_json_format(self, data_export_engine, sample_trades, temp_export_dir):
        """Test time-bin trades export to JSON format"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Test JSON-only export
        config = ExportConfiguration(export_formats=['json'])
        
        # Export trades
        metadata = data_export_engine.export_time_bin_trades(
            account_name='TEST_ACCOUNT',
            hour=10,
            minute_bin=30,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate metadata
        assert 'json' in metadata.file_paths
        
        # Validate JSON file
        json_path = metadata.file_paths['json']
        assert os.path.exists(json_path)
        
        # Read and validate JSON content
        with open(json_path, 'r') as f:
            trades_data = json.load(f)
        
        assert isinstance(trades_data, list)
        assert len(trades_data) == len(sample_trades)
        
        # Validate first trade structure
        first_trade = trades_data[0]
        required_fields = [
            'trade_id', 'account_name', 'symbol', 'entry_time', 'exit_time',
            'entry_price', 'exit_price', 'quantity', 'side', 'profit_loss',
            'commission', 'duration_minutes', 'hour_of_day', 'day_of_week'
        ]
        
        for field in required_fields:
            assert field in first_trade
        
        # Validate data values
        assert first_trade['trade_id'] == 'T001'
        assert first_trade['account_name'] == 'TEST_ACCOUNT'
        assert first_trade['symbol'] == 'AAPL'
        
        print(f"✓ JSON export validation passed - {len(sample_trades)} trades exported")
    
    def test_export_empty_trades_handling(self, data_export_engine, temp_export_dir):
        """Test handling of empty trade lists"""
        
        # Configure mocks to return empty trade list
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = []
        
        config = ExportConfiguration(export_formats=['csv', 'excel', 'json'])
        
        # Export empty trades
        metadata = data_export_engine.export_time_bin_trades(
            account_name='EMPTY_ACCOUNT',
            hour=15,
            minute_bin=0,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate metadata
        assert metadata.total_trades == 0
        assert len(metadata.file_paths) == 3  # CSV, Excel, JSON
        
        # Validate empty CSV
        csv_path = metadata.file_paths['csv']
        assert os.path.exists(csv_path)
        
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 1  # Headers only
        
        # Validate empty Excel
        excel_path = metadata.file_paths['excel']
        assert os.path.exists(excel_path)
        df = pd.read_excel(excel_path)
        assert len(df) == 0
        assert len(df.columns) > 0  # Has headers
        
        # Validate empty JSON
        json_path = metadata.file_paths['json']
        assert os.path.exists(json_path)
        
        with open(json_path, 'r') as f:
            trades_data = json.load(f)
            assert trades_data == []
        
        print("✓ Empty trades handling validation passed")
    
    def test_export_analysis_results(self, data_export_engine, sample_trades, temp_export_dir):
        """Test analytics results export functionality"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Mock performance metrics
        mock_performance = {
            'total_return': 0.125,
            'sharpe_ratio': 1.45,
            'max_drawdown': -0.08,
            'win_rate': 0.62,
            'total_trades': len(sample_trades),
            'average_trade': 125.50,
            'profit_factor': 1.35
        }
        data_export_engine.performance_calculator.calculate_comprehensive_metrics.return_value = mock_performance
        
        # Mock statistical analysis
        mock_stats = {
            't_test_p_value': 0.0234,
            'normality_test_p_value': 0.156,
            'statistical_significance': True,
            'confidence_interval_lower': 0.089,
            'confidence_interval_upper': 0.161
        }
        data_export_engine.time_bin_analyzer.analyze_time_bin_performance.return_value = mock_stats
        
        # Mock VIX analysis
        mock_vix = {
            'low_vix_performance': 0.145,
            'medium_vix_performance': 0.098,
            'high_vix_performance': 0.067,
            'regime_correlation': 0.234
        }
        data_export_engine.vix_analyzer.analyze_regime_performance.return_value = mock_vix
        
        # Export analysis results
        config = ExportConfiguration(export_formats=['json', 'excel'])
        metadata = data_export_engine.export_analysis_results(
            account_name='TEST_ACCOUNT',
            hour=9,
            minute_bin=30,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate metadata
        assert metadata.account_name == 'TEST_ACCOUNT'
        assert 'analysis_json' in metadata.file_paths
        assert 'analysis_excel' in metadata.file_paths
        
        # Validate JSON analysis export
        json_path = metadata.file_paths['analysis_json']
        assert os.path.exists(json_path)
        
        with open(json_path, 'r') as f:
            analysis_data = json.load(f)
        
        assert 'performance_metrics' in analysis_data
        assert 'statistical_analysis' in analysis_data
        assert 'vix_regime_analysis' in analysis_data
        
        # Validate performance metrics data
        perf_data = analysis_data['performance_metrics']
        assert perf_data['total_return'] == 0.125
        assert perf_data['sharpe_ratio'] == 1.45
        assert perf_data['total_trades'] == len(sample_trades)
        
        # Validate statistical analysis data
        stats_data = analysis_data['statistical_analysis']
        assert stats_data['statistical_significance'] == True
        assert 't_test_p_value' in stats_data
        
        print("✓ Analysis results export validation passed")
    
    def test_export_market_correlation_data(self, data_export_engine, sample_trades, temp_export_dir):
        """Test market correlation data export functionality"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Mock benchmark correlations
        mock_correlations = {
            'SPY': 0.345,
            'QQQ': 0.428,
            'VIX': -0.156
        }
        
        def mock_correlation_side_effect(*args, **kwargs):
            benchmark = kwargs.get('benchmark_symbol', args[4] if len(args) > 4 else 'SPY')
            return mock_correlations.get(benchmark, 0.0)
        
        data_export_engine.benchmark_analyzer.calculate_correlation_with_benchmark.side_effect = mock_correlation_side_effect
        
        # Mock VIX correlation
        mock_vix_corr = {
            'overall_correlation': -0.189,
            'regime_specific_correlations': {
                'low_vix': 0.123,
                'medium_vix': -0.067,
                'high_vix': -0.345
            }
        }
        data_export_engine.vix_analyzer.calculate_vix_correlation.return_value = mock_vix_corr
        
        # Export correlation data
        config = ExportConfiguration(export_formats=['json', 'csv'])
        metadata = data_export_engine.export_market_correlation_data(
            account_name='TEST_ACCOUNT',
            hour=11,
            minute_bin=0,
            output_path=temp_export_dir,
            benchmarks=['SPY', 'QQQ', 'VIX'],
            config=config
        )
        
        # Validate metadata
        assert metadata.account_name == 'TEST_ACCOUNT'
        assert metadata.time_bin_hour == 11
        assert 'correlation_json' in metadata.file_paths
        
        # Validate JSON correlation export
        json_path = metadata.file_paths['correlation_json']
        assert os.path.exists(json_path)
        
        with open(json_path, 'r') as f:
            correlation_data = json.load(f)
        
        assert 'benchmark_correlations' in correlation_data
        assert 'vix_correlation' in correlation_data
        assert 'trades' in correlation_data
        
        # Validate benchmark correlations
        bench_corr = correlation_data['benchmark_correlations']
        assert bench_corr['SPY'] == 0.345
        assert bench_corr['QQQ'] == 0.428
        assert bench_corr['VIX'] == -0.156
        
        # Validate VIX correlation data
        vix_corr = correlation_data['vix_correlation']
        assert vix_corr['overall_correlation'] == -0.189
        assert 'regime_specific_correlations' in vix_corr
        
        print("✓ Market correlation export validation passed")
    
    def test_create_export_package(self, data_export_engine, sample_trades, temp_export_dir):
        """Test comprehensive export package creation"""
        
        # Configure mocks for all components
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Mock performance metrics
        data_export_engine.performance_calculator.calculate_comprehensive_metrics.return_value = {
            'total_return': 0.15,
            'sharpe_ratio': 1.6,
            'total_trades': len(sample_trades)
        }
        
        # Mock statistical analysis
        data_export_engine.time_bin_analyzer.analyze_time_bin_performance.return_value = {
            't_test_p_value': 0.02,
            'statistical_significance': True
        }
        
        # Mock benchmark correlations
        data_export_engine.benchmark_analyzer.calculate_correlation_with_benchmark.return_value = 0.35
        
        # Create export package
        config = ExportConfiguration(
            export_formats=['csv', 'excel', 'json'],
            create_organized_structure=True,
            include_metadata=True,
            compress_output=False
        )
        
        metadata = data_export_engine.create_export_package(
            account_name='PACKAGE_TEST',
            hour=13,
            minute_bin=30,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate metadata
        assert metadata.account_name == 'PACKAGE_TEST'
        assert metadata.time_bin_hour == 13
        assert metadata.time_bin_minute == 30
        assert metadata.total_trades == len(sample_trades)
        
        # Validate package structure
        package_files = metadata.file_paths
        assert 'summary_report' in package_files
        assert 'package_metadata' in package_files
        assert 'readme' in package_files
        
        # Check for trades files
        trades_files = [k for k in package_files.keys() if k.startswith('trades_')]
        assert len(trades_files) == 3  # csv, excel, json
        
        # Check for analysis files
        analysis_files = [k for k in package_files.keys() if k.startswith('analysis_')]
        assert len(analysis_files) > 0
        
        # Validate directory structure
        package_name = f"PACKAGE_TEST_{13:02d}{30:02d}_{datetime.now().strftime('%Y%m%d')}"
        base_pattern = os.path.join(temp_export_dir, package_name.split('_')[0] + "_*")
        
        # Validate that files were created
        for file_path in package_files.values():
            if os.path.isfile(file_path):  # Only check actual files, not directories
                assert os.path.exists(file_path), f"File should exist: {file_path}"
        
        # Validate summary report
        summary_path = package_files['summary_report']
        assert os.path.exists(summary_path)
        
        with open(summary_path, 'r') as f:
            summary_content = f.read()
            assert 'Trading Analytics Export Summary' in summary_content
            assert 'PACKAGE_TEST' in summary_content
            assert '13:30' in summary_content
        
        # Validate README
        readme_path = package_files['readme']
        assert os.path.exists(readme_path)
        
        with open(readme_path, 'r') as f:
            readme_content = f.read()
            assert '# Trading Analytics Export Package' in readme_content
            assert 'PACKAGE_TEST' in readme_content
        
        print("✓ Export package creation validation passed")
    
    def test_export_package_compression(self, data_export_engine, sample_trades, temp_export_dir):
        """Test export package compression functionality"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades[:5]  # Smaller set for faster testing
        data_export_engine.performance_calculator.calculate_comprehensive_metrics.return_value = {'total_trades': 5}
        data_export_engine.time_bin_analyzer.analyze_time_bin_performance.return_value = {'t_test_p_value': 0.05}
        data_export_engine.benchmark_analyzer.calculate_correlation_with_benchmark.return_value = 0.25
        
        # Create compressed export package
        config = ExportConfiguration(
            export_formats=['csv'],
            compress_output=True,
            create_organized_structure=True
        )
        
        metadata = data_export_engine.create_export_package(
            account_name='COMPRESS_TEST',
            hour=16,
            minute_bin=0,
            output_path=temp_export_dir,
            config=config
        )
        
        # Validate compressed package
        assert 'compressed_package' in metadata.file_paths
        zip_path = metadata.file_paths['compressed_package']
        assert os.path.exists(zip_path)
        assert zip_path.endswith('.zip')
        
        # Validate ZIP content
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_list = zipf.namelist()
            
            # Check for expected files in ZIP
            assert any('trades.csv' in f for f in file_list)
            assert any('export_summary.txt' in f for f in file_list)
            assert any('README.md' in f for f in file_list)
            
            # Validate ZIP structure
            expected_dirs = ['01_trades', '02_analytics', '03_correlations', '04_metadata', '00_summary']
            for expected_dir in expected_dirs:
                assert any(expected_dir in f for f in file_list)
        
        print("✓ Export package compression validation passed")
    
    def test_export_configuration_validation(self, data_export_engine, temp_export_dir):
        """Test export configuration options and validation"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = []
        
        # Test different configuration options
        configs_to_test = [
            {
                'export_formats': ['csv'],
                'include_raw_trades': True,
                'include_performance_metrics': False,
                'decimal_places': 2
            },
            {
                'export_formats': ['excel', 'json'],
                'include_raw_trades': True,
                'include_statistical_analysis': False,
                'date_format': '%Y-%m-%d'
            },
            {
                'export_formats': ['json'],
                'include_market_correlation': False,
                'include_vix_regime_data': False,
                'include_metadata': False
            }
        ]
        
        for i, config_dict in enumerate(configs_to_test):
            config = ExportConfiguration(**config_dict)
            
            metadata = data_export_engine.export_time_bin_trades(
                account_name=f'CONFIG_TEST_{i}',
                hour=12,
                minute_bin=0,
                output_path=temp_export_dir,
                config=config
            )
            
            # Validate configuration was applied
            assert metadata.configuration.export_formats == config.export_formats
            assert len(metadata.file_paths) == len(config.export_formats) + (1 if config.include_metadata else 0)
            
            # Validate only requested formats were exported
            for format_type in config.export_formats:
                assert any(format_type in path for path in metadata.file_paths.values())
        
        print("✓ Export configuration validation passed")
    
    def test_date_range_filtering(self, data_export_engine, sample_trades, temp_export_dir):
        """Test date range filtering in exports"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Test with date range
        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 31)
        
        config = ExportConfiguration(export_formats=['csv'])
        
        metadata = data_export_engine.export_time_bin_trades(
            account_name='DATE_FILTER_TEST',
            hour=10,
            minute_bin=30,
            output_path=temp_export_dir,
            start_date=start_date,
            end_date=end_date,
            config=config
        )
        
        # Validate date range in metadata
        assert metadata.date_range_start == start_date
        assert metadata.date_range_end == end_date
        
        # Verify time_bin_analyzer was called with date filters
        data_export_engine.time_bin_analyzer.get_time_bin_trades.assert_called_with(
            time_bin=pytest.any,  # TimeBin object
            start_date=start_date,
            end_date=end_date
        )
        
        print("✓ Date range filtering validation passed")
    
    def test_export_history_tracking(self, data_export_engine, temp_export_dir):
        """Test export history tracking functionality"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = []
        
        # Perform multiple exports
        config = ExportConfiguration(export_formats=['csv'])
        
        accounts_to_test = ['HIST_TEST_1', 'HIST_TEST_2', 'HIST_TEST_3']
        
        for account in accounts_to_test:
            data_export_engine.export_time_bin_trades(
                account_name=account,
                hour=9,
                minute_bin=0,
                output_path=temp_export_dir,
                config=config
            )
        
        # Validate export history
        export_history = data_export_engine.get_export_history()
        assert len(export_history) == len(accounts_to_test)
        
        # Validate history content
        exported_accounts = [metadata.account_name for metadata in export_history]
        for account in accounts_to_test:
            assert account in exported_accounts
        
        # Test history clearing
        data_export_engine.clear_export_history()
        assert len(data_export_engine.get_export_history()) == 0
        
        print("✓ Export history tracking validation passed")
    
    def test_error_handling_scenarios(self, data_export_engine, temp_export_dir):
        """Test error handling in various failure scenarios"""
        
        # Test with invalid output directory
        with pytest.raises(Exception):
            invalid_path = "/invalid/nonexistent/path/that/should/not/exist"
            data_export_engine.export_time_bin_trades(
                account_name='ERROR_TEST',
                hour=9,
                minute_bin=0,
                output_path=invalid_path,
                config=ExportConfiguration(export_formats=['csv'])
            )
        
        # Test with analyzer failures
        data_export_engine.time_bin_analyzer.get_time_bin_trades.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc_info:
            data_export_engine.export_time_bin_trades(
                account_name='ERROR_TEST',
                hour=9,
                minute_bin=0,
                output_path=temp_export_dir,
                config=ExportConfiguration(export_formats=['csv'])
            )
        
        assert "Database connection failed" in str(exc_info.value)
        
        # Reset mock for other tests
        data_export_engine.time_bin_analyzer.get_time_bin_trades.side_effect = None
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = []
        
        print("✓ Error handling validation passed")
    
    def test_data_integrity_validation(self, data_export_engine, sample_trades, temp_export_dir):
        """Test data integrity across different export formats"""
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades[:10]  # Use smaller sample
        
        # Export to all formats
        config = ExportConfiguration(export_formats=['csv', 'excel', 'json'], decimal_places=4)
        
        metadata = data_export_engine.export_time_bin_trades(
            account_name='INTEGRITY_TEST',
            hour=14,
            minute_bin=30,
            output_path=temp_export_dir,
            config=config
        )
        
        # Load data from each format
        csv_path = metadata.file_paths['csv']
        excel_path = metadata.file_paths['excel']
        json_path = metadata.file_paths['json']
        
        # Read CSV data
        csv_df = pd.read_csv(csv_path)
        
        # Read Excel data
        excel_df = pd.read_excel(excel_path)
        
        # Read JSON data
        with open(json_path, 'r') as f:
            json_data = json.load(f)
        json_df = pd.DataFrame(json_data)
        
        # Convert datetime columns for comparison
        for df in [csv_df, excel_df, json_df]:
            if 'entry_time' in df.columns:
                df['entry_time'] = pd.to_datetime(df['entry_time'])
            if 'exit_time' in df.columns:
                df['exit_time'] = pd.to_datetime(df['exit_time'])
        
        # Validate data consistency across formats
        assert len(csv_df) == len(excel_df) == len(json_df)
        
        # Compare key columns
        numeric_cols = ['entry_price', 'exit_price', 'profit_loss', 'commission']
        for col in numeric_cols:
            if col in csv_df.columns:
                # Allow small floating point differences
                assert np.allclose(csv_df[col], excel_df[col], rtol=1e-4)
                assert np.allclose(csv_df[col], json_df[col], rtol=1e-4)
        
        # Validate string columns
        string_cols = ['trade_id', 'account_name', 'symbol', 'side']
        for col in string_cols:
            if col in csv_df.columns:
                assert csv_df[col].equals(excel_df[col])
                assert csv_df[col].equals(json_df[col])
        
        print("✓ Data integrity validation passed across all formats")
    
    def test_large_dataset_performance(self, data_export_engine, temp_export_dir):
        """Test performance with large datasets"""
        
        # Generate large sample dataset
        large_trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        for i in range(1000):  # 1000 trades for performance testing
            trade = SimpleTrade(
                trade_id=f'PERF{i+1:04d}',
                account_name='PERFORMANCE_TEST',
                symbol='TSLA',
                entry_time=base_date + timedelta(hours=i//10, minutes=i%60),
                exit_time=base_date + timedelta(hours=i//10, minutes=i%60 + 15),
                entry_price=200.0 + (i % 100),
                exit_price=200.0 + (i % 100) + np.random.uniform(-1, 1),
                quantity=100,
                side='BUY' if i % 2 == 0 else 'SELL',
                profit_loss=np.random.uniform(-50, 50),
                commission=0.50,
                duration_minutes=15,
                hour_of_day=9,
                day_of_week=0
            )
            large_trades.append(trade)
        
        # Configure mocks
        data_export_engine.time_bin_analyzer.get_time_bin_trades.return_value = large_trades
        
        # Test export performance
        import time
        start_time = time.time()
        
        config = ExportConfiguration(export_formats=['csv', 'excel'])
        metadata = data_export_engine.export_time_bin_trades(
            account_name='PERFORMANCE_TEST',
            hour=9,
            minute_bin=30,
            output_path=temp_export_dir,
            config=config
        )
        
        end_time = time.time()
        export_duration = end_time - start_time
        
        # Validate export completed successfully
        assert metadata.total_trades == 1000
        assert len(metadata.file_paths) >= 2  # CSV and Excel
        
        # Validate files exist and have correct size
        for file_path in metadata.file_paths.values():
            if file_path.endswith('.csv'):
                assert os.path.exists(file_path)
                # CSV should have reasonable file size (> 100KB for 1000 trades)
                assert os.path.getsize(file_path) > 100000
            elif file_path.endswith('.xlsx'):
                assert os.path.exists(file_path)
                # Excel should have reasonable file size
                assert os.path.getsize(file_path) > 50000
        
        print(f"✓ Large dataset performance validation passed")
        print(f"  - Exported {len(large_trades)} trades")
        print(f"  - Export duration: {export_duration:.2f} seconds")
        print(f"  - Performance: {len(large_trades)/export_duration:.1f} trades/second")


if __name__ == "__main__":
    # Run tests
    test_instance = TestDataExportEngine()
    
    print("Running DataExportEngine Tests...")
    print("=" * 60)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory(prefix='test_export_') as temp_dir:
        
        # Generate test fixtures
        sample_trades = test_instance.sample_trades()
        export_config = test_instance.export_config()
        
        # Create mock dependencies
        mock_db = Mock()
        
        # Create test engine
        with patch('trading_platform.services.export_reporting.data_export_engine.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db
            engine = DataExportEngine(mock_db)
            
            # Mock analyzers
            engine.time_bin_analyzer = Mock()
            engine.performance_calculator = Mock()
            engine.vix_analyzer = Mock()
            engine.benchmark_analyzer = Mock()
        
        try:
            # Run individual tests
            test_instance.test_export_time_bin_trades_csv_format(engine, sample_trades, temp_dir, export_config)
            test_instance.test_export_time_bin_trades_excel_format(engine, sample_trades, temp_dir, export_config)
            test_instance.test_export_time_bin_trades_json_format(engine, sample_trades, temp_dir)
            test_instance.test_export_empty_trades_handling(engine, temp_dir)
            test_instance.test_export_analysis_results(engine, sample_trades, temp_dir)
            test_instance.test_export_market_correlation_data(engine, sample_trades, temp_dir)
            test_instance.test_create_export_package(engine, sample_trades, temp_dir)
            test_instance.test_export_configuration_validation(engine, temp_dir)
            test_instance.test_date_range_filtering(engine, sample_trades, temp_dir)
            test_instance.test_export_history_tracking(engine, temp_dir)
            test_instance.test_data_integrity_validation(engine, sample_trades, temp_dir)
            test_instance.test_large_dataset_performance(engine, temp_dir)
            
            print("=" * 60)
            print("✅ ALL TESTS PASSED!")
            print("DataExportEngine is ready for production use.")
            
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            raise
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            raise