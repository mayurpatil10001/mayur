"""
Unit tests for model training service with walk-forward analysis.

Tests cover multiple ML algorithms, walk-forward validation across time horizons,
model versioning, persistence, and performance tracking.

Requirements: 4.1, 4.3, 4.5
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

from trading_platform.services.machine_learning.model_trainer import (
    ModelTrainer, ModelTrainingError, TimeHorizon, ModelConfig, 
    ModelPerformance, TrainedModel
)
from trading_platform.models.trading import ProcessedTrade


@pytest.fixture
def temp_dir():
    """Create temporary directory for model storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def trainer(temp_dir):
    """Create ModelTrainer instance."""
    return ModelTrainer(models_dir=temp_dir, random_state=42)


@pytest.fixture
def sample_features():
    """Create sample feature data with datetime index."""
    # Use hourly frequency with enough data for walk-forward validation (90 days = 2160 hours)
    dates = pd.date_range('2024-01-01', periods=2160, freq='H')
    np.random.seed(42)
    
    n_samples = len(dates)
    data = {
        'profit_loss': np.random.normal(10, 50, n_samples),
        'duration_minutes': np.random.randint(5, 300, n_samples),
        'hour_of_day': np.random.randint(9, 16, n_samples),
        'day_of_week': np.random.randint(0, 5, n_samples),
        'quantity': np.random.randint(1, 10, n_samples),
        'entry_price': np.random.uniform(4000, 4200, n_samples),
        'is_long': np.random.choice([0, 1], n_samples),
        'rolling_5_pnl_mean': np.random.normal(5, 20, n_samples),
        'rolling_10_win_rate': np.random.uniform(0.4, 0.6, n_samples),
        'cumulative_pnl': np.cumsum(np.random.normal(10, 50, n_samples))
    }
    
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_target_regression():
    """Create sample regression target."""
    dates = pd.date_range('2024-01-01', periods=2160, freq='H')
    np.random.seed(42)
    return pd.Series(np.random.normal(15, 40, 2160), index=dates, name='next_trade_pnl')


@pytest.fixture
def sample_target_classification():
    """Create sample classification target."""
    dates = pd.date_range('2024-01-01', periods=2160, freq='H')
    np.random.seed(42)
    return pd.Series(np.random.choice([0, 1], 2160, p=[0.6, 0.4]), index=dates, name='is_profitable')


@pytest.fixture
def sample_trades():
    """Create sample processed trades."""
    trades = []
    base_date = datetime(2024, 1, 1, 9, 0)
    
    for i in range(50):
        entry_time = base_date + timedelta(days=i, hours=np.random.randint(0, 8))
        exit_time = entry_time + timedelta(minutes=np.random.randint(5, 300))
        
        trade = ProcessedTrade(
            trade_id=f"trade_{i:03d}",
            account_name="IPS_TM_10",
            symbol="NQ",
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=4000 + np.random.uniform(-100, 100),
            exit_price=4000 + np.random.uniform(-100, 100),
            quantity=np.random.randint(1, 5),
            side=np.random.choice(['LONG', 'SHORT']),
            profit_loss=np.random.normal(10, 50),
            commission=2.5,
            duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
            hour_of_day=entry_time.hour,
            day_of_week=entry_time.weekday(),
            entry_order_id=f"entry_{i:03d}",
            exit_order_id=f"exit_{i:03d}"
        )
        trades.append(trade)
    
    return trades


class TestModelTrainer:
    """Test cases for ModelTrainer class."""


