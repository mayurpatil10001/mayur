"""
Market Data Types and Shared Classes

This module contains shared data types and classes used by market data services
to avoid circular imports.
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class MarketDataSeries:
    """Container for market data with metadata."""
    symbol: str
    data: pd.DataFrame
    start_date: datetime
    end_date: datetime
    total_records: int
    missing_dates: List[datetime]
    data_quality_score: float  # 0-1, higher is better


@dataclass
class SynchronizedMarketData:
    """Container for market data synchronized with trade timestamps."""
    trade_timestamps: List[datetime]
    spy_data: Dict[datetime, float]  # timestamp -> close price
    qqq_data: Dict[datetime, float]  # timestamp -> close price
    vix_data: Dict[datetime, float]  # timestamp -> close price
    synchronization_quality: float  # 0-1, percentage of trades with market data


class MarketDataValidationError(Exception):
    """Raised when market data fails validation checks."""
    pass