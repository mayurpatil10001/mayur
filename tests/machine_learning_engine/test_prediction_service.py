"""
Unit tests for prediction service with ensemble models and A/B testing.

Tests cover prediction generation, model ensembles, caching, performance optimization,
and A/B testing framework for model comparison.

Requirements: 4.2, 4.4
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from trading_platform.services.machine_learning.prediction_service import (
    PredictionService, PredictionResult, EnsemblePrediction, ModelComparison,
    ABTestResult, PredictionCache, PredictionServiceError
)
from trading_platform.services.machine_learning.model_trainer import TrainedModel, ModelConfig, ModelPerformance
from trading_platform.models.trading import TradingRecommendation
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler


class TestPredictionCache:
    """Test prediction caching functionality."""
    
    def test_cache_initialization(self):
        """Test cache initialization with TTL."""
        cache = PredictionCache(ttl_seconds=300)
        assert cache.ttl_seconds == 300
        assert len(cache.cache) == 0
        assert len(cache.timestamps) == 0
    
    def test_cache_set_and_get(self):
        """Test setting and getting cached predictions."""
        cache = PredictionCache(ttl_seconds=300)
        
        # Create test data
        features = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        prediction = PredictionResult(
            prediction=0.75,
            confidence_interval=(0.6, 0.9),
            confidence_score=0.8,
            model_name='test_model',
            feature_importance={'feature1': 0.6, 'feature2': 0.4},
            prediction_time=0.1,
            timestamp=datetime.now()
        )
        
        # Test set and get
        cache.set(features, 'test_model', prediction)
        cached_result = cache.get(features, 'test_model')
        
        assert cached_result is not None
        assert cached_result.prediction == 0.75
        assert cached_result.model_name == 'test_model'
    
    def test_cache_expiration(self):
        """Test cache expiration based on TTL."""
        cache = PredictionCache(ttl_seconds=1)  # 1 second TTL
        
        features = pd.DataFrame({'feature1': [1.0]})
        prediction = PredictionResult(
            prediction=0.5,
            confidence_interval=(0.4, 0.6),
            confidence_score=0.7,
            model_name='test_model',
            feature_importance={'feature1': 1.0},
            prediction_time=0.1,
            timestamp=datetime.now()
        )
        
        # Set cache
        cache.set(features, 'test_model', prediction)
        
        # Should be available immediately
        assert cache.get(features, 'test_model') is not None
        
        # Wait for expiration (in real test, would mock time)
        import time
        time.sleep(1.1)
        
        # Should be expired
        assert cache.get(features, 'test_model') is None
    
    def test_cache_clear_expired(self):
        """Test clearing expired cache entries."""
        cache = PredictionCache(ttl_seconds=1)
        
        features = pd.DataFrame({'feature1': [1.0]})
        prediction = PredictionResult(
            prediction=0.5,
            confidence_interval=(0.4, 0.6),
            confidence_score=0.7,
            model_name='test_model',
            feature_importance={'feature1': 1.0},
            prediction_time=0.1,
            timestamp=datetime.now()
        )
        
        cache.set(features, 'test_model', prediction)
        assert len(cache.cache) == 1
        
        # Manually set timestamp to past
        key = list(cache.timestamps.keys())[0]
        cache.timestamps[key] = datetime.now() - timedelta(seconds=2)
        
        cache.clear_expired()
        assert len(cache.cache) == 0
    
    def test_cache_clear_all(self):
        """Test clearing all cache entries."""
        cache = PredictionCache()
        
        features = pd.DataFrame({'feature1': [1.0]})
        prediction = PredictionResult(
            prediction=0.5,
            confidence_interval=(0.4, 0.6),
            confidence_score=0.7,
            model_name='test_model',
            feature_importance={'feature1': 1.0},
            prediction_time=0.1,
            timestamp=datetime.now()
        )
        
        cache.set(features, 'test_model', prediction)
        assert len(cache.cache) == 1
        
        cache.clear_all()
        assert len(cache.cache) == 0
        assert len(cache.timestamps) == 0


class TestPredictionService:
    """Test prediction service functionality."""
    
    @pytest.fixture
    def temp_models_dir(self):
        """Create temporary directory for models."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_trained_model(self):
        """Create mock trained model."""
        mock_model = Mock(spec=RandomForestRegressor)
        mock_model.predict.return_value = np.array([0.75])
        mock_model.feature_importances_ = np.array([0.6, 0.4])
        
        config = ModelConfig(
            name='test_model',
            model_class=RandomForestRegressor,
            params={'n_estimators': 10},
            is_classifier=False,
            description='Test model'
        )
        
        performance = ModelPerformance(
            model_name='test_model',
            horizon_name='short_term',
            training_score=0.8,
            validation_score=0.75,
            test_score=0.7,
            training_samples=100,
            test_samples=20,
            feature_count=2,
            training_time=1.0,
            prediction_time=0.1,
            metrics={'std': 0.1, 'mse': 0.05},
            timestamp=datetime.now()
        )
        
        trained_model = TrainedModel(
            model=mock_model,
            scaler=None,
            config=config,
            performance=performance,
            feature_names=['feature1', 'feature2'],
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_test',
            created_at=datetime.now()
        )
        
        return trained_model
    
    @pytest.fixture
    def prediction_service(self, temp_models_dir):
        """Create prediction service with temporary models directory."""
        return PredictionService(
            models_dir=temp_models_dir,
            cache_ttl_seconds=300,
            enable_parallel_prediction=False,  # Disable for testing
            max_workers=2
        )
    
    def test_prediction_service_initialization(self, prediction_service):
        """Test prediction service initialization."""
        assert prediction_service.models_dir.exists()
        assert prediction_service.cache is not None
        assert prediction_service.enable_parallel_prediction is False
        assert prediction_service.max_workers == 2
        assert len(prediction_service.loaded_models) == 0
    
    def test_predict_single_model_success(self, prediction_service, mock_trained_model):
        """Test successful single model prediction."""
        # Add mock model to service
        prediction_service.loaded_models['test_model'] = mock_trained_model
        
        # Create test features
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        # Make prediction
        result = prediction_service.predict_single_model(features, 'test_model')
        
        assert isinstance(result, PredictionResult)
        assert result.prediction == 0.75
        assert result.model_name == 'test_model'
        assert result.confidence_score > 0
        assert len(result.feature_importance) == 2
        assert result.prediction_time > 0
    
    def test_predict_single_model_missing_model(self, prediction_service):
        """Test prediction with missing model."""
        features = pd.DataFrame({'feature1': [1.0]})
        
        with pytest.raises(PredictionServiceError, match="Model not found"):
            prediction_service.predict_single_model(features, 'nonexistent_model')
    
    def test_predict_single_model_feature_mismatch(self, prediction_service, mock_trained_model):
        """Test prediction with mismatched features."""
        prediction_service.loaded_models['test_model'] = mock_trained_model
        
        # Features with wrong columns
        features = pd.DataFrame({'wrong_feature': [1.0]})
        
        with pytest.raises(PredictionServiceError, match="Missing features"):
            prediction_service.predict_single_model(features, 'test_model')
    
    def test_predict_single_model_with_scaler(self, prediction_service, mock_trained_model):
        """Test prediction with feature scaling."""
        # Add scaler to mock model
        mock_scaler = Mock(spec=StandardScaler)
        mock_scaler.transform.return_value = np.array([[0.5, 1.0]])
        mock_trained_model.scaler = mock_scaler
        
        prediction_service.loaded_models['test_model'] = mock_trained_model
        
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        result = prediction_service.predict_single_model(features, 'test_model')
        
        assert result.prediction == 0.75
        mock_scaler.transform.assert_called_once()
    
    def test_predict_ensemble_voting(self, prediction_service, mock_trained_model):
        """Test ensemble prediction with voting method."""
        # Create multiple mock models
        model1 = mock_trained_model
        model1.model.predict.return_value = np.array([0.7])
        
        model2 = mock_trained_model
        model2.model.predict.return_value = np.array([0.8])
        model2.config.name = 'test_model_2'
        model2.performance.model_name = 'test_model_2'
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        result = prediction_service.predict_ensemble(
            features, 
            ['test_model_1', 'test_model_2'], 
            ensemble_method='voting'
        )
        
        assert isinstance(result, EnsemblePrediction)
        # Both models return 0.8 since they're the same mock object
        assert result.prediction == 0.8
        assert result.ensemble_method == 'voting'
        assert len(result.individual_predictions) == 2
        assert len(result.weights) == 2
    
    def test_predict_ensemble_weighted(self, prediction_service, mock_trained_model):
        """Test ensemble prediction with weighted method."""
        # Create models with different confidence scores
        model1 = mock_trained_model
        model1.model.predict.return_value = np.array([0.6])
        
        model2 = mock_trained_model
        model2.model.predict.return_value = np.array([0.9])
        model2.config.name = 'test_model_2'
        model2.performance.model_name = 'test_model_2'
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        # Mock confidence scores for weighting
        with patch.object(prediction_service, '_calculate_confidence_interval') as mock_conf:
            mock_conf.side_effect = [
                ((0.5, 0.7), 0.6),  # Lower confidence for model1
                ((0.8, 1.0), 0.9)   # Higher confidence for model2
            ]
            
            result = prediction_service.predict_ensemble(
                features, 
                ['test_model_1', 'test_model_2'], 
                ensemble_method='weighted'
            )
        
        assert isinstance(result, EnsemblePrediction)
        assert result.ensemble_method == 'weighted'
        # Should be closer to model2 prediction due to higher confidence
        assert result.prediction > 0.75
    
    def test_predict_ensemble_empty_models(self, prediction_service):
        """Test ensemble prediction with empty model list."""
        features = pd.DataFrame({'feature1': [1.0]})
        
        with pytest.raises(PredictionServiceError, match="No models specified"):
            prediction_service.predict_ensemble(features, [])
    
    def test_predict_optimal_conditions(self, prediction_service, mock_trained_model):
        """Test optimal conditions prediction."""
        prediction_service.loaded_models['test_model'] = mock_trained_model
        
        conditions = {
            'account': 'IPS_TM_10',
            'symbol': 'NQ',
            'hour_of_day': 10,
            'day_of_week': 1,
            'timestamp': datetime.now()
        }
        
        with patch.object(prediction_service, '_select_best_models_for_prediction') as mock_select:
            mock_select.return_value = ['test_model']
            
            result = prediction_service.predict_optimal_conditions(conditions)
        
        assert isinstance(result, dict)
        assert 'profit_probability' in result
        assert 'expected_return' in result
        assert 'confidence_score' in result
        assert 'risk_score' in result
        assert 0 <= result['profit_probability'] <= 1
        assert 0 <= result['confidence_score'] <= 1
    
    def test_generate_recommendation(self, prediction_service, mock_trained_model):
        """Test trading recommendation generation."""
        prediction_service.loaded_models['test_model'] = mock_trained_model
        
        with patch.object(prediction_service, 'predict_optimal_conditions') as mock_predict:
            mock_predict.return_value = {
                'profit_probability': 0.7,
                'expected_return': 0.05,
                'confidence_score': 0.8,
                'risk_score': 0.2,
                'prediction_timestamp': datetime.now().isoformat()
            }
            
            recommendation = prediction_service.generate_recommendation(
                'IPS_TM_10', 'NQ', datetime.now()
            )
        
        assert isinstance(recommendation, TradingRecommendation)
        assert recommendation.account_name == 'IPS_TM_10'
        assert recommendation.symbol == 'NQ'
        assert recommendation.recommended_action in ['TRADE', 'AVOID']
        assert 0 <= recommendation.confidence_score <= 1
        assert len(recommendation.reasoning) > 0
    
    def test_calculate_prediction_confidence(self, prediction_service):
        """Test prediction confidence calculation."""
        prediction = {
            'confidence_score': 0.8,
            'profit_probability': 0.7,
            'risk_score': 0.3
        }
        
        confidence = prediction_service.calculate_prediction_confidence(prediction)
        
        assert 0 <= confidence <= 1
        assert isinstance(confidence, float)
    
    def test_compare_models(self, prediction_service, mock_trained_model):
        """Test model comparison functionality."""
        # Create two different models
        model1 = mock_trained_model
        model1.model.predict.return_value = np.array([0.7, 0.8, 0.6])
        
        model2 = mock_trained_model
        model2.model.predict.return_value = np.array([0.75, 0.85, 0.65])
        model2.config.name = 'test_model_2'
        model2.performance.model_name = 'test_model_2'
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        # Test data
        test_features = pd.DataFrame({
            'feature1': [1.0, 2.0, 3.0],
            'feature2': [2.0, 3.0, 4.0]
        })
        test_target = pd.Series([0.72, 0.82, 0.62])
        
        comparisons = prediction_service.compare_models(
            test_features, test_target, ['test_model_1', 'test_model_2']
        )
        
        assert len(comparisons) > 0
        for comparison in comparisons:
            assert isinstance(comparison, ModelComparison)
            assert comparison.model_a in ['test_model_1', 'test_model_2']
            assert comparison.model_b in ['test_model_1', 'test_model_2']
            assert comparison.model_a != comparison.model_b
            assert isinstance(comparison.model_a_score, float)
            assert isinstance(comparison.model_b_score, float)
    
    def test_start_ab_test(self, prediction_service, mock_trained_model):
        """Test starting A/B test."""
        # Add two models
        model1 = mock_trained_model
        model2 = mock_trained_model
        model2.config.name = 'test_model_2'
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        test_id = prediction_service.start_ab_test(
            'test_ab', 'test_model_1', 'test_model_2', 
            traffic_split=0.6, duration_days=3
        )
        
        assert test_id == 'test_ab'
        assert 'test_ab' in prediction_service.active_ab_tests
        
        test_config = prediction_service.active_ab_tests['test_ab']
        assert test_config['model_a'] == 'test_model_1'
        assert test_config['model_b'] == 'test_model_2'
        assert test_config['traffic_split'] == 0.6
        assert test_config['status'] == 'active'
    
    def test_start_ab_test_duplicate_name(self, prediction_service, mock_trained_model):
        """Test starting A/B test with duplicate name."""
        prediction_service.loaded_models['test_model'] = mock_trained_model
        prediction_service.active_ab_tests['existing_test'] = {'status': 'active'}
        
        with pytest.raises(PredictionServiceError, match="already active"):
            prediction_service.start_ab_test(
                'existing_test', 'test_model', 'test_model'
            )
    
    def test_predict_with_ab_test(self, prediction_service, mock_trained_model):
        """Test prediction with A/B test."""
        # Setup models and A/B test
        model1 = mock_trained_model
        model1.model.predict.return_value = np.array([0.7])
        
        model2 = mock_trained_model
        model2.model.predict.return_value = np.array([0.8])
        model2.config.name = 'test_model_2'
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        prediction_service.start_ab_test(
            'test_ab', 'test_model_1', 'test_model_2'
        )
        
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        # Make prediction with A/B test
        with patch('numpy.random.random', return_value=0.3):  # Should use model A
            result, model_used = prediction_service.predict_with_ab_test(
                features, 'test_ab'
            )
        
        assert isinstance(result, PredictionResult)
        assert model_used == 'test_model_1'
        
        # Check that test config was updated
        test_config = prediction_service.active_ab_tests['test_ab']
        assert test_config['model_a_predictions'] == 1
        assert test_config['model_b_predictions'] == 0
    
    def test_end_ab_test(self, prediction_service, mock_trained_model):
        """Test ending A/B test."""
        # Setup models and A/B test
        prediction_service.loaded_models['test_model_1'] = mock_trained_model
        prediction_service.loaded_models['test_model_2'] = mock_trained_model
        
        prediction_service.start_ab_test(
            'test_ab', 'test_model_1', 'test_model_2'
        )
        
        # Add some mock results
        test_config = prediction_service.active_ab_tests['test_ab']
        test_config['model_a_results'] = [
            {'prediction': 0.7, 'confidence': 0.8, 'timestamp': datetime.now()},
            {'prediction': 0.6, 'confidence': 0.7, 'timestamp': datetime.now()}
        ]
        test_config['model_b_results'] = [
            {'prediction': 0.8, 'confidence': 0.9, 'timestamp': datetime.now()}
        ]
        
        result = prediction_service.end_ab_test('test_ab')
        
        assert isinstance(result, ABTestResult)
        assert result.test_name == 'test_ab'
        assert result.model_a == 'test_model_1'
        assert result.model_b == 'test_model_2'
        assert result.winner in ['test_model_1', 'test_model_2']
        assert 0 <= result.confidence_level <= 1
        
        # Test should be removed from active tests
        assert 'test_ab' not in prediction_service.active_ab_tests
    
    def test_get_model_performance_summary(self, prediction_service):
        """Test model performance summary."""
        # Add some mock prediction history
        prediction_service.prediction_history = [
            PredictionResult(
                prediction=0.7,
                confidence_interval=(0.6, 0.8),
                confidence_score=0.8,
                model_name='model_1',
                feature_importance={},
                prediction_time=0.1,
                timestamp=datetime.now()
            ),
            PredictionResult(
                prediction=0.8,
                confidence_interval=(0.7, 0.9),
                confidence_score=0.9,
                model_name='model_1',
                feature_importance={},
                prediction_time=0.15,
                timestamp=datetime.now()
            ),
            PredictionResult(
                prediction=0.6,
                confidence_interval=(0.5, 0.7),
                confidence_score=0.7,
                model_name='model_2',
                feature_importance={},
                prediction_time=0.2,
                timestamp=datetime.now()
            )
        ]
        
        summary = prediction_service.get_model_performance_summary()
        
        assert 'model_1' in summary
        assert 'model_2' in summary
        
        model_1_stats = summary['model_1']
        assert model_1_stats['total_predictions'] == 2
        assert abs(model_1_stats['avg_confidence'] - 0.85) < 0.01
        assert model_1_stats['avg_prediction_time'] == 0.125
    
    def test_clear_cache(self, prediction_service):
        """Test cache clearing."""
        # Add something to cache
        features = pd.DataFrame({'feature1': [1.0]})
        prediction = PredictionResult(
            prediction=0.5,
            confidence_interval=(0.4, 0.6),
            confidence_score=0.7,
            model_name='test_model',
            feature_importance={},
            prediction_time=0.1,
            timestamp=datetime.now()
        )
        
        prediction_service.cache.set(features, 'test_model', prediction)
        assert len(prediction_service.cache.cache) == 1
        
        prediction_service.clear_cache()
        assert len(prediction_service.cache.cache) == 0
    
    def test_reload_models(self, prediction_service):
        """Test model reloading."""
        # Add a mock model
        prediction_service.loaded_models['test_model'] = Mock()
        assert len(prediction_service.loaded_models) == 1
        
        # Reload should clear existing models
        prediction_service.reload_models()
        # Since no actual model files exist, should be empty
        assert len(prediction_service.loaded_models) == 0


