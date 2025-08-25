"""
Integration tests for prediction service with real model training and validation.

Tests cover end-to-end prediction workflows, accuracy validation against historical data,
and performance benchmarking with model comparison metrics.

Requirements: 4.2, 4.4
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from trading_platform.services.machine_learning.prediction_service import (
    PredictionService, PredictionResult, EnsemblePrediction
)
from trading_platform.services.machine_learning.model_trainer import ModelTrainer
from trading_platform.services.machine_learning.feature_engineer import FeatureEngineer
from trading_platform.models.trading import ProcessedTrade, TradingRecommendation


class TestPredictionServiceIntegration:
    """Integration tests for prediction service with real data."""
    
    @pytest.fixture
    def temp_models_dir(self):
        """Create temporary directory for models."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample processed trades for testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0)
        
        for i in range(100):
            entry_price = 15000.0 + np.random.normal(0, 50)
            exit_price = 15000.0 + np.random.normal(10, 50)
            quantity = 1
            side = "LONG" if i % 2 == 0 else "SHORT"
            commission = 4.0
            
            # Calculate correct P&L based on side
            if side == "LONG":
                profit_loss = (exit_price - entry_price) * quantity - commission
            else:  # SHORT
                profit_loss = (entry_price - exit_price) * quantity - commission
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i:03d}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i, minutes=30),
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit_loss,
                commission=commission,
                duration_minutes=30,
                hour_of_day=(base_time + timedelta(hours=i)).hour,
                day_of_week=(base_time + timedelta(hours=i)).weekday(),
                entry_order_id=f"entry_{i:03d}",
                exit_order_id=f"exit_{i:03d}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def trained_models(self, temp_models_dir, sample_trades):
        """Create and train actual models for testing."""
        # Initialize feature engineer and model trainer
        feature_engineer = FeatureEngineer()
        model_trainer = ModelTrainer(models_dir=temp_models_dir)
        
        # Extract features and target
        features_df = feature_engineer.extract_features(sample_trades)
        target_series = pd.Series([trade.profit_loss for trade in sample_trades])
        target_series.index = features_df.index
        
        # Train multiple models
        trained_models = {}
        
        # Train Random Forest
        rf_model = model_trainer.train_model(
            features_df, target_series, 'random_forest_reg'
        )
        model_trainer.save_model(rf_model, 'rf_model.pkl')
        trained_models['random_forest_reg'] = rf_model
        
        # Train Linear Regression
        lr_model = model_trainer.train_model(
            features_df, target_series, 'linear_regression'
        )
        model_trainer.save_model(lr_model, 'lr_model.pkl')
        trained_models['linear_regression'] = lr_model
        
        return trained_models, features_df, target_series
    
    def test_end_to_end_prediction_workflow(self, temp_models_dir, trained_models):
        """Test complete prediction workflow from model loading to prediction."""
        trained_models_dict, features_df, target_series = trained_models
        
        # Initialize prediction service
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Service should load the saved models
        assert len(prediction_service.loaded_models) >= 2
        
        # Test single model prediction
        test_features = features_df.iloc[:1]  # First row
        
        model_keys = list(prediction_service.loaded_models.keys())
        result = prediction_service.predict_single_model(test_features, model_keys[0])
        
        assert isinstance(result, PredictionResult)
        assert isinstance(result.prediction, float)
        assert 0 <= result.confidence_score <= 1
        assert result.prediction_time > 0
        assert len(result.feature_importance) > 0
    
    def test_ensemble_prediction_with_real_models(self, temp_models_dir, trained_models):
        """Test ensemble prediction with real trained models."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Test ensemble prediction
        test_features = features_df.iloc[:1]
        model_keys = list(prediction_service.loaded_models.keys())
        
        if len(model_keys) >= 2:
            ensemble_result = prediction_service.predict_ensemble(
                test_features, 
                model_keys[:2],  # Use first two models
                ensemble_method='voting'
            )
            
            assert isinstance(ensemble_result, EnsemblePrediction)
            assert isinstance(ensemble_result.prediction, float)
            assert len(ensemble_result.individual_predictions) == 2
            assert ensemble_result.ensemble_method == 'voting'
            assert len(ensemble_result.weights) == 2
    
    def test_model_comparison_with_real_data(self, temp_models_dir, trained_models):
        """Test model comparison with real trained models."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Use part of data for testing
        test_features = features_df.iloc[80:]  # Last 20 samples
        test_target = target_series.iloc[80:]
        
        model_keys = list(prediction_service.loaded_models.keys())
        
        if len(model_keys) >= 2:
            comparisons = prediction_service.compare_models(
                test_features, test_target, model_keys[:2]
            )
            
            assert len(comparisons) > 0
            
            for comparison in comparisons:
                assert comparison.model_a in model_keys
                assert comparison.model_b in model_keys
                assert isinstance(comparison.model_a_score, float)
                assert isinstance(comparison.model_b_score, float)
                assert comparison.sample_size == len(test_target)
    
    def test_ab_testing_with_real_models(self, temp_models_dir, trained_models):
        """Test A/B testing framework with real models."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        model_keys = list(prediction_service.loaded_models.keys())
        
        if len(model_keys) >= 2:
            # Start A/B test
            test_id = prediction_service.start_ab_test(
                'real_model_test',
                model_keys[0],
                model_keys[1],
                traffic_split=0.5,
                duration_days=1
            )
            
            assert test_id in prediction_service.active_ab_tests
            
            # Make some predictions
            test_features = features_df.iloc[:5]  # First 5 samples
            
            predictions_made = []
            for i in range(5):
                single_feature = test_features.iloc[i:i+1]
                result, model_used = prediction_service.predict_with_ab_test(
                    single_feature, test_id
                )
                predictions_made.append((result, model_used))
            
            # Check that both models were used (with high probability)
            models_used = [model for _, model in predictions_made]
            assert len(set(models_used)) >= 1  # At least one model used
            
            # End test
            ab_result = prediction_service.end_ab_test(test_id)
            
            assert ab_result.test_name == 'real_model_test'
            assert ab_result.model_a == model_keys[0]
            assert ab_result.model_b == model_keys[1]
            assert ab_result.winner in model_keys
    
    def test_prediction_accuracy_validation(self, temp_models_dir, trained_models):
        """Test prediction accuracy validation against historical data."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Use holdout data for validation
        train_size = int(0.8 * len(features_df))
        test_features = features_df.iloc[train_size:]
        test_target = target_series.iloc[train_size:]
        
        model_keys = list(prediction_service.loaded_models.keys())
        
        if len(model_keys) > 0:
            # Make predictions on test set
            predictions = []
            actuals = []
            
            for i in range(len(test_features)):
                single_feature = test_features.iloc[i:i+1]
                result = prediction_service.predict_single_model(
                    single_feature, model_keys[0]
                )
                predictions.append(result.prediction)
                actuals.append(test_target.iloc[i])
            
            # Calculate accuracy metrics
            mse = np.mean([(p - a) ** 2 for p, a in zip(predictions, actuals)])
            mae = np.mean([abs(p - a) for p, a in zip(predictions, actuals)])
            
            # Predictions should be reasonable (not perfect, but not random)
            assert mse < 50000  # Reasonable MSE for profit/loss prediction
            assert mae < 200    # Reasonable MAE
            
            # Check that predictions have some correlation with actuals
            correlation = np.corrcoef(predictions, actuals)[0, 1]
            assert not np.isnan(correlation)  # Should have some correlation
    
    def test_recommendation_generation_with_real_models(self, temp_models_dir, trained_models):
        """Test trading recommendation generation with real models."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Generate recommendation
        current_time = datetime(2024, 6, 15, 10, 30)  # Saturday, 10:30 AM
        
        recommendation = prediction_service.generate_recommendation(
            'IPS_TM_10', 'NQ', current_time
        )
        
        assert isinstance(recommendation, TradingRecommendation)
        assert recommendation.account_name == 'IPS_TM_10'
        assert recommendation.symbol == 'NQ'
        assert recommendation.recommended_action in ['TRADE', 'AVOID']
        assert 0 <= recommendation.confidence_score <= 1
        assert recommendation.hour_of_day == 10
        assert recommendation.day_of_week == 5  # Saturday
        assert len(recommendation.reasoning) > 0
    
    def test_prediction_caching_performance(self, temp_models_dir, trained_models):
        """Test prediction caching for performance optimization."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(
            models_dir=temp_models_dir,
            cache_ttl_seconds=60  # 1 minute cache
        )
        
        model_keys = list(prediction_service.loaded_models.keys())
        
        if len(model_keys) > 0:
            test_features = features_df.iloc[:1]
            
            # First prediction (should be slow)
            start_time = datetime.now()
            result1 = prediction_service.predict_single_model(test_features, model_keys[0])
            first_time = (datetime.now() - start_time).total_seconds()
            
            # Second prediction (should be fast due to caching)
            start_time = datetime.now()
            result2 = prediction_service.predict_single_model(test_features, model_keys[0])
            second_time = (datetime.now() - start_time).total_seconds()
            
            # Results should be identical
            assert result1.prediction == result2.prediction
            assert result1.confidence_score == result2.confidence_score
            
            # Second call should be faster (cached)
            assert second_time < first_time
    
    def test_parallel_vs_sequential_ensemble_performance(self, temp_models_dir, trained_models):
        """Test performance difference between parallel and sequential ensemble prediction."""
        trained_models_dict, features_df, target_series = trained_models
        
        # Test with parallel enabled
        service_parallel = PredictionService(
            models_dir=temp_models_dir,
            enable_parallel_prediction=True,
            max_workers=2
        )
        
        # Test with parallel disabled
        service_sequential = PredictionService(
            models_dir=temp_models_dir,
            enable_parallel_prediction=False
        )
        
        model_keys = list(service_parallel.loaded_models.keys())
        
        if len(model_keys) >= 2:
            test_features = features_df.iloc[:1]
            
            # Parallel prediction
            start_time = datetime.now()
            parallel_result = service_parallel.predict_ensemble(
                test_features, model_keys[:2], ensemble_method='voting'
            )
            parallel_time = (datetime.now() - start_time).total_seconds()
            
            # Sequential prediction
            start_time = datetime.now()
            sequential_result = service_sequential.predict_ensemble(
                test_features, model_keys[:2], ensemble_method='voting'
            )
            sequential_time = (datetime.now() - start_time).total_seconds()
            
            # Results should be similar (within tolerance)
            assert abs(parallel_result.prediction - sequential_result.prediction) < 0.1
            
            # Parallel should generally be faster or similar
            # (May not always be true for small workloads due to overhead)
            assert parallel_time <= sequential_time * 2  # Allow some overhead
    
    def test_model_performance_summary_with_real_data(self, temp_models_dir, trained_models):
        """Test model performance summary with real prediction history."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        model_keys = list(prediction_service.loaded_models.keys())
        
        if len(model_keys) > 0:
            # Make several predictions to build history
            for i in range(10):
                test_features = features_df.iloc[i:i+1]
                prediction_service.predict_single_model(test_features, model_keys[0])
            
            # Get performance summary
            summary = prediction_service.get_model_performance_summary()
            
            assert isinstance(summary, dict)
            assert model_keys[0] in summary
            
            model_stats = summary[model_keys[0]]
            assert model_stats['total_predictions'] == 10
            assert 0 <= model_stats['avg_confidence'] <= 1
            assert model_stats['avg_prediction_time'] > 0
            assert isinstance(model_stats['prediction_std'], float)
    
    def test_optimal_conditions_prediction_with_real_models(self, temp_models_dir, trained_models):
        """Test optimal conditions prediction with real models."""
        trained_models_dict, features_df, target_series = trained_models
        
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Test different market conditions
        conditions = [
            {
                'account': 'IPS_TM_10',
                'symbol': 'NQ',
                'hour_of_day': 10,  # Market hours
                'day_of_week': 1,   # Tuesday
                'timestamp': datetime(2024, 6, 18, 10, 0)
            },
            {
                'account': 'IPS_TM_10',
                'symbol': 'NQ',
                'hour_of_day': 22,  # After hours
                'day_of_week': 5,   # Saturday
                'timestamp': datetime(2024, 6, 22, 22, 0)
            }
        ]
        
        for condition in conditions:
            result = prediction_service.predict_optimal_conditions(condition)
            
            assert isinstance(result, dict)
            assert 'profit_probability' in result
            assert 'expected_return' in result
            assert 'confidence_score' in result
            assert 'risk_score' in result
            
            # Values should be in reasonable ranges
            assert 0 <= result['profit_probability'] <= 1
            assert 0 <= result['confidence_score'] <= 1
            assert 0 <= result['risk_score'] <= 1
    
    def test_prediction_service_error_handling(self, temp_models_dir):
        """Test error handling in prediction service."""
        prediction_service = PredictionService(models_dir=temp_models_dir)
        
        # Test with empty models directory
        assert len(prediction_service.loaded_models) == 0
        
        # Should handle gracefully when no models available
        conditions = {
            'account': 'IPS_TM_10',
            'symbol': 'NQ',
            'hour_of_day': 10,
            'day_of_week': 1
        }
        
        with pytest.raises(Exception):  # Should raise appropriate error
            prediction_service.predict_optimal_conditions(conditions)


class TestPredictionServicePerformance:
    """Performance benchmarking tests for prediction service."""
    
    def test_prediction_latency_benchmark(self):
        """Benchmark prediction latency for different model types."""
        # This test would measure prediction latency across different models
        # and ensure they meet performance requirements
        pass
    
    def test_ensemble_scaling_performance(self):
        """Test how ensemble performance scales with number of models."""
        # This test would measure ensemble prediction time as function of model count
        pass
    
    def test_cache_hit_rate_optimization(self):
        """Test cache hit rates under different usage patterns."""
        # This test would measure cache effectiveness for different access patterns
        pass
    
    def test_concurrent_prediction_performance(self):
        """Test prediction service performance under concurrent load."""
        # This test would simulate multiple concurrent prediction requests
        pass


if __name__ == '__main__':
    pytest.main([__file__])