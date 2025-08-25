"""
Statistical validation tests for scenario accuracy.
Tests the statistical properties of generated scenarios against known distributions.
"""

import pytest
import numpy as np
from scipy import stats
from typing import List, Dict
import warnings

from trading_platform.services.monte_carlo.scenario_generator import ScenarioGenerator


class TestScenarioValidation:
    """Test suite for statistical validation of scenario generation."""
    
    @pytest.fixture
    def generator(self):
        """Create a ScenarioGenerator instance with fixed seed."""
        return ScenarioGenerator(random_seed=42)
    
    def test_normal_distribution_accuracy(self, generator):
        """Test accuracy of scenarios generated from normal distribution."""
        # Generate known normal distribution data
        np.random.seed(42)
        true_mean = 0.01
        true_std = 0.05
        historical_data = np.random.normal(true_mean, true_std, 1000).tolist()
        
        # Generate scenarios
        scenarios = generator.generate_multi_step_scenarios(
            historical_data, num_scenarios=1000, num_steps=10
        )
        
        # Flatten scenarios for analysis
        scenario_values = [val for scenario in scenarios for val in scenario]
        
        # Test statistical properties
        scenario_mean = np.mean(scenario_values)
        scenario_std = np.std(scenario_values, ddof=1)
        
        # Allow for some statistical variation (more generous tolerance for Monte Carlo)
        mean_tolerance = 0.005  # 0.5% absolute tolerance
        std_tolerance = 0.2 * true_std  # 20% tolerance for std
        
        assert abs(scenario_mean - true_mean) < mean_tolerance
        assert abs(scenario_std - true_std) < std_tolerance
    
    def test_t_distribution_detection(self, generator):
        """Test detection and fitting of t-distribution."""
        # Generate t-distribution data (heavy tails)
        np.random.seed(42)
        df = 3  # Low degrees of freedom for heavy tails
        historical_data = stats.t.rvs(df, size=1000).tolist()
        
        # Estimate parameters
        params = generator.estimate_parameters(historical_data)
        
        # Should detect heavy tails (high kurtosis)
        assert params['kurtosis'] > 1.0  # t-distribution with df=3 has high kurtosis
        
        # Best distribution might be t or skewnorm (both handle heavy tails)
        assert params['best_distribution'] in ['t', 'skewnorm', 'normal']
    
    def test_skewed_distribution_detection(self, generator):
        """Test detection of skewed distributions."""
        # Generate skewed data
        np.random.seed(42)
        historical_data = stats.skewnorm.rvs(a=5, size=1000).tolist()
        
        # Estimate parameters
        params = generator.estimate_parameters(historical_data)
        
        # Should detect positive skewness
        assert params['skewness'] > 0.5
        
        # Best distribution should handle skewness
        assert params['best_distribution'] in ['skewnorm', 't', 'normal']
    
    def test_correlation_preservation(self, generator):
        """Test that correlation structure is preserved in generated scenarios."""
        # Create correlated data
        np.random.seed(42)
        n_samples = 500
        
        # Generate correlated normal variables
        mean = [0.01, 0.005]
        cov = [[0.04, 0.02], [0.02, 0.03]]  # Correlation ≈ 0.577
        data = np.random.multivariate_normal(mean, cov, n_samples)
        
        assets_data = {
            'asset1': data[:, 0].tolist(),
            'asset2': data[:, 1].tolist()
        }
        
        # Calculate true correlation
        true_correlation = np.corrcoef(data[:, 0], data[:, 1])[0, 1]
        
        # Generate scenarios
        scenarios = generator.generate_correlated_scenarios(assets_data, num_scenarios=1000)
        
        # Extract scenario values
        asset1_values = [scenario[0] for scenario in scenarios['asset1']]
        asset2_values = [scenario[0] for scenario in scenarios['asset2']]
        
        # Calculate scenario correlation
        scenario_correlation = np.corrcoef(asset1_values, asset2_values)[0, 1]
        
        # Should preserve correlation structure (within tolerance)
        correlation_tolerance = 0.15  # Allow some variation due to sampling
        assert abs(scenario_correlation - true_correlation) < correlation_tolerance
    
    def test_multi_asset_correlation_matrix(self, generator):
        """Test correlation matrix preservation with multiple assets."""
        # Create 3-asset correlated data
        np.random.seed(42)
        n_samples = 300
        
        # Define correlation structure
        true_corr_matrix = np.array([
            [1.0, 0.6, 0.3],
            [0.6, 1.0, 0.4],
            [0.3, 0.4, 1.0]
        ])
        
        # Generate data with this correlation structure
        L = np.linalg.cholesky(true_corr_matrix)
        independent_data = np.random.standard_normal((n_samples, 3))
        correlated_data = independent_data @ L.T
        
        assets_data = {
            'asset1': correlated_data[:, 0].tolist(),
            'asset2': correlated_data[:, 1].tolist(),
            'asset3': correlated_data[:, 2].tolist()
        }
        
        # Generate scenarios
        scenarios = generator.generate_correlated_scenarios(assets_data, num_scenarios=500)
        
        # Extract scenario correlation matrix
        scenario_data = np.array([
            [scenario[0] for scenario in scenarios['asset1']],
            [scenario[0] for scenario in scenarios['asset2']],
            [scenario[0] for scenario in scenarios['asset3']]
        ]).T
        
        scenario_corr_matrix = np.corrcoef(scenario_data.T)
        
        # Check correlation preservation
        correlation_tolerance = 0.2
        for i in range(3):
            for j in range(3):
                if i != j:  # Skip diagonal elements
                    assert abs(scenario_corr_matrix[i, j] - true_corr_matrix[i, j]) < correlation_tolerance
    
    def test_scenario_validation_metrics(self, generator):
        """Test comprehensive scenario validation metrics."""
        # Generate known distribution data
        np.random.seed(42)
        true_mean = 0.02
        true_std = 0.1
        historical_data = np.random.normal(true_mean, true_std, 200).tolist()
        
        # Generate scenarios
        scenarios = generator.generate_multi_step_scenarios(
            historical_data, num_scenarios=100, num_steps=5
        )
        
        # Validate scenarios
        validation_results = generator.validate_scenarios(scenarios, historical_data)
        
        # Test statistical similarity
        mean_diff_threshold = 0.05  # 5% of true std
        std_diff_threshold = 0.1 * true_std  # 10% of true std
        
        assert validation_results['mean_difference'] < mean_diff_threshold
        assert validation_results['std_difference'] < std_diff_threshold
        
        # KS test should not reject similarity (p-value > 0.05 for similar distributions)
        # Note: This might occasionally fail due to randomness, so we use a lower threshold
        assert validation_results['ks_pvalue'] > 0.01
    
    def test_large_sample_validation(self, generator):
        """Test validation with large sample sizes."""
        # Generate large dataset
        np.random.seed(42)
        historical_data = np.random.normal(0.01, 0.03, 2000).tolist()
        
        # Generate many scenarios
        scenarios = generator.generate_multi_step_scenarios(
            historical_data, num_scenarios=500, num_steps=10
        )
        
        # Validate
        validation_results = generator.validate_scenarios(scenarios, historical_data)
        
        # With large samples, validation should be very accurate
        assert validation_results['mean_difference'] < 0.01
        assert validation_results['std_difference'] < 0.005
        assert validation_results['total_scenario_points'] == 5000  # 500 * 10
    
    def test_distribution_goodness_of_fit(self, generator):
        """Test goodness of fit for different distributions."""
        distributions_to_test = [
            ('normal', lambda: np.random.normal(0, 1, 500)),
            ('t_distribution', lambda: stats.t.rvs(df=5, size=500)),
            ('skewed', lambda: stats.skewnorm.rvs(a=3, size=500))
        ]
        
        for dist_name, data_generator in distributions_to_test:
            np.random.seed(42)
            historical_data = data_generator().tolist()
            
            # Estimate parameters
            params = generator.estimate_parameters(historical_data)
            
            # Check that parameter estimation completed successfully
            assert 'best_distribution' in params
            assert 'best_aic' in params
            assert np.isfinite(params['best_aic'])
            
            # Check basic statistical properties are reasonable
            assert np.isfinite(params['mean'])
            assert params['std'] > 0
            assert np.isfinite(params['skewness'])
            assert np.isfinite(params['kurtosis'])
    
    def test_extreme_value_handling(self, generator):
        """Test handling of extreme values in data."""
        # Create data with extreme outliers
        np.random.seed(42)
        normal_data = np.random.normal(0, 1, 100)
        extreme_data = np.concatenate([normal_data, [10, -10, 15, -15]])  # Add outliers
        
        historical_data = extreme_data.tolist()
        
        # Should handle extreme values without crashing
        params = generator.estimate_parameters(historical_data)
        
        # Parameters should still be reasonable
        assert np.isfinite(params['mean'])
        assert params['std'] > 0
        assert np.isfinite(params['skewness'])
        assert np.isfinite(params['kurtosis'])
        
        # Generate scenarios
        scenarios = generator.generate_multi_step_scenarios(
            historical_data, num_scenarios=50, num_steps=5
        )
        
        # Scenarios should be generated successfully
        assert len(scenarios) == 50
        assert all(len(scenario) == 5 for scenario in scenarios)
    
    def test_small_sample_robustness(self, generator):
        """Test robustness with small sample sizes."""
        # Test with minimum required sample size
        np.random.seed(42)
        historical_data = np.random.normal(0.01, 0.02, 10).tolist()  # Minimum size
        
        # Should work with minimum data
        params = generator.estimate_parameters(historical_data)
        assert params['sample_size'] == 10
        
        # Generate scenarios
        scenarios = generator.generate_multi_step_scenarios(
            historical_data, num_scenarios=20, num_steps=3
        )
        
        assert len(scenarios) == 20
        assert all(len(scenario) == 3 for scenario in scenarios)
    
    def test_parameter_estimation_consistency(self, generator):
        """Test consistency of parameter estimation across multiple runs."""
        # Generate fixed dataset
        np.random.seed(42)
        historical_data = np.random.normal(0.005, 0.025, 200).tolist()
        
        # Run parameter estimation multiple times with same seed
        results = []
        for _ in range(5):
            generator_instance = ScenarioGenerator(random_seed=123)
            params = generator_instance.estimate_parameters(historical_data)
            results.append(params)
        
        # Results should be identical (same seed, same data)
        for i in range(1, len(results)):
            assert results[i]['mean'] == results[0]['mean']
            assert results[i]['std'] == results[0]['std']
            assert results[i]['best_distribution'] == results[0]['best_distribution']
    
    def test_correlation_matrix_properties(self, generator):
        """Test mathematical properties of correlation matrices."""
        # Create multi-asset data
        np.random.seed(42)
        assets_data = {
            'asset1': np.random.normal(0.01, 0.02, 100).tolist(),
            'asset2': np.random.normal(0.005, 0.015, 100).tolist(),
            'asset3': np.random.normal(0.008, 0.018, 100).tolist()
        }
        
        # Generate scenarios to trigger correlation matrix calculation
        generator.generate_correlated_scenarios(assets_data, num_scenarios=10)
        
        corr_matrix = generator.correlation_matrix
        
        # Test correlation matrix properties
        assert corr_matrix.shape == (3, 3)
        
        # Should be symmetric
        np.testing.assert_array_almost_equal(corr_matrix, corr_matrix.T)
        
        # Diagonal elements should be 1
        np.testing.assert_array_almost_equal(np.diag(corr_matrix), np.ones(3))
        
        # Should be positive semi-definite (all eigenvalues >= 0)
        eigenvalues = np.linalg.eigvals(corr_matrix)
        assert all(eigenval >= -1e-10 for eigenval in eigenvalues)  # Allow small numerical errors
        
        # Off-diagonal elements should be between -1 and 1
        for i in range(3):
            for j in range(3):
                if i != j:
                    assert -1 <= corr_matrix[i, j] <= 1