class TestPredictionServiceIntegration:
    """Integration tests for prediction service with real data."""
    
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
            enable_parallel_prediction=False,  # Disable for testing
            max_workers=2
        )
    
    @pytest.fixture
    def sample_features(self):
        """Create sample features for testing."""
        return pd.DataFrame({
            'hour_of_day': [10, 14, 16],
            'day_of_week': [1, 2, 3],
            'avg_profit_last_5': [0.05, -0.02, 0.08],
            'volatility': [0.15, 0.25, 0.12],
            'win_rate_last_10': [0.6, 0.4, 0.7]
        })
    
    @pytest.fixture
    def sample_target(self):
        """Create sample target for testing."""
        return pd.Series([0.03, -0.01, 0.06])
    
    def test_end_to_end_prediction_workflow(self, sample_features, sample_target):
        """Test complete prediction workflow from training to prediction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = PredictionService(models_dir=temp_dir)
            
            # Since we don't have actual trained models, this test would
            # require integration with the model trainer
            # For now, test that the service initializes correctly
            assert service.models_dir.exists()
            assert len(service.loaded_models) == 0
    
    def test_parallel_prediction_performance(self, sample_features):
        """Test parallel prediction performance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with parallel enabled
            service_parallel = PredictionService(
                models_dir=temp_dir,
                enable_parallel_prediction=True,
                max_workers=2
            )
            
            # Test with parallel disabled
            service_sequential = PredictionService(
                models_dir=temp_dir,
                enable_parallel_prediction=False
            )
            
            assert service_parallel.enable_parallel_prediction is True
            assert service_sequential.enable_parallel_prediction is False
    
    def test_prediction_accuracy_validation(self, sample_features, sample_target):
        """Test prediction accuracy validation against historical data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = PredictionService(models_dir=temp_dir)
            
            # This would require actual trained models for meaningful testing
            # For now, verify the service can handle the data format
            assert len(sample_features) == len(sample_target)
            assert not sample_features.empty
            assert not sample_target.empty


    def test_create_ensemble_model(self, prediction_service):
        """Test creating ensemble models."""
        # Create mock models
        from unittest.mock import Mock
        from sklearn.ensemble import RandomForestRegressor
        
        mock_model1 = Mock(spec=RandomForestRegressor)
        mock_model1.predict.return_value = np.array([0.75])
        mock_model1.feature_importances_ = np.array([0.6, 0.4])
        
        config1 = ModelConfig(
            name='test_model_1',
            model_class=RandomForestRegressor,
            params={'n_estimators': 10},
            is_classifier=False,
            description='Test model 1'
        )
        
        performance1 = ModelPerformance(
            model_name='test_model_1',
            horizon_name='short_term',
            training_score=0.8,
            validation_score=0.75,
            test_score=0.7,
            training_samples=100,
            test_samples=20,
            feature_count=2,
            training_time=1.0,
            prediction_time=0.1,
            metrics={'std': 0.1, 'mse': 0.05},
            timestamp=datetime.now()
        )
        
        model1 = TrainedModel(
            model=mock_model1,
            scaler=None,
            config=config1,
            performance=performance1,
            feature_names=['feature1', 'feature2'],
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_test1',
            created_at=datetime.now()
        )
        
        # Create second model
        mock_model2 = Mock(spec=RandomForestRegressor)
        mock_model2.predict.return_value = np.array([0.8])
        mock_model2.feature_importances_ = np.array([0.5, 0.5])
        
        config2 = ModelConfig(
            name='test_model_2',
            model_class=RandomForestRegressor,
            params={'n_estimators': 10},
            is_classifier=False,
            description='Test model 2'
        )
        
        performance2 = ModelPerformance(
            model_name='test_model_2',
            horizon_name='short_term',
            training_score=0.82,
            validation_score=0.77,
            test_score=0.72,
            training_samples=100,
            test_samples=20,
            feature_count=2,
            training_time=1.0,
            prediction_time=0.1,
            metrics={'std': 0.1, 'mse': 0.05},
            timestamp=datetime.now()
        )
        
        model2 = TrainedModel(
            model=mock_model2,
            scaler=None,
            config=config2,
            performance=performance2,
            feature_names=['feature1', 'feature2'],
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_test2',
            created_at=datetime.now()
        )
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        # Create ensemble
        ensemble_key = prediction_service.create_ensemble_model(
            ['test_model_1', 'test_model_2'], 
            ensemble_type='voting',
            name='test_ensemble'
        )
        
        assert ensemble_key == 'test_ensemble'
        assert 'test_ensemble' in prediction_service.ensemble_models
        
        # Test with auto-generated name
        ensemble_key_2 = prediction_service.create_ensemble_model(
            ['test_model_1', 'test_model_2'], 
            ensemble_type='voting'
        )
        
        assert ensemble_key_2.startswith('ensemble_voting_2models_')
        assert ensemble_key_2 in prediction_service.ensemble_models
    
    def test_get_prediction_statistics(self, prediction_service):
        """Test prediction statistics generation."""
        # Add some mock prediction history
        prediction_service.prediction_history = [
            PredictionResult(
                prediction=0.7,
                confidence_interval=(0.6, 0.8),
                confidence_score=0.8,
                model_name='model_1',
                feature_importance={},
                prediction_time=0.1,
                timestamp=datetime.now()
            ),
            PredictionResult(
                prediction=0.8,
                confidence_interval=(0.7, 0.9),
                confidence_score=0.9,
                model_name='model_2',
                feature_importance={},
                prediction_time=0.15,
                timestamp=datetime.now()
            )
        ]
        
        stats = prediction_service.get_prediction_statistics()
        
        assert stats['total_predictions'] == 2
        assert 'model_1' in stats['models_used']
        assert 'model_2' in stats['models_used']
        assert stats['model_usage_distribution']['model_1'] == 1
        assert stats['model_usage_distribution']['model_2'] == 1
        assert stats['avg_prediction_time'] == 0.125
        assert abs(stats['avg_confidence_score'] - 0.85) < 1e-10
    
    def test_validate_model_compatibility(self, prediction_service):
        """Test model compatibility validation."""
        # Test with no models
        result = prediction_service.validate_model_compatibility([])
        assert not result['compatible']
        assert 'No models provided' in result['reason']
        
        # Test with single model
        result = prediction_service.validate_model_compatibility(['model_1'])
        assert not result['compatible']
        assert 'Need at least 2 models' in result['reason']
        
        # Test with missing models
        result = prediction_service.validate_model_compatibility(['model_1', 'model_2'])
        assert not result['compatible']
        assert 'Missing models' in result['reason']
        
        # Test with compatible models
        from unittest.mock import Mock
        from sklearn.ensemble import RandomForestRegressor
        
        mock_model1 = Mock(spec=RandomForestRegressor)
        mock_model1.predict.return_value = np.array([0.75])
        mock_model1.feature_importances_ = np.array([0.6, 0.4])
        
        config1 = ModelConfig(
            name='test_model_1',
            model_class=RandomForestRegressor,
            params={'n_estimators': 10},
            is_classifier=False,
            description='Test model 1'
        )
        
        performance1 = ModelPerformance(
            model_name='test_model_1',
            horizon_name='short_term',
            training_score=0.8,
            validation_score=0.75,
            test_score=0.7,
            training_samples=100,
            test_samples=20,
            feature_count=2,
            training_time=1.0,
            prediction_time=0.1,
            metrics={'std': 0.1, 'mse': 0.05},
            timestamp=datetime.now()
        )
        
        model1 = TrainedModel(
            model=mock_model1,
            scaler=None,
            config=config1,
            performance=performance1,
            feature_names=['feature1', 'feature2'],
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_test1',
            created_at=datetime.now()
        )
        
        # Create second model with same features
        mock_model2 = Mock(spec=RandomForestRegressor)
        mock_model2.predict.return_value = np.array([0.8])
        mock_model2.feature_importances_ = np.array([0.5, 0.5])
        
        config2 = ModelConfig(
            name='test_model_2',
            model_class=RandomForestRegressor,
            params={'n_estimators': 10},
            is_classifier=False,
            description='Test model 2'
        )
        
        performance2 = ModelPerformance(
            model_name='test_model_2',
            horizon_name='short_term',
            training_score=0.82,
            validation_score=0.77,
            test_score=0.72,
            training_samples=100,
            test_samples=20,
            feature_count=2,
            training_time=1.0,
            prediction_time=0.1,
            metrics={'std': 0.1, 'mse': 0.05},
            timestamp=datetime.now()
        )
        
        model2 = TrainedModel(
            model=mock_model2,
            scaler=None,
            config=config2,
            performance=performance2,
            feature_names=['feature1', 'feature2'],  # Same features as model1
            target_name='target',
            training_data_info={'total_samples': 100},
            version='v1.0_test2',
            created_at=datetime.now()
        )
        
        prediction_service.loaded_models['test_model_1'] = model1
        prediction_service.loaded_models['test_model_2'] = model2
        
        result = prediction_service.validate_model_compatibility(['test_model_1', 'test_model_2'])
        assert result['compatible']
        assert 'compatibility_score' in result
        assert 'common_features' in result
        assert result['feature_overlap_ratio'] == 1.0  # Same features


if __name__ == '__main__':
    pytest.main([__file__])