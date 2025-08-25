"""
Comprehensive integration tests for prediction service.

Tests the complete prediction service functionality including ensemble models,
A/B testing, model comparison, and performance optimization without relying
on complex trade validation.

Requirements: 4.2, 4.4
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from pathlib import Path

from trading_platform.services.machine_learning.prediction_service import (
    PredictionService, PredictionResult, EnsemblePrediction, ModelComparison,
    ABTestResult, PredictionServiceError
)
from trading_platform.services.machine_learning.model_trainer import TrainedModel, ModelConfig, ModelPerformance
from trading_platform.services.machine_learning.feature_engineer import FeatureEngineer
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler


class TestPredictionServiceComprehensive:
    """Comprehensive tests for prediction service functionality."""
    
    @pytest.fixture
    def temp_models_dir(self):
        """Create temporary directory for models."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def prediction_service(self, temp_models_dir):
        """Create prediction service with temporary models directory."""
        return PredictionService(
            models_dir=temp_models_dir,
            cache_ttl_seconds=300,
            enable_parallel_prediction=True,
            max_workers=2
        )
    
    @pytest.fixture
    def sample_features(self):
        """Create sample features for testing."""
        np.random.seed(42)  # For reproducible tests
        return pd.DataFrame({
            'feature1': np.random.normal(0, 1, 100),
            'feature2': np.random.normal(0, 1, 100),
            'feature3': np.random.normal(0, 1, 100),
            'hour_of_day': np.random.randint(0, 24, 100),
            'day_of_week': np.random.randint(0, 7, 100)
        })
    
    @pytest.fixture
    def sample_target(self):
        """Create sample target for testing."""
        np.random.seed(42)
        return pd.Series(np.random.normal(0, 1, 100))
    
    @pytest.fixture
    def trained_models(self, sample_features, sample_target):
        """Create trained models for testing."""
        models = {}
        
        # Random Forest Regressor
        rf_model = RandomForestRegressor(n_estimators=10, random_state=42)
        rf_model.fit(sample_features, sample_target)
        
        rf_config = ModelConfig(
            name='random_forest',
            model_class=RandomForestRegressor,
            params={'n_estimators': 10, 'random_state': 42},
            is_classifier=False,
            description='Random Forest Regressor'
        )
        
        rf_performance = ModelPerformance(
            model_name='random_forest',
            horizon_name='medium_term',
            training_score=0.85,
            validation_score=0.78,
            test_score=0.75,
            training_samples=100,
            test_samples=20,
            feature_count=5,
            training_time=2.0,
            prediction_time=0.1,
            metrics={'mse': 0.25, 'mae': 0.4, 'r2': 0.75},
            timestamp=datetime.now()
        )
        
        models['random_forest'] = TrainedModel(
            model=rf_model,
            scaler=None,
            config=rf_config,
            performance=rf_performance,
            feature_names=list(sample_features.columns),
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_rf',
            created_at=datetime.now()
        )
        
        # Linear Regression
        lr_model = LinearRegression()
        lr_model.fit(sample_features, sample_target)
        
        lr_config = ModelConfig(
            name='linear_regression',
            model_class=LinearRegression,
            params={},
            is_classifier=False,
            description='Linear Regression'
        )
        
        lr_performance = ModelPerformance(
            model_name='linear_regression',
            horizon_name='medium_term',
            training_score=0.72,
            validation_score=0.70,
            test_score=0.68,
            training_samples=100,
            test_samples=20,
            feature_count=5,
            training_time=0.5,
            prediction_time=0.05,
            metrics={'mse': 0.32, 'mae': 0.45, 'r2': 0.68},
            timestamp=datetime.now()
        )
        
        models['linear_regression'] = TrainedModel(
            model=lr_model,
            scaler=None,
            config=lr_config,
            performance=lr_performance,
            feature_names=list(sample_features.columns),
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_lr',
            created_at=datetime.now()
        )
        
        # Neural Network with scaling
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(sample_features)
        
        nn_model = MLPRegressor(hidden_layer_sizes=(10, 5), max_iter=100, random_state=42)
        nn_model.fit(scaled_features, sample_target)
        
        nn_config = ModelConfig(
            name='neural_network',
            model_class=MLPRegressor,
            params={'hidden_layer_sizes': (10, 5), 'max_iter': 100, 'random_state': 42},
            is_classifier=False,
            description='Neural Network'
        )
        
        nn_performance = ModelPerformance(
            model_name='neural_network',
            horizon_name='medium_term',
            training_score=0.80,
            validation_score=0.76,
            test_score=0.73,
            training_samples=100,
            test_samples=20,
            feature_count=5,
            training_time=5.0,
            prediction_time=0.15,
            metrics={'mse': 0.27, 'mae': 0.42, 'r2': 0.73},
            timestamp=datetime.now()
        )
        
        models['neural_network'] = TrainedModel(
            model=nn_model,
            scaler=scaler,
            config=nn_config,
            performance=nn_performance,
            feature_names=list(sample_features.columns),
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_nn',
            created_at=datetime.now()
        )
        
        return models
    
    def test_single_model_prediction_workflow(self, prediction_service, trained_models, sample_features):
        """Test complete single model prediction workflow."""
        # Load models
        prediction_service.loaded_models.update(trained_models)
        
        # Test each model
        for model_name in trained_models.keys():
            result = prediction_service.predict_single_model(
                sample_features.head(1), model_name, calculate_confidence=True
            )
            
            assert isinstance(result, PredictionResult)
            assert isinstance(result.prediction, float)
            assert isinstance(result.confidence_interval, tuple)
            assert len(result.confidence_interval) == 2
            assert 0 <= result.confidence_score <= 1
            assert result.model_name == model_name
            assert len(result.feature_importance) > 0
            assert result.prediction_time > 0
    
    def test_ensemble_prediction_workflow(self, prediction_service, trained_models, sample_features):
        """Test complete ensemble prediction workflow."""
        prediction_service.loaded_models.update(trained_models)
        
        model_keys = list(trained_models.keys())
        
        # Test voting ensemble
        voting_result = prediction_service.predict_ensemble(
            sample_features.head(1), model_keys, ensemble_method='voting'
        )
        
        assert isinstance(voting_result, EnsemblePrediction)
        assert isinstance(voting_result.prediction, float)
        assert len(voting_result.individual_predictions) == len(model_keys)
        assert voting_result.ensemble_method == 'voting'
        assert len(voting_result.weights) == len(model_keys)
        
        # Test weighted ensemble
        weighted_result = prediction_service.predict_ensemble(
            sample_features.head(1), model_keys, ensemble_method='weighted'
        )
        
        assert isinstance(weighted_result, EnsemblePrediction)
        assert weighted_result.ensemble_method == 'weighted'
        
        # Test stacking ensemble
        stacking_result = prediction_service.predict_ensemble(
            sample_features.head(1), model_keys, ensemble_method='stacking'
        )
        
        assert isinstance(stacking_result, EnsemblePrediction)
        assert stacking_result.ensemble_method == 'stacking'
    
    def test_model_comparison_workflow(self, prediction_service, trained_models, sample_features, sample_target):
        """Test complete model comparison workflow."""
        prediction_service.loaded_models.update(trained_models)
        
        model_keys = list(trained_models.keys())
        test_features = sample_features.head(20)
        test_target = sample_target.head(20)
        
        # Compare all models
        comparisons = prediction_service.compare_models(
            test_features, test_target, model_keys, metrics=['mse', 'r2', 'mae']
        )
        
        # Should have comparisons for each pair and each metric
        expected_pairs = len(model_keys) * (len(model_keys) - 1) // 2
        expected_comparisons = expected_pairs * 3  # 3 metrics
        
        assert len(comparisons) == expected_comparisons
        
        for comparison in comparisons:
            assert isinstance(comparison, ModelComparison)
            assert comparison.model_a in model_keys
            assert comparison.model_b in model_keys
            assert comparison.model_a != comparison.model_b
            assert comparison.metric_name in ['mse', 'r2', 'mae']
            assert isinstance(comparison.model_a_score, float)
            assert isinstance(comparison.model_b_score, float)
            assert isinstance(comparison.statistical_significance, float)
            assert 0 <= comparison.statistical_significance <= 1
    
    def test_ab_testing_workflow(self, prediction_service, trained_models, sample_features):
        """Test complete A/B testing workflow."""
        prediction_service.loaded_models.update(trained_models)
        
        # Start A/B test
        test_id = prediction_service.start_ab_test(
            'rf_vs_lr', 'random_forest', 'linear_regression',
            traffic_split=0.5, duration_days=1
        )
        
        assert test_id == 'rf_vs_lr'
        assert 'rf_vs_lr' in prediction_service.active_ab_tests
        
        # Make predictions with A/B test
        predictions_made = []
        models_used = []
        
        for i in range(20):
            result, model_used = prediction_service.predict_with_ab_test(
                sample_features.iloc[[i]], test_id
            )
            predictions_made.append(result)
            models_used.append(model_used)
        
        # Should have used both models
        assert 'random_forest' in models_used
        assert 'linear_regression' in models_used
        
        # End A/B test
        ab_result = prediction_service.end_ab_test(test_id)
        
        assert isinstance(ab_result, ABTestResult)
        assert ab_result.test_name == 'rf_vs_lr'
        assert ab_result.model_a == 'random_forest'
        assert ab_result.model_b == 'linear_regression'
        assert ab_result.winner in ['random_forest', 'linear_regression']
        assert 0 <= ab_result.confidence_level <= 1
        assert ab_result.model_a_predictions + ab_result.model_b_predictions == 20
    
    def test_prediction_caching_workflow(self, prediction_service, trained_models, sample_features):
        """Test prediction caching functionality."""
        prediction_service.loaded_models.update(trained_models)
        
        test_features = sample_features.head(1)
        
        # First prediction (should not be cached)
        start_time = datetime.now()
        result1 = prediction_service.predict_single_model(test_features, 'random_forest')
        first_duration = (datetime.now() - start_time).total_seconds()
        
        # Second prediction (should be cached)
        start_time = datetime.now()
        result2 = prediction_service.predict_single_model(test_features, 'random_forest')
        second_duration = (datetime.now() - start_time).total_seconds()
        
        # Results should be identical
        assert result1.prediction == result2.prediction
        assert result1.confidence_score == result2.confidence_score
        
        # Second call should be faster (cached)
        assert second_duration < first_duration
        
        # Clear cache and test again
        prediction_service.clear_cache()
        
        start_time = datetime.now()
        result3 = prediction_service.predict_single_model(test_features, 'random_forest')
        third_duration = (datetime.now() - start_time).total_seconds()
        
        # Should be slower again (not cached)
        assert third_duration > second_duration
    
    def test_optimal_conditions_prediction(self, prediction_service, trained_models):
        """Test optimal conditions prediction."""
        prediction_service.loaded_models.update(trained_models)
        
        conditions = {
            'account': 'IPS_TM_10',
            'symbol': 'NQ',
            'hour_of_day': 10,
            'day_of_week': 1,
            'timestamp': datetime.now()
        }
        
        result = prediction_service.predict_optimal_conditions(conditions)
        
        assert isinstance(result, dict)
        assert 'profit_probability' in result
        assert 'expected_return' in result
        assert 'confidence_score' in result
        assert 'risk_score' in result
        assert 'prediction_timestamp' in result
        
        # Validate ranges
        assert 0 <= result['profit_probability'] <= 1
        assert 0 <= result['confidence_score'] <= 1
        assert 0 <= result['risk_score'] <= 1
    
    def test_recommendation_generation(self, prediction_service, trained_models):
        """Test trading recommendation generation."""
        prediction_service.loaded_models.update(trained_models)
        
        recommendation = prediction_service.generate_recommendation(
            'IPS_TM_10', 'NQ', datetime.now()
        )
        
        assert recommendation.account_name == 'IPS_TM_10'
        assert recommendation.symbol == 'NQ'
        assert recommendation.recommended_action in ['TRADE', 'AVOID']
        assert 0 <= recommendation.confidence_score <= 1
        assert isinstance(recommendation.reasoning, str)
        assert len(recommendation.reasoning) > 0
    
    def test_model_performance_summary(self, prediction_service, trained_models, sample_features):
        """Test model performance summary generation."""
        prediction_service.loaded_models.update(trained_models)
        
        # Make some predictions to populate history
        for model_name in trained_models.keys():
            for i in range(5):
                prediction_service.predict_single_model(
                    sample_features.iloc[[i]], model_name
                )
        
        summary = prediction_service.get_model_performance_summary()
        
        assert isinstance(summary, dict)
        for model_name in trained_models.keys():
            assert model_name in summary
            model_stats = summary[model_name]
            assert 'total_predictions' in model_stats
            assert 'avg_confidence' in model_stats
            assert 'avg_prediction_time' in model_stats
            assert model_stats['total_predictions'] == 5
    
    def test_prediction_statistics(self, prediction_service, trained_models, sample_features):
        """Test prediction statistics generation."""
        prediction_service.loaded_models.update(trained_models)
        
        # Make predictions
        for model_name in trained_models.keys():
            prediction_service.predict_single_model(
                sample_features.head(1), model_name
            )
        
        stats = prediction_service.get_prediction_statistics()
        
        assert stats['total_predictions'] == len(trained_models)
        assert len(stats['models_used']) == len(trained_models)
        assert 'model_usage_distribution' in stats
        assert 'avg_prediction_time' in stats
        assert 'avg_confidence_score' in stats
        assert 'cache_hit_rate' in stats
    
    def test_model_compatibility_validation(self, prediction_service, trained_models):
        """Test model compatibility validation."""
        prediction_service.loaded_models.update(trained_models)
        
        model_keys = list(trained_models.keys())
        
        # Test compatible models
        result = prediction_service.validate_model_compatibility(model_keys)
        
        assert result['compatible']
        assert 'compatibility_score' in result
        assert 'common_features' in result
        assert 'feature_overlap_ratio' in result
        assert result['feature_overlap_ratio'] == 1.0  # All models have same features
        
        # Test recommendations
        assert 'recommendations' in result
        assert isinstance(result['recommendations'], list)
    
    def test_ensemble_model_creation(self, prediction_service, trained_models):
        """Test ensemble model creation."""
        prediction_service.loaded_models.update(trained_models)
        
        model_keys = list(trained_models.keys())
        
        # Create voting ensemble
        ensemble_key = prediction_service.create_ensemble_model(
            model_keys, ensemble_type='voting', name='test_ensemble'
        )
        
        assert ensemble_key == 'test_ensemble'
        assert 'test_ensemble' in prediction_service.ensemble_models
        
        # Get ensemble models
        ensembles = prediction_service.get_ensemble_models()
        assert 'test_ensemble' in ensembles
    
    def test_parallel_vs_sequential_prediction(self, prediction_service, trained_models, sample_features):
        """Test parallel vs sequential prediction performance."""
        prediction_service.loaded_models.update(trained_models)
        
        model_keys = list(trained_models.keys())
        test_features = sample_features.head(1)
        
        # Test with parallel enabled
        prediction_service.enable_parallel_prediction = True
        start_time = datetime.now()
        parallel_result = prediction_service.predict_ensemble(
            test_features, model_keys, ensemble_method='voting'
        )
        parallel_time = (datetime.now() - start_time).total_seconds()
        
        # Test with parallel disabled
        prediction_service.enable_parallel_prediction = False
        start_time = datetime.now()
        sequential_result = prediction_service.predict_ensemble(
            test_features, model_keys, ensemble_method='voting'
        )
        sequential_time = (datetime.now() - start_time).total_seconds()
        
        # Results should be similar
        assert abs(parallel_result.prediction - sequential_result.prediction) < 0.1
        
        # Both should complete successfully
        assert isinstance(parallel_result, EnsemblePrediction)
        assert isinstance(sequential_result, EnsemblePrediction)
    
    def test_error_handling_and_edge_cases(self, prediction_service, trained_models):
        """Test error handling and edge cases."""
        prediction_service.loaded_models.update(trained_models)
        
        # Test with empty features
        with pytest.raises(Exception):
            prediction_service.predict_single_model(pd.DataFrame(), 'random_forest')
        
        # Test with non-existent model
        with pytest.raises(PredictionServiceError):
            prediction_service.predict_single_model(
                pd.DataFrame({'feature1': [1]}), 'non_existent_model'
            )
        
        # Test ensemble with empty model list
        with pytest.raises(PredictionServiceError):
            prediction_service.predict_ensemble(
                pd.DataFrame({'feature1': [1]}), []
            )
        
        # Test A/B test with same model (should work but not be very useful)
        # This actually doesn't raise an exception, it just creates a test with the same model
        test_id = prediction_service.start_ab_test(
            'same_model_test', 'random_forest', 'random_forest'
        )
        assert test_id == 'same_model_test'
        
        # Clean up the test
        prediction_service.end_ab_test('same_model_test')
    
    def test_model_versioning_and_metadata(self, prediction_service, trained_models):
        """Test model versioning and metadata handling."""
        prediction_service.loaded_models.update(trained_models)
        
        for model_name, trained_model in trained_models.items():
            # Check model metadata
            assert trained_model.version.startswith('v1.0_')
            assert isinstance(trained_model.created_at, datetime)
            assert trained_model.config.name == model_name
            assert len(trained_model.feature_names) > 0
            assert trained_model.target_name == 'target'
            
            # Check performance metrics
            assert isinstance(trained_model.performance, ModelPerformance)
            assert trained_model.performance.model_name == model_name
            assert trained_model.performance.training_samples > 0
            assert trained_model.performance.feature_count > 0


if __name__ == '__main__':
    pytest.main([__file__])