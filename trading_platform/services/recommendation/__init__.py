"""
Recommendation engine services for trading optimization.

This package provides comprehensive recommendation services that combine
statistical analysis, machine learning predictions, and Monte Carlo simulations
to generate optimal trading recommendations.
"""

from .recommendation_service import RecommendationService
from .strategy_evaluator import StrategyEvaluator
from .risk_optimizer import RiskOptimizer
# from .backtesting_service import BacktestingService

__all__ = ['RecommendationService', 'StrategyEvaluator', 'RiskOptimizer']  # , 'BacktestingService']