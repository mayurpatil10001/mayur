"""
Monte Carlo simulator for trading optimization.
Implements simulation execution with configurable parameters, parallel processing, and progress tracking.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import logging
from datetime import datetime, timedelta
import time

from ...interfaces.simulation_interfaces import IMonteCarloSimulator
from ...models.trading import ProcessedTrade
from .scenario_generator import ScenarioGenerator


class MonteCarloSimulator(IMonteCarloSimulator):
    """
    Monte Carlo simulator for trading strategy analysis.
    Supports parallel processing, progress tracking, and configurable simulation parameters.
    """
    
    def __init__(self, scenario_generator: Optional[ScenarioGenerator] = None, 
                 max_workers: Optional[int] = None, random_seed: Optional[int] = None):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            scenario_generator: Optional scenario generator instance
            max_workers: Maximum number of parallel workers (defaults to CPU count)
            random_seed: Optional seed for reproducible results
        """
        self.logger = logging.getLogger(__name__)
        self.scenario_generator = scenario_generator or ScenarioGenerator(random_seed=random_seed)
        self.max_workers = max_workers or min(cpu_count(), 8)  # Cap at 8 to avoid memory issues
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
    
    def run_simulation(self, trades: List[ProcessedTrade], num_simulations: int = 10000, 
                      time_horizon: int = 252, progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation on trading data.
        
        Args:
            trades: List of historical trades
            num_simulations: Number of simulation runs
            time_horizon: Time horizon in trading days
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary containing simulation results and statistics
        """
        if not trades:
            raise ValueError("No trades provided for simulation")
        
        if num_simulations <= 0:
            raise ValueError("Number of simulations must be positive")
        
        if time_horizon <= 0:
            raise ValueError("Time horizon must be positive")
        
        start_time = time.time()
        self.logger.info(f"Starting Monte Carlo simulation with {num_simulations} runs over {time_horizon} days")
        
        # Extract returns from trades
        returns = self.scenario_generator.extract_returns_from_trades(trades)
        
        if not returns:
            raise ValueError("No valid returns extracted from trades")
        
        # Calculate initial capital based on average trade size
        initial_capital = self._calculate_initial_capital(trades)
        
        # Generate scenarios
        scenarios = self.generate_scenarios(returns, num_simulations, time_horizon)
        
        # Run simulations with parallel processing
        simulation_results = self._run_parallel_simulations(
            scenarios, initial_capital, progress_callback
        )
        
        # Calculate comprehensive statistics
        statistics = self._calculate_simulation_statistics(simulation_results, trades)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        self.logger.info(f"Monte Carlo simulation completed in {execution_time:.2f} seconds")
        
        return {
            'simulation_results': simulation_results,
            'statistics': statistics,
            'parameters': {
                'num_simulations': num_simulations,
                'time_horizon': time_horizon,
                'initial_capital': initial_capital,
                'num_trades': len(trades),
                'execution_time': execution_time
            },
            'scenarios_used': len(scenarios)
        }
    
    def generate_scenarios(self, historical_returns: List[float], 
                         num_scenarios: int, time_horizon: int = 252) -> List[List[float]]:
        """
        Generate scenario paths for simulation.
        
        Args:
            historical_returns: Historical return data
            num_scenarios: Number of scenarios to generate
            time_horizon: Number of time steps per scenario
            
        Returns:
            List of scenario paths
        """
        if not historical_returns:
            raise ValueError("No historical returns provided")
        
        return self.scenario_generator.generate_multi_step_scenarios(
            historical_returns, num_scenarios, time_horizon
        )
    
    def simulate_portfolio_performance(self, scenarios: List[List[float]], 
                                     initial_capital: float) -> List[float]:
        """
        Simulate portfolio performance across scenarios.
        
        Args:
            scenarios: List of scenario paths
            initial_capital: Starting capital amount
            
        Returns:
            List of final portfolio values
        """
        if not scenarios:
            raise ValueError("No scenarios provided")
        
        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        
        final_values = []
        
        for scenario in scenarios:
            portfolio_value = initial_capital
            
            for return_rate in scenario:
                # Apply return to current portfolio value
                portfolio_value *= (1 + return_rate)
            
            final_values.append(portfolio_value)
        
        return final_values
    
    def _calculate_initial_capital(self, trades: List[ProcessedTrade]) -> float:
        """
        Calculate initial capital based on trade characteristics.
        
        Args:
            trades: List of processed trades
            
        Returns:
            Estimated initial capital
        """
        if not trades:
            return 100000.0  # Default capital
        
        # Calculate average position size
        position_sizes = [abs(trade.entry_price * trade.quantity) for trade in trades]
        avg_position_size = np.mean(position_sizes)
        
        # Use 10x average position size as initial capital (conservative leverage)
        initial_capital = max(avg_position_size * 10, 50000.0)  # Minimum $50k
        
        return float(initial_capital)
    
    def _run_parallel_simulations(self, scenarios: List[List[float]], 
                                initial_capital: float,
                                progress_callback: Optional[Callable[[int, int], None]] = None) -> List[float]:
        """
        Run simulations in parallel for better performance.
        
        Args:
            scenarios: List of scenario paths
            initial_capital: Starting capital
            progress_callback: Optional progress callback
            
        Returns:
            List of simulation results
        """
        # Split scenarios into chunks for parallel processing
        chunk_size = max(1, len(scenarios) // self.max_workers)
        scenario_chunks = [scenarios[i:i + chunk_size] for i in range(0, len(scenarios), chunk_size)]
        
        results = []
        completed_simulations = 0
        
        if len(scenario_chunks) == 1 or self.max_workers == 1:
            # Run sequentially if only one chunk or single worker
            for chunk in scenario_chunks:
                chunk_results = self._simulate_chunk(chunk, initial_capital)
                results.extend(chunk_results)
                
                completed_simulations += len(chunk_results)
                if progress_callback:
                    progress_callback(completed_simulations, len(scenarios))
        else:
            # Run in parallel
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all chunks
                future_to_chunk = {
                    executor.submit(self._simulate_chunk, chunk, initial_capital): chunk 
                    for chunk in scenario_chunks
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_chunk):
                    try:
                        chunk_results = future.result()
                        results.extend(chunk_results)
                        
                        completed_simulations += len(chunk_results)
                        if progress_callback:
                            progress_callback(completed_simulations, len(scenarios))
                            
                    except Exception as e:
                        self.logger.error(f"Simulation chunk failed: {e}")
                        # Continue with other chunks
                        continue
        
        return results
    
    @staticmethod
    def _simulate_chunk(scenarios: List[List[float]], initial_capital: float) -> List[float]:
        """
        Simulate a chunk of scenarios (static method for multiprocessing).
        
        Args:
            scenarios: Chunk of scenario paths
            initial_capital: Starting capital
            
        Returns:
            List of final portfolio values for this chunk
        """
        results = []
        
        for scenario in scenarios:
            portfolio_value = initial_capital
            
            for return_rate in scenario:
                portfolio_value *= (1 + return_rate)
            
            results.append(portfolio_value)
        
        return results
    
    def _calculate_simulation_statistics(self, simulation_results: List[float], 
                                       trades: List[ProcessedTrade]) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics from simulation results.
        
        Args:
            simulation_results: List of final portfolio values
            trades: Original trade data for context
            
        Returns:
            Dictionary of statistical measures
        """
        if not simulation_results:
            return {}
        
        results_array = np.array(simulation_results)
        
        # Basic statistics
        mean_value = np.mean(results_array)
        median_value = np.median(results_array)
        std_value = np.std(results_array, ddof=1)
        min_value = np.min(results_array)
        max_value = np.max(results_array)
        
        # Percentiles
        percentiles = [1, 5, 10, 25, 75, 90, 95, 99]
        percentile_values = {f'p{p}': np.percentile(results_array, p) for p in percentiles}
        
        # Calculate returns relative to initial capital
        initial_capital = self._calculate_initial_capital(trades)
        returns = (results_array - initial_capital) / initial_capital
        
        # Return statistics
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        # Risk metrics
        negative_returns = returns[returns < 0]
        positive_returns = returns[returns > 0]
        
        probability_of_loss = len(negative_returns) / len(returns)
        probability_of_profit = len(positive_returns) / len(returns)
        
        # Expected values
        expected_loss = np.mean(negative_returns) if len(negative_returns) > 0 else 0.0
        expected_profit = np.mean(positive_returns) if len(positive_returns) > 0 else 0.0
        
        # Sharpe-like ratio (assuming risk-free rate of 0)
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < mean_return]
        downside_deviation = np.std(downside_returns, ddof=1) if len(downside_returns) > 0 else 0.0
        sortino_ratio = mean_return / downside_deviation if downside_deviation > 0 else 0.0
        
        # Maximum drawdown simulation
        max_drawdown = self._calculate_max_drawdown_from_results(results_array, initial_capital)
        
        return {
            'portfolio_values': {
                'mean': float(mean_value),
                'median': float(median_value),
                'std': float(std_value),
                'min': float(min_value),
                'max': float(max_value),
                **{k: float(v) for k, v in percentile_values.items()}
            },
            'returns': {
                'mean': float(mean_return),
                'std': float(std_return),
                'min': float(np.min(returns)),
                'max': float(np.max(returns))
            },
            'risk_metrics': {
                'probability_of_loss': float(probability_of_loss),
                'probability_of_profit': float(probability_of_profit),
                'expected_loss': float(expected_loss),
                'expected_profit': float(expected_profit),
                'sharpe_ratio': float(sharpe_ratio),
                'sortino_ratio': float(sortino_ratio),
                'max_drawdown': float(max_drawdown)
            },
            'simulation_quality': {
                'num_simulations': len(simulation_results),
                'convergence_metric': float(std_value / np.sqrt(len(simulation_results))),  # Standard error
                'outlier_count': int(np.sum(np.abs(results_array - mean_value) > 3 * std_value))
            }
        }
    
    def _calculate_max_drawdown_from_results(self, results: np.ndarray, initial_capital: float) -> float:
        """
        Calculate maximum drawdown from simulation results.
        
        Args:
            results: Array of final portfolio values
            initial_capital: Starting capital
            
        Returns:
            Maximum drawdown as a percentage
        """
        # For final values, drawdown is simply the worst case relative to initial capital
        min_value = np.min(results)
        max_drawdown = (min_value - initial_capital) / initial_capital
        
        return max_drawdown
    
    def run_sensitivity_analysis(self, trades: List[ProcessedTrade], 
                               parameter_ranges: Dict[str, List[Any]],
                               base_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run sensitivity analysis across different parameter values.
        
        Args:
            trades: Historical trade data
            parameter_ranges: Dictionary of parameter names to lists of values to test
            base_params: Base parameters to use (defaults applied for missing values)
            
        Returns:
            Dictionary containing sensitivity analysis results
        """
        if not trades:
            raise ValueError("No trades provided for sensitivity analysis")
        
        if not parameter_ranges:
            raise ValueError("No parameter ranges provided")
        
        # Default base parameters
        default_params = {
            'num_simulations': 1000,
            'time_horizon': 252
        }
        
        if base_params:
            default_params.update(base_params)
        
        sensitivity_results = {}
        
        for param_name, param_values in parameter_ranges.items():
            if param_name not in default_params:
                self.logger.warning(f"Unknown parameter {param_name}, skipping")
                continue
            
            param_results = []
            
            for param_value in param_values:
                # Create parameters for this run
                run_params = default_params.copy()
                run_params[param_name] = param_value
                
                try:
                    # Run simulation with these parameters
                    result = self.run_simulation(
                        trades=trades,
                        num_simulations=run_params['num_simulations'],
                        time_horizon=run_params['time_horizon']
                    )
                    
                    # Extract key metrics
                    param_results.append({
                        'parameter_value': param_value,
                        'mean_return': result['statistics']['returns']['mean'],
                        'std_return': result['statistics']['returns']['std'],
                        'sharpe_ratio': result['statistics']['risk_metrics']['sharpe_ratio'],
                        'probability_of_loss': result['statistics']['risk_metrics']['probability_of_loss'],
                        'max_drawdown': result['statistics']['risk_metrics']['max_drawdown'],
                        'execution_time': result['parameters']['execution_time']
                    })
                    
                except Exception as e:
                    self.logger.error(f"Sensitivity analysis failed for {param_name}={param_value}: {e}")
                    continue
            
            sensitivity_results[param_name] = param_results
        
        return {
            'sensitivity_results': sensitivity_results,
            'base_parameters': default_params,
            'analysis_timestamp': datetime.now().isoformat()
        }