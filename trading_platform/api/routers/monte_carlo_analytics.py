"""
Monte Carlo Analytics API endpoints.

This module provides REST endpoints for Monte Carlo risk simulation,
parallel processing, progress tracking, and comprehensive risk analysis.

Requirements: 2.1, 2.6, 14.1
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
from loguru import logger

from ..dependencies import (
    get_database_session,
    require_read_permission
)
from ..models.common import APIResponse
from ..models.time_bin_analytics import (
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
    SimulationProgressResponse,
    ComprehensiveRiskReportResponse,
    SimulationTypeEnum,
    SimulationStatusEnum
)
from ..exceptions import DataNotFoundException, ServiceException
from ...services.monte_carlo.parallel_monte_carlo_engine import (
    ParallelMonteCarloEngine, 
    MonteCarloSimulationRequest as EngineRequest,
    ParallelProcessingConfig,
    ScenarioGenerationConfig,
    SimulationType
)
from ...services.time_bin_analyzer import TimeBin


# Create router
router = APIRouter(prefix="/api/time-bins", tags=["Monte Carlo Analytics"])

# Global engine instance (would be better as dependency injection in production)
monte_carlo_engine = ParallelMonteCarloEngine()

# Service dependencies
def get_monte_carlo_engine() -> ParallelMonteCarloEngine:
    """Get Monte Carlo engine dependency."""
    return monte_carlo_engine


@router.post("/{account_name}/{hour}/{minute_bin}/monte-carlo",
            response_model=APIResponse[MonteCarloSimulationResponse],
            summary="Run Monte Carlo Risk Simulation",
            description="""
            Run comprehensive Monte Carlo risk simulation for a specific time-bin.
            
            Supports multiple simulation types:
            - Bootstrap: Resampling from historical trades
            - Parametric: Distribution fitting and generation
            - Regime-conditional: VIX-based volatility regime analysis
            - Comprehensive: All methods combined with comparison
            
            Features parallel processing, progress tracking, and cancellation capabilities.
            """)
async def run_monte_carlo_simulation(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    request: MonteCarloSimulationRequest = None,
    background_tasks: BackgroundTasks = None,
    db_session: Session = Depends(get_database_session),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Run Monte Carlo simulation with parallel processing and progress tracking."""
    
    # Validate minute bin
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        # Generate simulation ID
        simulation_id = f"sim_{account_name}_{hour:02d}{minute_bin:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Convert API request to engine request
        scenario_config = ScenarioGenerationConfig(
            num_scenarios=request.num_scenarios,
            scenario_length=request.scenario_length,
            random_seed=request.random_seed,
            confidence_levels=request.confidence_levels
        )
        
        parallel_config = ParallelProcessingConfig(
            n_jobs=request.max_workers or -1,
            enable_progress_tracking=request.enable_progress_tracking,
            prefer_threads=not request.parallel_processing
        )
        
        # Map simulation type
        simulation_type_map = {
            SimulationTypeEnum.BOOTSTRAP: SimulationType.BOOTSTRAP,
            SimulationTypeEnum.PARAMETRIC: SimulationType.PARAMETRIC,
            SimulationTypeEnum.REGIME_CONDITIONAL: SimulationType.REGIME_CONDITIONAL,
            SimulationTypeEnum.COMPREHENSIVE: SimulationType.COMPREHENSIVE
        }
        
        engine_request = EngineRequest(
            account_name=account_name,
            hour=hour,
            minute_bin=minute_bin,
            simulation_type=simulation_type_map[request.simulation_type],
            scenario_config=scenario_config,
            parallel_config=parallel_config,
            risk_analysis_config={},
            portfolio_value=request.portfolio_value,
            start_date=request.start_date,
            end_date=request.end_date,
            simulation_id=simulation_id
        )
        
        # Run simulation asynchronously
        logger.info("Starting Monte Carlo simulation {} for user {}", 
                   simulation_id, user_context.get("user_id", "unknown"))
        
        result = await engine.run_simulation(engine_request)
        
        # Convert engine result to API response
        api_response = _convert_engine_result_to_api_response(result, account_name, hour, minute_bin)
        
        return APIResponse(
            status="success",
            message=f"Monte Carlo simulation completed successfully",
            data=api_response
        )
        
    except ValueError as e:
        logger.warning("Monte Carlo simulation request validation failed: {}", e)
        raise HTTPException(status_code=400, detail=str(e))
        
    except RuntimeError as e:
        if "Maximum concurrent simulations" in str(e):
            raise HTTPException(
                status_code=503, 
                detail="Server is currently at capacity. Please try again later."
            )
        else:
            logger.error("Monte Carlo simulation runtime error: {}", e)
            raise HTTPException(status_code=500, detail="Simulation failed due to server error")
        
    except Exception as e:
        logger.error("Unexpected error in Monte Carlo simulation: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Monte Carlo simulation failed due to unexpected error"
        )


