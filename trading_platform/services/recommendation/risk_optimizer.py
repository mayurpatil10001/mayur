"""
Risk-return optimization service for trading recommendations.

This service implements optimization algorithms that balance profit maximization
with volatility minimization based on user-configurable risk tolerance settings.
It also provides portfolio allocation optimization across accounts and assets.

Requirements: 6.2, 6.3
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm
import warnings

from ...models.trading import ProcessedTrade, TradingRecommendation, PerformanceMetrics, Account


class OptimizationMethod(Enum):
    """Optimization methods for risk-return optimization."""
    MEAN_VARIANCE = "mean_variance"
    SHARPE_RATIO = "sharpe_ratio"
    KELLY_CRITERION = "kelly_criterion"
    RISK_PARITY = "risk_parity"
    MAXIMUM_DIVERSIFICATION = "max_diversification"


class RiskTolerance(Enum):
    """Risk tolerance levels."""
    CONSERVATIVE = 0.2
    MODERATE = 0.5
    AGGRESSIVE = 0.8
    VERY_AGGRESSIVE = 1.0


@dataclass
class TradingOption:
    """Represents a trading option with risk-return characteristics."""
    account_name: str
    symbol: str
    expected_return: float
    expected_risk: float  # Standard deviation
    confidence_score: float
    historical_sharpe: float
    max_drawdown: float
    win_rate: float
    trade_frequency: float  # Trades per day
    correlation_matrix: Optional[np.ndarray] = None
    
    @property
    def risk_adjusted_return(self) -> float:
        """Calculate risk-adjusted return (Sharpe-like ratio)."""
        return self.expected_return / self.expected_risk if self.expected_risk > 0 else 0.0
    
    @property
    def kelly_fraction(self) -> float:
        """Calculate Kelly criterion fraction."""
        if self.expected_risk == 0:
            return 0.0
        
        # Kelly = (bp - q) / b where b = odds, p = win prob, q = lose prob
        # Simplified for continuous returns: Kelly ≈ μ / σ²
        return self.expected_return / (self.expected_risk ** 2)


@dataclass
class RiskToleranceSettings:
    """User-configurable risk tolerance settings."""
    risk_level: float  # 0.0 (very conservative) to 1.0 (very aggressive)
    max_portfolio_risk: float  # Maximum acceptable portfolio volatility
    min_sharpe_ratio: float  # Minimum acceptable Sharpe ratio
    max_drawdown_tolerance: float  # Maximum acceptable drawdown
    diversification_preference: float  # Weight given to diversification (0.0 to 1.0)
    return_preference: float  # Weight given to returns vs risk (0.0 to 1.0)
    volatility_penalty: float  # Penalty factor for volatility
    concentration_limit: float  # Maximum concentration in single position
    
    def __post_init__(self):
        """Validate risk tolerance settings."""
        if not 0.0 <= self.risk_level <= 1.0:
            raise ValueError("Risk level must be between 0.0 and 1.0")
        if not 0.0 <= self.diversification_preference <= 1.0:
            raise ValueError("Diversification preference must be between 0.0 and 1.0")
        if not 0.0 <= self.return_preference <= 1.0:
            raise ValueError("Return preference must be between 0.0 and 1.0")
        if self.max_portfolio_risk <= 0:
            raise ValueError("Maximum portfolio risk must be positive")
        if self.max_drawdown_tolerance <= 0:
            raise ValueError("Maximum drawdown tolerance must be positive")


@dataclass
class OptimizationConstraints:
    """Constraints for portfolio optimization."""
    max_position_size: float = 1.0  # Maximum allocation to single position
    min_position_size: float = 0.0  # Minimum allocation to single position
    max_total_risk: float = 0.2  # Maximum portfolio risk
    min_diversification: int = 1  # Minimum number of positions
    max_concentration: float = 0.5  # Maximum concentration in single asset
    target_return: Optional[float] = None  # Target return constraint
    max_drawdown_limit: float = 0.25  # Maximum acceptable drawdown
    allow_short_positions: bool = False  # Allow negative weights (short positions)
    transaction_cost_rate: float = 0.001  # Transaction cost as percentage of trade value
    rebalancing_frequency: int = 30  # Days between rebalancing


@dataclass
class OptimizationResult:
    """Result from portfolio optimization."""
    optimal_weights: Dict[str, float]  # Account-symbol -> weight
    expected_portfolio_return: float
    expected_portfolio_risk: float
    sharpe_ratio: float
    diversification_ratio: float
    max_weight: float
    optimization_method: OptimizationMethod
    risk_tolerance: float
    constraints_satisfied: bool
    optimization_success: bool
    optimization_message: str
    timestamp: datetime = field(default_factory=datetime.now)


class RiskOptimizerError(Exception):
    """Exception raised by risk optimizer."""
    pass


class RiskOptimizer:
    """
    Risk-return optimization service for trading recommendations.
    
    This service implements various optimization algorithms to balance profit
    maximization with volatility minimization, supporting user-configurable
    risk tolerance and portfolio allocation optimization.
    """
    
    def __init__(self, 
                 default_risk_tolerance: float = 0.5,
                 default_optimization_method: OptimizationMethod = OptimizationMethod.SHARPE_RATIO,
                 risk_free_rate: float = 0.02,
                 user_risk_settings: Optional[RiskToleranceSettings] = None):
        """
        Initialize the risk optimizer.
        
        Args:
            default_risk_tolerance: Default risk tolerance (0.0 to 1.0)
            default_optimization_method: Default optimization method
            risk_free_rate: Risk-free rate for Sharpe ratio calculations
            user_risk_settings: User-configurable risk tolerance settings
        """
        self.logger = logging.getLogger(__name__)
        self.default_risk_tolerance = default_risk_tolerance
        self.default_optimization_method = default_optimization_method
        self.risk_free_rate = risk_free_rate
        self.user_risk_settings = user_risk_settings
        
        # Optimization history for performance tracking
        self.optimization_history: List[OptimizationResult] = []
        
        # Risk tolerance mappings
        self.risk_tolerance_params = {
            RiskTolerance.CONSERVATIVE: {
                'max_risk': 0.1,
                'min_sharpe': 1.0,
                'max_drawdown': 0.15,
                'diversification_weight': 0.4
            },
            RiskTolerance.MODERATE: {
                'max_risk': 0.2,
                'min_sharpe': 0.5,
                'max_drawdown': 0.25,
                'diversification_weight': 0.3
            },
            RiskTolerance.AGGRESSIVE: {
                'max_risk': 0.35,
                'min_sharpe': 0.3,
                'max_drawdown': 0.4,
                'diversification_weight': 0.2
            },
            RiskTolerance.VERY_AGGRESSIVE: {
                'max_risk': 0.5,
                'min_sharpe': 0.2,
                'max_drawdown': 0.6,
                'diversification_weight': 0.1
            }
        }
    
    def optimize_single_recommendation(self, 
                                     trading_options: List[TradingOption],
                                     risk_tolerance: float = None,
                                     optimization_method: OptimizationMethod = None) -> TradingOption:
        """
        Optimize selection of single best trading option.
        
        Args:
            trading_options: List of available trading options
            risk_tolerance: Risk tolerance level (0.0 to 1.0)
            optimization_method: Optimization method to use
            
        Returns:
            Optimal trading option
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        optimization_method = optimization_method or self.default_optimization_method
        
        try:
            self.logger.info(f"Optimizing single recommendation from {len(trading_options)} options")
            
            # Calculate optimization scores for each option
            scores = []
            for option in trading_options:
                score = self._calculate_option_score(option, risk_tolerance, optimization_method)
                scores.append((score, option))
            
            # Sort by score (higher is better)
            scores.sort(key=lambda x: x[0], reverse=True)
            
            best_option = scores[0][1]
            
            self.logger.info(f"Selected optimal option: {best_option.account_name}-{best_option.symbol} "
                           f"with score {scores[0][0]:.4f}")
            
            return best_option
            
        except Exception as e:
            self.logger.error(f"Single recommendation optimization failed: {e}")
            raise RiskOptimizerError(f"Optimization failed: {e}")
    
    def optimize_portfolio_allocation(self, 
                                    trading_options: List[TradingOption],
                                    risk_tolerance: float = None,
                                    optimization_method: OptimizationMethod = None,
                                    constraints: OptimizationConstraints = None) -> OptimizationResult:
        """
        Optimize portfolio allocation across multiple accounts and assets.
        
        Args:
            trading_options: List of available trading options
            risk_tolerance: Risk tolerance level (0.0 to 1.0)
            optimization_method: Optimization method to use
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with optimal weights and metrics
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        if len(trading_options) == 1:
            # Single option - return 100% allocation
            option = trading_options[0]
            key = f"{option.account_name}-{option.symbol}"
            return OptimizationResult(
                optimal_weights={key: 1.0},
                expected_portfolio_return=option.expected_return,
                expected_portfolio_risk=option.expected_risk,
                sharpe_ratio=option.risk_adjusted_return,
                diversification_ratio=1.0,
                max_weight=1.0,
                optimization_method=optimization_method or self.default_optimization_method,
                risk_tolerance=risk_tolerance or self.default_risk_tolerance,
                constraints_satisfied=True,
                optimization_success=True,
                optimization_message="Single option - 100% allocation"
            )
        
        risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        optimization_method = optimization_method or self.default_optimization_method
        constraints = constraints or self.create_constraints_from_risk_settings()
        
        try:
            self.logger.info(f"Optimizing portfolio allocation for {len(trading_options)} options")
            
            # Prepare data for optimization
            returns = np.array([opt.expected_return for opt in trading_options])
            risks = np.array([opt.expected_risk for opt in trading_options])
            
            # Build correlation matrix if not provided
            correlation_matrix = self._build_correlation_matrix(trading_options)
            
            # Calculate covariance matrix
            covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
            
            # Perform optimization based on method
            if optimization_method == OptimizationMethod.MEAN_VARIANCE:
                result = self._optimize_mean_variance(returns, covariance_matrix, risk_tolerance, constraints)
            elif optimization_method == OptimizationMethod.SHARPE_RATIO:
                result = self._optimize_sharpe_ratio(returns, covariance_matrix, constraints)
            elif optimization_method == OptimizationMethod.KELLY_CRITERION:
                result = self._optimize_kelly_criterion(trading_options, constraints)
            elif optimization_method == OptimizationMethod.RISK_PARITY:
                result = self._optimize_risk_parity(covariance_matrix, constraints)
            elif optimization_method == OptimizationMethod.MAXIMUM_DIVERSIFICATION:
                result = self._optimize_maximum_diversification(risks, correlation_matrix, constraints)
            else:
                raise RiskOptimizerError(f"Unsupported optimization method: {optimization_method}")
            
            # Create result with option keys
            option_keys = [f"{opt.account_name}-{opt.symbol}" for opt in trading_options]
            optimal_weights = dict(zip(option_keys, result['weights']))
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(result['weights'], returns)
            portfolio_risk = np.sqrt(np.dot(result['weights'], np.dot(covariance_matrix, result['weights'])))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0.0
            
            # Calculate diversification ratio
            weighted_avg_risk = np.dot(result['weights'], risks)
            diversification_ratio = weighted_avg_risk / portfolio_risk if portfolio_risk > 0 else 1.0
            
            optimization_result = OptimizationResult(
                optimal_weights=optimal_weights,
                expected_portfolio_return=portfolio_return,
                expected_portfolio_risk=portfolio_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                max_weight=np.max(result['weights']),
                optimization_method=optimization_method,
                risk_tolerance=risk_tolerance,
                constraints_satisfied=result.get('constraints_satisfied', True),
                optimization_success=result.get('success', True),
                optimization_message=result.get('message', 'Optimization completed successfully')
            )
            
            # Store in history
            self.optimization_history.append(optimization_result)
            
            self.logger.info(f"Portfolio optimization completed: Return={portfolio_return:.4f}, "
                           f"Risk={portfolio_risk:.4f}, Sharpe={sharpe_ratio:.4f}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Portfolio optimization failed: {e}")
            raise RiskOptimizerError(f"Portfolio optimization failed: {e}")
    
    def _calculate_option_score(self, 
                              option: TradingOption, 
                              risk_tolerance: float,
                              optimization_method: OptimizationMethod) -> float:
        """Calculate optimization score for a single trading option."""
        # Get user risk settings if available
        risk_settings = self.user_risk_settings
        
        if optimization_method == OptimizationMethod.SHARPE_RATIO:
            base_score = option.risk_adjusted_return
        elif optimization_method == OptimizationMethod.MEAN_VARIANCE:
            # Utility function: U = μ - (A/2) * σ² where A is risk aversion
            if risk_settings:
                risk_aversion = risk_settings.volatility_penalty
            else:
                risk_aversion = 2.0 * (1.0 - risk_tolerance)  # Higher risk aversion for lower tolerance
            base_score = option.expected_return - (risk_aversion / 2.0) * (option.expected_risk ** 2)
        elif optimization_method == OptimizationMethod.KELLY_CRITERION:
            base_score = option.kelly_fraction
        else:
            # Default to risk-adjusted return
            base_score = option.risk_adjusted_return
        
        # Apply additional factors based on user preferences
        confidence_factor = option.confidence_score
        
        # Drawdown penalty based on user tolerance
        if risk_settings:
            drawdown_penalty = max(0, 1.0 - abs(option.max_drawdown) / risk_settings.max_drawdown_tolerance)
        else:
            drawdown_penalty = max(0, 1.0 - abs(option.max_drawdown) / 0.5)
        
        win_rate_bonus = option.win_rate
        
        # Apply return preference weighting if available
        if risk_settings:
            return_weight = risk_settings.return_preference
            risk_weight = 1.0 - return_weight
            
            # Adjust base score based on return vs risk preference
            normalized_return = option.expected_return / 0.2  # Normalize to typical return range
            normalized_risk_penalty = option.expected_risk / 0.3  # Normalize to typical risk range
            
            preference_adjusted_score = (return_weight * normalized_return - 
                                       risk_weight * normalized_risk_penalty)
            
            # Combine with base score
            final_score = (0.7 * base_score + 0.3 * preference_adjusted_score) * confidence_factor * drawdown_penalty * (0.5 + 0.5 * win_rate_bonus)
        else:
            # Original calculation
            final_score = base_score * confidence_factor * drawdown_penalty * (0.5 + 0.5 * win_rate_bonus)
        
        return final_score
    
    def _build_correlation_matrix(self, trading_options: List[TradingOption]) -> np.ndarray:
        """Build correlation matrix for trading options."""
        n = len(trading_options)
        correlation_matrix = np.eye(n)  # Start with identity matrix
        
        # Apply correlation estimates based on account/symbol relationships
        for i in range(n):
            for j in range(i + 1, n):
                opt_i = trading_options[i]
                opt_j = trading_options[j]
                
                # Estimate correlation based on similarity
                if opt_i.symbol == opt_j.symbol:
                    # Same symbol, different accounts - high correlation
                    correlation = 0.8
                elif opt_i.account_name == opt_j.account_name:
                    # Same account, different symbols - moderate correlation
                    correlation = 0.4
                else:
                    # Different account and symbol - low correlation
                    correlation = 0.2
                
                correlation_matrix[i, j] = correlation
                correlation_matrix[j, i] = correlation
        
        return correlation_matrix
    
    def _calculate_covariance_matrix(self, risks: np.ndarray, correlation_matrix: np.ndarray) -> np.ndarray:
        """Calculate covariance matrix from risks and correlations."""
        # Covariance = σᵢ * σⱼ * ρᵢⱼ
        risk_matrix = np.outer(risks, risks)
        covariance_matrix = risk_matrix * correlation_matrix
        return covariance_matrix
    
    def _optimize_mean_variance(self, 
                              returns: np.ndarray, 
                              covariance_matrix: np.ndarray,
                              risk_tolerance: float,
                              constraints: OptimizationConstraints) -> Dict[str, Any]:
        """Optimize using mean-variance optimization."""
        n = len(returns)
        
        # Objective function: maximize utility = μ'w - (λ/2) * w'Σw
        risk_aversion = 2.0 * (1.0 - risk_tolerance)
        
        def objective(weights):
            portfolio_return = np.dot(weights, returns)
            portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
            utility = portfolio_return - (risk_aversion / 2.0) * portfolio_variance
            return -utility  # Minimize negative utility
        
        # Constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
        ]
        
        # Bounds
        bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
        
        # Initial guess
        x0 = np.ones(n) / n
        
        # Optimize
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
        
        # If optimization failed, try with different approaches
        if not result.success:
            # Try with random initial guess
            x0 = np.random.dirichlet(np.ones(n))
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
        
        # If still failed, try with equal weights as fallback
        if not result.success:
            # Check if equal weights satisfy constraints
            equal_weights = np.ones(n) / n
            if (all(constraints.min_position_size <= w <= constraints.max_position_size for w in equal_weights)):
                result.x = equal_weights
                result.success = False  # Keep original failure status but provide fallback
                result.message = "Fallback to equal weights due to optimization failure"
            else:
                # Adjust equal weights to satisfy bounds
                adjusted_weights = np.clip(equal_weights, constraints.min_position_size, constraints.max_position_size)
                adjusted_weights = adjusted_weights / np.sum(adjusted_weights)  # Renormalize
                result.x = adjusted_weights
                result.success = False  # Keep original failure status but provide fallback
                result.message = "Fallback to adjusted equal weights"
        
        # Ensure weights sum to 1 (normalize if needed)
        if result.success and abs(np.sum(result.x) - 1.0) > 1e-6:
            result.x = result.x / np.sum(result.x)
        
        return {
            'weights': result.x,
            'success': result.success,
            'message': result.message if hasattr(result, 'message') else 'Mean-variance optimization completed',
            'constraints_satisfied': result.success
        }
    
    def _optimize_sharpe_ratio(self, 
                             returns: np.ndarray, 
                             covariance_matrix: np.ndarray,
                             constraints: OptimizationConstraints) -> Dict[str, Any]:
        """Optimize using Sharpe ratio maximization."""
        n = len(returns)
        
        # Objective function: maximize Sharpe ratio = (μ'w - rf) / sqrt(w'Σw)
        def objective(weights):
            portfolio_return = np.dot(weights, returns)
            portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
            portfolio_risk = np.sqrt(portfolio_variance)
            
            if portfolio_risk == 0:
                return 1e6
            
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk
            return -sharpe_ratio  # Minimize negative Sharpe ratio
        
        # Constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
        ]
        
        # Bounds
        bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
        
        # Initial guess
        x0 = np.ones(n) / n
        
        # Use SLSQP for constrained optimization
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
        
        # If optimization failed, try differential evolution as fallback
        if not result.success:
            # For differential evolution, we need to handle constraints differently
            def constrained_objective(weights):
                # Penalty for constraint violation
                weight_sum_penalty = 1000 * abs(np.sum(weights) - 1.0)
                return objective(weights) + weight_sum_penalty
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = differential_evolution(constrained_objective, bounds, seed=42, maxiter=200)
            
            # Normalize weights to ensure they sum to 1
            if result.success:
                result.x = result.x / np.sum(result.x)
        
        return {
            'weights': result.x,
            'success': result.success,
            'message': 'Sharpe ratio optimization completed',
            'constraints_satisfied': result.success
        }
    
    def _optimize_kelly_criterion(self, 
                                trading_options: List[TradingOption],
                                constraints: OptimizationConstraints) -> Dict[str, Any]:
        """Optimize using Kelly criterion."""
        n = len(trading_options)
        
        # Calculate Kelly fractions
        kelly_fractions = np.array([opt.kelly_fraction for opt in trading_options])
        
        # Handle negative or zero Kelly fractions
        kelly_fractions = np.maximum(kelly_fractions, 0.001)  # Minimum positive value
        
        # Apply constraints
        kelly_fractions = np.clip(kelly_fractions, constraints.min_position_size, constraints.max_position_size)
        
        # Normalize to ensure they sum to 1
        total_kelly = np.sum(kelly_fractions)
        if total_kelly > 0:
            weights = kelly_fractions / total_kelly
        else:
            weights = np.ones(n) / n
        
        # Final check to ensure constraints are satisfied
        weights = np.clip(weights, constraints.min_position_size, constraints.max_position_size)
        
        # Renormalize after clipping
        weights = weights / np.sum(weights)
        
        return {
            'weights': weights,
            'success': True,
            'message': 'Kelly criterion optimization completed',
            'constraints_satisfied': True
        }
    
    def _optimize_risk_parity(self, 
                            covariance_matrix: np.ndarray,
                            constraints: OptimizationConstraints) -> Dict[str, Any]:
        """Optimize using risk parity approach."""
        n = covariance_matrix.shape[0]
        
        # Objective: minimize sum of squared differences in risk contributions
        def objective(weights):
            portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
            
            if portfolio_variance == 0:
                return 1e6
            
            # Risk contributions
            marginal_contrib = np.dot(covariance_matrix, weights)
            risk_contrib = weights * marginal_contrib / portfolio_variance
            
            # Target equal risk contribution
            target_contrib = 1.0 / n
            
            # Sum of squared deviations from equal risk contribution
            return np.sum((risk_contrib - target_contrib) ** 2)
        
        # Constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
        ]
        
        # Bounds
        bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
        
        # Initial guess
        x0 = np.ones(n) / n
        
        # Optimize
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
        
        # If optimization failed, try with different method
        if not result.success:
            # Try with trust-constr method
            result = minimize(objective, x0, method='trust-constr', bounds=bounds, constraints=constraints_list)
        
        # Ensure weights sum to 1 (normalize if needed)
        if result.success and abs(np.sum(result.x) - 1.0) > 1e-6:
            result.x = result.x / np.sum(result.x)
        
        return {
            'weights': result.x,
            'success': result.success,
            'message': result.message if hasattr(result, 'message') else 'Risk parity optimization completed',
            'constraints_satisfied': result.success
        }
    
    def _optimize_maximum_diversification(self, 
                                        risks: np.ndarray,
                                        correlation_matrix: np.ndarray,
                                        constraints: OptimizationConstraints) -> Dict[str, Any]:
        """Optimize using maximum diversification approach."""
        n = len(risks)
        covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
        
        # Objective: maximize diversification ratio = (w'σ) / sqrt(w'Σw)
        def objective(weights):
            weighted_avg_risk = np.dot(weights, risks)
            portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
            portfolio_risk = np.sqrt(portfolio_variance)
            
            if portfolio_risk == 0:
                return 1e6
            
            diversification_ratio = weighted_avg_risk / portfolio_risk
            return -diversification_ratio  # Minimize negative diversification ratio
        
        # Constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
        ]
        
        # Bounds
        bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
        
        # Initial guess
        x0 = np.ones(n) / n
        
        # Optimize
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
        
        # If optimization failed, try with different method
        if not result.success:
            # Try with trust-constr method
            result = minimize(objective, x0, method='trust-constr', bounds=bounds, constraints=constraints_list)
        
        # Ensure weights sum to 1 (normalize if needed)
        if result.success and abs(np.sum(result.x) - 1.0) > 1e-6:
            result.x = result.x / np.sum(result.x)
        
        return {
            'weights': result.x,
            'success': result.success,
            'message': result.message if hasattr(result, 'message') else 'Maximum diversification optimization completed',
            'constraints_satisfied': result.success
        }
    
    def get_risk_tolerance_parameters(self, risk_tolerance: float) -> Dict[str, Any]:
        """Get risk tolerance parameters for given risk level."""
        # Map continuous risk tolerance to discrete levels
        if risk_tolerance <= 0.3:
            return self.risk_tolerance_params[RiskTolerance.CONSERVATIVE]
        elif risk_tolerance <= 0.6:
            return self.risk_tolerance_params[RiskTolerance.MODERATE]
        elif risk_tolerance <= 0.85:
            return self.risk_tolerance_params[RiskTolerance.AGGRESSIVE]
        else:
            return self.risk_tolerance_params[RiskTolerance.VERY_AGGRESSIVE]
    
    def validate_optimization_result(self, 
                                   result: OptimizationResult,
                                   constraints: OptimizationConstraints) -> bool:
        """Validate optimization result against constraints."""
        try:
            # Check weight constraints
            weights = list(result.optimal_weights.values())
            
            if abs(sum(weights) - 1.0) > 1e-6:
                return False
            
            if any(w < constraints.min_position_size - 1e-6 or w > constraints.max_position_size + 1e-6 for w in weights):
                return False
            
            # Check risk constraints
            if result.expected_portfolio_risk > constraints.max_total_risk:
                return False
            
            # Check concentration constraint
            if result.max_weight > constraints.max_concentration:
                return False
            
            # Check diversification constraint
            active_positions = sum(1 for w in weights if w > 1e-6)
            if active_positions < constraints.min_diversification:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False
    
    def get_optimization_history(self, limit: int = 100) -> List[OptimizationResult]:
        """Get recent optimization history."""
        return self.optimization_history[-limit:]
    
    def clear_optimization_history(self):
        """Clear optimization history."""
        self.optimization_history.clear()
        self.logger.info("Optimization history cleared")
    
    def create_risk_tolerance_settings(self, 
                                     risk_level: float,
                                     return_preference: float = 0.6,
                                     diversification_preference: float = 0.4) -> RiskToleranceSettings:
        """
        Create user-configurable risk tolerance settings.
        
        Args:
            risk_level: Risk tolerance level (0.0 to 1.0)
            return_preference: Preference for returns vs risk (0.0 to 1.0)
            diversification_preference: Preference for diversification (0.0 to 1.0)
            
        Returns:
            RiskToleranceSettings configured for the user
        """
        # Map risk level to specific parameters
        if risk_level <= 0.25:
            # Conservative
            max_portfolio_risk = 0.08 + (risk_level * 0.08)  # 0.08 to 0.10
            min_sharpe_ratio = 1.2 - (risk_level * 0.8)      # 1.2 to 1.0
            max_drawdown_tolerance = 0.10 + (risk_level * 0.10)  # 0.10 to 0.15
            volatility_penalty = 3.0 - (risk_level * 1.0)    # 3.0 to 2.5
            concentration_limit = 0.25 + (risk_level * 0.15) # 0.25 to 0.35
        elif risk_level <= 0.5:
            # Moderate
            adjusted_level = (risk_level - 0.25) / 0.25
            max_portfolio_risk = 0.10 + (adjusted_level * 0.10)  # 0.10 to 0.20
            min_sharpe_ratio = 1.0 - (adjusted_level * 0.5)      # 1.0 to 0.5
            max_drawdown_tolerance = 0.15 + (adjusted_level * 0.10)  # 0.15 to 0.25
            volatility_penalty = 2.5 - (adjusted_level * 0.5)    # 2.5 to 2.0
            concentration_limit = 0.35 + (adjusted_level * 0.15) # 0.35 to 0.50
        elif risk_level <= 0.75:
            # Aggressive
            adjusted_level = (risk_level - 0.5) / 0.25
            max_portfolio_risk = 0.20 + (adjusted_level * 0.15)  # 0.20 to 0.35
            min_sharpe_ratio = 0.5 - (adjusted_level * 0.2)      # 0.5 to 0.3
            max_drawdown_tolerance = 0.25 + (adjusted_level * 0.15)  # 0.25 to 0.40
            volatility_penalty = 2.0 - (adjusted_level * 0.5)    # 2.0 to 1.5
            concentration_limit = 0.50 + (adjusted_level * 0.20) # 0.50 to 0.70
        else:
            # Very Aggressive
            adjusted_level = (risk_level - 0.75) / 0.25
            max_portfolio_risk = 0.35 + (adjusted_level * 0.15)  # 0.35 to 0.50
            min_sharpe_ratio = 0.3 - (adjusted_level * 0.1)      # 0.3 to 0.2
            max_drawdown_tolerance = 0.40 + (adjusted_level * 0.20)  # 0.40 to 0.60
            volatility_penalty = 1.5 - (adjusted_level * 0.5)    # 1.5 to 1.0
            concentration_limit = 0.70 + (adjusted_level * 0.30) # 0.70 to 1.00
        
        return RiskToleranceSettings(
            risk_level=risk_level,
            max_portfolio_risk=max_portfolio_risk,
            min_sharpe_ratio=min_sharpe_ratio,
            max_drawdown_tolerance=max_drawdown_tolerance,
            diversification_preference=diversification_preference,
            return_preference=return_preference,
            volatility_penalty=volatility_penalty,
            concentration_limit=concentration_limit
        )
    
    def update_risk_tolerance_settings(self, settings: RiskToleranceSettings):
        """
        Update user risk tolerance settings.
        
        Args:
            settings: New risk tolerance settings
        """
        self.user_risk_settings = settings
        self.logger.info(f"Updated risk tolerance settings: risk_level={settings.risk_level}")
    
    def get_effective_risk_tolerance(self, override_tolerance: Optional[float] = None) -> float:
        """
        Get effective risk tolerance considering user settings and overrides.
        
        Args:
            override_tolerance: Optional override for risk tolerance
            
        Returns:
            Effective risk tolerance to use
        """
        if override_tolerance is not None:
            return override_tolerance
        elif self.user_risk_settings is not None:
            return self.user_risk_settings.risk_level
        else:
            return self.default_risk_tolerance
    
    def create_constraints_from_risk_settings(self, 
                                            settings: Optional[RiskToleranceSettings] = None) -> OptimizationConstraints:
        """
        Create optimization constraints from risk tolerance settings.
        
        Args:
            settings: Risk tolerance settings (uses current user settings if None)
            
        Returns:
            OptimizationConstraints based on risk settings
        """
        effective_settings = settings or self.user_risk_settings
        
        if effective_settings is None:
            # Use default constraints
            return OptimizationConstraints()
        
        return OptimizationConstraints(
            max_position_size=effective_settings.concentration_limit,
            min_position_size=0.01,  # Small minimum to ensure diversification
            max_total_risk=effective_settings.max_portfolio_risk,
            min_diversification=max(2, int(5 * effective_settings.diversification_preference)),
            max_concentration=effective_settings.concentration_limit,
            max_drawdown_limit=effective_settings.max_drawdown_tolerance,
            allow_short_positions=effective_settings.risk_level > 0.8,  # Only for very aggressive
            transaction_cost_rate=0.001,
            rebalancing_frequency=30
        )
    
    def optimize_with_profit_volatility_balance(self, 
                                              trading_options: List[TradingOption],
                                              profit_weight: float = 0.6,
                                              volatility_weight: float = 0.4,
                                              risk_tolerance: Optional[float] = None,
                                              constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio with explicit profit-volatility balance.
        
        This method implements a custom optimization that directly balances
        profit maximization with volatility minimization using user-defined weights.
        
        Args:
            trading_options: List of available trading options
            profit_weight: Weight given to profit maximization (0.0 to 1.0)
            volatility_weight: Weight given to volatility minimization (0.0 to 1.0)
            risk_tolerance: Risk tolerance level
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with optimal allocation
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        if abs(profit_weight + volatility_weight - 1.0) > 1e-6:
            raise RiskOptimizerError("Profit weight and volatility weight must sum to 1.0")
        
        effective_risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        constraints = constraints or self.create_constraints_from_risk_settings()
        
        try:
            self.logger.info(f"Optimizing with profit-volatility balance: "
                           f"profit_weight={profit_weight}, volatility_weight={volatility_weight}")
            
            n = len(trading_options)
            returns = np.array([opt.expected_return for opt in trading_options])
            risks = np.array([opt.expected_risk for opt in trading_options])
            
            # Build correlation matrix and covariance matrix
            correlation_matrix = self._build_correlation_matrix(trading_options)
            covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
            
            # Custom objective function balancing profit and volatility
            def objective(weights):
                portfolio_return = np.dot(weights, returns)
                portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                portfolio_risk = np.sqrt(portfolio_variance)
                
                # Normalize return and risk for balanced comparison
                max_return = np.max(returns)
                max_risk = np.max(risks)
                
                normalized_return = portfolio_return / max_return if max_return > 0 else 0
                normalized_risk = portfolio_risk / max_risk if max_risk > 0 else 0
                
                # Objective: maximize profit, minimize volatility
                utility = profit_weight * normalized_return - volatility_weight * normalized_risk
                
                # Apply risk tolerance adjustment
                risk_penalty = (1.0 - effective_risk_tolerance) * portfolio_variance
                utility -= risk_penalty
                
                return -utility  # Minimize negative utility
            
            # Constraints
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
            ]
            
            # Add risk constraint if specified
            if constraints.max_total_risk < 1.0:
                def risk_constraint(weights):
                    portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                    portfolio_risk = np.sqrt(portfolio_variance)
                    return constraints.max_total_risk - portfolio_risk
                
                constraints_list.append({'type': 'ineq', 'fun': risk_constraint})
            
            # Bounds
            lower_bound = constraints.min_position_size
            upper_bound = min(constraints.max_position_size, constraints.max_concentration)
            bounds = [(lower_bound, upper_bound) for _ in range(n)]
            
            # Initial guess
            x0 = np.ones(n) / n
            
            # Optimize
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            # If optimization failed, try with different method
            if not result.success:
                result = differential_evolution(
                    lambda w: objective(w) + 1000 * abs(np.sum(w) - 1.0),
                    bounds, seed=42, maxiter=300
                )
                if result.success:
                    result.x = result.x / np.sum(result.x)  # Normalize
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(result.x, returns)
            portfolio_risk = np.sqrt(np.dot(result.x, np.dot(covariance_matrix, result.x)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0.0
            
            # Calculate diversification ratio
            weighted_avg_risk = np.dot(result.x, risks)
            diversification_ratio = weighted_avg_risk / portfolio_risk if portfolio_risk > 0 else 1.0
            
            # Create result
            option_keys = [f"{opt.account_name}-{opt.symbol}" for opt in trading_options]
            optimal_weights = dict(zip(option_keys, result.x))
            
            optimization_result = OptimizationResult(
                optimal_weights=optimal_weights,
                expected_portfolio_return=portfolio_return,
                expected_portfolio_risk=portfolio_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                max_weight=np.max(result.x),
                optimization_method=OptimizationMethod.MEAN_VARIANCE,  # Closest method
                risk_tolerance=effective_risk_tolerance,
                constraints_satisfied=self.validate_optimization_result(
                    OptimizationResult(
                        optimal_weights=optimal_weights,
                        expected_portfolio_return=portfolio_return,
                        expected_portfolio_risk=portfolio_risk,
                        sharpe_ratio=sharpe_ratio,
                        diversification_ratio=diversification_ratio,
                        max_weight=np.max(result.x),
                        optimization_method=OptimizationMethod.MEAN_VARIANCE,
                        risk_tolerance=effective_risk_tolerance,
                        constraints_satisfied=True,
                        optimization_success=result.success,
                        optimization_message="Profit-volatility balance optimization"
                    ), constraints
                ),
                optimization_success=result.success,
                optimization_message=f"Profit-volatility balance optimization: "
                                   f"profit_weight={profit_weight}, volatility_weight={volatility_weight}"
            )
            
            # Store in history
            self.optimization_history.append(optimization_result)
            
            self.logger.info(f"Profit-volatility optimization completed: "
                           f"Return={portfolio_return:.4f}, Risk={portfolio_risk:.4f}, "
                           f"Sharpe={sharpe_ratio:.4f}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Profit-volatility optimization failed: {e}")
            raise RiskOptimizerError(f"Profit-volatility optimization failed: {e}")
    
    def optimize_portfolio_allocation_with_user_preferences(self,
                                                          trading_options: List[TradingOption],
                                                          constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio allocation using user-configured risk tolerance settings.
        
        This method uses the user's risk tolerance settings to determine the optimization
        approach and constraints automatically.
        
        Args:
            trading_options: List of available trading options
            constraints: Optional constraints (will use risk settings if None)
            
        Returns:
            OptimizationResult with optimal allocation based on user preferences
            
        Raises:
            RiskOptimizerError: If optimization fails or no user settings configured
        """
        if self.user_risk_settings is None:
            raise RiskOptimizerError("No user risk tolerance settings configured")
        
        # Use user preferences to determine optimization method
        risk_level = self.user_risk_settings.risk_level
        return_preference = self.user_risk_settings.return_preference
        
        # Choose optimization method based on user preferences
        if return_preference > 0.7:
            # High return preference - use Sharpe ratio optimization
            optimization_method = OptimizationMethod.SHARPE_RATIO
        elif risk_level < 0.3:
            # Conservative - use risk parity
            optimization_method = OptimizationMethod.RISK_PARITY
        elif self.user_risk_settings.diversification_preference > 0.6:
            # High diversification preference
            optimization_method = OptimizationMethod.MAXIMUM_DIVERSIFICATION
        else:
            # Balanced approach - use mean variance
            optimization_method = OptimizationMethod.MEAN_VARIANCE
        
        # Create constraints from user settings if not provided
        if constraints is None:
            constraints = self.create_constraints_from_risk_settings()
        
        return self.optimize_portfolio_allocation(
            trading_options=trading_options,
            risk_tolerance=risk_level,
            optimization_method=optimization_method,
            constraints=constraints
        )
    
    def get_optimization_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for recent optimizations.
        
        Returns:
            Dictionary containing performance metrics
        """
        if not self.optimization_history:
            return {
                'total_optimizations': 0,
                'success_rate': 0.0,
                'average_sharpe_ratio': 0.0,
                'average_diversification_ratio': 0.0,
                'methods_used': {}
            }
        
        recent_results = self.optimization_history[-50:]  # Last 50 optimizations
        
        successful_results = [r for r in recent_results if r.optimization_success]
        success_rate = len(successful_results) / len(recent_results)
        
        if successful_results:
            avg_sharpe = np.mean([r.sharpe_ratio for r in successful_results])
            avg_diversification = np.mean([r.diversification_ratio for r in successful_results])
            
            # Count methods used
            methods_used = {}
            for result in successful_results:
                method = result.optimization_method.value
                methods_used[method] = methods_used.get(method, 0) + 1
        else:
            avg_sharpe = 0.0
            avg_diversification = 0.0
            methods_used = {}
        
        return {
            'total_optimizations': len(recent_results),
            'success_rate': success_rate,
            'average_sharpe_ratio': avg_sharpe,
            'average_diversification_ratio': avg_diversification,
            'methods_used': methods_used,
            'recent_results_count': len(recent_results)
        }
    
    def benchmark_optimization_methods(self, 
                                     trading_options: List[TradingOption],
                                     risk_tolerance: float = 0.5) -> Dict[str, OptimizationResult]:
        """
        Benchmark all optimization methods on the same set of trading options.
        
        Args:
            trading_options: List of trading options to optimize
            risk_tolerance: Risk tolerance level for comparison
            
        Returns:
            Dictionary mapping method names to optimization results
        """
        methods = [
            OptimizationMethod.SHARPE_RATIO,
            OptimizationMethod.MEAN_VARIANCE,
            OptimizationMethod.KELLY_CRITERION,
            OptimizationMethod.RISK_PARITY,
            OptimizationMethod.MAXIMUM_DIVERSIFICATION
        ]
        
        results = {}
        
        for method in methods:
            try:
                result = self.optimize_portfolio_allocation(
                    trading_options=trading_options,
                    risk_tolerance=risk_tolerance,
                    optimization_method=method
                )
                results[method.value] = result
                
                self.logger.info(f"Benchmark {method.value}: "
                               f"Return={result.expected_portfolio_return:.4f}, "
                               f"Risk={result.expected_portfolio_risk:.4f}, "
                               f"Sharpe={result.sharpe_ratio:.4f}")
                
            except Exception as e:
                self.logger.error(f"Benchmark failed for {method.value}: {e}")
                # Create a failed result
                results[method.value] = OptimizationResult(
                    optimal_weights={},
                    expected_portfolio_return=0.0,
                    expected_portfolio_risk=0.0,
                    sharpe_ratio=0.0,
                    diversification_ratio=0.0,
                    max_weight=0.0,
                    optimization_method=method,
                    risk_tolerance=risk_tolerance,
                    constraints_satisfied=False,
                    optimization_success=False,
                    optimization_message=f"Benchmark failed: {e}"
                )
        
        return results
    
    def optimize_dynamic_risk_budget(self,
                                   trading_options: List[TradingOption],
                                   total_risk_budget: float = 0.15,
                                   risk_tolerance: Optional[float] = None,
                                   constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio allocation using dynamic risk budgeting approach.
        
        This method allocates risk budget across trading options based on their
        individual risk contributions and expected returns, ensuring the total
        portfolio risk stays within the specified budget.
        
        Args:
            trading_options: List of available trading options
            total_risk_budget: Maximum total portfolio risk allowed
            risk_tolerance: Risk tolerance level
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with risk-budgeted allocation
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        effective_risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        constraints = constraints or self.create_constraints_from_risk_settings()
        
        # Override max total risk with risk budget
        constraints.max_total_risk = total_risk_budget
        
        try:
            self.logger.info(f"Optimizing with dynamic risk budget: {total_risk_budget}")
            
            n = len(trading_options)
            returns = np.array([opt.expected_return for opt in trading_options])
            risks = np.array([opt.expected_risk for opt in trading_options])
            
            # Build correlation matrix and covariance matrix
            correlation_matrix = self._build_correlation_matrix(trading_options)
            covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
            
            # Risk budgeting objective: maximize return subject to risk budget constraint
            def objective(weights):
                portfolio_return = np.dot(weights, returns)
                return -portfolio_return  # Minimize negative return
            
            # Risk budget constraint
            def risk_budget_constraint(weights):
                portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                portfolio_risk = np.sqrt(portfolio_variance)
                return total_risk_budget - portfolio_risk
            
            # Constraints
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
                {'type': 'ineq', 'fun': risk_budget_constraint}     # Risk budget constraint
            ]
            
            # Bounds
            bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
            
            # Initial guess - equal weights
            x0 = np.ones(n) / n
            
            # Optimize
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            if not result.success:
                # Try with different initial guess
                x0 = np.random.dirichlet(np.ones(n))
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(result.x, returns)
            portfolio_risk = np.sqrt(np.dot(result.x, np.dot(covariance_matrix, result.x)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0.0
            
            # Calculate diversification ratio
            weighted_avg_risk = np.dot(result.x, risks)
            diversification_ratio = weighted_avg_risk / portfolio_risk if portfolio_risk > 0 else 1.0
            
            # Create result
            option_keys = [f"{opt.account_name}-{opt.symbol}" for opt in trading_options]
            optimal_weights = dict(zip(option_keys, result.x))
            
            optimization_result = OptimizationResult(
                optimal_weights=optimal_weights,
                expected_portfolio_return=portfolio_return,
                expected_portfolio_risk=portfolio_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                max_weight=np.max(result.x),
                optimization_method=OptimizationMethod.MEAN_VARIANCE,  # Closest method
                risk_tolerance=effective_risk_tolerance,
                constraints_satisfied=portfolio_risk <= total_risk_budget + 1e-6,
                optimization_success=result.success,
                optimization_message=f"Dynamic risk budget optimization: budget={total_risk_budget}, "
                                   f"actual_risk={portfolio_risk:.4f}"
            )
            
            # Store in history
            self.optimization_history.append(optimization_result)
            
            self.logger.info(f"Risk budget optimization completed: "
                           f"Return={portfolio_return:.4f}, Risk={portfolio_risk:.4f}, "
                           f"Budget={total_risk_budget}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Dynamic risk budget optimization failed: {e}")
            raise RiskOptimizerError(f"Dynamic risk budget optimization failed: {e}")
    
    def optimize_conditional_value_at_risk(self,
                                         trading_options: List[TradingOption],
                                         confidence_level: float = 0.95,
                                         risk_tolerance: Optional[float] = None,
                                         constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio allocation using Conditional Value at Risk (CVaR) minimization.
        
        CVaR optimization focuses on minimizing the expected loss in the worst-case
        scenarios, providing better tail risk management than traditional mean-variance.
        
        Args:
            trading_options: List of available trading options
            confidence_level: Confidence level for CVaR calculation (e.g., 0.95 for 95%)
            risk_tolerance: Risk tolerance level
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with CVaR-optimized allocation
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        if not 0.5 <= confidence_level <= 0.99:
            raise RiskOptimizerError("Confidence level must be between 0.5 and 0.99")
        
        effective_risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        constraints = constraints or self.create_constraints_from_risk_settings()
        
        try:
            self.logger.info(f"Optimizing with CVaR at {confidence_level*100}% confidence level")
            
            n = len(trading_options)
            returns = np.array([opt.expected_return for opt in trading_options])
            risks = np.array([opt.expected_risk for opt in trading_options])
            
            # Build correlation matrix and covariance matrix
            correlation_matrix = self._build_correlation_matrix(trading_options)
            covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
            
            # For CVaR optimization, we'll use a simplified approach
            # In practice, this would require historical return scenarios
            # Here we approximate using normal distribution assumptions
            
            def objective(weights):
                portfolio_return = np.dot(weights, returns)
                portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                portfolio_risk = np.sqrt(portfolio_variance)
                
                # Approximate CVaR using normal distribution
                # CVaR = μ - σ * φ(Φ^(-1)(α)) / α where α is confidence level
                alpha = 1 - confidence_level
                z_alpha = norm.ppf(alpha)  # Quantile at alpha level
                phi_z_alpha = norm.pdf(z_alpha)  # PDF at quantile
                
                cvar_adjustment = phi_z_alpha / alpha
                expected_shortfall = portfolio_return - portfolio_risk * cvar_adjustment
                
                # Objective: maximize return while minimizing CVaR (expected shortfall)
                # Weight CVaR more heavily for conservative optimization
                cvar_weight = 2.0 * (1.0 - effective_risk_tolerance)
                utility = portfolio_return - cvar_weight * abs(expected_shortfall)
                
                return -utility  # Minimize negative utility
            
            # Constraints
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
            ]
            
            # Add risk constraint if specified
            if constraints.max_total_risk < 1.0:
                def risk_constraint(weights):
                    portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                    portfolio_risk = np.sqrt(portfolio_variance)
                    return constraints.max_total_risk - portfolio_risk
                
                constraints_list.append({'type': 'ineq', 'fun': risk_constraint})
            
            # Bounds
            bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
            
            # Initial guess
            x0 = np.ones(n) / n
            
            # Optimize
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            if not result.success:
                # Try with different method
                result = differential_evolution(
                    lambda w: objective(w) + 1000 * abs(np.sum(w) - 1.0),
                    bounds, seed=42, maxiter=300
                )
                if result.success:
                    result.x = result.x / np.sum(result.x)  # Normalize
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(result.x, returns)
            portfolio_risk = np.sqrt(np.dot(result.x, np.dot(covariance_matrix, result.x)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0.0
            
            # Calculate diversification ratio
            weighted_avg_risk = np.dot(result.x, risks)
            diversification_ratio = weighted_avg_risk / portfolio_risk if portfolio_risk > 0 else 1.0
            
            # Create result
            option_keys = [f"{opt.account_name}-{opt.symbol}" for opt in trading_options]
            optimal_weights = dict(zip(option_keys, result.x))
            
            optimization_result = OptimizationResult(
                optimal_weights=optimal_weights,
                expected_portfolio_return=portfolio_return,
                expected_portfolio_risk=portfolio_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                max_weight=np.max(result.x),
                optimization_method=OptimizationMethod.MEAN_VARIANCE,  # Closest method
                risk_tolerance=effective_risk_tolerance,
                constraints_satisfied=self.validate_optimization_result(
                    OptimizationResult(
                        optimal_weights=optimal_weights,
                        expected_portfolio_return=portfolio_return,
                        expected_portfolio_risk=portfolio_risk,
                        sharpe_ratio=sharpe_ratio,
                        diversification_ratio=diversification_ratio,
                        max_weight=np.max(result.x),
                        optimization_method=OptimizationMethod.MEAN_VARIANCE,
                        risk_tolerance=effective_risk_tolerance,
                        constraints_satisfied=True,
                        optimization_success=result.success,
                        optimization_message="CVaR optimization"
                    ), constraints
                ),
                optimization_success=result.success,
                optimization_message=f"CVaR optimization at {confidence_level*100}% confidence level"
            )
            
            # Store in history
            self.optimization_history.append(optimization_result)
            
            self.logger.info(f"CVaR optimization completed: "
                           f"Return={portfolio_return:.4f}, Risk={portfolio_risk:.4f}, "
                           f"Sharpe={sharpe_ratio:.4f}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"CVaR optimization failed: {e}")
            raise RiskOptimizerError(f"CVaR optimization failed: {e}") 
   
    def optimize_with_profit_volatility_balance(self, 
                                              trading_options: List[TradingOption],
                                              profit_weight: float = 0.6,
                                              volatility_weight: float = 0.4,
                                              risk_tolerance: Optional[float] = None,
                                              constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio with explicit profit-volatility balance.
        
        This method implements a custom optimization that directly balances
        profit maximization with volatility minimization using user-defined weights.
        
        Args:
            trading_options: List of available trading options
            profit_weight: Weight given to profit maximization (0.0 to 1.0)
            volatility_weight: Weight given to volatility minimization (0.0 to 1.0)
            risk_tolerance: Risk tolerance level
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with optimal allocation
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        if abs(profit_weight + volatility_weight - 1.0) > 1e-6:
            raise RiskOptimizerError("Profit weight and volatility weight must sum to 1.0")
        
        effective_risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        constraints = constraints or self.create_constraints_from_risk_settings()
        
        try:
            self.logger.info(f"Optimizing with profit-volatility balance: "
                           f"profit_weight={profit_weight}, volatility_weight={volatility_weight}")
            
            n = len(trading_options)
            returns = np.array([opt.expected_return for opt in trading_options])
            risks = np.array([opt.expected_risk for opt in trading_options])
            
            # Build correlation matrix and covariance matrix
            correlation_matrix = self._build_correlation_matrix(trading_options)
            covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
            
            # Custom objective function balancing profit and volatility
            def objective(weights):
                portfolio_return = np.dot(weights, returns)
                portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                portfolio_risk = np.sqrt(portfolio_variance)
                
                # Normalize return and risk for balanced comparison
                max_return = np.max(returns)
                max_risk = np.max(risks)
                
                normalized_return = portfolio_return / max_return if max_return > 0 else 0
                normalized_risk = portfolio_risk / max_risk if max_risk > 0 else 0
                
                # Objective: maximize profit, minimize volatility
                utility = profit_weight * normalized_return - volatility_weight * normalized_risk
                
                # Apply risk tolerance adjustment
                risk_penalty = (1.0 - effective_risk_tolerance) * portfolio_variance
                utility -= risk_penalty
                
                return -utility  # Minimize negative utility
            
            # Constraints
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
            ]
            
            # Add risk constraint if specified
            if constraints.max_total_risk < 1.0:
                def risk_constraint(weights):
                    portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                    portfolio_risk = np.sqrt(portfolio_variance)
                    return constraints.max_total_risk - portfolio_risk
                
                constraints_list.append({'type': 'ineq', 'fun': risk_constraint})
            
            # Bounds
            lower_bound = constraints.min_position_size
            upper_bound = min(constraints.max_position_size, constraints.max_concentration)
            bounds = [(lower_bound, upper_bound) for _ in range(n)]
            
            # Initial guess
            x0 = np.ones(n) / n
            
            # Optimize
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            # If optimization failed, try with different method
            if not result.success:
                result = differential_evolution(
                    lambda w: objective(w) + 1000 * abs(np.sum(w) - 1.0),
                    bounds, seed=42, maxiter=300
                )
                if result.success:
                    result.x = result.x / np.sum(result.x)  # Normalize
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(result.x, returns)
            portfolio_risk = np.sqrt(np.dot(result.x, np.dot(covariance_matrix, result.x)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0.0
            
            # Calculate diversification ratio
            weighted_avg_risk = np.dot(result.x, risks)
            diversification_ratio = weighted_avg_risk / portfolio_risk if portfolio_risk > 0 else 1.0
            
            # Create result
            option_keys = [f"{opt.account_name}-{opt.symbol}" for opt in trading_options]
            optimal_weights = dict(zip(option_keys, result.x))
            
            optimization_result = OptimizationResult(
                optimal_weights=optimal_weights,
                expected_portfolio_return=portfolio_return,
                expected_portfolio_risk=portfolio_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                max_weight=np.max(result.x),
                optimization_method=OptimizationMethod.MEAN_VARIANCE,  # Closest method
                risk_tolerance=effective_risk_tolerance,
                constraints_satisfied=self.validate_optimization_result(
                    OptimizationResult(
                        optimal_weights=optimal_weights,
                        expected_portfolio_return=portfolio_return,
                        expected_portfolio_risk=portfolio_risk,
                        sharpe_ratio=sharpe_ratio,
                        diversification_ratio=diversification_ratio,
                        max_weight=np.max(result.x),
                        optimization_method=OptimizationMethod.MEAN_VARIANCE,
                        risk_tolerance=effective_risk_tolerance,
                        constraints_satisfied=True,
                        optimization_success=result.success,
                        optimization_message="Profit-volatility balance optimization"
                    ), constraints
                ),
                optimization_success=result.success,
                optimization_message=f"Profit-volatility balance optimization: "
                                   f"profit_weight={profit_weight}, volatility_weight={volatility_weight}"
            )
            
            # Store in history
            self.optimization_history.append(optimization_result)
            
            self.logger.info(f"Profit-volatility optimization completed: "
                           f"Return={portfolio_return:.4f}, Risk={portfolio_risk:.4f}, "
                           f"Sharpe={sharpe_ratio:.4f}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Profit-volatility optimization failed: {e}")
            raise RiskOptimizerError(f"Profit-volatility optimization failed: {e}")
    
    def optimize_portfolio_allocation_with_user_preferences(self,
                                                          trading_options: List[TradingOption],
                                                          constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio allocation using user-configured risk tolerance settings.
        
        This method uses the user's risk tolerance settings to determine the optimization
        approach and constraints automatically.
        
        Args:
            trading_options: List of available trading options
            constraints: Optional constraints (will use risk settings if None)
            
        Returns:
            OptimizationResult with optimal allocation based on user preferences
            
        Raises:
            RiskOptimizerError: If optimization fails or no user settings configured
        """
        if self.user_risk_settings is None:
            raise RiskOptimizerError("No user risk tolerance settings configured")
        
        # Use user preferences to determine optimization method
        risk_level = self.user_risk_settings.risk_level
        return_preference = self.user_risk_settings.return_preference
        
        # Choose optimization method based on user preferences
        if return_preference > 0.7:
            # High return preference - use Sharpe ratio optimization
            optimization_method = OptimizationMethod.SHARPE_RATIO
        elif risk_level < 0.3:
            # Conservative - use risk parity
            optimization_method = OptimizationMethod.RISK_PARITY
        elif self.user_risk_settings.diversification_preference > 0.6:
            # High diversification preference
            optimization_method = OptimizationMethod.MAXIMUM_DIVERSIFICATION
        else:
            # Balanced approach - use mean variance
            optimization_method = OptimizationMethod.MEAN_VARIANCE
        
        # Create constraints from user settings if not provided
        if constraints is None:
            constraints = self.create_constraints_from_risk_settings()
        
        return self.optimize_portfolio_allocation(
            trading_options=trading_options,
            risk_tolerance=risk_level,
            optimization_method=optimization_method,
            constraints=constraints
        )
    
    def optimize_dynamic_risk_budget(self,
                                   trading_options: List[TradingOption],
                                   total_risk_budget: float = 0.15,
                                   risk_tolerance: Optional[float] = None,
                                   constraints: Optional[OptimizationConstraints] = None) -> OptimizationResult:
        """
        Optimize portfolio allocation using dynamic risk budgeting approach.
        
        This method allocates risk budget across trading options based on their
        individual risk contributions and expected returns, ensuring the total
        portfolio risk stays within the specified budget.
        
        Args:
            trading_options: List of available trading options
            total_risk_budget: Maximum total portfolio risk allowed
            risk_tolerance: Risk tolerance level
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with risk-budgeted allocation
            
        Raises:
            RiskOptimizerError: If optimization fails
        """
        if not trading_options:
            raise RiskOptimizerError("No trading options provided")
        
        effective_risk_tolerance = self.get_effective_risk_tolerance(risk_tolerance)
        constraints = constraints or self.create_constraints_from_risk_settings()
        
        # Override max total risk with risk budget
        constraints.max_total_risk = total_risk_budget
        
        try:
            self.logger.info(f"Optimizing with dynamic risk budget: {total_risk_budget}")
            
            n = len(trading_options)
            returns = np.array([opt.expected_return for opt in trading_options])
            risks = np.array([opt.expected_risk for opt in trading_options])
            
            # Build correlation matrix and covariance matrix
            correlation_matrix = self._build_correlation_matrix(trading_options)
            covariance_matrix = self._calculate_covariance_matrix(risks, correlation_matrix)
            
            # Risk budgeting objective: maximize return subject to risk budget constraint
            def objective(weights):
                portfolio_return = np.dot(weights, returns)
                return -portfolio_return  # Minimize negative return
            
            # Risk budget constraint
            def risk_budget_constraint(weights):
                portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                portfolio_risk = np.sqrt(portfolio_variance)
                return total_risk_budget - portfolio_risk
            
            # Constraints
            constraints_list = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
                {'type': 'ineq', 'fun': risk_budget_constraint}     # Risk budget constraint
            ]
            
            # Bounds
            bounds = [(constraints.min_position_size, constraints.max_position_size) for _ in range(n)]
            
            # Initial guess
            x0 = np.ones(n) / n
            
            # Optimize
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints_list)
            
            # If optimization failed, try with different method
            if not result.success:
                # Try with penalty method
                def penalized_objective(weights):
                    portfolio_return = np.dot(weights, returns)
                    portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
                    portfolio_risk = np.sqrt(portfolio_variance)
                    
                    # Penalty for exceeding risk budget
                    risk_penalty = max(0, portfolio_risk - total_risk_budget) * 1000
                    weight_penalty = abs(np.sum(weights) - 1.0) * 1000
                    
                    return -portfolio_return + risk_penalty + weight_penalty
                
                result = differential_evolution(penalized_objective, bounds, seed=42, maxiter=300)
                if result.success:
                    result.x = result.x / np.sum(result.x)  # Normalize
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(result.x, returns)
            portfolio_risk = np.sqrt(np.dot(result.x, np.dot(covariance_matrix, result.x)))
            sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_risk if portfolio_risk > 0 else 0.0
            
            # Calculate diversification ratio
            weighted_avg_risk = np.dot(result.x, risks)
            diversification_ratio = weighted_avg_risk / portfolio_risk if portfolio_risk > 0 else 1.0
            
            # Create result
            option_keys = [f"{opt.account_name}-{opt.symbol}" for opt in trading_options]
            optimal_weights = dict(zip(option_keys, result.x))
            
            optimization_result = OptimizationResult(
                optimal_weights=optimal_weights,
                expected_portfolio_return=portfolio_return,
                expected_portfolio_risk=portfolio_risk,
                sharpe_ratio=sharpe_ratio,
                diversification_ratio=diversification_ratio,
                max_weight=np.max(result.x),
                optimization_method=OptimizationMethod.MEAN_VARIANCE,  # Closest method
                risk_tolerance=effective_risk_tolerance,
                constraints_satisfied=portfolio_risk <= total_risk_budget + 1e-6,
                optimization_success=result.success,
                optimization_message=f"Dynamic risk budget optimization: budget={total_risk_budget}"
            )
            
            # Store in history
            self.optimization_history.append(optimization_result)
            
            self.logger.info(f"Dynamic risk budget optimization completed: "
                           f"Return={portfolio_return:.4f}, Risk={portfolio_risk:.4f}, "
                           f"Budget={total_risk_budget}, Sharpe={sharpe_ratio:.4f}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Dynamic risk budget optimization failed: {e}")
            raise RiskOptimizerError(f"Dynamic risk budget optimization failed: {e}")
    
    def get_optimization_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for recent optimizations.
        
        Returns:
            Dictionary containing performance metrics
        """
        if not self.optimization_history:
            return {
                'total_optimizations': 0,
                'success_rate': 0.0,
                'average_sharpe_ratio': 0.0,
                'average_diversification_ratio': 0.0,
                'methods_used': {}
            }
        
        recent_results = self.optimization_history[-50:]  # Last 50 optimizations
        
        successful_results = [r for r in recent_results if r.optimization_success]
        success_rate = len(successful_results) / len(recent_results)
        
        if successful_results:
            avg_sharpe = np.mean([r.sharpe_ratio for r in successful_results])
            avg_diversification = np.mean([r.diversification_ratio for r in successful_results])
            
            # Count methods used
            methods_used = {}
            for result in successful_results:
                method = result.optimization_method.value
                methods_used[method] = methods_used.get(method, 0) + 1
        else:
            avg_sharpe = 0.0
            avg_diversification = 0.0
            methods_used = {}
        
        return {
            'total_optimizations': len(recent_results),
            'success_rate': success_rate,
            'average_sharpe_ratio': avg_sharpe,
            'average_diversification_ratio': avg_diversification,
            'methods_used': methods_used,
            'recent_results_count': len(recent_results)
        }
    
    def benchmark_optimization_methods(self, 
                                     trading_options: List[TradingOption],
                                     risk_tolerance: float = 0.5) -> Dict[str, OptimizationResult]:
        """
        Benchmark all optimization methods on the same set of trading options.
        
        Args:
            trading_options: List of trading options to optimize
            risk_tolerance: Risk tolerance level for comparison
            
        Returns:
            Dictionary mapping method names to optimization results
        """
        methods = [
            OptimizationMethod.SHARPE_RATIO,
            OptimizationMethod.MEAN_VARIANCE,
            OptimizationMethod.KELLY_CRITERION,
            OptimizationMethod.RISK_PARITY,
            OptimizationMethod.MAXIMUM_DIVERSIFICATION
        ]
        
        results = {}
        
        for method in methods:
            try:
                result = self.optimize_portfolio_allocation(
                    trading_options=trading_options,
                    risk_tolerance=risk_tolerance,
                    optimization_method=method
                )
                results[method.value] = result
                
                self.logger.info(f"Benchmark {method.value}: "
                               f"Return={result.expected_portfolio_return:.4f}, "
                               f"Risk={result.expected_portfolio_risk:.4f}, "
                               f"Sharpe={result.sharpe_ratio:.4f}")
                
            except Exception as e:
                self.logger.error(f"Benchmark failed for {method.value}: {e}")
                # Create a failed result
                results[method.value] = OptimizationResult(
                    optimal_weights={},
                    expected_portfolio_return=0.0,
                    expected_portfolio_risk=0.0,
                    sharpe_ratio=0.0,
                    diversification_ratio=0.0,
                    max_weight=0.0,
                    optimization_method=method,
                    risk_tolerance=risk_tolerance,
                    constraints_satisfied=False,
                    optimization_success=False,
                    optimization_message=f"Benchmark failed: {e}"
                )
        
        return results