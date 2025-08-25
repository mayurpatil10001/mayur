"""
Free Market Data Service

This service provides free market data access using Stooq.com and other free sources
as a fallback when Yahoo Finance fails with rate limits (429, 409 errors).

Supports: SPY, QQQ, VIX EOD data
Requirements: 11.1, 11.2, 10.2 - Task #5 alternative implementation
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
import time
import io

from .market_data_ingestion import MarketDataSeries, MarketDataValidationError


class FreeMarketDataService:
    """
    Free market data service using Stooq.com and other free sources.
    
    This service provides a fallback data source when Yahoo Finance encounters
    rate limiting or other API issues (429, 409 errors).
    """
    
    def __init__(self):
        """Initialize the free market data service."""
        self.base_url = "https://stooq.com/q/d/l/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Symbol mappings for Stooq
        self.stooq_symbols = {
            'SPY': 'spy.us',
            'QQQ': 'qqq.us', 
            'VIX': 'vix'
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
    
    def fetch_spy_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch SPY data from Stooq.com.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: SPY data with quality metrics
        """
        logger.info(f"Fetching SPY data from Stooq: {start_date.date()} to {end_date.date()}")
        return self._fetch_stooq_data('SPY', start_date, end_date)
    
    def fetch_qqq_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch QQQ data from Stooq.com.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: QQQ data with quality metrics
        """
        logger.info(f"Fetching QQQ data from Stooq: {start_date.date()} to {end_date.date()}")
        return self._fetch_stooq_data('QQQ', start_date, end_date)
    
    def fetch_vix_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch VIX data from Stooq.com.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: VIX data with quality metrics
        """
        logger.info(f"Fetching VIX data from Stooq: {start_date.date()} to {end_date.date()}")
        return self._fetch_stooq_data('VIX', start_date, end_date)
    
    def _fetch_stooq_data(self, symbol: str, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch data from Stooq.com with proper error handling and rate limiting.
        
        Args:
            symbol: Market symbol (SPY, QQQ, VIX)
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: Market data with quality metrics
            
        Raises:
            MarketDataValidationError: If data cannot be retrieved or validated
        """
        try:
            # Rate limiting
            self._enforce_rate_limit()
            
            # Get Stooq symbol
            stooq_symbol = self.stooq_symbols.get(symbol)
            if not stooq_symbol:
                raise MarketDataValidationError(f"Symbol {symbol} not supported by Stooq")
            
            # Build URL with date parameters
            url = f"{self.base_url}"
            params = {
                's': stooq_symbol,
                'd1': start_date.strftime('%Y%m%d'),
                'd2': end_date.strftime('%Y%m%d'),
                'i': 'd'  # daily interval
            }
            
            logger.debug(f"Fetching from Stooq URL: {url} with params: {params}")
            
            # Make request with retry logic
            response = self._make_request_with_retry(url, params)
            
            if response.status_code != 200:
                raise MarketDataValidationError(
                    f"Stooq request failed for {symbol}: HTTP {response.status_code}"
                )
            
            # Parse CSV data
            data = self._parse_stooq_csv(response.text, symbol)
            
            # Validate and create MarketDataSeries
            return self._validate_and_create_series(data, symbol, start_date, end_date)
            
        except requests.RequestException as e:
            logger.error(f"Network error fetching {symbol} from Stooq: {e}")
            raise MarketDataValidationError(f"Network error fetching {symbol}: {e}")
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Stooq: {e}")
            raise MarketDataValidationError(f"Failed to fetch {symbol} from Stooq: {e}")
    
    def _make_request_with_retry(self, url: str, params: dict, max_retries: int = 3) -> requests.Response:
        """
        Make HTTP request with retry logic for reliability.
        
        Args:
            url: Request URL
            params: Request parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            requests.Response: HTTP response
            
        Raises:
            requests.RequestException: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                return response
                
            except requests.RequestException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All retry attempts failed: {e}")
        
        raise last_exception
    
    def _parse_stooq_csv(self, csv_content: str, symbol: str) -> pd.DataFrame:
        """
        Parse CSV data from Stooq response.
        
        Args:
            csv_content: Raw CSV content from Stooq
            symbol: Market symbol for error context
            
        Returns:
            pd.DataFrame: Parsed market data
            
        Raises:
            MarketDataValidationError: If CSV cannot be parsed
        """
        try:
            # Stooq CSV format: Date,Open,High,Low,Close,Volume
            df = pd.read_csv(
                io.StringIO(csv_content),
                parse_dates=['Date'],
                index_col='Date'
            )
            
            if df.empty:
                raise MarketDataValidationError(f"No data returned from Stooq for {symbol}")
            
            # Ensure required columns exist
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise MarketDataValidationError(
                    f"Missing columns in Stooq data for {symbol}: {missing_columns}"
                )
            
            # Sort by date ascending (oldest first)
            df = df.sort_index()
            
            logger.info(f"Successfully parsed {len(df)} records from Stooq for {symbol}")
            return df
            
        except pd.errors.EmptyDataError:
            raise MarketDataValidationError(f"Empty CSV data from Stooq for {symbol}")
        except pd.errors.ParserError as e:
            raise MarketDataValidationError(f"CSV parsing error for {symbol}: {e}")
        except Exception as e:
            logger.error(f"Error parsing Stooq CSV for {symbol}: {e}")
            raise MarketDataValidationError(f"Failed to parse Stooq data for {symbol}: {e}")
    
    def _validate_and_create_series(self, data: pd.DataFrame, symbol: str, 
                                  start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Validate data and create MarketDataSeries object.
        
        Args:
            data: Parsed market data
            symbol: Market symbol
            start_date: Expected start date
            end_date: Expected end date
            
        Returns:
            MarketDataSeries: Validated market data series
        """
        # Basic data validation
        if data.empty:
            raise MarketDataValidationError(f"No valid data for {symbol}")
        
        # Check for reasonable price ranges
        if symbol in ['SPY', 'QQQ']:
            # Stock prices should be positive and reasonable
            if (data['Close'] <= 0).any():
                logger.warning(f"Found non-positive prices in {symbol} data from Stooq")
            if (data['Close'] > 1000).any():
                logger.warning(f"Found unusually high prices in {symbol} data from Stooq")
        elif symbol == 'VIX':
            # VIX should be positive and typically under 100
            if (data['Close'] <= 0).any():
                logger.warning(f"Found non-positive VIX values from Stooq")
            if (data['Close'] > 100).any():
                logger.warning(f"Found unusually high VIX values from Stooq")
        
        # Calculate data quality metrics
        total_days = (end_date - start_date).days + 1
        expected_trading_days = total_days * 5 / 7  # Rough estimate
        
        # Identify expected trading days
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        expected_dates = [d for d in date_range if d.weekday() < 5]  # Monday=0, Friday=4
        missing_dates = [d for d in expected_dates if d not in data.index]
        
        # Calculate quality score
        completeness_score = len(data) / max(expected_trading_days, 1)
        completeness_score = min(completeness_score, 1.0)  # Cap at 1.0
        
        gap_penalty = len(missing_dates) / max(len(expected_dates), 1)
        quality_score = completeness_score * (1 - gap_penalty * 0.5)
        quality_score = max(quality_score, 0.0)  # Floor at 0.0
        
        if quality_score < 0.8:
            logger.warning(f"Low data quality from Stooq for {symbol}: {quality_score:.2%}")
        
        return MarketDataSeries(
            symbol=symbol,
            data=data,
            start_date=start_date,
            end_date=end_date,
            total_records=len(data),
            missing_dates=missing_dates,
            data_quality_score=quality_score
        )
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests to be respectful to Stooq."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def test_connection(self) -> bool:
        """
        Test connection to Stooq service.
        
        Returns:
            bool: True if connection is successful
        """
        try:
            # Test with a simple SPY request for recent data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Last week
            
            url = f"{self.base_url}"
            params = {
                's': 'spy.us',
                'd1': start_date.strftime('%Y%m%d'),
                'd2': end_date.strftime('%Y%m%d'),
                'i': 'd'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            success = response.status_code == 200 and len(response.text) > 50
            
            if success:
                logger.info("Stooq connection test successful")
            else:
                logger.warning(f"Stooq connection test failed: HTTP {response.status_code}")
            
            return success
            
        except Exception as e:
            logger.error(f"Stooq connection test failed: {e}")
            return False