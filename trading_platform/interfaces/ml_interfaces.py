"""
Machine learning and prediction interfaces.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from datetime import datetime
import pandas as pd
from sklearn.base import BaseEstimator

from ..models.trading import ProcessedTrade, TradingRecommendation


class IFeatureEngineer(ABC):
    """Interface for feature engineering from trading data."""
    
    @abstractmethod
    def extract_features(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """Extract features from processed trades for ML models."""
        pass
    
    @abstractmethod
    def create_temporal_features(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """Create time-based features (hour, day, week patterns)."""
        pass
    
    @abstractmethod
    def create_technical_indicators(self, trades: List[ProcessedTrade]) -> pd.DataFrame:
        """Create technical indicator features."""
        pass


class IModelTrainer(ABC):
    """Interface for ML model training and validation."""
    
    @abstractmethod
    def train_model(self, features: pd.DataFrame, target: pd.Series, 
                   model_type: str = "random_forest_reg") -> Any:
        """Train a machine learning model."""
        pass
    
    @abstractmethod
    def walk_forward_validation(self, features: pd.DataFrame, target: pd.Series, 
                              model_type: str, horizon: str = 'medium_term') -> Dict[str, Any]:
        """Perform walk-forward validation to prevent overfitting."""
        pass
    
    @abstractmethod
    def evaluate_model(self, model: BaseEstimator, test_features: pd.DataFrame, 
                      test_target: pd.Series) -> Dict[str, float]:
        """Evaluate model performance on test data."""
        pass


class IPredictionService(ABC):
    """Interface for generating predictions and recommendations."""
    
    @abstractmethod
    def predict_optimal_conditions(self, current_conditions: Dict[str, Any]) -> Dict[str, float]:
        """Predict optimal trading conditions."""
        pass
    
    @abstractmethod
    def generate_recommendation(self, account: str, symbol: str, 
                             current_time: datetime) -> TradingRecommendation:
        """Generate trading recommendation for specific account and time."""
        pass
    
    @abstractmethod
    def calculate_prediction_confidence(self, prediction: Dict[str, float]) -> float:
        """Calculate confidence score for predictions."""
        pass
    
    @abstractmethod
    def predict_single_model(self, features: pd.DataFrame, model_key: str) -> Any:
        """Generate prediction using a single model."""
        pass
    
    @abstractmethod
    def predict_ensemble(self, features: pd.DataFrame, model_keys: List[str]) -> Any:
        """Generate ensemble prediction combining multiple models."""
        pass
    
    @abstractmethod
    def compare_models(self, test_features: pd.DataFrame, test_target: pd.Series, 
                      model_keys: List[str]) -> List[Any]:
        """Compare performance of different models."""
        pass
    
    @abstractmethod
    def start_ab_test(self, test_name: str, model_a: str, model_b: str) -> str:
        """Start A/B test between two models."""
        pass
    
    @abstractmethod
    def end_ab_test(self, test_name: str) -> Any:
        """End A/B test and return results."""
        pass