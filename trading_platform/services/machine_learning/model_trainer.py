"""
Model training service with walk-forward analysis for trading optimization.

This service implements multiple ML algorithms with walk-forward validation
across different time horizons to prevent overfitting and ensure robustness.

Requirements: 4.1, 4.3, 4.5
"""

import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge, Lasso
from sklearn.svm import SVR, SVC
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.base import BaseEstimator, clone

from ...models.trading import ProcessedTrade
from ...interfaces.ml_interfaces import IModelTrainer


@dataclass
class TimeHorizon:
    """Configuration for walk-forward time horizon."""
    name: str
    training_days: int
    testing_days: int
    description: str


@dataclass
class ModelConfig:
    """Configuration for ML model."""
    name: str
    model_class: type
    params: Dict[str, Any]
    is_classifier: bool
    description: str


@dataclass
class ModelPerformance:
    """Performance metrics for a trained model."""
    model_name: str
    horizon_name: str
    training_score: float
    validation_score: float
    test_score: float
    training_samples: int
    test_samples: int
    feature_count: int
    training_time: float
    prediction_time: float
    metrics: Dict[str, float]
    timestamp: datetime


@dataclass
class TrainedModel:
    """Container for trained model with metadata."""
    model: BaseEstimator
    scaler: Optional[StandardScaler]
    config: ModelConfig
    performance: ModelPerformance
    feature_names: List[str]
    target_name: str
    training_data_info: Dict[str, Any]
    version: str
    created_at: datetime


class ModelTrainingError(Exception):
    """Exception raised by model training service."""
    pass


