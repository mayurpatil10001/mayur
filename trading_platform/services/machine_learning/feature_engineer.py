"""
Feature engineering pipeline for machine learning models.

This service extracts features from historical trade data including:
- Basic trade features (P&L, duration, win/loss patterns)
- Temporal features (hour, day, week patterns)
- Rolling statistics and performance metrics
- Technical indicators (optional)

Requirements: 4.1, 4.4
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict

from ...models.trading import ProcessedTrade
from ...interfaces.ml_interfaces import IFeatureEngineer


@dataclass
class FeatureSet:
    """Container for engineered features."""
    features: pd.DataFrame
    feature_names: List[str]
    target_column: Optional[str] = None
    metadata: Dict[str, Any] = None


class FeatureEngineeringError(Exception):
    """Exception raised by feature engineering service."""
    pass


class FeatureEngineer(IFeatureEngineer):
    """
    Feature engineering pipeline for trading data.
    
    Extracts comprehensive features from processed trades for machine learning models.
    """
    
    def __init__(self, 
                 rolling_windows: List[int] = None,
                 include_technical_indicators: bool = False):
        """
        Initialize the feature engineer.
        
        Args:
            rolling_windows: List of window sizes for rolling statistics (default: [5, 10, 20])
            include_technical_indicators: Whether to include technical indicators
        """
        self.rolling_windows = rolling_windows or [5, 10, 20]
        self.include_technical_indicators = include_technical_indicators
        
    def extract_features(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """
        Extract comprehensive features from processed trades.
        
        Args:
            trades: List of processed trades
            
        Returns:
            DataFrame with engineered features
            
        Raises:
            FeatureEngineeringError: If feature extraction fails
        """
        if not trades:
            raise FeatureEngineeringError("Cannot extract features from empty trade list")
        
        try:
            # Convert trades to DataFrame for easier manipulation
            df = self._trades_to_dataframe(trades)
            
            # Extract basic trade features
            basic_features = self._extract_basic_features(df)
            
            # Extract temporal features
            temporal_features = self._extract_temporal_features(df)
            
            # Extract rolling statistics
            rolling_features = self._extract_rolling_features(df)
            
            # Extract performance metrics features
            performance_features = self._extract_performance_features(df)
            
            # Extract sequence features
            sequence_features = self._extract_sequence_features(df)
            
            # Combine all features
            all_features = pd.concat([
                basic_features,
                temporal_features,
                rolling_features,
                performance_features,
                sequence_features
            ], axis=1)
            
            # Add technical indicators if requested
            if self.include_technical_indicators:
                technical_features = self._extract_technical_indicators(df)
                all_features = pd.concat([all_features, technical_features], axis=1)
            
            # Clean up features
            all_features = self._clean_features(all_features)
            
            return all_features
            
        except Exception as e:
            raise FeatureEngineeringError(f"Failed to extract features: {e}")
    
    def create_temporal_features(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """
        Create time-based features from trades.
        
        Args:
            trades: List of processed trades
            
        Returns:
            DataFrame with temporal features
        """
        if not trades:
            raise FeatureEngineeringError("Cannot create temporal features from empty trade list")
        
        df = self._trades_to_dataframe(trades)
        return self._extract_temporal_features(df)
    
    def create_technical_indicators(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """
        Create technical indicator features.
        
        Args:
            trades: List of processed trades
            
        Returns:
            DataFrame with technical indicator features
        """
        if not trades:
            raise FeatureEngineeringError("Cannot create technical indicators from empty trade list")
        
        df = self._trades_to_dataframe(trades)
        return self._extract_technical_indicators(df)
    
    def create_feature_set(self, 
                          trades: List[ProcessedTrade],
                          target_column: str = 'profit_loss',
                          include_metadata: bool = True) -> FeatureSet:
        """
        Create a complete feature set for machine learning.
        
        Args:
            trades: List of processed trades
            target_column: Name of target column for prediction
            include_metadata: Whether to include metadata about features
            
        Returns:
            FeatureSet with features and metadata
        """
        features_df = self.extract_features(trades)
        
        # Prepare metadata
        metadata = {}
        if include_metadata:
            metadata = {
                'total_trades': len(trades),
                'feature_count': len(features_df.columns),
                'rolling_windows': self.rolling_windows,
                'includes_technical_indicators': self.include_technical_indicators,
                'extraction_timestamp': datetime.now(),
                'accounts': list(set(t.account_name for t in trades)),
                'symbols': list(set(t.symbol for t in trades)),
                'date_range': {
                    'start': min(t.entry_time for t in trades),
                    'end': max(t.exit_time for t in trades)
                }
            }
        
        return FeatureSet(
            features=features_df,
            feature_names=list(features_df.columns),
            target_column=target_column,
            metadata=metadata
        )
    
    def _trades_to_dataframe(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """Convert list of trades to DataFrame."""
        data = []
        for trade in trades:
            data.append({
                'trade_id': trade.trade_id,
                'account_name': trade.account_name,
                'symbol': trade.symbol,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'side': trade.side,
                'profit_loss': trade.profit_loss,
                'commission': trade.commission,
                'duration_minutes': trade.duration_minutes,
                'hour_of_day': trade.hour_of_day,
                'day_of_week': trade.day_of_week,
                'entry_order_id': trade.entry_order_id,
                'exit_order_id': trade.exit_order_id
            })
        
        df = pd.DataFrame(data)
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df = df.sort_values('entry_time').reset_index(drop=True)
        
        return df
    
    def _extract_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract basic trade features."""
        features = pd.DataFrame(index=df.index)
        
        # P&L features
        features['profit_loss'] = df['profit_loss']
        features['gross_pnl'] = df['profit_loss'] + df['commission']
        features['is_profitable'] = (df['profit_loss'] > 0).astype(int)
        features['pnl_magnitude'] = np.abs(df['profit_loss'])
        
        # Price features
        features['entry_price'] = df['entry_price']
        features['exit_price'] = df['exit_price']
        features['price_change'] = df['exit_price'] - df['entry_price']
        features['price_change_pct'] = (df['exit_price'] - df['entry_price']) / df['entry_price']
        
        # Trade characteristics
        features['quantity'] = df['quantity']
        features['duration_minutes'] = df['duration_minutes']
        features['duration_hours'] = df['duration_minutes'] / 60
        features['commission'] = df['commission']
        features['commission_pct'] = df['commission'] / (df['entry_price'] * df['quantity'])
        
        # Side features
        features['is_long'] = (df['side'] == 'LONG').astype(int)
        features['is_short'] = (df['side'] == 'SHORT').astype(int)
        
        # Return metrics
        features['return_pct'] = df['profit_loss'] / (df['entry_price'] * df['quantity'])
        features['return_per_minute'] = df['profit_loss'] / df['duration_minutes']
        
        return features
    
    def _extract_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract temporal features."""
        features = pd.DataFrame(index=df.index)
        
        # Basic temporal features
        features['hour_of_day'] = df['hour_of_day']
        features['day_of_week'] = df['day_of_week']
        
        # Cyclical encoding for temporal features
        features['hour_sin'] = np.sin(2 * np.pi * df['hour_of_day'] / 24)
        features['hour_cos'] = np.cos(2 * np.pi * df['hour_of_day'] / 24)
        features['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        features['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Time-based features from entry_time
        features['entry_year'] = df['entry_time'].dt.year
        features['entry_month'] = df['entry_time'].dt.month
        features['entry_day'] = df['entry_time'].dt.day
        features['entry_week_of_year'] = df['entry_time'].dt.isocalendar().week
        
        # Market session features (assuming US market hours)
        features['is_market_open'] = ((df['hour_of_day'] >= 9) & (df['hour_of_day'] < 16)).astype(int)
        features['is_pre_market'] = ((df['hour_of_day'] >= 4) & (df['hour_of_day'] < 9)).astype(int)
        features['is_after_hours'] = ((df['hour_of_day'] >= 16) | (df['hour_of_day'] < 4)).astype(int)
        
        # Weekend indicator
        features['is_weekend'] = (df['day_of_week'].isin([5, 6])).astype(int)
        features['is_weekday'] = (~df['day_of_week'].isin([5, 6])).astype(int)
        
        # Time since market open (assuming 9 AM open)
        features['minutes_since_market_open'] = np.where(
            df['hour_of_day'] >= 9,
            (df['hour_of_day'] - 9) * 60,
            0
        )
        
        return features
    
    def _extract_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract rolling statistics features."""
        features = pd.DataFrame(index=df.index)
        
        # Group by account and symbol for rolling calculations
        for account in df['account_name'].unique():
            for symbol in df['symbol'].unique():
                mask = (df['account_name'] == account) & (df['symbol'] == symbol)
                if not mask.any():
                    continue
                
                account_symbol_df = df[mask].copy()
                
                for window in self.rolling_windows:
                    prefix = f'{account}_{symbol}_rolling_{window}'
                    
                    # Rolling P&L statistics
                    rolling_pnl = account_symbol_df['profit_loss'].rolling(window=window, min_periods=1)
                    features.loc[mask, f'{prefix}_pnl_mean'] = rolling_pnl.mean()
                    features.loc[mask, f'{prefix}_pnl_std'] = rolling_pnl.std()
                    features.loc[mask, f'{prefix}_pnl_sum'] = rolling_pnl.sum()
                    features.loc[mask, f'{prefix}_pnl_max'] = rolling_pnl.max()
                    features.loc[mask, f'{prefix}_pnl_min'] = rolling_pnl.min()
                    
                    # Rolling win rate
                    rolling_wins = (account_symbol_df['profit_loss'] > 0).rolling(window=window, min_periods=1)
                    features.loc[mask, f'{prefix}_win_rate'] = rolling_wins.mean()
                    
                    # Rolling duration statistics
                    rolling_duration = account_symbol_df['duration_minutes'].rolling(window=window, min_periods=1)
                    features.loc[mask, f'{prefix}_duration_mean'] = rolling_duration.mean()
                    features.loc[mask, f'{prefix}_duration_std'] = rolling_duration.std()
                    
                    # Rolling volatility
                    features.loc[mask, f'{prefix}_volatility'] = rolling_pnl.std()
                    
                    # Rolling Sharpe ratio approximation
                    rolling_sharpe = rolling_pnl.mean() / (rolling_pnl.std() + 1e-8)
                    features.loc[mask, f'{prefix}_sharpe'] = rolling_sharpe
        
        # Fill NaN values with 0 for accounts/symbols not present
        features = features.fillna(0)
        
        return features
    
    def _extract_performance_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract performance-based features."""
        features = pd.DataFrame(index=df.index)
        
        # Cumulative features
        features['cumulative_pnl'] = df['profit_loss'].cumsum()
        features['cumulative_trades'] = range(1, len(df) + 1)
        features['cumulative_wins'] = (df['profit_loss'] > 0).cumsum()
        features['cumulative_win_rate'] = features['cumulative_wins'] / features['cumulative_trades']
        
        # Drawdown features
        cumulative_pnl = df['profit_loss'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        features['current_drawdown'] = cumulative_pnl - running_max
        features['max_drawdown_so_far'] = features['current_drawdown'].expanding().min()
        
        # Streak features
        features['win_streak'] = self._calculate_streaks(df['profit_loss'] > 0)
        features['loss_streak'] = self._calculate_streaks(df['profit_loss'] <= 0)
        
        # Recent performance (last N trades)
        for lookback in [3, 5, 10]:
            if len(df) >= lookback:
                recent_pnl = df['profit_loss'].rolling(window=lookback, min_periods=1).sum()
                recent_wins = (df['profit_loss'] > 0).rolling(window=lookback, min_periods=1).sum()
                features[f'recent_{lookback}_pnl'] = recent_pnl
                features[f'recent_{lookback}_win_rate'] = recent_wins / lookback
        
        return features
    
    def _extract_sequence_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract sequence-based features."""
        features = pd.DataFrame(index=df.index)
        
        # Lag features (previous trade characteristics)
        for lag in [1, 2, 3]:
            features[f'prev_{lag}_pnl'] = df['profit_loss'].shift(lag)
            features[f'prev_{lag}_duration'] = df['duration_minutes'].shift(lag)
            features[f'prev_{lag}_was_profitable'] = (df['profit_loss'] > 0).shift(lag).astype(float)
            features[f'prev_{lag}_side'] = (df['side'] == 'LONG').shift(lag).astype(float)
        
        # Time between trades
        features['time_since_last_trade'] = df['entry_time'].diff().dt.total_seconds() / 60  # minutes
        
        # Trade sequence position
        features['trade_number'] = range(1, len(df) + 1)
        features['trades_remaining_in_day'] = self._calculate_trades_remaining_in_day(df)
        
        # Pattern features
        features['same_side_as_prev'] = (df['side'] == df['side'].shift(1)).astype(int)
        features['opposite_side_as_prev'] = (df['side'] != df['side'].shift(1)).astype(int)
        
        # Fill NaN values
        features = features.fillna(0)
        
        return features
    
    def _extract_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract basic technical indicator features."""
        features = pd.DataFrame(index=df.index)
        
        # Price momentum indicators
        for window in [5, 10, 20]:
            # Simple moving averages of entry prices
            features[f'entry_price_sma_{window}'] = df['entry_price'].rolling(window=window).mean()
            
            # Price relative to moving average
            sma = df['entry_price'].rolling(window=window).mean()
            features[f'price_above_sma_{window}'] = (df['entry_price'] > sma).astype(int)
            features[f'price_distance_from_sma_{window}'] = (df['entry_price'] - sma) / sma
        
        # Volatility indicators
        for window in [10, 20]:
            # Rolling standard deviation of prices
            features[f'price_volatility_{window}'] = df['entry_price'].rolling(window=window).std()
            
            # Bollinger Band position
            sma = df['entry_price'].rolling(window=window).mean()
            std = df['entry_price'].rolling(window=window).std()
            features[f'bollinger_position_{window}'] = (df['entry_price'] - sma) / (2 * std)
        
        # RSI-like indicator based on P&L
        for window in [14, 21]:
            gains = df['profit_loss'].where(df['profit_loss'] > 0, 0)
            losses = -df['profit_loss'].where(df['profit_loss'] < 0, 0)
            
            avg_gain = gains.rolling(window=window).mean()
            avg_loss = losses.rolling(window=window).mean()
            
            rs = avg_gain / (avg_loss + 1e-8)
            features[f'pnl_rsi_{window}'] = 100 - (100 / (1 + rs))
        
        # Fill NaN values
        features = features.bfill().fillna(0)
        
        return features
    
    def _calculate_streaks(self, condition_series: pd.Series) -> pd.Series:
        """Calculate consecutive streaks of True values."""
        streaks = []
        current_streak = 0
        
        for value in condition_series:
            if value:
                current_streak += 1
            else:
                current_streak = 0
            streaks.append(current_streak)
        
        return pd.Series(streaks, index=condition_series.index)
    
    def _calculate_trades_remaining_in_day(self, df: pd.DataFrame) -> pd.Series:
        """Calculate number of trades remaining in the same day."""
        trades_remaining = []
        
        for i, row in df.iterrows():
            current_date = row['entry_time'].date()
            remaining = sum(1 for j in range(i + 1, len(df)) 
                          if df.iloc[j]['entry_time'].date() == current_date)
            trades_remaining.append(remaining)
        
        return pd.Series(trades_remaining, index=df.index)
    
    def _clean_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate features."""
        # Remove features with all NaN values
        features = features.dropna(axis=1, how='all')
        
        # Fill remaining NaN values with 0
        features = features.fillna(0)
        
        # Remove infinite values
        features = features.replace([np.inf, -np.inf], 0)
        
        # Remove features with zero variance, but keep important basic features
        # even if they have zero variance in small samples
        important_features = [
            'profit_loss', 'gross_pnl', 'is_profitable', 'pnl_magnitude',
            'entry_price', 'exit_price', 'price_change', 'price_change_pct',
            'quantity', 'duration_minutes', 'duration_hours', 'commission',
            'commission_pct', 'is_long', 'is_short', 'return_pct', 'return_per_minute'
        ]
        
        numeric_features = features.select_dtypes(include=[np.number])
        zero_var_cols = []
        for col in numeric_features.columns:
            if numeric_features[col].var() == 0 and col not in important_features:
                zero_var_cols.append(col)
        
        if zero_var_cols:
            features = features.drop(columns=zero_var_cols)
        
        return features
    
    def get_feature_groups(self) -> Dict[str, List[str]]:
        """
        Get feature groups for analysis and selection.
        
        Returns:
            Dictionary mapping feature group names to feature name patterns
        """
        return {
            'basic': ['profit_loss', 'gross_pnl', 'is_profitable', 'pnl_magnitude',
                     'entry_price', 'exit_price', 'price_change', 'price_change_pct',
                     'quantity', 'duration_minutes', 'duration_hours', 'commission',
                     'is_long', 'is_short', 'return_pct', 'return_per_minute'],
            
            'temporal': ['hour_of_day', 'day_of_week', 'hour_sin', 'hour_cos',
                        'day_sin', 'day_cos', 'is_market_open', 'is_pre_market',
                        'is_after_hours', 'is_weekend', 'is_weekday'],
            
            'rolling': [col for col in [] if 'rolling' in col],  # Will be populated dynamically
            
            'performance': ['cumulative_pnl', 'cumulative_trades', 'cumulative_wins',
                           'cumulative_win_rate', 'current_drawdown', 'max_drawdown_so_far',
                           'win_streak', 'loss_streak'],
            
            'sequence': ['prev_1_pnl', 'prev_2_pnl', 'prev_3_pnl', 'time_since_last_trade',
                        'trade_number', 'same_side_as_prev', 'opposite_side_as_prev'],
            
            'technical': ['entry_price_sma_5', 'entry_price_sma_10', 'entry_price_sma_20',
                         'price_volatility_10', 'price_volatility_20', 'pnl_rsi_14', 'pnl_rsi_21']
        }