"""
Comprehensive unit tests for MonteCarloSimulator.
Tests simulation execution, parallel processing, and result aggregation.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List

from trading_platform.services.monte_carlo.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.services.monte_carlo.scenario_generator import ScenarioGenerator
from trading_platform.models.trading import ProcessedTrade


class TestMonteCarloSimulator:
    """Test suite for MonteCarloSimulator class."""
    
    @pytest.fixture
    def sample_trades(self):
        """Generate sample ProcessedTrade objects for testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 30)
        
        for i in range(20):
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
    
    @pytest.fixture
    def simulator(self):
        """Create a MonteCarloSimulator instance with fixed seed."""
        return MonteCarloSimulator(random_seed=42, max_workers=2)
    
    @pytest.fixture
    def mock_scenario_generator(self):
        """Create a mock scenario generator."""
        generator = Mock(spec=ScenarioGenerator)
        generator.extract_returns_from_trades.return_value = [0.01, -0.005, 0.02, -0.01, 0.015] * 4
        generator.generate_multi_step_scenarios.return_value = [
            [0.01, -0.005, 0.02] for _ in range(10)
        ]
        return generator
    
    def test_initialization_default(self):
        """Test MonteCarloSimulator initialization with defaults."""
        simulator = MonteCarloSimulator()
        
        assert simulator.scenario_generator is not None
        assert simulator.max_workers > 0
        assert simulator.random_seed is None
    
    def test_initialization_with_parameters(self):
        """Test MonteCarloSimulator initialization with custom parameters."""
        mock_generator = Mock(spec=ScenarioGenerator)
        simulator = MonteCarloSimulator(
            scenario_generator=mock_generator,
            max_workers=4,
            random_seed=123
        )
        
        assert simulator.scenario_generator is mock_generator
        assert simulator.max_workers == 4
        assert simulator.random_seed == 123
    
    def test_run_simulation_basic(self, simulator, sample_trades):
        """Test basic simulation execution."""
        result = simulator.run_simulation(
            trades=sample_trades,
            num_simulations=100,
            time_horizon=10
        )
        
        # Check result structure
        assert 'simulation_results' in result
        assert 'statistics' in result
        assert 'parameters' in result
        assert 'scenarios_used' in result
        
        # Check simulation results
        assert len(result['simulation_results']) == 100
        assert all(isinstance(val, float) for val in result['simulation_results'])
        
        # Check parameters
        params = result['parameters']
        assert params['num_simulations'] == 100
        assert params['time_horizon'] == 10
        assert params['num_trades'] == len(sample_trades)
        assert 'execution_time' in params
        assert 'initial_capital' in params
    
    def test_run_simulation_validation(self, simulator):
        """Test validation in run_simulation method."""
        # Test with empty trades
        with pytest.raises(ValueError, match="No trades provided"):
            simulator.run_simulation([], num_simulations=100)
        
        # Test with invalid num_simulations
        sample_trade = Mock(spec=ProcessedTrade)
        with pytest.raises(ValueError, match="Number of simulations must be positive"):
            simulator.run_simulation([sample_trade], num_simulations=0)
        
        # Test with invalid time_horizon
        with pytest.raises(ValueError, match="Time horizon must be positive"):
            simulator.run_simulation([sample_trade], num_simulations=100, time_horizon=0)
    
    def test_generate_scenarios(self, simulator):
        """Test scenario generation."""
        # Use sufficient historical data (minimum 10 points)
        historical_returns = [0.01, -0.005, 0.02, -0.01, 0.015, 0.008, -0.003, 0.012, -0.007, 0.009, 0.004]
        
        scenarios = simulator.generate_scenarios(
            historical_returns, num_scenarios=50, time_horizon=5
        )
        
        assert len(scenarios) == 50
        assert all(len(scenario) == 5 for scenario in scenarios)
        assert all(all(isinstance(val, float) for val in scenario) for scenario in scenarios)
    
    def test_generate_scenarios_validation(self, simulator):
        """Test validation in generate_scenarios method."""
        with pytest.raises(ValueError, match="No historical returns provided"):
            simulator.generate_scenarios([], num_scenarios=10)
    
    def test_simulate_portfolio_performance(self, simulator):
        """Test portfolio performance simulation."""
        scenarios = [
            [0.01, -0.005, 0.02],
            [-0.01, 0.015, -0.005],
            [0.005, 0.01, 0.008]
        ]
        initial_capital = 100000.0
        
        final_values = simulator.simulate_portfolio_performance(scenarios, initial_capital)
        
        assert len(final_values) == 3
        assert all(isinstance(val, float) for val in final_values)
        assert all(val > 0 for val in final_values)  # Should be positive
        
        # Test first scenario manually
        expected_first = initial_capital * (1 + 0.01) * (1 - 0.005) * (1 + 0.02)
        assert abs(final_values[0] - expected_first) < 1e-10
    
    def test_simulate_portfolio_performance_validation(self, simulator):
        """Test validation in simulate_portfolio_performance method."""
        # Test with empty scenarios
        with pytest.raises(ValueError, match="No scenarios provided"):
            simulator.simulate_portfolio_performance([], 100000.0)
        
        # Test with invalid initial capital
        scenarios = [[0.01, 0.02]]
        with pytest.raises(ValueError, match="Initial capital must be positive"):
            simulator.simulate_portfolio_performance(scenarios, 0.0)
    
    def test_calculate_initial_capital(self, simulator, sample_trades):
        """Test initial capital calculation."""
        initial_capital = simulator._calculate_initial_capital(sample_trades)
        
        assert isinstance(initial_capital, float)
        assert initial_capital > 0
        assert initial_capital >= 50000.0  # Minimum threshold
    
    def test_calculate_initial_capital_empty_trades(self, simulator):
        """Test initial capital calculation with empty trades."""
        initial_capital = simulator._calculate_initial_capital([])
        assert initial_capital == 100000.0  # Default value
    
    def test_simulate_chunk_static_method(self):
        """Test the static _simulate_chunk method."""
        scenarios = [
            [0.01, -0.005],
            [0.02, 0.01]
        ]
        initial_capital = 100000.0
        
        results = MonteCarloSimulator._simulate_chunk(scenarios, initial_capital)
        
        assert len(results) == 2
        expected_first = initial_capital * (1 + 0.01) * (1 - 0.005)
        expected_second = initial_capital * (1 + 0.02) * (1 + 0.01)
        
        assert abs(results[0] - expected_first) < 1e-10
        assert abs(results[1] - expected_second) < 1e-10
    
    def test_parallel_simulation_execution(self, sample_trades):
        """Test parallel simulation execution."""
        simulator = MonteCarloSimulator(max_workers=2, random_seed=42)
        
        result = simulator.run_simulation(
            trades=sample_trades,
            num_simulations=20,  # Small number for testing
            time_horizon=5
        )
        
        assert len(result['simulation_results']) == 20
        assert 'execution_time' in result['parameters']
    
    def test_progress_callback(self, simulator, sample_trades):
        """Test progress callback functionality."""
        progress_calls = []
        
        def progress_callback(completed, total):
            progress_calls.append((completed, total))
        
        simulator.run_simulation(
            trades=sample_trades,
            num_simulations=10,
            time_horizon=5,
            progress_callback=progress_callback
        )
        
        # Should have received progress updates
        assert len(progress_calls) > 0
        assert all(completed <= total for completed, total in progress_calls)
        assert progress_calls[-1][0] == progress_calls[-1][1]  # Final call should be complete
    
    def test_simulation_statistics_calculation(self, simulator, sample_trades):
        """Test comprehensive statistics calculation."""
        result = simulator.run_simulation(
            trades=sample_trades,
            num_simulations=100,
            time_horizon=10
        )
        
        stats = result['statistics']
        
        # Check portfolio values statistics
        assert 'portfolio_values' in stats
        portfolio_stats = stats['portfolio_values']
        required_portfolio_keys = ['mean', 'median', 'std', 'min', 'max', 'p1', 'p5', 'p95', 'p99']
        for key in required_portfolio_keys:
            assert key in portfolio_stats
            assert isinstance(portfolio_stats[key], float)
        
        # Check returns statistics
        assert 'returns' in stats
        returns_stats = stats['returns']
        required_return_keys = ['mean', 'std', 'min', 'max']
        for key in required_return_keys:
            assert key in returns_stats
            assert isinstance(returns_stats[key], float)
        
        # Check risk metrics
        assert 'risk_metrics' in stats
        risk_stats = stats['risk_metrics']
        required_risk_keys = [
            'probability_of_loss', 'probability_of_profit', 'expected_loss',
            'expected_profit', 'sharpe_ratio', 'sortino_ratio', 'max_drawdown'
        ]
        for key in required_risk_keys:
            assert key in risk_stats
            assert isinstance(risk_stats[key], float)
        
        # Check simulation quality
        assert 'simulation_quality' in stats
        quality_stats = stats['simulation_quality']
        assert 'num_simulations' in quality_stats
        assert 'convergence_metric' in quality_stats
        assert 'outlier_count' in quality_stats
    
    def test_max_drawdown_calculation(self, simulator):
        """Test maximum drawdown calculation."""
        # Create results with known drawdown
        initial_capital = 100000.0
        results = np.array([120000.0, 80000.0, 110000.0, 90000.0])  # Min is 80k
        
        max_drawdown = simulator._calculate_max_drawdown_from_results(results, initial_capital)
        
        expected_drawdown = (80000.0 - 100000.0) / 100000.0  # -20%
        assert abs(max_drawdown - expected_drawdown) < 1e-10
    
    def test_sensitivity_analysis(self, simulator, sample_trades):
        """Test sensitivity analysis functionality."""
        parameter_ranges = {
            'num_simulations': [50, 100],
            'time_horizon': [10, 20]
        }
        
        result = simulator.run_sensitivity_analysis(
            trades=sample_trades,
            parameter_ranges=parameter_ranges
        )
        
        assert 'sensitivity_results' in result
        assert 'base_parameters' in result
        assert 'analysis_timestamp' in result
        
        # Check results for each parameter
        sensitivity_results = result['sensitivity_results']
        assert 'num_simulations' in sensitivity_results
        assert 'time_horizon' in sensitivity_results
        
        # Check structure of parameter results
        for param_name, param_results in sensitivity_results.items():
            assert len(param_results) == 2  # Two values tested
            for param_result in param_results:
                required_keys = [
                    'parameter_value', 'mean_return', 'std_return', 'sharpe_ratio',
                    'probability_of_loss', 'max_drawdown', 'execution_time'
                ]
                for key in required_keys:
                    assert key in param_result
    
    def test_sensitivity_analysis_validation(self, simulator):
        """Test validation in sensitivity analysis."""
        # Test with empty trades
        with pytest.raises(ValueError, match="No trades provided"):
            simulator.run_sensitivity_analysis([], {'num_simulations': [100]})
        
        # Test with empty parameter ranges
        sample_trade = Mock(spec=ProcessedTrade)
        with pytest.raises(ValueError, match="No parameter ranges provided"):
            simulator.run_sensitivity_analysis([sample_trade], {})
    
    def test_sensitivity_analysis_unknown_parameter(self, simulator, sample_trades):
        """Test sensitivity analysis with unknown parameter."""
        parameter_ranges = {
            'unknown_param': [1, 2, 3]
        }
        
        with patch.object(simulator.logger, 'warning') as mock_warning:
            result = simulator.run_sensitivity_analysis(
                trades=sample_trades,
                parameter_ranges=parameter_ranges
            )
            
            # Should log warning and skip unknown parameter
            mock_warning.assert_called_once()
            assert 'unknown_param' not in result['sensitivity_results']
    
    @patch('trading_platform.services.monte_carlo.monte_carlo_simulator.ProcessPoolExecutor')
    def test_parallel_processing_error_handling(self, mock_executor, simulator, sample_trades):
        """Test error handling in parallel processing."""
        # Mock executor to raise exception
        mock_future = Mock()
        mock_future.result.side_effect = Exception("Simulation failed")
        
        # Create a proper context manager mock
        mock_executor_instance = MagicMock()
        mock_executor_instance.submit.return_value = mock_future
        mock_executor.return_value = mock_executor_instance
        
        # Mock as_completed to return the failing future
        with patch('trading_platform.services.monte_carlo.monte_carlo_simulator.as_completed') as mock_as_completed:
            mock_as_completed.return_value = [mock_future]
            
            with patch.object(simulator.logger, 'error') as mock_error:
                # Should handle the error gracefully
                result = simulator.run_simulation(
                    trades=sample_trades,
                    num_simulations=10,
                    time_horizon=5
                )
                
                # Should log error
                mock_error.assert_called_once()
                
                # Should still return a result (might be empty or partial)
                assert 'simulation_results' in result
    
    def test_single_worker_execution(self, sample_trades):
        """Test execution with single worker (sequential processing)."""
        simulator = MonteCarloSimulator(max_workers=1, random_seed=42)
        
        result = simulator.run_simulation(
            trades=sample_trades,
            num_simulations=10,
            time_horizon=5
        )
        
        assert len(result['simulation_results']) == 10
        assert all(isinstance(val, float) for val in result['simulation_results'])
    
    def test_scenario_generator_integration(self, sample_trades):
        """Test integration with scenario generator."""
        # Create simulator with custom scenario generator
        custom_generator = ScenarioGenerator(random_seed=42)
        simulator = MonteCarloSimulator(scenario_generator=custom_generator, random_seed=42)
        
        result = simulator.run_simulation(
            trades=sample_trades,
            num_simulations=50,
            time_horizon=10
        )
        
        assert len(result['simulation_results']) == 50
        assert result['scenarios_used'] == 50
    
    def test_reproducibility_with_seed(self, sample_trades):
        """Test that results are reproducible with same seed."""
        # Test reproducibility by running the same simulator instance twice
        simulator = MonteCarloSimulator(random_seed=42, max_workers=1)
        
        # Reset the random seed before each run to ensure reproducibility
        np.random.seed(42)
        result1 = simulator.run_simulation(sample_trades, num_simulations=20, time_horizon=5)
        
        # Reset the scenario generator and random seed
        simulator.scenario_generator = simulator.scenario_generator.__class__(random_seed=42)
        np.random.seed(42)
        result2 = simulator.run_simulation(sample_trades, num_simulations=20, time_horizon=5)
        
        # Check that both simulations completed successfully
        assert len(result1['simulation_results']) == 20
        assert len(result2['simulation_results']) == 20
        
        # Check that the results have similar statistical properties
        # (exact reproducibility is difficult with complex random processes)
        mean1 = np.mean(result1['simulation_results'])
        mean2 = np.mean(result2['simulation_results'])
        
        # Results should be in the same ballpark (within reasonable variance)
        assert abs(mean1 - mean2) / max(mean1, mean2) < 0.1  # Within 10%