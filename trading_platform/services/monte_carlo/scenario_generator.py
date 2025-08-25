"""
Scenario generation service for Monte Carlo simulations.
Implements historical data-based scenario generation with parameter estimation and correlation modeling.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from scipy import stats
from scipy.stats import norm, t, jarque_bera, kstest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import logging

from ...interfaces.simulation_interfaces import IScenarioGenerator
from ...models.trading import ProcessedTrade


class ScenarioGenerator(IScenarioGenerator):
    """
    Generates scenarios for Monte Carlo simulation based on historical trading data.
    Supports parameter estimation, correlation modeling, and scenario validation.
    """
    
    def __init__(self, random_seed: Optional[int] = None):
        """
        Initialize scenario generator.
        
        Args:
            random_seed: Optional seed for reproducible random number generation
        """
        self.logger = logging.getLogger(__name__)
        if random_seed is not None:
            np.random.seed(random_seed)
        
        self.scaler = StandardScaler()
        self.fitted_distributions = {}
        self.correlation_matrix = None
        
    def estimate_parameters(self, historical_data: List[float]) -> Dict[str, float]:
        """
        Estimate distribution parameters from historical data.
        
        Args:
            historical_data: List of historical returns or values
            
        Returns:
            Dictionary containing distribution parameters and goodness-of-fit statistics
        """
        if not historical_data or len(historical_data) < 10:
            raise ValueError("Insufficient historical data for parameter estimation (minimum 10 points required)")
        
        data = np.array(historical_data)
        
        # Remove any infinite or NaN values
        data = data[np.isfinite(data)]
        
        if len(data) < 10:
            raise ValueError("Insufficient valid data points after cleaning")
        
        # Basic statistics
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        skewness = stats.skew(data)
        kurtosis = stats.kurtosis(data)
        
        # Test for normality
        jb_stat, jb_pvalue = jarque_bera(data)
        ks_stat, ks_pvalue = kstest(data, 'norm', args=(mean, std))
        
        # Fit different distributions
        distributions = {
            'normal': stats.norm,
            't': stats.t,
            'skewnorm': stats.skewnorm
        }
        
        best_distribution = 'normal'
        best_aic = float('inf')
        distribution_params = {}
        
        for dist_name, distribution in distributions.items():
            try:
                # Fit distribution
                params = distribution.fit(data)
                
                # Calculate AIC (Akaike Information Criterion)
                log_likelihood = np.sum(distribution.logpdf(data, *params))
                aic = 2 * len(params) - 2 * log_likelihood
                
                distribution_params[dist_name] = {
                    'params': params,
                    'aic': aic,
                    'log_likelihood': log_likelihood
                }
                
                if aic < best_aic:
                    best_aic = aic
                    best_distribution = dist_name
                    
            except Exception as e:
                self.logger.warning(f"Failed to fit {dist_name} distribution: {e}")
                continue
        
        # Store the best fitted distribution
        if distribution_params and best_distribution in distribution_params:
            self.fitted_distributions['best'] = {
                'name': best_distribution,
                'distribution': distributions[best_distribution],
                'params': distribution_params[best_distribution]['params']
            }
        else:
            # Fallback to normal distribution with sample statistics if all fitting failed
            self.fitted_distributions['best'] = {
                'name': 'normal',
                'distribution': distributions['normal'],
                'params': (mean, std)
            }
        
        return {
            'mean': float(mean),
            'std': float(std),
            'skewness': float(skewness),
            'kurtosis': float(kurtosis),
            'min': float(np.min(data)),
            'max': float(np.max(data)),
            'median': float(np.median(data)),
            'q25': float(np.percentile(data, 25)),
            'q75': float(np.percentile(data, 75)),
            'jarque_bera_stat': float(jb_stat),
            'jarque_bera_pvalue': float(jb_pvalue),
            'ks_stat': float(ks_stat),
            'ks_pvalue': float(ks_pvalue),
            'best_distribution': best_distribution,
            'best_aic': float(best_aic),
            'distribution_params': distribution_params,
            'sample_size': len(data)
        }
    
    def generate_correlated_scenarios(self, assets_data: Dict[str, List[float]], 
                                    num_scenarios: int) -> Dict[str, List[List[float]]]:
        """
        Generate correlated scenarios for multiple assets.
        
        Args:
            assets_data: Dictionary mapping asset names to historical return data
            num_scenarios: Number of scenarios to generate
            
        Returns:
            Dictionary mapping asset names to lists of scenario paths
        """
        if not assets_data:
            raise ValueError("No asset data provided")
        
        if num_scenarios <= 0:
            raise ValueError("Number of scenarios must be positive")
        
        # Validate all assets have sufficient data
        for asset, data in assets_data.items():
            if len(data) < 10:
                raise ValueError(f"Insufficient data for asset {asset} (minimum 10 points required)")
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(assets_data)
        
        # Remove any rows with NaN or infinite values
        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        
        if len(df) < 10:
            raise ValueError("Insufficient valid data points after cleaning")
        
        # Calculate correlation matrix
        self.correlation_matrix = df.corr().values
        
        # Estimate parameters for each asset
        asset_parameters = {}
        for asset in df.columns:
            asset_parameters[asset] = self.estimate_parameters(df[asset].tolist())
        
        # Generate correlated random numbers using Cholesky decomposition
        try:
            cholesky_matrix = np.linalg.cholesky(self.correlation_matrix)
        except np.linalg.LinAlgError:
            # If correlation matrix is not positive definite, use nearest positive definite matrix
            self.logger.warning("Correlation matrix is not positive definite, using nearest PD matrix")
            cholesky_matrix = self._nearest_positive_definite_cholesky(self.correlation_matrix)
        
        # Generate scenarios
        scenarios = {}
        assets = list(df.columns)
        
        for scenario_idx in range(num_scenarios):
            # Generate independent standard normal random variables
            independent_randoms = np.random.standard_normal(len(assets))
            
            # Apply correlation structure
            correlated_randoms = cholesky_matrix @ independent_randoms
            
            # Transform to each asset's distribution
            scenario_values = {}
            for i, asset in enumerate(assets):
                params = asset_parameters[asset]
                
                # Transform standard normal to asset's distribution
                if params['best_distribution'] == 'normal':
                    value = params['mean'] + params['std'] * correlated_randoms[i]
                elif params['best_distribution'] == 't':
                    # For t-distribution, use inverse CDF transformation
                    u = norm.cdf(correlated_randoms[i])
                    dist_params = self.fitted_distributions.get('best', {}).get('params', [])
                    if dist_params:
                        value = stats.t.ppf(u, *dist_params)
                    else:
                        value = params['mean'] + params['std'] * correlated_randoms[i]
                else:
                    # Default to normal transformation
                    value = params['mean'] + params['std'] * correlated_randoms[i]
                
                scenario_values[asset] = value
            
            # Store scenario values
            for asset in assets:
                if asset not in scenarios:
                    scenarios[asset] = []
                scenarios[asset].append([scenario_values[asset]])
        
        # Convert single values to paths (for now, single-step scenarios)
        # In a more advanced implementation, this could generate multi-step paths
        result = {}
        for asset in assets:
            result[asset] = scenarios[asset]
        
        return result
    
    def generate_multi_step_scenarios(self, historical_data: List[float], 
                                    num_scenarios: int, 
                                    num_steps: int) -> List[List[float]]:
        """
        Generate multi-step scenario paths for a single asset.
        
        Args:
            historical_data: Historical return data
            num_scenarios: Number of scenarios to generate
            num_steps: Number of time steps in each scenario
            
        Returns:
            List of scenario paths, each containing num_steps values
        """
        if num_scenarios <= 0 or num_steps <= 0:
            raise ValueError("Number of scenarios and steps must be positive")
        
        # Estimate parameters
        params = self.estimate_parameters(historical_data)
        
        # Get best fitted distribution
        best_dist_info = self.fitted_distributions.get('best')
        if not best_dist_info:
            # Fallback to normal distribution
            distribution = stats.norm
            dist_params = (params['mean'], params['std'])
        else:
            distribution = best_dist_info['distribution']
            dist_params = best_dist_info['params']
        
        scenarios = []
        
        for _ in range(num_scenarios):
            scenario_path = []
            
            for _ in range(num_steps):
                # Generate random value from fitted distribution
                value = distribution.rvs(*dist_params)
                scenario_path.append(float(value))
            
            scenarios.append(scenario_path)
        
        return scenarios
    
    def validate_scenarios(self, scenarios: List[List[float]], 
                         historical_data: List[float]) -> Dict[str, float]:
        """
        Validate generated scenarios against historical data.
        
        Args:
            scenarios: Generated scenario paths
            historical_data: Original historical data
            
        Returns:
            Dictionary containing validation metrics
        """
        if not scenarios or not historical_data:
            raise ValueError("Both scenarios and historical data must be provided")
        
        # Flatten scenarios to compare distributions
        scenario_values = []
        for scenario in scenarios:
            scenario_values.extend(scenario)
        
        scenario_values = np.array(scenario_values)
        historical_values = np.array(historical_data)
        
        # Remove infinite and NaN values
        scenario_values = scenario_values[np.isfinite(scenario_values)]
        historical_values = historical_values[np.isfinite(historical_values)]
        
        if len(scenario_values) == 0 or len(historical_values) == 0:
            raise ValueError("No valid data points for validation")
        
        # Calculate statistical measures
        hist_mean = np.mean(historical_values)
        hist_std = np.std(historical_values, ddof=1)
        hist_skew = stats.skew(historical_values)
        hist_kurt = stats.kurtosis(historical_values)
        
        scen_mean = np.mean(scenario_values)
        scen_std = np.std(scenario_values, ddof=1)
        scen_skew = stats.skew(scenario_values)
        scen_kurt = stats.kurtosis(scenario_values)
        
        # Calculate differences
        mean_diff = abs(scen_mean - hist_mean)
        std_diff = abs(scen_std - hist_std)
        skew_diff = abs(scen_skew - hist_skew)
        kurt_diff = abs(scen_kurt - hist_kurt)
        
        # Kolmogorov-Smirnov test
        ks_stat, ks_pvalue = stats.ks_2samp(historical_values, scenario_values)
        
        # Anderson-Darling test (if sample sizes are reasonable)
        ad_stat = None
        ad_pvalue = None
        if len(historical_values) < 1000 and len(scenario_values) < 1000:
            try:
                ad_result = stats.anderson_ksamp([historical_values, scenario_values])
                ad_stat = ad_result.statistic
                ad_pvalue = ad_result.significance_level
            except Exception as e:
                self.logger.warning(f"Anderson-Darling test failed: {e}")
        
        return {
            'historical_mean': float(hist_mean),
            'scenario_mean': float(scen_mean),
            'mean_difference': float(mean_diff),
            'historical_std': float(hist_std),
            'scenario_std': float(scen_std),
            'std_difference': float(std_diff),
            'historical_skewness': float(hist_skew),
            'scenario_skewness': float(scen_skew),
            'skewness_difference': float(skew_diff),
            'historical_kurtosis': float(hist_kurt),
            'scenario_kurtosis': float(scen_kurt),
            'kurtosis_difference': float(kurt_diff),
            'ks_statistic': float(ks_stat),
            'ks_pvalue': float(ks_pvalue),
            'anderson_darling_stat': float(ad_stat) if ad_stat is not None else None,
            'anderson_darling_pvalue': float(ad_pvalue) if ad_pvalue is not None else None,
            'num_scenarios': len(scenarios),
            'total_scenario_points': len(scenario_values),
            'historical_sample_size': len(historical_values)
        }
    
    def extract_returns_from_trades(self, trades: List[ProcessedTrade]) -> List[float]:
        """
        Extract return percentages from processed trades.
        
        Args:
            trades: List of processed trades
            
        Returns:
            List of return percentages
        """
        if not trades:
            return []
        
        returns = []
        for trade in trades:
            if trade.entry_price > 0:  # Avoid division by zero
                return_pct = trade.return_percentage / 100.0  # Convert to decimal
                if np.isfinite(return_pct):  # Only include finite values
                    returns.append(return_pct)
        
        return returns
    
    def _nearest_positive_definite_cholesky(self, matrix: np.ndarray) -> np.ndarray:
        """
        Find the nearest positive definite matrix and return its Cholesky decomposition.
        
        Args:
            matrix: Input correlation matrix
            
        Returns:
            Cholesky decomposition of nearest positive definite matrix
        """
        # Eigenvalue decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        
        # Ensure all eigenvalues are positive
        eigenvalues = np.maximum(eigenvalues, 1e-8)
        
        # Reconstruct matrix
        pd_matrix = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        
        # Ensure it's a proper correlation matrix (diagonal elements = 1)
        diag_sqrt = np.sqrt(np.diag(pd_matrix))
        pd_matrix = pd_matrix / np.outer(diag_sqrt, diag_sqrt)
        
        return np.linalg.cholesky(pd_matrix)