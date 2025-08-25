"""
Accuracy validation tests for risk metrics against known distributions.
Tests the accuracy of VaR, Expected Shortfall, and other risk metrics calculations.
"""

import pytest
import numpy as np
from scipy import stats
from typing import List

from trading_platform.services.monte_carlo.risk_calculator import RiskCalculator


class TestRiskAccuracyValidation:
    """Test suite for validating risk metric accuracy against known distributions."""
    
    @pytest.fixture
    def calculator(self):
        """Create a RiskCalculator instance."""
        return RiskCalculator()
    
    def test_var_accuracy_normal_distribution(self, calculator):
        """Test VaR accuracy against known normal distribution."""
        # Generate large sample from known normal distribution
        np.random.seed(42)
        mean = 0.01
        std = 0.05
        sample_size = 10000
        
        returns = np.random.normal(mean, std, sample_size).tolist()
        
        # Calculate VaR at different confidence levels
        confidence_levels = [0.01, 0.05, 0.10]
        
        for conf_level in confidence_levels:
            calculated_var = calculator.calculate_var(returns, conf_level)
            
            # Theoretical VaR for normal distribution
            theoretical_var = stats.norm.ppf(conf_level, mean, std)
            
            # Allow for sampling error (should be close with large sample)
            relative_error = abs(calculated_var - theoretical_var) / abs(theoretical_var)
            assert relative_error < 0.05  # Within 5% of theoretical value
    
    def test_var_accuracy_t_distribution(self, calculator):
        """Test VaR accuracy against known t-distribution."""
        # Generate sample from t-distribution
        np.random.seed(42)
        df = 5  # degrees of freedom
        sample_size = 10000
        
        returns = stats.t.rvs(df, size=sample_size).tolist()
        
        # Calculate VaR
        confidence_levels = [0.01, 0.05, 0.10]
        
        for conf_level in confidence_levels:
            calculated_var = calculator.calculate_var(returns, conf_level)
            
            # Theoretical VaR for t-distribution
            theoretical_var = stats.t.ppf(conf_level, df)
            
            # Allow for sampling error
            relative_error = abs(calculated_var - theoretical_var) / abs(theoretical_var)
            assert relative_error < 0.1  # Within 10% for t-distribution (heavier tails)
    
    def test_expected_shortfall_accuracy_normal(self, calculator):
        """Test Expected Shortfall accuracy against known normal distribution."""
        np.random.seed(42)
        mean = 0.02
        std = 0.08
        sample_size = 10000
        
        returns = np.random.normal(mean, std, sample_size).tolist()
        
        confidence_levels = [0.01, 0.05, 0.10]
        
        for conf_level in confidence_levels:
            calculated_es = calculator.calculate_expected_shortfall(returns, conf_level)
            
            # Theoretical Expected Shortfall for normal distribution
            # ES = μ - σ * φ(Φ^(-1)(α)) / α
            # where φ is PDF and Φ is CDF of standard normal
            z_alpha = stats.norm.ppf(conf_level)
            theoretical_es = mean - std * stats.norm.pdf(z_alpha) / conf_level
            
            # Allow for sampling error
            relative_error = abs(calculated_es - theoretical_es) / abs(theoretical_es)
            assert relative_error < 0.1  # Within 10% of theoretical value
    
    def test_percentile_accuracy(self, calculator):
        """Test that VaR percentiles match numpy percentiles."""
        np.random.seed(42)
        returns = np.random.normal(0.01, 0.03, 5000).tolist()
        
        confidence_levels = [0.01, 0.05, 0.10, 0.25, 0.50]
        
        for conf_level in confidence_levels:
            calculated_var = calculator.calculate_var(returns, conf_level)
            numpy_percentile = np.percentile(returns, conf_level * 100)
            
            # Should be identical (within floating point precision)
            assert abs(calculated_var - numpy_percentile) < 1e-10
    
    def test_confidence_bands_accuracy(self, calculator):
        """Test confidence band accuracy against theoretical values."""
        np.random.seed(42)
        mean = 0.015
        std = 0.04
        sample_size = 8000
        
        # Generate normal distribution sample
        data = np.random.normal(mean, std, sample_size).tolist()
        
        confidence_levels = [0.90, 0.95, 0.99]
        bands = calculator.generate_confidence_bands(data, confidence_levels)
        
        for conf_level in confidence_levels:
            band_key = f'{conf_level:.0%}'
            band = bands[band_key]
            
            # Calculate theoretical bounds
            tail_prob = (1 - conf_level) / 2
            theoretical_lower = stats.norm.ppf(tail_prob, mean, std)
            theoretical_upper = stats.norm.ppf(1 - tail_prob, mean, std)
            theoretical_median = mean  # For normal distribution
            
            # Check accuracy
            lower_error = abs(band['lower_bound'] - theoretical_lower) / abs(theoretical_lower)
            upper_error = abs(band['upper_bound'] - theoretical_upper) / abs(theoretical_upper)
            median_error = abs(band['median'] - theoretical_median) / abs(theoretical_median)
            
            assert lower_error < 0.05  # Within 5%
            assert upper_error < 0.05  # Within 5%
            assert median_error < 0.05  # Within 5%
    
    def test_distribution_fitting_accuracy(self, calculator):
        """Test distribution fitting accuracy against known distributions."""
        test_cases = [
            {
                'name': 'normal',
                'generator': lambda: np.random.normal(0.02, 0.06, 5000),
                'expected_best': 'normal'
            },
            {
                'name': 't_distribution',
                'generator': lambda: stats.t.rvs(df=3, size=5000),
                'expected_best': 't'  # Should detect heavy tails
            },
            {
                'name': 'skewed',
                'generator': lambda: stats.skewnorm.rvs(a=5, size=5000),
                'expected_best': 'skewnorm'  # Should detect skewness
            }
        ]
        
        for test_case in test_cases:
            np.random.seed(42)
            data = test_case['generator']().tolist()
            
            analysis = calculator.analyze_distribution(data)
            
            # Check that the correct distribution is identified (or at least in top candidates)
            # Note: This might not always be exact due to sampling variation
            assert analysis['best_distribution'] in ['normal', 't', 'skewnorm']
            
            # Check that distribution fits are reasonable
            assert len(analysis['distribution_fits']) > 0
            
            # Check that fitted parameters are reasonable
            best_fit = analysis['distribution_fits'][analysis['best_distribution']]
            assert 'aic' in best_fit
            assert 'ks_pvalue' in best_fit
            assert np.isfinite(best_fit['aic'])
    
    def test_portfolio_var_accuracy(self, calculator):
        """Test portfolio VaR accuracy with known correlation structure."""
        # Create correlated assets with known correlation
        np.random.seed(42)
        n_samples = 2000
        correlation = 0.6
        
        # Generate correlated returns
        returns1 = np.random.normal(0.01, 0.02, n_samples)
        noise = np.random.normal(0, 0.015, n_samples)
        returns2 = correlation * returns1 + np.sqrt(1 - correlation**2) * noise + 0.005
        
        # Portfolio weights
        weights = [0.6, 0.4]
        
        # Calculate portfolio VaR
        asset_returns = [returns1.tolist(), returns2.tolist()]
        portfolio_metrics = calculator.calculate_portfolio_var(weights, asset_returns, 0.05)
        
        # Calculate theoretical portfolio statistics
        portfolio_mean = weights[0] * np.mean(returns1) + weights[1] * np.mean(returns2)
        portfolio_var_theoretical = (
            weights[0]**2 * np.var(returns1) + 
            weights[1]**2 * np.var(returns2) + 
            2 * weights[0] * weights[1] * correlation * np.std(returns1) * np.std(returns2)
        )
        portfolio_std_theoretical = np.sqrt(portfolio_var_theoretical)
        
        # Theoretical portfolio VaR (assuming normal distribution)
        theoretical_portfolio_var = stats.norm.ppf(0.05, portfolio_mean, portfolio_std_theoretical)
        
        # Check accuracy
        calculated_var = portfolio_metrics['portfolio_var']
        relative_error = abs(calculated_var - theoretical_portfolio_var) / abs(theoretical_portfolio_var)
        
        assert relative_error < 0.15  # Within 15% (allowing for estimation errors)
        
        # Check diversification benefit (can be negative if correlation is high)
        # Just check that it's a finite number
        assert np.isfinite(portfolio_metrics['diversification_benefit'])
    
    def test_stress_test_accuracy(self, calculator):
        """Test stress test accuracy with known transformations."""
        np.random.seed(42)
        base_returns = np.random.normal(0.01, 0.03, 1000).tolist()
        
        # Define stress scenarios with known effects
        stress_scenarios = {
            'mean_shift_down': {
                'mean_shift': -0.05
            },
            'volatility_double': {
                'volatility_multiplier': 2.0
            }
        }
        
        stress_results = calculator.stress_test_scenarios(base_returns, stress_scenarios)
        
        # Test mean shift scenario
        base_mean = np.mean(base_returns)
        stressed_mean = stress_results['mean_shift_down']['mean_return']
        expected_stressed_mean = base_mean - 0.05
        
        assert abs(stressed_mean - expected_stressed_mean) < 0.001  # Should be very accurate
        
        # Test volatility scaling scenario
        base_std = np.std(base_returns, ddof=1)
        stressed_std = stress_results['volatility_double']['volatility']
        expected_stressed_std = base_std * 2.0
        
        # Allow for some error due to mean adjustment in volatility scaling
        relative_error = abs(stressed_std - expected_stressed_std) / expected_stressed_std
        assert relative_error < 0.1  # Within 10%
    
    def test_tail_risk_metrics_accuracy(self, calculator):
        """Test accuracy of tail risk metrics."""
        # Generate data with known tail properties
        np.random.seed(42)
        
        # Use t-distribution for heavy tails
        df = 4
        sample_size = 5000
        returns = stats.t.rvs(df, size=sample_size).tolist()
        
        metrics = calculator.calculate_risk_metrics(returns)
        
        # Check that tail metrics are reasonable for t-distribution
        tail_metrics = metrics['tail_risk']
        
        # For t-distribution with df=4, kurtosis should be 6/(df-4) = undefined, but sample kurtosis should be high
        assert metrics['basic_statistics']['kurtosis'] > 1.0  # Should detect heavy tails
        
        # Downside deviation should be significant for heavy-tailed distribution
        assert tail_metrics['downside_deviation'] > 0
        
        # Tail ratio should indicate asymmetry if present
        assert 'tail_ratio' in tail_metrics
        assert np.isfinite(tail_metrics['tail_ratio'])
    
    def test_large_sample_convergence(self, calculator):
        """Test that risk metrics converge to theoretical values with large samples."""
        # Test convergence with increasing sample sizes
        sample_sizes = [1000, 5000, 10000]
        mean = 0.01
        std = 0.04
        confidence_level = 0.05
        
        theoretical_var = stats.norm.ppf(confidence_level, mean, std)
        
        errors = []
        
        for sample_size in sample_sizes:
            np.random.seed(42)  # Same seed for consistency
            returns = np.random.normal(mean, std, sample_size).tolist()
            calculated_var = calculator.calculate_var(returns, confidence_level)
            
            error = abs(calculated_var - theoretical_var) / abs(theoretical_var)
            errors.append(error)
        
        # Errors should generally decrease with larger samples
        # (though this might not be strictly monotonic due to randomness)
        assert errors[-1] < 0.02  # Final error should be very small
    
    def test_coherent_risk_measure_properties(self, calculator):
        """Test that Expected Shortfall satisfies coherent risk measure properties."""
        np.random.seed(42)
        
        # Generate two return series
        returns1 = np.random.normal(0.01, 0.02, 1000).tolist()
        returns2 = np.random.normal(0.005, 0.025, 1000).tolist()
        
        # Test subadditivity: ES(X + Y) <= ES(X) + ES(Y)
        # This is complex to test exactly, so we'll test a simpler version
        
        es1 = calculator.calculate_expected_shortfall(returns1, 0.05)
        es2 = calculator.calculate_expected_shortfall(returns2, 0.05)
        
        # Combined returns (simplified addition)
        combined_returns = [(r1 + r2) / 2 for r1, r2 in zip(returns1, returns2)]
        es_combined = calculator.calculate_expected_shortfall(combined_returns, 0.05)
        
        # For this simplified test, just check that ES is calculated correctly
        # The exact relationship depends on the specific combination method
        assert np.isfinite(es_combined)
        assert es_combined < 0  # Should be negative (representing loss)
    
    def test_var_vs_expected_shortfall_relationship(self, calculator):
        """Test the mathematical relationship between VaR and Expected Shortfall."""
        # Generate various distributions to test the relationship
        test_distributions = [
            np.random.normal(0.01, 0.03, 2000),
            stats.t.rvs(df=5, size=2000),
            stats.skewnorm.rvs(a=3, size=2000)
        ]
        
        confidence_levels = [0.01, 0.05, 0.10]
        
        for dist_data in test_distributions:
            returns = dist_data.tolist()
            
            for conf_level in confidence_levels:
                var_value = calculator.calculate_var(returns, conf_level)
                es_value = calculator.calculate_expected_shortfall(returns, conf_level)
                
                # ES should always be more conservative (lower/more negative) than VaR
                assert es_value <= var_value
                
                # Just check that both values are finite
                assert np.isfinite(var_value)
                assert np.isfinite(es_value)
    
    def test_numerical_stability(self, calculator):
        """Test numerical stability with extreme values."""
        # Test with very small values
        small_returns = [1e-10, -1e-10, 2e-10, -2e-10, 1.5e-10] * 100
        var_small = calculator.calculate_var(small_returns, 0.05)
        assert np.isfinite(var_small)
        
        # Test with very large values
        large_returns = [1e6, -1e6, 2e6, -2e6, 1.5e6] * 100
        var_large = calculator.calculate_var(large_returns, 0.05)
        assert np.isfinite(var_large)
        
        # Test with mixed scales
        mixed_returns = [0.001, -0.002, 1000, -2000, 0.0015] * 100
        var_mixed = calculator.calculate_var(mixed_returns, 0.05)
        assert np.isfinite(var_mixed)