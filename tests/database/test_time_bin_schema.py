"""
Test suite for enhanced time-bin analytics database schema.

This module tests table creation, constraints, relationships, and index performance
with sample data for the enhanced time-bin analytics functionality.

Requirements: 1.1, 4.1, 10.2
"""

import pytest
import sqlite3
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import tempfile
import os
import time

from trading_platform.database.base import Base
from trading_platform.models.time_bin_analytics import (
    MarketData, VolatilityRegime, TimeBinAnalysis, RegimePerformance,
    WalkForwardResult, MonteCarloResult, ExportHistory, PDFReport
)
from trading_platform.models.database import Account


class TestTimeBinSchema:
    """Test suite for time-bin analytics database schema."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        engine = create_engine(f'sqlite:///{temp_file.name}')
        Base.metadata.create_all(engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        yield session, engine
        
        session.close()
        engine.dispose()
        os.unlink(temp_file.name)
    
    @pytest.fixture
    def sample_account(self, temp_db):
        """Create a sample account for testing."""
        session, _ = temp_db
        
        account = Account(
            name='IPS_TM_10',
            symbol='NQ',
            total_trades=100,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 12, 31),
            is_active=True
        )
        session.add(account)
        session.commit()
        
        return account
    
    def test_market_data_table_creation(self, temp_db):
        """Test market data table creation and constraints."""
        session, engine = temp_db
        
        # Test table exists
        result = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='market_data'"
        ))
        assert result.fetchone() is not None
        
        # Test unique constraint on symbol and date
        market_data1 = MarketData(
            symbol='SPY',
            date=date(2024, 1, 1),
            open_price=450.0,
            high_price=455.0,
            low_price=448.0,
            close_price=452.0,
            volume=1000000,
            adjusted_close=452.0
        )
        session.add(market_data1)
        session.commit()
        
        # Try to add duplicate - should fail
        market_data2 = MarketData(
            symbol='SPY',
            date=date(2024, 1, 1),
            close_price=453.0
        )
        session.add(market_data2)
        
        with pytest.raises(IntegrityError):
            session.commit()
        
        session.rollback()
    
    def test_market_data_index_performance(self, temp_db):
        """Test market data index performance with sample data."""
        session, engine = temp_db
        
        # Insert sample market data
        symbols = ['SPY', 'QQQ', 'VIX']
        start_date = date(2024, 1, 1)
        
        for i in range(100):  # 100 days of data
            current_date = start_date + timedelta(days=i)
            for symbol in symbols:
                market_data = MarketData(
                    symbol=symbol,
                    date=current_date,
                    open_price=100.0 + i,
                    high_price=105.0 + i,
                    low_price=95.0 + i,
                    close_price=102.0 + i,
                    volume=1000000 + i * 1000,
                    adjusted_close=102.0 + i
                )
                session.add(market_data)
        
        session.commit()
        
        # Test index performance - query should be fast
        start_time = time.time()
        result = session.query(MarketData).filter(
            MarketData.symbol == 'SPY',
            MarketData.date >= date(2024, 2, 19),  # 50th day from Jan 1
            MarketData.date <= date(2024, 3, 1)    # 60th day from Jan 1
        ).all()
        query_time = time.time() - start_time
        
        assert len(result) == 12  # 12 days of SPY data (inclusive range)
        assert query_time < 0.1  # Should be very fast with index
    
    def test_volatility_regimes_table(self, temp_db):
        """Test volatility regimes table creation and functionality."""
        session, _ = temp_db
        
        # Test table creation
        result = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='volatility_regimes'"
        ))
        assert result.fetchone() is not None
        
        # Test data insertion
        regime = VolatilityRegime(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            regime_name='Low',
            avg_vix=12.5,
            min_vix=10.0,
            max_vix=15.0
        )
        session.add(regime)
        session.commit()
        
        # Verify data
        retrieved = session.query(VolatilityRegime).first()
        assert retrieved.regime_name == 'Low'
        assert retrieved.avg_vix == 12.5
    
    def test_time_bin_analysis_table(self, temp_db, sample_account):
        """Test time-bin analysis table creation and constraints."""
        session, _ = temp_db
        
        # Test table creation
        result = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='time_bin_analysis'"
        ))
        assert result.fetchone() is not None
        
        # Test data insertion
        analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=9,
            minute_bin=30,
            day_of_week=1,  # Tuesday
            analysis_date=date(2024, 1, 15),
            total_trades=25,
            win_rate=0.68,
            average_pnl=125.50,
            sharpe_ratio=1.85,
            max_drawdown=-250.0,
            profit_factor=1.75,
            confidence_interval_lower=0.55,
            confidence_interval_upper=0.81,
            p_value_vs_random=0.02,
            statistical_significance=True,
            sample_size_adequate=True,
            spy_correlation=0.15,
            qqq_correlation=0.22,
            beta_spy=0.18,
            alpha_vs_spy=0.08,
            market_neutrality_p_value=0.45
        )
        session.add(analysis)
        session.commit()
        
        # Verify foreign key relationship
        retrieved = session.query(TimeBinAnalysis).first()
        assert retrieved.account_name == 'IPS_TM_10'
        assert retrieved.account.symbol == 'NQ'
    
    def test_time_bin_analysis_indexes(self, temp_db, sample_account):
        """Test time-bin analysis index performance."""
        session, _ = temp_db
        
        # Insert sample time-bin analyses
        for hour in range(9, 16):  # Trading hours
            for minute_bin in [0, 30]:  # 30-minute bins
                for day in range(5):  # Weekdays
                    analysis = TimeBinAnalysis(
                        account_name='IPS_TM_10',
                        hour=hour,
                        minute_bin=minute_bin,
                        day_of_week=day,
                        analysis_date=date(2024, 1, 15),
                        total_trades=10 + hour,
                        win_rate=0.5 + (hour * 0.02),
                        average_pnl=100.0 + hour * 10,
                        max_drawdown=-50.0 - hour * 5,
                        profit_factor=1.0 + hour * 0.1
                    )
                    session.add(analysis)
        
        session.commit()
        
        # Test lookup index performance
        start_time = time.time()
        result = session.query(TimeBinAnalysis).filter(
            TimeBinAnalysis.account_name == 'IPS_TM_10',
            TimeBinAnalysis.hour == 10,
            TimeBinAnalysis.minute_bin == 30,
            TimeBinAnalysis.day_of_week == 2
        ).first()
        query_time = time.time() - start_time
        
        assert result is not None
        assert result.hour == 10
        assert result.minute_bin == 30
        assert query_time < 0.05  # Should be fast with composite index
    
    def test_regime_performance_relationships(self, temp_db, sample_account):
        """Test regime performance table and relationships."""
        session, _ = temp_db
        
        # Create time-bin analysis
        analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=10,
            minute_bin=0,
            analysis_date=date(2024, 1, 15),
            total_trades=30,
            win_rate=0.70,
            average_pnl=150.0,
            max_drawdown=-200.0,
            profit_factor=2.0
        )
        session.add(analysis)
        session.flush()  # Get the ID
        
        # Create regime performance
        regime_perf = RegimePerformance(
            time_bin_analysis_id=analysis.id,
            regime_name='High',
            trades_in_regime=10,
            win_rate_in_regime=0.80,
            avg_pnl_in_regime=200.0,
            sharpe_ratio_in_regime=2.5
        )
        session.add(regime_perf)
        session.commit()
        
        # Test relationship
        retrieved_analysis = session.query(TimeBinAnalysis).first()
        assert len(retrieved_analysis.regime_performances) == 1
        assert retrieved_analysis.regime_performances[0].regime_name == 'High'
    
    def test_walk_forward_results_table(self, temp_db, sample_account):
        """Test walk-forward results table and constraints."""
        session, _ = temp_db
        
        # Create time-bin analysis
        analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=11,
            minute_bin=30,
            analysis_date=date(2024, 1, 15),
            total_trades=20,
            win_rate=0.65,
            average_pnl=120.0,
            max_drawdown=-150.0,
            profit_factor=1.8
        )
        session.add(analysis)
        session.flush()
        
        # Create walk-forward result
        wf_result = WalkForwardResult(
            time_bin_analysis_id=analysis.id,
            validation_scheme='anchored',
            in_sample_start=date(2024, 1, 1),
            in_sample_end=date(2024, 6, 30),
            out_sample_start=date(2024, 7, 1),
            out_sample_end=date(2024, 7, 31),
            predicted_performance=0.65,
            actual_performance=0.58,
            prediction_error=-0.07,
            trades_in_out_sample=8
        )
        session.add(wf_result)
        session.commit()
        
        # Verify data and relationship
        retrieved = session.query(WalkForwardResult).first()
        assert retrieved.validation_scheme == 'anchored'
        assert retrieved.prediction_error == -0.07
        assert retrieved.time_bin_analysis.hour == 11
    
    def test_monte_carlo_results_table(self, temp_db, sample_account):
        """Test Monte Carlo results table."""
        session, _ = temp_db
        
        # Create time-bin analysis
        analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=14,
            minute_bin=0,
            analysis_date=date(2024, 1, 15),
            total_trades=40,
            win_rate=0.72,
            average_pnl=180.0,
            max_drawdown=-300.0,
            profit_factor=2.2
        )
        session.add(analysis)
        session.flush()
        
        # Create Monte Carlo result
        mc_result = MonteCarloResult(
            time_bin_analysis_id=analysis.id,
            simulation_date=date(2024, 1, 15),
            n_scenarios=10000,
            var_95=-150.0,
            var_99=-250.0,
            var_99_9=-400.0,
            expected_shortfall_95=-200.0,
            expected_return=180.0,
            probability_of_profit=0.72
        )
        session.add(mc_result)
        session.commit()
        
        # Verify data
        retrieved = session.query(MonteCarloResult).first()
        assert retrieved.n_scenarios == 10000
        assert retrieved.var_95 == -150.0
        assert retrieved.probability_of_profit == 0.72
    
    def test_export_history_and_pdf_reports(self, temp_db, sample_account):
        """Test export history and PDF reports tables."""
        session, _ = temp_db
        
        # Create time-bin analysis
        analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=13,
            minute_bin=30,
            analysis_date=date(2024, 1, 15),
            total_trades=35,
            win_rate=0.74,
            average_pnl=160.0,
            max_drawdown=-220.0,
            profit_factor=2.1
        )
        session.add(analysis)
        session.flush()
        
        # Create export history
        export_hist = ExportHistory(
            time_bin_analysis_id=analysis.id,
            export_directory='/exports/test',
            export_config_json='{"format": "csv", "include_charts": true}',
            exported_files_json='["trades.csv", "metrics.xlsx"]',
            pdf_report_path='/exports/test/report.pdf',
            total_trades_exported=35,
            user_id='test_user'
        )
        session.add(export_hist)
        session.flush()
        
        # Create PDF report
        pdf_report = PDFReport(
            export_history_id=export_hist.id,
            report_title='Time-Bin Analysis Report',
            file_path='/exports/test/report.pdf',
            file_size_mb=2.5,
            page_count=12,
            sections_included_json='["summary", "performance", "risk"]'
        )
        session.add(pdf_report)
        session.commit()
        
        # Test relationships
        retrieved_export = session.query(ExportHistory).first()
        assert len(retrieved_export.pdf_reports) == 1
        assert retrieved_export.pdf_reports[0].report_title == 'Time-Bin Analysis Report'
        assert retrieved_export.time_bin_analysis.hour == 13
    
    def test_database_constraints_and_integrity(self, temp_db, sample_account):
        """Test database constraints and referential integrity."""
        session, engine = temp_db
        
        # Enable foreign key constraints for SQLite
        session.execute(text("PRAGMA foreign_keys=ON"))
        session.commit()
        
        # Test foreign key constraint - should fail with invalid account
        with pytest.raises(IntegrityError):
            invalid_analysis = TimeBinAnalysis(
                account_name='INVALID_ACCOUNT',
                hour=10,
                minute_bin=0,
                analysis_date=date(2024, 1, 15),
                total_trades=10,
                win_rate=0.5,
                average_pnl=100.0,
                max_drawdown=-50.0,
                profit_factor=1.0
            )
            session.add(invalid_analysis)
            session.commit()
        
        session.rollback()
        
        # Test valid foreign key relationship
        valid_analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=10,
            minute_bin=0,
            analysis_date=date(2024, 1, 15),
            total_trades=10,
            win_rate=0.5,
            average_pnl=100.0,
            max_drawdown=-50.0,
            profit_factor=1.0
        )
        session.add(valid_analysis)
        session.commit()
        
        assert valid_analysis.id is not None
    
    def test_index_existence_and_performance(self, temp_db):
        """Test that all required indexes exist and perform well."""
        session, engine = temp_db
        
        # Check that indexes exist
        indexes_to_check = [
            'idx_market_data_symbol_date',
            'idx_volatility_regimes_date',
            'idx_time_bin_analysis_lookup',
            'idx_time_bin_analysis_date',
            'idx_time_bin_analysis_performance',
            'idx_regime_performance_lookup',
            'idx_walk_forward_timebin',
            'idx_walk_forward_scheme',
            'idx_monte_carlo_timebin',
            'idx_monte_carlo_date',
            'idx_export_history_timebin',
            'idx_export_history_user',
            'idx_pdf_reports_export'
        ]
        
        for index_name in indexes_to_check:
            result = session.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
            ))
            assert result.fetchone() is not None, f"Index {index_name} does not exist"
    
    def test_comprehensive_data_workflow(self, temp_db, sample_account):
        """Test a complete workflow with all tables."""
        session, _ = temp_db
        
        # 1. Create market data
        market_data = MarketData(
            symbol='SPY',
            date=date(2024, 1, 15),
            close_price=450.0,
            volume=1000000
        )
        session.add(market_data)
        
        # 2. Create volatility regime
        regime = VolatilityRegime(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            regime_name='Medium',
            avg_vix=18.5,
            min_vix=15.0,
            max_vix=22.0
        )
        session.add(regime)
        
        # 3. Create time-bin analysis
        analysis = TimeBinAnalysis(
            account_name='IPS_TM_10',
            hour=10,
            minute_bin=30,
            analysis_date=date(2024, 1, 15),
            total_trades=50,
            win_rate=0.68,
            average_pnl=145.0,
            sharpe_ratio=1.95,
            max_drawdown=-280.0,
            profit_factor=1.85
        )
        session.add(analysis)
        session.flush()
        
        # 4. Create regime performance
        regime_perf = RegimePerformance(
            time_bin_analysis_id=analysis.id,
            regime_name='Medium',
            trades_in_regime=50,
            win_rate_in_regime=0.68,
            avg_pnl_in_regime=145.0
        )
        session.add(regime_perf)
        
        # 5. Create walk-forward result
        wf_result = WalkForwardResult(
            time_bin_analysis_id=analysis.id,
            validation_scheme='rolling',
            in_sample_start=date(2024, 1, 1),
            in_sample_end=date(2024, 3, 31),
            out_sample_start=date(2024, 4, 1),
            out_sample_end=date(2024, 4, 30),
            predicted_performance=0.68,
            actual_performance=0.64,
            prediction_error=-0.04,
            trades_in_out_sample=12
        )
        session.add(wf_result)
        
        # 6. Create Monte Carlo result
        mc_result = MonteCarloResult(
            time_bin_analysis_id=analysis.id,
            simulation_date=date(2024, 1, 15),
            n_scenarios=5000,
            var_95=-120.0,
            var_99=-200.0,
            var_99_9=-350.0,
            expected_shortfall_95=-160.0,
            expected_return=145.0,
            probability_of_profit=0.68
        )
        session.add(mc_result)
        
        # 7. Create export history
        export_hist = ExportHistory(
            time_bin_analysis_id=analysis.id,
            export_directory='/test/exports',
            export_config_json='{"complete": true}',
            exported_files_json='["all_data.csv"]',
            total_trades_exported=50
        )
        session.add(export_hist)
        session.flush()
        
        # 8. Create PDF report
        pdf_report = PDFReport(
            export_history_id=export_hist.id,
            report_title='Complete Analysis Report',
            file_path='/test/exports/complete_report.pdf',
            file_size_mb=5.2,
            page_count=25,
            sections_included_json='["all"]'
        )
        session.add(pdf_report)
        
        session.commit()
        
        # Verify all relationships work
        retrieved_analysis = session.query(TimeBinAnalysis).first()
        assert len(retrieved_analysis.regime_performances) == 1
        assert len(retrieved_analysis.walk_forward_results) == 1
        assert len(retrieved_analysis.monte_carlo_results) == 1
        assert len(retrieved_analysis.export_history) == 1
        assert len(retrieved_analysis.export_history[0].pdf_reports) == 1
        
        # Verify data integrity
        assert retrieved_analysis.total_trades == 50
        assert retrieved_analysis.regime_performances[0].trades_in_regime == 50
        assert retrieved_analysis.walk_forward_results[0].prediction_error == -0.04
        assert retrieved_analysis.monte_carlo_results[0].n_scenarios == 5000
        assert retrieved_analysis.export_history[0].total_trades_exported == 50


if __name__ == '__main__':
    pytest.main([__file__, '-v'])