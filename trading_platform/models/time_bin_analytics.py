"""
SQLAlchemy ORM models for enhanced time-bin analytics.

This module contains the database models for advanced trading analytics
focused on account/30-minute time bin combinations.

Requirements: 1.1, 4.1, 10.2
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, Date,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

from ..database.base import Base


class MarketData(Base):
    """Market data table for SPY/QQQ/VIX data storage."""
    
    __tablename__ = "market_data"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Market data fields
    symbol = Column(String(10), nullable=False)  # 'SPY', 'QQQ', 'VIX'
    date = Column(Date, nullable=False)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    adjusted_close = Column(Float, nullable=True)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uq_market_data_symbol_date'),
        Index('idx_market_data_symbol_date', 'symbol', 'date'),
    )
    
    def __repr__(self):
        return f"<MarketData(id={self.id}, symbol={self.symbol}, date={self.date}, close={self.close_price})>"


class VolatilityRegime(Base):
    """VIX volatility regimes table for regime classification."""
    
    __tablename__ = "volatility_regimes"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Regime details
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    regime_name = Column(String(20), nullable=False)  # 'Low', 'Medium', 'High'
    avg_vix = Column(Float, nullable=False)
    min_vix = Column(Float, nullable=False)
    max_vix = Column(Float, nullable=False)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_volatility_regimes_date', 'start_date', 'end_date'),
    )
    
    def __repr__(self):
        return f"<VolatilityRegime(id={self.id}, regime={self.regime_name}, avg_vix={self.avg_vix})>"


class TimeBinAnalysis(Base):
    """Time-bin analysis table for performance metrics."""
    
    __tablename__ = "time_bin_analysis"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Time-bin identification
    account_name = Column(String(50), ForeignKey('accounts.name'), nullable=False)
    hour = Column(Integer, nullable=False)  # 0-23
    minute_bin = Column(Integer, nullable=False)  # 0 or 30
    day_of_week = Column(Integer, nullable=True)  # NULL for all days, 0-6 for specific days
    analysis_date = Column(Date, nullable=False)
    
    # Performance metrics
    total_trades = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=False)
    average_pnl = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=False)
    profit_factor = Column(Float, nullable=False)
    
    # Statistical significance
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    p_value_vs_random = Column(Float, nullable=True)
    statistical_significance = Column(Boolean, nullable=True)
    sample_size_adequate = Column(Boolean, nullable=True)
    
    # Market correlation
    spy_correlation = Column(Float, nullable=True)
    qqq_correlation = Column(Float, nullable=True)
    beta_spy = Column(Float, nullable=True)
    alpha_vs_spy = Column(Float, nullable=True)
    market_neutrality_p_value = Column(Float, nullable=True)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    account = relationship("Account")
    regime_performances = relationship("RegimePerformance", back_populates="time_bin_analysis")
    walk_forward_results = relationship("WalkForwardResult", back_populates="time_bin_analysis")
    monte_carlo_results = relationship("MonteCarloResult", back_populates="time_bin_analysis")
    export_history = relationship("ExportHistory", back_populates="time_bin_analysis")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_time_bin_analysis_lookup', 'account_name', 'hour', 'minute_bin', 'day_of_week'),
        Index('idx_time_bin_analysis_date', 'analysis_date'),
        Index('idx_time_bin_analysis_performance', 'win_rate', 'sharpe_ratio', 'profit_factor'),
    )
    
    def __repr__(self):
        return f"<TimeBinAnalysis(id={self.id}, account={self.account_name}, time={self.hour}:{self.minute_bin:02d}, trades={self.total_trades})>"


class RegimePerformance(Base):
    """Regime-specific performance table."""
    
    __tablename__ = "regime_performance"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # References
    time_bin_analysis_id = Column(Integer, ForeignKey('time_bin_analysis.id'), nullable=False)
    regime_name = Column(String(20), nullable=False)
    
    # Performance in regime
    trades_in_regime = Column(Integer, nullable=False)
    win_rate_in_regime = Column(Float, nullable=False)
    avg_pnl_in_regime = Column(Float, nullable=False)
    sharpe_ratio_in_regime = Column(Float, nullable=True)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    time_bin_analysis = relationship("TimeBinAnalysis", back_populates="regime_performances")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_regime_performance_lookup', 'time_bin_analysis_id', 'regime_name'),
    )
    
    def __repr__(self):
        return f"<RegimePerformance(id={self.id}, regime={self.regime_name}, trades={self.trades_in_regime})>"


class WalkForwardResult(Base):
    """Walk-forward analysis results table."""
    
    __tablename__ = "walk_forward_results"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # References
    time_bin_analysis_id = Column(Integer, ForeignKey('time_bin_analysis.id'), nullable=False)
    
    # Validation details
    validation_scheme = Column(String(20), nullable=False)  # 'anchored', 'rolling', 'expanding'
    in_sample_start = Column(Date, nullable=False)
    in_sample_end = Column(Date, nullable=False)
    out_sample_start = Column(Date, nullable=False)
    out_sample_end = Column(Date, nullable=False)
    
    # Results
    predicted_performance = Column(Float, nullable=False)
    actual_performance = Column(Float, nullable=False)
    prediction_error = Column(Float, nullable=False)
    trades_in_out_sample = Column(Integer, nullable=False)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    time_bin_analysis = relationship("TimeBinAnalysis", back_populates="walk_forward_results")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_walk_forward_timebin', 'time_bin_analysis_id'),
        Index('idx_walk_forward_scheme', 'validation_scheme'),
    )
    
    def __repr__(self):
        return f"<WalkForwardResult(id={self.id}, scheme={self.validation_scheme}, error={self.prediction_error})>"


class MonteCarloResult(Base):
    """Monte Carlo simulation results table."""
    
    __tablename__ = "monte_carlo_results"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # References
    time_bin_analysis_id = Column(Integer, ForeignKey('time_bin_analysis.id'), nullable=False)
    
    # Simulation details
    simulation_date = Column(Date, nullable=False)
    n_scenarios = Column(Integer, nullable=False)
    
    # Risk metrics
    var_95 = Column(Float, nullable=False)
    var_99 = Column(Float, nullable=False)
    var_99_9 = Column(Float, nullable=False)
    expected_shortfall_95 = Column(Float, nullable=False)
    expected_return = Column(Float, nullable=False)
    probability_of_profit = Column(Float, nullable=False)
    
    # Metadata
    created_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    time_bin_analysis = relationship("TimeBinAnalysis", back_populates="monte_carlo_results")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_monte_carlo_timebin', 'time_bin_analysis_id'),
        Index('idx_monte_carlo_date', 'simulation_date'),
    )
    
    def __repr__(self):
        return f"<MonteCarloResult(id={self.id}, scenarios={self.n_scenarios}, var_95={self.var_95})>"


class ExportHistory(Base):
    """Export and report tracking table."""
    
    __tablename__ = "export_history"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # References
    time_bin_analysis_id = Column(Integer, ForeignKey('time_bin_analysis.id'), nullable=False)
    
    # Export details
    export_directory = Column(String(500), nullable=False)
    export_config_json = Column(Text, nullable=False)  # JSON of ExportConfig
    exported_files_json = Column(Text, nullable=False)  # JSON list of exported files
    pdf_report_path = Column(String(500), nullable=True)
    total_trades_exported = Column(Integer, nullable=False)
    user_id = Column(String(100), nullable=True)  # Optional user tracking
    
    # Metadata
    export_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    time_bin_analysis = relationship("TimeBinAnalysis", back_populates="export_history")
    pdf_reports = relationship("PDFReport", back_populates="export_history")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_export_history_timebin', 'time_bin_analysis_id', 'export_timestamp'),
        Index('idx_export_history_user', 'user_id'),
    )
    
    def __repr__(self):
        return f"<ExportHistory(id={self.id}, directory={self.export_directory}, trades={self.total_trades_exported})>"


class PDFReport(Base):
    """PDF reports table."""
    
    __tablename__ = "pdf_reports"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # References
    export_history_id = Column(Integer, ForeignKey('export_history.id'), nullable=False)
    
    # Report details
    report_title = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_mb = Column(Float, nullable=False)
    page_count = Column(Integer, nullable=False)
    sections_included_json = Column(Text, nullable=False)  # JSON list of sections
    
    # Metadata
    generation_timestamp = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    export_history = relationship("ExportHistory", back_populates="pdf_reports")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_pdf_reports_export', 'export_history_id'),
    )
    
    def __repr__(self):
        return f"<PDFReport(id={self.id}, title={self.report_title}, pages={self.page_count})>"