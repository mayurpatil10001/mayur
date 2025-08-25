"""
Services module for the Trading Optimization Platform.

This module contains business logic services for advanced analytics
and trading optimization functionality.
"""

from .time_bin_analyzer import TimeBin, TimeBinAnalyzer, TimeBinMetrics, SignificanceTest
from .market_data_ingestion import (
    MarketDataIngestion, MarketDataSeries, SynchronizedMarketData,
    MarketDataValidationError
)
from .free_market_data import FreeMarketDataService

__all__ = [
    'TimeBin',
    'TimeBinAnalyzer', 
    'TimeBinMetrics',
    'SignificanceTest',
    'MarketDataIngestion',
    'MarketDataSeries',
    'SynchronizedMarketData',
    'MarketDataValidationError',
    'FreeMarketDataService'
]