"""
Prediction service with ensemble models, confidence intervals, and A/B testing.

This service implements prediction generation with model ensembles, caching,
performance optimization, and comprehensive model comparison framework.

Requirements: 4.2, 4.4
"""

import pandas as pd
import numpy as np
import pickle
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Union, Set
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.base import BaseEstimator
from sklearn.ensemble import VotingRegressor, VotingClassifier
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, accuracy_score
from sklearn.preprocessing import StandardScaler
import threading
import time
import os
import scipy.stats as stats

from ...models.trading import ProcessedTrade, TradingRecommendation
from ...interfaces.ml_interfaces import IPredictionService
from .model_trainer import TrainedModel, ModelTrainer


@dataclass
class PredictionResult:
    """Result of a prediction with confidence intervals."""
    prediction: float
    confidence_interval: Tuple[float, float]
    confidence_score: float
    model_name: str
    feature_importance: Dict[str, float]
    prediction_time: float
    timestamp: datetime


@dataclass
class EnsemblePrediction:
    """Result of ensemble prediction combining multiple models."""
    prediction: float
    confidence_interval: Tuple[float, float]
    confidence_score: float
    individual_predictions: List[PredictionResult]
    ensemble_method: str
    weights: Dict[str, float]
    prediction_time: float
    timestamp: datetime


@dataclass
class ModelComparison:
    """Comparison metrics between different models."""
    model_a: str
    model_b: str
    metric_name: str
    model_a_score: float
    model_b_score: float
    difference: float
    statistical_significance: float
    sample_size: int
    comparison_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ABTestResult:
    """Result of A/B testing between models."""
    test_name: str
    model_a: str
    model_b: str
    start_date: datetime
    end_date: datetime
    model_a_predictions: int
    model_b_predictions: int
    model_a_accuracy: float
    model_b_accuracy: float
    winner: str
    confidence_level: float
    metrics: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class PredictionServiceError(Exception):
    """Custom exception for prediction service errors."""
    pass


class PredictionCache:
    """Cache for prediction results with TTL support."""
    
    def __init__(self, ttl_seconds: int = 300):
        """Initialize cache with TTL in seconds."""
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, PredictionResult] = {}
        self.timestamps: Dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def _generate_key(self, features: pd.DataFrame, model_name: str) -> str:
        """Generate cache key from features and model name."""
        features_str = features.to_json(sort_keys=True)
        key_data = f"{model_name}_{features_str}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, features: pd.DataFrame, model_name: str) -> Optional[PredictionResult]:
        """Get cached prediction if available and not expired."""
        with self._lock:
            key = self._generate_key(features, model_name)
            
            if key not in self.cache:
                return None
            
            # Check if expired
            if datetime.now() - self.timestamps[key] > timedelta(seconds=self.ttl_seconds):
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            return self.cache[key]
    
    def set(self, features: pd.DataFrame, model_name: str, prediction: PredictionResult):
        """Cache prediction result."""
        with self._lock:
            key = self._generate_key(features, model_name)
            self.cache[key] = prediction
            self.timestamps[key] = datetime.now()
    
    def clear_expired(self):
        """Clear expired cache entries."""
        with self._lock:
            current_time = datetime.now()
            expired_keys = [
                key for key, timestamp in self.timestamps.items()
                if current_time - timestamp > timedelta(seconds=self.ttl_seconds)
            ]
            
            for key in expired_keys:
                del self.cache[key]
                del self.timestamps[key]
    
    def clear_all(self):
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()


