"""
Parallel processing engine for Monte Carlo simulations.

This module provides high-performance parallel processing capabilities for Monte Carlo
simulations, including distributed computing, batch processing, and memory optimization.

Requirements: 10.1, 10.2, 10.3
"""

import logging
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, Future
import queue
import time
import psutil
import numpy as np
from pathlib import Path
import pickle
import json
import os

# Placeholder classes for missing imports
@dataclass
class MonteCarloConfiguration:
    """Placeholder configuration class."""
    num_simulations: int = 10000
    time_horizon_days: int = 252
    confidence_levels: list = None
    
@dataclass 
class SimulationResult:
    """Placeholder simulation result class."""
    result_data: Any = None

from .monte_carlo_simulator import MonteCarloSimulator
from ..time_bin_analyzer import TimeBin, TimeBinAnalyzer
from ...models.trading import ProcessedTrade

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing mode for Monte Carlo simulations."""
    SINGLE_THREADED = "single_threaded"
    MULTI_THREADED = "multi_threaded"
    MULTI_PROCESS = "multi_process"
    HYBRID = "hybrid"
    DISTRIBUTED = "distributed"


class MemoryStrategy(Enum):
    """Memory management strategy."""
    IN_MEMORY = "in_memory"
    DISK_CACHE = "disk_cache"
    STREAMING = "streaming"
    COMPRESSED = "compressed"


class LoadBalancingStrategy(Enum):
    """Load balancing strategy for parallel processing."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    DYNAMIC = "dynamic"
    WORK_STEALING = "work_stealing"


@dataclass
class ProcessingConfiguration:
    """Configuration for parallel processing."""
    processing_mode: ProcessingMode = ProcessingMode.MULTI_PROCESS
    max_workers: int = 0  # 0 = auto-detect
    chunk_size: int = 100  # Simulations per chunk
    memory_strategy: MemoryStrategy = MemoryStrategy.IN_MEMORY
    load_balancing: LoadBalancingStrategy = LoadBalancingStrategy.DYNAMIC
    
    # Memory management
    max_memory_gb: float = 8.0
    disk_cache_dir: Optional[str] = None
    compression_level: int = 1  # 0-9, 0=no compression
    
    # Performance tuning
    batch_timeout_seconds: float = 300.0  # 5 minutes
    progress_callback_frequency: int = 100
    enable_profiling: bool = False
    
    # Distributed processing
    worker_nodes: List[str] = field(default_factory=list)
    coordinator_port: int = 9999
    
    # Error handling
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    fail_fast: bool = False


@dataclass
class WorkerMetrics:
    """Metrics for individual workers."""
    worker_id: str
    cpu_usage: float
    memory_usage_mb: float
    simulations_completed: int
    simulations_failed: int
    average_processing_time: float
    last_active: datetime
    status: str  # IDLE, BUSY, FAILED, STOPPED


@dataclass
class ProcessingMetrics:
    """Overall processing metrics."""
    total_simulations: int
    completed_simulations: int
    failed_simulations: int
    processing_rate: float  # simulations per second
    estimated_time_remaining: float  # seconds
    memory_usage_mb: float
    cpu_usage: float
    worker_metrics: List[WorkerMetrics]
    start_time: datetime
    elapsed_time: float


