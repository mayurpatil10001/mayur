"""
Risk metrics calculator for Monte Carlo simulation results.
Implements Value at Risk (VaR), Expected Shortfall, and probability distribution analysis.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from scipy import stats
from scipy.stats import norm, t
import logging

from ...interfaces.simulation_interfaces import IRiskCalculator


class RiskCalculator(IRiskCalculator):
    """
    Calculator for comprehensive risk metrics from simulation results.
    Supports VaR, Expected Shortfall, confidence bands, and distribution analysis.
    """
    
    def __init__(self):
        """Initialize risk calculator."""
        self.logger = logging.getLogger(__name__)
    
    def calculate_var(self, returns: List[float], confidence_level: float = 0.05) -> float:
        """
        Calculate Value at Risk (VaR) at specified confidence level.
        
        Args:
            returns: List of return values (as decimals, e.g., 0.05 for 5%)
            confidence_level: Confidence level (e.g., 0.05 for 95% VaR)
            
        Returns:
            VaR value (negative number representing potential loss)
        """
        if not returns:
            raise ValueError("No returns provided for VaR calculation")
        
        if not (0 < confidence_level < 1):
            raise ValueError("Confidence level must be between 0 and 1")
        
        returns_array = np.array(returns)
        
        # Remove any infinite or NaN values
        returns_array = returns_array[np.isfinite(returns_array)]
        
        if len(returns_array) == 0:
            raise ValueError("No valid returns after cleaning")
        
        # Calculate VaR as the percentile
        var_value = np.percentile(returns_array, confidence_level * 100)
        
        return float(var_value)
    
    def calculate_expected_shortfall(self, returns: List[float], 
                                   confidence_level: float = 0.05) -> float:
        """
        Calculate Expected Shortfall (Conditional VaR) at specified confidence level.
        
        Args:
            returns: List of return values
            confidence_level: Confidence level (e.g., 0.05 for 95% ES)
            
        Returns:
            Expected Shortfall value (average of losses beyond VaR)
        """
        if not returns:
            raise ValueError("No returns provided for Expected Shortfall calculation")
        
        if not (0 < confidence_level < 1):
            raise ValueError("Confidence level must be between 0 and 1")
        
        returns_array = np.array(returns)
        
        # Remove any infinite or NaN values
        returns_array = returns_array[np.isfinite(returns_array)]
        
        if len(returns_array) == 0:
            raise ValueError("No valid returns after cleaning")
        
        # Calculate VaR first
        var_value = self.calculate_var(returns, confidence_level)
        
        # Calculate Expected Shortfall as mean of returns below VaR
        tail_returns = returns_array[returns_array <= var_value]
        
        if len(tail_returns) == 0:
            # If no returns are below VaR, return VaR itself
            return var_value
        
        expected_shortfall = np.mean(tail_returns)
        
        return float(expected_shortfall)
    
    def calculate_risk_metrics(self, simulation_results: List[float], 
                             initial_capital: Optional[float] = None) -> Dict[str, float]:
        """
        Calculate comprehensive risk metrics from simulation results.
        
        Args:
            simulation_results: List of final portfolio values from simulation
            initial_capital: Initial capital amount (for return calculation)
            
        Returns:
            Dictionary containing comprehensive risk metrics
        """
        if not simulation_results:
            raise ValueError("No simulation results provided")
        
        results_array = np.array(simulation_results)
        
        # Remove any infinite or NaN values
        results_array = results_array[np.isfinite(results_array)]
        
        if len(results_array) == 0:
            raise ValueError("No valid simulation results after cleaning")
        
        # Calculate returns if initial capital is provided
        if initial_capital and initial_capital > 0:
            returns = (results_array - initial_capital) / initial_capital
        else:
            # Assume results are already returns
            returns = results_array
            initial_capital = 1.0  # Normalize
        
        # Basic statistics
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        min_return = np.min(returns)
        max_return = np.max(returns)
        
        # VaR calculations at different confidence levels
        var_95 = self.calculate_var(returns.tolist(), 0.05)
        var_99 = self.calculate_var(returns.tolist(), 0.01)
        var_99_9 = self.calculate_var(returns.tolist(), 0.001)
        
        # Expected Shortfall calculations
        es_95 = self.calculate_expected_shortfall(returns.tolist(), 0.05)
        es_99 = self.calculate_expected_shortfall(returns.tolist(), 0.01)
        
        # Probability metrics
        prob_loss = np.sum(returns < 0) / len(returns)
        prob_profit = np.sum(returns > 0) / len(returns)
        prob_large_loss = np.sum(returns < -0.1) / len(returns)  # > 10% loss
        prob_large_gain = np.sum(returns > 0.1) / len(returns)   # > 10% gain
        
        # Tail risk metrics
        tail_ratio = abs(es_95 / var_95) if var_95 != 0 else 1.0
        
        # Downside deviation (semi-standard deviation)
        downside_returns = returns[returns < mean_return]
        downside_deviation = np.std(downside_returns, ddof=1) if len(downside_returns) > 0 else 0.0
        
        # Upside deviation
        upside_returns = returns[returns > mean_return]
        upside_deviation = np.std(upside_returns, ddof=1) if len(upside_returns) > 0 else 0.0
        
        # Risk-adjusted returns
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
        sortino_ratio = mean_return / downside_deviation if downside_deviation > 0 else 0.0
        
        # Calmar ratio (return / max drawdown)
        max_drawdown = abs(min_return)  # Simplified for final values
        calmar_ratio = mean_return / max_drawdown if max_drawdown > 0 else 0.0
        
        # Skewness and kurtosis
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)
        
        # Percentiles for distribution analysis
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_values = {f'p{p}': np.percentile(returns, p) for p in percentiles}
        
        return {
            'basic_statistics': {
                'mean_return': float(mean_return),
                'std_return': float(std_return),
                'min_return': float(min_return),
                'max_return': float(max_return),
                'skewness': float(skewness),
                'kurtosis': float(kurtosis)
            },
            'var_metrics': {
                'var_95': float(var_95),
                'var_99': float(var_99),
                'var_99_9': float(var_99_9)
            },
            'expected_shortfall': {
                'es_95': float(es_95),
                'es_99': float(es_99)
            },
            'probability_metrics': {
                'prob_loss': float(prob_loss),
                'prob_profit': float(prob_profit),
                'prob_large_loss': float(prob_large_loss),
                'prob_large_gain': float(prob_large_gain)
            },
            'risk_adjusted_returns': {
                'sharpe_ratio': float(sharpe_ratio),
                'sortino_ratio': float(sortino_ratio),
                'calmar_ratio': float(calmar_ratio)
            },
            'tail_risk': {
                'tail_ratio': float(tail_ratio),
                'downside_deviation': float(downside_deviation),
                'upside_deviation': float(upside_deviation),
                'max_drawdown': float(max_drawdown)
            },
            'percentiles': {k: float(v) for k, v in percentile_values.items()},
            'sample_size': len(returns)
        }
    
    def generate_confidence_bands(self, simulation_results: List[float], 
                                confidence_levels: List[float] = None) -> Dict[str, Dict[str, float]]:
        """
        Generate confidence bands for simulation results.
        
        Args:
            simulation_results: List of simulation results
            confidence_levels: List of confidence levels (default: [0.90, 0.95, 0.99])
            
        Returns:
            Dictionary containing confidence bands for each level
        """
        if not simulation_results:
            raise ValueError("No simulation results provided")
        
        if confidence_levels is None:
            confidence_levels = [0.90, 0.95, 0.99]
        
        results_array = np.array(simulation_results)
        
        # Remove any infinite or NaN values
        results_array = results_array[np.isfinite(results_array)]
        
        if len(results_array) == 0:
            raise ValueError("No valid simulation results after cleaning")
        
        confidence_bands = {}
        
        for confidence_level in confidence_levels:
            if not (0 < confidence_level < 1):
                self.logger.warning(f"Invalid confidence level {confidence_level}, skipping")
                continue
            
            # Calculate tail probabilities
            tail_prob = (1 - confidence_level) / 2
            
            # Calculate confidence band
            lower_bound = np.percentile(results_array, tail_prob * 100)
            upper_bound = np.percentile(results_array, (1 - tail_prob) * 100)
            median = np.percentile(results_array, 50)
            
            confidence_bands[f'{confidence_level:.0%}'] = {
                'lower_bound': float(lower_bound),
                'upper_bound': float(upper_bound),
                'median': float(median),
                'width': float(upper_bound - lower_bound)
            }
        
        return confidence_bands
    
    def analyze_distribution(self, simulation_results: List[float]) -> Dict[str, Any]:
        """
        Analyze the probability distribution of simulation results.
        
        Args:
            simulation_results: List of simulation results
            
        Returns:
            Dictionary containing distribution analysis
        """
        if not simulation_results:
            raise ValueError("No simulation results provided")
        
        results_array = np.array(simulation_results)
        
        # Remove any infinite or NaN values
        results_array = results_array[np.isfinite(results_array)]
        
        if len(results_array) == 0:
            raise ValueError("No valid simulation results after cleaning")
        
        # Basic distribution properties
        mean = np.mean(results_array)
        std = np.std(results_array, ddof=1)
        skewness = stats.skew(results_array)
        kurtosis = stats.kurtosis(results_array)
        
        # Test for normality
        jb_stat, jb_pvalue = stats.jarque_bera(results_array)
        ks_stat, ks_pvalue = stats.kstest(results_array, 'norm', args=(mean, std))
        
        # Fit different distributions and compare
        distributions_to_test = {
            'normal': stats.norm,
            't': stats.t,
            'skewnorm': stats.skewnorm,
            'lognorm': stats.lognorm
        }
        
        distribution_fits = {}
        best_distribution = 'normal'
        best_aic = float('inf')
        
        for dist_name, distribution in distributions_to_test.items():
            try:
                # Fit distribution
                if dist_name == 'lognorm' and np.any(results_array <= 0):
                    # Skip lognormal if there are non-positive values
                    continue
                
                params = distribution.fit(results_array)
                
                # Calculate AIC (Akaike Information Criterion)
                log_likelihood = np.sum(distribution.logpdf(results_array, *params))
                aic = 2 * len(params) - 2 * log_likelihood
                
                # Calculate Kolmogorov-Smirnov test
                ks_test_stat, ks_test_pvalue = stats.kstest(results_array, distribution.cdf, args=params)
                
                distribution_fits[dist_name] = {
                    'params': params,
                    'aic': float(aic),
                    'log_likelihood': float(log_likelihood),
                    'ks_statistic': float(ks_test_stat),
                    'ks_pvalue': float(ks_test_pvalue)
                }
                
                if aic < best_aic:
                    best_aic = aic
                    best_distribution = dist_name
                    
            except Exception as e:
                self.logger.warning(f"Failed to fit {dist_name} distribution: {e}")
                continue
        
        # Calculate distribution moments
        moments = {
            'mean': float(mean),
            'variance': float(std ** 2),
            'std': float(std),
            'skewness': float(skewness),
            'kurtosis': float(kurtosis)
        }
        
        # Tail analysis
        left_tail_5 = np.percentile(results_array, 5)
        right_tail_95 = np.percentile(results_array, 95)
        tail_ratio = abs(left_tail_5 - mean) / abs(right_tail_95 - mean) if right_tail_95 != mean else 1.0
        
        return {
            'moments': moments,
            'normality_tests': {
                'jarque_bera_statistic': float(jb_stat),
                'jarque_bera_pvalue': float(jb_pvalue),
                'ks_statistic': float(ks_stat),
                'ks_pvalue': float(ks_pvalue),
                'is_normal_jb': bool(jb_pvalue > 0.05),
                'is_normal_ks': bool(ks_pvalue > 0.05)
            },
            'distribution_fits': distribution_fits,
            'best_distribution': best_distribution,
            'tail_analysis': {
                'left_tail_5': float(left_tail_5),
                'right_tail_95': float(right_tail_95),
                'tail_asymmetry_ratio': float(tail_ratio)
            },
            'sample_size': len(results_array)
        }
    
    def calculate_portfolio_var(self, portfolio_weights: List[float], 
                              asset_returns: List[List[float]], 
                              confidence_level: float = 0.05) -> Dict[str, float]:
        """
        Calculate portfolio VaR considering correlations between assets.
        
        Args:
            portfolio_weights: List of portfolio weights (must sum to 1)
            asset_returns: List of return series for each asset
            confidence_level: Confidence level for VaR calculation
            
        Returns:
            Dictionary containing portfolio VaR metrics
        """
        if not portfolio_weights or not asset_returns:
            raise ValueError("Portfolio weights and asset returns must be provided")
        
        if len(portfolio_weights) != len(asset_returns):
            raise ValueError("Number of weights must match number of assets")
        
        if abs(sum(portfolio_weights) - 1.0) > 1e-6:
            raise ValueError("Portfolio weights must sum to 1")
        
        # Convert to numpy arrays
        weights = np.array(portfolio_weights)
        
        # Calculate portfolio returns for each time period
        portfolio_returns = []
        min_length = min(len(returns) for returns in asset_returns)
        
        for t in range(min_length):
            period_returns = [asset_returns[i][t] for i in range(len(asset_returns))]
            portfolio_return = np.dot(weights, period_returns)
            portfolio_returns.append(portfolio_return)
        
        # Calculate portfolio VaR and ES
        portfolio_var = self.calculate_var(portfolio_returns, confidence_level)
        portfolio_es = self.calculate_expected_shortfall(portfolio_returns, confidence_level)
        
        # Calculate individual asset VaRs for comparison
        individual_vars = []
        for i, asset_return in enumerate(asset_returns):
            asset_var = self.calculate_var(asset_return, confidence_level)
            individual_vars.append(asset_var * weights[i])
        
        # Diversification benefit
        undiversified_var = sum(individual_vars)
        diversification_benefit = undiversified_var - portfolio_var
        
        return {
            'portfolio_var': float(portfolio_var),
            'portfolio_expected_shortfall': float(portfolio_es),
            'undiversified_var': float(undiversified_var),
            'diversification_benefit': float(diversification_benefit),
            'diversification_ratio': float(diversification_benefit / abs(undiversified_var)) if undiversified_var != 0 else 0.0,
            'individual_asset_vars': [float(var) for var in individual_vars],
            'portfolio_volatility': float(np.std(portfolio_returns, ddof=1)),
            'sample_size': len(portfolio_returns)
        }
    
    def stress_test_scenarios(self, base_returns: List[float], 
                            stress_scenarios: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """
        Apply stress test scenarios to calculate risk metrics under extreme conditions.
        
        Args:
            base_returns: Base return series
            stress_scenarios: Dictionary of stress scenarios with parameters
            
        Returns:
            Dictionary containing stress test results
        """
        if not base_returns:
            raise ValueError("Base returns must be provided")
        
        if not stress_scenarios:
            raise ValueError("Stress scenarios must be provided")
        
        base_returns_array = np.array(base_returns)
        stress_results = {}
        
        for scenario_name, scenario_params in stress_scenarios.items():
            try:
                # Apply stress scenario transformations
                stressed_returns = base_returns_array.copy()
                
                # Apply mean shift
                if 'mean_shift' in scenario_params:
                    stressed_returns += scenario_params['mean_shift']
                
                # Apply volatility scaling
                if 'volatility_multiplier' in scenario_params:
                    mean_return = np.mean(stressed_returns)
                    stressed_returns = mean_return + (stressed_returns - mean_return) * scenario_params['volatility_multiplier']
                
                # Apply percentile shock (e.g., move all returns to 5th percentile level)
                if 'percentile_shock' in scenario_params:
                    shock_level = np.percentile(base_returns_array, scenario_params['percentile_shock'])
                    stressed_returns = np.minimum(stressed_returns, shock_level)
                
                # Calculate risk metrics for stressed scenario
                stressed_var_95 = self.calculate_var(stressed_returns.tolist(), 0.05)
                stressed_es_95 = self.calculate_expected_shortfall(stressed_returns.tolist(), 0.05)
                stressed_mean = np.mean(stressed_returns)
                stressed_std = np.std(stressed_returns, ddof=1)
                
                stress_results[scenario_name] = {
                    'var_95': float(stressed_var_95),
                    'expected_shortfall_95': float(stressed_es_95),
                    'mean_return': float(stressed_mean),
                    'volatility': float(stressed_std),
                    'scenario_params': scenario_params
                }
                
            except Exception as e:
                self.logger.error(f"Failed to process stress scenario {scenario_name}: {e}")
                continue
        
        return stress_results