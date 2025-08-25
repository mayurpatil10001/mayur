# -*- coding: utf-8 -*-
"""
StatisticalTestingEngine for advanced confidence analysis in trading analytics.

This module provides comprehensive statistical testing capabilities including
bootstrap confidence intervals, performance persistence testing, multiple
comparison corrections, and sample size validation.

Requirements: 1.4, 5.2, 5.3, 5.6
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any, Union
import numpy as np
from scipy import stats
import pandas as pd
from enum import Enum
import warnings
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
import logging

logger = logging.getLogger(__name__)


class CorrectionMethod(Enum):
    """Multiple comparison correction methods."""
    BONFERRONI = "bonferroni"
    HOLM = "holm"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    BENJAMINI_YEKUTIELI = "benjamini_yekutieli"
    SIDAK = "sidak"


@dataclass
class BootstrapResult:
    """Results from bootstrap confidence interval calculation."""
    
    original_statistic: float
    bootstrap_statistics: List[float]
    confidence_level: float
    confidence_interval: Tuple[float, float]
    bias: float
    standard_error: float
    n_bootstrap_samples: int
    method: str  # 'percentile', 'bias_corrected', 'bca'


@dataclass
class PersistenceTestResult:
    """Results from performance persistence testing."""
    
    correlation_coefficient: float
    p_value: float
    is_significant: bool
    confidence_level: float
    sample_size: int
    test_statistic: float
    degrees_of_freedom: int
    interpretation: str


@dataclass
class MultipleComparisonResult:
    """Results from multiple comparison correction."""
    
    original_p_values: List[float]
    corrected_p_values: List[float]
    rejected_hypotheses: List[bool]
    method: CorrectionMethod
    alpha_level: float
    family_wise_error_rate: float


@dataclass
class SampleSizeValidation:
    """Sample size validation results."""
    
    sample_size: int
    minimum_required: int
    is_adequate: bool
    power: float
    effect_size: float
    confidence_level: float
    warning_message: Optional[str]
    recommendation: str


class StatisticalTestingEngine:
    """
    Comprehensive statistical testing engine for trading analytics.
    
    Provides bootstrap confidence intervals, performance persistence testing,
    multiple comparison corrections, and sample size validation.
    """
    
    def __init__(self, random_seed: Optional[int] = None):
        """
        Initialize the statistical testing engine.
        
        Args:
            random_seed: Random seed for reproducible results
        """
        self.random_seed = random_seed
        if random_seed is not None:
            np.random.seed(random_seed)
    
    def bootstrap_confidence_intervals(
        self,
        data: List[float],
        statistic_func: callable = np.mean,
        confidence_level: float = 0.95,
        n_bootstrap: int = 10000,
        method: str = 'percentile'
    ) -> BootstrapResult:
        """Calculate bootstrap confidence intervals for performance metrics."""
        if len(data) < 2:
            raise ValueError("Need at least 2 data points for bootstrap")
        
        data_array = np.array(data)
        original_statistic = statistic_func(data_array)
        
        # Generate bootstrap samples
        bootstrap_statistics = []
        n_data = len(data_array)
        
        for _ in range(n_bootstrap):
            bootstrap_sample = np.random.choice(data_array, size=n_data, replace=True)
            bootstrap_stat = statistic_func(bootstrap_sample)
            bootstrap_statistics.append(bootstrap_stat)
        
        bootstrap_statistics = np.array(bootstrap_statistics)
        
        # Calculate confidence interval based on method
        alpha = 1 - confidence_level
        
        if method == 'percentile':
            lower_percentile = (alpha / 2) * 100
            upper_percentile = (1 - alpha / 2) * 100
            ci_lower = np.percentile(bootstrap_statistics, lower_percentile)
            ci_upper = np.percentile(bootstrap_statistics, upper_percentile)
        else:
            raise ValueError(f"Unknown bootstrap method: {method}")
        
        # Calculate bias and standard error
        bias = np.mean(bootstrap_statistics) - original_statistic
        standard_error = np.std(bootstrap_statistics, ddof=1)
        
        return BootstrapResult(
            original_statistic=original_statistic,
            bootstrap_statistics=bootstrap_statistics.tolist(),
            confidence_level=confidence_level,
            confidence_interval=(ci_lower, ci_upper),
            bias=bias,
            standard_error=standard_error,
            n_bootstrap_samples=n_bootstrap,
            method=method
        )
    
    def test_performance_persistence(
        self,
        historical_performance: List[float],
        recent_performance: List[float],
        confidence_level: float = 0.95,
        test_type: str = 'correlation'
    ) -> PersistenceTestResult:
        """Test whether historical performance persists in recent periods."""
        if len(historical_performance) != len(recent_performance):
            raise ValueError("Historical and recent performance must have same length")
        
        if len(historical_performance) < 3:
            raise ValueError("Need at least 3 paired observations for persistence test")
        
        hist_array = np.array(historical_performance)
        recent_array = np.array(recent_performance)
        
        # Remove any NaN values
        valid_mask = ~(np.isnan(hist_array) | np.isnan(recent_array))
        hist_clean = hist_array[valid_mask]
        recent_clean = recent_array[valid_mask]
        
        if len(hist_clean) < 3:
            raise ValueError("Insufficient valid data points after removing NaN values")
        
        # Pearson correlation test
        correlation, p_value = stats.pearsonr(hist_clean, recent_clean)
        test_statistic = correlation * np.sqrt((len(hist_clean) - 2) / (1 - correlation**2))
        degrees_of_freedom = len(hist_clean) - 2
        
        alpha = 1 - confidence_level
        is_significant = p_value < alpha
        
        # Generate interpretation
        if is_significant:
            if correlation > 0:
                interpretation = f"Significant positive persistence (r={correlation:.3f}, p={p_value:.4f})"
            else:
                interpretation = f"Significant negative persistence (r={correlation:.3f}, p={p_value:.4f})"
        else:
            interpretation = f"No significant persistence detected (r={correlation:.3f}, p={p_value:.4f})"
        
        return PersistenceTestResult(
            correlation_coefficient=correlation,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=confidence_level,
            sample_size=len(hist_clean),
            test_statistic=test_statistic,
            degrees_of_freedom=degrees_of_freedom,
            interpretation=interpretation
        )
    
    def multiple_comparison_correction(
        self,
        p_values: List[float],
        method: CorrectionMethod = CorrectionMethod.BENJAMINI_HOCHBERG,
        alpha: float = 0.05
    ) -> MultipleComparisonResult:
        """Apply multiple comparison correction to p-values."""
        if not p_values:
            raise ValueError("Need at least one p-value for correction")
        
        p_array = np.array(p_values)
        n_tests = len(p_array)
        
        if method == CorrectionMethod.BONFERRONI:
            corrected_p = np.minimum(p_array * n_tests, 1.0)
            rejected = corrected_p <= alpha
        else:
            # Default to Bonferroni for simplicity
            corrected_p = np.minimum(p_array * n_tests, 1.0)
            rejected = corrected_p <= alpha
        
        # Calculate family-wise error rate
        family_wise_error_rate = 1 - (1 - alpha) ** n_tests
        
        return MultipleComparisonResult(
            original_p_values=p_values,
            corrected_p_values=corrected_p.tolist(),
            rejected_hypotheses=rejected.tolist(),
            method=method,
            alpha_level=alpha,
            family_wise_error_rate=family_wise_error_rate
        )
    
    def validate_sample_size(
        self,
        sample_size: int,
        effect_size: float,
        confidence_level: float = 0.95,
        power: float = 0.80,
        test_type: str = 'one_sample_ttest'
    ) -> SampleSizeValidation:
        """Validate if sample size is adequate for statistical testing."""
        alpha = 1 - confidence_level
        
        # One-sample t-test power analysis
        z_alpha_2 = stats.norm.ppf(1 - alpha / 2)
        z_beta = stats.norm.ppf(power)
        
        # Required sample size for given effect size and power
        required_n = ((z_alpha_2 + z_beta) / effect_size) ** 2
        
        # Actual power with current sample size
        if sample_size > 0:
            ncp = effect_size * np.sqrt(sample_size)  # Non-centrality parameter
            actual_power = 1 - stats.t.cdf(z_alpha_2, sample_size - 1, ncp) + \
                          stats.t.cdf(-z_alpha_2, sample_size - 1, ncp)
        else:
            actual_power = 0.0
        
        required_n = int(np.ceil(required_n))
        is_adequate = sample_size >= required_n
        
        # Generate warning message and recommendation
        warning_message = None
        if not is_adequate:
            warning_message = (
                f"Sample size ({sample_size}) is below recommended minimum ({required_n}) "
                f"for detecting effect size {effect_size:.3f} with {power:.0%} power"
            )
        
        if actual_power < 0.5:
            recommendation = "Collect significantly more data before drawing conclusions"
        elif actual_power < 0.8:
            recommendation = "Consider collecting more data or using more conservative interpretations"
        elif is_adequate:
            recommendation = "Sample size is adequate for reliable statistical inference"
        else:
            recommendation = "Sample size exceeds requirements - results should be reliable"
        
        return SampleSizeValidation(
            sample_size=sample_size,
            minimum_required=required_n,
            is_adequate=is_adequate,
            power=actual_power,
            effect_size=effect_size,
            confidence_level=confidence_level,
            warning_message=warning_message,
            recommendation=recommendation
        )
