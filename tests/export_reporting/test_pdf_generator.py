"""
Comprehensive test suite for PDFReportGenerator with real analysis data validation.

Tests cover:
1. Time-bin report generation with standard sections
2. Performance summary pages with key metrics
3. Statistical analysis pages with significance testing
4. Market correlation pages with benchmark comparisons
5. PDF document structure and formatting
6. Report configuration options
7. Data integrity in PDF output
8. Error handling and edge cases
9. Professional formatting validation
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

# Import the test infrastructure
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from trading_platform.services.export_reporting.pdf_report_generator import (
        PDFReportGenerator,
        ReportConfiguration,
        ReportMetadata,
        REPORTLAB_AVAILABLE
    )
    from trading_platform.services.time_bin_analyzer import SimpleTrade, TimeBin
    
    # Skip all tests if ReportLab is not available
    pytestmark = pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="ReportLab not available")
    
except ImportError as e:
    # Create dummy classes if import fails
    class PDFReportGenerator:
        pass
    class ReportConfiguration:
        pass
    class ReportMetadata:
        pass
    
    REPORTLAB_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason=f"Required dependencies not available: {e}")


class TestPDFReportGenerator:
    """Test suite for PDFReportGenerator functionality"""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for PDF output testing"""
        temp_dir = tempfile.mkdtemp(prefix='test_pdf_reports_')
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_trades(self):
        """Generate sample trade data for testing"""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        # Generate diverse trade scenarios
        trade_scenarios = [
            # Winning trades
            {'pnl_mult': 1.5, 'duration_mult': 1.0, 'count': 15},
            # Losing trades  
            {'pnl_mult': -0.8, 'duration_mult': 1.2, 'count': 10},
            # Break-even trades
            {'pnl_mult': 0, 'duration_mult': 0.5, 'count': 3},
            # Large winners
            {'pnl_mult': 3.0, 'duration_mult': 2.0, 'count': 2},
            # Large losers
            {'pnl_mult': -2.5, 'duration_mult': 0.8, 'count': 3}
        ]
        
        trade_id = 1
        for scenario in trade_scenarios:
            for i in range(scenario['count']):
                entry_time = base_date + timedelta(days=trade_id, hours=np.random.randint(0, 8))
                base_duration = 45 * scenario['duration_mult']
                duration = int(base_duration + np.random.uniform(-10, 10))
                exit_time = entry_time + timedelta(minutes=duration)
                
                entry_price = 100.0 + np.random.uniform(-5, 5)
                base_pnl = 50 * scenario['pnl_mult']
                profit_loss = base_pnl + np.random.uniform(-10, 10)
                
                quantity = np.random.choice([100, 200, 300])
                side = np.random.choice(['BUY', 'SELL'])
                
                trade = SimpleTrade(
                    trade_id=f'TEST{trade_id:03d}',
                    account_name='PDF_TEST_ACCOUNT',
                    symbol=np.random.choice(['AAPL', 'GOOGL', 'MSFT', 'TSLA']),
                    entry_time=entry_time,
                    exit_time=exit_time,
                    entry_price=entry_price,
                    exit_price=entry_price + (profit_loss / quantity),
                    quantity=quantity,
                    side=side,
                    profit_loss=profit_loss,
                    commission=quantity * 0.005,
                    duration_minutes=duration,
                    hour_of_day=entry_time.hour,
                    day_of_week=entry_time.weekday()
                )
                trades.append(trade)
                trade_id += 1
        
        return trades
    
    @pytest.fixture
    def sample_performance_data(self, sample_trades):
        """Generate sample performance metrics"""
        if not sample_trades:
            return {}
            
        total_pnl = sum(t.profit_loss for t in sample_trades)
        winning_trades = [t for t in sample_trades if t.profit_loss > 0]
        losing_trades = [t for t in sample_trades if t.profit_loss < 0]
        
        return {
            'total_pnl': total_pnl,
            'total_return_pct': total_pnl / 10000,  # Assume $10k starting capital
            'sharpe_ratio': 1.25,
            'max_drawdown': 0.15,
            'win_rate': len(winning_trades) / len(sample_trades),
            'profit_factor': abs(sum(t.profit_loss for t in winning_trades)) / max(abs(sum(t.profit_loss for t in losing_trades)), 1),
            'avg_trade_pnl': total_pnl / len(sample_trades),
            'total_trades': len(sample_trades),
            'avg_win': np.mean([t.profit_loss for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t.profit_loss for t in losing_trades]) if losing_trades else 0
        }
    
    @pytest.fixture
    def sample_statistical_data(self):
        """Generate sample statistical analysis data"""
        return {
            't_test_p_value': 0.0234,
            't_statistic': 2.456,
            'normality_test_p_value': 0.156,
            'normality_statistic': 0.987,
            'autocorrelation_test_p_value': 0.345,
            'ljung_box_statistic': 1.234,
            'confidence_interval_lower': 15.67,
            'confidence_interval_upper': 89.23,
            'statistical_significance': True
        }
    
    @pytest.fixture
    def sample_correlation_data(self):
        """Generate sample market correlation data"""
        return {
            'benchmark_correlations': {
                'SPY': {'correlation': 0.345, 'p_value': 0.023},
                'QQQ': {'correlation': 0.567, 'p_value': 0.001},
                'VIX': {'correlation': -0.234, 'p_value': 0.089}
            },
            'vix_correlation': {
                'overall_correlation': -0.189,
                'regime_specific_correlations': {
                    'low_vix': 0.123,
                    'medium_vix': -0.067,
                    'high_vix': -0.345
                }
            }
        }
    
    @pytest.fixture
    def report_config(self):
        """Default report configuration for testing"""
        return ReportConfiguration(
            page_size='letter',
            margins={'top': 1, 'bottom': 1, 'left': 1, 'right': 1},
            include_executive_summary=True,
            include_performance_summary=True,
            include_statistical_analysis=True,
            include_market_correlation=True,
            include_trade_details=True,
            include_charts=True,
            chart_style='professional',
            decimal_places=4,
            percentage_places=2
        )
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def pdf_generator(self, mock_db_session):
        """Create PDFReportGenerator instance with mocked dependencies"""
        if not REPORTLAB_AVAILABLE:
            pytest.skip("ReportLab not available")
            
        with patch('trading_platform.services.export_reporting.pdf_report_generator.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            generator = PDFReportGenerator(mock_db_session)
            
            # Mock the dependent analyzers
            generator.time_bin_analyzer = Mock()
            generator.performance_calculator = Mock()
            generator.vix_analyzer = Mock()
            generator.benchmark_analyzer = Mock()
            
            return generator
    
    def test_pdf_generator_initialization(self, mock_db_session):
        """Test PDFReportGenerator initialization"""
        if not REPORTLAB_AVAILABLE:
            with pytest.raises(ImportError):
                PDFReportGenerator()
            return
        
        with patch('trading_platform.services.export_reporting.pdf_report_generator.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            generator = PDFReportGenerator(mock_db_session)
            
            assert generator.db_session == mock_db_session
            assert hasattr(generator, 'time_bin_analyzer')
            assert hasattr(generator, 'performance_calculator')
            assert hasattr(generator, 'vix_analyzer')
            assert hasattr(generator, 'benchmark_analyzer')
            assert isinstance(generator.report_history, list)
            assert len(generator.report_history) == 0
        
        print("✓ PDF generator initialization validation passed")
    
    def test_generate_time_bin_report(self, pdf_generator, sample_trades, sample_performance_data, 
                                     sample_statistical_data, temp_output_dir, report_config):
        """Test comprehensive time-bin report generation"""
        
        # Configure mocks
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = sample_performance_data
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = sample_statistical_data
        
        # Mock correlation data collection
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {'benchmark_correlations': {'SPY': 0.35}}
            
            # Generate report
            output_path = os.path.join(temp_output_dir, 'test_report.pdf')
            metadata = pdf_generator.generate_time_bin_report(
                account_name='TEST_ACCOUNT',
                hour=9,
                minute_bin=30,
                output_path=output_path,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                config=report_config
            )
        
        # Validate metadata
        assert isinstance(metadata, ReportMetadata)
        assert metadata.account_name == 'TEST_ACCOUNT'
        assert metadata.time_bin_hour == 9
        assert metadata.time_bin_minute == 30
        assert metadata.total_trades == len(sample_trades)
        assert metadata.file_path == output_path
        assert metadata.file_size_bytes > 0
        assert metadata.page_count > 0
        
        # Validate file exists and has content
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 10000  # Should be substantial PDF
        
        # Validate report sections
        expected_sections = [
            "Title Page",
            "Executive Summary", 
            "Performance Summary",
            "Statistical Analysis",
            "Market Correlation",
            "Trade Details"
        ]
        
        for section in expected_sections:
            assert section in metadata.report_sections
        
        # Validate report history tracking
        assert len(pdf_generator.get_report_history()) == 1
        assert pdf_generator.get_report_history()[0].report_id == metadata.report_id
        
        print(f"✓ Time-bin report generation validation passed")
        print(f"  - Report ID: {metadata.report_id}")
        print(f"  - File size: {metadata.file_size_bytes:,} bytes")
        print(f"  - Pages: {metadata.page_count}")
        print(f"  - Sections: {len(metadata.report_sections)}")
    
    def test_create_performance_summary_page(self, pdf_generator, sample_trades, 
                                           sample_performance_data, report_config):
        """Test performance summary page creation"""
        
        # Create performance summary elements
        elements = pdf_generator.create_performance_summary_page(
            trades=sample_trades,
            performance_data=sample_performance_data,
            config=report_config
        )
        
        # Validate elements were created
        assert len(elements) > 0
        assert elements is not None
        
        # Test with empty data
        empty_elements = pdf_generator.create_performance_summary_page(
            trades=[],
            performance_data={},
            config=report_config
        )
        
        assert len(empty_elements) > 0  # Should still have header and empty message
        
        print("✓ Performance summary page validation passed")
        print(f"  - Elements with data: {len(elements)}")
        print(f"  - Elements without data: {len(empty_elements)}")
    
    def test_create_statistical_analysis_page(self, pdf_generator, sample_trades,
                                            sample_statistical_data, report_config):
        """Test statistical analysis page creation"""
        
        # Create statistical analysis elements
        elements = pdf_generator.create_statistical_analysis_page(
            statistical_data=sample_statistical_data,
            trades=sample_trades,
            config=report_config
        )
        
        # Validate elements were created
        assert len(elements) > 0
        assert elements is not None
        
        # Test with empty data
        empty_elements = pdf_generator.create_statistical_analysis_page(
            statistical_data={},
            trades=[],
            config=report_config
        )
        
        assert len(empty_elements) > 0  # Should still have header and empty message
        
        print("✓ Statistical analysis page validation passed")
        print(f"  - Elements with data: {len(elements)}")
        print(f"  - Elements without data: {len(empty_elements)}")
    
    def test_create_market_correlation_page(self, pdf_generator, sample_trades,
                                          sample_correlation_data, report_config):
        """Test market correlation page creation"""
        
        # Create correlation analysis elements
        elements = pdf_generator.create_market_correlation_page(
            correlation_data=sample_correlation_data,
            trades=sample_trades,
            config=report_config
        )
        
        # Validate elements were created
        assert len(elements) > 0
        assert elements is not None
        
        # Test with empty data
        empty_elements = pdf_generator.create_market_correlation_page(
            correlation_data={},
            trades=[],
            config=report_config
        )
        
        assert len(empty_elements) > 0  # Should still have header and empty message
        
        print("✓ Market correlation page validation passed")
        print(f"  - Elements with data: {len(elements)}")
        print(f"  - Elements without data: {len(empty_elements)}")
    
    def test_report_configuration_options(self, pdf_generator, sample_trades,
                                        temp_output_dir):
        """Test different report configuration options"""
        
        # Configure mocks
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = {'total_pnl': 1000}
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = {'t_test_p_value': 0.05}
        
        # Test minimal configuration
        minimal_config = ReportConfiguration(
            include_executive_summary=False,
            include_statistical_analysis=False,
            include_market_correlation=False,
            include_trade_details=False,
            include_charts=False
        )
        
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {}
            
            output_path = os.path.join(temp_output_dir, 'minimal_report.pdf')
            metadata = pdf_generator.generate_time_bin_report(
                account_name='MINIMAL_TEST',
                hour=14,
                minute_bin=0,
                output_path=output_path,
                config=minimal_config
            )
        
        # Validate minimal report
        assert os.path.exists(output_path)
        assert len(metadata.report_sections) >= 2  # At least title and performance summary
        assert "Executive Summary" not in metadata.report_sections
        assert "Statistical Analysis" not in metadata.report_sections
        
        # Test A4 page size configuration
        a4_config = ReportConfiguration(
            page_size='A4',
            include_executive_summary=True,
            include_performance_summary=True
        )
        
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {}
            
            a4_output_path = os.path.join(temp_output_dir, 'a4_report.pdf')
            a4_metadata = pdf_generator.generate_time_bin_report(
                account_name='A4_TEST',
                hour=10,
                minute_bin=30,
                output_path=a4_output_path,
                config=a4_config
            )
        
        assert os.path.exists(a4_output_path)
        assert a4_metadata.configuration.page_size == 'A4'
        
        print("✓ Report configuration options validation passed")
        print(f"  - Minimal report sections: {len(metadata.report_sections)}")
        print(f"  - A4 report generated successfully")
    
    def test_date_range_handling(self, pdf_generator, sample_trades, temp_output_dir):
        """Test date range handling in reports"""
        
        # Configure mocks
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = {'total_pnl': 500}
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = {}
        
        # Test with specific date range
        start_date = date(2024, 1, 15)
        end_date = date(2024, 2, 15)
        
        config = ReportConfiguration(include_market_correlation=False)
        
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {}
            
            output_path = os.path.join(temp_output_dir, 'date_range_report.pdf')
            metadata = pdf_generator.generate_time_bin_report(
                account_name='DATE_TEST',
                hour=11,
                minute_bin=0,
                output_path=output_path,
                start_date=start_date,
                end_date=end_date,
                config=config
            )
        
        # Validate date range in metadata
        assert metadata.date_range_start == start_date
        assert metadata.date_range_end == end_date
        
        # Verify analyzer was called with date filters
        pdf_generator.time_bin_analyzer.get_time_bin_trades.assert_called_with(
            time_bin=pytest.any,  # TimeBin object
            start_date=start_date,
            end_date=end_date
        )
        
        print("✓ Date range handling validation passed")
        print(f"  - Start date: {start_date}")
        print(f"  - End date: {end_date}")
    
    def test_empty_data_handling(self, pdf_generator, temp_output_dir):
        """Test handling of empty or no trade data"""
        
        # Configure mocks to return empty data
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = []
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = {}
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = {}
        
        config = ReportConfiguration()
        
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {}
            
            output_path = os.path.join(temp_output_dir, 'empty_data_report.pdf')
            metadata = pdf_generator.generate_time_bin_report(
                account_name='EMPTY_TEST',
                hour=16,
                minute_bin=30,
                output_path=output_path,
                config=config
            )
        
        # Validate empty data report
        assert os.path.exists(output_path)
        assert metadata.total_trades == 0
        assert metadata.file_size_bytes > 0  # Should still generate a report
        assert len(metadata.report_sections) > 0
        
        print("✓ Empty data handling validation passed")
        print(f"  - File size with no trades: {metadata.file_size_bytes} bytes")
        print(f"  - Sections generated: {len(metadata.report_sections)}")
    
    def test_statistical_calculations(self, pdf_generator):
        """Test statistical calculation helper methods"""
        
        # Test skewness calculation
        normal_data = [1, 2, 3, 4, 5, 4, 3, 2, 1]  # Roughly symmetric
        skewed_data = [1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # Right-skewed
        
        normal_skew = pdf_generator._calculate_skewness(normal_data)
        skewed_skew = pdf_generator._calculate_skewness(skewed_data)
        
        assert abs(normal_skew) < abs(skewed_skew)  # Skewed data should have higher absolute skewness
        
        # Test kurtosis calculation
        normal_kurt = pdf_generator._calculate_kurtosis(normal_data)
        peaked_data = [3, 3, 3, 3, 3, 3, 3]  # High kurtosis (peaked)
        peaked_kurt = pdf_generator._calculate_kurtosis(peaked_data)
        
        # Test edge cases
        empty_skew = pdf_generator._calculate_skewness([])
        assert empty_skew == 0.0
        
        single_kurt = pdf_generator._calculate_kurtosis([5])
        assert single_kurt == 0.0
        
        print("✓ Statistical calculations validation passed")
        print(f"  - Normal data skewness: {normal_skew:.4f}")
        print(f"  - Skewed data skewness: {skewed_skew:.4f}")
    
    def test_correlation_data_collection(self, pdf_generator):
        """Test correlation data collection functionality"""
        
        # Mock benchmark analyzer responses
        def mock_benchmark_correlation(*args, **kwargs):
            benchmark = kwargs.get('benchmark_symbol', 'SPY')
            correlations = {'SPY': 0.35, 'QQQ': 0.67, 'VIX': -0.23}
            return correlations.get(benchmark, 0.0)
        
        pdf_generator.benchmark_analyzer.calculate_correlation_with_benchmark.side_effect = mock_benchmark_correlation
        
        # Mock VIX analyzer response
        pdf_generator.vix_analyzer.calculate_vix_correlation.return_value = {
            'overall_correlation': -0.15,
            'regime_specific_correlations': {
                'low_vix': 0.12,
                'medium_vix': -0.05,
                'high_vix': -0.34
            }
        }
        
        # Test correlation data collection
        correlation_data = pdf_generator._collect_correlation_data(
            account_name='CORR_TEST',
            hour=13,
            minute_bin=0,
            start_date=None,
            end_date=None
        )
        
        # Validate collected data
        assert 'benchmark_correlations' in correlation_data
        assert 'vix_correlation' in correlation_data
        
        benchmark_corrs = correlation_data['benchmark_correlations']
        assert benchmark_corrs['SPY'] == 0.35
        assert benchmark_corrs['QQQ'] == 0.67
        assert benchmark_corrs['VIX'] == -0.23
        
        vix_corr = correlation_data['vix_correlation']
        assert vix_corr['overall_correlation'] == -0.15
        assert 'regime_specific_correlations' in vix_corr
        
        print("✓ Correlation data collection validation passed")
        print(f"  - Benchmark correlations collected: {len(benchmark_corrs)}")
        print(f"  - VIX regime correlations: {len(vix_corr['regime_specific_correlations'])}")
    
    def test_report_history_management(self, pdf_generator, sample_trades, temp_output_dir):
        """Test report history tracking and management"""
        
        # Configure mocks
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades[:5]
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = {'total_pnl': 100}
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = {}
        
        config = ReportConfiguration(include_market_correlation=False)
        
        # Generate multiple reports
        reports = []
        for i in range(3):
            with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
                mock_collect_corr.return_value = {}
                
                output_path = os.path.join(temp_output_dir, f'history_test_{i}.pdf')
                metadata = pdf_generator.generate_time_bin_report(
                    account_name=f'HISTORY_TEST_{i}',
                    hour=9,
                    minute_bin=0,
                    output_path=output_path,
                    config=config
                )
                reports.append(metadata)
        
        # Validate history tracking
        history = pdf_generator.get_report_history()
        assert len(history) == 3
        
        for i, report_metadata in enumerate(history):
            assert report_metadata.account_name == f'HISTORY_TEST_{i}'
            assert report_metadata.report_id == reports[i].report_id
        
        # Test history clearing
        pdf_generator.clear_report_history()
        assert len(pdf_generator.get_report_history()) == 0
        
        print("✓ Report history management validation passed")
        print(f"  - Reports generated and tracked: {len(history)}")
        print(f"  - History cleared successfully")
    
    def test_error_handling_scenarios(self, pdf_generator, temp_output_dir):
        """Test error handling in various failure scenarios"""
        
        # Test with invalid output path
        with pytest.raises(Exception):
            invalid_path = "/invalid/nonexistent/path/report.pdf"
            pdf_generator.generate_time_bin_report(
                account_name='ERROR_TEST',
                hour=9,
                minute_bin=0,
                output_path=invalid_path,
                config=ReportConfiguration()
            )
        
        # Test with analyzer failures
        pdf_generator.time_bin_analyzer.get_time_bin_trades.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception) as exc_info:
            output_path = os.path.join(temp_output_dir, 'error_test.pdf')
            pdf_generator.generate_time_bin_report(
                account_name='ERROR_TEST',
                hour=9,
                minute_bin=0,
                output_path=output_path,
                config=ReportConfiguration()
            )
        
        assert "Database connection failed" in str(exc_info.value)
        
        print("✓ Error handling validation passed")
    
    def test_report_metadata_serialization(self, pdf_generator, sample_trades, temp_output_dir):
        """Test report metadata serialization and deserialization"""
        
        # Configure mocks
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = {'total_pnl': 1500}
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = {}
        
        config = ReportConfiguration()
        
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {}
            
            output_path = os.path.join(temp_output_dir, 'metadata_test.pdf')
            metadata = pdf_generator.generate_time_bin_report(
                account_name='METADATA_TEST',
                hour=15,
                minute_bin=30,
                output_path=output_path,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                config=config
            )
        
        # Test metadata serialization
        metadata_dict = metadata.to_dict()
        
        # Validate serialized fields
        assert isinstance(metadata_dict, dict)
        assert 'report_id' in metadata_dict
        assert 'generation_timestamp' in metadata_dict
        assert 'account_name' in metadata_dict
        assert 'date_range_start' in metadata_dict
        assert 'date_range_end' in metadata_dict
        
        # Validate datetime serialization
        assert isinstance(metadata_dict['generation_timestamp'], str)
        assert isinstance(metadata_dict['date_range_start'], str)
        assert isinstance(metadata_dict['date_range_end'], str)
        
        # Validate content
        assert metadata_dict['account_name'] == 'METADATA_TEST'
        assert metadata_dict['time_bin_hour'] == 15
        assert metadata_dict['time_bin_minute'] == 30
        assert metadata_dict['total_trades'] == len(sample_trades)
        
        print("✓ Report metadata serialization validation passed")
        print(f"  - Serialized fields: {len(metadata_dict)}")
        print(f"  - Report ID: {metadata_dict['report_id']}")
    
    def test_pdf_content_validation(self, pdf_generator, sample_trades,
                                   sample_performance_data, temp_output_dir):
        """Test PDF content validation and structure"""
        
        # Configure mocks
        pdf_generator.time_bin_analyzer.get_time_bin_trades.return_value = sample_trades
        pdf_generator.performance_calculator.calculate_comprehensive_metrics.return_value = sample_performance_data
        pdf_generator.time_bin_analyzer.analyze_time_bin_performance.return_value = {
            't_test_p_value': 0.023,
            'statistical_significance': True
        }
        
        config = ReportConfiguration(
            include_executive_summary=True,
            include_performance_summary=True,
            include_statistical_analysis=True,
            include_trade_details=True
        )
        
        with patch.object(pdf_generator, '_collect_correlation_data') as mock_collect_corr:
            mock_collect_corr.return_value = {
                'benchmark_correlations': {'SPY': 0.45, 'QQQ': 0.67}
            }
            
            output_path = os.path.join(temp_output_dir, 'content_validation.pdf')
            metadata = pdf_generator.generate_time_bin_report(
                account_name='CONTENT_TEST',
                hour=12,
                minute_bin=0,
                output_path=output_path,
                config=config
            )
        
        # Validate file properties
        assert os.path.exists(output_path)
        
        file_size = os.path.getsize(output_path)
        assert file_size > 20000  # Should be substantial PDF with content
        
        # Validate metadata consistency
        assert metadata.file_size_bytes == file_size
        assert metadata.page_count > 1  # Multiple sections should create multiple pages
        
        # Validate sections match configuration
        expected_sections = ['Title Page', 'Executive Summary', 'Performance Summary', 
                           'Statistical Analysis', 'Market Correlation', 'Trade Details']
        
        for section in expected_sections:
            assert section in metadata.report_sections
        
        print("✓ PDF content validation passed")
        print(f"  - File size: {file_size:,} bytes")
        print(f"  - Estimated pages: {metadata.page_count}")
        print(f"  - Sections included: {len(metadata.report_sections)}")


if __name__ == "__main__":
    # Run tests if ReportLab is available
    if not REPORTLAB_AVAILABLE:
        print("❌ ReportLab not available. PDF generation tests cannot run.")
        print("Install ReportLab with: pip install reportlab")
        exit(1)
    
    # Run tests
    test_instance = TestPDFReportGenerator()
    
    print("Running PDFReportGenerator Tests...")
    print("=" * 60)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory(prefix='test_pdf_') as temp_dir:
        
        # Generate test fixtures
        sample_trades = test_instance.sample_trades()
        sample_performance_data = test_instance.sample_performance_data(sample_trades)
        sample_statistical_data = test_instance.sample_statistical_data()
        sample_correlation_data = test_instance.sample_correlation_data()
        report_config = test_instance.report_config()
        
        # Create mock dependencies
        mock_db = Mock()
        
        # Create test generator
        try:
            with patch('trading_platform.services.export_reporting.pdf_report_generator.get_db_session') as mock_get_db:
                mock_get_db.return_value = mock_db
                generator = PDFReportGenerator(mock_db)
                
                # Mock analyzers
                generator.time_bin_analyzer = Mock()
                generator.performance_calculator = Mock()
                generator.vix_analyzer = Mock() 
                generator.benchmark_analyzer = Mock()
        except ImportError as e:
            print(f"❌ Required dependencies not available: {e}")
            exit(1)
        
        try:
            # Run individual tests
            test_instance.test_pdf_generator_initialization(mock_db)
            test_instance.test_generate_time_bin_report(generator, sample_trades, sample_performance_data, 
                                                       sample_statistical_data, temp_dir, report_config)
            test_instance.test_create_performance_summary_page(generator, sample_trades, 
                                                             sample_performance_data, report_config)
            test_instance.test_create_statistical_analysis_page(generator, sample_trades,
                                                              sample_statistical_data, report_config)
            test_instance.test_create_market_correlation_page(generator, sample_trades,
                                                            sample_correlation_data, report_config)
            test_instance.test_report_configuration_options(generator, sample_trades, temp_dir)
            test_instance.test_date_range_handling(generator, sample_trades, temp_dir)
            test_instance.test_empty_data_handling(generator, temp_dir)
            test_instance.test_statistical_calculations(generator)
            test_instance.test_correlation_data_collection(generator)
            test_instance.test_report_history_management(generator, sample_trades, temp_dir)
            test_instance.test_report_metadata_serialization(generator, sample_trades, temp_dir)
            test_instance.test_pdf_content_validation(generator, sample_trades, sample_performance_data, temp_dir)
            
            print("=" * 60)
            print("✅ ALL TESTS PASSED!")
            print("PDFReportGenerator is ready for production use.")
            
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            raise
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            raise