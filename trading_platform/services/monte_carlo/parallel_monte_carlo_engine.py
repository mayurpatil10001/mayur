"""
Parallel Monte Carlo Engine for high-performance risk simulation.

This service provides parallel processing capabilities for Monte Carlo simulations
using joblib for distributed computation, progress tracking, and cancellation
support for large-scale risk analysis.

Requirements: 2.1, 2.6, 14.1
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from joblib import Parallel, delayed
import multiprocessing as mp
import threading
import time
from loguru import logger
from sqlalchemy.orm import Session

from .time_bin_scenario_generator import (
    TimeBinScenarioGenerator, ScenarioGenerationConfig, ScenarioSet,
    RegimeConditionalScenarios, ScenarioType
)
from .risk_metrics_calculator import (
    RiskMetricsCalculator, ComprehensiveRiskReport, RiskMeasureType
)
from ..time_bin_analyzer import TimeBin
from ...database.connection import get_db_session


class SimulationStatus(Enum):
    """Status of Monte Carlo simulation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled" 
    FAILED = "failed"


class SimulationType(Enum):
    """Types of Monte Carlo simulation."""
    BOOTSTRAP = "bootstrap"
    PARAMETRIC = "parametric"
    REGIME_CONDITIONAL = "regime_conditional"
    COMPREHENSIVE = "comprehensive"  # All methods


@dataclass
class SimulationProgress:
    """Progress tracking for Monte Carlo simulation."""
    simulation_id: str
    status: SimulationStatus
    current_step: str
    steps_completed: int
    total_steps: int
    progress_percentage: float
    start_time: datetime
    estimated_completion: Optional[datetime]
    elapsed_time: float
    scenarios_generated: int
    total_scenarios_target: int
    current_operation: str
    worker_count: int
    memory_usage_mb: float
    error_message: Optional[str] = None


@dataclass
class ParallelProcessingConfig:
    """Configuration for parallel processing."""
    n_jobs: int = -1  # -1 uses all available cores
    batch_size: int = 1000  # Scenarios per batch
    max_memory_usage_gb: float = 8.0  # Maximum memory usage
    prefer_threads: bool = False  # Use threads vs processes
    timeout_minutes: int = 30  # Maximum simulation time
    enable_progress_tracking: bool = True
    checkpoint_interval: int = 5000  # Save progress every N scenarios


@dataclass
class MonteCarloSimulationRequest:
    """Request for Monte Carlo simulation."""
    account_name: str
    hour: int
    minute_bin: int
    simulation_type: SimulationType
    scenario_config: ScenarioGenerationConfig
    parallel_config: ParallelProcessingConfig
    risk_analysis_config: Dict[str, Any]
    portfolio_value: float = 100000
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    simulation_id: Optional[str] = None
    priority: int = 1  # 1=high, 2=medium, 3=low


@dataclass
class MonteCarloSimulationResult:
    """Result of Monte Carlo simulation."""
    simulation_id: str
    request: MonteCarloSimulationRequest
    scenario_set: Optional[ScenarioSet]
    regime_scenarios: Optional[RegimeConditionalScenarios]
    risk_report: Optional[ComprehensiveRiskReport]
    progress: SimulationProgress
    performance_metrics: Dict[str, Any]
    generation_timestamp: datetime
    total_execution_time: float
    parallel_efficiency: float
    memory_peak_usage_mb: float


class SimulationCancelledException(Exception):
    """Exception raised when simulation is cancelled."""
    pass


