"""
SQLAlchemy ORM models for the Trading Optimization Platform database.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, 
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

from ..database.base import Base


class SierraChartFill(Base):
    """Raw SierraChart data table for all fill records."""
    
    __tablename__ = "sierra_chart_fills"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core SierraChart fields
    activity_type = Column(String(50), nullable=False)
    date_time = Column(DateTime, nullable=False)
    trans_date_time = Column(DateTime, nullable=False)
    service_order_id = Column(String(100), nullable=False)
    order_type = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    order_status = Column(String(50), nullable=False)
    trade_account = Column(String(50), nullable=False)
    buy_sell = Column(String(10), nullable=False)
    price = Column(Float, nullable=True)
    price2 = Column(Float, nullable=True)
    fill_price = Column(Float, nullable=False)
    filled_quantity = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    order_action_source = Column(String(100), nullable=True)
    internal_order_id = Column(String(100), nullable=False)
    symbol = Column(String(50), nullable=False)
    open_close = Column(String(10), nullable=False)
    parent_internal_order_id = Column(String(100), nullable=True)
    position_quantity = Column(Integer, nullable=False)
    fill_execution_service_id = Column(String(100), nullable=True)
    high_during_position = Column(Float, nullable=True)
    low_during_position = Column(Float, nullable=True)
    account_balance = Column(Float, nullable=False)
    exchange_order_id = Column(String(100), nullable=True)
    client_order_id = Column(String(100), nullable=True)
    time_in_force = Column(String(50), nullable=True)
    username = Column(String(100), nullable=True)
    is_automated = Column(String(1), nullable=True)
    
    # Metadata fields
    file_source = Column(String(500), nullable=False)
    import_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('service_order_id', 'internal_order_id', name='uq_sierra_fills_order_ids'),
        Index('idx_sierra_fills_account_symbol', 'trade_account', 'symbol'),
        Index('idx_sierra_fills_datetime', 'date_time'),
        Index('idx_sierra_fills_position_qty', 'position_quantity'),
    )
    
    def __repr__(self):
        return f"<SierraChartFill(id={self.id}, account={self.trade_account}, symbol={self.symbol}, datetime={self.date_time})>"


class ProcessedTrade(Base):
    """Processed trades table for complete round-trip trades."""
    
    __tablename__ = "processed_trades"
    
    # Trade identification
    trade_id = Column(String(200), primary_key=True, nullable=False)
    account_name = Column(String(50), ForeignKey('accounts.name'), nullable=False)
    symbol = Column(String(50), nullable=False)
    
    # Trade timing
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=False)
    
    # Trade details
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    side = Column(String(10), nullable=False)  # 'LONG' or 'SHORT'
    
    # Financial metrics
    profit_loss = Column(Float, nullable=False)
    commission = Column(Float, nullable=False, default=0.0)
    
    # Derived fields
    duration_minutes = Column(Integer, nullable=False)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    
    # Foreign key relationship
    account = relationship("Account", back_populates="trades")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_processed_trades_account_time', 'account_name', 'entry_time'),
        Index('idx_processed_trades_temporal', 'hour_of_day', 'day_of_week'),
        Index('idx_processed_trades_symbol', 'symbol'),
        Index('idx_processed_trades_pnl', 'profit_loss'),
    )
    
    def __repr__(self):
        return f"<ProcessedTrade(id={self.id}, trade_id={self.trade_id}, pnl={self.profit_loss})>"


class Account(Base):
    """Accounts table for trading account metadata."""
    
    __tablename__ = "accounts"
    
    # Primary key
    name = Column(String(50), primary_key=True)  # IPS_TM_10, IPS_TM_13, etc.
    
    # Account details
    symbol = Column(String(50), nullable=False)  # NQ, FDAX, etc.
    total_trades = Column(Integer, nullable=False, default=0)
    first_trade_date = Column(DateTime, nullable=True)
    last_trade_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    trades = relationship("ProcessedTrade", back_populates="account")
    performance_metrics = relationship("PerformanceMetric", back_populates="account")
    temporal_performance = relationship("TemporalPerformance", back_populates="account")
    recommendations = relationship("Recommendation", back_populates="account")
    
    def __repr__(self):
        return f"<Account(name={self.name}, symbol={self.symbol}, trades={self.total_trades})>"


class PerformanceMetric(Base):
    """Performance metrics table for calculated trading statistics."""
    
    __tablename__ = "performance_metrics"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Account reference
    account_name = Column(String(50), ForeignKey('accounts.name'), nullable=False)
    symbol = Column(String(50), nullable=False)
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Performance metrics
    total_return = Column(Float, nullable=False)
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    losing_trades = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=False)
    average_win = Column(Float, nullable=False)
    average_loss = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    volatility = Column(Float, nullable=False)
    largest_win = Column(Float, nullable=False)
    largest_loss = Column(Float, nullable=False)
    
    # Metadata
    calculation_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="performance_metrics")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_perf_metrics_account_period', 'account_name', 'period_start', 'period_end'),
        Index('idx_perf_metrics_symbol', 'symbol'),
    )
    
    def __repr__(self):
        return f"<PerformanceMetric(id={self.id}, account={self.account_name}, return={self.total_return})>"


class TemporalPerformance(Base):
    """Temporal analysis table for performance by hour/day patterns."""
    
    __tablename__ = "temporal_performance"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Account reference
    account_name = Column(String(50), ForeignKey('accounts.name'), nullable=False)
    symbol = Column(String(50), nullable=False)
    
    # Temporal dimensions (one will be NULL for each record)
    hour_of_day = Column(Integer, nullable=True)  # NULL for day-of-week analysis
    day_of_week = Column(Integer, nullable=True)  # NULL for hour-of-day analysis
    
    # Performance data
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    total_pnl = Column(Float, nullable=False)
    average_pnl = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    
    # Metadata
    calculation_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="temporal_performance")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_temporal_perf_lookup', 'account_name', 'symbol', 'hour_of_day', 'day_of_week'),
        Index('idx_temporal_perf_hour', 'hour_of_day'),
        Index('idx_temporal_perf_day', 'day_of_week'),
    )
    
    def __repr__(self):
        return f"<TemporalPerformance(id={self.id}, account={self.account_name}, hour={self.hour_of_day}, day={self.day_of_week})>"


class Recommendation(Base):
    """Recommendations table for trading suggestions."""
    
    __tablename__ = "recommendations"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Recommendation details
    timestamp = Column(DateTime, nullable=False)
    account_name = Column(String(50), ForeignKey('accounts.name'), nullable=False)
    symbol = Column(String(50), nullable=False)
    recommended_action = Column(String(10), nullable=False)  # 'TRADE', 'AVOID'
    confidence_score = Column(Float, nullable=False)
    expected_return = Column(Float, nullable=True)
    expected_risk = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    
    # Temporal context
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    
    # Supporting data
    historical_win_rate = Column(Float, nullable=True)
    avg_profit_this_time = Column(Float, nullable=True)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="recommendations")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_recommendations_timestamp', 'timestamp'),
        Index('idx_recommendations_account', 'account_name'),
        Index('idx_recommendations_action', 'recommended_action'),
        Index('idx_recommendations_confidence', 'confidence_score'),
    )
    
    def __repr__(self):
        return f"<Recommendation(id={self.id}, account={self.account_name}, action={self.recommended_action}, confidence={self.confidence_score})>"


# Additional utility tables for system management

class DataImportLog(Base):
    """Log table for tracking data import operations."""
    
    __tablename__ = "data_import_log"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Import details
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    records_processed = Column(Integer, nullable=False)
    records_imported = Column(Integer, nullable=False)
    records_rejected = Column(Integer, nullable=False)
    
    # Status and timing
    import_status = Column(String(20), nullable=False)  # 'SUCCESS', 'FAILED', 'PARTIAL'
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    warnings = Column(Text, nullable=True)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_import_log_status', 'import_status'),
        Index('idx_import_log_start_time', 'start_time'),
        Index('idx_import_log_file_path', 'file_path'),
    )
    
    def __repr__(self):
        return f"<DataImportLog(id={self.id}, file={self.file_path}, status={self.import_status})>"


class SystemHealth(Base):
    """System health monitoring table."""
    
    __tablename__ = "system_health"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Health check details
    component = Column(String(100), nullable=False)  # 'database', 'mcp', 'api', etc.
    status = Column(String(20), nullable=False)  # 'HEALTHY', 'WARNING', 'ERROR'
    response_time_ms = Column(Float, nullable=True)
    
    # Metrics
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    disk_usage_percent = Column(Float, nullable=True)
    
    # Status details
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    
    # Metadata
    check_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_health_component_time', 'component', 'check_timestamp'),
        Index('idx_health_status', 'status'),
    )
    
    def __repr__(self):
        return f"<SystemHealth(id={self.id}, component={self.component}, status={self.status})>"