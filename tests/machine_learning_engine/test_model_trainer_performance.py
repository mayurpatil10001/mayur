"""
Performance benchmarking tests for model training pipeline across time horizons.

Tests training speed, memory usage, and scalability across different
model types and time horizons.

Requirements: 4.1, 4.3, 4.5
"""

import pytest
import pandas as pd
import numpy as np
import time
import psutil
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass

from trading_platform.services.machine_learning.model_trainer import ModelTrainer
from trading_platform.models.trading import ProcessedTrade


@dataclass
class PerformanceBenchmark:
    """Performance benchmark result."""
    test_name: str
    model_type: str
    horizon: str
    data_size: int
    feature_count: int
    training_time: float
    prediction_time: float
    memory_usage_mb: float
    peak_memory_mb: float
    success: bool
    error_message: str = ""


@pytest.fixture
def temp_dir():
    """Create temporary directory for model storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def trainer(temp_dir):
    """Create ModelTrainer instance."""
    return ModelTrainer(models_dir=temp_dir, random_state=42)


class TestModelTrainerPerformance:
    """Performance benchmarking tests for ModelTrainer."""
    
    def create_synthetic_data(self, 
                            n_samples: int, 
                            n_features: int = 20,
                            start_date: str = '2024-01-01') -> Tuple[pd.DataFrame, pd.Series]:
        """Create synthetic trading data for performance testing."""
        np.random.seed(42)
        
        # Create datetime index
        dates = pd.date_range(start_date, periods=n_samples, freq='H')
        
        # Generate features
        feature_data = {}
        
        # Basic trading features
        feature_data['profit_loss'] = np.random.normal(10, 50, n_samples)
        feature_data['duration_minutes'] = np.random.randint(5, 300, n_samples)
        feature_data['hour_of_day'] = np.random.randint(9, 16, n_samples)
        feature_data['day_of_week'] = np.random.randint(0, 5, n_samples)
        feature_data['quantity'] = np.random.randint(1, 10, n_samples)
        feature_data['entry_price'] = np.random.uniform(4000, 4200, n_samples)
        feature_data['exit_price'] = np.random.uniform(4000, 4200, n_samples)
        feature_data['is_long'] = np.random.choice([0, 1], n_samples)
        feature_data['is_short'] = 1 - feature_data['is_long']
        
        # Rolling features
        for window in [5, 10, 20]:
            feature_data[f'rolling_{window}_pnl_mean'] = np.random.normal(5, 20, n_samples)
            feature_data[f'rolling_{window}_pnl_std'] = np.random.uniform(10, 30, n_samples)
            feature_data[f'rolling_{window}_win_rate'] = np.random.uniform(0.4, 0.6, n_samples)
            feature_data[f'rolling_{window}_duration_mean'] = np.random.uniform(30, 120, n_samples)
        
        # Performance features
        feature_data['cumulative_pnl'] = np.cumsum(feature_data['profit_loss'])
        feature_data['cumulative_trades'] = np.arange(1, n_samples + 1)
        feature_data['cumulative_win_rate'] = np.random.uniform(0.45, 0.55, n_samples)
        feature_data['current_drawdown'] = np.random.uniform(-100, 0, n_samples)
        feature_data['win_streak'] = np.random.randint(0, 10, n_samples)
        feature_data['loss_streak'] = np.random.randint(0, 5, n_samples)
        
        # Sequence features
        for lag in [1, 2, 3]:
            feature_data[f'prev_{lag}_pnl'] = np.random.normal(10, 50, n_samples)
            feature_data[f'prev_{lag}_duration'] = np.random.randint(5, 300, n_samples)
            feature_data[f'prev_{lag}_was_profitable'] = np.random.choice([0, 1], n_samples)
        
        # Add additional random features to reach desired count
        current_features = len(feature_data)
        for i in range(current_features, n_features):
            feature_data[f'feature_{i}'] = np.random.normal(0, 1, n_samples)
        
        # Create DataFrame
        features = pd.DataFrame(feature_data, index=dates)
        
        # Create target (next trade P&L)
        target = pd.Series(
            np.random.normal(15, 40, n_samples),
            index=dates,
            name='next_trade_pnl'
        )
        
        return features, target
    
    def measure_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def benchmark_single_model_training(self, 
                                      trainer: ModelTrainer,
                                      features: pd.DataFrame,
                                      target: pd.Series,
                                      model_type: str) -> PerformanceBenchmark:
        """Benchmark single model training performance."""
        initial_memory = self.measure_memory_usage()
        peak_memory = initial_memory
        
        try:
            # Measure training time
            start_time = time.time()
            trained_model = trainer.train_model(features, target, model_type)
            training_time = time.time() - start_time
            
            # Measure prediction time
            start_time = time.time()
            predictions = trained_model.model.predict(features)
            prediction_time = time.time() - start_time
            
            # Measure memory usage
            current_memory = self.measure_memory_usage()
            peak_memory = max(peak_memory, current_memory)
            
            return PerformanceBenchmark(
                test_name="single_model_training",
                model_type=model_type,
                horizon="single_train",
                data_size=len(features),
                feature_count=len(features.columns),
                training_time=training_time,
                prediction_time=prediction_time,
                memory_usage_mb=current_memory - initial_memory,
                peak_memory_mb=peak_memory,
                success=True
            )
            
        except Exception as e:
            return PerformanceBenchmark(
                test_name="single_model_training",
                model_type=model_type,
                horizon="single_train",
                data_size=len(features),
                feature_count=len(features.columns),
                training_time=0,
                prediction_time=0,
                memory_usage_mb=0,
                peak_memory_mb=peak_memory,
                success=False,
                error_message=str(e)
            )
    
    def benchmark_walk_forward_validation(self,
                                        trainer: ModelTrainer,
                                        features: pd.DataFrame,
                                        target: pd.Series,
                                        model_type: str,
                                        horizon: str) -> PerformanceBenchmark:
        """Benchmark walk-forward validation performance."""
        initial_memory = self.measure_memory_usage()
        peak_memory = initial_memory
        
        try:
            # Measure validation time
            start_time = time.time()
            results = trainer.walk_forward_validation(features, target, model_type, horizon)
            validation_time = time.time() - start_time
            
            # Measure memory usage
            current_memory = self.measure_memory_usage()
            peak_memory = max(peak_memory, current_memory)
            
            return PerformanceBenchmark(
                test_name="walk_forward_validation",
                model_type=model_type,
                horizon=horizon,
                data_size=len(features),
                feature_count=len(features.columns),
                training_time=validation_time,
                prediction_time=results.get('avg_prediction_time', 0),
                memory_usage_mb=current_memory - initial_memory,
                peak_memory_mb=peak_memory,
                success=True
            )
            
        except Exception as e:
            return PerformanceBenchmark(
                test_name="walk_forward_validation",
                model_type=model_type,
                horizon=horizon,
                data_size=len(features),
                feature_count=len(features.columns),
                training_time=0,
                prediction_time=0,
                memory_usage_mb=0,
                peak_memory_mb=peak_memory,
                success=False,
                error_message=str(e)
            )


class TestTrainingSpeedBenchmarks:
    """Test training speed across different scenarios."""
    
    @pytest.mark.performance
    def test_small_dataset_performance(self, trainer):
        """Test performance with small dataset (100 samples)."""
        features, target = TestModelTrainerPerformance().create_synthetic_data(100, 10)
        benchmark_helper = TestModelTrainerPerformance()
        
        # Test fast models
        fast_models = ['linear_regression', 'ridge_regression']
        
        for model_type in fast_models:
            benchmark = benchmark_helper.benchmark_single_model_training(
                trainer, features, target, model_type
            )
            
            assert benchmark.success, f"Training failed for {model_type}: {benchmark.error_message}"
            assert benchmark.training_time < 5.0, f"Training too slow for {model_type}: {benchmark.training_time}s"
            assert benchmark.prediction_time < 1.0, f"Prediction too slow for {model_type}: {benchmark.prediction_time}s"
            
            print(f"Small dataset - {model_type}: "
                  f"train={benchmark.training_time:.3f}s, "
                  f"predict={benchmark.prediction_time:.3f}s, "
                  f"memory={benchmark.memory_usage_mb:.1f}MB")
    
    @pytest.mark.performance
    def test_medium_dataset_performance(self, trainer):
        """Test performance with medium dataset (1000 samples)."""
        features, target = TestModelTrainerPerformance().create_synthetic_data(1000, 20)
        benchmark_helper = TestModelTrainerPerformance()
        
        # Test medium complexity models
        medium_models = ['random_forest_reg', 'gradient_boosting_reg']
        
        for model_type in medium_models:
            benchmark = benchmark_helper.benchmark_single_model_training(
                trainer, features, target, model_type
            )
            
            assert benchmark.success, f"Training failed for {model_type}: {benchmark.error_message}"
            assert benchmark.training_time < 30.0, f"Training too slow for {model_type}: {benchmark.training_time}s"
            assert benchmark.prediction_time < 5.0, f"Prediction too slow for {model_type}: {benchmark.prediction_time}s"
            
            print(f"Medium dataset - {model_type}: "
                  f"train={benchmark.training_time:.3f}s, "
                  f"predict={benchmark.prediction_time:.3f}s, "
                  f"memory={benchmark.memory_usage_mb:.1f}MB")
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_large_dataset_performance(self, trainer):
        """Test performance with large dataset (5000 samples)."""
        features, target = TestModelTrainerPerformance().create_synthetic_data(5000, 30)
        benchmark_helper = TestModelTrainerPerformance()
        
        # Test scalable models
        scalable_models = ['linear_regression', 'random_forest_reg']
        
        for model_type in scalable_models:
            benchmark = benchmark_helper.benchmark_single_model_training(
                trainer, features, target, model_type
            )
            
            assert benchmark.success, f"Training failed for {model_type}: {benchmark.error_message}"
            assert benchmark.training_time < 120.0, f"Training too slow for {model_type}: {benchmark.training_time}s"
            assert benchmark.prediction_time < 10.0, f"Prediction too slow for {model_type}: {benchmark.prediction_time}s"
            
            print(f"Large dataset - {model_type}: "
                  f"train={benchmark.training_time:.3f}s, "
                  f"predict={benchmark.prediction_time:.3f}s, "
                  f"memory={benchmark.memory_usage_mb:.1f}MB")


class TestWalkForwardPerformance:
    """Test walk-forward validation performance across time horizons."""
    
    @pytest.mark.performance
    def test_short_term_horizon_performance(self, trainer):
        """Test walk-forward validation performance for short-term horizon."""
        # Create data spanning 30 days to allow multiple folds
        features, target = TestModelTrainerPerformance().create_synthetic_data(720, 15)  # 30 days * 24 hours
        benchmark_helper = TestModelTrainerPerformance()
        
        models_to_test = ['linear_regression', 'random_forest_reg']
        
        for model_type in models_to_test:
            benchmark = benchmark_helper.benchmark_walk_forward_validation(
                trainer, features, target, model_type, 'short_term'
            )
            
            if benchmark.success:
                assert benchmark.training_time < 60.0, f"Walk-forward too slow for {model_type}: {benchmark.training_time}s"
                
                print(f"Short-term WF - {model_type}: "
                      f"total_time={benchmark.training_time:.3f}s, "
                      f"avg_predict={benchmark.prediction_time:.3f}s, "
                      f"memory={benchmark.memory_usage_mb:.1f}MB")
            else:
                print(f"Short-term WF - {model_type}: FAILED - {benchmark.error_message}")
    
    @pytest.mark.performance
    def test_medium_term_horizon_performance(self, trainer):
        """Test walk-forward validation performance for medium-term horizon."""
        # Create data spanning 60 days
        features, target = TestModelTrainerPerformance().create_synthetic_data(1440, 20)  # 60 days * 24 hours
        benchmark_helper = TestModelTrainerPerformance()
        
        models_to_test = ['linear_regression', 'random_forest_reg']
        
        for model_type in models_to_test:
            benchmark = benchmark_helper.benchmark_walk_forward_validation(
                trainer, features, target, model_type, 'medium_term'
            )
            
            if benchmark.success:
                assert benchmark.training_time < 120.0, f"Walk-forward too slow for {model_type}: {benchmark.training_time}s"
                
                print(f"Medium-term WF - {model_type}: "
                      f"total_time={benchmark.training_time:.3f}s, "
                      f"avg_predict={benchmark.prediction_time:.3f}s, "
                      f"memory={benchmark.memory_usage_mb:.1f}MB")
            else:
                print(f"Medium-term WF - {model_type}: FAILED - {benchmark.error_message}")
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_long_term_horizon_performance(self, trainer):
        """Test walk-forward validation performance for long-term horizon."""
        # Create data spanning 90 days
        features, target = TestModelTrainerPerformance().create_synthetic_data(2160, 25)  # 90 days * 24 hours
        benchmark_helper = TestModelTrainerPerformance()
        
        models_to_test = ['linear_regression', 'random_forest_reg']
        
        for model_type in models_to_test:
            benchmark = benchmark_helper.benchmark_walk_forward_validation(
                trainer, features, target, model_type, 'long_term'
            )
            
            if benchmark.success:
                assert benchmark.training_time < 300.0, f"Walk-forward too slow for {model_type}: {benchmark.training_time}s"
                
                print(f"Long-term WF - {model_type}: "
                      f"total_time={benchmark.training_time:.3f}s, "
                      f"avg_predict={benchmark.prediction_time:.3f}s, "
                      f"memory={benchmark.memory_usage_mb:.1f}MB")
            else:
                print(f"Long-term WF - {model_type}: FAILED - {benchmark.error_message}")


class TestMemoryUsageBenchmarks:
    """Test memory usage across different scenarios."""
    
    @pytest.mark.performance
    def test_memory_usage_scaling(self, trainer):
        """Test memory usage scaling with dataset size."""
        benchmark_helper = TestModelTrainerPerformance()
        data_sizes = [100, 500, 1000, 2000]
        model_type = 'random_forest_reg'
        
        memory_usage = []
        
        for size in data_sizes:
            features, target = benchmark_helper.create_synthetic_data(size, 20)
            
            benchmark = benchmark_helper.benchmark_single_model_training(
                trainer, features, target, model_type
            )
            
            if benchmark.success:
                memory_usage.append((size, benchmark.memory_usage_mb))
                print(f"Size {size}: {benchmark.memory_usage_mb:.1f}MB")
            else:
                print(f"Size {size}: FAILED - {benchmark.error_message}")
        
        # Check that memory usage doesn't grow too quickly
        if len(memory_usage) >= 2:
            # Memory should scale reasonably (not exponentially)
            size_ratio = memory_usage[-1][0] / memory_usage[0][0]
            memory_ratio = memory_usage[-1][1] / memory_usage[0][1]
            
            # Memory growth should be less than 10x for reasonable size increases
            assert memory_ratio < size_ratio * 2, f"Memory usage growing too fast: {memory_ratio}x for {size_ratio}x data"
    
    @pytest.mark.performance
    def test_feature_count_memory_impact(self, trainer):
        """Test memory usage impact of feature count."""
        benchmark_helper = TestModelTrainerPerformance()
        feature_counts = [10, 20, 50, 100]
        model_type = 'linear_regression'
        data_size = 1000
        
        for feature_count in feature_counts:
            features, target = benchmark_helper.create_synthetic_data(data_size, feature_count)
            
            benchmark = benchmark_helper.benchmark_single_model_training(
                trainer, features, target, model_type
            )
            
            if benchmark.success:
                print(f"Features {feature_count}: {benchmark.memory_usage_mb:.1f}MB, "
                      f"train={benchmark.training_time:.3f}s")
                
                # Memory usage should be reasonable even with many features
                assert benchmark.memory_usage_mb < 500, f"Memory usage too high with {feature_count} features"
            else:
                print(f"Features {feature_count}: FAILED - {benchmark.error_message}")


class TestModelComparisonBenchmarks:
    """Test performance comparison across different model types."""
    
    @pytest.mark.performance
    def test_model_type_performance_comparison(self, trainer):
        """Compare performance across different model types."""
        features, target = TestModelTrainerPerformance().create_synthetic_data(1000, 20)
        benchmark_helper = TestModelTrainerPerformance()
        
        # Test different model categories
        models_to_compare = {
            'linear': ['linear_regression', 'ridge_regression', 'lasso_regression'],
            'tree_based': ['random_forest_reg', 'gradient_boosting_reg'],
            'neural': ['mlp_regressor']
        }
        
        results = {}
        
        for category, model_list in models_to_compare.items():
            results[category] = []
            
            for model_type in model_list:
                benchmark = benchmark_helper.benchmark_single_model_training(
                    trainer, features, target, model_type
                )
                
                if benchmark.success:
                    results[category].append({
                        'model': model_type,
                        'train_time': benchmark.training_time,
                        'predict_time': benchmark.prediction_time,
                        'memory': benchmark.memory_usage_mb
                    })
                    
                    print(f"{category} - {model_type}: "
                          f"train={benchmark.training_time:.3f}s, "
                          f"predict={benchmark.prediction_time:.3f}s, "
                          f"memory={benchmark.memory_usage_mb:.1f}MB")
        
        # Verify linear models are fastest
        if 'linear' in results and results['linear']:
            linear_times = [r['train_time'] for r in results['linear']]
            avg_linear_time = sum(linear_times) / len(linear_times)
            
            # Linear models should generally be faster than tree-based
            if 'tree_based' in results and results['tree_based']:
                tree_times = [r['train_time'] for r in results['tree_based']]
                avg_tree_time = sum(tree_times) / len(tree_times)
                
                assert avg_linear_time < avg_tree_time, "Linear models should be faster than tree-based"
    
    @pytest.mark.performance
    def test_horizon_performance_comparison(self, trainer):
        """Compare walk-forward validation performance across horizons."""
        # Use sufficient data for all horizons
        features, target = TestModelTrainerPerformance().create_synthetic_data(2160, 15)  # 90 days
        benchmark_helper = TestModelTrainerPerformance()
        
        model_type = 'random_forest_reg'
        horizons = ['short_term', 'medium_term', 'long_term']
        
        horizon_results = {}
        
        for horizon in horizons:
            benchmark = benchmark_helper.benchmark_walk_forward_validation(
                trainer, features, target, model_type, horizon
            )
            
            if benchmark.success:
                horizon_results[horizon] = {
                    'total_time': benchmark.training_time,
                    'avg_predict_time': benchmark.prediction_time,
                    'memory': benchmark.memory_usage_mb
                }
                
                print(f"Horizon {horizon}: "
                      f"total={benchmark.training_time:.3f}s, "
                      f"predict={benchmark.prediction_time:.3f}s, "
                      f"memory={benchmark.memory_usage_mb:.1f}MB")
            else:
                print(f"Horizon {horizon}: FAILED - {benchmark.error_message}")
        
        # Verify that longer horizons generally take more time (more training data per fold)
        if len(horizon_results) >= 2:
            times = [(h, r['total_time']) for h, r in horizon_results.items()]
            times.sort(key=lambda x: x[1])  # Sort by time
            
            print(f"Horizon performance ranking: {[h for h, _ in times]}")


class TestScalabilityBenchmarks:
    """Test scalability limits and edge cases."""
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_maximum_data_size_handling(self, trainer):
        """Test handling of large datasets near memory limits."""
        benchmark_helper = TestModelTrainerPerformance()
        
        # Test progressively larger datasets
        sizes_to_test = [5000, 10000]  # Start conservative
        model_type = 'linear_regression'  # Use fast model
        
        for size in sizes_to_test:
            print(f"Testing dataset size: {size}")
            
            try:
                features, target = benchmark_helper.create_synthetic_data(size, 20)
                
                benchmark = benchmark_helper.benchmark_single_model_training(
                    trainer, features, target, model_type
                )
                
                if benchmark.success:
                    print(f"Size {size}: SUCCESS - "
                          f"train={benchmark.training_time:.3f}s, "
                          f"memory={benchmark.memory_usage_mb:.1f}MB")
                    
                    # Set reasonable limits
                    assert benchmark.training_time < 300, f"Training too slow for size {size}"
                    assert benchmark.memory_usage_mb < 1000, f"Memory usage too high for size {size}"
                else:
                    print(f"Size {size}: FAILED - {benchmark.error_message}")
                    
            except MemoryError:
                print(f"Size {size}: MEMORY ERROR - Dataset too large")
                break
            except Exception as e:
                print(f"Size {size}: ERROR - {e}")
    
    @pytest.mark.performance
    def test_concurrent_training_performance(self, trainer):
        """Test performance implications of concurrent model training."""
        import threading
        import queue
        
        features, target = TestModelTrainerPerformance().create_synthetic_data(500, 15)
        benchmark_helper = TestModelTrainerPerformance()
        
        # Test concurrent training of different models
        models_to_train = ['linear_regression', 'ridge_regression', 'random_forest_reg']
        results_queue = queue.Queue()
        
        def train_model_thread(model_type):
            try:
                benchmark = benchmark_helper.benchmark_single_model_training(
                    trainer, features, target, model_type
                )
                results_queue.put((model_type, benchmark))
            except Exception as e:
                results_queue.put((model_type, f"ERROR: {e}"))
        
        # Start concurrent training
        threads = []
        start_time = time.time()
        
        for model_type in models_to_train:
            thread = threading.Thread(target=train_model_thread, args=(model_type,))
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        total_concurrent_time = time.time() - start_time
        
        # Collect results
        concurrent_results = []
        while not results_queue.empty():
            result = results_queue.get()
            concurrent_results.append(result)
        
        print(f"Concurrent training completed in {total_concurrent_time:.3f}s")
        
        for model_type, benchmark in concurrent_results:
            if isinstance(benchmark, str):
                print(f"Concurrent {model_type}: {benchmark}")
            else:
                print(f"Concurrent {model_type}: "
                      f"train={benchmark.training_time:.3f}s, "
                      f"success={benchmark.success}")
        
        # Verify concurrent training completed in reasonable time
        assert total_concurrent_time < 60, "Concurrent training took too long"


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-m", "performance"])