class ModelTrainer(IModelTrainer):
    """
    Model training service with walk-forward analysis.
    
    Implements multiple ML algorithms with comprehensive validation
    across different time horizons.
    """
    
    def __init__(self, 
                 models_dir: str = "models",
                 enable_scaling: bool = True,
                 random_state: int = 42):
        """
        Initialize the model trainer.
        
        Args:
            models_dir: Directory to save trained models
            enable_scaling: Whether to apply feature scaling
            random_state: Random state for reproducibility
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        self.enable_scaling = enable_scaling
        self.random_state = random_state
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # Define time horizons
        self.time_horizons = {
            'short_term': TimeHorizon(
                name='short_term',
                training_days=7,
                testing_days=2,
                description='1 week training → 2 days testing'
            ),
            'medium_term': TimeHorizon(
                name='medium_term',
                training_days=14,
                testing_days=7,
                description='2 weeks training → 1 week testing'
            ),
            'long_term': TimeHorizon(
                name='long_term',
                training_days=30,
                testing_days=14,
                description='1 month training → 2 weeks testing'
            )
        }
        
        # Define model configurations
        self.model_configs = {
            # Regression models
            'random_forest_reg': ModelConfig(
                name='random_forest_reg',
                model_class=RandomForestRegressor,
                params={'n_estimators': 100, 'max_depth': 10, 'random_state': random_state},
                is_classifier=False,
                description='Random Forest Regressor'
            ),
            'gradient_boosting_reg': ModelConfig(
                name='gradient_boosting_reg',
                model_class=GradientBoostingRegressor,
                params={'n_estimators': 100, 'max_depth': 6, 'learning_rate': 0.1, 'random_state': random_state},
                is_classifier=False,
                description='Gradient Boosting Regressor'
            ),
            'linear_regression': ModelConfig(
                name='linear_regression',
                model_class=LinearRegression,
                params={},
                is_classifier=False,
                description='Linear Regression'
            ),
            'ridge_regression': ModelConfig(
                name='ridge_regression',
                model_class=Ridge,
                params={'alpha': 1.0, 'random_state': random_state},
                is_classifier=False,
                description='Ridge Regression'
            ),
            'lasso_regression': ModelConfig(
                name='lasso_regression',
                model_class=Lasso,
                params={'alpha': 0.1, 'random_state': random_state},
                is_classifier=False,
                description='Lasso Regression'
            ),
            'svr': ModelConfig(
                name='svr',
                model_class=SVR,
                params={'kernel': 'rbf', 'C': 1.0, 'gamma': 'scale'},
                is_classifier=False,
                description='Support Vector Regression'
            ),
            'mlp_regressor': ModelConfig(
                name='mlp_regressor',
                model_class=MLPRegressor,
                params={'hidden_layer_sizes': (100, 50), 'max_iter': 500, 'random_state': random_state},
                is_classifier=False,
                description='Multi-layer Perceptron Regressor'
            ),
            
            # Classification models
            'random_forest_clf': ModelConfig(
                name='random_forest_clf',
                model_class=RandomForestClassifier,
                params={'n_estimators': 100, 'max_depth': 10, 'random_state': random_state},
                is_classifier=True,
                description='Random Forest Classifier'
            ),
            'gradient_boosting_clf': ModelConfig(
                name='gradient_boosting_clf',
                model_class=GradientBoostingClassifier,
                params={'n_estimators': 100, 'max_depth': 6, 'learning_rate': 0.1, 'random_state': random_state},
                is_classifier=True,
                description='Gradient Boosting Classifier'
            ),
            'logistic_regression': ModelConfig(
                name='logistic_regression',
                model_class=LogisticRegression,
                params={'random_state': random_state, 'max_iter': 1000},
                is_classifier=True,
                description='Logistic Regression'
            ),
            'svc': ModelConfig(
                name='svc',
                model_class=SVC,
                params={'kernel': 'rbf', 'C': 1.0, 'gamma': 'scale', 'random_state': random_state},
                is_classifier=True,
                description='Support Vector Classifier'
            ),
            'mlp_classifier': ModelConfig(
                name='mlp_classifier',
                model_class=MLPClassifier,
                params={'hidden_layer_sizes': (100, 50), 'max_iter': 500, 'random_state': random_state},
                is_classifier=True,
                description='Multi-layer Perceptron Classifier'
            )
        }
        
        # Model performance tracking
        self.performance_history: List[ModelPerformance] = []
        self.best_models: Dict[str, Dict[str, TrainedModel]] = {}  # horizon -> model_type -> best_model
    
    def train_model(self, 
                   features: pd.DataFrame, 
                   target: pd.Series, 
                   model_type: str = "random_forest_reg") -> TrainedModel:
        """
        Train a single machine learning model.
        
        Args:
            features: Feature DataFrame with datetime index
            target: Target series
            model_type: Type of model to train
            
        Returns:
            Trained model with metadata
            
        Raises:
            ModelTrainingError: If training fails
        """
        if model_type not in self.model_configs:
            raise ModelTrainingError(f"Unknown model type: {model_type}")
        
        # Validate input types
        if not isinstance(features, pd.DataFrame):
            raise ModelTrainingError("Features must be a pandas DataFrame")
        
        if not isinstance(target, pd.Series):
            raise ModelTrainingError("Target must be a pandas Series")
        
        if len(features) != len(target):
            raise ModelTrainingError("Features and target must have same length")
        
        if features.empty:
            raise ModelTrainingError("Cannot train on empty features")
        
        try:
            config = self.model_configs[model_type]
            
            # Prepare data
            X = features.copy()
            y = target.copy()
            
            # Apply scaling if enabled
            scaler = None
            if self.enable_scaling:
                scaler = StandardScaler()
                X = pd.DataFrame(
                    scaler.fit_transform(X),
                    index=X.index,
                    columns=X.columns
                )
            
            # Train model
            start_time = datetime.now()
            model = config.model_class(**config.params)
            model.fit(X, y)
            training_time = (datetime.now() - start_time).total_seconds()
            
            # Calculate training performance
            start_time = datetime.now()
            train_pred = model.predict(X)
            prediction_time = (datetime.now() - start_time).total_seconds()
            
            # Calculate metrics
            if config.is_classifier:
                training_score = accuracy_score(y, train_pred)
                metrics = self._calculate_classification_metrics(y, train_pred)
            else:
                training_score = r2_score(y, train_pred)
                metrics = self._calculate_regression_metrics(y, train_pred)
            
            # Create performance record
            performance = ModelPerformance(
                model_name=model_type,
                horizon_name='single_train',
                training_score=training_score,
                validation_score=training_score,  # Same as training for single train
                test_score=training_score,
                training_samples=len(X),
                test_samples=len(X),
                feature_count=len(X.columns),
                training_time=training_time,
                prediction_time=prediction_time,
                metrics=metrics,
                timestamp=datetime.now()
            )
            
            # Create training data info
            training_data_info = {
                'total_samples': len(X),
                'feature_count': len(X.columns),
                'target_name': target.name or 'target',
                'date_range': {
                    'start': X.index.min(),
                    'end': X.index.max()
                } if hasattr(X.index, 'min') else None,
                'feature_stats': {
                    'mean': X.mean().to_dict(),
                    'std': X.std().to_dict(),
                    'min': X.min().to_dict(),
                    'max': X.max().to_dict()
                }
            }
            
            # Create trained model with unique versioning
            now = datetime.now()
            trained_model = TrainedModel(
                model=model,
                scaler=scaler,
                config=config,
                performance=performance,
                feature_names=list(X.columns),
                target_name=target.name or 'target',
                training_data_info=training_data_info,
                version=f"v1.0_{now.strftime('%Y%m%d_%H%M%S_%f')}",
                created_at=now
            )
            
            self.logger.info(f"Successfully trained {model_type} model with score: {training_score:.4f}")
            return trained_model
            
        except Exception as e:
            raise ModelTrainingError(f"Failed to train {model_type} model: {e}")
    
    def walk_forward_validation(self, 
                              features: pd.DataFrame, 
                              target: pd.Series, 
                              model_type: str, 
                              horizon: str = 'medium_term') -> Dict[str, Any]:
        """
        Perform walk-forward validation to prevent overfitting.
        
        Args:
            features: Feature DataFrame with datetime index
            target: Target series
            model_type: Type of model to validate
            horizon: Time horizon configuration to use
            
        Returns:
            Dictionary with validation results
            
        Raises:
            ModelTrainingError: If validation fails
        """
        if model_type not in self.model_configs:
            raise ModelTrainingError(f"Unknown model type: {model_type}")
        
        if horizon not in self.time_horizons:
            raise ModelTrainingError(f"Unknown horizon: {horizon}")
        
        if not isinstance(features.index, pd.DatetimeIndex):
            raise ModelTrainingError("Features must have datetime index for walk-forward validation")
        
        try:
            config = self.model_configs[model_type]
            horizon_config = self.time_horizons[horizon]
            
            # Prepare data
            X = features.copy().sort_index()
            y = target.copy().reindex(X.index)
            
            # Remove NaN values
            valid_mask = ~(X.isnull().any(axis=1) | y.isnull())
            X = X[valid_mask]
            y = y[valid_mask]
            
            # Generate walk-forward splits
            splits = self._generate_walk_forward_splits(X, horizon_config)
            
            if len(splits) == 0:
                raise ModelTrainingError(f"Insufficient data for {horizon} walk-forward validation")
            
            # Perform validation
            results = []
            all_predictions = []
            all_actuals = []
            
            for i, (train_idx, test_idx) in enumerate(splits):
                self.logger.info(f"Walk-forward fold {i+1}/{len(splits)} for {model_type} on {horizon}")
                
                # Split data
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
                
                # Apply scaling
                scaler = None
                if self.enable_scaling:
                    scaler = StandardScaler()
                    X_train_scaled = pd.DataFrame(
                        scaler.fit_transform(X_train),
                        index=X_train.index,
                        columns=X_train.columns
                    )
                    X_test_scaled = pd.DataFrame(
                        scaler.transform(X_test),
                        index=X_test.index,
                        columns=X_test.columns
                    )
                else:
                    X_train_scaled = X_train
                    X_test_scaled = X_test
                
                # Train model
                start_time = datetime.now()
                model = config.model_class(**config.params)
                model.fit(X_train_scaled, y_train)
                training_time = (datetime.now() - start_time).total_seconds()
                
                # Make predictions
                start_time = datetime.now()
                train_pred = model.predict(X_train_scaled)
                test_pred = model.predict(X_test_scaled)
                prediction_time = (datetime.now() - start_time).total_seconds()
                
                # Calculate scores
                if config.is_classifier:
                    train_score = accuracy_score(y_train, train_pred)
                    test_score = accuracy_score(y_test, test_pred)
                    test_metrics = self._calculate_classification_metrics(y_test, test_pred)
                else:
                    train_score = r2_score(y_train, train_pred)
                    test_score = r2_score(y_test, test_pred)
                    test_metrics = self._calculate_regression_metrics(y_test, test_pred)
                
                # Store results
                fold_result = {
                    'fold': i + 1,
                    'train_start': X_train.index.min(),
                    'train_end': X_train.index.max(),
                    'test_start': X_test.index.min(),
                    'test_end': X_test.index.max(),
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'train_score': train_score,
                    'test_score': test_score,
                    'training_time': training_time,
                    'prediction_time': prediction_time,
                    'metrics': test_metrics
                }
                results.append(fold_result)
                
                # Collect predictions for overall metrics
                all_predictions.extend(test_pred)
                all_actuals.extend(y_test)
            
            # Calculate overall performance
            if config.is_classifier:
                overall_score = accuracy_score(all_actuals, all_predictions)
                overall_metrics = self._calculate_classification_metrics(all_actuals, all_predictions)
            else:
                overall_score = r2_score(all_actuals, all_predictions)
                overall_metrics = self._calculate_regression_metrics(all_actuals, all_predictions)
            
            # Calculate summary statistics
            train_scores = [r['train_score'] for r in results]
            test_scores = [r['test_score'] for r in results]
            
            validation_results = {
                'model_type': model_type,
                'horizon': horizon,
                'horizon_config': asdict(horizon_config),
                'total_folds': len(results),
                'fold_results': results,
                'summary': {
                    'mean_train_score': np.mean(train_scores),
                    'std_train_score': np.std(train_scores),
                    'mean_test_score': np.mean(test_scores),
                    'std_test_score': np.std(test_scores),
                    'overall_test_score': overall_score,
                    'score_stability': 1 - (np.std(test_scores) / (np.mean(test_scores) + 1e-8)),
                    'overfitting_ratio': np.mean(train_scores) / (np.mean(test_scores) + 1e-8)
                },
                'overall_metrics': overall_metrics,
                'total_samples': len(X),
                'total_training_time': sum(r['training_time'] for r in results),
                'avg_prediction_time': np.mean([r['prediction_time'] for r in results]),
                'validation_timestamp': datetime.now()
            }
            
            # Create performance record
            performance = ModelPerformance(
                model_name=model_type,
                horizon_name=horizon,
                training_score=validation_results['summary']['mean_train_score'],
                validation_score=validation_results['summary']['mean_test_score'],
                test_score=overall_score,
                training_samples=sum(r['train_samples'] for r in results) // len(results),
                test_samples=sum(r['test_samples'] for r in results) // len(results),
                feature_count=len(X.columns),
                training_time=validation_results['total_training_time'],
                prediction_time=validation_results['avg_prediction_time'],
                metrics=overall_metrics,
                timestamp=datetime.now()
            )
            
            # Store performance
            self.performance_history.append(performance)
            
            self.logger.info(f"Walk-forward validation completed for {model_type} on {horizon}: "
                           f"mean test score = {validation_results['summary']['mean_test_score']:.4f}")
            
            return validation_results
            
        except Exception as e:
            raise ModelTrainingError(f"Walk-forward validation failed for {model_type}: {e}")   
 
    def train_all_models_all_horizons(self, 
                                    features: pd.DataFrame, 
                                    target: pd.Series,
                                    model_types: Optional[List[str]] = None,
                                    horizons: Optional[List[str]] = None) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Train all models across all time horizons with walk-forward validation.
        
        Args:
            features: Feature DataFrame with datetime index
            target: Target series
            model_types: List of model types to train (default: all)
            horizons: List of horizons to test (default: all)
            
        Returns:
            Dictionary with results for each model and horizon
        """
        if model_types is None:
            model_types = list(self.model_configs.keys())
        
        if horizons is None:
            horizons = list(self.time_horizons.keys())
        
        results = {}
        
        for model_type in model_types:
            results[model_type] = {}
            
            for horizon in horizons:
                try:
                    self.logger.info(f"Training {model_type} with {horizon} horizon")
                    validation_result = self.walk_forward_validation(
                        features, target, model_type, horizon
                    )
                    results[model_type][horizon] = validation_result
                    
                except Exception as e:
                    self.logger.error(f"Failed to train {model_type} with {horizon}: {e}")
                    results[model_type][horizon] = {'error': str(e)}
        
        return results
    
    def select_best_model(self, 
                         validation_results: Dict[str, Dict[str, Dict[str, Any]]],
                         selection_metric: str = 'mean_test_score',
                         stability_weight: float = 0.3) -> Dict[str, Tuple[str, Dict[str, Any]]]:
        """
        Select best model for each horizon based on performance and stability.
        
        Args:
            validation_results: Results from train_all_models_all_horizons
            selection_metric: Primary metric for selection
            stability_weight: Weight for stability in selection (0-1)
            
        Returns:
            Dictionary mapping horizon to (best_model_type, results)
        """
        best_models = {}
        
        for horizon in self.time_horizons.keys():
            best_score = -np.inf
            best_model_type = None
            best_result = None
            
            for model_type, model_results in validation_results.items():
                if horizon not in model_results or 'error' in model_results[horizon]:
                    continue
                
                result = model_results[horizon]
                summary = result.get('summary', {})
                
                # Calculate composite score
                primary_score = summary.get(selection_metric, 0)
                stability_score = summary.get('score_stability', 0)
                
                composite_score = (
                    (1 - stability_weight) * primary_score + 
                    stability_weight * stability_score
                )
                
                if composite_score > best_score:
                    best_score = composite_score
                    best_model_type = model_type
                    best_result = result
            
            if best_model_type:
                best_models[horizon] = (best_model_type, best_result)
                self.logger.info(f"Best model for {horizon}: {best_model_type} "
                               f"(score: {best_score:.4f})")
        
        return best_models
    
    def train_final_models(self, 
                          features: pd.DataFrame, 
                          target: pd.Series,
                          best_models: Dict[str, Tuple[str, Dict[str, Any]]]) -> Dict[str, TrainedModel]:
        """
        Train final models using full dataset for the best model types.
        
        Args:
            features: Feature DataFrame
            target: Target series
            best_models: Best models selected for each horizon
            
        Returns:
            Dictionary mapping horizon to trained model
        """
        final_models = {}
        
        for horizon, (model_type, validation_result) in best_models.items():
            try:
                self.logger.info(f"Training final {model_type} model for {horizon}")
                
                # Train on full dataset
                trained_model = self.train_model(features, target, model_type)
                
                # Update performance with validation results
                trained_model.performance.horizon_name = horizon
                trained_model.performance.validation_score = validation_result['summary']['mean_test_score']
                trained_model.performance.metrics.update(validation_result['overall_metrics'])
                
                final_models[horizon] = trained_model
                
                # Store as best model
                if horizon not in self.best_models:
                    self.best_models[horizon] = {}
                self.best_models[horizon][model_type] = trained_model
                
            except Exception as e:
                self.logger.error(f"Failed to train final {model_type} model for {horizon}: {e}")
        
        return final_models
    
    def evaluate_model(self, 
                      model: BaseEstimator, 
                      test_features: pd.DataFrame, 
                      test_target: pd.Series) -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        
        Args:
            model: Trained model
            test_features: Test features
            test_target: Test target
            
        Returns:
            Dictionary with evaluation metrics
        """
        try:
            predictions = model.predict(test_features)
            
            # Determine if classification or regression
            is_classifier = hasattr(model, 'predict_proba')
            
            if is_classifier:
                return self._calculate_classification_metrics(test_target, predictions)
            else:
                return self._calculate_regression_metrics(test_target, predictions)
                
        except Exception as e:
            raise ModelTrainingError(f"Model evaluation failed: {e}")
    
    def save_model(self, trained_model: TrainedModel, filename: Optional[str] = None) -> str:
        """
        Save trained model to disk.
        
        Args:
            trained_model: Model to save
            filename: Optional filename (auto-generated if None)
            
        Returns:
            Path to saved model file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{trained_model.config.name}_{trained_model.performance.horizon_name}_{timestamp}.pkl"
        
        filepath = self.models_dir / filename
        
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(trained_model, f)
            
            # Save metadata separately
            metadata_path = filepath.with_suffix('.json')
            metadata = {
                'model_name': trained_model.config.name,
                'horizon': trained_model.performance.horizon_name,
                'version': trained_model.version,
                'created_at': trained_model.created_at.isoformat(),
                'performance': asdict(trained_model.performance),
                'feature_names': trained_model.feature_names,
                'target_name': trained_model.target_name
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            self.logger.info(f"Model saved to {filepath}")
            return str(filepath)
            
        except Exception as e:
            raise ModelTrainingError(f"Failed to save model: {e}")
    
    def load_model(self, filepath: str) -> TrainedModel:
        """
        Load trained model from disk.
        
        Args:
            filepath: Path to model file
            
        Returns:
            Loaded trained model
        """
        try:
            with open(filepath, 'rb') as f:
                trained_model = pickle.load(f)
            
            self.logger.info(f"Model loaded from {filepath}")
            return trained_model
            
        except Exception as e:
            raise ModelTrainingError(f"Failed to load model: {e}")
    
    def get_model_performance_summary(self) -> pd.DataFrame:
        """
        Get summary of all model performances.
        
        Returns:
            DataFrame with performance summary
        """
        if not self.performance_history:
            return pd.DataFrame()
        
        data = []
        for perf in self.performance_history:
            row = {
                'model_name': perf.model_name,
                'horizon': perf.horizon_name,
                'training_score': perf.training_score,
                'validation_score': perf.validation_score,
                'test_score': perf.test_score,
                'training_samples': perf.training_samples,
                'test_samples': perf.test_samples,
                'feature_count': perf.feature_count,
                'training_time': perf.training_time,
                'prediction_time': perf.prediction_time,
                'timestamp': perf.timestamp
            }
            # Add metrics
            row.update(perf.metrics)
            data.append(row)
        
        return pd.DataFrame(data)
    
    def _generate_walk_forward_splits(self, 
                                    features: pd.DataFrame, 
                                    horizon_config: TimeHorizon) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Generate walk-forward time series splits."""
        splits = []
        
        # Sort by datetime index
        features_sorted = features.sort_index()
        
        # Calculate split parameters
        training_delta = timedelta(days=horizon_config.training_days)
        testing_delta = timedelta(days=horizon_config.testing_days)
        
        # Find date range
        start_date = features_sorted.index.min()
        end_date = features_sorted.index.max()
        
        self.logger.debug(f"Walk-forward splits for {horizon_config.name}: "
                         f"data from {start_date} to {end_date} "
                         f"({(end_date - start_date).days} days)")
        self.logger.debug(f"Training window: {horizon_config.training_days} days, "
                         f"Testing window: {horizon_config.testing_days} days")
        
        # Generate splits
        current_date = start_date + training_delta
        
        while current_date + testing_delta <= end_date:
            # Define training period
            train_start = current_date - training_delta
            train_end = current_date
            
            # Define testing period
            test_start = current_date
            test_end = current_date + testing_delta
            
            # Get indices
            train_mask = (features_sorted.index >= train_start) & (features_sorted.index < train_end)
            test_mask = (features_sorted.index >= test_start) & (features_sorted.index < test_end)
            
            train_indices = np.where(train_mask)[0]
            test_indices = np.where(test_mask)[0]
            
            self.logger.debug(f"Split candidate: train {train_start} to {train_end} "
                             f"({len(train_indices)} samples), "
                             f"test {test_start} to {test_end} ({len(test_indices)} samples)")
            
            # Only add split if both training and testing have sufficient data
            # Reduce minimum training samples for small datasets
            min_train_samples = min(10, len(features_sorted) // 4)
            if len(train_indices) >= min_train_samples and len(test_indices) >= 1:
                splits.append((train_indices, test_indices))
                self.logger.debug(f"Added split {len(splits)}")
            else:
                self.logger.debug(f"Skipped split: insufficient data "
                                 f"(need {min_train_samples} train, 1 test)")
            
            # Move to next period (advance by testing period)
            current_date += testing_delta
        
        self.logger.debug(f"Generated {len(splits)} walk-forward splits")
        return splits
    
    def _calculate_regression_metrics(self, y_true: Union[pd.Series, np.ndarray], 
                                    y_pred: Union[pd.Series, np.ndarray]) -> Dict[str, float]:
        """Calculate regression metrics."""
        try:
            return {
                'mse': mean_squared_error(y_true, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
                'mae': mean_absolute_error(y_true, y_pred),
                'r2': r2_score(y_true, y_pred),
                'mean_actual': np.mean(y_true),
                'mean_predicted': np.mean(y_pred),
                'std_actual': np.std(y_true),
                'std_predicted': np.std(y_pred)
            }
        except Exception:
            return {
                'mse': 0.0, 'rmse': 0.0, 'mae': 0.0, 'r2': 0.0,
                'mean_actual': 0.0, 'mean_predicted': 0.0,
                'std_actual': 0.0, 'std_predicted': 0.0
            }
    
    def _calculate_classification_metrics(self, y_true: Union[pd.Series, np.ndarray], 
                                        y_pred: Union[pd.Series, np.ndarray]) -> Dict[str, float]:
        """Calculate classification metrics."""
        try:
            return {
                'accuracy': accuracy_score(y_true, y_pred),
                'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
                'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
                'f1': f1_score(y_true, y_pred, average='weighted', zero_division=0),
                'positive_rate': np.mean(y_pred),
                'actual_positive_rate': np.mean(y_true)
            }
        except Exception:
            return {
                'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0,
                'positive_rate': 0.0, 'actual_positive_rate': 0.0
            }
    
    def get_available_models(self) -> Dict[str, ModelConfig]:
        """Get available model configurations."""
        return self.model_configs.copy()
    
    def get_time_horizons(self) -> Dict[str, TimeHorizon]:
        """Get available time horizons."""
        return self.time_horizons.copy()
    
    def get_best_models(self) -> Dict[str, Dict[str, TrainedModel]]:
        """Get best trained models for each horizon."""
        return self.best_models.copy()
    
    def clear_performance_history(self):
        """Clear performance history."""
        self.performance_history.clear()
        self.best_models.clear()