@router.get("/{account_name}/{hour}/{minute_bin}/monte-carlo/{simulation_id}/progress",
           response_model=APIResponse[SimulationProgressResponse],
           summary="Get Simulation Progress",
           description="Get real-time progress of a running Monte Carlo simulation.")
async def get_simulation_progress(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    simulation_id: str = Path(description="Simulation ID"),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Get current progress of a Monte Carlo simulation."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        progress = engine.get_simulation_progress(simulation_id)
        
        if progress is None:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {simulation_id} not found"
            )
        
        # Convert to API response
        progress_response = SimulationProgressResponse(
            simulation_id=progress.simulation_id,
            status=SimulationStatusEnum(progress.status.value),
            current_step=progress.current_step,
            steps_completed=progress.steps_completed,
            total_steps=progress.total_steps,
            progress_percentage=progress.progress_percentage,
            start_time=progress.start_time,
            estimated_completion=progress.estimated_completion,
            elapsed_time=progress.elapsed_time,
            scenarios_generated=progress.scenarios_generated,
            total_scenarios_target=progress.total_scenarios_target,
            current_operation=progress.current_operation,
            worker_count=progress.worker_count,
            memory_usage_mb=progress.memory_usage_mb,
            error_message=progress.error_message
        )
        
        return APIResponse(
            status="success",
            message=f"Progress retrieved for simulation {simulation_id}",
            data=progress_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving simulation progress: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve simulation progress"
        )


@router.delete("/{account_name}/{hour}/{minute_bin}/monte-carlo/{simulation_id}",
              response_model=APIResponse[Dict[str, Any]],
              summary="Cancel Monte Carlo Simulation",
              description="Cancel a running Monte Carlo simulation.")
async def cancel_simulation(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    simulation_id: str = Path(description="Simulation ID"),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Cancel a running Monte Carlo simulation."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        success = engine.cancel_simulation(simulation_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {simulation_id} not found or already completed"
            )
        
        logger.info("Simulation {} cancelled by user {}", 
                   simulation_id, user_context.get("user_id", "unknown"))
        
        return APIResponse(
            status="success",
            message=f"Simulation {simulation_id} cancelled successfully",
            data={"simulation_id": simulation_id, "cancelled": True}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error cancelling simulation: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel simulation"
        )


@router.get("/{account_name}/{hour}/{minute_bin}/risk-metrics",
           response_model=APIResponse[ComprehensiveRiskReportResponse],
           summary="Get Risk Metrics Analysis",
           description="""
           Get comprehensive risk analysis including VaR, Expected Shortfall,
           tail risk metrics, and probability analysis for a specific time-bin.
           
           This endpoint provides quick risk analysis without full Monte Carlo simulation.
           """)
