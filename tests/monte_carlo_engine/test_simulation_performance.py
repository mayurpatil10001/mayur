"""
Performance benchmarking tests for Monte Carlo simulation speed.
Tests execution time, memory usage, and scalability of the simulation engine.
"""

import pytest
import numpy as np
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import List

from trading_platform.services.monte_carlo.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.models.trading import ProcessedTrade


class TestSimulationPerformance:
    """Test suite for Monte Carlo simulation performance benchmarking."""
    
    @pytest.fixture
    def large_trade_dataset(self):
        """Generate a large dataset of trades for performance testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 30)
        
        # Generate 1000 trades
        for i in range(1000):
            entry_time = base_time + timedelta(hours=i % 24, days=i // 24)
            exit_time = entry_time + timedelta(minutes=np.random.randint(5, 120))
            entry_price = 100.0 + np.random.normal(0, 5)
            exit_price = entry_price + np.random.normal(0, 2)
            quantity = np.random.randint(1, 20)
            side = 'LONG' if np.random.random() > 0.5 else 'SHORT'
            
            if side == 'LONG':
                profit_loss = (exit_price - entry_price) * quantity - 2.0
            else:
                profit_loss = (entry_price - exit_price) * quantity - 2.0
            
            trade = ProcessedTrade(
                trade_id=f"PERF_TRADE_{i:04d}",
                account_name="PERF_TEST_ACCOUNT",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit_loss,
                commission=2.0,
                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i:04d}",
                exit_order_id=f"EXIT_{i:04d}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def performance_simulator(self):
        """Create a simulator optimized for performance testing."""
        return MonteCarloSimulator(random_seed=42, max_workers=4)
    
    def test_small_simulation_performance(self, performance_simulator, large_trade_dataset):
        """Test performance with small simulation parameters."""
        start_time = time.time()
        
        result = performance_simulator.run_simulation(
            trades=large_trade_dataset[:100],  # Use subset for small test
            num_simulations=1000,
            time_horizon=50
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Performance assertions
        assert execution_time < 10.0  # Should complete within 10 seconds
        assert len(result['simulation_results']) == 1000
        assert result['parameters']['execution_time'] < 10.0
        
        print(f"Small simulation completed in {execution_time:.2f} seconds")
    
    def test_medium_simulation_performance(self, performance_simulator, large_trade_dataset):
        """Test performance with medium simulation parameters."""
        start_time = time.time()
        
        result = performance_simulator.run_simulation(
            trades=large_trade_dataset[:500],  # Medium dataset
            num_simulations=5000,
            time_horizon=100
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Performance assertions
        assert execution_time < 30.0  # Should complete within 30 seconds
        assert len(result['simulation_results']) == 5000
        
        print(f"Medium simulation completed in {execution_time:.2f} seconds")
    
    def test_large_simulation_performance(self, performance_simulator, large_trade_dataset):
        """Test performance with large simulation parameters."""
        start_time = time.time()
        
        result = performance_simulator.run_simulation(
            trades=large_trade_dataset,  # Full dataset
            num_simulations=10000,
            time_horizon=252
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Performance assertions
        assert execution_time < 60.0  # Should complete within 1 minute
        assert len(result['simulation_results']) == 10000
        
        print(f"Large simulation completed in {execution_time:.2f} seconds")
    
    def test_parallel_vs_sequential_performance(self, large_trade_dataset):
        """Compare parallel vs sequential execution performance."""
        # Sequential execution
        sequential_simulator = MonteCarloSimulator(max_workers=1, random_seed=42)
        start_time = time.time()
        sequential_result = sequential_simulator.run_simulation(
            trades=large_trade_dataset[:200],
            num_simulations=2000,
            time_horizon=50
        )
        sequential_time = time.time() - start_time
        
        # Parallel execution
        parallel_simulator = MonteCarloSimulator(max_workers=4, random_seed=42)
        start_time = time.time()
        parallel_result = parallel_simulator.run_simulation(
            trades=large_trade_dataset[:200],
            num_simulations=2000,
            time_horizon=50
        )
        parallel_time = time.time() - start_time
        
        # Performance comparison
        speedup = sequential_time / parallel_time
        print(f"Sequential time: {sequential_time:.2f}s, Parallel time: {parallel_time:.2f}s")
        print(f"Speedup: {speedup:.2f}x")
        
        # Parallel should be faster (or at least not significantly slower)
        assert parallel_time <= sequential_time * 1.2  # Allow 20% tolerance
        
        # Results should be similar (same seed)
        assert len(sequential_result['simulation_results']) == len(parallel_result['simulation_results'])
    
    def test_memory_usage_monitoring(self, performance_simulator, large_trade_dataset):
        """Monitor memory usage during simulation."""
        process = psutil.Process(os.getpid())
        
        # Measure initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run simulation
        result = performance_simulator.run_simulation(
            trades=large_trade_dataset,
            num_simulations=5000,
            time_horizon=100
        )
        
        # Measure peak memory
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Peak memory: {peak_memory:.1f} MB")
        print(f"Memory increase: {memory_increase:.1f} MB")
        
        # Memory usage should be reasonable (less than 500MB increase)
        assert memory_increase < 500.0
        assert len(result['simulation_results']) == 5000
    
    def test_scalability_with_simulations(self, performance_simulator, large_trade_dataset):
        """Test how execution time scales with number of simulations."""
        simulation_counts = [1000, 2000, 5000]
        execution_times = []
        
        for num_sims in simulation_counts:
            start_time = time.time()
            
            result = performance_simulator.run_simulation(
                trades=large_trade_dataset[:100],
                num_simulations=num_sims,
                time_horizon=50
            )
            
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            
            assert len(result['simulation_results']) == num_sims
            print(f"{num_sims} simulations: {execution_time:.2f}s")
        
        # Execution time should scale roughly linearly
        # Check that doubling simulations doesn't more than triple execution time
        assert execution_times[1] < execution_times[0] * 3.0
        assert execution_times[2] < execution_times[0] * 6.0
    
    def test_scalability_with_time_horizon(self, performance_simulator, large_trade_dataset):
        """Test how execution time scales with time horizon."""
        time_horizons = [50, 100, 252]
        execution_times = []
        
        for horizon in time_horizons:
            start_time = time.time()
            
            result = performance_simulator.run_simulation(
                trades=large_trade_dataset[:100],
                num_simulations=2000,
                time_horizon=horizon
            )
            
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            
            assert len(result['simulation_results']) == 2000
            print(f"Time horizon {horizon}: {execution_time:.2f}s")
        
        # Execution time should scale with time horizon
        # Longer horizons should take more time, but not excessively
        assert execution_times[1] > execution_times[0]
        assert execution_times[2] > execution_times[1]
        assert execution_times[2] < execution_times[0] * 10.0  # Should not be 10x slower
    
    def test_worker_count_optimization(self, large_trade_dataset):
        """Test optimal number of workers for performance."""
        worker_counts = [1, 2, 4, 8]
        execution_times = []
        
        for workers in worker_counts:
            simulator = MonteCarloSimulator(max_workers=workers, random_seed=42)
            
            start_time = time.time()
            result = simulator.run_simulation(
                trades=large_trade_dataset[:200],
                num_simulations=3000,
                time_horizon=50
            )
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            
            assert len(result['simulation_results']) == 3000
            print(f"{workers} workers: {execution_time:.2f}s")
        
        # Find optimal worker count (minimum execution time)
        optimal_index = execution_times.index(min(execution_times))
        optimal_workers = worker_counts[optimal_index]
        
        print(f"Optimal worker count: {optimal_workers}")
        
        # Performance should improve with more workers up to a point
        assert execution_times[1] <= execution_times[0] * 1.1  # 2 workers should be similar or better than 1
    
    def test_progress_callback_overhead(self, performance_simulator, large_trade_dataset):
        """Test performance overhead of progress callbacks."""
        # Run without progress callback
        start_time = time.time()
        result_no_callback = performance_simulator.run_simulation(
            trades=large_trade_dataset[:100],
            num_simulations=2000,
            time_horizon=50
        )
        time_no_callback = time.time() - start_time
        
        # Run with progress callback
        progress_calls = []
        def progress_callback(completed, total):
            progress_calls.append((completed, total))
        
        start_time = time.time()
        result_with_callback = performance_simulator.run_simulation(
            trades=large_trade_dataset[:100],
            num_simulations=2000,
            time_horizon=50,
            progress_callback=progress_callback
        )
        time_with_callback = time.time() - start_time
        
        # Progress callback should not add significant overhead
        overhead = (time_with_callback - time_no_callback) / time_no_callback
        print(f"Progress callback overhead: {overhead:.1%}")
        
        assert overhead < 0.1  # Less than 10% overhead
        assert len(progress_calls) > 0  # Callback was actually called
        assert len(result_no_callback['simulation_results']) == len(result_with_callback['simulation_results'])
    
    def test_sensitivity_analysis_performance(self, performance_simulator, large_trade_dataset):
        """Test performance of sensitivity analysis."""
        parameter_ranges = {
            'num_simulations': [500, 1000, 2000],
            'time_horizon': [50, 100, 150]
        }
        
        start_time = time.time()
        result = performance_simulator.run_sensitivity_analysis(
            trades=large_trade_dataset[:100],
            parameter_ranges=parameter_ranges
        )
        execution_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert execution_time < 30.0  # 30 seconds for sensitivity analysis
        
        # Should have results for all parameter combinations
        assert 'num_simulations' in result['sensitivity_results']
        assert 'time_horizon' in result['sensitivity_results']
        assert len(result['sensitivity_results']['num_simulations']) == 3
        assert len(result['sensitivity_results']['time_horizon']) == 3
        
        print(f"Sensitivity analysis completed in {execution_time:.2f} seconds")
    
    def test_large_dataset_handling(self, performance_simulator):
        """Test handling of very large trade datasets."""
        # Generate extra large dataset
        large_trades = []
        base_time = datetime(2024, 1, 1, 9, 30)
        
        for i in range(5000):  # 5000 trades
            entry_time = base_time + timedelta(hours=i % 24, days=i // 24)
            exit_time = entry_time + timedelta(minutes=30)
            entry_price = 100.0 + np.random.normal(0, 1)
            exit_price = entry_price + np.random.normal(0.1, 0.5)
            
            trade = ProcessedTrade(
                trade_id=f"LARGE_{i:05d}",
                account_name="LARGE_TEST",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=10,
                side='LONG' if i % 2 == 0 else 'SHORT',
                profit_loss=(exit_price - entry_price) * 10 - 2.0,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"ENTRY_{i:05d}",
                exit_order_id=f"EXIT_{i:05d}"
            )
            large_trades.append(trade)
        
        start_time = time.time()
        result = performance_simulator.run_simulation(
            trades=large_trades,
            num_simulations=1000,  # Smaller simulation count for large dataset
            time_horizon=100
        )
        execution_time = time.time() - start_time
        
        # Should handle large dataset without issues
        assert execution_time < 45.0  # Should complete within 45 seconds
        assert len(result['simulation_results']) == 1000
        assert result['parameters']['num_trades'] == 5000
        
        print(f"Large dataset (5000 trades) processed in {execution_time:.2f} seconds")
    
    def test_concurrent_simulations(self, large_trade_dataset):
        """Test running multiple simulations concurrently."""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def run_simulation(simulator_id):
            simulator = MonteCarloSimulator(random_seed=simulator_id, max_workers=2)
            result = simulator.run_simulation(
                trades=large_trade_dataset[:100],
                num_simulations=1000,
                time_horizon=50
            )
            results_queue.put((simulator_id, result))
        
        # Start multiple simulations concurrently
        threads = []
        start_time = time.time()
        
        for i in range(3):  # 3 concurrent simulations
            thread = threading.Thread(target=run_simulation, args=(i,))
            thread.start()
            threads.append(thread)
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        execution_time = time.time() - start_time
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        assert len(results) == 3
        assert execution_time < 20.0  # Should complete within 20 seconds
        
        # All simulations should have completed successfully
        for sim_id, result in results:
            assert len(result['simulation_results']) == 1000
            assert 'statistics' in result
        
        print(f"3 concurrent simulations completed in {execution_time:.2f} seconds")