"""
Tests for StatisticalTestingEngine - comprehensive statistical testing capabilities.

Tests bootstrap confidence intervals, performance persistence testing,
multiple comparison corrections, and sample size validation against
known distributions and analytical solutions.

Requirements: 1.4, 5.2, 5.3, 5.6
"""

import pytest
import numpy as np
from scipy import stats
from typing import List, Tuple
import warnings

from trading_platform.services.statistical_testing_engine import (
    StatisticalTestingEngine,
    CorrectionMethod,
    BootstrapResult,
    PersistenceTestResult,
    MultipleComparisonResult,
    SampleSizeValidation
)


class TestStatisticalTestingEngine:
    """Test suite for StatisticalTestingEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = StatisticalTestingEngine(random_seed=42)
        np.random.seed(42)
        self.normal_data = np.random.normal(loc=0.5, scale=1.0, size=100).tolist()
        self.small_sample_data = np.random.normal(loc=1.0, scale=0.5, size=10).tolist()
    
    def test_bootstrap_percentile_method(self):
        """Test percentile bootstrap method with normal data."""
        result = self.engine.bootstrap_confidence_intervals(
            self.normal_data, 
            confidence_level=0.95,
            n_bootstrap=1000,
            method='percentile'
        )
        
        assert isinstance(result, BootstrapResult)
        assert result.confidence_level == 0.95
        assert result.method == 'percentile'
        assert len(result.bootstrap_statistics) == 1000
        
        # Check that confidence interval contains true mean (approximately)
        true_mean = np.mean(self.normal_data)
        ci_lower, ci_upper = result.confidence_interval
        assert ci_lower <= true_mean <= ci_upper
        
        # Check that confidence interval is reasonable width
        ci_width = ci_upper - ci_lower
        assert 0.1 < ci_width < 1.0  # Should be reasonable for this data
    
    def test_bootstrap_insufficient_data(self):
        """Test bootstrap with insufficient data."""
        with pytest.raises(ValueError, match="Need at least 2 data points"):
            self.engine.bootstrap_confidence_intervals([1.0])
    
    def test_bootstrap_invalid_method(self):
        """Test bootstrap with invalid method."""
        with pytest.raises(ValueError, match="Unknown bootstrap method"):
            self.engine.bootstrap_confidence_intervals(self.normal_data, method='invalid')
    
    def test_positive_correlation_persistence(self):
        """Test persistence with positively correlated data."""
        # Create positively correlated data
        np.random.seed(42)
        base_performance = np.random.normal(0, 1, 20)
        noise = np.random.normal(0, 0.5, 20)
        
        historical = base_performance.tolist()
        recent = (base_performance + noise).tolist()
        
        result = self.engine.test_performance_persistence(
            historical, recent, confidence_level=0.95
        )
        
        assert isinstance(result, PersistenceTestResult)
        assert result.correlation_coefficient > 0
        assert result.sample_size == 20
        assert result.degrees_of_freedom == 18
        assert "positive" in result.interpretation.lower()
    
    def test_persistence_insufficient_data(self):
        """Test persistence with insufficient data."""
        with pytest.raises(ValueError, match="Need at least 3 paired observations"):
            self.engine.test_performance_persistence([1, 2], [1, 2])
    
    def test_persistence_mismatched_lengths(self):
        """Test persistence with mismatched data lengths."""
        with pytest.raises(ValueError, match="must have same length"):
            self.engine.test_performance_persistence([1, 2, 3], [1, 2])
    
    def test_bonferroni_correction(self):
        """Test Bonferroni correction method."""
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]
        
        result = self.engine.multiple_comparison_correction(
            p_values, method=CorrectionMethod.BONFERRONI, alpha=0.05
        )
        
        assert isinstance(result, MultipleComparisonResult)
        assert result.method == CorrectionMethod.BONFERRONI
        assert len(result.corrected_p_values) == 5
        
        # Bonferroni: corrected p = original p * n_tests
        expected_corrected = [p * 5 for p in p_values]
        for i, expected in enumerate(expected_corrected):
            assert abs(result.corrected_p_values[i] - min(expected, 1.0)) < 1e-10
        
        # Only the first p-value should be significant after correction
        assert result.rejected_hypotheses[0] == True  # 0.01 * 5 = 0.05
        assert result.rejected_hypotheses[1] == False  # 0.02 * 5 = 0.10 > 0.05
    
    def test_multiple_comparison_empty_input(self):
        """Test multiple comparison with empty input."""
        with pytest.raises(ValueError, match="Need at least one p-value"):
            self.engine.multiple_comparison_correction([])
    
    def test_adequate_sample_size_one_sample_ttest(self):
        """Test sample size validation for one-sample t-test with adequate sample."""
        # Large effect size with adequate sample
        result = self.engine.validate_sample_size(
            sample_size=50,
            effect_size=0.8,  # Large effect size
            confidence_level=0.95,
            power=0.80,
            test_type='one_sample_ttest'
        )
        
        assert isinstance(result, SampleSizeValidation)
        assert result.sample_size == 50
        assert result.effect_size == 0.8
        assert result.confidence_level == 0.95
        assert result.is_adequate == True
        assert result.power >= 0.80
        assert result.warning_message is None
        assert "adequate" in result.recommendation.lower()
    
    def test_inadequate_sample_size_one_sample_ttest(self):
        """Test sample size validation with inadequate sample."""
        # Small effect size with small sample
        result = self.engine.validate_sample_size(
            sample_size=10,
            effect_size=0.2,  # Small effect size
            confidence_level=0.95,
            power=0.80,
            test_type='one_sample_ttest'
        )
        
        assert result.is_adequate == False
        assert result.power < 0.80
        assert result.warning_message is not None
        assert "below recommended minimum" in result.warning_message
        assert "more data" in result.recommendation.lower()
    
    def test_sample_size_zero_sample(self):
        """Test sample size validation with zero sample size."""
        result = self.engine.validate_sample_size(
            sample_size=0,
            effect_size=0.5,
            test_type='one_sample_ttest'
        )
        
        assert result.is_adequate == False
        assert result.power == 0.0
        assert "significantly more data" in result.recommendation.lower()


class TestStatisticalTestingEngineIntegration:
    """Integration tests for StatisticalTestingEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = StatisticalTestingEngine(random_seed=42)
    
    def test_engine_with_trading_data_simulation(self):
        """Test engine with simulated trading P&L data."""
        # Simulate trading P&L data with some positive bias
        np.random.seed(42)
        base_returns = np.random.normal(loc=0.02, scale=0.15, size=100)  # 2% mean return, 15% volatility
        pnl_data = (base_returns * 1000).tolist()  # Convert to dollar P&L
        
        # Test bootstrap confidence intervals
        bootstrap_result = self.engine.bootstrap_confidence_intervals(
            pnl_data, confidence_level=0.95, n_bootstrap=1000
        )
        
        assert bootstrap_result.original_statistic > 0  # Should be positive on average
        assert bootstrap_result.confidence_interval[0] < bootstrap_result.confidence_interval[1]
    
    def test_multiple_time_bin_comparison_simulation(self):
        """Test multiple comparison correction for time-bin analysis."""
        # Simulate testing 20 different time bins
        np.random.seed(42)
        p_values = []
        
        for i in range(20):
            # Most time bins have no effect (null hypothesis true)
            if i < 17:
                data = np.random.normal(0, 1, 30)  # No effect
            else:
                data = np.random.normal(0.5, 1, 30)  # Some effect
            
            t_stat, p_val = stats.ttest_1samp(data, 0)
            p_values.append(p_val)
        
        # Apply multiple comparison correction
        correction_result = self.engine.multiple_comparison_correction(
            p_values, method=CorrectionMethod.BONFERRONI, alpha=0.05
        )
        
        # Should control false discovery rate
        assert len(correction_result.corrected_p_values) == 20
        assert len(correction_result.rejected_hypotheses) == 20
        
        # Should reject fewer hypotheses than uncorrected
        uncorrected_rejections = sum(p < 0.05 for p in p_values)
        corrected_rejections = sum(correction_result.rejected_hypotheses)
        assert corrected_rejections <= uncorrected_rejections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])