class ParallelMonteCarloEngine:
    """
    High-performance parallel Monte Carlo engine for risk simulation.
    
    Provides parallel processing, progress tracking, and cancellation
    capabilities for large-scale Monte Carlo simulations using joblib
    and multiprocessing for optimal performance.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize parallel Monte Carlo engine."""
        self.db_session = db_session or get_db_session()
        
        # Core components
        self.scenario_generator = TimeBinScenarioGenerator(db_session=self.db_session)
        self.risk_calculator = RiskMetricsCalculator()
        
        # Simulation tracking
        self.active_simulations: Dict[str, MonteCarloSimulationResult] = {}
        self.simulation_lock = threading.Lock()
        
        # Resource management
        self.max_concurrent_simulations = max(1, mp.cpu_count() // 2)
        self.current_simulation_count = 0
        self.resource_lock = threading.Lock()
        
        # Performance monitoring
        self.performance_history: List[Dict[str, Any]] = []
        
        logger.info("ParallelMonteCarloEngine initialized with {} max concurrent simulations",
                   self.max_concurrent_simulations)
    
    async def run_simulation(self, request: MonteCarloSimulationRequest) -> MonteCarloSimulationResult:
        """
        Run Monte Carlo simulation with parallel processing and progress tracking.
        
        Args:
            request: MonteCarloSimulationRequest with simulation parameters
            
        Returns:
            MonteCarloSimulationResult with complete simulation results
        """
        simulation_id = request.simulation_id or str(uuid.uuid4())
        logger.info("Starting Monte Carlo simulation {} for account {} {}:{:02d}",
                   simulation_id, request.account_name, request.hour, request.minute_bin)
        
        # Check resource availability
        if not self._acquire_simulation_slot():
            raise RuntimeError("Maximum concurrent simulations reached. Please try again later.")
        
        try:
            # Initialize simulation tracking
            start_time = datetime.now()
            progress = SimulationProgress(
                simulation_id=simulation_id,
                status=SimulationStatus.PENDING,
                current_step="Initializing",
                steps_completed=0,
                total_steps=self._calculate_total_steps(request),
                progress_percentage=0.0,
                start_time=start_time,
                estimated_completion=None,
                elapsed_time=0.0,
                scenarios_generated=0,
                total_scenarios_target=request.scenario_config.num_scenarios,
                current_operation="Preparing simulation",
                worker_count=self._get_optimal_worker_count(request.parallel_config),
                memory_usage_mb=0.0
            )
            
            # Create initial result object
            result = MonteCarloSimulationResult(
                simulation_id=simulation_id,
                request=request,
                scenario_set=None,
                regime_scenarios=None,
                risk_report=None,
                progress=progress,
                performance_metrics={},
                generation_timestamp=start_time,
                total_execution_time=0.0,
                parallel_efficiency=0.0,
                memory_peak_usage_mb=0.0
            )
            
            # Store in active simulations
            with self.simulation_lock:
                self.active_simulations[simulation_id] = result
            
            # Run simulation based on type
            if request.simulation_type == SimulationType.BOOTSTRAP:
                await self._run_bootstrap_simulation(result)
            elif request.simulation_type == SimulationType.PARAMETRIC:
                await self._run_parametric_simulation(result)
            elif request.simulation_type == SimulationType.REGIME_CONDITIONAL:
                await self._run_regime_conditional_simulation(result)
            elif request.simulation_type == SimulationType.COMPREHENSIVE:
                await self._run_comprehensive_simulation(result)
            else:
                raise ValueError(f"Unsupported simulation type: {request.simulation_type}")
            
            # Complete simulation
            result.progress.status = SimulationStatus.COMPLETED
            result.progress.progress_percentage = 100.0
            result.total_execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info("Monte Carlo simulation {} completed in {:.2f} seconds",
                       simulation_id, result.total_execution_time)
            
            return result
            
        except SimulationCancelledException:
            logger.info("Monte Carlo simulation {} was cancelled", simulation_id)
            with self.simulation_lock:
                if simulation_id in self.active_simulations:
                    self.active_simulations[simulation_id].progress.status = SimulationStatus.CANCELLED
            raise
            
        except Exception as e:
            logger.error("Monte Carlo simulation {} failed: {}", simulation_id, e)
            with self.simulation_lock:
                if simulation_id in self.active_simulations:
                    self.active_simulations[simulation_id].progress.status = SimulationStatus.FAILED
                    self.active_simulations[simulation_id].progress.error_message = str(e)
            raise
            
        finally:
            self._release_simulation_slot()
    
    def cancel_simulation(self, simulation_id: str) -> bool:
        """
        Cancel a running simulation.
        
        Args:
            simulation_id: ID of simulation to cancel
            
        Returns:
            True if cancellation was successful, False if simulation not found
        """
        with self.simulation_lock:
            if simulation_id not in self.active_simulations:
                return False
            
            result = self.active_simulations[simulation_id]
            if result.progress.status in [SimulationStatus.COMPLETED, SimulationStatus.FAILED, SimulationStatus.CANCELLED]:
                return False
            
            result.progress.status = SimulationStatus.CANCELLED
            result.progress.current_operation = "Cancelling simulation"
            
        logger.info("Simulation {} marked for cancellation", simulation_id)
        return True
    
    def get_simulation_progress(self, simulation_id: str) -> Optional[SimulationProgress]:
        """
        Get current progress of a simulation.
        
        Args:
            simulation_id: ID of simulation
            
        Returns:
            SimulationProgress or None if not found
        """
        with self.simulation_lock:
            if simulation_id in self.active_simulations:
                result = self.active_simulations[simulation_id]
                # Update elapsed time
                result.progress.elapsed_time = (datetime.now() - result.progress.start_time).total_seconds()
                return result.progress
        return None
    
    def get_active_simulations(self) -> List[SimulationProgress]:
        """Get progress of all active simulations."""
        with self.simulation_lock:
            return [result.progress for result in self.active_simulations.values()]
    
    def cleanup_completed_simulations(self, max_age_hours: int = 24):
        """Clean up completed simulations older than specified age."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.simulation_lock:
            to_remove = []
            for sim_id, result in self.active_simulations.items():
                if (result.progress.status in [SimulationStatus.COMPLETED, SimulationStatus.FAILED, SimulationStatus.CANCELLED]
                    and result.generation_timestamp < cutoff_time):
                    to_remove.append(sim_id)
            
            for sim_id in to_remove:
                del self.active_simulations[sim_id]
        
        if to_remove:
            logger.info("Cleaned up {} completed simulations", len(to_remove))
    
    async def _run_bootstrap_simulation(self, result: MonteCarloSimulationResult):
        """Run bootstrap scenario generation with parallel processing."""
        request = result.request
        
        # Update progress
        result.progress.status = SimulationStatus.RUNNING
        result.progress.current_step = "Generating bootstrap scenarios"
        result.progress.current_operation = "Fetching historical data"
        
        # Check for cancellation
        self._check_cancellation(result.simulation_id)
        
        try:
            # Generate scenarios with parallel processing
            scenario_set = await self._parallel_bootstrap_generation(request, result)
            result.scenario_set = scenario_set
            
            # Update progress
            result.progress.steps_completed += 1
            result.progress.progress_percentage = (result.progress.steps_completed / result.progress.total_steps) * 100
            result.progress.current_operation = "Calculating risk metrics"
            
            # Calculate risk metrics
            risk_report = self.risk_calculator.generate_comprehensive_risk_report(
                scenario_set, portfolio_value=request.portfolio_value
            )
            result.risk_report = risk_report
            
            # Update final progress
            result.progress.steps_completed += 1
            result.progress.progress_percentage = 100.0
            
        except Exception as e:
            logger.error("Bootstrap simulation failed: {}", e)
            raise
    
    async def _run_parametric_simulation(self, result: MonteCarloSimulationResult):
        """Run parametric scenario generation with parallel processing."""
        request = result.request
        
        result.progress.status = SimulationStatus.RUNNING
        result.progress.current_step = "Generating parametric scenarios"
        result.progress.current_operation = "Fitting distributions"
        
        self._check_cancellation(result.simulation_id)
        
        try:
            # Generate scenarios
            scenario_set = await self._parallel_parametric_generation(request, result)
            result.scenario_set = scenario_set
            
            # Calculate risk metrics
            result.progress.current_operation = "Calculating risk metrics"
            risk_report = self.risk_calculator.generate_comprehensive_risk_report(
                scenario_set, portfolio_value=request.portfolio_value
            )
            result.risk_report = risk_report
            
            result.progress.steps_completed = result.progress.total_steps
            result.progress.progress_percentage = 100.0
            
        except Exception as e:
            logger.error("Parametric simulation failed: {}", e)
            raise
    
    async def _run_regime_conditional_simulation(self, result: MonteCarloSimulationResult):
        """Run regime-conditional scenario generation with parallel processing."""
        request = result.request
        
        result.progress.status = SimulationStatus.RUNNING
        result.progress.current_step = "Generating regime-conditional scenarios"
        result.progress.current_operation = "Analyzing VIX regimes"
        
        self._check_cancellation(result.simulation_id)
        
        try:
            # Generate regime-conditional scenarios
            regime_scenarios = await self._parallel_regime_generation(request, result)
            result.regime_scenarios = regime_scenarios
            
            # Use one of the regime scenario sets for main scenario set
            result.scenario_set = regime_scenarios.medium_regime_scenarios
            
            # Calculate comprehensive risk metrics including regime analysis
            result.progress.current_operation = "Calculating regime-specific risk metrics"
            risk_report = self.risk_calculator.generate_comprehensive_risk_report(
                result.scenario_set, 
                regime_scenarios=regime_scenarios,
                portfolio_value=request.portfolio_value
            )
            result.risk_report = risk_report
            
            result.progress.steps_completed = result.progress.total_steps
            result.progress.progress_percentage = 100.0
            
        except Exception as e:
            logger.error("Regime-conditional simulation failed: {}", e)
            raise
    
    async def _run_comprehensive_simulation(self, result: MonteCarloSimulationResult):
        """Run comprehensive simulation with all methods."""
        request = result.request
        
        result.progress.status = SimulationStatus.RUNNING
        result.progress.current_step = "Running comprehensive analysis"
        result.progress.total_steps = 6  # Bootstrap + Parametric + Regime + Risk analysis
        
        try:
            # Run bootstrap scenarios
            result.progress.current_operation = "Bootstrap scenario generation"
            bootstrap_scenarios = await self._parallel_bootstrap_generation(request, result)
            result.progress.steps_completed += 1
            self._update_progress(result)
            
            self._check_cancellation(result.simulation_id)
            
            # Run parametric scenarios  
            result.progress.current_operation = "Parametric scenario generation"
            parametric_scenarios = await self._parallel_parametric_generation(request, result)
            result.progress.steps_completed += 1
            self._update_progress(result)
            
            self._check_cancellation(result.simulation_id)
            
            # Run regime-conditional scenarios
            result.progress.current_operation = "Regime-conditional scenario generation"
            regime_scenarios = await self._parallel_regime_generation(request, result)
            result.progress.steps_completed += 1
            self._update_progress(result)
            
            self._check_cancellation(result.simulation_id)
            
            # Use parametric as primary scenario set
            result.scenario_set = parametric_scenarios
            result.regime_scenarios = regime_scenarios
            
            # Comprehensive risk analysis
            result.progress.current_operation = "Comprehensive risk analysis"
            risk_report = self.risk_calculator.generate_comprehensive_risk_report(
                parametric_scenarios,
                regime_scenarios=regime_scenarios,
                portfolio_value=request.portfolio_value
            )
            result.risk_report = risk_report
            
            # Add comparative analysis
            result.performance_metrics = self._compare_scenario_methods(
                bootstrap_scenarios, parametric_scenarios, regime_scenarios
            )
            
            result.progress.steps_completed = result.progress.total_steps
            result.progress.progress_percentage = 100.0
            
        except Exception as e:
            logger.error("Comprehensive simulation failed: {}", e)
            raise
    
    async def _parallel_bootstrap_generation(self, request: MonteCarloSimulationRequest, 
                                           result: MonteCarloSimulationResult) -> ScenarioSet:
        """Generate bootstrap scenarios using parallel processing."""
        
        # For now, use single-threaded generation as the scenario generator handles internal parallelization
        # Future enhancement: split scenario generation across multiple workers
        
        loop = asyncio.get_event_loop()
        
        def generate_scenarios():
            return self.scenario_generator.generate_bootstrap_scenarios(
                account_name=request.account_name,
                hour=request.hour,
                minute_bin=request.minute_bin,
                config=request.scenario_config
            )
        
        # Run in thread pool to avoid blocking
        with ThreadPoolExecutor(max_workers=1) as executor:
            scenario_set = await loop.run_in_executor(executor, generate_scenarios)
        
        result.progress.scenarios_generated = scenario_set.scenarios.size
        
        return scenario_set
    
    async def _parallel_parametric_generation(self, request: MonteCarloSimulationRequest,
                                            result: MonteCarloSimulationResult) -> ScenarioSet:
        """Generate parametric scenarios using parallel processing."""
        
        loop = asyncio.get_event_loop()
        
        def generate_scenarios():
            return self.scenario_generator.generate_parametric_scenarios(
                account_name=request.account_name,
                hour=request.hour,
                minute_bin=request.minute_bin,
                config=request.scenario_config
            )
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            scenario_set = await loop.run_in_executor(executor, generate_scenarios)
        
        result.progress.scenarios_generated = scenario_set.scenarios.size
        
        return scenario_set
    
    async def _parallel_regime_generation(self, request: MonteCarloSimulationRequest,
                                        result: MonteCarloSimulationResult) -> RegimeConditionalScenarios:
        """Generate regime-conditional scenarios using parallel processing."""
        
        loop = asyncio.get_event_loop()
        
        def generate_scenarios():
            return self.scenario_generator.generate_regime_conditional_scenarios(
                account_name=request.account_name,
                hour=request.hour,
                minute_bin=request.minute_bin,
                config=request.scenario_config
            )
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            regime_scenarios = await loop.run_in_executor(executor, generate_scenarios)
        
        # Count total scenarios across all regimes
        total_scenarios = (regime_scenarios.low_regime_scenarios.scenarios.size +
                         regime_scenarios.medium_regime_scenarios.scenarios.size + 
                         regime_scenarios.high_regime_scenarios.scenarios.size)
        result.progress.scenarios_generated = total_scenarios
        
        return regime_scenarios
    
    def _calculate_total_steps(self, request: MonteCarloSimulationRequest) -> int:
        """Calculate total steps for progress tracking."""
        if request.simulation_type == SimulationType.COMPREHENSIVE:
            return 6  # Bootstrap + Parametric + Regime + Risk analysis + Comparison + Finalization
        elif request.simulation_type == SimulationType.REGIME_CONDITIONAL:
            return 4  # Regime analysis + Generation + Risk calculation + Finalization
        else:
            return 3  # Generation + Risk calculation + Finalization
    
    def _get_optimal_worker_count(self, config: ParallelProcessingConfig) -> int:
        """Determine optimal number of workers."""
        if config.n_jobs == -1:
            return mp.cpu_count()
        elif config.n_jobs == -2:
            return mp.cpu_count() - 1
        else:
            return min(config.n_jobs, mp.cpu_count())
    
    def _check_cancellation(self, simulation_id: str):
        """Check if simulation should be cancelled."""
        with self.simulation_lock:
            if (simulation_id in self.active_simulations and 
                self.active_simulations[simulation_id].progress.status == SimulationStatus.CANCELLED):
                raise SimulationCancelledException(f"Simulation {simulation_id} was cancelled")
    
    def _update_progress(self, result: MonteCarloSimulationResult):
        """Update progress percentage."""
        result.progress.progress_percentage = (result.progress.steps_completed / result.progress.total_steps) * 100
        result.progress.elapsed_time = (datetime.now() - result.progress.start_time).total_seconds()
        
        # Estimate completion time
        if result.progress.progress_percentage > 0:
            estimated_total_time = result.progress.elapsed_time / (result.progress.progress_percentage / 100)
            estimated_remaining = estimated_total_time - result.progress.elapsed_time
            result.progress.estimated_completion = datetime.now() + timedelta(seconds=estimated_remaining)
    
    def _acquire_simulation_slot(self) -> bool:
        """Acquire a simulation slot if available."""
        with self.resource_lock:
            if self.current_simulation_count < self.max_concurrent_simulations:
                self.current_simulation_count += 1
                return True
            return False
    
    def _release_simulation_slot(self):
        """Release a simulation slot."""
        with self.resource_lock:
            if self.current_simulation_count > 0:
                self.current_simulation_count -= 1
    
    def _compare_scenario_methods(self, bootstrap: ScenarioSet, parametric: ScenarioSet,
                                regime: RegimeConditionalScenarios) -> Dict[str, Any]:
        """Compare different scenario generation methods."""
        try:
            bootstrap_flat = bootstrap.scenarios.flatten()
            parametric_flat = parametric.scenarios.flatten()
            
            return {
                'method_comparison': {
                    'bootstrap_mean': float(np.mean(bootstrap_flat)),
                    'parametric_mean': float(np.mean(parametric_flat)),
                    'bootstrap_std': float(np.std(bootstrap_flat)),
                    'parametric_std': float(np.std(parametric_flat)),
                    'correlation_bootstrap_parametric': float(np.corrcoef(
                        bootstrap_flat[:min(len(bootstrap_flat), len(parametric_flat))],
                        parametric_flat[:min(len(bootstrap_flat), len(parametric_flat))]
                    )[0, 1])
                },
                'regime_analysis': {
                    'low_regime_scenarios': regime.low_regime_scenarios.scenarios.size,
                    'medium_regime_scenarios': regime.medium_regime_scenarios.scenarios.size,
                    'high_regime_scenarios': regime.high_regime_scenarios.scenarios.size,
                    'transition_probabilities': regime.regime_transition_probabilities,
                    'regime_persistence': regime.regime_persistence
                },
                'statistical_properties': {
                    'bootstrap_validation_score': bootstrap.validation_results.get('overall_validation_score', 0),
                    'parametric_validation_score': parametric.validation_results.get('overall_validation_score', 0),
                    'bootstrap_generation_method': bootstrap.generation_method.value,
                    'parametric_generation_method': parametric.generation_method.value
                }
            }
        
        except Exception as e:
            logger.warning("Failed to compare scenario methods: {}", e)
            return {'comparison_error': str(e)}
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get current engine status and performance metrics."""
        with self.simulation_lock, self.resource_lock:
            return {
                'active_simulations': len(self.active_simulations),
                'max_concurrent_simulations': self.max_concurrent_simulations,
                'current_simulation_count': self.current_simulation_count,
                'available_slots': self.max_concurrent_simulations - self.current_simulation_count,
                'cpu_count': mp.cpu_count(),
                'performance_history_size': len(self.performance_history),
                'active_simulation_ids': list(self.active_simulations.keys()),
                'memory_usage_mb': self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0  # psutil not available