"""
Unit tests for model comparison framework and A/B testing.

Tests cover model performance comparison, statistical significance testing,
and comprehensive A/B testing framework for model evaluation.

Requirements: 4.2, 4.4
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trading_platform.services.machine_learning.prediction_service import (
    PredictionService, ModelComparison, ABTestResult, PredictionServiceError
)
from trading_platform.services.machine_learning.model_trainer import TrainedModel, ModelConfig, ModelPerformance
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor


class TestModelComparison:
    """Test model comparison functionality."""
    
    @pytest.fixture
    def prediction_service(self):
        """Create prediction service for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield PredictionService(models_dir=temp_dir)
    
    @pytest.fixture
    def mock_models(self):
        """Create mock models with different performance characteristics."""
        models = {}
        
        # Random Forest model
        rf_model = Mock(spec=RandomForestRegressor)
        rf_model.predict.return_value = np.array([0.7, 0.8, 0.6, 0.9, 0.5])
        rf_model.feature_importances_ = np.array([0.4, 0.3, 0.3])
        
        rf_config = ModelConfig(
            name='random_forest',
            model_class=RandomForestRegressor,
            params={'n_estimators': 100},
            is_classifier=False,
            description='Random Forest Regressor'
        )
        
        rf_performance = ModelPerformance(
            model_name='random_forest',
            horizon_name='medium_term',
            training_score=0.85,
            validation_score=0.78,
            test_score=0.75,
            training_samples=1000,
            test_samples=200,
            feature_count=3,
            training_time=5.0,
            prediction_time=0.1,
            metrics={'mse': 0.05, 'mae': 0.15, 'r2': 0.75, 'std': 0.12},
            timestamp=datetime.now()
        )
        
        models['random_forest'] = TrainedModel(
            model=rf_model,
            scaler=None,
            config=rf_config,
            performance=rf_performance,
            feature_names=['feature1', 'feature2', 'feature3'],
            target_name='profit_loss',
            training_data_info={'total_samples': 1000},
            version='v1.0_rf',
            created_at=datetime.now()
        )
        
        # Linear Regression model
        lr_model = Mock(spec=LinearRegression)
        lr_model.predict.return_value = np.array([0.65, 0.75, 0.55, 0.85, 0.45])
        lr_model.coef_ = np.array([0.5, 0.3, 0.2])
        
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
            training_samples=1000,
            test_samples=200,
            feature_count=3,
            training_time=1.0,
            prediction_time=0.05,
            metrics={'mse': 0.08, 'mae': 0.20, 'r2': 0.68, 'std': 0.15},
            timestamp=datetime.now()
        )
        
        models['linear_regression'] = TrainedModel(
            model=lr_model,
            scaler=None,
            config=lr_config,
            performance=lr_performance,
            feature_names=['feature1', 'feature2', 'feature3'],
            target_name='profit_loss',
            training_data_info={'total_samples': 1000},
            version='v1.0_lr',
            created_at=datetime.now()
        )
        
        # Neural Network model
        nn_model = Mock(spec=MLPRegressor)
        nn_model.predict.return_value = np.array([0.72, 0.82, 0.62, 0.88, 0.52])
        
        nn_config = ModelConfig(
            name='neural_network',
            model_class=MLPRegressor,
            params={'hidden_layer_sizes': (100, 50)},
            is_classifier=False,
            description='Neural Network'
        )
        
        nn_performance = ModelPerformance(
            model_name='neural_network',
            horizon_name='medium_term',
            training_score=0.88,
            validation_score=0.76,
            test_score=0.73,
            training_samples=1000,
            test_samples=200,
            feature_count=3,
            training_time=15.0,
            prediction_time=0.2,
            metrics={'mse': 0.06, 'mae': 0.18, 'r2': 0.73, 'std': 0.13},
            timestamp=datetime.now()
        )
        
        models['neural_network'] = TrainedModel(
            model=nn_model,
            scaler=None,
            config=nn_config,
            performance=nn_performance,
            feature_names=['feature1', 'feature2', 'feature3'],
            target_name='profit_loss',
            training_data_info={'total_samples': 1000},
            version='v1.0_nn',
            created_at=datetime.now()
        )
        
        return models
    
    @pytest.fixture
    def test_data(self):
        """Create test data for model comparison."""
        features = pd.DataFrame({
            'feature1': [1.0, 2.0, 3.0, 4.0, 5.0],
            'feature2': [0.5, 1.5, 2.5, 3.5, 4.5],
            'feature3': [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        
        target = pd.Series([0.68, 0.78, 0.58, 0.88, 0.48])
        
        return features, target
    
    def test_compare_two_models(self, prediction_service, mock_models, test_data):
        """Test comparison between two models."""
        # Load models into service
        prediction_service.loaded_models.update(mock_models)
        
        features, target = test_data
        
        # Compare Random Forest vs Linear Regression
        comparisons = prediction_service.compare_models(
            features, target, 
            ['random_forest', 'linear_regression'],
            metrics=['mse', 'r2', 'accuracy']
        )
        
        assert len(comparisons) == 3  # 3 metrics for 1 pair
        
        for comparison in comparisons:
            assert isinstance(comparison, ModelComparison)
            assert comparison.model_a == 'random_forest'
            assert comparison.model_b == 'linear_regression'
            assert comparison.metric_name in ['mse', 'r2', 'accuracy']
            assert isinstance(comparison.model_a_score, float)
            assert isinstance(comparison.model_b_score, float)
            assert isinstance(comparison.difference, float)
            assert 0 <= comparison.statistical_significance <= 1
            assert comparison.sample_size == len(target)
    
    def test_compare_multiple_models(self, prediction_service, mock_models, test_data):
        """Test comparison among multiple models."""
        prediction_service.loaded_models.update(mock_models)
        
        features, target = test_data
        
        # Compare all three models
        comparisons = prediction_service.compare_models(
            features, target,
            ['random_forest', 'linear_regression', 'neural_network'],
            metrics=['r2']
        )
        
        # Should have 3 pairs: RF-LR, RF-NN, LR-NN
        assert len(comparisons) == 3
        
        model_pairs = [(c.model_a, c.model_b) for c in comparisons]
        expected_pairs = [
            ('random_forest', 'linear_regression'),
            ('random_forest', 'neural_network'),
            ('linear_regression', 'neural_network')
        ]
        
        for pair in expected_pairs:
            assert pair in model_pairs
    
    def test_compare_models_with_missing_model(self, prediction_service, mock_models, test_data):
        """Test comparison with missing model."""
        prediction_service.loaded_models.update(mock_models)
        
        features, target = test_data
        
        # Try to compare with non-existent model
        comparisons = prediction_service.compare_models(
            features, target,
            ['random_forest', 'nonexistent_model'],
            metrics=['r2']
        )
        
        # Should return empty list since one model doesn't exist
        assert len(comparisons) == 0
    
    def test_model_comparison_metrics_calculation(self, prediction_service):
        """Test individual metric calculations."""
        # Test MSE calculation
        actual = pd.Series([1.0, 2.0, 3.0])
        predicted = 2.0
        
        mse = prediction_service._calculate_metric(actual, predicted, 'mse')
        expected_mse = np.mean([(1.0-2.0)**2, (2.0-2.0)**2, (3.0-2.0)**2])
        assert abs(mse - expected_mse) < 1e-6
        
        # Test R2 calculation
        r2 = prediction_service._calculate_metric(actual, predicted, 'r2')
        assert isinstance(r2, float)
        
        # Test accuracy calculation (threshold-based for regression)
        accuracy = prediction_service._calculate_metric(actual, predicted, 'accuracy')
        assert 0 <= accuracy <= 1
    
    def test_statistical_significance_calculation(self, prediction_service):
        """Test statistical significance calculation."""
        actual = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        pred_a = 3.0
        pred_b = 3.1
        
        significance = prediction_service._calculate_statistical_significance(
            actual, pred_a, pred_b, 'mse'
        )
        
        assert 0 <= significance <= 1
        assert isinstance(significance, float)
    
    def test_model_comparison_history_storage(self, prediction_service, mock_models, test_data):
        """Test that comparison results are stored in history."""
        prediction_service.loaded_models.update(mock_models)
        
        features, target = test_data
        
        initial_history_length = len(prediction_service.comparison_history)
        
        comparisons = prediction_service.compare_models(
            features, target,
            ['random_forest', 'linear_regression'],
            metrics=['r2']
        )
        
        # History should be updated
        assert len(prediction_service.comparison_history) == initial_history_length + len(comparisons)
        
        # Check that stored comparisons match returned ones
        stored_comparisons = prediction_service.comparison_history[-len(comparisons):]
        for stored, returned in zip(stored_comparisons, comparisons):
            assert stored.model_a == returned.model_a
            assert stored.model_b == returned.model_b
            assert stored.metric_name == returned.metric_name


class TestABTesting:
    """Test A/B testing framework."""
    
    @pytest.fixture
    def prediction_service(self):
        """Create prediction service for A/B testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield PredictionService(models_dir=temp_dir)
    
    @pytest.fixture
    def mock_models_for_ab_test(self):
        """Create mock models for A/B testing."""
        models = {}
        
        # Model A - Higher accuracy, slower
        model_a = Mock(spec=RandomForestRegressor)
        model_a.predict.return_value = np.array([0.8])
        model_a.feature_importances_ = np.array([0.5, 0.5])
        
        config_a = ModelConfig(
            name='model_a',
            model_class=RandomForestRegressor,
            params={'n_estimators': 100},
            is_classifier=False,
            description='Model A'
        )
        
        performance_a = ModelPerformance(
            model_name='model_a',
            horizon_name='short_term',
            training_score=0.85,
            validation_score=0.82,
            test_score=0.80,
            training_samples=500,
            test_samples=100,
            feature_count=2,
            training_time=10.0,
            prediction_time=0.2,
            metrics={'accuracy': 0.80, 'std': 0.1},
            timestamp=datetime.now()
        )
        
        models['model_a'] = TrainedModel(
            model=model_a,
            scaler=None,
            config=config_a,
            performance=performance_a,
            feature_names=['feature1', 'feature2'],
            target_name='target',
            training_data_info={'total_samples': 500},
            version='v1.0_a',
            created_at=datetime.now()
        )
        
        # Model B - Lower accuracy, faster
        model_b = Mock(spec=LinearRegression)
        model_b.predict.return_value = np.array([0.7])
        model_b.coef_ = np.array([0.6, 0.4])
        
        config_b = ModelConfig(
            name='model_b',
            model_class=LinearRegression,
            params={},
            is_classifier=False,
            description='Model B'
        )
        
        performance_b = ModelPerformance(
            model_name='model_b',
            horizon_name='short_term',
            training_score=0.75,
            validation_score=0.72,
            test_score=0.70,
            training_samples=500,
            test_samples=100,
            feature_count=2,
            training_time=2.0,
            prediction_time=0.05,
            metrics={'accuracy': 0.70, 'std': 0.12},
            timestamp=datetime.now()
        )
        
        models['model_b'] = TrainedModel(
            model=model_b,
            scaler=None,
            config=config_b,
            performance=performance_b,
            feature_names=['feature1', 'feature2'],
            target_name='target',
            training_data_info={'total_samples': 500},
            version='v1.0_b',
            created_at=datetime.now()
        )
        
        return models
    
    def test_start_ab_test_success(self, prediction_service, mock_models_for_ab_test):
        """Test successful A/B test initialization."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        test_id = prediction_service.start_ab_test(
            test_name='accuracy_vs_speed',
            model_a='model_a',
            model_b='model_b',
            traffic_split=0.6,
            duration_days=5
        )
        
        assert test_id == 'accuracy_vs_speed'
        assert 'accuracy_vs_speed' in prediction_service.active_ab_tests
        
        test_config = prediction_service.active_ab_tests['accuracy_vs_speed']
        assert test_config['model_a'] == 'model_a'
        assert test_config['model_b'] == 'model_b'
        assert test_config['traffic_split'] == 0.6
        assert test_config['status'] == 'active'
        assert test_config['model_a_predictions'] == 0
        assert test_config['model_b_predictions'] == 0
        assert len(test_config['model_a_results']) == 0
        assert len(test_config['model_b_results']) == 0
        
        # Check dates
        assert isinstance(test_config['start_date'], datetime)
        assert isinstance(test_config['end_date'], datetime)
        assert test_config['end_date'] > test_config['start_date']
    
    def test_start_ab_test_duplicate_name(self, prediction_service, mock_models_for_ab_test):
        """Test starting A/B test with duplicate name."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        # Start first test
        prediction_service.start_ab_test('test_name', 'model_a', 'model_b')
        
        # Try to start another with same name
        with pytest.raises(PredictionServiceError, match="already active"):
            prediction_service.start_ab_test('test_name', 'model_a', 'model_b')
    
    def test_start_ab_test_missing_models(self, prediction_service):
        """Test starting A/B test with missing models."""
        with pytest.raises(PredictionServiceError, match="must be loaded"):
            prediction_service.start_ab_test('test', 'missing_a', 'missing_b')
    
    def test_predict_with_ab_test_model_a(self, prediction_service, mock_models_for_ab_test):
        """Test prediction with A/B test selecting model A."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        prediction_service.start_ab_test('test_ab', 'model_a', 'model_b', traffic_split=0.7)
        
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        # Mock random to select model A
        with patch('numpy.random.random', return_value=0.5):  # < 0.7, so model A
            result, model_used = prediction_service.predict_with_ab_test(features, 'test_ab')
        
        assert model_used == 'model_a'
        assert result.prediction == 0.8  # Model A prediction
        
        # Check test config updated
        test_config = prediction_service.active_ab_tests['test_ab']
        assert test_config['model_a_predictions'] == 1
        assert test_config['model_b_predictions'] == 0
        assert len(test_config['model_a_results']) == 1
        assert len(test_config['model_b_results']) == 0
    
    def test_predict_with_ab_test_model_b(self, prediction_service, mock_models_for_ab_test):
        """Test prediction with A/B test selecting model B."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        prediction_service.start_ab_test('test_ab', 'model_a', 'model_b', traffic_split=0.3)
        
        features = pd.DataFrame({
            'feature1': [1.0],
            'feature2': [2.0]
        })
        
        # Mock random to select model B
        with patch('numpy.random.random', return_value=0.5):  # > 0.3, so model B
            result, model_used = prediction_service.predict_with_ab_test(features, 'test_ab')
        
        assert model_used == 'model_b'
        assert result.prediction == 0.7  # Model B prediction
        
        # Check test config updated
        test_config = prediction_service.active_ab_tests['test_ab']
        assert test_config['model_a_predictions'] == 0
        assert test_config['model_b_predictions'] == 1
        assert len(test_config['model_a_results']) == 0
        assert len(test_config['model_b_results']) == 1
    
    def test_predict_with_ab_test_nonexistent(self, prediction_service):
        """Test prediction with non-existent A/B test."""
        features = pd.DataFrame({'feature1': [1.0]})
        
        with pytest.raises(PredictionServiceError, match="not found"):
            prediction_service.predict_with_ab_test(features, 'nonexistent_test')
    
    def test_predict_with_ab_test_expired(self, prediction_service, mock_models_for_ab_test):
        """Test prediction with expired A/B test."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        # Start test with past end date
        test_id = prediction_service.start_ab_test('test_ab', 'model_a', 'model_b')
        test_config = prediction_service.active_ab_tests[test_id]
        test_config['end_date'] = datetime.now() - timedelta(days=1)  # Past date
        
        features = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        
        with pytest.raises(PredictionServiceError, match="has expired"):
            prediction_service.predict_with_ab_test(features, test_id)
        
        # Test should be marked as expired
        assert test_config['status'] == 'expired'
    
    def test_end_ab_test_success(self, prediction_service, mock_models_for_ab_test):
        """Test successful A/B test completion."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        # Start test
        test_id = prediction_service.start_ab_test('test_ab', 'model_a', 'model_b')
        
        # Add mock results
        test_config = prediction_service.active_ab_tests[test_id]
        test_config['model_a_predictions'] = 50
        test_config['model_b_predictions'] = 45
        test_config['model_a_results'] = [
            {'prediction': 0.8, 'confidence': 0.85, 'timestamp': datetime.now()},
            {'prediction': 0.75, 'confidence': 0.80, 'timestamp': datetime.now()},
            {'prediction': 0.82, 'confidence': 0.88, 'timestamp': datetime.now()}
        ]
        test_config['model_b_results'] = [
            {'prediction': 0.7, 'confidence': 0.75, 'timestamp': datetime.now()},
            {'prediction': 0.68, 'confidence': 0.72, 'timestamp': datetime.now()}
        ]
        
        # End test
        result = prediction_service.end_ab_test(test_id)
        
        assert isinstance(result, ABTestResult)
        assert result.test_name == 'test_ab'
        assert result.model_a == 'model_a'
        assert result.model_b == 'model_b'
        assert result.model_a_predictions == 50
        assert result.model_b_predictions == 45
        assert result.winner in ['model_a', 'model_b']
        assert 0 <= result.confidence_level <= 1
        assert isinstance(result.metrics, dict)
        
        # Test should be removed from active tests
        assert test_id not in prediction_service.active_ab_tests
        
        # Result should be stored in history
        assert result in prediction_service.ab_test_results
    
    def test_end_ab_test_nonexistent(self, prediction_service):
        """Test ending non-existent A/B test."""
        with pytest.raises(PredictionServiceError, match="not found"):
            prediction_service.end_ab_test('nonexistent_test')
    
    def test_ab_test_accuracy_calculation(self, prediction_service):
        """Test A/B test accuracy calculation."""
        results = [
            {'prediction': 0.8, 'confidence': 0.85, 'timestamp': datetime.now()},
            {'prediction': 0.7, 'confidence': 0.75, 'timestamp': datetime.now()},
            {'prediction': 0.9, 'confidence': 0.90, 'timestamp': datetime.now()}
        ]
        
        accuracy = prediction_service._calculate_ab_test_accuracy(results)
        expected_accuracy = (0.85 + 0.75 + 0.90) / 3
        
        assert abs(accuracy - expected_accuracy) < 1e-6
    
    def test_ab_test_confidence_calculation(self, prediction_service):
        """Test A/B test confidence level calculation."""
        results_a = [
            {'prediction': 0.8, 'confidence': 0.85, 'timestamp': datetime.now()},
            {'prediction': 0.82, 'confidence': 0.87, 'timestamp': datetime.now()}
        ] * 10  # 20 results
        
        results_b = [
            {'prediction': 0.7, 'confidence': 0.75, 'timestamp': datetime.now()},
            {'prediction': 0.72, 'confidence': 0.77, 'timestamp': datetime.now()}
        ] * 10  # 20 results
        
        confidence = prediction_service._calculate_ab_test_confidence(results_a, results_b)
        
        assert 0 <= confidence <= 1
        assert isinstance(confidence, float)
    
    def test_ab_test_with_insufficient_data(self, prediction_service):
        """Test A/B test with insufficient data."""
        results_a = [{'prediction': 0.8, 'confidence': 0.85, 'timestamp': datetime.now()}]
        results_b = [{'prediction': 0.7, 'confidence': 0.75, 'timestamp': datetime.now()}]
        
        confidence = prediction_service._calculate_ab_test_confidence(results_a, results_b)
        
        # Should return low confidence with small sample size
        assert confidence == 0.5
    
    def test_multiple_concurrent_ab_tests(self, prediction_service, mock_models_for_ab_test):
        """Test running multiple A/B tests concurrently."""
        prediction_service.loaded_models.update(mock_models_for_ab_test)
        
        # Start multiple tests
        test_id_1 = prediction_service.start_ab_test('test_1', 'model_a', 'model_b')
        test_id_2 = prediction_service.start_ab_test('test_2', 'model_a', 'model_b')
        
        assert len(prediction_service.active_ab_tests) == 2
        assert test_id_1 in prediction_service.active_ab_tests
        assert test_id_2 in prediction_service.active_ab_tests
        
        # Tests should be independent
        features = pd.DataFrame({'feature1': [1.0], 'feature2': [2.0]})
        
        with patch('numpy.random.random', return_value=0.2):
            result_1, model_1 = prediction_service.predict_with_ab_test(features, test_id_1)
            result_2, model_2 = prediction_service.predict_with_ab_test(features, test_id_2)
        
        # Both should use model_a (traffic_split default 0.5, random 0.2 < 0.5)
        assert model_1 == 'model_a'
        assert model_2 == 'model_a'
        
        # Counters should be independent
        config_1 = prediction_service.active_ab_tests[test_id_1]
        config_2 = prediction_service.active_ab_tests[test_id_2]
        
        assert config_1['model_a_predictions'] == 1
        assert config_2['model_a_predictions'] == 1


if __name__ == '__main__':
    pytest.main([__file__])