"""
Analytics and statistical analysis interfaces.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from datetime import datetime

from ..models.trading import ProcessedTrade, PerformanceMetrics


class IPerformanceAnalyzer(ABC):
    """Interface for performance metrics calculation."""
    
    @abstractmethod
    def calculate_performance_metrics(self, trades: List[ProcessedTrade]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics for a set of trades."""
        pass
    
    @abstractmethod
    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio for a series of returns."""
        pass
    
    @abstractmethod
    def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown from equity curve."""
        pass
    
    @abstractmethod
    def calculate_volatility(self, returns: List[float]) -> float:
        """Calculate volatility (standard deviation) of returns."""
        pass


class ITemporalAnalyzer(ABC):
    """Interface for temporal pattern analysis."""
    
    @abstractmethod
    def analyze_hourly_patterns(self, trades: List[ProcessedTrade]) -> Dict[int, Dict[str, float]]:
        """Analyze performance patterns by hour of day."""
        pass
    
    @abstractmethod
    def analyze_daily_patterns(self, trades: List[ProcessedTrade]) -> Dict[int, Dict[str, float]]:
        """Analyze performance patterns by day of week."""
        pass
    
    @abstractmethod
    def test_temporal_significance(self, trades: List[ProcessedTrade]) -> Dict[str, Any]:
        """Test statistical significance of temporal patterns."""
        pass


class IStatisticalTestService(ABC):
    """Interface for statistical testing and comparison."""
    
    @abstractmethod
    def compare_account_performance(self, account1_trades: List[ProcessedTrade], 
                                  account2_trades: List[ProcessedTrade]) -> Dict[str, Any]:
        """Compare performance between two accounts statistically."""
        pass
    
    @abstractmethod
    def test_normality(self, returns: List[float]) -> Tuple[float, float]:
        """Test if returns follow normal distribution."""
        pass
    
    @abstractmethod
    def calculate_confidence_intervals(self, data: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence intervals for data."""
        pass