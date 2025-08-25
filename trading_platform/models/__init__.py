"""Data models for the Trading Optimization Platform."""

# Import dataclass models
from .trading import ProcessedTrade, Account, PerformanceMetrics, TradingRecommendation
from .sierra_chart import SierraChartTradeRecord

# Import database ORM models
from .database import (
    SierraChartFill,
    ProcessedTrade as ProcessedTradeORM,
    Account as AccountORM,
    PerformanceMetric,
    TemporalPerformance,
    Recommendation,
    DataImportLog,
    SystemHealth
)

# Import enhanced time-bin analytics models
from .time_bin_analytics import (
    MarketData,
    VolatilityRegime,
    TimeBinAnalysis,
    RegimePerformance,
    WalkForwardResult,
    MonteCarloResult,
    ExportHistory,
    PDFReport
)

__all__ = [
    # Dataclass models
    'ProcessedTrade',
    'Account', 
    'PerformanceMetrics',
    'TradingRecommendation',
    'SierraChartTradeRecord',
    
    # ORM models
    'SierraChartFill',
    'ProcessedTradeORM',
    'AccountORM',
    'PerformanceMetric',
    'TemporalPerformance', 
    'Recommendation',
    'DataImportLog',
    'SystemHealth',
    
    # Enhanced time-bin analytics models
    'MarketData',
    'VolatilityRegime',
    'TimeBinAnalysis',
    'RegimePerformance',
    'WalkForwardResult',
    'MonteCarloResult',
    'ExportHistory',
    'PDFReport'
]