class PredictionService(IPredictionService):
    """
    Prediction service with ensemble models, confidence intervals, and A/B testing.
    
    Provides comprehensive prediction capabilities including:
    - Single model predictions with confidence intervals
    - Ensemble predictions combining multiple models
    - Model comparison framework
    - A/B testing for model performance evaluation
    - Prediction caching and performance optimization
    """
    
    def __init__(self, models_dir: str = "models", cache_ttl_seconds: int = 300,
                 enable_parallel_prediction: bool = True, max_workers: int = 4):
        """
        Initialize prediction service.
        
        Args:
            models_dir: Directory containing trained models
            cache_ttl_seconds: Cache time-to-live in seconds
            enable_parallel_prediction: Enable parallel prediction for ensembles
            max_workers: Maximum number of worker threads for parallel prediction
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        
        # Prediction caching
        self.cache = PredictionCache(ttl_seconds=cache_ttl_seconds)
        
        # Parallel processing
        self.enable_parallel_prediction = enable_parallel_prediction
        self.max_workers = max_workers
        
        # Model storage
        self.loaded_models: Dict[str, TrainedModel] = {}
        
        # History tracking
        self.prediction_history: List[PredictionResult] = []
        self.comparison_history: List[ModelComparison] = []
        self.ab_test_results: List[ABTestResult] = []
        
        # A/B testing
        self.active_ab_tests: Dict[str, Dict[str, Any]] = {}
        
        # Load existing models
        self.reload_models()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def reload_models(self):
        """Reload all models from the models directory."""
        self.loaded_models.clear()
        
        if not self.models_dir.exists():
            return
        
        for model_file in self.models_dir.glob("*.pkl"):
            try:
                with open(model_file, 'rb') as f:
                    trained_model = pickle.load(f)
                    if isinstance(trained_model, TrainedModel):
                        self.loaded_models[trained_model.config.name] = trained_model
                        self.logger.info(f"Loaded model: {trained_model.config.name}")
            except Exception as e:
                self.logger.error(f"Failed to load model {model_file}: {e}")
    
    def predict_single_model(self, features: pd.DataFrame, model_key: str, 
                           calculate_confidence: bool = True) -> PredictionResult:
        """
        Generate prediction using a single model.
        
        Args:
            features: Input features for prediction
            model_key: Key identifying the model to use
            
        Returns:
            PredictionResult with prediction and confidence information
            
        Raises:
            PredictionServiceError: If model not found or prediction fails
        """
        start_time = time.time()
        
        # Check cache first
        cached_result = self.cache.get(features, model_key)
        if cached_result is not None:
            return cached_result
        
        # Validate model exists
        if model_key not in self.loaded_models:
            raise PredictionServiceError(f"Model '{model_key}' not found")
        
        trained_model = self.loaded_models[model_key]
        
        # Validate features
        missing_features = set(trained_model.feature_names) - set(features.columns)
        if missing_features:
            raise PredictionServiceError(f"Missing features: {missing_features}")
        
        try:
            # Prepare features in correct order
            model_features = features[trained_model.feature_names].copy()
            
            # Apply scaling if available
            if trained_model.scaler is not None:
                model_features = pd.DataFrame(
                    trained_model.scaler.transform(model_features),
                    columns=model_features.columns,
                    index=model_features.index
                )
            
            # Make prediction
            prediction = trained_model.model.predict(model_features)[0]
            
            # Calculate confidence interval and score
            confidence_interval, confidence_score = self._calculate_confidence_interval(
                trained_model, model_features
            )
            
            # Get feature importance
            feature_importance = self._get_feature_importance(trained_model)
            
            prediction_time = time.time() - start_time
            
            result = PredictionResult(
                prediction=float(prediction),
                confidence_interval=confidence_interval,
                confidence_score=confidence_score,
                model_name=model_key,
                feature_importance=feature_importance,
                prediction_time=prediction_time,
                timestamp=datetime.now()
            )
            
            # Cache result
            self.cache.set(features, model_key, result)
            
            # Store in history
            self.prediction_history.append(result)
            
            return result
            
        except Exception as e:
            raise PredictionServiceError(f"Prediction failed for model '{model_key}': {e}")
    
    def predict_ensemble(self, features: pd.DataFrame, model_keys: List[str], 
                        ensemble_method: str = 'voting') -> EnsemblePrediction:
        """
        Generate ensemble prediction combining multiple models.
        
        Args:
            features: Input features for prediction
            model_keys: List of model keys to combine
            ensemble_method: Method for combining predictions ('voting', 'weighted')
            
        Returns:
            EnsemblePrediction with combined prediction and individual results
            
        Raises:
            PredictionServiceError: If no models specified or prediction fails
        """
        if not model_keys:
            raise PredictionServiceError("No models specified for ensemble")
        
        start_time = time.time()
        
        # Get individual predictions
        if self.enable_parallel_prediction and len(model_keys) > 1:
            individual_predictions = self._predict_parallel(features, model_keys)
        else:
            individual_predictions = []
            for model_key in model_keys:
                try:
                    pred = self.predict_single_model(features, model_key)
                    individual_predictions.append(pred)
                except PredictionServiceError:
                    # Skip failed models
                    continue
        
        if not individual_predictions:
            raise PredictionServiceError("No successful predictions from ensemble models")
        
        # Combine predictions
        if ensemble_method == 'voting':
            ensemble_prediction = np.mean([p.prediction for p in individual_predictions])
            weights = {p.model_name: 1.0 / len(individual_predictions) 
                      for p in individual_predictions}
        elif ensemble_method == 'weighted':
            # Weight by confidence score
            total_confidence = sum(p.confidence_score for p in individual_predictions)
            if total_confidence > 0:
                weights = {p.model_name: p.confidence_score / total_confidence 
                          for p in individual_predictions}
                ensemble_prediction = sum(p.prediction * weights[p.model_name] 
                                        for p in individual_predictions)
            else:
                # Fallback to equal weighting
                ensemble_prediction = np.mean([p.prediction for p in individual_predictions])
                weights = {p.model_name: 1.0 / len(individual_predictions) 
                          for p in individual_predictions}
        elif ensemble_method == 'stacking':
            # Use stacking method
            return self.predict_ensemble_stacking(features, model_keys)
        else:
            raise PredictionServiceError(f"Unknown ensemble method: {ensemble_method}")
        
        # Calculate ensemble confidence
        ensemble_confidence_score = np.mean([p.confidence_score for p in individual_predictions])
        
        # Calculate ensemble confidence interval
        predictions = [p.prediction for p in individual_predictions]
        ensemble_std = np.std(predictions)
        ensemble_confidence_interval = (
            ensemble_prediction - 1.96 * ensemble_std,
            ensemble_prediction + 1.96 * ensemble_std
        )
        
        prediction_time = time.time() - start_time
        
        return EnsemblePrediction(
            prediction=float(ensemble_prediction),
            confidence_interval=ensemble_confidence_interval,
            confidence_score=ensemble_confidence_score,
            individual_predictions=individual_predictions,
            ensemble_method=ensemble_method,
            weights=weights,
            prediction_time=prediction_time,
            timestamp=datetime.now()
        )
    
    def _predict_parallel(self, features: pd.DataFrame, model_keys: List[str]) -> List[PredictionResult]:
        """Execute predictions in parallel for better performance."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_model = {
                executor.submit(self.predict_single_model, features, model_key): model_key
                for model_key in model_keys
            }
            
            for future in as_completed(future_to_model):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    model_key = future_to_model[future]
                    self.logger.warning(f"Parallel prediction failed for {model_key}: {e}")
        
        return results    
 
    def predict_optimal_conditions(self, current_conditions: Dict[str, Any]) -> Dict[str, float]:
        """
        Predict optimal trading conditions.
        
        Args:
            current_conditions: Dictionary with current market/time conditions
            
        Returns:
            Dictionary with prediction metrics
        """
        # Extract features from conditions
        features_dict = {
            'hour_of_day': current_conditions.get('hour_of_day', datetime.now().hour),
            'day_of_week': current_conditions.get('day_of_week', datetime.now().weekday()),
            'account': current_conditions.get('account', ''),
            'symbol': current_conditions.get('symbol', '')
        }
        
        # Convert to DataFrame
        features = pd.DataFrame([features_dict])
        
        # Select best models for prediction
        best_models = self._select_best_models_for_prediction(
            current_conditions.get('account', ''),
            current_conditions.get('symbol', '')
        )
        
        if not best_models:
            return {
                'profit_probability': 0.5,
                'expected_return': 0.0,
                'confidence_score': 0.0,
                'risk_score': 1.0,
                'prediction_timestamp': datetime.now().isoformat()
            }
        
        try:
            # Get ensemble prediction
            ensemble_result = self.predict_ensemble(features, best_models, 'weighted')
            
            # Convert prediction to probability
            profit_probability = self._prediction_to_probability(ensemble_result.prediction)
            
            # Calculate risk score (inverse of confidence)
            risk_score = 1.0 - ensemble_result.confidence_score
            
            return {
                'profit_probability': profit_probability,
                'expected_return': ensemble_result.prediction,
                'confidence_score': ensemble_result.confidence_score,
                'risk_score': risk_score,
                'prediction_timestamp': ensemble_result.timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Optimal conditions prediction failed: {e}")
            return {
                'profit_probability': 0.5,
                'expected_return': 0.0,
                'confidence_score': 0.0,
                'risk_score': 1.0,
                'prediction_timestamp': datetime.now().isoformat()
            }
    
    def generate_recommendation(self, account: str, symbol: str, 
                             current_time: datetime) -> TradingRecommendation:
        """
        Generate trading recommendation for specific account and time.
        
        Args:
            account: Trading account name
            symbol: Trading symbol
            current_time: Current timestamp
            
        Returns:
            TradingRecommendation with action and reasoning
        """
        conditions = {
            'account': account,
            'symbol': symbol,
            'hour_of_day': current_time.hour,
            'day_of_week': current_time.weekday(),
            'timestamp': current_time
        }
        
        prediction = self.predict_optimal_conditions(conditions)
        
        # Determine action based on prediction
        profit_probability = prediction['profit_probability']
        confidence_score = prediction['confidence_score']
        
        # Decision thresholds
        if profit_probability > 0.6 and confidence_score > 0.7:
            action = 'TRADE'
            reasoning = f"High profit probability ({profit_probability:.2f}) with good confidence ({confidence_score:.2f})"
        elif profit_probability > 0.55 and confidence_score > 0.8:
            action = 'TRADE'
            reasoning = f"Moderate profit probability ({profit_probability:.2f}) with high confidence ({confidence_score:.2f})"
        else:
            action = 'AVOID'
            reasoning = f"Low profit probability ({profit_probability:.2f}) or confidence ({confidence_score:.2f})"
        
        return TradingRecommendation(
            timestamp=current_time,
            account_name=account,
            symbol=symbol,
            recommended_action=action,
            confidence_score=confidence_score,
            expected_return=prediction['expected_return'],
            expected_risk=prediction['risk_score'],
            reasoning=reasoning,
            hour_of_day=current_time.hour,
            day_of_week=current_time.weekday(),
            historical_win_rate=profit_probability,
            avg_profit_this_time=prediction['expected_return']
        )
    
    def calculate_prediction_confidence(self, prediction: Dict[str, float]) -> float:
        """
        Calculate confidence score for predictions.
        
        Args:
            prediction: Dictionary with prediction metrics
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence_score = prediction.get('confidence_score', 0.0)
        profit_probability = prediction.get('profit_probability', 0.5)
        risk_score = prediction.get('risk_score', 1.0)
        
        # Combine multiple factors for overall confidence
        # Higher profit probability increases confidence
        prob_factor = abs(profit_probability - 0.5) * 2  # 0 to 1
        
        # Lower risk increases confidence
        risk_factor = 1.0 - risk_score
        
        # Weighted combination
        overall_confidence = (
            0.5 * confidence_score +
            0.3 * prob_factor +
            0.2 * risk_factor
        )
        
        return max(0.0, min(1.0, overall_confidence))
    
    def compare_models(self, test_features: pd.DataFrame, test_target: pd.Series, 
                      model_keys: List[str], metrics: List[str] = None) -> List[ModelComparison]:
        """
        Compare performance of different models.
        
        Args:
            test_features: Features for testing
            test_target: Target values for testing
            model_keys: List of model keys to compare
            metrics: List of metrics to compare ('mse', 'r2', 'accuracy')
            
        Returns:
            List of ModelComparison objects
        """
        if metrics is None:
            metrics = ['mse', 'r2', 'accuracy']
        
        comparisons = []
        
        # Get predictions from all models
        model_predictions = {}
        for model_key in model_keys:
            if model_key not in self.loaded_models:
                continue
            
            try:
                predictions = []
                for i in range(len(test_features)):
                    features_row = test_features.iloc[[i]]
                    pred_result = self.predict_single_model(features_row, model_key)
                    predictions.append(pred_result.prediction)
                
                model_predictions[model_key] = np.array(predictions)
            except Exception as e:
                self.logger.warning(f"Failed to get predictions for {model_key}: {e}")
                continue
        
        # Compare all pairs of models
        model_names = list(model_predictions.keys())
        for i in range(len(model_names)):
            for j in range(i + 1, len(model_names)):
                model_a = model_names[i]
                model_b = model_names[j]
                
                pred_a = model_predictions[model_a]
                pred_b = model_predictions[model_b]
                
                for metric in metrics:
                    score_a = self._calculate_metric(test_target, pred_a, metric)
                    score_b = self._calculate_metric(test_target, pred_b, metric)
                    
                    difference = score_a - score_b
                    significance = self._calculate_statistical_significance(
                        test_target, pred_a, pred_b, metric
                    )
                    
                    comparison = ModelComparison(
                        model_a=model_a,
                        model_b=model_b,
                        metric_name=metric,
                        model_a_score=score_a,
                        model_b_score=score_b,
                        difference=difference,
                        statistical_significance=significance,
                        sample_size=len(test_target)
                    )
                    
                    comparisons.append(comparison)
        
        # Store in history
        self.comparison_history.extend(comparisons)
        
        return comparisons
    
    def start_ab_test(self, test_name: str, model_a: str, model_b: str,
                     traffic_split: float = 0.5, duration_days: int = 7) -> str:
        """
        Start A/B test between two models.
        
        Args:
            test_name: Name for the A/B test
            model_a: First model to test
            model_b: Second model to test
            traffic_split: Fraction of traffic for model A (0.0 to 1.0)
            duration_days: Duration of test in days
            
        Returns:
            Test ID for tracking
            
        Raises:
            PredictionServiceError: If test already exists or models not found
        """
        if test_name in self.active_ab_tests:
            raise PredictionServiceError(f"A/B test '{test_name}' already active")
        
        if model_a not in self.loaded_models or model_b not in self.loaded_models:
            raise PredictionServiceError("Both models must be loaded before starting A/B test")
        
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)
        
        test_config = {
            'model_a': model_a,
            'model_b': model_b,
            'traffic_split': traffic_split,
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
            'model_a_predictions': 0,
            'model_b_predictions': 0,
            'model_a_results': [],
            'model_b_results': []
        }
        
        self.active_ab_tests[test_name] = test_config
        
        self.logger.info(f"Started A/B test '{test_name}': {model_a} vs {model_b}")
        
        return test_name
    
    def predict_with_ab_test(self, features: pd.DataFrame, test_name: str) -> Tuple[PredictionResult, str]:
        """
        Make prediction using A/B test configuration.
        
        Args:
            features: Input features
            test_name: Name of A/B test
            
        Returns:
            Tuple of (prediction result, model used)
            
        Raises:
            PredictionServiceError: If test not found or expired
        """
        if test_name not in self.active_ab_tests:
            raise PredictionServiceError(f"A/B test '{test_name}' not found")
        
        test_config = self.active_ab_tests[test_name]
        
        # Check if test has expired
        if datetime.now() > test_config['end_date']:
            test_config['status'] = 'expired'
            raise PredictionServiceError(f"A/B test '{test_name}' has expired")
        
        # Select model based on traffic split
        if np.random.random() < test_config['traffic_split']:
            model_to_use = test_config['model_a']
            result_key = 'model_a_results'
            count_key = 'model_a_predictions'
        else:
            model_to_use = test_config['model_b']
            result_key = 'model_b_results'
            count_key = 'model_b_predictions'
        
        # Make prediction
        prediction_result = self.predict_single_model(features, model_to_use)
        
        # Update test tracking
        test_config[count_key] += 1
        test_config[result_key].append({
            'prediction': prediction_result.prediction,
            'confidence': prediction_result.confidence_score,
            'timestamp': prediction_result.timestamp
        })
        
        return prediction_result, model_to_use
    
    def end_ab_test(self, test_name: str) -> ABTestResult:
        """
        End A/B test and return results.
        
        Args:
            test_name: Name of A/B test to end
            
        Returns:
            ABTestResult with test outcomes
            
        Raises:
            PredictionServiceError: If test not found
        """
        if test_name not in self.active_ab_tests:
            raise PredictionServiceError(f"A/B test '{test_name}' not found")
        
        test_config = self.active_ab_tests[test_name]
        
        # Calculate accuracies
        model_a_accuracy = self._calculate_ab_test_accuracy(test_config['model_a_results'])
        model_b_accuracy = self._calculate_ab_test_accuracy(test_config['model_b_results'])
        
        # Determine winner
        if model_a_accuracy > model_b_accuracy:
            winner = test_config['model_a']
        elif model_b_accuracy > model_a_accuracy:
            winner = test_config['model_b']
        else:
            winner = 'tie'
        
        # Calculate confidence level
        confidence_level = self._calculate_ab_test_confidence(
            test_config['model_a_results'],
            test_config['model_b_results']
        )
        
        # Create result
        result = ABTestResult(
            test_name=test_name,
            model_a=test_config['model_a'],
            model_b=test_config['model_b'],
            start_date=test_config['start_date'],
            end_date=test_config['end_date'],
            model_a_predictions=test_config['model_a_predictions'],
            model_b_predictions=test_config['model_b_predictions'],
            model_a_accuracy=model_a_accuracy,
            model_b_accuracy=model_b_accuracy,
            winner=winner,
            confidence_level=confidence_level,
            metrics={
                'model_a_avg_confidence': np.mean([r['confidence'] for r in test_config['model_a_results']]) if test_config['model_a_results'] else 0,
                'model_b_avg_confidence': np.mean([r['confidence'] for r in test_config['model_b_results']]) if test_config['model_b_results'] else 0,
                'total_predictions': test_config['model_a_predictions'] + test_config['model_b_predictions']
            }
        )
        
        # Store result and remove from active tests
        self.ab_test_results.append(result)
        del self.active_ab_tests[test_name]
        
        self.logger.info(f"Ended A/B test '{test_name}': Winner = {winner}")
        
        return result
    
    def get_model_performance_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get performance summary for all models based on prediction history."""
        summary = {}
        
        for prediction in self.prediction_history:
            model_name = prediction.model_name
            
            if model_name not in summary:
                summary[model_name] = {
                    'total_predictions': 0,
                    'avg_confidence': 0.0,
                    'avg_prediction_time': 0.0,
                    'predictions': []
                }
            
            summary[model_name]['total_predictions'] += 1
            summary[model_name]['predictions'].append(prediction)
        
        # Calculate averages
        for model_name, stats in summary.items():
            predictions = stats['predictions']
            stats['avg_confidence'] = np.mean([p.confidence_score for p in predictions])
            stats['avg_prediction_time'] = np.mean([p.prediction_time for p in predictions])
            stats['prediction_std'] = np.std([p.prediction for p in predictions])
            del stats['predictions']  # Remove raw data
        
        return summary
    
    def clear_cache(self):
        """Clear prediction cache."""
        self.cache.clear_all()
    
    # Helper methods
    
    def _calculate_confidence_interval(self, trained_model: TrainedModel, 
                                     features: pd.DataFrame) -> Tuple[Tuple[float, float], float]:
        """Calculate confidence interval and score for prediction."""
        # Use model's validation performance to estimate uncertainty
        validation_score = trained_model.performance.validation_score
        test_score = trained_model.performance.test_score
        
        # Estimate standard deviation from performance metrics
        if 'std' in trained_model.performance.metrics:
            std_dev = trained_model.performance.metrics['std']
        else:
            # Fallback: estimate from score difference
            std_dev = abs(validation_score - test_score) * 2
        
        # Make prediction
        prediction = trained_model.model.predict(features)[0]
        
        # Calculate 95% confidence interval
        margin = 1.96 * std_dev
        confidence_interval = (prediction - margin, prediction + margin)
        
        # Confidence score based on model performance
        confidence_score = min(validation_score, test_score)
        
        return confidence_interval, confidence_score
    
    def _get_feature_importance(self, trained_model: TrainedModel) -> Dict[str, float]:
        """Get feature importance from trained model."""
        importance_dict = {}
        
        try:
            if hasattr(trained_model.model, 'feature_importances_'):
                importances = trained_model.model.feature_importances_
                for i, feature_name in enumerate(trained_model.feature_names):
                    importance_dict[feature_name] = float(importances[i])
            elif hasattr(trained_model.model, 'coef_'):
                # For linear models, use absolute coefficients
                coefs = np.abs(trained_model.model.coef_)
                total = np.sum(coefs)
                if total > 0:
                    for i, feature_name in enumerate(trained_model.feature_names):
                        importance_dict[feature_name] = float(coefs[i] / total)
        except Exception as e:
            self.logger.warning(f"Could not extract feature importance: {e}")
        
        return importance_dict
    
    def _select_best_models_for_prediction(self, account: str, symbol: str) -> List[str]:
        """Select best models for given account and symbol."""
        # For now, return all available models
        # In a more sophisticated implementation, this would select models
        # based on their performance for specific account/symbol combinations
        return list(self.loaded_models.keys())
    
    def _prediction_to_probability(self, prediction: float) -> float:
        """Convert prediction value to probability."""
        # Assuming prediction is profit/loss, convert to probability
        # This is a simple sigmoid transformation
        return 1.0 / (1.0 + np.exp(-prediction * 5))  # Scale factor of 5
    
    def _calculate_metric(self, actual: pd.Series, predicted: Union[np.ndarray, float], 
                         metric: str) -> float:
        """Calculate specific metric for model comparison."""
        if isinstance(predicted, (int, float)):
            predicted = np.full(len(actual), predicted)
        
        if metric == 'mse':
            return mean_squared_error(actual, predicted)
        elif metric == 'mae':
            return mean_absolute_error(actual, predicted)
        elif metric == 'r2':
            return r2_score(actual, predicted)
        elif metric == 'accuracy':
            # For regression, use threshold-based accuracy
            threshold = 0.1  # Within 10% is considered accurate
            return np.mean(np.abs(actual - predicted) <= threshold)
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def _calculate_statistical_significance(self, actual: pd.Series, pred_a: np.ndarray, 
                                          pred_b: np.ndarray, metric: str) -> float:
        """Calculate statistical significance of difference between models."""
        try:
            # Calculate metric for both predictions
            score_a = self._calculate_metric(actual, pred_a, metric)
            score_b = self._calculate_metric(actual, pred_b, metric)
            
            # Simple t-test approximation
            # In practice, you might want more sophisticated statistical tests
            errors_a = np.abs(actual - pred_a)
            errors_b = np.abs(actual - pred_b)
            
            if len(errors_a) < 3 or len(errors_b) < 3:
                return 0.5  # Not enough data
            
            t_stat, p_value = stats.ttest_ind(errors_a, errors_b)
            
            return 1.0 - p_value  # Convert p-value to significance score
            
        except Exception:
            return 0.5  # Default to no significance
    
    def _calculate_ab_test_accuracy(self, results: List[Dict[str, Any]]) -> float:
        """Calculate accuracy for A/B test results."""
        if not results:
            return 0.0
        
        return np.mean([r['confidence'] for r in results])
    
    def _calculate_ab_test_confidence(self, results_a: List[Dict[str, Any]], 
                                    results_b: List[Dict[str, Any]]) -> float:
        """Calculate confidence level for A/B test comparison."""
        if len(results_a) < 5 or len(results_b) < 5:
            return 0.5  # Not enough data for confidence
        
        try:
            scores_a = [r['confidence'] for r in results_a]
            scores_b = [r['confidence'] for r in results_b]
            
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b)
            
            return 1.0 - p_value  # Convert p-value to confidence level
            
        except Exception:
            return 0.5  # Default confidence    
   
    def get_prediction_statistics(self) -> Dict[str, Any]:
        """Get comprehensive prediction statistics."""
        if not self.prediction_history:
            return {
                'total_predictions': 0,
                'models_used': [],
                'model_usage_distribution': {},
                'avg_prediction_time': 0.0,
                'avg_confidence_score': 0.0,
                'cache_hit_rate': 0.0
            }
        
        # Calculate statistics
        total_predictions = len(self.prediction_history)
        models_used = list(set(p.model_name for p in self.prediction_history))
        
        # Model usage distribution
        model_counts = {}
        for prediction in self.prediction_history:
            model_counts[prediction.model_name] = model_counts.get(prediction.model_name, 0) + 1
        
        model_usage_distribution = {
            model: count / total_predictions 
            for model, count in model_counts.items()
        }
        
        # Average metrics
        avg_prediction_time = np.mean([p.prediction_time for p in self.prediction_history])
        avg_confidence_score = np.mean([p.confidence_score for p in self.prediction_history])
        
        # Cache hit rate (simplified calculation)
        cache_hit_rate = 0.0  # Would need to track cache hits vs misses
        
        return {
            'total_predictions': total_predictions,
            'models_used': models_used,
            'model_usage_distribution': model_usage_distribution,
            'avg_prediction_time': avg_prediction_time,
            'avg_confidence_score': avg_confidence_score,
            'cache_hit_rate': cache_hit_rate
        }
    
    def validate_model_compatibility(self, model_keys: List[str]) -> Dict[str, Any]:
        """Validate compatibility between models for ensemble use."""
        if not model_keys:
            return {
                'compatible': False,
                'compatibility_score': 0.0,
                'common_features': [],
                'feature_overlap_ratio': 0.0,
                'recommendations': ['No models provided']
            }
        
        # Get feature sets for each model
        feature_sets = []
        for model_key in model_keys:
            if model_key in self.loaded_models:
                feature_sets.append(set(self.loaded_models[model_key].feature_names))
        
        if not feature_sets:
            return {
                'compatible': False,
                'compatibility_score': 0.0,
                'common_features': [],
                'feature_overlap_ratio': 0.0,
                'recommendations': ['No valid models found']
            }
        
        # Find common features
        common_features = set.intersection(*feature_sets) if feature_sets else set()
        all_features = set.union(*feature_sets) if feature_sets else set()
        
        # Calculate compatibility metrics
        feature_overlap_ratio = len(common_features) / len(all_features) if all_features else 0.0
        compatibility_score = feature_overlap_ratio
        compatible = feature_overlap_ratio > 0.5  # At least 50% overlap
        
        # Generate recommendations
        recommendations = []
        if not compatible:
            recommendations.append("Low feature overlap - consider feature engineering")
        if len(common_features) < 3:
            recommendations.append("Very few common features - ensemble may not be effective")
        if compatible:
            recommendations.append("Models are compatible for ensemble use")
        
        return {
            'compatible': compatible,
            'compatibility_score': compatibility_score,
            'common_features': list(common_features),
            'feature_overlap_ratio': feature_overlap_ratio,
            'recommendations': recommendations
        }
    
    def create_ensemble_model(self, model_keys: List[str], ensemble_type: str = 'voting', 
                            name: str = None) -> str:
        """Create and register an ensemble model."""
        if not hasattr(self, 'ensemble_models'):
            self.ensemble_models = {}
        
        if name is None:
            name = f"ensemble_{len(self.ensemble_models) + 1}"
        
        # Validate models exist
        valid_models = [key for key in model_keys if key in self.loaded_models]
        if not valid_models:
            raise PredictionServiceError("No valid models found for ensemble")
        
        # Create ensemble configuration
        ensemble_config = {
            'name': name,
            'model_keys': valid_models,
            'ensemble_type': ensemble_type,
            'created_at': datetime.now(),
            'performance_history': []
        }
        
        self.ensemble_models[name] = ensemble_config
        
        self.logger.info(f"Created ensemble model '{name}' with {len(valid_models)} models")
        
        return name
    
    def get_ensemble_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered ensemble models."""
        if not hasattr(self, 'ensemble_models'):
            self.ensemble_models = {}
        
        return self.ensemble_models.copy()
    
    def predict_ensemble_stacking(self, features: pd.DataFrame, model_keys: List[str]) -> EnsemblePrediction:
        """Generate stacking ensemble prediction."""
        start_time = time.time()
        
        # Get individual predictions
        individual_predictions = []
        for model_key in model_keys:
            try:
                pred = self.predict_single_model(features, model_key)
                individual_predictions.append(pred)
            except PredictionServiceError:
                continue
        
        if not individual_predictions:
            raise PredictionServiceError("No successful predictions from ensemble models")
        
        # Simple stacking: weighted average based on historical performance
        weights = {}
        total_weight = 0
        
        for pred in individual_predictions:
            model_name = pred.model_name
            if model_name in self.loaded_models:
                # Use test score as weight
                weight = self.loaded_models[model_name].performance.test_score
                weights[model_name] = weight
                total_weight += weight
        
        # Normalize weights
        if total_weight > 0:
            for model_name in weights:
                weights[model_name] /= total_weight
        else:
            # Equal weights fallback
            equal_weight = 1.0 / len(individual_predictions)
            weights = {pred.model_name: equal_weight for pred in individual_predictions}
        
        # Calculate stacked prediction
        stacked_prediction = sum(pred.prediction * weights[pred.model_name] 
                               for pred in individual_predictions)
        
        # Calculate ensemble confidence
        ensemble_confidence_score = np.mean([pred.confidence_score for pred in individual_predictions])
        
        # Calculate ensemble confidence interval
        predictions = [pred.prediction for pred in individual_predictions]
        ensemble_std = np.std(predictions)
        ensemble_confidence_interval = (
            stacked_prediction - 1.96 * ensemble_std,
            stacked_prediction + 1.96 * ensemble_std
        )
        
        prediction_time = time.time() - start_time
        
        return EnsemblePrediction(
            prediction=float(stacked_prediction),
            confidence_interval=ensemble_confidence_interval,
            confidence_score=ensemble_confidence_score,
            individual_predictions=individual_predictions,
            ensemble_method='stacking',
            weights=weights,
            prediction_time=prediction_time,
            timestamp=datetime.now()
        )