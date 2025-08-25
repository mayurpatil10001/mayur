"""
Unit tests for feature engineering pipeline.

Tests feature extraction, temporal features, rolling statistics,
and technical indicators functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trading_platform.models.trading import ProcessedTrade
from trading_platform.services.machine_learning.feature_engineer import (
    FeatureEngineer, FeatureSet, FeatureEngineeringError
)


class TestFeatureEngineer:
    """Test cases for FeatureEngineer class."""
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        
        for i in range(20):
            entry_time = base_time + timedelta(hours=i, minutes=i*5)
            exit_time = entry_time + timedelta(minutes=30 + i*2)
            
            entry_price = 15000.0 + i*10
            exit_price = entry_price + (10 if i % 2 == 0 else -5)
            side = "LONG" if i % 2 == 0 else "SHORT"
            commission = 2.5
            
            # Calculate correct P&L based on side
            if side == "LONG":
                profit_loss = (exit_price - entry_price) * 1 - commission
            else:  # SHORT
                profit_loss = (entry_price - exit_price) * 1 - commission
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side=side,
                profit_loss=profit_loss,
                commission=commission,
                duration_minutes=30 + i*2,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def feature_engineer(self):
        """Create FeatureEngineer instance."""
        return FeatureEngineer(
            rolling_windows=[3, 5],
            include_technical_indicators=True
        )
    
    def test_init(self):
        """Test FeatureEngineer initialization."""
        # Test default initialization
        fe = FeatureEngineer()
        assert fe.rolling_windows == [5, 10, 20]
        assert fe.include_technical_indicators is False
        
        # Test custom initialization
        fe = FeatureEngineer(rolling_windows=[3, 7], include_technical_indicators=True)
        assert fe.rolling_windows == [3, 7]
        assert fe.include_technical_indicators is True
    
    def test_extract_features_empty_trades(self, feature_engineer):
        """Test feature extraction with empty trade list."""
        with pytest.raises(FeatureEngineeringError, match="Cannot extract features from empty trade list"):
            feature_engineer.extract_features([])
    
    def test_extract_features_basic(self, feature_engineer, sample_trades):
        """Test basic feature extraction."""
        features = feature_engineer.extract_features(sample_trades)
        
        # Check that features DataFrame is created
        assert isinstance(features, pd.DataFrame)
        assert len(features) == len(sample_trades)
        
        # Check for basic features
        expected_basic_features = [
            'profit_loss', 'gross_pnl', 'is_profitable', 'pnl_magnitude',
            'entry_price', 'exit_price', 'price_change', 'price_change_pct',
            'quantity', 'duration_minutes', 'duration_hours', 'commission',
            'is_long', 'is_short', 'return_pct', 'return_per_minute'
        ]
        
        for feature in expected_basic_features:
            assert feature in features.columns, f"Missing basic feature: {feature}"
    
    def test_extract_temporal_features(self, feature_engineer, sample_trades):
        """Test temporal feature extraction."""
        features = feature_engineer.create_temporal_features(sample_trades)
        
        # Check temporal features
        expected_temporal_features = [
            'hour_of_day', 'day_of_week', 'hour_sin', 'hour_cos',
            'day_sin', 'day_cos', 'is_market_open', 'is_pre_market',
            'is_after_hours', 'is_weekend', 'is_weekday'
        ]
        
        for feature in expected_temporal_features:
            assert feature in features.columns, f"Missing temporal feature: {feature}"
        
        # Test cyclical encoding
        assert features['hour_sin'].between(-1, 1).all()
        assert features['hour_cos'].between(-1, 1).all()
        assert features['day_sin'].between(-1, 1).all()
        assert features['day_cos'].between(-1, 1).all()
        
        # Test market session features
        assert features['is_market_open'].isin([0, 1]).all()
        assert features['is_pre_market'].isin([0, 1]).all()
        assert features['is_after_hours'].isin([0, 1]).all()
    
    def test_extract_rolling_features(self, feature_engineer, sample_trades):
        """Test rolling statistics feature extraction."""
        features = feature_engineer.extract_features(sample_trades)
        
        # Check for rolling features
        rolling_feature_patterns = [
            'rolling_3_pnl_mean', 'rolling_3_pnl_std', 'rolling_3_win_rate',
            'rolling_5_pnl_mean', 'rolling_5_pnl_std', 'rolling_5_win_rate'
        ]
        
        # Find columns that match rolling patterns
        rolling_columns = [col for col in features.columns 
                          if any(pattern in col for pattern in rolling_feature_patterns)]
        
        assert len(rolling_columns) > 0, "No rolling features found"
        
        # Test that rolling features have reasonable values
        for col in rolling_columns:
            if 'win_rate' in col:
                assert features[col].between(0, 1).all(), f"Invalid win rate values in {col}"
    
    def test_extract_performance_features(self, feature_engineer, sample_trades):
        """Test performance feature extraction."""
        features = feature_engineer.extract_features(sample_trades)
        
        # Check performance features
        expected_performance_features = [
            'cumulative_pnl', 'cumulative_trades', 'cumulative_wins',
            'cumulative_win_rate', 'current_drawdown', 'win_streak', 'loss_streak'
        ]
        
        for feature in expected_performance_features:
            assert feature in features.columns, f"Missing performance feature: {feature}"
        
        # Test cumulative features
        assert features['cumulative_trades'].equals(pd.Series(range(1, len(sample_trades) + 1)))
        assert features['cumulative_win_rate'].between(0, 1).all()
        
        # Test drawdown is non-positive
        assert (features['current_drawdown'] <= 0).all()
    
    def test_extract_sequence_features(self, feature_engineer, sample_trades):
        """Test sequence feature extraction."""
        features = feature_engineer.extract_features(sample_trades)
        
        # Check sequence features
        expected_sequence_features = [
            'prev_1_pnl', 'prev_2_pnl', 'prev_3_pnl',
            'time_since_last_trade', 'trade_number',
            'same_side_as_prev', 'opposite_side_as_prev'
        ]
        
        for feature in expected_sequence_features:
            assert feature in features.columns, f"Missing sequence feature: {feature}"
        
        # Test lag features
        assert pd.isna(features['prev_1_pnl'].iloc[0])  # First trade has no previous
        assert features['prev_1_pnl'].iloc[1] == sample_trades[0].profit_loss
        
        # Test trade number
        assert features['trade_number'].equals(pd.Series(range(1, len(sample_trades) + 1)))
    
    def test_extract_technical_indicators(self, feature_engineer, sample_trades):
        """Test technical indicator extraction."""
        features = feature_engineer.create_technical_indicators(sample_trades)
        
        # Check technical indicator features
        expected_technical_features = [
            'entry_price_sma_5', 'entry_price_sma_10', 'entry_price_sma_20',
            'price_volatility_10', 'price_volatility_20',
            'pnl_rsi_14', 'pnl_rsi_21'
        ]
        
        for feature in expected_technical_features:
            assert feature in features.columns, f"Missing technical feature: {feature}"
        
        # Test RSI values are in valid range
        assert features['pnl_rsi_14'].between(0, 100).all()
        assert features['pnl_rsi_21'].between(0, 100).all()
    
    def test_create_feature_set(self, feature_engineer, sample_trades):
        """Test feature set creation."""
        feature_set = feature_engineer.create_feature_set(
            sample_trades,
            target_column='profit_loss',
            include_metadata=True
        )
        
        # Check feature set structure
        assert isinstance(feature_set, FeatureSet)
        assert isinstance(feature_set.features, pd.DataFrame)
        assert len(feature_set.features) == len(sample_trades)
        assert feature_set.target_column == 'profit_loss'
        
        # Check metadata
        assert feature_set.metadata is not None
        assert feature_set.metadata['total_trades'] == len(sample_trades)
        assert feature_set.metadata['feature_count'] == len(feature_set.features.columns)
        assert 'IPS_TM_10' in feature_set.metadata['accounts']
        assert 'NQ' in feature_set.metadata['symbols']
    
    def test_feature_groups(self, feature_engineer):
        """Test feature group definitions."""
        groups = feature_engineer.get_feature_groups()
        
        # Check that all expected groups exist
        expected_groups = ['basic', 'temporal', 'rolling', 'performance', 'sequence', 'technical']
        for group in expected_groups:
            assert group in groups
        
        # Check that groups contain expected features
        assert 'profit_loss' in groups['basic']
        assert 'hour_of_day' in groups['temporal']
        assert 'cumulative_pnl' in groups['performance']
    
    def test_clean_features(self, feature_engineer, sample_trades):
        """Test feature cleaning functionality."""
        # Create features with some problematic values
        features = feature_engineer.extract_features(sample_trades)
        
        # Add some NaN and infinite values for testing
        test_features = features.copy()
        test_features.loc[0, 'profit_loss'] = np.nan
        test_features.loc[1, 'entry_price'] = np.inf
        test_features.loc[2, 'exit_price'] = -np.inf
        
        # Add a zero-variance column
        test_features['zero_var'] = 1.0
        
        # Clean features
        cleaned = feature_engineer._clean_features(test_features)
        
        # Check that problematic values are handled
        assert not cleaned.isnull().any().any()
        assert not np.isinf(cleaned.values).any()
        assert 'zero_var' not in cleaned.columns
    
    def test_trades_to_dataframe(self, feature_engineer, sample_trades):
        """Test trade to DataFrame conversion."""
        df = feature_engineer._trades_to_dataframe(sample_trades)
        
        # Check DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(sample_trades)
        
        # Check that DataFrame is sorted by entry time
        assert df['entry_time'].is_monotonic_increasing
        
        # Check data types
        assert pd.api.types.is_datetime64_any_dtype(df['entry_time'])
        assert pd.api.types.is_datetime64_any_dtype(df['exit_time'])
        assert pd.api.types.is_numeric_dtype(df['profit_loss'])
    
    def test_calculate_streaks(self, feature_engineer):
        """Test streak calculation."""
        # Test win streak calculation
        condition = pd.Series([True, True, False, True, True, True, False])
        streaks = feature_engineer._calculate_streaks(condition)
        
        expected = pd.Series([1, 2, 0, 1, 2, 3, 0])
        pd.testing.assert_series_equal(streaks, expected)
    
    def test_multiple_accounts_symbols(self, feature_engineer):
        """Test feature extraction with multiple accounts and symbols."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        
        accounts = ["IPS_TM_10", "IPS_TM_13"]
        symbols = ["NQ", "FDAX"]
        
        for i in range(10):
            account = accounts[i % 2]
            symbol = symbols[i % 2]
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name=account,
                symbol=symbol,
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i, minutes=30),
                entry_price=15000.0 + i*10,
                exit_price=15000.0 + i*10 + 10,
                quantity=1,
                side="LONG",
                profit_loss=10.0,
                commission=2.5,
                duration_minutes=30,
                hour_of_day=(base_time + timedelta(hours=i)).hour,
                day_of_week=(base_time + timedelta(hours=i)).weekday(),
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        features = feature_engineer.extract_features(trades)
        
        # Check that features are created for multiple accounts/symbols
        assert len(features) == len(trades)
        
        # Check that rolling features exist for different account/symbol combinations
        rolling_columns = [col for col in features.columns if 'rolling' in col]
        assert len(rolling_columns) > 0
    
    def test_error_handling(self, feature_engineer):
        """Test error handling in feature extraction."""
        # Test with invalid trades
        invalid_trades = [None, "not_a_trade"]
        
        with pytest.raises(Exception):  # Should raise some kind of error
            feature_engineer.extract_features(invalid_trades)
    
    def test_feature_consistency(self, feature_engineer, sample_trades):
        """Test that feature extraction is consistent across runs."""
        features1 = feature_engineer.extract_features(sample_trades)
        features2 = feature_engineer.extract_features(sample_trades)
        
        # Features should be identical across runs
        pd.testing.assert_frame_equal(features1, features2)
    
    def test_feature_completeness(self, feature_engineer, sample_trades):
        """Test that all expected feature categories are present."""
        features = feature_engineer.extract_features(sample_trades)
        
        # Get feature groups
        groups = feature_engineer.get_feature_groups()
        
        # Check that features from each group are present
        for group_name, group_features in groups.items():
            if group_name == 'rolling':
                # Rolling features are dynamically named, so check for pattern
                rolling_features = [col for col in features.columns if 'rolling' in col]
                assert len(rolling_features) > 0, f"No rolling features found"
            else:
                # Check for at least some features from each group
                found_features = [f for f in group_features if f in features.columns]
                assert len(found_features) > 0, f"No features found for group: {group_name}"


class TestFeatureSet:
    """Test cases for FeatureSet class."""
    
    def test_feature_set_creation(self):
        """Test FeatureSet creation."""
        features = pd.DataFrame({'feature1': [1, 2, 3], 'feature2': [4, 5, 6]})
        feature_names = ['feature1', 'feature2']
        metadata = {'test': 'value'}
        
        feature_set = FeatureSet(
            features=features,
            feature_names=feature_names,
            target_column='target',
            metadata=metadata
        )
        
        assert feature_set.features.equals(features)
        assert feature_set.feature_names == feature_names
        assert feature_set.target_column == 'target'
        assert feature_set.metadata == metadata


if __name__ == '__main__':
    pytest.main([__file__])