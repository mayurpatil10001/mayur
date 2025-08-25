"""
Integration tests for feature engineering pipeline.

Tests the complete feature engineering workflow with real data patterns
and integration between components.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trading_platform.models.trading import ProcessedTrade
from trading_platform.services.machine_learning.feature_engineer import FeatureEngineer
from trading_platform.services.machine_learning.feature_importance_analyzer import FeatureImportanceAnalyzer


class TestFeaturePipelineIntegration:
    """Integration tests for the complete feature engineering pipeline."""
    
    @pytest.fixture
    def realistic_trades(self):
        """Create realistic trading data for integration testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        
        # Create trades with realistic patterns
        accounts = ["IPS_TM_10", "IPS_TM_13"]
        symbols = ["NQ", "FDAX"]
        
        for i in range(100):
            # Vary entry times to create realistic temporal patterns
            hour_offset = (i % 8) + 9  # Trading hours 9-16
            day_offset = i // 10  # Spread across multiple days
            
            entry_time = base_time + timedelta(days=day_offset, hours=hour_offset, minutes=i*5)
            exit_time = entry_time + timedelta(minutes=np.random.randint(15, 120))
            
            # Create realistic P&L patterns
            base_price = 15000.0 if "NQ" in symbols[i % 2] else 18000.0
            price_move = np.random.normal(0, 20)  # Random price movement
            
            # Add some temporal bias (better performance in morning)
            if entry_time.hour < 12:
                price_move += 5  # Slight morning bias
            
            entry_price = base_price + i * 2 + np.random.normal(0, 10)
            exit_price = entry_price + price_move
            
            side = "LONG" if i % 3 != 0 else "SHORT"
            if side == "SHORT":
                profit_loss = (entry_price - exit_price) * 1 - 2.5
            else:
                profit_loss = (exit_price - entry_price) * 1 - 2.5
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name=accounts[i % 2],
                symbol=symbols[i % 2],
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side=side,
                profit_loss=profit_loss,
                commission=2.5,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def feature_engineer(self):
        """Create feature engineer for integration testing."""
        return FeatureEngineer(
            rolling_windows=[5, 10, 20],
            include_technical_indicators=True
        )
    
    @pytest.fixture
    def importance_analyzer(self):
        """Create feature importance analyzer."""
        return FeatureImportanceAnalyzer(random_state=42, n_jobs=1)
    
    def test_complete_feature_pipeline(self, feature_engineer, importance_analyzer, realistic_trades):
        """Test the complete feature engineering and analysis pipeline."""
        
        # Step 1: Extract features
        feature_set = feature_engineer.create_feature_set(
            realistic_trades,
            target_column='profit_loss',
            include_metadata=True
        )
        
        # Verify feature set creation
        assert len(feature_set.features) == len(realistic_trades)
        assert feature_set.target_column == 'profit_loss'
        assert feature_set.metadata is not None
        
        # Step 2: Analyze feature importance
        features = feature_set.features
        target = features[feature_set.target_column]
        feature_matrix = features.drop(columns=[feature_set.target_column])
        
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression'
        )
        
        # Verify importance analysis
        assert analysis_report.total_features == len(feature_matrix.columns)
        assert len(analysis_report.consensus_features) > 0
        assert len(analysis_report.method_results) > 0
        
        # Step 3: Select best features
        selected_features = importance_analyzer.select_features(
            feature_matrix, target, method='consensus', max_features=20
        )
        
        # Verify feature selection
        assert len(selected_features) <= 20
        assert all(feature in feature_matrix.columns for feature in selected_features)
        
        # Step 4: Create final feature set with selected features
        final_features = feature_matrix[selected_features]
        
        # Verify final feature set
        assert len(final_features.columns) == len(selected_features)
        assert len(final_features) == len(realistic_trades)
    
    def test_temporal_feature_effectiveness(self, feature_engineer, importance_analyzer, realistic_trades):
        """Test that temporal features are effective for prediction."""
        
        # Extract features
        features = feature_engineer.extract_features(realistic_trades)
        target = features['profit_loss']
        feature_matrix = features.drop(columns=['profit_loss'])
        
        # Analyze importance
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression'
        )
        
        # Check that temporal features are among important features
        temporal_features = [f for f in analysis_report.consensus_features 
                           if any(temporal in f for temporal in ['hour', 'day', 'market'])]
        
        assert len(temporal_features) > 0, "No temporal features found in important features"
    
    def test_rolling_feature_effectiveness(self, feature_engineer, importance_analyzer, realistic_trades):
        """Test that rolling statistics features are effective."""
        
        # Extract features
        features = feature_engineer.extract_features(realistic_trades)
        target = features['profit_loss']
        feature_matrix = features.drop(columns=['profit_loss'])
        
        # Analyze importance
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression'
        )
        
        # Check that rolling features are among important features
        rolling_features = [f for f in analysis_report.consensus_features 
                          if 'rolling' in f]
        
        assert len(rolling_features) > 0, "No rolling features found in important features"
    
    def test_feature_correlation_analysis(self, feature_engineer, importance_analyzer, realistic_trades):
        """Test feature correlation analysis in the pipeline."""
        
        # Extract features
        features = feature_engineer.extract_features(realistic_trades)
        target = features['profit_loss']
        feature_matrix = features.drop(columns=['profit_loss'])
        
        # Analyze importance with correlation analysis
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression'
        )
        
        # Check correlation analysis results
        corr_analysis = analysis_report.correlation_analysis
        assert 'correlation_matrix' in corr_analysis
        assert 'high_correlation_pairs' in corr_analysis
        assert 'average_correlations' in corr_analysis
        
        # Verify correlation matrix dimensions
        assert corr_analysis['correlation_matrix'].shape == (len(feature_matrix.columns), len(feature_matrix.columns))
    
    def test_multiple_account_symbol_integration(self, feature_engineer, importance_analyzer):
        """Test integration with multiple accounts and symbols."""
        
        # Create trades for multiple accounts and symbols
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        
        accounts = ["IPS_TM_10", "IPS_TM_13", "IPS_TM_15"]
        symbols = ["NQ", "FDAX", "ES"]
        
        for i in range(60):  # 20 trades per account/symbol combination
            account = accounts[i % 3]
            symbol = symbols[i % 3]
            
            entry_time = base_time + timedelta(hours=i, minutes=i*10)
            exit_time = entry_time + timedelta(minutes=30)
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name=account,
                symbol=symbol,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=15000.0 + i*5,
                exit_price=15000.0 + i*5 + (10 if i % 2 == 0 else -5),
                quantity=1,
                side="LONG" if i % 2 == 0 else "SHORT",
                profit_loss=7.5 if i % 2 == 0 else -7.5,
                commission=2.5,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        # Test feature extraction
        features = feature_engineer.extract_features(trades)
        assert len(features) == len(trades)
        
        # Test importance analysis
        target = features['profit_loss']
        feature_matrix = features.drop(columns=['profit_loss'])
        
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression'
        )
        
        # Should handle multiple accounts/symbols without errors
        assert len(analysis_report.consensus_features) > 0
    
    def test_feature_pipeline_with_missing_data(self, feature_engineer, importance_analyzer):
        """Test pipeline robustness with missing or irregular data."""
        
        # Create trades with some irregular patterns
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        
        for i in range(50):
            # Some trades with unusual timing
            if i % 10 == 0:
                entry_time = base_time + timedelta(days=i, hours=2)  # Very early
            elif i % 7 == 0:
                entry_time = base_time + timedelta(days=i, hours=23)  # Very late
            else:
                entry_time = base_time + timedelta(days=i//5, hours=9 + i%8)
            
            exit_time = entry_time + timedelta(minutes=np.random.randint(5, 180))
            
            # Some trades with extreme values
            if i % 15 == 0:
                profit_loss = 1000.0  # Large win
            elif i % 13 == 0:
                profit_loss = -500.0  # Large loss
            else:
                profit_loss = np.random.normal(0, 20)
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=15000.0 + np.random.normal(0, 100),
                exit_price=15000.0 + np.random.normal(0, 100),
                quantity=1,
                side="LONG" if i % 2 == 0 else "SHORT",
                profit_loss=profit_loss,
                commission=2.5,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        # Pipeline should handle irregular data without errors
        features = feature_engineer.extract_features(trades)
        assert len(features) == len(trades)
        
        # Should not have NaN or infinite values
        assert not features.isnull().any().any()
        assert not np.isinf(features.values).any()
        
        # Importance analysis should still work
        target = features['profit_loss']
        feature_matrix = features.drop(columns=['profit_loss'])
        
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression'
        )
        
        assert len(analysis_report.consensus_features) > 0
    
    def test_feature_pipeline_performance(self, feature_engineer, importance_analyzer, realistic_trades):
        """Test pipeline performance with larger datasets."""
        
        # Create larger dataset
        large_trades = realistic_trades * 5  # 500 trades
        
        # Update trade IDs to avoid duplicates
        for i, trade in enumerate(large_trades):
            trade.trade_id = f"trade_{i}"
        
        # Test feature extraction performance
        import time
        start_time = time.time()
        features = feature_engineer.extract_features(large_trades)
        feature_time = time.time() - start_time
        
        # Should complete in reasonable time (less than 10 seconds)
        assert feature_time < 10.0, f"Feature extraction took too long: {feature_time:.2f}s"
        
        # Test importance analysis performance
        target = features['profit_loss']
        feature_matrix = features.drop(columns=['profit_loss'])
        
        start_time = time.time()
        analysis_report = importance_analyzer.analyze_feature_importance(
            feature_matrix, target, task_type='regression', methods=['random_forest', 'univariate']
        )
        analysis_time = time.time() - start_time
        
        # Should complete in reasonable time (less than 30 seconds)
        assert analysis_time < 30.0, f"Importance analysis took too long: {analysis_time:.2f}s"
        
        # Results should still be valid
        assert len(analysis_report.consensus_features) > 0
    
    def test_feature_consistency_across_runs(self, feature_engineer, realistic_trades):
        """Test that feature extraction is consistent across multiple runs."""
        
        # Extract features multiple times
        features1 = feature_engineer.extract_features(realistic_trades)
        features2 = feature_engineer.extract_features(realistic_trades)
        features3 = feature_engineer.extract_features(realistic_trades)
        
        # All runs should produce identical results
        pd.testing.assert_frame_equal(features1, features2)
        pd.testing.assert_frame_equal(features2, features3)
    
    def test_feature_metadata_accuracy(self, feature_engineer, realistic_trades):
        """Test that feature metadata is accurate."""
        
        feature_set = feature_engineer.create_feature_set(
            realistic_trades,
            target_column='profit_loss',
            include_metadata=True
        )
        
        metadata = feature_set.metadata
        
        # Check metadata accuracy
        assert metadata['total_trades'] == len(realistic_trades)
        assert metadata['feature_count'] == len(feature_set.features.columns)
        
        # Check accounts and symbols
        expected_accounts = set(t.account_name for t in realistic_trades)
        expected_symbols = set(t.symbol for t in realistic_trades)
        
        assert set(metadata['accounts']) == expected_accounts
        assert set(metadata['symbols']) == expected_symbols
        
        # Check date range
        expected_start = min(t.entry_time for t in realistic_trades)
        expected_end = max(t.exit_time for t in realistic_trades)
        
        assert metadata['date_range']['start'] == expected_start
        assert metadata['date_range']['end'] == expected_end


if __name__ == '__main__':
    pytest.main([__file__])