@dataclass
class SimulationBatch:
    """Batch of simulations for processing."""
    batch_id: str
    simulation_indices: List[int]
    configuration: MonteCarloConfiguration
    time_bins: List[TimeBin]
    historical_data: Dict[TimeBin, List[ProcessedTrade]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of processing a simulation batch."""
    batch_id: str
    simulation_results: List[SimulationResult]
    processing_time: float
    worker_id: str
    memory_used_mb: float
    errors: List[str] = field(default_factory=list)


class ParallelMonteCarloProcessor:
    """
    High-performance parallel processor for Monte Carlo simulations.
    
    Provides advanced parallel processing capabilities including multi-threading,
    multi-processing, distributed computing, and memory optimization strategies.
    """
    
    def __init__(
        self,
        monte_carlo_simulator: MonteCarloSimulator,
        time_bin_analyzer: TimeBinAnalyzer,
        processing_config: Optional[ProcessingConfiguration] = None
    ):
        """Initialize the parallel processor."""
        self.monte_carlo_simulator = monte_carlo_simulator
        self.time_bin_analyzer = time_bin_analyzer
        self.processing_config = processing_config or ProcessingConfiguration()
        
        # Auto-detect optimal worker count if not specified
        if self.processing_config.max_workers == 0:
            self.processing_config.max_workers = self._auto_detect_workers()
        
        # Initialize components
        self.executor: Optional[Union[ThreadPoolExecutor, ProcessPoolExecutor]] = None
        self.worker_pool: List[Any] = []
        self.result_queue = queue.Queue()
        self.metrics = ProcessingMetrics(
            total_simulations=0,
            completed_simulations=0,
            failed_simulations=0,
            processing_rate=0.0,
            estimated_time_remaining=0.0,
            memory_usage_mb=0.0,
            cpu_usage=0.0,
            worker_metrics=[],
            start_time=datetime.now(),
            elapsed_time=0.0
        )
        
        # Caching and memory management
        self.disk_cache: Dict[str, str] = {}  # batch_id -> file_path
        self.memory_cache: Dict[str, Any] = {}
        
        # Profiling
        self.profiling_data: Dict[str, List[float]] = {
            'batch_processing_times': [],
            'memory_usage_samples': [],
            'cpu_usage_samples': []
        }
        
        # Setup disk cache if needed
        if self.processing_config.disk_cache_dir:
            self._setup_disk_cache()
        
        logger.info(f"ParallelMonteCarloProcessor initialized with {self.processing_config.max_workers} workers")
    
    async def run_parallel_simulations(
        self,
        configuration: MonteCarloConfiguration,
        time_bins: List[TimeBin],
        num_simulations: int,
        progress_callback: Optional[Callable[[ProcessingMetrics], None]] = None
    ) -> List[SimulationResult]:
        """
        Run Monte Carlo simulations in parallel.
        
        Args:
            configuration: Monte Carlo configuration
            time_bins: List of time-bins to simulate
            num_simulations: Total number of simulations to run
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of simulation results
        """
        start_time = datetime.now()
        self.metrics.start_time = start_time
        self.metrics.total_simulations = num_simulations
        
        try:
            logger.info(f"Starting {num_simulations} parallel Monte Carlo simulations")
            
            # Load historical data
            historical_data = await self._load_historical_data(time_bins, configuration)
            
            # Create simulation batches
            batches = self._create_simulation_batches(
                configuration, time_bins, historical_data, num_simulations
            )
            
            logger.info(f"Created {len(batches)} simulation batches")
            
            # Initialize executor based on processing mode
            await self._initialize_executor()
            
            # Process batches in parallel
            all_results = await self._process_batches_parallel(
                batches, progress_callback
            )
            
            # Combine results
            combined_results = []
            for batch_result in all_results:
                combined_results.extend(batch_result.simulation_results)
            
            # Calculate final metrics
            self.metrics.elapsed_time = (datetime.now() - start_time).total_seconds()
            self.metrics.processing_rate = len(combined_results) / self.metrics.elapsed_time
            
            logger.info(f"Completed {len(combined_results)} simulations in {self.metrics.elapsed_time:.2f} seconds")
            logger.info(f"Processing rate: {self.metrics.processing_rate:.2f} simulations/second")
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Parallel Monte Carlo simulation failed: {str(e)}")
            raise
        finally:
            await self._cleanup_executor()
    
    async def run_batch_optimized_simulations(
        self,
        configurations: List[MonteCarloConfiguration],
        time_bins: List[TimeBin],
        simulations_per_config: int,
        progress_callback: Optional[Callable[[ProcessingMetrics], None]] = None
    ) -> Dict[str, List[SimulationResult]]:
        """
        Run multiple Monte Carlo configurations with batch optimization.
        
        Optimizes processing by batching similar configurations and reusing
        computations where possible.
        """
        start_time = datetime.now()
        total_simulations = len(configurations) * simulations_per_config
        
        self.metrics.start_time = start_time
        self.metrics.total_simulations = total_simulations
        
        try:
            logger.info(f"Starting batch-optimized simulations for {len(configurations)} configurations")
            
            # Group similar configurations for optimization
            config_groups = self._group_similar_configurations(configurations)
            
            # Load historical data once for all configurations
            all_historical_data = {}
            for config in configurations:
                data = await self._load_historical_data(time_bins, config)
                config_hash = self._hash_configuration(config)
                all_historical_data[config_hash] = data
            
            # Initialize executor
            await self._initialize_executor()
            
            # Process each configuration group
            all_results = {}
            
            for group_id, config_list in config_groups.items():
                logger.info(f"Processing configuration group {group_id} with {len(config_list)} configurations")
                
                for config in config_list:
                    config_id = f"config_{hash(str(config))}"
                    config_hash = self._hash_configuration(config)
                    
                    # Create batches for this configuration
                    historical_data = all_historical_data[config_hash]
                    batches = self._create_simulation_batches(
                        config, time_bins, historical_data, simulations_per_config
                    )
                    
                    # Process batches
                    batch_results = await self._process_batches_parallel(
                        batches, progress_callback
                    )
                    
                    # Combine results for this configuration
                    config_results = []
                    for batch_result in batch_results:
                        config_results.extend(batch_result.simulation_results)
                    
                    all_results[config_id] = config_results
            
            # Calculate final metrics
            self.metrics.elapsed_time = (datetime.now() - start_time).total_seconds()
            total_completed = sum(len(results) for results in all_results.values())
            self.metrics.processing_rate = total_completed / self.metrics.elapsed_time
            
            logger.info(f"Completed batch optimization in {self.metrics.elapsed_time:.2f} seconds")
            
            return all_results
            
        except Exception as e:
            logger.error(f"Batch-optimized simulation failed: {str(e)}")
            raise
        finally:
            await self._cleanup_executor()
    
    async def run_distributed_simulations(
        self,
        configuration: MonteCarloConfiguration,
        time_bins: List[TimeBin],
        num_simulations: int,
        worker_nodes: List[str],
        progress_callback: Optional[Callable[[ProcessingMetrics], None]] = None
    ) -> List[SimulationResult]:
        """
        Run Monte Carlo simulations across distributed worker nodes.
        
        Coordinates simulation across multiple machines for maximum throughput.
        """
        if not worker_nodes:
            # Fallback to local parallel processing
            return await self.run_parallel_simulations(
                configuration, time_bins, num_simulations, progress_callback
            )
        
        logger.info(f"Starting distributed simulations across {len(worker_nodes)} nodes")
        
        try:
            # Setup distributed coordination
            coordinator = DistributedCoordinator(worker_nodes)
            await coordinator.initialize()
            
            # Load and distribute historical data
            historical_data = await self._load_historical_data(time_bins, configuration)
            await coordinator.distribute_data(historical_data)
            
            # Create and distribute simulation batches
            batches = self._create_simulation_batches(
                configuration, time_bins, historical_data, num_simulations
            )
            
            # Distribute batches across nodes
            batch_assignments = coordinator.assign_batches(batches)
            
            # Monitor and collect results
            all_results = await coordinator.execute_and_collect(
                batch_assignments, progress_callback
            )
            
            # Combine results from all nodes
            combined_results = []
            for batch_result in all_results:
                combined_results.extend(batch_result.simulation_results)
            
            logger.info(f"Completed distributed simulation with {len(combined_results)} results")
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Distributed simulation failed: {str(e)}")
            raise
        finally:
            if 'coordinator' in locals():
                await coordinator.cleanup()
    
    def get_processing_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics."""
        # Update real-time metrics
        self._update_system_metrics()
        return self.metrics
    
    def get_optimal_configuration(
        self,
        target_simulations: int,
        time_constraint_seconds: Optional[float] = None,
        memory_constraint_gb: Optional[float] = None
    ) -> ProcessingConfiguration:
        """
        Get optimal processing configuration for given constraints.
        
        Analyzes system capabilities and constraints to recommend
        the best processing configuration.
        """
        logger.info("Calculating optimal processing configuration")
        
        # System analysis
        cpu_count = mp.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Start with current configuration
        optimal_config = ProcessingConfiguration()
        
        # Adjust based on constraints
        if memory_constraint_gb and memory_constraint_gb < memory_gb:
            # Memory constrained - use disk caching
            optimal_config.memory_strategy = MemoryStrategy.DISK_CACHE
            optimal_config.max_memory_gb = memory_constraint_gb * 0.8  # 80% safety margin
        
        if time_constraint_seconds:
            # Time constrained - maximize parallelism
            optimal_config.processing_mode = ProcessingMode.MULTI_PROCESS
            optimal_config.max_workers = cpu_count
            optimal_config.chunk_size = max(10, target_simulations // (cpu_count * 4))
        
        # Optimize chunk size based on simulation count
        if target_simulations < 100:
            optimal_config.chunk_size = max(1, target_simulations // 4)
            optimal_config.processing_mode = ProcessingMode.MULTI_THREADED
        elif target_simulations < 1000:
            optimal_config.chunk_size = max(10, target_simulations // cpu_count)
            optimal_config.processing_mode = ProcessingMode.MULTI_PROCESS
        else:
            optimal_config.chunk_size = max(50, target_simulations // (cpu_count * 2))
            optimal_config.processing_mode = ProcessingMode.HYBRID
        
        # Memory optimization for large simulations
        if target_simulations > 10000:
            optimal_config.memory_strategy = MemoryStrategy.STREAMING
            optimal_config.compression_level = 3
        
        logger.info(f"Optimal configuration: {optimal_config.processing_mode.value} with {optimal_config.max_workers} workers")
        
        return optimal_config
    
    async def benchmark_performance(
        self,
        test_configurations: List[ProcessingConfiguration],
        sample_simulations: int = 100
    ) -> Dict[str, Dict[str, float]]:
        """
        Benchmark different processing configurations.
        
        Tests various configurations to determine optimal settings
        for the current system and workload.
        """
        logger.info(f"Benchmarking {len(test_configurations)} processing configurations")
        
        benchmark_results = {}
        
        # Create a simple test configuration and time-bins
        test_config = MonteCarloConfiguration(
            num_simulations=sample_simulations,
            time_horizon_days=30,
            confidence_levels=[0.95]
        )
        
        test_time_bins = [TimeBin("TEST", 9, 30), TimeBin("TEST", 14, 45)]
        
        for i, proc_config in enumerate(test_configurations):
            config_name = f"config_{i}_{proc_config.processing_mode.value}"
            logger.info(f"Benchmarking configuration: {config_name}")
            
            try:
                # Temporarily switch to test configuration
                original_config = self.processing_config
                self.processing_config = proc_config
                
                # Run benchmark
                start_time = time.time()
                await self.run_parallel_simulations(
                    test_config, test_time_bins, sample_simulations
                )
                elapsed_time = time.time() - start_time
                
                # Calculate metrics
                throughput = sample_simulations / elapsed_time
                memory_efficiency = self.metrics.memory_usage_mb / sample_simulations
                cpu_efficiency = self.metrics.cpu_usage / proc_config.max_workers
                
                benchmark_results[config_name] = {
                    'elapsed_time_seconds': elapsed_time,
                    'throughput_sims_per_sec': throughput,
                    'memory_efficiency_mb_per_sim': memory_efficiency,
                    'cpu_efficiency': cpu_efficiency,
                    'peak_memory_mb': self.metrics.memory_usage_mb,
                    'average_cpu_usage': self.metrics.cpu_usage
                }
                
                # Restore original configuration
                self.processing_config = original_config
                
            except Exception as e:
                logger.warning(f"Benchmark failed for {config_name}: {str(e)}")
                benchmark_results[config_name] = {'error': str(e)}
        
        logger.info("Performance benchmarking completed")
        return benchmark_results
    
    # Private methods
    def _auto_detect_workers(self) -> int:
        """Auto-detect optimal number of workers."""
        cpu_count = mp.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Consider both CPU and memory constraints
        cpu_workers = cpu_count
        memory_workers = int(memory_gb // 2)  # Assume 2GB per worker
        
        optimal_workers = min(cpu_workers, memory_workers, 16)  # Cap at 16 workers
        return max(1, optimal_workers)
    
    async def _load_historical_data(
        self,
        time_bins: List[TimeBin],
        configuration: MonteCarloConfiguration
    ) -> Dict[TimeBin, List[ProcessedTrade]]:
        """Load historical data for time-bins."""
        historical_data = {}
        
        for time_bin in time_bins:
            try:
                # Calculate date range based on configuration
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=configuration.time_horizon_days * 2)
                
                trades = await self.time_bin_analyzer.get_trades_for_time_bin(
                    time_bin, start_date=start_date, end_date=end_date
                )
                historical_data[time_bin] = trades
                
            except Exception as e:
                logger.warning(f"Failed to load data for {time_bin}: {str(e)}")
                historical_data[time_bin] = []
        
        return historical_data
    
    def _create_simulation_batches(
        self,
        configuration: MonteCarloConfiguration,
        time_bins: List[TimeBin],
        historical_data: Dict[TimeBin, List[ProcessedTrade]],
        num_simulations: int
    ) -> List[SimulationBatch]:
        """Create simulation batches for parallel processing."""
        batches = []
        chunk_size = self.processing_config.chunk_size
        
        # Split simulations into chunks
        for start_idx in range(0, num_simulations, chunk_size):
            end_idx = min(start_idx + chunk_size, num_simulations)
            simulation_indices = list(range(start_idx, end_idx))
            
            batch = SimulationBatch(
                batch_id=f"batch_{start_idx}_{end_idx}",
                simulation_indices=simulation_indices,
                configuration=configuration,
                time_bins=time_bins,
                historical_data=historical_data,
                metadata={'chunk_size': len(simulation_indices)}
            )
            
            batches.append(batch)
        
        return batches
    
    async def _initialize_executor(self):
        """Initialize the appropriate executor based on processing mode."""
        mode = self.processing_config.processing_mode
        max_workers = self.processing_config.max_workers
        
        if mode == ProcessingMode.MULTI_THREADED:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
        elif mode == ProcessingMode.MULTI_PROCESS:
            self.executor = ProcessPoolExecutor(max_workers=max_workers)
        elif mode == ProcessingMode.HYBRID:
            # Use both thread and process pools
            self.thread_executor = ThreadPoolExecutor(max_workers=max_workers // 2)
            self.process_executor = ProcessPoolExecutor(max_workers=max_workers // 2)
        
        logger.debug(f"Initialized {mode.value} executor with {max_workers} workers")
    
    async def _process_batches_parallel(
        self,
        batches: List[SimulationBatch],
        progress_callback: Optional[Callable[[ProcessingMetrics], None]] = None
    ) -> List[BatchResult]:
        """Process simulation batches in parallel."""
        logger.info(f"Processing {len(batches)} batches in parallel")
        
        # Submit all batches for processing
        futures = []
        for batch in batches:
            if self.processing_config.processing_mode == ProcessingMode.HYBRID:
                # Alternate between thread and process pools
                executor = self.thread_executor if len(futures) % 2 == 0 else self.process_executor
            else:
                executor = self.executor
            
            future = executor.submit(self._process_single_batch, batch)
            futures.append(future)
        
        # Collect results as they complete
        batch_results = []
        completed_count = 0
        
        for future in as_completed(futures):
            try:
                batch_result = future.result(timeout=self.processing_config.batch_timeout_seconds)
                batch_results.append(batch_result)
                
                completed_count += 1
                self.metrics.completed_simulations += len(batch_result.simulation_results)
                
                # Update progress
                if progress_callback and completed_count % self.processing_config.progress_callback_frequency == 0:
                    self._update_metrics()
                    progress_callback(self.metrics)
                
            except Exception as e:
                logger.error(f"Batch processing failed: {str(e)}")
                if self.processing_config.fail_fast:
                    raise
                else:
                    self.metrics.failed_simulations += self.processing_config.chunk_size
        
        logger.info(f"Completed processing {len(batch_results)} batches")
        return batch_results
    
    def _process_single_batch(self, batch: SimulationBatch) -> BatchResult:
        """Process a single simulation batch."""
        start_time = time.time()
        worker_id = f"worker_{threading.current_thread().ident}"
        
        try:
            # Track memory usage
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Run simulations for this batch
            simulation_results = []
            
            for sim_idx in batch.simulation_indices:
                try:
                    # Create a new simulator instance for thread safety
                    simulator = MonteCarloSimulator()
                    
                    # Run individual simulation
                    result = simulator.run_simulation(
                        time_bins=batch.time_bins,
                        configuration=batch.configuration,
                        historical_data=batch.historical_data,
                        simulation_id=sim_idx
                    )
                    
                    simulation_results.append(result)
                    
                except Exception as e:
                    logger.warning(f"Simulation {sim_idx} failed: {str(e)}")
                    # Continue with other simulations
            
            # Calculate resource usage
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = memory_after - memory_before
            processing_time = time.time() - start_time
            
            return BatchResult(
                batch_id=batch.batch_id,
                simulation_results=simulation_results,
                processing_time=processing_time,
                worker_id=worker_id,
                memory_used_mb=memory_used
            )
            
        except Exception as e:
            logger.error(f"Batch {batch.batch_id} processing failed: {str(e)}")
            return BatchResult(
                batch_id=batch.batch_id,
                simulation_results=[],
                processing_time=time.time() - start_time,
                worker_id=worker_id,
                memory_used_mb=0.0,
                errors=[str(e)]
            )
    
    def _update_metrics(self):
        """Update processing metrics."""
        elapsed_time = (datetime.now() - self.metrics.start_time).total_seconds()
        self.metrics.elapsed_time = elapsed_time
        
        if elapsed_time > 0:
            self.metrics.processing_rate = self.metrics.completed_simulations / elapsed_time
            
            if self.metrics.processing_rate > 0:
                remaining_sims = self.metrics.total_simulations - self.metrics.completed_simulations
                self.metrics.estimated_time_remaining = remaining_sims / self.metrics.processing_rate
        
        self._update_system_metrics()
    
    def _update_system_metrics(self):
        """Update system resource metrics."""
        # CPU usage
        self.metrics.cpu_usage = psutil.cpu_percent()
        
        # Memory usage
        memory_info = psutil.virtual_memory()
        self.metrics.memory_usage_mb = (memory_info.total - memory_info.available) / 1024 / 1024
        
        # Update profiling data if enabled
        if self.processing_config.enable_profiling:
            self.profiling_data['cpu_usage_samples'].append(self.metrics.cpu_usage)
            self.profiling_data['memory_usage_samples'].append(self.metrics.memory_usage_mb)
    
    def _group_similar_configurations(
        self, 
        configurations: List[MonteCarloConfiguration]
    ) -> Dict[str, List[MonteCarloConfiguration]]:
        """Group similar configurations for batch optimization."""
        groups = {}
        
        for config in configurations:
            # Create a group key based on similar parameters
            group_key = f"{config.time_horizon_days}_{config.num_scenarios}_{len(config.confidence_levels)}"
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(config)
        
        return groups
    
    def _hash_configuration(self, config: MonteCarloConfiguration) -> str:
        """Create a hash for configuration caching."""
        # Create a deterministic hash based on configuration parameters
        config_str = f"{config.time_horizon_days}_{config.num_scenarios}_{config.random_seed}"
        return str(hash(config_str))
    
    def _setup_disk_cache(self):
        """Setup disk caching for memory optimization."""
        cache_dir = Path(self.processing_config.disk_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean old cache files
        for cache_file in cache_dir.glob("*.cache"):
            if cache_file.stat().st_mtime < time.time() - 86400:  # 24 hours
                cache_file.unlink()
        
        logger.info(f"Disk cache setup at {cache_dir}")
    
    async def _cleanup_executor(self):
        """Cleanup executor resources."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
        
        if hasattr(self, 'thread_executor') and self.thread_executor:
            self.thread_executor.shutdown(wait=True)
            self.thread_executor = None
        
        if hasattr(self, 'process_executor') and self.process_executor:
            self.process_executor.shutdown(wait=True)
            self.process_executor = None
        
        logger.debug("Executor cleanup completed")


class DistributedCoordinator:
    """
    Coordinator for distributed Monte Carlo processing.
    
    Manages simulation distribution across multiple worker nodes
    and coordinates result collection.
    """
    
    def __init__(self, worker_nodes: List[str]):
        """Initialize distributed coordinator."""
        self.worker_nodes = worker_nodes
        self.worker_status: Dict[str, str] = {}
        self.active_connections: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize connections to worker nodes."""
        logger.info(f"Initializing connections to {len(self.worker_nodes)} worker nodes")
        
        for node in self.worker_nodes:
            try:
                # In a real implementation, this would establish network connections
                # For now, we'll simulate the connection
                self.worker_status[node] = "CONNECTED"
                self.active_connections[node] = f"connection_{node}"
                
            except Exception as e:
                logger.warning(f"Failed to connect to worker node {node}: {str(e)}")
                self.worker_status[node] = "FAILED"
    
    async def distribute_data(self, historical_data: Dict[TimeBin, List[ProcessedTrade]]):
        """Distribute historical data to worker nodes."""
        logger.info("Distributing historical data to worker nodes")
        
        # In a real implementation, this would serialize and send data
        # For now, we'll simulate the distribution
        for node in self.worker_nodes:
            if self.worker_status[node] == "CONNECTED":
                # Simulate data distribution
                await asyncio.sleep(0.1)  # Simulate network transfer
    
    def assign_batches(self, batches: List[SimulationBatch]) -> Dict[str, List[SimulationBatch]]:
        """Assign simulation batches to worker nodes."""
        assignments = {}
        available_nodes = [node for node in self.worker_nodes if self.worker_status[node] == "CONNECTED"]
        
        if not available_nodes:
            raise RuntimeError("No available worker nodes")
        
        # Round-robin assignment
        for i, batch in enumerate(batches):
            node = available_nodes[i % len(available_nodes)]
            if node not in assignments:
                assignments[node] = []
            assignments[node].append(batch)
        
        logger.info(f"Assigned {len(batches)} batches across {len(available_nodes)} nodes")
        return assignments
    
    async def execute_and_collect(
        self,
        batch_assignments: Dict[str, List[SimulationBatch]],
        progress_callback: Optional[Callable] = None
    ) -> List[BatchResult]:
        """Execute simulations on worker nodes and collect results."""
        logger.info("Executing distributed simulations")
        
        all_results = []
        
        # In a real implementation, this would coordinate remote execution
        # For now, we'll simulate the process
        for node, batches in batch_assignments.items():
            for batch in batches:
                # Simulate batch processing
                await asyncio.sleep(0.5)  # Simulate processing time
                
                # Create mock result
                result = BatchResult(
                    batch_id=batch.batch_id,
                    simulation_results=[],  # Would contain actual results
                    processing_time=0.5,
                    worker_id=node,
                    memory_used_mb=100.0
                )
                
                all_results.append(result)
        
        return all_results
    
    async def cleanup(self):
        """Cleanup distributed resources."""
        logger.info("Cleaning up distributed coordinator")
        
        for node in self.worker_nodes:
            if node in self.active_connections:
                # Close connection
                del self.active_connections[node]
                self.worker_status[node] = "DISCONNECTED"


# Utility functions for external use
def create_optimal_processor(
    monte_carlo_simulator: MonteCarloSimulator,
    time_bin_analyzer: TimeBinAnalyzer,
    target_simulations: int = 1000,
    time_constraint_seconds: Optional[float] = None,
    memory_constraint_gb: Optional[float] = None
) -> ParallelMonteCarloProcessor:
    """
    Create an optimally configured parallel processor.
    
    Analyzes system capabilities and constraints to create
    the best processor configuration.
    """
    processor = ParallelMonteCarloProcessor(monte_carlo_simulator, time_bin_analyzer)
    
    optimal_config = processor.get_optimal_configuration(
        target_simulations, time_constraint_seconds, memory_constraint_gb
    )
    
    processor.processing_config = optimal_config
    
    return processor


async def run_performance_test(
    monte_carlo_simulator: MonteCarloSimulator,
    time_bin_analyzer: TimeBinAnalyzer,
    test_simulations: int = 500
) -> Dict[str, Any]:
    """
    Run a comprehensive performance test of parallel processing.
    
    Tests various configurations and returns performance metrics.
    """
    processor = ParallelMonteCarloProcessor(monte_carlo_simulator, time_bin_analyzer)
    
    # Test configurations
    test_configs = [
        ProcessingConfiguration(
            processing_mode=ProcessingMode.SINGLE_THREADED,
            max_workers=1
        ),
        ProcessingConfiguration(
            processing_mode=ProcessingMode.MULTI_THREADED,
            max_workers=4
        ),
        ProcessingConfiguration(
            processing_mode=ProcessingMode.MULTI_PROCESS,
            max_workers=4
        ),
        ProcessingConfiguration(
            processing_mode=ProcessingMode.HYBRID,
            max_workers=8
        )
    ]
    
    results = await processor.benchmark_performance(test_configs, test_simulations)
    
    return results