"""
Tests for database models and connection management.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trading_platform.database.connection import DatabaseManager
from trading_platform.database.base import Base
from trading_platform.models.database import (
    SierraChartFill, ProcessedTrade, Account, PerformanceMetric,
    TemporalPerformance, Recommendation, DataImportLog, SystemHealth
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create temporary database file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    db_url = f"sqlite:///{temp_file.name}"
    db_manager = DatabaseManager(db_url)
    db_manager.initialize()
    db_manager.create_tables()
    
    yield db_manager
    
    # Cleanup
    db_manager.close()
    os.unlink(temp_file.name)


def test_database_initialization(temp_db):
    """Test database initialization and table creation."""
    assert temp_db._initialized
    assert temp_db.engine is not None
    assert temp_db.SessionLocal is not None
    
    # Test health check
    assert temp_db.health_check()


def test_account_model(temp_db):
    """Test Account model creation and validation."""
    with temp_db.session_scope() as session:
        # Create test account
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=100,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 12, 31),
            is_active=True
        )
        
        session.add(account)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(Account).filter_by(name="IPS_TM_10").first()
        assert retrieved is not None
        assert retrieved.symbol == "NQ"
        assert retrieved.total_trades == 100
        assert retrieved.is_active is True


def test_sierra_chart_fill_model(temp_db):
    """Test SierraChartFill model creation."""
    with temp_db.session_scope() as session:
        # Create test fill record
        fill = SierraChartFill(
            activity_type="Fills",
            date_time=datetime.now(),
            trans_date_time=datetime.now(),
            service_order_id="TEST123",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            fill_price=4500.0,
            filled_quantity=1,
            note="Test fill",
            internal_order_id="INT123",
            symbol="NQH24",
            open_close="Open",
            position_quantity=1,
            account_balance=100000.0,
            file_source="test_file.txt"
        )
        
        session.add(fill)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(SierraChartFill).filter_by(service_order_id="TEST123").first()
        assert retrieved is not None
        assert retrieved.trade_account == "IPS_TM_10"
        assert retrieved.fill_price == 4500.0


def test_processed_trade_model(temp_db):
    """Test ProcessedTrade model creation."""
    with temp_db.session_scope() as session:
        # First create an account
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=1,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 1, 1),
            is_active=True
        )
        session.add(account)
        session.commit()
        
        # Create test processed trade
        entry_time = datetime(2024, 1, 1, 9, 30)
        exit_time = datetime(2024, 1, 1, 10, 30)
        
        trade = ProcessedTrade(
            trade_id="TEST_TRADE_001",
            account_name="IPS_TM_10",
            symbol="NQ",
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=4500.0,
            exit_price=4510.0,
            quantity=1,
            side="LONG",
            profit_loss=10.0,
            commission=2.0,
            duration_minutes=60,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY123",
            exit_order_id="EXIT123"
        )
        
        session.add(trade)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(ProcessedTrade).filter_by(trade_id="TEST_TRADE_001").first()
        assert retrieved is not None
        assert retrieved.profit_loss == 10.0
        assert retrieved.side == "LONG"


def test_performance_metrics_model(temp_db):
    """Test PerformanceMetric model creation."""
    with temp_db.session_scope() as session:
        # First create an account
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=10,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 1, 31),
            is_active=True
        )
        session.add(account)
        session.commit()
        
        # Create performance metrics
        metrics = PerformanceMetric(
            account_name="IPS_TM_10",
            symbol="NQ",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
            total_return=500.0,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            average_win=100.0,
            average_loss=-50.0,
            profit_factor=1.2,
            max_drawdown=-200.0,
            sharpe_ratio=1.5,
            volatility=0.15,
            largest_win=200.0,
            largest_loss=-100.0
        )
        
        session.add(metrics)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(PerformanceMetric).filter_by(account_name="IPS_TM_10").first()
        assert retrieved is not None
        assert retrieved.total_return == 500.0
        assert retrieved.win_rate == 0.6


def test_recommendation_model(temp_db):
    """Test Recommendation model creation."""
    with temp_db.session_scope() as session:
        # First create an account
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=1,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 1, 1),
            is_active=True
        )
        session.add(account)
        session.commit()
        
        # Create recommendation
        recommendation = Recommendation(
            timestamp=datetime.now(),
            account_name="IPS_TM_10",
            symbol="NQ",
            recommended_action="TRADE",
            confidence_score=0.85,
            expected_return=50.0,
            expected_risk=25.0,
            reasoning="Strong historical performance at this time",
            hour_of_day=9,
            day_of_week=1,
            historical_win_rate=0.7,
            avg_profit_this_time=45.0
        )
        
        session.add(recommendation)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(Recommendation).filter_by(account_name="IPS_TM_10").first()
        assert retrieved is not None
        assert retrieved.recommended_action == "TRADE"
        assert retrieved.confidence_score == 0.85


def test_data_import_log_model(temp_db):
    """Test DataImportLog model creation."""
    with temp_db.session_scope() as session:
        # Create import log entry
        log_entry = DataImportLog(
            file_path="/path/to/test/file.txt",
            file_size_bytes=1024,
            records_processed=100,
            records_imported=95,
            records_rejected=5,
            import_status="SUCCESS",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(seconds=30),
            duration_seconds=30.0,
            warnings="5 records had validation warnings"
        )
        
        session.add(log_entry)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(DataImportLog).filter_by(file_path="/path/to/test/file.txt").first()
        assert retrieved is not None
        assert retrieved.import_status == "SUCCESS"
        assert retrieved.records_imported == 95


def test_system_health_model(temp_db):
    """Test SystemHealth model creation."""
    with temp_db.session_scope() as session:
        # Create health check entry
        health_check = SystemHealth(
            component="database",
            status="HEALTHY",
            response_time_ms=15.5,
            cpu_usage_percent=25.0,
            memory_usage_mb=512.0,
            disk_usage_percent=45.0,
            message="All systems operational"
        )
        
        session.add(health_check)
        session.commit()
        
        # Retrieve and verify
        retrieved = session.query(SystemHealth).filter_by(component="database").first()
        assert retrieved is not None
        assert retrieved.status == "HEALTHY"
        assert retrieved.response_time_ms == 15.5


def test_relationships(temp_db):
    """Test model relationships."""
    with temp_db.session_scope() as session:
        # Create account
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=1,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 1, 1),
            is_active=True
        )
        session.add(account)
        session.commit()
        
        # Create related records
        trade = ProcessedTrade(
            trade_id="TEST_001",
            account_name="IPS_TM_10",
            symbol="NQ",
            entry_time=datetime(2024, 1, 1, 9, 30),
            exit_time=datetime(2024, 1, 1, 10, 30),
            entry_price=4500.0,
            exit_price=4510.0,
            quantity=1,
            side="LONG",
            profit_loss=10.0,
            commission=2.0,
            duration_minutes=60,
            hour_of_day=9,
            day_of_week=0,
            entry_order_id="ENTRY123",
            exit_order_id="EXIT123"
        )
        
        recommendation = Recommendation(
            timestamp=datetime.now(),
            account_name="IPS_TM_10",
            symbol="NQ",
            recommended_action="TRADE",
            confidence_score=0.85,
            expected_return=50.0,
            expected_risk=25.0,
            reasoning="Test recommendation",
            hour_of_day=9,
            day_of_week=1,
            historical_win_rate=0.7,
            avg_profit_this_time=45.0
        )
        
        session.add_all([trade, recommendation])
        session.commit()
        
        # Test relationships
        retrieved_account = session.query(Account).filter_by(name="IPS_TM_10").first()
        assert len(retrieved_account.trades) == 1
        assert len(retrieved_account.recommendations) == 1
        assert retrieved_account.trades[0].trade_id == "TEST_001"
        assert retrieved_account.recommendations[0].recommended_action == "TRADE"


if __name__ == "__main__":
    pytest.main([__file__])