class TestModelTrainerInitialization:
    """Test ModelTrainer initialization."""
    
    def test_init_default_parameters(self, temp_dir):
        """Test initialization with default parameters."""
        trainer = ModelTrainer(models_dir=temp_dir)
        
        assert trainer.models_dir == Path(temp_dir)
        assert trainer.enable_scaling is True
        assert trainer.random_state == 42
        assert len(trainer.time_horizons) == 3
        assert len(trainer.model_configs) > 5
        assert trainer.performance_history == []
        assert trainer.best_models == {}
    
    def test_init_custom_parameters(self, temp_dir):
        """Test initialization with custom parameters."""
        trainer = ModelTrainer(
            models_dir=temp_dir,
            enable_scaling=False,
            random_state=123
        )
        
        assert trainer.enable_scaling is False
        assert trainer.random_state == 123
    
    def test_time_horizons_configuration(self, trainer):
        """Test time horizons are properly configured."""
        horizons = trainer.get_time_horizons()
        
        assert 'short_term' in horizons
        assert 'medium_term' in horizons
        assert 'long_term' in horizons
        
        short_term = horizons['short_term']
        assert short_term.training_days == 7
        assert short_term.testing_days == 2
        
        medium_term = horizons['medium_term']
        assert medium_term.training_days == 14
        assert medium_term.testing_days == 7
        
        long_term = horizons['long_term']
        assert long_term.training_days == 30
        assert long_term.testing_days == 14
    
    def test_model_configurations(self, trainer):
        """Test model configurations are properly set up."""
        models = trainer.get_available_models()
        
        # Check regression models
        assert 'random_forest_reg' in models
        assert 'gradient_boosting_reg' in models
        assert 'linear_regression' in models
        assert 'ridge_regression' in models
        assert 'lasso_regression' in models
        assert 'svr' in models
        assert 'mlp_regressor' in models
        
        # Check classification models
        assert 'random_forest_clf' in models
        assert 'gradient_boosting_clf' in models
        assert 'logistic_regression' in models
        assert 'svc' in models
        assert 'mlp_classifier' in models
        
        # Verify model config structure
        rf_config = models['random_forest_reg']
        assert rf_config.name == 'random_forest_reg'
        assert rf_config.model_class == RandomForestRegressor
        assert rf_config.is_classifier is False
        assert 'n_estimators' in rf_config.params


class TestSingleModelTraining:
    """Test single model training functionality."""
    
    def test_train_regression_model_success(self, trainer, sample_features, sample_target_regression):
        """Test successful regression model training."""
        trained_model = trainer.train_model(
            sample_features, sample_target_regression, 'random_forest_reg'
        )
        
        assert isinstance(trained_model, TrainedModel)
        assert isinstance(trained_model.model, RandomForestRegressor)
        assert trained_model.config.name == 'random_forest_reg'
        assert trained_model.target_name == 'next_trade_pnl'
        assert len(trained_model.feature_names) == len(sample_features.columns)
        assert trained_model.performance.training_score > -1  # R² can be negative
        assert trained_model.performance.feature_count == len(sample_features.columns)
        assert trained_model.performance.training_samples == len(sample_features)
        assert 'r2' in trained_model.performance.metrics
        assert 'mse' in trained_model.performance.metrics
    
    def test_train_classification_model_success(self, trainer, sample_features, sample_target_classification):
        """Test successful classification model training."""
        trained_model = trainer.train_model(
            sample_features, sample_target_classification, 'random_forest_clf'
        )
        
        assert isinstance(trained_model, TrainedModel)
        assert isinstance(trained_model.model, RandomForestClassifier)
        assert trained_model.config.name == 'random_forest_clf'
        assert trained_model.target_name == 'is_profitable'
        assert 0 <= trained_model.performance.training_score <= 1  # Accuracy
        assert 'accuracy' in trained_model.performance.metrics
        assert 'precision' in trained_model.performance.metrics
    
    def test_train_model_with_scaling(self, temp_dir, sample_features, sample_target_regression):
        """Test model training with feature scaling."""
        trainer = ModelTrainer(models_dir=temp_dir, enable_scaling=True)
        trained_model = trainer.train_model(
            sample_features, sample_target_regression, 'linear_regression'
        )
        
        assert trained_model.scaler is not None
        assert hasattr(trained_model.scaler, 'mean_')
        assert hasattr(trained_model.scaler, 'scale_')
    
    def test_train_model_without_scaling(self, temp_dir, sample_features, sample_target_regression):
        """Test model training without feature scaling."""
        trainer = ModelTrainer(models_dir=temp_dir, enable_scaling=False)
        trained_model = trainer.train_model(
            sample_features, sample_target_regression, 'linear_regression'
        )
        
        assert trained_model.scaler is None
    
    def test_train_model_invalid_type(self, trainer, sample_features, sample_target_regression):
        """Test training with invalid model type."""
        with pytest.raises(ModelTrainingError, match="Unknown model type"):
            trainer.train_model(sample_features, sample_target_regression, 'invalid_model')
    
    def test_train_model_empty_features(self, trainer):
        """Test training with empty features."""
        empty_features = pd.DataFrame()
        empty_target = pd.Series([], dtype=float)
        
        with pytest.raises(ModelTrainingError, match="Cannot train on empty features"):
            trainer.train_model(empty_features, empty_target, 'random_forest_reg')
    
    def test_train_model_mismatched_lengths(self, trainer, sample_features):
        """Test training with mismatched feature and target lengths."""
        short_target = pd.Series([1, 2, 3])
        
        with pytest.raises(ModelTrainingError, match="Features and target must have same length"):
            trainer.train_model(sample_features, short_target, 'random_forest_reg')


