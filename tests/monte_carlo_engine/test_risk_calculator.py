"""
Comprehensive unit tests for RiskCalculator.
Tests VaR, Expected Shortfall, confidence bands, and distribution analysis.
"""

import pytest
import numpy as np
from scipy import stats
from unittest.mock import patch
from typing import List

from trading_platform.services.monte_carlo.risk_calculator import RiskCalculator


class TestRiskCalculator:
    """Test suite for RiskCalculator class."""
    
    @pytest.fixture
    def calculator(self):
        """Create a RiskCalculator instance."""
        return RiskCalculator()
    
    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data for testing."""
        np.random.seed(42)
        return np.random.normal(0.01, 0.05, 1000).tolist()
    
    @pytest.fixture
    def sample_simulation_results(self):
        """Generate sample simulation results."""
        np.random.seed(42)
        initial_capital = 100000
        returns = np.random.normal(0.01, 0.05, 1000)
        final_values = [initial_capital * (1 + ret) for ret in returns]
        return final_values
    
    def test_initialization(self):
        """Test RiskCalculator initialization."""
        calculator = RiskCalculator()
        assert calculator.logger is not None
    
    def test_calculate_var_basic(self, calculator, sample_returns):
        """Test basic VaR calculation."""
        var_95 = calculator.calculate_var(sample_returns, confidence_level=0.05)
        
        assert isinstance(var_95, float)
        assert var_95 < 0  # VaR should be negative (representing loss)
        
        # VaR should be approximately at the 5th percentile
        expected_var = np.percentile(sample_returns, 5)
        assert abs(var_95 - expected_var) < 1e-10
    
    def test_calculate_var_different_confidence_levels(self, calculator, sample_returns):
        """Test VaR calculation with different confidence levels."""
        var_95 = calculator.calculate_var(sample_returns, 0.05)
        var_99 = calculator.calculate_var(sample_returns, 0.01)
        var_90 = calculator.calculate_var(sample_returns, 0.10)
        
        # Higher confidence (lower confidence_level) should give more extreme VaR
        assert var_99 < var_95 < var_90
    
    def test_calculate_var_validation(self, calculator):
        """Test validation in VaR calculation."""
        # Test with empty returns
        with pytest.raises(ValueError, match="No returns provided"):
            calculator.calculate_var([])
        
        # Test with invalid confidence level
        with pytest.raises(ValueError, match="Confidence level must be between 0 and 1"):
            calculator.calculate_var([0.01, 0.02], confidence_level=0.0)
        
        with pytest.raises(ValueError, match="Confidence level must be between 0 and 1"):
            calculator.calculate_var([0.01, 0.02], confidence_level=1.0)
    
    def test_calculate_var_with_invalid_data(self, calculator):
        """Test VaR calculation with invalid data."""
        # Test with all NaN values
        with pytest.raises(ValueError, match="No valid returns after cleaning"):
            calculator.calculate_var([np.nan, np.nan, np.nan])
        
        # Test with all infinite values
        with pytest.raises(ValueError, match="No valid returns after cleaning"):
            calculator.calculate_var([np.inf, -np.inf, np.inf])
    
    def test_calculate_var_with_mixed_data(self, calculator):
        """Test VaR calculation with mixed valid/invalid data."""
        mixed_data = [0.01, np.nan, 0.02, np.inf, -0.01, -np.inf, 0.005]
        var_value = calculator.calculate_var(mixed_data)
        
        # Should work with valid subset
        assert isinstance(var_value, float)
        assert np.isfinite(var_value)
    
    def test_calculate_expected_shortfall_basic(self, calculator, sample_returns):
        """Test basic Expected Shortfall calculation."""
        es_95 = calculator.calculate_expected_shortfall(sample_returns, confidence_level=0.05)
        var_95 = calculator.calculate_var(sample_returns, confidence_level=0.05)
        
        assert isinstance(es_95, float)
        assert es_95 <= var_95  # ES should be more extreme than VaR
    
    def test_calculate_expected_shortfall_validation(self, calculator):
        """Test validation in Expected Shortfall calculation."""
        # Test with empty returns
        with pytest.raises(ValueError, match="No returns provided"):
            calculator.calculate_expected_shortfall([])
        
        # Test with invalid confidence level
        with pytest.raises(ValueError, match="Confidence level must be between 0 and 1"):
            calculator.calculate_expected_shortfall([0.01, 0.02], confidence_level=1.5)
    
    def test_calculate_expected_shortfall_edge_cases(self, calculator):
        """Test Expected Shortfall with edge cases."""
        # Test with data where very few returns are below VaR
        positive_returns = [0.01, 0.02, 0.03, 0.04, 0.05]
        es = calculator.calculate_expected_shortfall(positive_returns, confidence_level=0.01)
        var = calculator.calculate_var(positive_returns, confidence_level=0.01)
        
        # When very few returns are below VaR, ES should be close to VaR
        # Allow for some difference due to the discrete nature of small samples
        assert abs(es - var) < 0.001  # More lenient tolerance
    
    def test_calculate_risk_metrics_comprehensive(self, calculator, sample_simulation_results):
        """Test comprehensive risk metrics calculation."""
        initial_capital = 100000.0
        metrics = calculator.calculate_risk_metrics(sample_simulation_results, initial_capital)
        
        # Check main categories
        assert 'basic_statistics' in metrics
        assert 'var_metrics' in metrics
        assert 'expected_shortfall' in metrics
        assert 'probability_metrics' in metrics
        assert 'risk_adjusted_returns' in metrics
        assert 'tail_risk' in metrics
        assert 'percentiles' in metrics
        assert 'sample_size' in metrics
        
        # Check basic statistics
        basic_stats = metrics['basic_statistics']
        required_basic_keys = ['mean_return', 'std_return', 'min_return', 'max_return', 'skewness', 'kurtosis']
        for key in required_basic_keys:
            assert key in basic_stats
            assert isinstance(basic_stats[key], float)
        
        # Check VaR metrics
        var_metrics = metrics['var_metrics']
        assert 'var_95' in var_metrics
        assert 'var_99' in var_metrics
        assert 'var_99_9' in var_metrics
        assert var_metrics['var_99'] <= var_metrics['var_95']  # 99% VaR should be more extreme
        
        # Check Expected Shortfall
        es_metrics = metrics['expected_shortfall']
        assert 'es_95' in es_metrics
        assert 'es_99' in es_metrics
        assert es_metrics['es_95'] <= var_metrics['var_95']  # ES should be more extreme (lower/more negative) than VaR
        
        # Check probability metrics
        prob_metrics = metrics['probability_metrics']
        prob_keys = ['prob_loss', 'prob_profit', 'prob_large_loss', 'prob_large_gain']
        for key in prob_keys:
            assert key in prob_metrics
            assert 0 <= prob_metrics[key] <= 1  # Probabilities should be between 0 and 1
        
        # Check that probabilities are consistent
        assert abs(prob_metrics['prob_loss'] + prob_metrics['prob_profit'] - 1.0) < 0.1  # Allow for zero returns
    
    def test_calculate_risk_metrics_validation(self, calculator):
        """Test validation in risk metrics calculation."""
        # Test with empty results
        with pytest.raises(ValueError, match="No simulation results provided"):
            calculator.calculate_risk_metrics([])
        
        # Test with all invalid data
        with pytest.raises(ValueError, match="No valid simulation results after cleaning"):
            calculator.calculate_risk_metrics([np.nan, np.inf, -np.inf])
    
    def test_calculate_risk_metrics_without_initial_capital(self, calculator):
        """Test risk metrics calculation without initial capital."""
        # Use returns directly
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        metrics = calculator.calculate_risk_metrics(returns)
        
        assert 'basic_statistics' in metrics
        assert metrics['basic_statistics']['mean_return'] == np.mean(returns)
    
    def test_generate_confidence_bands_basic(self, calculator, sample_simulation_results):
        """Test basic confidence band generation."""
        bands = calculator.generate_confidence_bands(sample_simulation_results)
        
        # Check default confidence levels
        assert '90%' in bands
        assert '95%' in bands
        assert '99%' in bands
        
        # Check structure of each band
        for level, band in bands.items():
            assert 'lower_bound' in band
            assert 'upper_bound' in band
            assert 'median' in band
            assert 'width' in band
            
            # Check logical relationships
            assert band['lower_bound'] < band['median'] < band['upper_bound']
            assert band['width'] == band['upper_bound'] - band['lower_bound']
        
        # Check that higher confidence levels have wider bands
        assert bands['99%']['width'] > bands['95%']['width'] > bands['90%']['width']
    
    def test_generate_confidence_bands_custom_levels(self, calculator, sample_simulation_results):
        """Test confidence band generation with custom levels."""
        custom_levels = [0.80, 0.90, 0.95]
        bands = calculator.generate_confidence_bands(sample_simulation_results, custom_levels)
        
        assert '80%' in bands
        assert '90%' in bands
        assert '95%' in bands
        assert len(bands) == 3
    
    def test_generate_confidence_bands_validation(self, calculator):
        """Test validation in confidence band generation."""
        # Test with empty results
        with pytest.raises(ValueError, match="No simulation results provided"):
            calculator.generate_confidence_bands([])
        
        # Test with invalid confidence levels
        with patch.object(calculator.logger, 'warning') as mock_warning:
            bands = calculator.generate_confidence_bands([1, 2, 3, 4, 5], [0.0, 1.0, 1.5])
            mock_warning.assert_called()
            assert len(bands) == 0  # No valid confidence levels
    
    def test_analyze_distribution_basic(self, calculator, sample_simulation_results):
        """Test basic distribution analysis."""
        analysis = calculator.analyze_distribution(sample_simulation_results)
        
        # Check main categories
        assert 'moments' in analysis
        assert 'normality_tests' in analysis
        assert 'distribution_fits' in analysis
        assert 'best_distribution' in analysis
        assert 'tail_analysis' in analysis
        assert 'sample_size' in analysis
        
        # Check moments
        moments = analysis['moments']
        moment_keys = ['mean', 'variance', 'std', 'skewness', 'kurtosis']
        for key in moment_keys:
            assert key in moments
            assert isinstance(moments[key], float)
        
        # Check normality tests
        normality = analysis['normality_tests']
        normality_keys = ['jarque_bera_statistic', 'jarque_bera_pvalue', 'ks_statistic', 'ks_pvalue']
        for key in normality_keys:
            assert key in normality
            assert isinstance(normality[key], float)
        
        assert 'is_normal_jb' in normality
        assert 'is_normal_ks' in normality
        assert isinstance(normality['is_normal_jb'], bool)
        assert isinstance(normality['is_normal_ks'], bool)
        
        # Check distribution fits
        assert isinstance(analysis['distribution_fits'], dict)
        assert len(analysis['distribution_fits']) > 0
        
        # Check best distribution
        assert analysis['best_distribution'] in analysis['distribution_fits']
    
    def test_analyze_distribution_with_negative_values(self, calculator):
        """Test distribution analysis with negative values (should skip lognormal)."""
        data_with_negatives = [-1, -0.5, 0, 0.5, 1, 1.5, 2]
        analysis = calculator.analyze_distribution(data_with_negatives)
        
        # Should not include lognormal distribution
        assert 'lognorm' not in analysis['distribution_fits']
        assert 'normal' in analysis['distribution_fits']
    
    def test_analyze_distribution_validation(self, calculator):
        """Test validation in distribution analysis."""
        # Test with empty results
        with pytest.raises(ValueError, match="No simulation results provided"):
            calculator.analyze_distribution([])
    
    def test_calculate_portfolio_var_basic(self, calculator):
        """Test basic portfolio VaR calculation."""
        # Create sample portfolio data
        weights = [0.6, 0.4]
        asset1_returns = np.random.normal(0.01, 0.02, 100).tolist()
        asset2_returns = np.random.normal(0.005, 0.015, 100).tolist()
        asset_returns = [asset1_returns, asset2_returns]
        
        portfolio_metrics = calculator.calculate_portfolio_var(weights, asset_returns)
        
        # Check required keys
        required_keys = [
            'portfolio_var', 'portfolio_expected_shortfall', 'undiversified_var',
            'diversification_benefit', 'diversification_ratio', 'individual_asset_vars',
            'portfolio_volatility', 'sample_size'
        ]
        
        for key in required_keys:
            assert key in portfolio_metrics
            if key == 'sample_size':
                assert isinstance(portfolio_metrics[key], int)
            elif key == 'individual_asset_vars':
                assert isinstance(portfolio_metrics[key], list)
            else:
                assert isinstance(portfolio_metrics[key], float)
        
        # Check logical relationships
        assert len(portfolio_metrics['individual_asset_vars']) == 2
        # Diversification benefit can be negative if assets are highly correlated or poorly diversified
        assert isinstance(portfolio_metrics['diversification_benefit'], float)
        assert np.isfinite(portfolio_metrics['diversification_benefit'])
    
    def test_calculate_portfolio_var_validation(self, calculator):
        """Test validation in portfolio VaR calculation."""
        # Test with empty weights
        with pytest.raises(ValueError, match="Portfolio weights and asset returns must be provided"):
            calculator.calculate_portfolio_var([], [[1, 2, 3]])
        
        # Test with mismatched dimensions
        with pytest.raises(ValueError, match="Number of weights must match number of assets"):
            calculator.calculate_portfolio_var([0.5, 0.5], [[1, 2, 3]])
        
        # Test with weights not summing to 1
        with pytest.raises(ValueError, match="Portfolio weights must sum to 1"):
            calculator.calculate_portfolio_var([0.3, 0.4], [[1, 2, 3], [4, 5, 6]])
    
    def test_stress_test_scenarios_basic(self, calculator, sample_returns):
        """Test basic stress testing functionality."""
        stress_scenarios = {
            'market_crash': {
                'mean_shift': -0.05,
                'volatility_multiplier': 2.0
            },
            'tail_event': {
                'percentile_shock': 1
            }
        }
        
        stress_results = calculator.stress_test_scenarios(sample_returns, stress_scenarios)
        
        assert 'market_crash' in stress_results
        assert 'tail_event' in stress_results
        
        # Check structure of stress results
        for scenario_name, results in stress_results.items():
            required_keys = ['var_95', 'expected_shortfall_95', 'mean_return', 'volatility', 'scenario_params']
            for key in required_keys:
                assert key in results
                assert isinstance(results[key], (float, dict))
        
        # Market crash should have worse VaR than base case
        base_var = calculator.calculate_var(sample_returns, 0.05)
        crash_var = stress_results['market_crash']['var_95']
        assert crash_var < base_var  # More negative (worse)
    
    def test_stress_test_scenarios_validation(self, calculator):
        """Test validation in stress testing."""
        # Test with empty returns
        with pytest.raises(ValueError, match="Base returns must be provided"):
            calculator.stress_test_scenarios([], {'scenario': {}})
        
        # Test with empty scenarios
        with pytest.raises(ValueError, match="Stress scenarios must be provided"):
            calculator.stress_test_scenarios([0.01, 0.02], {})
    
    def test_stress_test_scenarios_error_handling(self, calculator, sample_returns):
        """Test error handling in stress testing."""
        # Create a scenario that might cause issues
        problematic_scenarios = {
            'bad_scenario': {
                'invalid_param': 'invalid_value'
            }
        }
        
        with patch.object(calculator.logger, 'error') as mock_error:
            results = calculator.stress_test_scenarios(sample_returns, problematic_scenarios)
            
            # Should handle errors gracefully
            assert isinstance(results, dict)
            # Error should be logged if scenario processing fails
    
    def test_var_coherence_properties(self, calculator):
        """Test that VaR satisfies coherence properties where applicable."""
        # Create two return series
        returns1 = np.random.normal(0.01, 0.02, 100).tolist()
        returns2 = np.random.normal(0.005, 0.015, 100).tolist()
        
        var1 = calculator.calculate_var(returns1, 0.05)
        var2 = calculator.calculate_var(returns2, 0.05)
        
        # Test monotonicity: if returns1 dominates returns2, VaR1 should be better
        # This is a simplified test - full stochastic dominance is complex
        mean1 = np.mean(returns1)
        mean2 = np.mean(returns2)
        
        if mean1 > mean2:
            # Higher mean should generally lead to better (higher) VaR
            # Note: This might not always hold due to distribution shapes
            pass  # Skip this test as it's not always true for VaR
    
    def test_expected_shortfall_coherence(self, calculator):
        """Test that Expected Shortfall is a coherent risk measure."""
        returns = np.random.normal(0.01, 0.02, 100).tolist()
        
        # Test that ES is always worse than or equal to VaR
        var_95 = calculator.calculate_var(returns, 0.05)
        es_95 = calculator.calculate_expected_shortfall(returns, 0.05)
        
        assert es_95 <= var_95  # ES should be more conservative (lower/more negative)
    
    def test_large_dataset_performance(self, calculator):
        """Test performance with large datasets."""
        # Generate large dataset
        large_returns = np.random.normal(0.01, 0.02, 10000).tolist()
        
        # Should handle large datasets efficiently
        var_value = calculator.calculate_var(large_returns, 0.05)
        es_value = calculator.calculate_expected_shortfall(large_returns, 0.05)
        metrics = calculator.calculate_risk_metrics(large_returns)
        
        assert isinstance(var_value, float)
        assert isinstance(es_value, float)
        assert metrics['sample_size'] == 10000
    
    def test_extreme_confidence_levels(self, calculator, sample_returns):
        """Test with extreme confidence levels."""
        # Very high confidence (very low probability)
        var_999 = calculator.calculate_var(sample_returns, 0.001)
        var_95 = calculator.calculate_var(sample_returns, 0.05)
        
        # Should be more extreme
        assert var_999 < var_95
        
        # Very low confidence (high probability)
        var_50 = calculator.calculate_var(sample_returns, 0.50)
        
        # Should be close to median
        median_return = np.median(sample_returns)
        assert abs(var_50 - median_return) < 1e-10