"""
Market Data Ingestion Service

This service handles fetching and synchronizing market data (SPY, QQQ, VIX) 
with trade timestamps for advanced time-bin analytics.

Requirements: 11.1, 11.2, 10.2
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session
from loguru import logger

from ..models.time_bin_analytics import MarketData
from ..models.database import ProcessedTrade
from ..database.connection import get_db_session


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


class MarketDataIngestion:
    """
    Service for fetching and managing market data for time-bin analytics.
    
    This class handles:
    - Fetching SPY/QQQ/VIX data from Yahoo Finance
    - Data validation and quality checks
    - Synchronization with trade timestamps
    - Database storage and retrieval
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the market data ingestion service."""
        self.db_session = db_session or get_db_session()
        self.supported_symbols = ['SPY', 'QQQ', '^VIX']
        self.symbol_mapping = {
            'SPY': 'SPY',
            'QQQ': 'QQQ', 
            'VIX': '^VIX'
        }
        # Initialize free data service as fallback (lazy loading to avoid circular imports)
        self._free_data_service = None
        
    def fetch_spy_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch SPY market data with comprehensive error handling and fallback sources.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: SPY data with quality metrics
            
        Raises:
            MarketDataValidationError: If data quality is insufficient from all sources
        """
        logger.info(f"Fetching SPY data from {start_date.date()} to {end_date.date()}")
        
        # Try Yahoo Finance first
        try:
            spy_ticker = yf.Ticker('SPY')
            data = spy_ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),  # Include end date
                interval='1d',
                auto_adjust=True,
                prepost=False
            )
            
            if not data.empty:
                validated_data = self._validate_market_data(data, 'SPY', start_date, end_date)
                logger.info(f"Successfully fetched {len(validated_data.data)} SPY records from Yahoo Finance")
                return validated_data
            else:
                logger.warning("No SPY data from Yahoo Finance, trying free data source...")
                
        except Exception as e:
            logger.warning(f"Yahoo Finance failed for SPY: {e}, trying free data source...")
        
        # Fallback to free data source (Stooq)
        try:
            if self._free_data_service is None:
                from .free_market_data import FreeMarketDataService
                self._free_data_service = FreeMarketDataService()
            
            result = self._free_data_service.fetch_spy_data(start_date, end_date)
            logger.info(f"Successfully fetched {result.total_records} SPY records from free data source")
            return result
            
        except Exception as e:
            logger.error(f"All data sources failed for SPY: {e}")
            raise MarketDataValidationError(f"Failed to fetch SPY data from all sources: {e}")
    
    def fetch_qqq_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch QQQ market data with comprehensive error handling and fallback sources.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: QQQ data with quality metrics
            
        Raises:
            MarketDataValidationError: If data quality is insufficient from all sources
        """
        logger.info(f"Fetching QQQ data from {start_date.date()} to {end_date.date()}")
        
        # Try Yahoo Finance first
        try:
            qqq_ticker = yf.Ticker('QQQ')
            data = qqq_ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),  # Include end date
                interval='1d',
                auto_adjust=True,
                prepost=False
            )
            
            if not data.empty:
                validated_data = self._validate_market_data(data, 'QQQ', start_date, end_date)
                logger.info(f"Successfully fetched {len(validated_data.data)} QQQ records from Yahoo Finance")
                return validated_data
            else:
                logger.warning("No QQQ data from Yahoo Finance, trying free data source...")
                
        except Exception as e:
            logger.warning(f"Yahoo Finance failed for QQQ: {e}, trying free data source...")
        
        # Fallback to free data source (Stooq)
        try:
            if self._free_data_service is None:
                from .free_market_data import FreeMarketDataService
                self._free_data_service = FreeMarketDataService()
            
            result = self._free_data_service.fetch_qqq_data(start_date, end_date)
            logger.info(f"Successfully fetched {result.total_records} QQQ records from free data source")
            return result
            
        except Exception as e:
            logger.error(f"All data sources failed for QQQ: {e}")
            raise MarketDataValidationError(f"Failed to fetch QQQ data from all sources: {e}")
    
    def fetch_vix_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch VIX volatility data with comprehensive error handling and fallback sources.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: VIX data with quality metrics
            
        Raises:
            MarketDataValidationError: If data quality is insufficient from all sources
        """
        logger.info(f"Fetching VIX data from {start_date.date()} to {end_date.date()}")
        
        # Try Yahoo Finance first
        try:
            vix_ticker = yf.Ticker('^VIX')
            data = vix_ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),  # Include end date
                interval='1d',
                auto_adjust=True,
                prepost=False
            )
            
            if not data.empty:
                validated_data = self._validate_market_data(data, 'VIX', start_date, end_date)
                logger.info(f"Successfully fetched {len(validated_data.data)} VIX records from Yahoo Finance")
                return validated_data
            else:
                logger.warning("No VIX data from Yahoo Finance, trying free data source...")
                
        except Exception as e:
            logger.warning(f"Yahoo Finance failed for VIX: {e}, trying free data source...")
        
        # Fallback to free data source (Stooq)
        try:
            if self._free_data_service is None:
                from .free_market_data import FreeMarketDataService
                self._free_data_service = FreeMarketDataService()
            
            result = self._free_data_service.fetch_vix_data(start_date, end_date)
            logger.info(f"Successfully fetched {result.total_records} VIX records from free data source")
            return result
            
        except Exception as e:
            logger.error(f"All data sources failed for VIX: {e}")
            raise MarketDataValidationError(f"Failed to fetch VIX data from all sources: {e}")
    
    def synchronize_market_data(self, trade_timestamps: List[datetime]) -> SynchronizedMarketData:
        """
        Synchronize market data with trade timestamps for accurate correlation analysis.
        
        This method ensures that for each trade timestamp, we have corresponding
        market data (SPY, QQQ, VIX) from the same trading day.
        
        Args:
            trade_timestamps: List of trade entry/exit timestamps
            
        Returns:
            SynchronizedMarketData: Market data aligned with trade timestamps
            
        Raises:
            MarketDataValidationError: If synchronization quality is too low
        """
        try:
            if not trade_timestamps:
                raise MarketDataValidationError("No trade timestamps provided for synchronization")
                
            logger.info(f"Synchronizing market data for {len(trade_timestamps)} trade timestamps")
            
            # Determine date range for market data
            min_date = min(trade_timestamps).replace(hour=0, minute=0, second=0, microsecond=0)
            max_date = max(trade_timestamps).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Fetch market data for the required date range
            spy_data = self.fetch_spy_data(min_date, max_date)
            qqq_data = self.fetch_qqq_data(min_date, max_date)
            vix_data = self.fetch_vix_data(min_date, max_date)
            
            # Create synchronized data dictionaries
            spy_sync = {}
            qqq_sync = {}
            vix_sync = {}
            successful_syncs = 0
            
            for timestamp in trade_timestamps:
                trade_date = timestamp.date()
                
                # Find market data for the trade date
                spy_price = self._get_market_data_for_date(spy_data.data, trade_date)
                qqq_price = self._get_market_data_for_date(qqq_data.data, trade_date)
                vix_price = self._get_market_data_for_date(vix_data.data, trade_date)
                
                if spy_price is not None and qqq_price is not None and vix_price is not None:
                    spy_sync[timestamp] = spy_price
                    qqq_sync[timestamp] = qqq_price
                    vix_sync[timestamp] = vix_price
                    successful_syncs += 1
                else:
                    # Log missing data for debugging
                    logger.warning(f"Missing market data for trade date {trade_date}")
            
            # Calculate synchronization quality
            sync_quality = successful_syncs / len(trade_timestamps) if trade_timestamps else 0.0
            
            if sync_quality < 0.8:  # Require at least 80% synchronization
                logger.warning(f"Low synchronization quality: {sync_quality:.2%}")
            
            logger.info(f"Market data synchronization complete: {sync_quality:.2%} success rate")
            
            return SynchronizedMarketData(
                trade_timestamps=trade_timestamps,
                spy_data=spy_sync,
                qqq_data=qqq_sync,
                vix_data=vix_sync,
                synchronization_quality=sync_quality
            )
            
        except Exception as e:
            logger.error(f"Error synchronizing market data: {str(e)}")
            raise MarketDataValidationError(f"Failed to synchronize market data: {str(e)}")
    
    def store_market_data(self, market_data: MarketDataSeries) -> int:
        """
        Store market data in the database with duplicate handling.
        
        Args:
            market_data: MarketDataSeries to store
            
        Returns:
            int: Number of records stored
        """
        try:
            stored_count = 0
            
            for date, row in market_data.data.iterrows():
                # Check if record already exists
                existing = self.db_session.query(MarketData).filter(
                    MarketData.symbol == market_data.symbol,
                    MarketData.date == date.date()
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open_price = float(row['Open']) if pd.notna(row['Open']) else None
                    existing.high_price = float(row['High']) if pd.notna(row['High']) else None
                    existing.low_price = float(row['Low']) if pd.notna(row['Low']) else None
                    existing.close_price = float(row['Close']) if pd.notna(row['Close']) else None
                    existing.volume = int(row['Volume']) if pd.notna(row['Volume']) else None
                    existing.adjusted_close = float(row['Close']) if pd.notna(row['Close']) else None
                else:
                    # Create new record
                    market_record = MarketData(
                        symbol=market_data.symbol,
                        date=date.date(),
                        open_price=float(row['Open']) if pd.notna(row['Open']) else None,
                        high_price=float(row['High']) if pd.notna(row['High']) else None,
                        low_price=float(row['Low']) if pd.notna(row['Low']) else None,
                        close_price=float(row['Close']) if pd.notna(row['Close']) else None,
                        volume=int(row['Volume']) if pd.notna(row['Volume']) else None,
                        adjusted_close=float(row['Close']) if pd.notna(row['Close']) else None
                    )
                    self.db_session.add(market_record)
                
                stored_count += 1
            
            self.db_session.commit()
            logger.info(f"Stored {stored_count} {market_data.symbol} market data records")
            return stored_count
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error storing market data: {str(e)}")
            raise MarketDataValidationError(f"Failed to store market data: {str(e)}")
    
    def _validate_market_data(self, data: pd.DataFrame, symbol: str, 
                            start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Validate and clean market data with quality scoring.
        
        Args:
            data: Raw market data from yfinance
            symbol: Market symbol (SPY, QQQ, VIX)
            start_date: Expected start date
            end_date: Expected end date
            
        Returns:
            MarketDataSeries: Validated data with quality metrics
            
        Raises:
            MarketDataValidationError: If data quality is insufficient
        """
        try:
            # Basic validation
            if data.empty:
                raise MarketDataValidationError(f"No data available for {symbol}")
            
            # Check required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                raise MarketDataValidationError(f"Missing columns for {symbol}: {missing_columns}")
            
            # Remove rows with all NaN values
            data_clean = data.dropna(how='all')
            
            # Check for reasonable price ranges
            if symbol in ['SPY', 'QQQ']:
                # Stock prices should be positive and reasonable
                if (data_clean['Close'] <= 0).any():
                    logger.warning(f"Found non-positive prices in {symbol} data")
                if (data_clean['Close'] > 1000).any():
                    logger.warning(f"Found unusually high prices in {symbol} data")
            elif symbol == 'VIX':
                # VIX should be positive and typically under 100
                if (data_clean['Close'] <= 0).any():
                    logger.warning(f"Found non-positive VIX values")
                if (data_clean['Close'] > 100).any():
                    logger.warning(f"Found unusually high VIX values")
            
            # Calculate expected trading days (approximate)
            total_days = (end_date - start_date).days + 1
            expected_trading_days = total_days * 5 / 7  # Rough estimate
            
            # Identify missing dates
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            trading_days = [d for d in date_range if d.weekday() < 5]  # Monday=0, Friday=4
            missing_dates = [d for d in trading_days if d not in data_clean.index]
            
            # Calculate data quality score
            completeness_score = len(data_clean) / max(expected_trading_days, 1)
            completeness_score = min(completeness_score, 1.0)  # Cap at 1.0
            
            # Check for data gaps (consecutive missing days)
            gap_penalty = len(missing_dates) / max(len(trading_days), 1)
            quality_score = completeness_score * (1 - gap_penalty * 0.5)
            quality_score = max(quality_score, 0.0)  # Floor at 0.0
            
            # Warn if quality is low
            if quality_score < 0.8:
                logger.warning(f"Low data quality for {symbol}: {quality_score:.2%}")
            
            # Convert symbol for storage (^VIX -> VIX)
            storage_symbol = symbol.replace('^', '')
            
            return MarketDataSeries(
                symbol=storage_symbol,
                data=data_clean,
                start_date=start_date,
                end_date=end_date,
                total_records=len(data_clean),
                missing_dates=missing_dates,
                data_quality_score=quality_score
            )
            
        except Exception as e:
            logger.error(f"Error validating {symbol} data: {str(e)}")
            raise MarketDataValidationError(f"Data validation failed for {symbol}: {str(e)}")
    
    def _get_market_data_for_date(self, market_data: pd.DataFrame, trade_date) -> Optional[float]:
        """
        Get market data (close price) for a specific trade date.
        
        Args:
            market_data: DataFrame with market data
            trade_date: Date to find market data for
            
        Returns:
            Optional[float]: Close price for the date, or None if not found
        """
        try:
            # Convert trade_date to pandas Timestamp for comparison
            if hasattr(trade_date, 'date'):
                trade_date = trade_date.date()
            
            # Look for exact date match first
            for idx, row in market_data.iterrows():
                if idx.date() == trade_date:
                    return float(row['Close']) if pd.notna(row['Close']) else None
            
            # If no exact match, try previous trading day (for weekend trades)
            for i in range(1, 4):  # Check up to 3 days back
                check_date = pd.Timestamp(trade_date) - pd.Timedelta(days=i)
                for idx, row in market_data.iterrows():
                    if idx.date() == check_date.date():
                        logger.debug(f"Using {check_date.date()} market data for trade on {trade_date}")
                        return float(row['Close']) if pd.notna(row['Close']) else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting market data for date {trade_date}: {str(e)}")
            return None
    
    def get_trade_timestamps_for_account(self, account_name: str, 
                                       start_date: Optional[datetime] = None,
                                       end_date: Optional[datetime] = None) -> List[datetime]:
        """
        Get all trade timestamps for an account within a date range.
        
        Args:
            account_name: Account to get trades for
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List[datetime]: List of trade entry timestamps
        """
        try:
            query = self.db_session.query(ProcessedTrade.entry_time).filter(
                ProcessedTrade.account_name == account_name
            )
            
            if start_date:
                query = query.filter(ProcessedTrade.entry_time >= start_date)
            if end_date:
                query = query.filter(ProcessedTrade.entry_time <= end_date)
            
            timestamps = [row[0] for row in query.all()]
            logger.info(f"Found {len(timestamps)} trade timestamps for account {account_name}")
            return timestamps
            
        except Exception as e:
            logger.error(f"Error getting trade timestamps: {str(e)}")
            return []
    
    def validate_synchronization_quality(self, sync_data: SynchronizedMarketData, 
                                       min_quality: float = 0.8) -> bool:
        """
        Validate that synchronization quality meets minimum requirements.
        
        Args:
            sync_data: Synchronized market data
            min_quality: Minimum acceptable synchronization quality (0-1)
            
        Returns:
            bool: True if quality is acceptable
            
        Raises:
            MarketDataValidationError: If quality is below threshold
        """
        if sync_data.synchronization_quality < min_quality:
            raise MarketDataValidationError(
                f"Synchronization quality {sync_data.synchronization_quality:.2%} "
                f"below minimum threshold {min_quality:.2%}"
            )
        return True