class TestWalkForwardValidation:
    """Test walk-forward validation functionality."""
    
    def test_walk_forward_validation_success(self, trainer, sample_features, sample_target_regression):
        """Test successful walk-forward validation."""
        results = trainer.walk_forward_validation(
            sample_features, sample_target_regression, 'random_forest_reg', 'medium_term'
        )
        
        assert results['model_type'] == 'random_forest_reg'
        assert results['horizon'] == 'medium_term'
        assert results['total_folds'] > 0
        assert 'fold_results' in results
        assert 'summary' in results
        assert 'overall_metrics' in results
        
        # Check summary statistics
        summary = results['summary']
        assert 'mean_train_score' in summary
        assert 'mean_test_score' in summary
        assert 'std_test_score' in summary
        assert 'score_stability' in summary
        assert 'overfitting_ratio' in summary
        
        # Check fold results
        fold_results = results['fold_results']
        assert len(fold_results) > 0
        
        for fold in fold_results:
            assert 'fold' in fold
            assert 'train_score' in fold
            assert 'test_score' in fold
            assert 'train_samples' in fold
            assert 'test_samples' in fold
            assert 'training_time' in fold
            assert 'prediction_time' in fold
    
    def test_walk_forward_different_horizons(self, trainer, sample_features, sample_target_regression):
        """Test walk-forward validation with different time horizons."""
        for horizon in ['short_term', 'medium_term', 'long_term']:
            results = trainer.walk_forward_validation(
                sample_features, sample_target_regression, 'linear_regression', horizon
            )
            
            assert results['horizon'] == horizon
            assert results['total_folds'] >= 0  # May be 0 for insufficient data
    
    def test_walk_forward_classification(self, trainer, sample_features, sample_target_classification):
        """Test walk-forward validation with classification."""
        results = trainer.walk_forward_validation(
            sample_features, sample_target_classification, 'random_forest_clf', 'medium_term'
        )
        
        assert results['model_type'] == 'random_forest_clf'
        assert 'accuracy' in results['overall_metrics']
        assert 'precision' in results['overall_metrics']
    
    def test_walk_forward_invalid_model(self, trainer, sample_features, sample_target_regression):
        """Test walk-forward validation with invalid model type."""
        with pytest.raises(ModelTrainingError, match="Unknown model type"):
            trainer.walk_forward_validation(
                sample_features, sample_target_regression, 'invalid_model', 'medium_term'
            )
    
    def test_walk_forward_invalid_horizon(self, trainer, sample_features, sample_target_regression):
        """Test walk-forward validation with invalid horizon."""
        with pytest.raises(ModelTrainingError, match="Unknown horizon"):
            trainer.walk_forward_validation(
                sample_features, sample_target_regression, 'random_forest_reg', 'invalid_horizon'
            )
    
    def test_walk_forward_non_datetime_index(self, trainer, sample_target_regression):
        """Test walk-forward validation with non-datetime index."""
        features_no_datetime = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [5, 4, 3, 2, 1]
        })
        
        with pytest.raises(ModelTrainingError, match="Features must have datetime index"):
            trainer.walk_forward_validation(
                features_no_datetime, sample_target_regression[:5], 'linear_regression', 'short_term'
            )
    
    def test_walk_forward_insufficient_data(self, trainer, sample_target_regression):
        """Test walk-forward validation with insufficient data."""
        # Create very small dataset
        small_features = pd.DataFrame({
            'feature1': [1, 2, 3]
        }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
        
        small_target = sample_target_regression[:3]
        
        with pytest.raises(ModelTrainingError, match="Insufficient data"):
            trainer.walk_forward_validation(
                small_features, small_target, 'linear_regression', 'long_term'
            )


class TestModelSelection:
    """Test model selection functionality."""
    
    def test_train_all_models_all_horizons(self, trainer, sample_features, sample_target_regression):
        """Test training all models across all horizons."""
        # Use subset of models for faster testing
        model_types = ['linear_regression', 'random_forest_reg']
        horizons = ['short_term', 'medium_term']
        
        results = trainer.train_all_models_all_horizons(
            sample_features, sample_target_regression, model_types, horizons
        )
        
        assert len(results) == len(model_types)
        
        for model_type in model_types:
            assert model_type in results
            assert len(results[model_type]) == len(horizons)
            
            for horizon in horizons:
                assert horizon in results[model_type]
                # Should either have results or error
                assert 'summary' in results[model_type][horizon] or 'error' in results[model_type][horizon]
    
    def test_select_best_model(self, trainer, sample_features, sample_target_regression):
        """Test best model selection."""
        # Train models
        model_types = ['linear_regression', 'random_forest_reg']
        horizons = ['short_term', 'medium_term']
        
        results = trainer.train_all_models_all_horizons(
            sample_features, sample_target_regression, model_types, horizons
        )
        
        # Select best models
        best_models = trainer.select_best_model(results)
        
        # Should have best model for each horizon (if data sufficient)
        for horizon in horizons:
            if horizon in best_models:
                model_type, result = best_models[horizon]
                assert model_type in model_types
                assert 'summary' in result
    
    def test_train_final_models(self, trainer, sample_features, sample_target_regression):
        """Test training final models."""
        # Create mock best models selection
        best_models = {
            'short_term': ('linear_regression', {
                'summary': {'mean_test_score': 0.5},
                'overall_metrics': {'r2': 0.5, 'mse': 100}
            })
        }
        
        final_models = trainer.train_final_models(
            sample_features, sample_target_regression, best_models
        )
        
        assert 'short_term' in final_models
        assert isinstance(final_models['short_term'], TrainedModel)
        assert final_models['short_term'].performance.horizon_name == 'short_term'


class TestModelPersistence:
    """Test model saving and loading functionality."""
    
    def test_save_and_load_model(self, trainer, sample_features, sample_target_regression):
        """Test saving and loading trained model."""
        # Train model
        trained_model = trainer.train_model(
            sample_features, sample_target_regression, 'random_forest_reg'
        )
        
        # Save model
        filepath = trainer.save_model(trained_model)
        assert Path(filepath).exists()
        
        # Check metadata file exists
        metadata_path = Path(filepath).with_suffix('.json')
        assert metadata_path.exists()
        
        # Load model
        loaded_model = trainer.load_model(filepath)
        
        # Verify loaded model
        assert isinstance(loaded_model, TrainedModel)
        assert loaded_model.config.name == trained_model.config.name
        assert loaded_model.feature_names == trained_model.feature_names
        assert loaded_model.target_name == trained_model.target_name
        
        # Test prediction works
        predictions = loaded_model.model.predict(sample_features)
        assert len(predictions) == len(sample_features)
    
    def test_save_model_custom_filename(self, trainer, sample_features, sample_target_regression):
        """Test saving model with custom filename."""
        trained_model = trainer.train_model(
            sample_features, sample_target_regression, 'linear_regression'
        )
        
        custom_filename = "custom_model.pkl"
        filepath = trainer.save_model(trained_model, custom_filename)
        
        assert Path(filepath).name == custom_filename
        assert Path(filepath).exists()
    
    def test_load_nonexistent_model(self, trainer):
        """Test loading non-existent model."""
        with pytest.raises(ModelTrainingError, match="Failed to load model"):
            trainer.load_model("nonexistent_model.pkl")


class TestModelEvaluation:
    """Test model evaluation functionality."""
    
    def test_evaluate_regression_model(self, trainer, sample_features, sample_target_regression):
        """Test evaluating regression model."""
        trained_model = trainer.train_model(
            sample_features, sample_target_regression, 'random_forest_reg'
        )
        
        metrics = trainer.evaluate_model(
            trained_model.model, sample_features, sample_target_regression
        )
        
        assert 'mse' in metrics
        assert 'rmse' in metrics
        assert 'mae' in metrics
        assert 'r2' in metrics
        assert isinstance(metrics['mse'], float)
        assert metrics['rmse'] >= 0
        assert metrics['mae'] >= 0
    
    def test_evaluate_classification_model(self, trainer, sample_features, sample_target_classification):
        """Test evaluating classification model."""
        trained_model = trainer.train_model(
            sample_features, sample_target_classification, 'random_forest_clf'
        )
        
        metrics = trainer.evaluate_model(
            trained_model.model, sample_features, sample_target_classification
        )
        
        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics
        assert 'f1' in metrics
        assert 0 <= metrics['accuracy'] <= 1
        assert 0 <= metrics['precision'] <= 1


class TestPerformanceTracking:
    """Test performance tracking functionality."""
    
    def test_performance_history_tracking(self, trainer, sample_features, sample_target_regression):
        """Test that performance history is tracked."""
        initial_count = len(trainer.performance_history)
        
        # Perform walk-forward validation
        trainer.walk_forward_validation(
            sample_features, sample_target_regression, 'linear_regression', 'short_term'
        )
        
        assert len(trainer.performance_history) == initial_count + 1
        
        # Check performance record
        performance = trainer.performance_history[-1]
        assert isinstance(performance, ModelPerformance)
        assert performance.model_name == 'linear_regression'
        assert performance.horizon_name == 'short_term'
    
    def test_get_performance_summary(self, trainer, sample_features, sample_target_regression):
        """Test getting performance summary."""
        # Train some models
        trainer.walk_forward_validation(
            sample_features, sample_target_regression, 'linear_regression', 'short_term'
        )
        trainer.walk_forward_validation(
            sample_features, sample_target_regression, 'random_forest_reg', 'short_term'
        )
        
        summary = trainer.get_model_performance_summary()
        
        assert isinstance(summary, pd.DataFrame)
        assert len(summary) >= 2
        assert 'model_name' in summary.columns
        assert 'horizon' in summary.columns
        assert 'training_score' in summary.columns
        assert 'validation_score' in summary.columns
    
    def test_clear_performance_history(self, trainer, sample_features, sample_target_regression):
        """Test clearing performance history."""
        # Add some performance records
        trainer.walk_forward_validation(
            sample_features, sample_target_regression, 'linear_regression', 'short_term'
        )
        
        assert len(trainer.performance_history) > 0
        
        trainer.clear_performance_history()
        
        assert len(trainer.performance_history) == 0
        assert len(trainer.best_models) == 0


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_training_workflow(self, trainer, sample_features, sample_target_regression):
        """Test complete model training workflow."""
        # 1. Train all models across horizons
        model_types = ['linear_regression', 'random_forest_reg']
        horizons = ['short_term']
        
        results = trainer.train_all_models_all_horizons(
            sample_features, sample_target_regression, model_types, horizons
        )
        
        # 2. Select best models
        best_models = trainer.select_best_model(results)
        
        # 3. Train final models
        if best_models:  # Only if we have valid results
            final_models = trainer.train_final_models(
                sample_features, sample_target_regression, best_models
            )
            
            # 4. Save models
            for horizon, model in final_models.items():
                filepath = trainer.save_model(model)
                assert Path(filepath).exists()
                
                # 5. Load and test
                loaded_model = trainer.load_model(filepath)
                predictions = loaded_model.model.predict(sample_features)
                assert len(predictions) == len(sample_features)
    
    def test_model_versioning(self, trainer, sample_features, sample_target_regression):
        """Test model versioning functionality."""
        # Train same model type multiple times
        model1 = trainer.train_model(
            sample_features, sample_target_regression, 'linear_regression'
        )
        
        # Small delay to ensure different timestamps
        import time
        time.sleep(0.1)
        
        model2 = trainer.train_model(
            sample_features, sample_target_regression, 'linear_regression'
        )
        
        # Versions should be different
        assert model1.version != model2.version
        assert model1.created_at != model2.created_at
    
    def test_error_handling_robustness(self, trainer):
        """Test error handling in various scenarios."""
        # Test with invalid data types
        with pytest.raises(ModelTrainingError):
            trainer.train_model("invalid", "invalid", 'linear_regression')
        
        # Test with NaN values
        features_with_nan = pd.DataFrame({
            'feature1': [1, 2, np.nan, 4, 5],
            'feature2': [5, 4, 3, 2, 1]
        }, index=pd.date_range('2024-01-01', periods=5, freq='D'))
        
        target_with_nan = pd.Series([1, 2, np.nan, 4, 5])
        
        # Should handle NaN values gracefully or raise appropriate error
        try:
            trainer.train_model(features_with_nan, target_with_nan, 'linear_regression')
        except ModelTrainingError:
            pass  # Expected behavior


if __name__ == "__main__":
    pytest.main([__file__])