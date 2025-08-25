"""
Comprehensive unit tests for ScenarioGenerator.
Tests parameter estimation, correlation modeling, and scenario generation functionality.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List, Dict

from trading_platform.services.monte_carlo.scenario_generator import ScenarioGenerator
from trading_platform.models.trading import ProcessedTrade


class TestScenarioGenerator:
    """Test suite for ScenarioGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create a ScenarioGenerator instance with fixed seed for reproducible tests."""
        return ScenarioGenerator(random_seed=42)
    
    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data for testing."""
        np.random.seed(42)
        return np.random.normal(0.001, 0.02, 100).tolist()
    
    @pytest.fixture
    def sample_trades(self):
        """Generate sample ProcessedTrade objects for testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 30)
        
        for i in range(50):
            entry_time = base_time + timedelta(hours=i)
            exit_time = entry_time + timedelta(minutes=30)
            entry_price = 100.0 + np.random.normal(0, 1)
            exit_price = entry_price + np.random.normal(0.1, 0.5)
            quantity = 10
            side = 'LONG' if i % 2 == 0 else 'SHORT'
            
            if side == 'LONG':
                profit_loss = (exit_price - entry_price) * quantity - 2.0
            else:
                profit_loss = (entry_price - exit_price) * quantity - 2.0
            
            trade = ProcessedTrade(
                trade_id=f"TRADE_{i:03d}",
                account_name="TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit_loss,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i:03d}",
                exit_order_id=f"EXIT_{i:03d}"
            )
            trades.append(trade)
        
        return trades
    
    def test_initialization(self):
        """Test ScenarioGenerator initialization."""
        # Test with random seed
        generator = ScenarioGenerator(random_seed=123)
        assert generator.fitted_distributions == {}
        assert generator.correlation_matrix is None
        
        # Test without random seed
        generator = ScenarioGenerator()
        assert generator.fitted_distributions == {}
        assert generator.correlation_matrix is None
    
    def test_estimate_parameters_basic(self, generator, sample_returns):
        """Test basic parameter estimation functionality."""
        params = generator.estimate_parameters(sample_returns)
        
        # Check required keys are present
        required_keys = [
            'mean', 'std', 'skewness', 'kurtosis', 'min', 'max', 'median',
            'q25', 'q75', 'jarque_bera_stat', 'jarque_bera_pvalue',
            'ks_stat', 'ks_pvalue', 'best_distribution', 'best_aic',
            'distribution_params', 'sample_size'
        ]
        
        for key in required_keys:
            assert key in params
        
        # Check parameter values are reasonable
        assert isinstance(params['mean'], float)
        assert isinstance(params['std'], float)
        assert params['std'] > 0
        assert params['sample_size'] == len(sample_returns)
        assert params['best_distribution'] in ['normal', 't', 'skewnorm']
        assert isinstance(params['best_aic'], float)
    
    def test_estimate_parameters_insufficient_data(self, generator):
        """Test parameter estimation with insufficient data."""
        # Test with empty data
        with pytest.raises(ValueError, match="Insufficient historical data"):
            generator.estimate_parameters([])
        
        # Test with too few data points
        with pytest.raises(ValueError, match="Insufficient historical data"):
            generator.estimate_parameters([1.0, 2.0, 3.0])
    
    def test_estimate_parameters_invalid_data(self, generator):
        """Test parameter estimation with invalid data."""
        # Test with all NaN values
        invalid_data = [np.nan] * 20
        with pytest.raises(ValueError, match="Insufficient valid data points"):
            generator.estimate_parameters(invalid_data)
        
        # Test with all infinite values
        invalid_data = [np.inf] * 20
        with pytest.raises(ValueError, match="Insufficient valid data points"):
            generator.estimate_parameters(invalid_data)
    
    def test_estimate_parameters_mixed_data(self, generator):
        """Test parameter estimation with mixed valid/invalid data."""
        # Create data with some NaN and infinite values
        data = [1.0, 2.0, np.nan, 3.0, 4.0, np.inf, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        params = generator.estimate_parameters(data)
        
        # Should work with valid subset
        assert params['sample_size'] == 10  # Only valid values counted
        assert np.isfinite(params['mean'])
        assert np.isfinite(params['std'])
    
    def test_generate_correlated_scenarios_basic(self, generator):
        """Test basic correlated scenario generation."""
        # Create sample asset data
        np.random.seed(42)
        assets_data = {
            'asset1': np.random.normal(0.001, 0.02, 100).tolist(),
            'asset2': np.random.normal(0.0005, 0.015, 100).tolist(),
            'asset3': np.random.normal(0.002, 0.025, 100).tolist()
        }
        
        scenarios = generator.generate_correlated_scenarios(assets_data, num_scenarios=50)
        
        # Check structure
        assert isinstance(scenarios, dict)
        assert len(scenarios) == 3
        assert all(asset in scenarios for asset in assets_data.keys())
        
        # Check each asset has correct number of scenarios
        for asset, asset_scenarios in scenarios.items():
            assert len(asset_scenarios) == 50
            assert all(isinstance(scenario, list) for scenario in asset_scenarios)
    
    def test_generate_correlated_scenarios_validation(self, generator):
        """Test validation in correlated scenario generation."""
        # Test with empty data
        with pytest.raises(ValueError, match="No asset data provided"):
            generator.generate_correlated_scenarios({}, 10)
        
        # Test with negative scenarios
        assets_data = {'asset1': [1.0] * 20}
        with pytest.raises(ValueError, match="Number of scenarios must be positive"):
            generator.generate_correlated_scenarios(assets_data, -1)
        
        # Test with insufficient data
        assets_data = {'asset1': [1.0, 2.0]}  # Too few points
        with pytest.raises(ValueError, match="Insufficient data for asset"):
            generator.generate_correlated_scenarios(assets_data, 10)
    
    def test_generate_multi_step_scenarios(self, generator, sample_returns):
        """Test multi-step scenario generation."""
        scenarios = generator.generate_multi_step_scenarios(
            sample_returns, num_scenarios=20, num_steps=10
        )
        
        # Check structure
        assert len(scenarios) == 20
        assert all(len(scenario) == 10 for scenario in scenarios)
        assert all(all(isinstance(val, float) for val in scenario) for scenario in scenarios)
    
    def test_generate_multi_step_scenarios_validation(self, generator, sample_returns):
        """Test validation in multi-step scenario generation."""
        # Test with invalid parameters
        with pytest.raises(ValueError, match="Number of scenarios and steps must be positive"):
            generator.generate_multi_step_scenarios(sample_returns, 0, 10)
        
        with pytest.raises(ValueError, match="Number of scenarios and steps must be positive"):
            generator.generate_multi_step_scenarios(sample_returns, 10, 0)
    
    def test_validate_scenarios_basic(self, generator, sample_returns):
        """Test basic scenario validation."""
        # Generate scenarios first
        scenarios = generator.generate_multi_step_scenarios(
            sample_returns, num_scenarios=100, num_steps=5
        )
        
        validation_results = generator.validate_scenarios(scenarios, sample_returns)
        
        # Check required keys
        required_keys = [
            'historical_mean', 'scenario_mean', 'mean_difference',
            'historical_std', 'scenario_std', 'std_difference',
            'historical_skewness', 'scenario_skewness', 'skewness_difference',
            'historical_kurtosis', 'scenario_kurtosis', 'kurtosis_difference',
            'ks_statistic', 'ks_pvalue', 'num_scenarios', 'total_scenario_points',
            'historical_sample_size'
        ]
        
        for key in required_keys:
            assert key in validation_results
        
        # Check values are reasonable
        assert validation_results['num_scenarios'] == 100
        assert validation_results['historical_sample_size'] == len(sample_returns)
        assert validation_results['total_scenario_points'] == 500  # 100 scenarios * 5 steps
        assert 0 <= validation_results['ks_pvalue'] <= 1
    
    def test_validate_scenarios_validation(self, generator):
        """Test validation in scenario validation."""
        # Test with empty scenarios
        with pytest.raises(ValueError, match="Both scenarios and historical data must be provided"):
            generator.validate_scenarios([], [1.0, 2.0, 3.0])
        
        # Test with empty historical data
        with pytest.raises(ValueError, match="Both scenarios and historical data must be provided"):
            generator.validate_scenarios([[1.0, 2.0]], [])
    
    def test_extract_returns_from_trades(self, generator, sample_trades):
        """Test extraction of returns from trades."""
        returns = generator.extract_returns_from_trades(sample_trades)
        
        # Check structure
        assert isinstance(returns, list)
        assert len(returns) == len(sample_trades)
        assert all(isinstance(ret, float) for ret in returns)
        assert all(np.isfinite(ret) for ret in returns)
    
    def test_extract_returns_from_trades_empty(self, generator):
        """Test extraction from empty trade list."""
        returns = generator.extract_returns_from_trades([])
        assert returns == []
    
    def test_extract_returns_from_trades_zero_entry_price(self, generator):
        """Test extraction with zero entry price (should be filtered out)."""
        # Create a trade with zero entry price
        trade = Mock()
        trade.entry_price = 0.0
        trade.return_percentage = 10.0
        
        returns = generator.extract_returns_from_trades([trade])
        assert returns == []  # Should be filtered out
    
    def test_nearest_positive_definite_cholesky(self, generator):
        """Test nearest positive definite matrix calculation."""
        # Create a non-positive definite matrix
        matrix = np.array([
            [1.0, 0.9, 0.9],
            [0.9, 1.0, 0.9],
            [0.9, 0.9, 1.0]
        ])
        
        # Make it non-positive definite by setting a negative eigenvalue
        eigenvals, eigenvecs = np.linalg.eigh(matrix)
        eigenvals[0] = -0.1  # Make first eigenvalue negative
        matrix = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
        
        # Test the method
        cholesky = generator._nearest_positive_definite_cholesky(matrix)
        
        # Check that result is valid Cholesky decomposition
        assert cholesky.shape == matrix.shape
        reconstructed = cholesky @ cholesky.T
        
        # Check diagonal elements are approximately 1 (correlation matrix property)
        np.testing.assert_array_almost_equal(np.diag(reconstructed), np.ones(3), decimal=6)
    
    def test_correlation_matrix_storage(self, generator):
        """Test that correlation matrix is properly stored."""
        assets_data = {
            'asset1': np.random.normal(0.001, 0.02, 50).tolist(),
            'asset2': np.random.normal(0.0005, 0.015, 50).tolist()
        }
        
        generator.generate_correlated_scenarios(assets_data, num_scenarios=10)
        
        # Check correlation matrix was stored
        assert generator.correlation_matrix is not None
        assert generator.correlation_matrix.shape == (2, 2)
        
        # Check it's a valid correlation matrix
        np.testing.assert_array_almost_equal(
            np.diag(generator.correlation_matrix), 
            np.ones(2), 
            decimal=10
        )
    
    def test_fitted_distributions_storage(self, generator, sample_returns):
        """Test that fitted distributions are properly stored."""
        generator.estimate_parameters(sample_returns)
        
        # Check fitted distribution was stored
        assert 'best' in generator.fitted_distributions
        best_dist = generator.fitted_distributions['best']
        
        assert 'name' in best_dist
        assert 'distribution' in best_dist
        assert 'params' in best_dist
        assert best_dist['name'] in ['normal', 't', 'skewnorm']
    
    @patch('trading_platform.services.monte_carlo.scenario_generator.stats')
    def test_distribution_fitting_failure_handling(self, mock_stats, generator):
        """Test handling of distribution fitting failures."""
        # Mock distribution fitting to raise an exception
        mock_stats.norm.fit.side_effect = Exception("Fitting failed")
        mock_stats.t.fit.side_effect = Exception("Fitting failed")
        mock_stats.skewnorm.fit.side_effect = Exception("Fitting failed")
        
        # Mock other stats functions to work normally
        mock_stats.skew.return_value = 0.1
        mock_stats.kurtosis.return_value = 0.2
        mock_stats.jarque_bera.return_value = (1.0, 0.5)
        mock_stats.kstest.return_value = (0.1, 0.8)
        
        sample_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        
        # Should handle the exception gracefully
        with patch.object(generator.logger, 'warning') as mock_warning:
            params = generator.estimate_parameters(sample_data)
            
            # Should have logged warnings for failed fits
            assert mock_warning.call_count >= 1
            
            # Should still return basic parameters
            assert 'mean' in params
            assert 'std' in params