async def get_risk_metrics(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    num_scenarios: int = Query(default=1000, ge=100, le=10000, 
                              description="Number of scenarios for analysis"),
    simulation_type: SimulationTypeEnum = Query(default=SimulationTypeEnum.BOOTSTRAP,
                                               description="Type of scenario generation"),
    portfolio_value: float = Query(default=100000, gt=0,
                                  description="Portfolio value for percentage calculations"),
    confidence_levels: Optional[List[float]] = Query(default=None,
                                                    description="Confidence levels for VaR/ES"),
    start_date: Optional[str] = Query(default=None, 
                                     description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None,
                                   description="End date (YYYY-MM-DD)"),
    db_session: Session = Depends(get_database_session),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Get comprehensive risk analysis for time-bin without full simulation tracking."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        # Create quick simulation request
        scenario_config = ScenarioGenerationConfig(
            num_scenarios=num_scenarios,
            scenario_length=30,  # Short scenarios for quick analysis
            confidence_levels=confidence_levels or [0.95, 0.99, 0.999]
        )
        
        parallel_config = ParallelProcessingConfig(
            n_jobs=2,  # Limited parallelism for quick requests
            enable_progress_tracking=False
        )
        
        simulation_type_map = {
            SimulationTypeEnum.BOOTSTRAP: SimulationType.BOOTSTRAP,
            SimulationTypeEnum.PARAMETRIC: SimulationType.PARAMETRIC,
            SimulationTypeEnum.REGIME_CONDITIONAL: SimulationType.REGIME_CONDITIONAL
        }
        
        engine_request = EngineRequest(
            account_name=account_name,
            hour=hour,
            minute_bin=minute_bin,
            simulation_type=simulation_type_map[simulation_type],
            scenario_config=scenario_config,
            parallel_config=parallel_config,
            risk_analysis_config={},
            portfolio_value=portfolio_value,
            start_date=start_date,
            end_date=end_date,
            simulation_id=f"quick_risk_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Run quick simulation
        result = await engine.run_simulation(engine_request)
        
        if result.risk_report is None:
            raise HTTPException(
                status_code=500,
                detail="Risk analysis failed to generate results"
            )
        
        # Convert to API response
        risk_report = _convert_risk_report_to_api_response(result.risk_report)
        
        return APIResponse(
            status="success",
            message=f"Risk metrics calculated for {account_name} {hour}:{minute_bin:02d}",
            data=risk_report
        )
        
    except ValueError as e:
        logger.warning("Risk metrics request validation failed: {}", e)
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error("Error calculating risk metrics: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Risk metrics calculation failed"
        )


@router.get("/monte-carlo/active-simulations",
           response_model=APIResponse[List[SimulationProgressResponse]],
           summary="Get Active Simulations",
           description="Get list of all active Monte Carlo simulations with their progress.")
async def get_active_simulations(
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Get list of all active simulations."""
    
    try:
        active_simulations = engine.get_active_simulations()
        
        # Convert to API response
        simulation_responses = []
        for progress in active_simulations:
            simulation_responses.append(SimulationProgressResponse(
                simulation_id=progress.simulation_id,
                status=SimulationStatusEnum(progress.status.value),
                current_step=progress.current_step,
                steps_completed=progress.steps_completed,
                total_steps=progress.total_steps,
                progress_percentage=progress.progress_percentage,
                start_time=progress.start_time,
                estimated_completion=progress.estimated_completion,
                elapsed_time=progress.elapsed_time,
                scenarios_generated=progress.scenarios_generated,
                total_scenarios_target=progress.total_scenarios_target,
                current_operation=progress.current_operation,
                worker_count=progress.worker_count,
                memory_usage_mb=progress.memory_usage_mb,
                error_message=progress.error_message
            ))
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(simulation_responses)} active simulations",
            data=simulation_responses
        )
        
    except Exception as e:
        logger.error("Error retrieving active simulations: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve active simulations"
        )


@router.get("/monte-carlo/engine-status",
           response_model=APIResponse[Dict[str, Any]],
           summary="Get Monte Carlo Engine Status",
           description="Get current status of the Monte Carlo engine including resource usage.")
async def get_engine_status(
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Get Monte Carlo engine status and performance metrics."""
    
    try:
        status = engine.get_engine_status()
        
        return APIResponse(
            status="success",
            message="Engine status retrieved successfully",
            data=status
        )
        
    except Exception as e:
        logger.error("Error retrieving engine status: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve engine status"
        )


def _convert_engine_result_to_api_response(result, account_name: str, hour: int, minute_bin: int) -> MonteCarloSimulationResponse:
    """Convert engine result to API response format."""
    
    # Convert progress
    progress = SimulationProgressResponse(
        simulation_id=result.progress.simulation_id,
        status=SimulationStatusEnum(result.progress.status.value),
        current_step=result.progress.current_step,
        steps_completed=result.progress.steps_completed,
        total_steps=result.progress.total_steps,
        progress_percentage=result.progress.progress_percentage,
        start_time=result.progress.start_time,
        estimated_completion=result.progress.estimated_completion,
        elapsed_time=result.progress.elapsed_time,
        scenarios_generated=result.progress.scenarios_generated,
        total_scenarios_target=result.progress.total_scenarios_target,
        current_operation=result.progress.current_operation,
        worker_count=result.progress.worker_count,
        memory_usage_mb=result.progress.memory_usage_mb,
        error_message=result.progress.error_message
    )
    
    # Convert risk report
    risk_report = _convert_risk_report_to_api_response(result.risk_report) if result.risk_report else None
    
    return MonteCarloSimulationResponse(
        simulation_id=result.simulation_id,
        simulation_type=SimulationTypeEnum(result.request.simulation_type.value),
        status=SimulationStatusEnum(result.progress.status.value),
        risk_report=risk_report,
        progress=progress,
        performance_metrics=result.performance_metrics,
        account_name=account_name,
        time_bin=f"{hour:02d}:{minute_bin:02d}",
        request_timestamp=result.generation_timestamp,
        completion_timestamp=datetime.now() if result.progress.status.value == "completed" else None
    )


def _convert_risk_report_to_api_response(risk_report) -> ComprehensiveRiskReportResponse:
    """Convert risk report to API response format."""
    from ..models.time_bin_analytics import (
        VaRResultResponse, ExpectedShortfallResultResponse, TailRiskMetricsResponse,
        ProbabilityMetricsResponse, ScenarioSummaryResponse, RiskDecompositionResponse
    )
    
    # Convert VaR results
    var_results = {}
    for conf_level, var_result in risk_report.var_results.items():
        var_results[conf_level] = VaRResultResponse(
            confidence_level=var_result.confidence_level,
            var_absolute=var_result.var_absolute,
            var_percentage=var_result.var_percentage,
            calculation_method=var_result.calculation_method.value,
            sample_size=var_result.sample_size,
            percentile_rank=var_result.percentile_rank,
            worst_case_scenario=var_result.worst_case_scenario
        )
    
    # Convert Expected Shortfall results
    es_results = {}
    for conf_level, es_result in risk_report.expected_shortfall_results.items():
        es_results[conf_level] = ExpectedShortfallResultResponse(
            confidence_level=es_result.confidence_level,
            expected_shortfall=es_result.expected_shortfall,
            var_threshold=es_result.var_threshold,
            tail_scenarios_count=es_result.tail_scenarios_count,
            calculation_method=es_result.calculation_method.value,
            sample_size=es_result.sample_size
        )
    
    # Convert tail risk metrics
    tail_metrics = TailRiskMetricsResponse(
        extreme_value_model=risk_report.tail_risk_metrics.extreme_value_model.value,
        model_parameters=risk_report.tail_risk_metrics.model_parameters,
        return_level_99_9=risk_report.tail_risk_metrics.return_level_99_9,
        return_level_99_95=risk_report.tail_risk_metrics.return_level_99_95,
        return_level_99_99=risk_report.tail_risk_metrics.return_level_99_99,
        tail_index=risk_report.tail_risk_metrics.tail_index,
        model_fit_quality=risk_report.tail_risk_metrics.model_fit_quality,
        worst_historical_loss=risk_report.tail_risk_metrics.worst_historical_loss,
        tail_concentration=risk_report.tail_risk_metrics.tail_concentration
    )
    
    # Convert probability metrics
    prob_metrics = ProbabilityMetricsResponse(
        probability_of_profit=risk_report.probability_metrics.probability_of_profit,
        probability_of_loss=risk_report.probability_metrics.probability_of_loss,
        probability_large_loss=risk_report.probability_metrics.probability_large_loss,
        probability_large_gain=risk_report.probability_metrics.probability_large_gain,
        expected_positive_return=risk_report.probability_metrics.expected_positive_return,
        expected_negative_return=risk_report.probability_metrics.expected_negative_return,
        gain_loss_ratio=risk_report.probability_metrics.gain_loss_ratio,
        kelly_criterion=risk_report.probability_metrics.kelly_criterion
    )
    
    # Convert scenario summary
    scenario_summary = ScenarioSummaryResponse(
        total_scenarios=risk_report.scenario_summary['total_scenarios'],
        mean_return=risk_report.scenario_summary['mean_return'],
        std_return=risk_report.scenario_summary['std_return'],
        skewness=risk_report.scenario_summary['skewness'],
        kurtosis=risk_report.scenario_summary['kurtosis'],
        min_scenario=risk_report.scenario_summary['min_scenario'],
        max_scenario=risk_report.scenario_summary['max_scenario'],
        median_scenario=risk_report.scenario_summary['median_scenario']
    )
    
    # Convert risk decomposition
    risk_decomposition = RiskDecompositionResponse(
        worst_1_percent=risk_report.risk_decomposition['worst_1_percent'],
        worst_5_percent=risk_report.risk_decomposition['worst_5_percent'],
        worst_10_percent=risk_report.risk_decomposition['worst_10_percent'],
        best_10_percent=risk_report.risk_decomposition['best_10_percent'],
        middle_80_percent=risk_report.risk_decomposition['middle_80_percent'],
        interquartile_range=risk_report.risk_decomposition['interquartile_range'],
        range_ratio=risk_report.risk_decomposition['range_ratio']
    )
    
    return ComprehensiveRiskReportResponse(
        var_results=var_results,
        expected_shortfall_results=es_results,
        tail_risk_metrics=tail_metrics,
        probability_metrics=prob_metrics,
        scenario_summary=scenario_summary,
        risk_decomposition=risk_decomposition,
        regime_risk_analysis=risk_report.regime_risk_analysis,
        calculation_config=risk_report.calculation_config,
        generation_timestamp=risk_report.generation_timestamp
    )


# Cleanup task to remove old completed simulations
@router.delete("/monte-carlo/cleanup-completed",
              response_model=APIResponse[Dict[str, Any]],
              summary="Cleanup Completed Simulations",
              description="Remove completed simulations older than specified age.")
async def cleanup_completed_simulations(
    max_age_hours: int = Query(default=24, ge=1, le=168,
                              description="Maximum age in hours for keeping completed simulations"),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    engine: ParallelMonteCarloEngine = Depends(get_monte_carlo_engine)
):
    """Clean up completed simulations to free memory."""
    
    try:
        engine.cleanup_completed_simulations(max_age_hours)
        
        return APIResponse(
            status="success", 
            message=f"Cleaned up simulations older than {max_age_hours} hours",
            data={"max_age_hours": max_age_hours, "cleanup_completed": True}
        )
        
    except Exception as e:
        logger.error("Error during simulation cleanup: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to cleanup completed simulations"
        )