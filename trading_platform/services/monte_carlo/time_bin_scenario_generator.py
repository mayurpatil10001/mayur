"""
Time-Bin Scenario Generator for Monte Carlo Risk Simulation

This service generates scenarios specifically for time-bin trading strategies,
supporting bootstrap, parametric, and regime-conditional scenario generation
for comprehensive risk analysis.

Requirements: 2.1, 2.2, 2.3
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from scipy import stats
from scipy.stats import norm, t, skewnorm, jarque_bera, anderson, shapiro
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture
from loguru import logger
from sqlalchemy.orm import Session

from ..time_bin_analyzer import TimeBin, TimeBinAnalyzer
from ..vix_regime_analyzer import VIXDataIntegration, VolatilityRegime, TradeRegimeAlignment
from ...models.database import ProcessedTrade
from ...database.connection import get_db_session


class ScenarioType(Enum):
    """Types of scenario generation methods."""
    BOOTSTRAP = "bootstrap"
    PARAMETRIC = "parametric"
    REGIME_CONDITIONAL = "regime_conditional"


class DistributionType(Enum):
    """Supported probability distributions for parametric scenarios."""
    NORMAL = "normal"
    T_DISTRIBUTION = "t_distribution"
    SKEWED_NORMAL = "skewed_normal"
    MIXTURE_NORMAL = "mixture_normal"


@dataclass
class DistributionFit:
    """Container for distribution fitting results."""
    distribution_type: DistributionType
    parameters: Dict[str, float]
    goodness_of_fit: Dict[str, float]
    aic: float
    bic: float
    log_likelihood: float


@dataclass
class ScenarioGenerationConfig:
    """Configuration for scenario generation."""
    num_scenarios: int = 10000
    scenario_length: int = 252  # Trading days (1 year)
    bootstrap_block_size: Optional[int] = None  # For block bootstrap
    confidence_levels: List[float] = None  # For validation
    random_seed: Optional[int] = None
    
    def __post_init__(self):
        if self.confidence_levels is None:
            self.confidence_levels = [0.95, 0.99, 0.999]


@dataclass
class ScenarioSet:
    """Container for generated scenarios with metadata."""
    scenarios: np.ndarray  # Shape: (num_scenarios, scenario_length)
    generation_method: ScenarioType
    distribution_fit: Optional[DistributionFit]
    statistical_properties: Dict[str, float]
    validation_results: Dict[str, Any]
    generation_config: ScenarioGenerationConfig
    generation_timestamp: datetime


@dataclass
class RegimeConditionalScenarios:
    """Container for regime-conditional scenarios."""
    low_regime_scenarios: ScenarioSet
    medium_regime_scenarios: ScenarioSet
    high_regime_scenarios: ScenarioSet
    regime_transition_probabilities: Dict[str, float]
    regime_persistence: Dict[str, float]


class TimeBinScenarioGenerator:
    """
    Advanced scenario generator for time-bin trading strategies.
    
    Supports multiple generation methods:
    - Bootstrap scenarios from historical time-bin trades
    - Parametric scenarios with distribution fitting
    - Regime-conditional scenarios based on VIX volatility regimes
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the time-bin scenario generator."""
        self.db_session = db_session or get_db_session()
        self.time_bin_analyzer = TimeBinAnalyzer(db_session=self.db_session)
        self.vix_analyzer = VIXDataIntegration(db_session=self.db_session)
        
        # Statistical fitting tools
        self.scaler = StandardScaler()
        self.supported_distributions = [
            DistributionType.NORMAL,
            DistributionType.T_DISTRIBUTION,
            DistributionType.SKEWED_NORMAL,
            DistributionType.MIXTURE_NORMAL
        ]
    
    def generate_bootstrap_scenarios(self, 
                                   account_name: str,
                                   hour: int,
                                   minute_bin: int,
                                   config: ScenarioGenerationConfig) -> ScenarioSet:
        """
        Generate bootstrap scenarios using historical time-bin trades.
        
        Bootstrap resampling preserves the empirical distribution of returns
        while allowing for scenario generation beyond the historical sample size.
        
        Args:
            account_name: Account to analyze
            hour: Hour of trading day (0-23)
            minute_bin: Minute bin (0 or 30)
            config: Scenario generation configuration
            
        Returns:
            ScenarioSet: Bootstrap scenarios with validation
        """
        logger.info(f"Generating bootstrap scenarios for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            # Set random seed for reproducibility
            if config.random_seed is not None:
                np.random.seed(config.random_seed)
            
            # Get historical time-bin trades
            time_bin = TimeBin(account_name=account_name, hour=hour, minute_bin=minute_bin)
            trades = self.time_bin_analyzer.get_time_bin_trades(time_bin)
            
            if len(trades) < 30:
                raise ValueError(f"Insufficient historical data: {len(trades)} trades (minimum 30 required)")
            
            # Extract daily P&L values
            historical_pnl = [trade.pnl for trade in trades]
            
            # Generate scenarios using bootstrap resampling
            scenarios = self._generate_bootstrap_samples(
                historical_pnl, config.num_scenarios, config.scenario_length, config.bootstrap_block_size
            )
            
            # Calculate statistical properties
            statistical_properties = self._calculate_statistical_properties(scenarios)
            
            # Validate scenarios
            validation_results = self._validate_scenarios(scenarios, historical_pnl, config)
            
            scenario_set = ScenarioSet(
                scenarios=scenarios,
                generation_method=ScenarioType.BOOTSTRAP,
                distribution_fit=None,  # Bootstrap doesn't use parametric fit
                statistical_properties=statistical_properties,
                validation_results=validation_results,
                generation_config=config,
                generation_timestamp=datetime.now()
            )
            
            logger.info(f"Generated {config.num_scenarios} bootstrap scenarios from {len(trades)} historical trades")
            return scenario_set
            
        except Exception as e:
            logger.error(f"Error generating bootstrap scenarios: {e}")
            raise ValueError(f"Failed to generate bootstrap scenarios: {e}")
    
    def generate_parametric_scenarios(self,
                                    account_name: str,
                                    hour: int,
                                    minute_bin: int,
                                    config: ScenarioGenerationConfig,
                                    distribution_type: Optional[DistributionType] = None) -> ScenarioSet:
        """
        Generate parametric scenarios with distribution fitting.
        
        Fits probability distributions to historical data and generates scenarios
        from the fitted distributions. Automatically selects best-fit distribution
        if none specified.
        
        Args:
            account_name: Account to analyze
            hour: Hour of trading day (0-23)
            minute_bin: Minute bin (0 or 30)
            config: Scenario generation configuration
            distribution_type: Specific distribution to use (auto-select if None)
            
        Returns:
            ScenarioSet: Parametric scenarios with distribution fit details
        """
        logger.info(f"Generating parametric scenarios for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            if config.random_seed is not None:
                np.random.seed(config.random_seed)
            
            # Get historical data
            time_bin = TimeBin(account_name=account_name, hour=hour, minute_bin=minute_bin)
            trades = self.time_bin_analyzer.get_time_bin_trades(time_bin)
            
            if len(trades) < 50:
                raise ValueError(f"Insufficient data for parametric fitting: {len(trades)} trades (minimum 50 required)")
            
            historical_pnl = [trade.pnl for trade in trades]
            
            # Fit distribution
            if distribution_type is None:
                distribution_fit = self._find_best_distribution_fit(historical_pnl)
            else:
                distribution_fit = self._fit_specific_distribution(historical_pnl, distribution_type)
            
            # Generate scenarios from fitted distribution
            scenarios = self._generate_parametric_samples(distribution_fit, config.num_scenarios, config.scenario_length)
            
            # Calculate statistical properties
            statistical_properties = self._calculate_statistical_properties(scenarios)
            
            # Validate scenarios
            validation_results = self._validate_scenarios(scenarios, historical_pnl, config)
            
            scenario_set = ScenarioSet(
                scenarios=scenarios,
                generation_method=ScenarioType.PARAMETRIC,
                distribution_fit=distribution_fit,
                statistical_properties=statistical_properties,
                validation_results=validation_results,
                generation_config=config,
                generation_timestamp=datetime.now()
            )
            
            logger.info(f"Generated {config.num_scenarios} parametric scenarios using {distribution_fit.distribution_type.value}")
            return scenario_set
            
        except Exception as e:
            logger.error(f"Error generating parametric scenarios: {e}")
            raise ValueError(f"Failed to generate parametric scenarios: {e}")
    
    def generate_regime_conditional_scenarios(self,
                                            account_name: str,
                                            hour: int,
                                            minute_bin: int,
                                            config: ScenarioGenerationConfig) -> RegimeConditionalScenarios:
        """
        Generate regime-conditional scenarios based on VIX volatility regimes.
        
        Creates separate scenario sets for Low, Medium, and High volatility regimes,
        incorporating regime transition probabilities and persistence patterns.
        
        Args:
            account_name: Account to analyze
            hour: Hour of trading day (0-23)
            minute_bin: Minute bin (0 or 30)
            config: Scenario generation configuration
            
        Returns:
            RegimeConditionalScenarios: Regime-specific scenario sets
        """
        logger.info(f"Generating regime-conditional scenarios for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            if config.random_seed is not None:
                np.random.seed(config.random_seed)
            
            # Get VIX-trade alignments
            alignments = self.vix_analyzer.synchronize_vix_with_trades(account_name)
            
            # Filter by time bin
            time_bin_alignments = self._filter_alignments_by_time_bin(alignments, hour, minute_bin)
            
            if len(time_bin_alignments) < 50:
                raise ValueError(f"Insufficient regime data: {len(time_bin_alignments)} aligned trades")
            
            # Separate trades by regime
            regime_trades = self._separate_trades_by_regime(time_bin_alignments)
            
            # Calculate regime transition probabilities
            transition_probs = self._calculate_regime_transition_probabilities(time_bin_alignments)
            regime_persistence = self._calculate_regime_persistence(time_bin_alignments)
            
            # Generate scenarios for each regime
            low_scenarios = self._generate_regime_specific_scenarios(
                regime_trades.get(VolatilityRegime.LOW, []), config, "Low"
            )
            
            medium_scenarios = self._generate_regime_specific_scenarios(
                regime_trades.get(VolatilityRegime.MEDIUM, []), config, "Medium"  
            )
            
            high_scenarios = self._generate_regime_specific_scenarios(
                regime_trades.get(VolatilityRegime.HIGH, []), config, "High"
            )
            
            regime_conditional_scenarios = RegimeConditionalScenarios(
                low_regime_scenarios=low_scenarios,
                medium_regime_scenarios=medium_scenarios,
                high_regime_scenarios=high_scenarios,
                regime_transition_probabilities=transition_probs,
                regime_persistence=regime_persistence
            )
            
            logger.info(f"Generated regime-conditional scenarios: "
                       f"Low={low_scenarios.scenarios.shape[0]}, "
                       f"Medium={medium_scenarios.scenarios.shape[0]}, "
                       f"High={high_scenarios.scenarios.shape[0]}")
            
            return regime_conditional_scenarios
            
        except Exception as e:
            logger.error(f"Error generating regime-conditional scenarios: {e}")
            raise ValueError(f"Failed to generate regime-conditional scenarios: {e}")
    
    def validate_scenario_properties(self, scenario_set: ScenarioSet, 
                                   historical_data: List[float]) -> Dict[str, Any]:
        """
        Comprehensive validation of scenario statistical properties.
        
        Args:
            scenario_set: Generated scenario set
            historical_data: Historical data for comparison
            
        Returns:
            Dict: Detailed validation results
        """
        logger.info("Validating scenario statistical properties")
        
        try:
            validation_results = {}
            
            # Flatten scenarios for analysis
            scenario_data = scenario_set.scenarios.flatten()
            
            # Statistical tests
            validation_results.update(self._run_distribution_tests(scenario_data, historical_data))
            validation_results.update(self._run_moment_tests(scenario_data, historical_data))
            validation_results.update(self._run_independence_tests(scenario_set.scenarios))
            validation_results.update(self._run_stationarity_tests(scenario_set.scenarios))
            
            # Overall validation score
            validation_results['overall_validation_score'] = self._calculate_validation_score(validation_results)
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating scenario properties: {e}")
            return {"error": str(e)}
    
    def _generate_bootstrap_samples(self, historical_data: List[float], 
                                  num_scenarios: int, scenario_length: int,
                                  block_size: Optional[int] = None) -> np.ndarray:
        """Generate bootstrap samples with optional block bootstrap."""
        historical_array = np.array(historical_data)
        
        if block_size is not None and block_size > 1:
            # Block bootstrap for time series dependence
            return self._block_bootstrap(historical_array, num_scenarios, scenario_length, block_size)
        else:
            # Simple bootstrap
            scenarios = np.random.choice(historical_array, size=(num_scenarios, scenario_length), replace=True)
            return scenarios
    
    def _block_bootstrap(self, data: np.ndarray, num_scenarios: int, 
                        scenario_length: int, block_size: int) -> np.ndarray:
        """Generate block bootstrap samples to preserve time series structure."""
        scenarios = np.zeros((num_scenarios, scenario_length))
        
        for i in range(num_scenarios):
            scenario = []
            while len(scenario) < scenario_length:
                # Random starting point for block
                start_idx = np.random.randint(0, max(1, len(data) - block_size + 1))
                end_idx = min(start_idx + block_size, len(data))
                block = data[start_idx:end_idx]
                scenario.extend(block)
            
            scenarios[i, :] = scenario[:scenario_length]
        
        return scenarios
    
    def _find_best_distribution_fit(self, data: List[float]) -> DistributionFit:
        """Find the best-fitting distribution using multiple criteria."""
        data_array = np.array(data)
        best_fit = None
        best_score = float('inf')
        
        for dist_type in self.supported_distributions:
            try:
                fit = self._fit_specific_distribution(data, dist_type)
                # Use AIC as primary selection criterion
                if fit.aic < best_score:
                    best_score = fit.aic
                    best_fit = fit
            except Exception as e:
                logger.warning(f"Failed to fit {dist_type.value}: {e}")
                continue
        
        if best_fit is None:
            # Fallback to normal distribution
            logger.warning("All distribution fits failed, using normal distribution")
            best_fit = self._fit_specific_distribution(data, DistributionType.NORMAL)
        
        return best_fit
    
    def _fit_specific_distribution(self, data: List[float], 
                                 dist_type: DistributionType) -> DistributionFit:
        """Fit a specific distribution to the data."""
        data_array = np.array(data)
        
        if dist_type == DistributionType.NORMAL:
            params = stats.norm.fit(data_array)
            log_likelihood = np.sum(stats.norm.logpdf(data_array, *params))
            
        elif dist_type == DistributionType.T_DISTRIBUTION:
            params = stats.t.fit(data_array)
            log_likelihood = np.sum(stats.t.logpdf(data_array, *params))
            
        elif dist_type == DistributionType.SKEWED_NORMAL:
            params = stats.skewnorm.fit(data_array)
            log_likelihood = np.sum(stats.skewnorm.logpdf(data_array, *params))
            
        elif dist_type == DistributionType.MIXTURE_NORMAL:
            # Fit Gaussian Mixture Model
            gm = GaussianMixture(n_components=2, random_state=42)
            gm.fit(data_array.reshape(-1, 1))
            params = {
                'weights': gm.weights_.tolist(),
                'means': gm.means_.flatten().tolist(),
                'covariances': gm.covariances_.flatten().tolist()
            }
            log_likelihood = gm.score_samples(data_array.reshape(-1, 1)).sum()
            
        else:
            raise ValueError(f"Unsupported distribution type: {dist_type}")
        
        # Calculate information criteria
        k = len(params) if isinstance(params, (tuple, list)) else len(params.values())
        n = len(data_array)
        aic = 2 * k - 2 * log_likelihood
        bic = k * np.log(n) - 2 * log_likelihood
        
        # Goodness of fit tests
        goodness_tests = self._run_goodness_of_fit_tests(data_array, dist_type, params)
        
        return DistributionFit(
            distribution_type=dist_type,
            parameters=params if isinstance(params, dict) else dict(enumerate(params)),
            goodness_of_fit=goodness_tests,
            aic=aic,
            bic=bic,
            log_likelihood=log_likelihood
        )
    
    def _generate_parametric_samples(self, distribution_fit: DistributionFit,
                                   num_scenarios: int, scenario_length: int) -> np.ndarray:
        """Generate samples from fitted distribution."""
        dist_type = distribution_fit.distribution_type
        params = distribution_fit.parameters
        
        if dist_type == DistributionType.NORMAL:
            loc, scale = params[0], params[1]
            scenarios = np.random.normal(loc, scale, size=(num_scenarios, scenario_length))
            
        elif dist_type == DistributionType.T_DISTRIBUTION:
            df, loc, scale = params[0], params[1], params[2]
            scenarios = stats.t.rvs(df, loc, scale, size=(num_scenarios, scenario_length))
            
        elif dist_type == DistributionType.SKEWED_NORMAL:
            a, loc, scale = params[0], params[1], params[2]
            scenarios = stats.skewnorm.rvs(a, loc, scale, size=(num_scenarios, scenario_length))
            
        elif dist_type == DistributionType.MIXTURE_NORMAL:
            # Generate from mixture model
            scenarios = np.zeros((num_scenarios, scenario_length))
            weights = params['weights']
            means = params['means']
            stds = np.sqrt(params['covariances'])
            
            for i in range(num_scenarios):
                for j in range(scenario_length):
                    # Choose component based on weights
                    component = np.random.choice(len(weights), p=weights)
                    scenarios[i, j] = np.random.normal(means[component], stds[component])
        
        else:
            raise ValueError(f"Unsupported distribution type: {dist_type}")
        
        return scenarios
    
    def _filter_alignments_by_time_bin(self, alignments: List[TradeRegimeAlignment],
                                     hour: int, minute_bin: int) -> List[TradeRegimeAlignment]:
        """Filter trade alignments by specific time bin."""
        filtered = []
        for alignment in alignments:
            trade_hour = alignment.trade_timestamp.hour
            trade_minute = alignment.trade_timestamp.minute
            trade_minute_bin = 0 if trade_minute < 30 else 30
            
            if trade_hour == hour and trade_minute_bin == minute_bin:
                filtered.append(alignment)
        
        return filtered
    
    def _separate_trades_by_regime(self, alignments: List[TradeRegimeAlignment]) -> Dict[VolatilityRegime, List[float]]:
        """Separate trades by volatility regime."""
        regime_trades = {
            VolatilityRegime.LOW: [],
            VolatilityRegime.MEDIUM: [],
            VolatilityRegime.HIGH: []
        }
        
        for alignment in alignments:
            regime_trades[alignment.regime].append(alignment.trade_pnl)
        
        return regime_trades
    
    def _calculate_regime_transition_probabilities(self, alignments: List[TradeRegimeAlignment]) -> Dict[str, float]:
        """Calculate regime transition probabilities."""
        if len(alignments) < 2:
            return {}
        
        # Sort by timestamp
        sorted_alignments = sorted(alignments, key=lambda x: x.trade_timestamp)
        
        transitions = {}
        total_transitions = 0
        
        for i in range(1, len(sorted_alignments)):
            prev_regime = sorted_alignments[i-1].regime
            curr_regime = sorted_alignments[i].regime
            
            transition_key = f"{prev_regime.value}_to_{curr_regime.value}"
            transitions[transition_key] = transitions.get(transition_key, 0) + 1
            total_transitions += 1
        
        # Convert to probabilities
        if total_transitions > 0:
            return {k: v / total_transitions for k, v in transitions.items()}
        return {}
    
    def _calculate_regime_persistence(self, alignments: List[TradeRegimeAlignment]) -> Dict[str, float]:
        """Calculate average regime persistence (days in same regime)."""
        if len(alignments) < 2:
            return {}
        
        sorted_alignments = sorted(alignments, key=lambda x: x.trade_timestamp)
        
        regime_durations = {regime.value: [] for regime in VolatilityRegime}
        current_regime = sorted_alignments[0].regime
        regime_start = sorted_alignments[0].trade_timestamp
        
        for alignment in sorted_alignments[1:]:
            if alignment.regime != current_regime:
                # Regime changed
                duration = (alignment.trade_timestamp - regime_start).days
                regime_durations[current_regime.value].append(duration)
                current_regime = alignment.regime
                regime_start = alignment.trade_timestamp
        
        # Calculate average persistence
        persistence = {}
        for regime, durations in regime_durations.items():
            if durations:
                persistence[f"{regime}_avg_persistence_days"] = np.mean(durations)
        
        return persistence
    
    def _generate_regime_specific_scenarios(self, regime_trades: List[float],
                                          config: ScenarioGenerationConfig,
                                          regime_name: str) -> ScenarioSet:
        """Generate scenarios for a specific regime."""
        if len(regime_trades) < 10:
            logger.warning(f"Insufficient data for {regime_name} regime: {len(regime_trades)} trades")
            # Generate minimal scenarios using available data
            if regime_trades:
                scenarios = np.random.choice(regime_trades, size=(max(100, config.num_scenarios // 10), 
                                                               min(30, config.scenario_length)), replace=True)
            else:
                scenarios = np.zeros((100, 30))  # Empty scenarios
        else:
            # Use bootstrap for regime-specific scenarios
            scenarios = self._generate_bootstrap_samples(
                regime_trades, config.num_scenarios // 3, config.scenario_length
            )
        
        statistical_properties = self._calculate_statistical_properties(scenarios)
        validation_results = self._validate_scenarios(scenarios, regime_trades, config)
        
        return ScenarioSet(
            scenarios=scenarios,
            generation_method=ScenarioType.REGIME_CONDITIONAL,
            distribution_fit=None,
            statistical_properties=statistical_properties,
            validation_results=validation_results,
            generation_config=config,
            generation_timestamp=datetime.now()
        )
    
    def _calculate_statistical_properties(self, scenarios: np.ndarray) -> Dict[str, float]:
        """Calculate statistical properties of generated scenarios."""
        flat_scenarios = scenarios.flatten()
        
        return {
            'mean': float(np.mean(flat_scenarios)),
            'std': float(np.std(flat_scenarios)),
            'skewness': float(stats.skew(flat_scenarios)),
            'kurtosis': float(stats.kurtosis(flat_scenarios)),
            'min': float(np.min(flat_scenarios)),
            'max': float(np.max(flat_scenarios)),
            'median': float(np.median(flat_scenarios)),
            'q25': float(np.percentile(flat_scenarios, 25)),
            'q75': float(np.percentile(flat_scenarios, 75)),
            'var_95': float(np.percentile(flat_scenarios, 5)),  # 95% VaR
            'var_99': float(np.percentile(flat_scenarios, 1)),  # 99% VaR
        }
    
    def _validate_scenarios(self, scenarios: np.ndarray, historical_data: List[float],
                          config: ScenarioGenerationConfig) -> Dict[str, Any]:
        """Validate generated scenarios against historical data."""
        validation = {}
        
        try:
            flat_scenarios = scenarios.flatten()
            hist_array = np.array(historical_data)
            
            # Moment comparisons
            validation['mean_diff'] = abs(np.mean(flat_scenarios) - np.mean(hist_array))
            validation['std_diff'] = abs(np.std(flat_scenarios) - np.std(hist_array))
            validation['skew_diff'] = abs(stats.skew(flat_scenarios) - stats.skew(hist_array))
            
            # Distribution tests
            if len(hist_array) >= 20 and len(flat_scenarios) >= 20:
                ks_stat, ks_p = stats.ks_2samp(flat_scenarios, hist_array)
                validation['ks_statistic'] = ks_stat
                validation['ks_p_value'] = ks_p
                validation['distributions_similar'] = ks_p > 0.05
            
            # Scenario quality checks
            validation['num_scenarios'] = scenarios.shape[0]
            validation['scenario_length'] = scenarios.shape[1]
            validation['total_observations'] = scenarios.size
            
            return validation
            
        except Exception as e:
            logger.error(f"Error in scenario validation: {e}")
            return {'validation_error': str(e)}
    
    def _run_goodness_of_fit_tests(self, data: np.ndarray, dist_type: DistributionType, 
                                  params) -> Dict[str, float]:
        """Run goodness of fit tests for distribution."""
        tests = {}
        
        try:
            # Jarque-Bera test for normality
            if dist_type == DistributionType.NORMAL:
                jb_stat, jb_p = jarque_bera(data)
                tests['jarque_bera_stat'] = jb_stat
                tests['jarque_bera_p'] = jb_p
            
            # Anderson-Darling test
            try:
                ad_stat, ad_crit, ad_sig = anderson(data, dist='norm')
                tests['anderson_darling_stat'] = ad_stat
            except:
                pass
            
            # Shapiro-Wilk test (for small samples)
            if len(data) <= 5000:
                sw_stat, sw_p = shapiro(data)
                tests['shapiro_wilk_stat'] = sw_stat
                tests['shapiro_wilk_p'] = sw_p
            
        except Exception as e:
            logger.warning(f"Some goodness-of-fit tests failed: {e}")
        
        return tests
    
    def _run_distribution_tests(self, scenario_data: np.ndarray, 
                              historical_data: List[float]) -> Dict[str, Any]:
        """Run distribution comparison tests."""
        tests = {}
        
        try:
            hist_array = np.array(historical_data)
            
            # Kolmogorov-Smirnov test
            ks_stat, ks_p = stats.ks_2samp(scenario_data, hist_array)
            tests['ks_test'] = {'statistic': ks_stat, 'p_value': ks_p, 'similar': ks_p > 0.05}
            
            # Mann-Whitney U test  
            mw_stat, mw_p = stats.mannwhitneyu(scenario_data, hist_array, alternative='two-sided')
            tests['mann_whitney_test'] = {'statistic': mw_stat, 'p_value': mw_p, 'similar': mw_p > 0.05}
            
        except Exception as e:
            tests['distribution_tests_error'] = str(e)
        
        return tests
    
    def _run_moment_tests(self, scenario_data: np.ndarray, historical_data: List[float]) -> Dict[str, Any]:
        """Run moment comparison tests."""
        tests = {}
        
        try:
            hist_array = np.array(historical_data)
            
            # Moment comparisons with relative differences
            tests['moment_tests'] = {
                'mean_rel_diff': abs(np.mean(scenario_data) - np.mean(hist_array)) / (abs(np.mean(hist_array)) + 1e-8),
                'std_rel_diff': abs(np.std(scenario_data) - np.std(hist_array)) / (np.std(hist_array) + 1e-8),
                'skew_diff': abs(stats.skew(scenario_data) - stats.skew(hist_array)),
                'kurtosis_diff': abs(stats.kurtosis(scenario_data) - stats.kurtosis(hist_array))
            }
            
            # Overall moment similarity score
            rel_diffs = [tests['moment_tests']['mean_rel_diff'], tests['moment_tests']['std_rel_diff']]
            tests['moment_similarity_score'] = 1.0 / (1.0 + np.mean(rel_diffs))
            
        except Exception as e:
            tests['moment_tests_error'] = str(e)
        
        return tests
    
    def _run_independence_tests(self, scenarios: np.ndarray) -> Dict[str, Any]:
        """Run independence tests on scenario paths."""
        tests = {}
        
        try:
            # Test a sample of scenarios for independence
            sample_size = min(100, scenarios.shape[0])
            sample_scenarios = scenarios[:sample_size, :]
            
            autocorrelations = []
            for scenario in sample_scenarios:
                if len(scenario) > 10:
                    # Calculate lag-1 autocorrelation
                    autocorr = np.corrcoef(scenario[:-1], scenario[1:])[0, 1]
                    if not np.isnan(autocorr):
                        autocorrelations.append(autocorr)
            
            if autocorrelations:
                tests['independence_tests'] = {
                    'mean_autocorr_lag1': np.mean(autocorrelations),
                    'max_autocorr_lag1': np.max(np.abs(autocorrelations)),
                    'independence_score': 1.0 - min(1.0, np.mean(np.abs(autocorrelations)))
                }
            
        except Exception as e:
            tests['independence_tests_error'] = str(e)
        
        return tests
    
    def _run_stationarity_tests(self, scenarios: np.ndarray) -> Dict[str, Any]:
        """Run stationarity tests on scenario paths."""
        tests = {}
        
        try:
            # Simple stationarity check: compare first and second half statistics
            sample_size = min(50, scenarios.shape[0])
            sample_scenarios = scenarios[:sample_size, :]
            
            stationarity_scores = []
            for scenario in sample_scenarios:
                if len(scenario) >= 20:
                    mid = len(scenario) // 2
                    first_half = scenario[:mid]
                    second_half = scenario[mid:]
                    
                    # Compare means and stds
                    mean_diff = abs(np.mean(first_half) - np.mean(second_half))
                    std_diff = abs(np.std(first_half) - np.std(second_half))
                    
                    # Simple stationarity score
                    score = 1.0 / (1.0 + mean_diff + std_diff)
                    stationarity_scores.append(score)
            
            if stationarity_scores:
                tests['stationarity_tests'] = {
                    'mean_stationarity_score': np.mean(stationarity_scores),
                    'min_stationarity_score': np.min(stationarity_scores)
                }
            
        except Exception as e:
            tests['stationarity_tests_error'] = str(e)
        
        return tests
    
    def _calculate_validation_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall validation score from test results."""
        try:
            scores = []
            
            # Distribution similarity
            if 'ks_test' in validation_results and validation_results['ks_test']['similar']:
                scores.append(0.3)
            
            # Moment similarity
            if 'moment_similarity_score' in validation_results:
                scores.append(0.3 * validation_results['moment_similarity_score'])
            
            # Independence
            if 'independence_tests' in validation_results:
                independence_score = validation_results['independence_tests'].get('independence_score', 0)
                scores.append(0.2 * independence_score)
            
            # Stationarity
            if 'stationarity_tests' in validation_results:
                stationarity_score = validation_results['stationarity_tests'].get('mean_stationarity_score', 0)
                scores.append(0.2 * stationarity_score)
            
            return sum(scores) if scores else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating validation score: {e}")
            return 0.0