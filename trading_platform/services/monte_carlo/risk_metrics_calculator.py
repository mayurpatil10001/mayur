"""
Risk Metrics Calculator for comprehensive Monte Carlo risk analysis.

This service calculates various risk metrics from scenario distributions including
Value at Risk (VaR), Expected Shortfall (ES), tail risk metrics, and probability
assessments for comprehensive risk evaluation.

Requirements: 2.2, 2.4, 2.5
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
from scipy import stats
from scipy.stats import norm, genextreme, pareto
from loguru import logger
import warnings

from .time_bin_scenario_generator import ScenarioSet, RegimeConditionalScenarios, ScenarioType


class RiskMeasureType(Enum):
    """Types of risk measures for calculation."""
    PARAMETRIC = "parametric"
    HISTORICAL = "historical" 
    MONTE_CARLO = "monte_carlo"


class TailRiskModel(Enum):
    """Extreme value models for tail risk analysis."""
    GENERALIZED_EXTREME_VALUE = "gev"
    PARETO = "pareto"
    EMPIRICAL = "empirical"


@dataclass
class VaRResult:
    """Container for Value at Risk calculation results."""
    confidence_level: float
    var_absolute: float  # Absolute VaR value
    var_percentage: float  # VaR as percentage of capital
    calculation_method: RiskMeasureType
    sample_size: int
    calculation_timestamp: datetime
    percentile_rank: float  # Percentile in the distribution
    worst_case_scenario: Optional[float] = None  # Worst scenario if available


@dataclass 
class ExpectedShortfallResult:
    """Container for Expected Shortfall (Conditional VaR) results."""
    confidence_level: float
    expected_shortfall: float  # Average loss beyond VaR
    var_threshold: float  # VaR threshold
    tail_scenarios_count: int  # Number of scenarios beyond VaR
    calculation_method: RiskMeasureType
    sample_size: int
    calculation_timestamp: datetime
    tail_scenarios: Optional[List[float]] = None  # Actual tail scenarios


@dataclass
class TailRiskMetrics:
    """Container for comprehensive tail risk analysis."""
    extreme_value_model: TailRiskModel
    model_parameters: Dict[str, float]
    return_level_99_9: float  # 99.9% return level (1 in 1000)
    return_level_99_95: float  # 99.95% return level (1 in 2000)
    return_level_99_99: float  # 99.99% return level (1 in 10000)
    tail_index: Optional[float]  # Tail index for power law distributions
    model_fit_quality: Dict[str, float]  # Goodness of fit metrics
    calculation_timestamp: datetime
    worst_historical_loss: float
    tail_concentration: float  # Concentration of losses in tail


@dataclass
class ProbabilityMetrics:
    """Container for probability-based risk metrics."""
    probability_of_profit: float  # P(return > 0)
    probability_of_loss: float  # P(return < 0)
    probability_large_loss: Dict[str, float]  # P(loss > threshold) for different thresholds
    probability_large_gain: Dict[str, float]  # P(gain > threshold) for different thresholds
    expected_positive_return: float  # E[return | return > 0]
    expected_negative_return: float  # E[return | return < 0]
    gain_loss_ratio: float  # Expected gain / Expected loss
    kelly_criterion: Optional[float]  # Optimal position size
    calculation_timestamp: datetime


@dataclass
class ComprehensiveRiskReport:
    """Container for complete risk analysis results."""
    var_results: Dict[str, VaRResult]  # VaR at different confidence levels
    expected_shortfall_results: Dict[str, ExpectedShortfallResult]  # ES results
    tail_risk_metrics: TailRiskMetrics
    probability_metrics: ProbabilityMetrics
    scenario_summary: Dict[str, Any]  # Summary statistics of scenarios
    risk_decomposition: Dict[str, float]  # Risk contribution analysis
    regime_risk_analysis: Optional[Dict[str, Any]]  # Regime-specific risk if applicable
    calculation_config: Dict[str, Any]  # Configuration used for calculations
    generation_timestamp: datetime


class RiskMetricsCalculator:
    """
    Advanced risk metrics calculator for Monte Carlo scenario analysis.
    
    Calculates Value at Risk (VaR), Expected Shortfall (ES), tail risk metrics,
    and probability assessments from scenario distributions with multiple
    methodologies and comprehensive validation.
    """
    
    def __init__(self, default_confidence_levels: Optional[List[float]] = None):
        """
        Initialize risk metrics calculator.
        
        Args:
            default_confidence_levels: Default confidence levels for VaR/ES calculations
        """
        self.default_confidence_levels = default_confidence_levels or [0.95, 0.99, 0.999]
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        
        # Validation thresholds
        self.min_scenarios_parametric = 1000
        self.min_scenarios_historical = 100
        self.min_tail_scenarios = 10
        
        logger.info("RiskMetricsCalculator initialized with confidence levels: {}", 
                   self.default_confidence_levels)
    
    def calculate_var(self, 
                     scenarios: np.ndarray,
                     confidence_levels: Optional[List[float]] = None,
                     method: RiskMeasureType = RiskMeasureType.MONTE_CARLO,
                     portfolio_value: float = 100000) -> Dict[str, VaRResult]:
        """
        Calculate Value at Risk (VaR) at multiple confidence levels.
        
        VaR represents the maximum expected loss over a specific time period
        at a given confidence level. For example, 95% VaR is the loss that
        will not be exceeded 95% of the time.
        
        Args:
            scenarios: Array of scenario returns/P&L values
            confidence_levels: List of confidence levels (e.g., [0.95, 0.99, 0.999])
            method: Calculation method (parametric, historical, monte_carlo)
            portfolio_value: Portfolio value for percentage calculations
            
        Returns:
            Dictionary mapping confidence level strings to VaRResult objects
        """
        logger.info("Calculating VaR for {} scenarios using {} method", 
                   len(scenarios), method.value)
        
        try:
            confidence_levels = confidence_levels or self.default_confidence_levels
            scenarios_flat = scenarios.flatten() if scenarios.ndim > 1 else scenarios
            
            # Validate input
            self._validate_scenarios_for_risk_calc(scenarios_flat, method)
            
            var_results = {}
            
            for conf_level in confidence_levels:
                if method == RiskMeasureType.PARAMETRIC:
                    var_result = self._calculate_parametric_var(
                        scenarios_flat, conf_level, portfolio_value
                    )
                else:  # Historical or Monte Carlo (both use empirical approach)
                    var_result = self._calculate_empirical_var(
                        scenarios_flat, conf_level, portfolio_value, method
                    )
                
                var_results[f"{conf_level:.1%}"] = var_result
            
            logger.info("VaR calculated for {} confidence levels", len(confidence_levels))
            return var_results
            
        except Exception as e:
            logger.error("Error calculating VaR: {}", e)
            raise ValueError(f"VaR calculation failed: {e}")
    
    def calculate_expected_shortfall(self,
                                   scenarios: np.ndarray,
                                   confidence_levels: Optional[List[float]] = None,
                                   method: RiskMeasureType = RiskMeasureType.MONTE_CARLO) -> Dict[str, ExpectedShortfallResult]:
        """
        Calculate Expected Shortfall (Conditional VaR) at multiple confidence levels.
        
        Expected Shortfall is the average loss beyond the VaR threshold, providing
        information about the tail risk that VaR does not capture. ES is a coherent
        risk measure and provides better tail risk assessment than VaR alone.
        
        Args:
            scenarios: Array of scenario returns/P&L values
            confidence_levels: List of confidence levels
            method: Calculation method
            
        Returns:
            Dictionary mapping confidence level strings to ExpectedShortfallResult objects
        """
        logger.info("Calculating Expected Shortfall for {} scenarios", len(scenarios))
        
        try:
            confidence_levels = confidence_levels or self.default_confidence_levels
            scenarios_flat = scenarios.flatten() if scenarios.ndim > 1 else scenarios
            
            # Validate input
            self._validate_scenarios_for_risk_calc(scenarios_flat, method)
            
            es_results = {}
            
            for conf_level in confidence_levels:
                # First calculate VaR threshold
                var_threshold = np.percentile(scenarios_flat, (1 - conf_level) * 100)
                
                # Find scenarios beyond VaR (tail scenarios)
                tail_scenarios = scenarios_flat[scenarios_flat <= var_threshold]
                
                if len(tail_scenarios) < self.min_tail_scenarios:
                    logger.warning("Insufficient tail scenarios ({}) for reliable ES at {}% confidence",
                                 len(tail_scenarios), conf_level * 100)
                
                # Calculate Expected Shortfall as mean of tail scenarios
                expected_shortfall = np.mean(tail_scenarios) if len(tail_scenarios) > 0 else var_threshold
                
                es_result = ExpectedShortfallResult(
                    confidence_level=conf_level,
                    expected_shortfall=expected_shortfall,
                    var_threshold=var_threshold,
                    tail_scenarios_count=len(tail_scenarios),
                    calculation_method=method,
                    sample_size=len(scenarios_flat),
                    calculation_timestamp=datetime.now(),
                    tail_scenarios=tail_scenarios.tolist() if len(tail_scenarios) <= 100 else None
                )
                
                es_results[f"{conf_level:.1%}"] = es_result
            
            logger.info("Expected Shortfall calculated for {} confidence levels", 
                       len(confidence_levels))
            return es_results
            
        except Exception as e:
            logger.error("Error calculating Expected Shortfall: {}", e)
            raise ValueError(f"Expected Shortfall calculation failed: {e}")
    
    def calculate_tail_risk_metrics(self,
                                  scenarios: np.ndarray,
                                  tail_model: TailRiskModel = TailRiskModel.GENERALIZED_EXTREME_VALUE) -> TailRiskMetrics:
        """
        Calculate comprehensive tail risk metrics using extreme value theory.
        
        Analyzes the tail behavior of the loss distribution using extreme value
        models to estimate rare event probabilities and extreme loss scenarios
        beyond what traditional VaR/ES can capture.
        
        Args:
            scenarios: Array of scenario returns/P&L values  
            tail_model: Extreme value model to use for tail analysis
            
        Returns:
            TailRiskMetrics object with comprehensive tail risk analysis
        """
        logger.info("Calculating tail risk metrics using {} model", tail_model.value)
        
        try:
            scenarios_flat = scenarios.flatten() if scenarios.ndim > 1 else scenarios
            losses = -scenarios_flat  # Convert to losses (positive values)
            
            # Extract extreme losses for model fitting
            threshold = np.percentile(losses, 95)  # Focus on top 5% losses
            extreme_losses = losses[losses > threshold]
            
            if len(extreme_losses) < 20:
                logger.warning("Insufficient extreme losses ({}) for reliable tail modeling", 
                             len(extreme_losses))
            
            # Fit extreme value model
            if tail_model == TailRiskModel.GENERALIZED_EXTREME_VALUE:
                tail_metrics = self._fit_gev_model(losses, extreme_losses)
            elif tail_model == TailRiskModel.PARETO:
                tail_metrics = self._fit_pareto_model(extreme_losses, threshold)
            else:  # Empirical
                tail_metrics = self._calculate_empirical_tail_metrics(losses)
            
            logger.info("Tail risk metrics calculated using {} model", tail_model.value)
            return tail_metrics
            
        except Exception as e:
            logger.error("Error calculating tail risk metrics: {}", e)
            raise ValueError(f"Tail risk metrics calculation failed: {e}")
    
    def calculate_probability_of_profit(self, scenarios: np.ndarray) -> ProbabilityMetrics:
        """
        Calculate probability-based risk and return metrics.
        
        Analyzes the probability distribution of scenarios to calculate
        various probability metrics including profit probability, loss
        probabilities at different thresholds, and expected returns.
        
        Args:
            scenarios: Array of scenario returns/P&L values
            
        Returns:
            ProbabilityMetrics object with comprehensive probability analysis
        """
        logger.info("Calculating probability metrics for {} scenarios", len(scenarios))
        
        try:
            scenarios_flat = scenarios.flatten() if scenarios.ndim > 1 else scenarios
            
            if len(scenarios_flat) < 100:
                logger.warning("Small sample size ({}) may affect probability metric reliability",
                             len(scenarios_flat))
            
            # Basic probability calculations
            probability_of_profit = np.mean(scenarios_flat > 0)
            probability_of_loss = np.mean(scenarios_flat < 0)
            
            # Expected returns conditional on profit/loss
            positive_scenarios = scenarios_flat[scenarios_flat > 0]
            negative_scenarios = scenarios_flat[scenarios_flat < 0]
            
            expected_positive_return = np.mean(positive_scenarios) if len(positive_scenarios) > 0 else 0.0
            expected_negative_return = np.mean(negative_scenarios) if len(negative_scenarios) > 0 else 0.0
            
            # Gain/Loss ratio
            gain_loss_ratio = (abs(expected_positive_return) / abs(expected_negative_return) 
                             if expected_negative_return != 0 else float('inf'))
            
            # Probability of large losses/gains at different thresholds
            loss_thresholds = [-1000, -2000, -5000, -10000]  # Absolute loss amounts
            gain_thresholds = [1000, 2000, 5000, 10000]   # Absolute gain amounts
            
            probability_large_loss = {
                f"loss_gt_{abs(thresh)}": np.mean(scenarios_flat <= thresh) 
                for thresh in loss_thresholds
            }
            
            probability_large_gain = {
                f"gain_gt_{thresh}": np.mean(scenarios_flat >= thresh) 
                for thresh in gain_thresholds
            }
            
            # Kelly Criterion calculation (if applicable)
            kelly_criterion = self._calculate_kelly_criterion(scenarios_flat)
            
            probability_metrics = ProbabilityMetrics(
                probability_of_profit=probability_of_profit,
                probability_of_loss=probability_of_loss,
                probability_large_loss=probability_large_loss,
                probability_large_gain=probability_large_gain,
                expected_positive_return=expected_positive_return,
                expected_negative_return=expected_negative_return,
                gain_loss_ratio=gain_loss_ratio,
                kelly_criterion=kelly_criterion,
                calculation_timestamp=datetime.now()
            )
            
            logger.info("Probability metrics calculated: {:.1%} profit probability, {:.2f} gain/loss ratio",
                       probability_of_profit, gain_loss_ratio)
            return probability_metrics
            
        except Exception as e:
            logger.error("Error calculating probability metrics: {}", e)
            raise ValueError(f"Probability metrics calculation failed: {e}")
    
    def generate_comprehensive_risk_report(self,
                                         scenario_set: ScenarioSet,
                                         regime_scenarios: Optional[RegimeConditionalScenarios] = None,
                                         portfolio_value: float = 100000) -> ComprehensiveRiskReport:
        """
        Generate comprehensive risk analysis report from scenario set.
        
        Creates a complete risk assessment combining VaR, Expected Shortfall,
        tail risk metrics, and probability analysis with regime-specific
        analysis if regime scenarios are provided.
        
        Args:
            scenario_set: ScenarioSet from TimeBinScenarioGenerator
            regime_scenarios: Optional regime-conditional scenarios
            portfolio_value: Portfolio value for percentage calculations
            
        Returns:
            ComprehensiveRiskReport with complete risk analysis
        """
        logger.info("Generating comprehensive risk report for {} scenarios",
                   scenario_set.scenarios.size)
        
        try:
            scenarios = scenario_set.scenarios
            method = (RiskMeasureType.MONTE_CARLO if scenario_set.generation_method != ScenarioType.BOOTSTRAP
                     else RiskMeasureType.HISTORICAL)
            
            # Calculate all risk metrics
            var_results = self.calculate_var(scenarios, method=method, portfolio_value=portfolio_value)
            es_results = self.calculate_expected_shortfall(scenarios, method=method)
            tail_metrics = self.calculate_tail_risk_metrics(scenarios)
            probability_metrics = self.calculate_probability_of_profit(scenarios)
            
            # Scenario summary statistics
            scenarios_flat = scenarios.flatten()
            scenario_summary = {
                'total_scenarios': len(scenarios_flat),
                'mean_return': float(np.mean(scenarios_flat)),
                'std_return': float(np.std(scenarios_flat)),
                'skewness': float(stats.skew(scenarios_flat)),
                'kurtosis': float(stats.kurtosis(scenarios_flat)),
                'min_scenario': float(np.min(scenarios_flat)),
                'max_scenario': float(np.max(scenarios_flat)),
                'median_scenario': float(np.median(scenarios_flat))
            }
            
            # Risk decomposition analysis
            risk_decomposition = self._calculate_risk_decomposition(scenarios_flat)
            
            # Regime-specific risk analysis (if available)
            regime_risk_analysis = None
            if regime_scenarios is not None:
                regime_risk_analysis = self._analyze_regime_specific_risk(regime_scenarios)
            
            # Configuration used
            calculation_config = {
                'confidence_levels': self.default_confidence_levels,
                'portfolio_value': portfolio_value,
                'risk_free_rate': self.risk_free_rate,
                'generation_method': scenario_set.generation_method.value,
                'calculation_timestamp': datetime.now().isoformat()
            }
            
            report = ComprehensiveRiskReport(
                var_results=var_results,
                expected_shortfall_results=es_results,
                tail_risk_metrics=tail_metrics,
                probability_metrics=probability_metrics,
                scenario_summary=scenario_summary,
                risk_decomposition=risk_decomposition,
                regime_risk_analysis=regime_risk_analysis,
                calculation_config=calculation_config,
                generation_timestamp=datetime.now()
            )
            
            logger.info("Comprehensive risk report generated successfully")
            return report
            
        except Exception as e:
            logger.error("Error generating comprehensive risk report: {}", e)
            raise ValueError(f"Risk report generation failed: {e}")
    
    def _validate_scenarios_for_risk_calc(self, scenarios: np.ndarray, method: RiskMeasureType):
        """Validate scenario data for risk calculations."""
        if len(scenarios) == 0:
            raise ValueError("No scenarios provided for risk calculation")
        
        if not np.all(np.isfinite(scenarios)):
            logger.warning("Non-finite values found in scenarios, filtering out")
            scenarios = scenarios[np.isfinite(scenarios)]
        
        min_required = (self.min_scenarios_parametric if method == RiskMeasureType.PARAMETRIC 
                       else self.min_scenarios_historical)
        
        if len(scenarios) < min_required:
            raise ValueError(f"Insufficient scenarios ({len(scenarios)}) for {method.value} method "
                           f"(minimum {min_required} required)")
    
    def _calculate_parametric_var(self, scenarios: np.ndarray, confidence_level: float, 
                                portfolio_value: float) -> VaRResult:
        """Calculate parametric VaR assuming normal distribution."""
        mean_return = np.mean(scenarios)
        std_return = np.std(scenarios, ddof=1)
        
        # Calculate VaR using normal distribution
        z_score = stats.norm.ppf(1 - confidence_level)
        var_absolute = mean_return + z_score * std_return
        var_percentage = var_absolute / portfolio_value * 100
        
        return VaRResult(
            confidence_level=confidence_level,
            var_absolute=var_absolute,
            var_percentage=var_percentage,
            calculation_method=RiskMeasureType.PARAMETRIC,
            sample_size=len(scenarios),
            calculation_timestamp=datetime.now(),
            percentile_rank=(1 - confidence_level) * 100
        )
    
    def _calculate_empirical_var(self, scenarios: np.ndarray, confidence_level: float,
                               portfolio_value: float, method: RiskMeasureType) -> VaRResult:
        """Calculate empirical VaR using percentile method."""
        percentile_rank = (1 - confidence_level) * 100
        var_absolute = np.percentile(scenarios, percentile_rank)
        var_percentage = var_absolute / portfolio_value * 100
        worst_case = np.min(scenarios)
        
        return VaRResult(
            confidence_level=confidence_level,
            var_absolute=var_absolute,
            var_percentage=var_percentage,
            calculation_method=method,
            sample_size=len(scenarios),
            calculation_timestamp=datetime.now(),
            percentile_rank=percentile_rank,
            worst_case_scenario=worst_case
        )
    
    def _fit_gev_model(self, losses: np.ndarray, extreme_losses: np.ndarray) -> TailRiskMetrics:
        """Fit Generalized Extreme Value distribution to loss data."""
        try:
            # Fit GEV distribution to block maxima (use annual maxima approach)
            block_maxima = self._extract_block_maxima(losses, block_size=252)  # Annual blocks
            
            if len(block_maxima) < 10:
                logger.warning("Insufficient block maxima ({}) for GEV fitting", len(block_maxima))
                return self._calculate_empirical_tail_metrics(losses)
            
            # Fit GEV distribution
            gev_params = genextreme.fit(block_maxima)
            c, loc, scale = gev_params  # shape, location, scale
            
            # Calculate return levels
            return_level_99_9 = genextreme.ppf(0.999, c, loc, scale)
            return_level_99_95 = genextreme.ppf(0.9995, c, loc, scale)
            return_level_99_99 = genextreme.ppf(0.9999, c, loc, scale)
            
            # Model fit quality (Kolmogorov-Smirnov test)
            ks_stat, ks_p = stats.kstest(block_maxima, lambda x: genextreme.cdf(x, c, loc, scale))
            
            model_parameters = {'shape': c, 'location': loc, 'scale': scale}
            model_fit_quality = {'ks_statistic': ks_stat, 'ks_p_value': ks_p}
            
            return TailRiskMetrics(
                extreme_value_model=TailRiskModel.GENERALIZED_EXTREME_VALUE,
                model_parameters=model_parameters,
                return_level_99_9=return_level_99_9,
                return_level_99_95=return_level_99_95, 
                return_level_99_99=return_level_99_99,
                tail_index=c,  # Shape parameter is tail index for GEV
                model_fit_quality=model_fit_quality,
                calculation_timestamp=datetime.now(),
                worst_historical_loss=np.max(losses),
                tail_concentration=self._calculate_tail_concentration(losses)
            )
            
        except Exception as e:
            logger.warning("GEV model fitting failed ({}), using empirical approach", e)
            return self._calculate_empirical_tail_metrics(losses)
    
    def _fit_pareto_model(self, extreme_losses: np.ndarray, threshold: float) -> TailRiskMetrics:
        """Fit Pareto distribution to exceedances over threshold."""
        try:
            exceedances = extreme_losses - threshold
            
            if len(exceedances) < 10:
                logger.warning("Insufficient exceedances for Pareto fitting")
                return self._calculate_empirical_tail_metrics(-extreme_losses)  # Convert back to returns
            
            # Fit Pareto distribution
            pareto_params = pareto.fit(exceedances, floc=0)  # Fix location at 0
            shape, loc, scale = pareto_params
            
            # Calculate return levels using Pareto model
            return_level_99_9 = threshold + pareto.ppf(0.999, shape, loc, scale)
            return_level_99_95 = threshold + pareto.ppf(0.9995, shape, loc, scale)
            return_level_99_99 = threshold + pareto.ppf(0.9999, shape, loc, scale)
            
            # Model fit quality
            ks_stat, ks_p = stats.kstest(exceedances, lambda x: pareto.cdf(x, shape, loc, scale))
            
            model_parameters = {'shape': shape, 'location': loc, 'scale': scale, 'threshold': threshold}
            model_fit_quality = {'ks_statistic': ks_stat, 'ks_p_value': ks_p}
            
            return TailRiskMetrics(
                extreme_value_model=TailRiskModel.PARETO,
                model_parameters=model_parameters,
                return_level_99_9=return_level_99_9,
                return_level_99_95=return_level_99_95,
                return_level_99_99=return_level_99_99,
                tail_index=1/shape if shape > 0 else None,
                model_fit_quality=model_fit_quality,
                calculation_timestamp=datetime.now(),
                worst_historical_loss=np.max(extreme_losses),
                tail_concentration=self._calculate_tail_concentration(-extreme_losses)
            )
            
        except Exception as e:
            logger.warning("Pareto model fitting failed ({}), using empirical approach", e)
            return self._calculate_empirical_tail_metrics(-extreme_losses)
    
    def _calculate_empirical_tail_metrics(self, losses: np.ndarray) -> TailRiskMetrics:
        """Calculate empirical tail risk metrics without model fitting."""
        return_level_99_9 = np.percentile(losses, 99.9)
        return_level_99_95 = np.percentile(losses, 99.95)
        return_level_99_99 = np.percentile(losses, 99.99)
        
        return TailRiskMetrics(
            extreme_value_model=TailRiskModel.EMPIRICAL,
            model_parameters={},
            return_level_99_9=return_level_99_9,
            return_level_99_95=return_level_99_95,
            return_level_99_99=return_level_99_99,
            tail_index=None,
            model_fit_quality={},
            calculation_timestamp=datetime.now(),
            worst_historical_loss=np.max(losses),
            tail_concentration=self._calculate_tail_concentration(losses)
        )
    
    def _extract_block_maxima(self, data: np.ndarray, block_size: int) -> np.ndarray:
        """Extract block maxima for extreme value analysis."""
        if len(data) < block_size:
            return data
        
        num_blocks = len(data) // block_size
        blocks = data[:num_blocks * block_size].reshape(num_blocks, block_size)
        return np.max(blocks, axis=1)
    
    def _calculate_tail_concentration(self, losses: np.ndarray) -> float:
        """Calculate tail concentration metric."""
        # Percentage of total loss concentrated in top 10% worst scenarios
        top_10_pct_threshold = np.percentile(losses, 90)
        top_10_pct_losses = losses[losses >= top_10_pct_threshold]
        
        total_loss = np.sum(losses[losses > 0])  # Only positive losses
        top_10_pct_total = np.sum(top_10_pct_losses)
        
        return top_10_pct_total / total_loss if total_loss > 0 else 0.0
    
    def _calculate_kelly_criterion(self, scenarios: np.ndarray) -> Optional[float]:
        """Calculate Kelly Criterion for optimal position sizing."""
        try:
            wins = scenarios[scenarios > 0]
            losses = scenarios[scenarios < 0]
            
            if len(wins) == 0 or len(losses) == 0:
                return None
            
            win_rate = len(wins) / len(scenarios)
            avg_win = np.mean(wins)
            avg_loss = abs(np.mean(losses))
            
            if avg_loss == 0:
                return None
            
            # Kelly formula: f = (bp - q) / b
            # where b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
            b = avg_win / avg_loss
            kelly_fraction = (b * win_rate - (1 - win_rate)) / b
            
            # Cap at reasonable limits
            return max(-0.25, min(0.25, kelly_fraction))
            
        except Exception as e:
            logger.warning("Kelly criterion calculation failed: {}", e)
            return None
    
    def _calculate_risk_decomposition(self, scenarios: np.ndarray) -> Dict[str, float]:
        """Calculate risk decomposition metrics."""
        scenarios_sorted = np.sort(scenarios)
        n = len(scenarios_sorted)
        
        return {
            'worst_1_percent': float(np.mean(scenarios_sorted[:max(1, n//100)])),
            'worst_5_percent': float(np.mean(scenarios_sorted[:max(1, n//20)])),
            'worst_10_percent': float(np.mean(scenarios_sorted[:max(1, n//10)])),
            'best_10_percent': float(np.mean(scenarios_sorted[-max(1, n//10):])),
            'middle_80_percent': float(np.mean(scenarios_sorted[n//10:-n//10]) if n > 20 else np.mean(scenarios_sorted)),
            'interquartile_range': float(np.percentile(scenarios_sorted, 75) - np.percentile(scenarios_sorted, 25)),
            'range_ratio': float((np.max(scenarios_sorted) - np.min(scenarios_sorted)) / np.std(scenarios_sorted)) if np.std(scenarios_sorted) > 0 else 0
        }
    
    def _analyze_regime_specific_risk(self, regime_scenarios: RegimeConditionalScenarios) -> Dict[str, Any]:
        """Analyze risk metrics across different volatility regimes."""
        regime_analysis = {}
        
        for regime_name, scenario_set in [
            ('low_volatility', regime_scenarios.low_regime_scenarios),
            ('medium_volatility', regime_scenarios.medium_regime_scenarios),
            ('high_volatility', regime_scenarios.high_regime_scenarios)
        ]:
            if scenario_set.scenarios.size == 0:
                continue
                
            scenarios_flat = scenario_set.scenarios.flatten()
            
            # Basic risk metrics for each regime
            regime_analysis[regime_name] = {
                'var_95': float(np.percentile(scenarios_flat, 5)),
                'var_99': float(np.percentile(scenarios_flat, 1)),
                'expected_shortfall_95': float(np.mean(scenarios_flat[scenarios_flat <= np.percentile(scenarios_flat, 5)])),
                'mean_return': float(np.mean(scenarios_flat)),
                'volatility': float(np.std(scenarios_flat)),
                'skewness': float(stats.skew(scenarios_flat)),
                'probability_of_profit': float(np.mean(scenarios_flat > 0)),
                'scenario_count': len(scenarios_flat)
            }
        
        # Cross-regime analysis
        if len(regime_analysis) > 1:
            regime_analysis['cross_regime_analysis'] = {
                'highest_var_regime': max(regime_analysis.keys(), 
                                        key=lambda x: regime_analysis[x].get('var_99', 0) if x != 'cross_regime_analysis' else -float('inf')),
                'most_profitable_regime': max(regime_analysis.keys(),
                                            key=lambda x: regime_analysis[x].get('mean_return', -float('inf')) if x != 'cross_regime_analysis' else -float('inf')),
                'regime_transition_probabilities': regime_scenarios.regime_transition_probabilities,
                'regime_persistence': regime_scenarios.regime_persistence
            }
        
        return regime_analysis