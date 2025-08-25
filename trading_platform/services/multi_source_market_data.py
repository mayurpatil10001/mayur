"""
Multi-Source Market Data Service

This service provides market data from multiple free sources as fallbacks
when Yahoo Finance is unavailable. It's designed for infrequent use since
data is stored locally after fetching.

Free Data Sources:
1. Alpha Vantage (25 requests/day free)
2. Polygon.io (5 requests/minute free) 
3. Tiingo (1000 requests/day free)
4. Yahoo Finance (as fallback)

Requirements: 11.1, 11.2, 10.2
"""

import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import time
import json
from loguru import logger

from .market_data_ingestion import MarketDataSeries, MarketDataValidationError


@dataclass
class DataSourceConfig:
    """Configuration for a market data source."""
    name: str
    base_url: str
    api_key_required: bool
    rate_limit_per_minute: int
    free_tier_daily_limit: Optional[int] = None


class MultiSourceMarketDataService:
    """
    Enhanced market data service with multiple free data sources.
    
    This service tries multiple sources in order of preference:
    1. Alpha Vantage (most reliable, 25/day free)
    2. Tiingo (good backup, 1000/day free)  
    3. Polygon.io (good for recent data, 5/min free)
    4. Yahoo Finance (unreliable but no limits)
    """
    
    def __init__(self, alpha_vantage_key: Optional[str] = None, 
                 tiingo_key: Optional[str] = None,
                 polygon_key: Optional[str] = None):
        """
        Initialize with optional API keys.
        
        Args:
            alpha_vantage_key: Free from https://www.alphavantage.co/support/#api-key
            tiingo_key: Free from https://api.tiingo.com/
            polygon_key: Free from https://polygon.io/
        """
        self.alpha_vantage_key = alpha_vantage_key
        self.tiingo_key = tiingo_key
        self.polygon_key = polygon_key
        
        # Track API usage to respect rate limits
        self.last_request_times = {}
        self.daily_request_counts = {}
        
        # Data source configurations
        self.sources = {
            'alphavantage': DataSourceConfig(
                name='Alpha Vantage',
                base_url='https://www.alphavantage.co/query',
                api_key_required=True,
                rate_limit_per_minute=5,
                free_tier_daily_limit=25
            ),
            'tiingo': DataSourceConfig(
                name='Tiingo',
                base_url='https://api.tiingo.com/tiingo/daily',
                api_key_required=True,
                rate_limit_per_minute=20,
                free_tier_daily_limit=1000
            ),
            'polygon': DataSourceConfig(
                name='Polygon.io',
                base_url='https://api.polygon.io/v2/aggs/ticker',
                api_key_required=True,
                rate_limit_per_minute=5
            ),
            'yfinance': DataSourceConfig(
                name='Yahoo Finance',
                base_url='',
                api_key_required=False,
                rate_limit_per_minute=60  # Conservative estimate
            )
        }
    
    def fetch_spy_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """Fetch SPY data using multiple sources as fallbacks."""
        return self._fetch_symbol_data('SPY', start_date, end_date)
    
    def fetch_qqq_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """Fetch QQQ data using multiple sources as fallbacks."""
        return self._fetch_symbol_data('QQQ', start_date, end_date)
    
    def fetch_vix_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """Fetch VIX data using multiple sources as fallbacks."""
        return self._fetch_symbol_data('^VIX', start_date, end_date)
    
    def _fetch_symbol_data(self, symbol: str, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch data for a symbol trying multiple sources in order of preference.
        
        Args:
            symbol: Stock symbol (SPY, QQQ, ^VIX)
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            MarketDataSeries: Market data with quality metrics
            
        Raises:
            MarketDataValidationError: If all sources fail
        """
        logger.info(f"Fetching {symbol} data from {start_date.date()} to {end_date.date()}")
        
        # Define source priority order
        source_order = []
        
        # Add sources based on available API keys
        if self.alpha_vantage_key:
            source_order.append('alphavantage')
        if self.tiingo_key:
            source_order.append('tiingo')
        if self.polygon_key:
            source_order.append('polygon')
        
        # Always add Yahoo Finance as final fallback
        source_order.append('yfinance')
        
        last_error = None
        
        for source_name in source_order:
            try:
                logger.info(f"Trying {self.sources[source_name].name} for {symbol}")
                
                # Check rate limits
                if not self._check_rate_limit(source_name):
                    logger.warning(f"Rate limit exceeded for {source_name}, skipping")
                    continue
                
                # Fetch data from source
                data = self._fetch_from_source(source_name, symbol, start_date, end_date)
                
                if data is not None and not data.empty:
                    # Validate and return data
                    validated_data = self._validate_and_convert_data(data, symbol, start_date, end_date, source_name)
                    logger.info(f"Successfully fetched {len(validated_data.data)} {symbol} records from {source_name}")
                    return validated_data
                else:
                    logger.warning(f"No data returned from {source_name} for {symbol}")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Error fetching {symbol} from {source_name}: {e}")
                continue
        
        # All sources failed
        raise MarketDataValidationError(f"Failed to fetch {symbol} data from all sources. Last error: {last_error}")
    
    def _fetch_from_source(self, source_name: str, symbol: str, 
                          start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch data from a specific source."""
        
        if source_name == 'alphavantage':
            return self._fetch_from_alphavantage(symbol, start_date, end_date)
        elif source_name == 'tiingo':
            return self._fetch_from_tiingo(symbol, start_date, end_date)
        elif source_name == 'polygon':
            return self._fetch_from_polygon(symbol, start_date, end_date)
        elif source_name == 'yfinance':
            return self._fetch_from_yfinance(symbol, start_date, end_date)
        else:
            raise ValueError(f"Unknown source: {source_name}")
    
    def _fetch_from_alphavantage(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch data from Alpha Vantage API."""
        if not self.alpha_vantage_key:
            return None
        
        # Alpha Vantage uses different symbol format for VIX
        av_symbol = 'VIX' if symbol == '^VIX' else symbol
        
        url = self.sources['alphavantage'].base_url
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': av_symbol,
            'apikey': self.alpha_vantage_key,
            'outputsize': 'full',
            'datatype': 'json'
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for API errors
        if 'Error Message' in data:
            raise MarketDataValidationError(f"Alpha Vantage error: {data['Error Message']}")
        
        if 'Note' in data:
            raise MarketDataValidationError(f"Alpha Vantage rate limit: {data['Note']}")
        
        # Parse time series data
        time_series_key = 'Time Series (Daily)'
        if time_series_key not in data:
            return None
        
        time_series = data[time_series_key]
        
        # Convert to DataFrame
        df_data = []
        for date_str, values in time_series.items():
            date = pd.to_datetime(date_str)
            if start_date <= date <= end_date:
                df_data.append({
                    'Date': date,
                    'Open': float(values['1. open']),
                    'High': float(values['2. high']),
                    'Low': float(values['3. low']),
                    'Close': float(values['4. close']),
                    'Volume': int(values['5. volume'])
                })
        
        if not df_data:
            return None
        
        df = pd.DataFrame(df_data)
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        
        return df
    
    def _fetch_from_tiingo(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch data from Tiingo API."""
        if not self.tiingo_key:
            return None
        
        # Tiingo uses different symbol format for VIX
        tiingo_symbol = 'VIX' if symbol == '^VIX' else symbol
        
        url = f"{self.sources['tiingo'].base_url}/{tiingo_symbol}/prices"
        params = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'token': self.tiingo_key
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            return None
        
        # Convert to DataFrame
        df_data = []
        for item in data:
            df_data.append({
                'Date': pd.to_datetime(item['date']),
                'Open': item['open'],
                'High': item['high'],
                'Low': item['low'],
                'Close': item['close'],
                'Volume': item['volume']
            })
        
        if not df_data:
            return None
        
        df = pd.DataFrame(df_data)
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        
        return df
    
    def _fetch_from_polygon(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch data from Polygon.io API."""
        if not self.polygon_key:
            return None
        
        # Polygon uses different symbol format for VIX
        polygon_symbol = 'I:VIX' if symbol == '^VIX' else symbol
        
        url = f"{self.sources['polygon'].base_url}/{polygon_symbol}/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        params = {
            'apikey': self.polygon_key
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') != 'OK' or 'results' not in data:
            return None
        
        results = data['results']
        if not results:
            return None
        
        # Convert to DataFrame
        df_data = []
        for item in results:
            df_data.append({
                'Date': pd.to_datetime(item['t'], unit='ms'),
                'Open': item['o'],
                'High': item['h'],
                'Low': item['l'],
                'Close': item['c'],
                'Volume': item['v']
            })
        
        df = pd.DataFrame(df_data)
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        
        return df
    
    def _fetch_from_yfinance(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch data from Yahoo Finance (fallback)."""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=True,
                prepost=False
            )
            
            if data.empty:
                return None
            
            return data
            
        except Exception as e:
            logger.warning(f"Yahoo Finance error for {symbol}: {e}")
            return None
    
    def _validate_and_convert_data(self, data: pd.DataFrame, symbol: str, 
                                 start_date: datetime, end_date: datetime, 
                                 source_name: str) -> MarketDataSeries:
        """Validate and convert raw data to MarketDataSeries."""
        
        # Ensure required columns exist
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise MarketDataValidationError(f"Missing columns from {source_name}: {missing_columns}")
        
        # Remove rows with all NaN values
        data_clean = data.dropna(how='all')
        
        # Basic validation
        if data_clean.empty:
            raise MarketDataValidationError(f"No valid data from {source_name}")
        
        # Check for reasonable price ranges
        close_prices = data_clean['Close']
        if symbol in ['SPY', 'QQQ']:
            if (close_prices <= 0).any():
                logger.warning(f"Found non-positive prices in {symbol} data from {source_name}")
            if (close_prices > 2000).any():
                logger.warning(f"Found unusually high prices in {symbol} data from {source_name}")
        elif symbol in ['^VIX', 'VIX']:
            if (close_prices <= 0).any():
                logger.warning(f"Found non-positive VIX values from {source_name}")
            if (close_prices > 200).any():
                logger.warning(f"Found unusually high VIX values from {source_name}")
        
        # Calculate data quality score
        total_days = (end_date - start_date).days + 1
        expected_trading_days = total_days * 5 / 7  # Rough estimate
        completeness_score = len(data_clean) / max(expected_trading_days, 1)
        completeness_score = min(completeness_score, 1.0)
        
        # Identify missing dates
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = [d for d in date_range if d.weekday() < 5]
        missing_dates = [d for d in trading_days if d not in data_clean.index]
        
        quality_score = completeness_score * (1 - len(missing_dates) / max(len(trading_days), 1) * 0.5)
        quality_score = max(quality_score, 0.0)
        
        # Convert symbol for storage (^VIX -> VIX)
        storage_symbol = symbol.replace('^', '')
        
        logger.info(f"Data quality from {source_name}: {quality_score:.2%} ({len(data_clean)} records)")
        
        return MarketDataSeries(
            symbol=storage_symbol,
            data=data_clean,
            start_date=start_date,
            end_date=end_date,
            total_records=len(data_clean),
            missing_dates=missing_dates,
            data_quality_score=quality_score
        )
    
    def _check_rate_limit(self, source_name: str) -> bool:
        """Check if we can make a request to this source without exceeding rate limits."""
        config = self.sources[source_name]
        current_time = time.time()
        
        # Check per-minute rate limit
        if source_name not in self.last_request_times:
            self.last_request_times[source_name] = []
        
        # Remove requests older than 1 minute
        minute_ago = current_time - 60
        self.last_request_times[source_name] = [
            t for t in self.last_request_times[source_name] if t > minute_ago
        ]
        
        # Check if we can make another request
        if len(self.last_request_times[source_name]) >= config.rate_limit_per_minute:
            return False
        
        # Check daily limit if applicable
        if config.free_tier_daily_limit:
            today = datetime.now().date()
            if source_name not in self.daily_request_counts:
                self.daily_request_counts[source_name] = {}
            
            if today not in self.daily_request_counts[source_name]:
                self.daily_request_counts[source_name][today] = 0
            
            if self.daily_request_counts[source_name][today] >= config.free_tier_daily_limit:
                return False
        
        # Record this request
        self.last_request_times[source_name].append(current_time)
        if config.free_tier_daily_limit:
            today = datetime.now().date()
            self.daily_request_counts[source_name][today] += 1
        
        return True
    
    def get_api_usage_status(self) -> Dict[str, Dict]:
        """Get current API usage status for all sources."""
        status = {}
        current_time = time.time()
        today = datetime.now().date()
        
        for source_name, config in self.sources.items():
            if source_name == 'yfinance':
                continue  # No API key required
            
            # Count recent requests
            recent_requests = 0
            if source_name in self.last_request_times:
                minute_ago = current_time - 60
                recent_requests = len([
                    t for t in self.last_request_times[source_name] if t > minute_ago
                ])
            
            # Count daily requests
            daily_requests = 0
            if (source_name in self.daily_request_counts and 
                today in self.daily_request_counts[source_name]):
                daily_requests = self.daily_request_counts[source_name][today]
            
            status[source_name] = {
                'name': config.name,
                'requests_last_minute': recent_requests,
                'rate_limit_per_minute': config.rate_limit_per_minute,
                'requests_today': daily_requests,
                'daily_limit': config.free_tier_daily_limit,
                'api_key_configured': getattr(self, f'{source_name}_key') is not None
            }
        
        return status


def create_multi_source_service() -> MultiSourceMarketDataService:
    """
    Create a multi-source market data service with API keys from environment variables.
    
    To use this service, set these environment variables:
    - ALPHA_VANTAGE_API_KEY (get free at https://www.alphavantage.co/support/#api-key)
    - TIINGO_API_KEY (get free at https://api.tiingo.com/)
    - POLYGON_API_KEY (get free at https://polygon.io/)
    
    Returns:
        MultiSourceMarketDataService: Configured service
    """
    import os
    
    return MultiSourceMarketDataService(
        alpha_vantage_key=os.getenv('ALPHA_VANTAGE_API_KEY'),
        tiingo_key=os.getenv('TIINGO_API_KEY'),
        polygon_key=os.getenv('POLYGON_API_KEY')
    )