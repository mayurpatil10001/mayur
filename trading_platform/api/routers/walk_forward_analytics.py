"""
Walk-Forward Analysis API endpoints.

This module provides REST endpoints for walk-forward validation, strategy robustness
assessment, performance decay analysis, and background processing for long-running
walk-forward tests with comprehensive monitoring and alerting capabilities.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
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
    WalkForwardValidationRequest,
    WalkForwardValidationResponse,
    StrategyRobustnessResponse,
    DecayAnalysisResponse,
    PredictionAccuracyRequest,
    RetrainingAnalysisRequest,
    BackgroundProcessRequest,
    BackgroundProcessResponse,
    ValidationMethodEnum,
    DegradationSeverityEnum,
    PerformanceMetricsResponse,
    PeriodPerformanceResponse,
    DegradationAlertResponse
)
from ..exceptions import DataNotFoundException, ServiceException
from ...services.walk_forward.out_of_sample_validator import (
    OutOfSampleValidator,
    WalkForwardValidationRequest as ServiceRequest,
    RobustnessTestConfig,
    CrossValidationConfig
)
from ...services.walk_forward.performance_decay_tracker import (
    PerformanceDecayTracker,
    PerformanceDecayConfig
)
from ...services.time_bin_analyzer import TimeBin
from ...models.models import ProcessedTrade


# Create router
router = APIRouter(prefix="/api/time-bins", tags=["Walk-Forward Analytics"])

# Global service instances (would be better as dependency injection in production)
out_of_sample_validator = OutOfSampleValidator()
performance_decay_tracker = PerformanceDecayTracker()

# Background processing tracking
background_processes: Dict[str, Dict[str, Any]] = {}


# Service dependencies
def get_out_of_sample_validator() -> OutOfSampleValidator:
    """Get OutOfSampleValidator dependency."""
    return out_of_sample_validator


def get_decay_tracker() -> PerformanceDecayTracker:
    """Get PerformanceDecayTracker dependency."""
    return performance_decay_tracker


@router.post("/{account_name}/{hour}/{minute_bin}/walk-forward",
            response_model=APIResponse[Union[WalkForwardValidationResponse, BackgroundProcessResponse]],
            summary="Run Walk-Forward Validation",
            description="""
            Run comprehensive walk-forward validation for strategy robustness testing.
            
            Supports multiple validation methods:
            - Anchored: Fixed start date with expanding in-sample window
            - Rolling Window: Fixed-size moving window validation
            - Expanding Window: Growing in-sample period validation
            - Time Series CV: Cross-validation respecting temporal order
            
            For long-running analyses, returns background process information.
            """)
async def run_walk_forward_validation(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    request: WalkForwardValidationRequest = None,
    background_process: Optional[BackgroundProcessRequest] = None,
    background_tasks: BackgroundTasks = None,
    db_session: Session = Depends(get_database_session),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    validator: OutOfSampleValidator = Depends(get_out_of_sample_validator)
):
    """Run walk-forward validation with optional background processing."""
    
    # Validate minute bin
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        # Generate validation ID
        validation_id = f"wf_{account_name}_{hour:02d}{minute_bin:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        time_bin = TimeBin.from_time(hour, minute_bin)
        
        logger.info("Starting walk-forward validation {} for user {}", 
                   validation_id, user_context.get("user_id", "unknown"))
        
        # Convert API request to service request
        robustness_config = RobustnessTestConfig(
            min_trades_threshold=request.min_trades_threshold,
            performance_stability_threshold=request.performance_stability_threshold,
            overfitting_detection_threshold=request.overfitting_detection_threshold,
            confidence_level=request.confidence_level
        )
        
        service_request = ServiceRequest(
            account_name=account_name,
            start_date=request.start_date,
            end_date=request.end_date,
            time_bin=time_bin,
            validation_method=request.validation_method.value,
            min_in_sample_days=request.min_in_sample_days,
            out_of_sample_days=request.out_of_sample_days,
            step_days=request.step_days,
            robustness_config=robustness_config
        )
        
        # Estimate execution time
        estimated_minutes = _estimate_validation_time(request, account_name)
        
        # Check if background processing is needed/requested
        if (background_process and 
            (estimated_minutes > 5 or background_process.max_execution_time_minutes)):
            
            # Start background processing
            process_id = f"proc_{validation_id}"
            
            background_processes[process_id] = {
                "process_id": process_id,
                "process_type": "walk_forward_validation",
                "status": "pending",
                "progress_percentage": 0.0,
                "current_operation": "Initializing validation",
                "start_time": datetime.now(),
                "estimated_completion": datetime.now() + timedelta(minutes=estimated_minutes),
                "elapsed_time_seconds": 0.0,
                "validation_request": service_request,
                "account_name": account_name,
                "hour": hour,
                "minute_bin": minute_bin,
                "user_context": user_context,
                "result": None,
                "error_message": None
            }
            
            # Add background task
            background_tasks.add_task(
                _run_validation_background,
                process_id,
                service_request,
                validator
            )
            
            # Return background process response
            process_response = BackgroundProcessResponse(
                process_id=process_id,
                process_type="walk_forward_validation",
                status="pending",
                progress_percentage=0.0,
                current_operation="Initializing validation",
                start_time=datetime.now(),
                estimated_completion=datetime.now() + timedelta(minutes=estimated_minutes),
                elapsed_time_seconds=0.0,
                result_url=f"/api/time-bins/{account_name}/{hour}/{minute_bin}/walk-forward/results/{process_id}"
            )
            
            return APIResponse(
                status="accepted",
                message=f"Walk-forward validation started in background",
                data=process_response
            )
        
        else:
            # Run synchronously
            if request.validation_method == ValidationMethodEnum.ANCHORED_WALK_FORWARD:
                result = validator.anchored_walk_forward(service_request)
            elif request.validation_method == ValidationMethodEnum.ROLLING_WINDOW:
                result = validator.rolling_window_validation(service_request)
            elif request.validation_method == ValidationMethodEnum.EXPANDING_WINDOW:
                result = validator.expanding_window_validation(service_request)
            elif request.validation_method == ValidationMethodEnum.TIME_SERIES_CV:
                cv_config = CrossValidationConfig(
                    n_splits=request.n_splits or 5,
                    test_size_ratio=request.test_size_ratio or 0.2,
                    gap_days=request.gap_days or 2,
                    shuffle=False
                )
                result = validator.time_series_cross_validation(service_request, cv_config)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported validation method: {request.validation_method}")
            
            # Convert service result to API response
            api_response = _convert_validation_result_to_api_response(
                result, validation_id, account_name, hour, minute_bin
            )
            
            return APIResponse(
                status="success",
                message=f"Walk-forward validation completed successfully",
                data=api_response
            )
            
    except ValueError as e:
        logger.warning("Walk-forward validation request validation failed: {}", e)
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error("Unexpected error in walk-forward validation: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Walk-forward validation failed due to unexpected error"
        )


@router.get("/{account_name}/{hour}/{minute_bin}/walk-forward/results/{process_id}",
           response_model=APIResponse[Union[WalkForwardValidationResponse, BackgroundProcessResponse]],
           summary="Get Walk-Forward Validation Results",
           description="Get results from background walk-forward validation process.")
async def get_walk_forward_results(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    process_id: str = Path(description="Background process ID"),
    user_context: Dict[str, Any] = Depends(require_read_permission)
):
    """Get results from background walk-forward validation process."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    if process_id not in background_processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    process_info = background_processes[process_id]
    
    # Check if process is complete
    if process_info["status"] == "completed" and process_info["result"]:
        return APIResponse(
            status="success",
            message="Walk-forward validation completed",
            data=process_info["result"]
        )
    elif process_info["status"] == "failed":
        return APIResponse(
            status="error",
            message=f"Walk-forward validation failed: {process_info['error_message']}",
            data=None
        )
    else:
        # Return current progress
        current_time = datetime.now()
        elapsed_seconds = (current_time - process_info["start_time"]).total_seconds()
        
        process_response = BackgroundProcessResponse(
            process_id=process_id,
            process_type=process_info["process_type"],
            status=process_info["status"],
            progress_percentage=process_info["progress_percentage"],
            current_operation=process_info["current_operation"],
            start_time=process_info["start_time"],
            estimated_completion=process_info.get("estimated_completion"),
            elapsed_time_seconds=elapsed_seconds,
            result_url=f"/api/time-bins/{account_name}/{hour}/{minute_bin}/walk-forward/results/{process_id}",
            error_message=process_info.get("error_message")
        )
        
        return APIResponse(
            status="processing",
            message="Walk-forward validation in progress",
            data=process_response
        )


@router.get("/{account_name}/{hour}/{minute_bin}/robustness",
           response_model=APIResponse[StrategyRobustnessResponse],
           summary="Get Strategy Robustness Assessment",
           description="""
           Get comprehensive strategy robustness assessment including degradation analysis,
           performance trends, alerts, and actionable recommendations.
           
           Analyzes recent performance against historical baseline to detect degradation.
           """)
async def get_strategy_robustness(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    lookback_days: int = Query(default=30, ge=7, le=180,
                              description="Days to look back for recent performance"),
    baseline_days: int = Query(default=90, ge=30, le=365,
                              description="Days to look back for historical baseline"),
    sensitivity: float = Query(default=0.05, ge=0.01, le=0.2,
                              description="Degradation detection sensitivity"),
    db_session: Session = Depends(get_database_session),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    decay_tracker: PerformanceDecayTracker = Depends(get_decay_tracker)
):
    """Get strategy robustness assessment with degradation detection."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        robustness_id = f"rob_{account_name}_{hour:02d}{minute_bin:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        time_bin = TimeBin.from_time(hour, minute_bin)
        
        logger.info("Running robustness assessment {} for user {}", 
                   robustness_id, user_context.get("user_id", "unknown"))
        
        # Get performance history (mock implementation - would query database)
        recent_performance, historical_baseline = _get_performance_history(
            account_name, time_bin, lookback_days, baseline_days, db_session
        )
        
        if not recent_performance or not historical_baseline:
            raise DataNotFoundException(
                f"Insufficient performance data for {account_name} time-bin {time_bin}"
            )
        
        # Run degradation analysis
        degradation_result = decay_tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name=account_name,
            time_bin=time_bin
        )
        
        # Convert to API response
        api_response = _convert_degradation_result_to_api_response(
            degradation_result, robustness_id, account_name, hour, minute_bin
        )
        
        return APIResponse(
            status="success",
            message=f"Strategy robustness assessment completed",
            data=api_response
        )
        
    except DataNotFoundException as e:
        logger.warning("Robustness assessment data not found: {}", e)
        raise HTTPException(status_code=404, detail=str(e))
        
    except Exception as e:
        logger.error("Error in strategy robustness assessment: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Robustness assessment failed due to unexpected error"
        )


@router.get("/{account_name}/{hour}/{minute_bin}/decay-analysis",
           response_model=APIResponse[DecayAnalysisResponse],
           summary="Get Comprehensive Performance Decay Analysis",
           description="""
           Get comprehensive performance decay analysis including prediction accuracy,
           optimal retraining frequency, degradation assessment, and persistence testing.
           
           Provides complete strategy health monitoring and actionable recommendations.
           """)
async def get_decay_analysis(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    prediction_accuracy: Optional[PredictionAccuracyRequest] = None,
    retraining_analysis: Optional[RetrainingAnalysisRequest] = None,
    include_persistence: bool = Query(default=True, description="Include persistence analysis"),
    include_degradation: bool = Query(default=True, description="Include degradation analysis"),
    db_session: Session = Depends(get_database_session),
    user_context: Dict[str, Any] = Depends(require_read_permission),
    decay_tracker: PerformanceDecayTracker = Depends(get_decay_tracker)
):
    """Get comprehensive performance decay analysis."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    try:
        analysis_id = f"decay_{account_name}_{hour:02d}{minute_bin:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        time_bin = TimeBin.from_time(hour, minute_bin)
        
        logger.info("Running comprehensive decay analysis {} for user {}", 
                   analysis_id, user_context.get("user_id", "unknown"))
        
        # Initialize analysis results
        analysis_results = {
            "analysis_id": analysis_id,
            "account_name": account_name,
            "time_bin": f"{hour:02d}:{minute_bin:02d}",
        }
        
        # 1. Prediction accuracy analysis
        if prediction_accuracy:
            try:
                pred_result = await _run_prediction_accuracy_analysis(
                    account_name, time_bin, prediction_accuracy, db_session, decay_tracker
                )
                analysis_results["prediction_accuracy"] = _serialize_prediction_accuracy(pred_result)
            except Exception as e:
                logger.warning("Prediction accuracy analysis failed: {}", e)
                analysis_results["prediction_accuracy"] = {"error": str(e)}
        
        # 2. Retraining frequency analysis
        if retraining_analysis:
            try:
                retrain_result = await _run_retraining_analysis(
                    account_name, time_bin, retraining_analysis, db_session, decay_tracker
                )
                analysis_results["retraining_analysis"] = _serialize_retraining_analysis(retrain_result)
            except Exception as e:
                logger.warning("Retraining analysis failed: {}", e)
                analysis_results["retraining_analysis"] = {"error": str(e)}
        
        # 3. Strategy degradation assessment
        if include_degradation:
            try:
                # Get performance data for degradation analysis
                recent_performance, historical_baseline = _get_performance_history(
                    account_name, time_bin, 30, 90, db_session
                )
                
                if recent_performance and historical_baseline:
                    degradation_result = decay_tracker.detect_strategy_degradation(
                        recent_performance=recent_performance,
                        historical_baseline=historical_baseline,
                        account_name=account_name,
                        time_bin=time_bin
                    )
                    
                    robustness_id = f"rob_{analysis_id}"
                    degradation_response = _convert_degradation_result_to_api_response(
                        degradation_result, robustness_id, account_name, hour, minute_bin
                    )
                    analysis_results["degradation_assessment"] = degradation_response
                else:
                    analysis_results["degradation_assessment"] = {"error": "Insufficient performance data"}
            except Exception as e:
                logger.warning("Degradation analysis failed: {}", e)
                analysis_results["degradation_assessment"] = {"error": str(e)}
        
        # 4. Performance persistence analysis
        if include_persistence:
            try:
                persistence_result = await _run_persistence_analysis(
                    account_name, time_bin, db_session, decay_tracker
                )
                analysis_results["persistence_analysis"] = _serialize_persistence_analysis(persistence_result)
            except Exception as e:
                logger.warning("Persistence analysis failed: {}", e)
                analysis_results["persistence_analysis"] = {"error": str(e)}
        
        # 5. Calculate overall health score and priority actions
        overall_health_score, priority_actions = _calculate_overall_health_assessment(analysis_results)
        
        analysis_results["overall_health_score"] = overall_health_score
        analysis_results["priority_actions"] = priority_actions
        analysis_results["analysis_timestamp"] = datetime.now()
        
        # Convert to DecayAnalysisResponse format
        decay_response = DecayAnalysisResponse(**analysis_results)
        
        return APIResponse(
            status="success",
            message=f"Comprehensive decay analysis completed",
            data=decay_response
        )
        
    except Exception as e:
        logger.error("Error in comprehensive decay analysis: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Decay analysis failed due to unexpected error"
        )


@router.delete("/{account_name}/{hour}/{minute_bin}/walk-forward/{process_id}",
              response_model=APIResponse[Dict[str, Any]],
              summary="Cancel Walk-Forward Validation",
              description="Cancel a running background walk-forward validation process.")
async def cancel_walk_forward_validation(
    account_name: str = Path(description="Account name", example="IPS_TM_10"),
    hour: int = Path(description="Hour (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(description="Minute bin (0 or 30)", example=30),
    process_id: str = Path(description="Background process ID"),
    user_context: Dict[str, Any] = Depends(require_read_permission)
):
    """Cancel a running background walk-forward validation process."""
    
    if minute_bin not in [0, 30]:
        raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
    
    if process_id not in background_processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    process_info = background_processes[process_id]
    
    if process_info["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel process with status: {process_info['status']}"
        )
    
    # Cancel the process
    background_processes[process_id]["status"] = "cancelled"
    background_processes[process_id]["current_operation"] = "Cancelled by user"
    
    logger.info("Walk-forward validation {} cancelled by user {}", 
               process_id, user_context.get("user_id", "unknown"))
    
    return APIResponse(
        status="success",
        message=f"Walk-forward validation {process_id} cancelled successfully",
        data={"process_id": process_id, "cancelled": True}
    )


@router.get("/walk-forward/active-processes",
           response_model=APIResponse[List[BackgroundProcessResponse]],
           summary="Get Active Walk-Forward Processes",
           description="Get list of all active walk-forward validation processes.")
async def get_active_walk_forward_processes(
    user_context: Dict[str, Any] = Depends(require_read_permission)
):
    """Get list of all active walk-forward validation processes."""
    
    try:
        active_processes = []
        current_time = datetime.now()
        
        for process_id, process_info in background_processes.items():
            if process_info["status"] not in ["completed", "failed", "cancelled"]:
                elapsed_seconds = (current_time - process_info["start_time"]).total_seconds()
                
                process_response = BackgroundProcessResponse(
                    process_id=process_id,
                    process_type=process_info["process_type"],
                    status=process_info["status"],
                    progress_percentage=process_info["progress_percentage"],
                    current_operation=process_info["current_operation"],
                    start_time=process_info["start_time"],
                    estimated_completion=process_info.get("estimated_completion"),
                    elapsed_time_seconds=elapsed_seconds,
                    result_url=f"/api/time-bins/{process_info['account_name']}/{process_info['hour']}/{process_info['minute_bin']}/walk-forward/results/{process_id}",
                    error_message=process_info.get("error_message")
                )
                
                active_processes.append(process_response)
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(active_processes)} active walk-forward processes",
            data=active_processes
        )
        
    except Exception as e:
        logger.error("Error retrieving active walk-forward processes: {}", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve active processes"
        )


# Helper functions

async def _run_validation_background(
    process_id: str,
    service_request: ServiceRequest,
    validator: OutOfSampleValidator
):
    """Run walk-forward validation in background."""
    
    try:
        # Update status to running
        background_processes[process_id]["status"] = "running"
        background_processes[process_id]["current_operation"] = "Starting validation"
        background_processes[process_id]["progress_percentage"] = 5.0
        
        # Simulate progress updates (in real implementation, validator would provide progress callbacks)
        await asyncio.sleep(1)
        background_processes[process_id]["current_operation"] = "Processing validation periods"
        background_processes[process_id]["progress_percentage"] = 25.0
        
        # Run the actual validation
        if service_request.validation_method == "anchored_walk_forward":
            result = validator.anchored_walk_forward(service_request)
        elif service_request.validation_method == "rolling_window":
            result = validator.rolling_window_validation(service_request)
        elif service_request.validation_method == "expanding_window":
            result = validator.expanding_window_validation(service_request)
        elif service_request.validation_method == "time_series_cv":
            cv_config = CrossValidationConfig(n_splits=5, test_size_ratio=0.2, gap_days=2)
            result = validator.time_series_cross_validation(service_request, cv_config)
        else:
            raise ValueError(f"Unsupported validation method: {service_request.validation_method}")
        
        # Update progress
        background_processes[process_id]["progress_percentage"] = 80.0
        background_processes[process_id]["current_operation"] = "Generating response"
        
        # Convert result to API response
        process_info = background_processes[process_id]
        validation_id = f"wf_{process_info['account_name']}_{process_info['hour']:02d}{process_info['minute_bin']:02d}_{process_id}"
        
        api_response = _convert_validation_result_to_api_response(
            result, validation_id, process_info['account_name'], 
            process_info['hour'], process_info['minute_bin']
        )
        
        # Mark as completed
        background_processes[process_id]["status"] = "completed"
        background_processes[process_id]["progress_percentage"] = 100.0
        background_processes[process_id]["current_operation"] = "Completed"
        background_processes[process_id]["result"] = api_response
        
    except Exception as e:
        # Mark as failed
        background_processes[process_id]["status"] = "failed"
        background_processes[process_id]["error_message"] = str(e)
        background_processes[process_id]["current_operation"] = "Failed"
        logger.error("Background validation {} failed: {}", process_id, e)


def _estimate_validation_time(request: WalkForwardValidationRequest, account_name: str) -> int:
    """Estimate validation execution time in minutes."""
    
    # Parse dates
    start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
    total_days = (end_date - start_date).days
    
    # Estimate number of validation periods
    if request.validation_method == ValidationMethodEnum.TIME_SERIES_CV:
        periods = request.n_splits or 5
    else:
        periods = max(1, (total_days - request.min_in_sample_days) // request.step_days)
    
    # Base time per period (varies by method complexity)
    base_time_seconds = {
        ValidationMethodEnum.ANCHORED_WALK_FORWARD: 10,
        ValidationMethodEnum.ROLLING_WINDOW: 8,
        ValidationMethodEnum.EXPANDING_WINDOW: 12,
        ValidationMethodEnum.TIME_SERIES_CV: 15
    }.get(request.validation_method, 10)
    
    # Estimate total time
    total_seconds = periods * base_time_seconds
    return max(1, int(total_seconds / 60))  # Convert to minutes


def _get_performance_history(account_name: str, time_bin: TimeBin, 
                           lookback_days: int, baseline_days: int,
                           db_session: Session):
    """Get performance history for degradation analysis."""
    
    # Mock implementation - in real system would query database
    from ...services.walk_forward.out_of_sample_validator import PerformanceMetrics
    import numpy as np
    
    # Generate mock recent performance (simulating degradation)
    recent_performance = []
    for i in range(lookback_days // 5):  # One metric per 5-day period
        degradation_factor = 1.0 - (i * 0.02)  # Gradual degradation
        
        metrics = PerformanceMetrics(
            total_trades=25,
            winning_trades=int(15 * degradation_factor),
            losing_trades=int(10 / max(degradation_factor, 0.5)),
            win_rate=0.6 * degradation_factor,
            average_pnl=100.0 * degradation_factor,
            total_pnl=2500.0 * degradation_factor,
            average_winner=167.0 * degradation_factor,
            average_loser=-83.0 / max(degradation_factor, 0.5),
            largest_winner=400.0,
            largest_loser=-200.0,
            profit_factor=2.0 * degradation_factor,
            sharpe_ratio=1.2 * degradation_factor,
            max_drawdown_pct=8.0 / max(degradation_factor, 0.5),
            max_consecutive_losses=int(3 / max(degradation_factor, 0.5)),
            total_commission=62.5,
            avg_trade_duration_minutes=28.0,
            longest_drawdown_period_days=int(3 / max(degradation_factor, 0.5)),
            calmar_ratio=0.15 * degradation_factor
        )
        recent_performance.append(metrics)
    
    # Generate mock historical baseline (good performance)
    historical_baseline = []
    for i in range(baseline_days // 5):  # One metric per 5-day period
        metrics = PerformanceMetrics(
            total_trades=25,
            winning_trades=15,
            losing_trades=10,
            win_rate=0.6,
            average_pnl=100.0,
            total_pnl=2500.0,
            average_winner=167.0,
            average_loser=-83.0,
            largest_winner=400.0,
            largest_loser=-200.0,
            profit_factor=2.0,
            sharpe_ratio=1.2,
            max_drawdown_pct=8.0,
            max_consecutive_losses=3,
            total_commission=62.5,
            avg_trade_duration_minutes=28.0,
            longest_drawdown_period_days=3,
            calmar_ratio=0.15
        )
        historical_baseline.append(metrics)
    
    return recent_performance, historical_baseline


def _convert_validation_result_to_api_response(result, validation_id: str, 
                                             account_name: str, hour: int, minute_bin: int) -> WalkForwardValidationResponse:
    """Convert service validation result to API response."""
    
    # Convert period performances
    period_responses = []
    for period_perf in result.period_performances:
        # Convert performance metrics to response format
        in_sample_response = PerformanceMetricsResponse(
            total_trades=period_perf.in_sample_metrics.total_trades,
            winning_trades=period_perf.in_sample_metrics.winning_trades,
            losing_trades=period_perf.in_sample_metrics.losing_trades,
            win_rate=period_perf.in_sample_metrics.win_rate,
            average_pnl=period_perf.in_sample_metrics.average_pnl,
            total_pnl=period_perf.in_sample_metrics.total_pnl,
            profit_factor=period_perf.in_sample_metrics.profit_factor,
            sharpe_ratio=period_perf.in_sample_metrics.sharpe_ratio,
            max_drawdown_pct=period_perf.in_sample_metrics.max_drawdown_pct,
            calmar_ratio=period_perf.in_sample_metrics.calmar_ratio
        )
        
        out_of_sample_response = PerformanceMetricsResponse(
            total_trades=period_perf.out_of_sample_metrics.total_trades,
            winning_trades=period_perf.out_of_sample_metrics.winning_trades,
            losing_trades=period_perf.out_of_sample_metrics.losing_trades,
            win_rate=period_perf.out_of_sample_metrics.win_rate,
            average_pnl=period_perf.out_of_sample_metrics.average_pnl,
            total_pnl=period_perf.out_of_sample_metrics.total_pnl,
            profit_factor=period_perf.out_of_sample_metrics.profit_factor,
            sharpe_ratio=period_perf.out_of_sample_metrics.sharpe_ratio,
            max_drawdown_pct=period_perf.out_of_sample_metrics.max_drawdown_pct,
            calmar_ratio=period_perf.out_of_sample_metrics.calmar_ratio
        )
        
        period_response = PeriodPerformanceResponse(
            period_id=period_perf.period_id,
            in_sample_start=period_perf.in_sample_start,
            in_sample_end=period_perf.in_sample_end,
            out_of_sample_start=period_perf.out_of_sample_start,
            out_of_sample_end=period_perf.out_of_sample_end,
            in_sample_metrics=in_sample_response,
            out_of_sample_metrics=out_of_sample_response,
            trades_count_in_sample=period_perf.trades_count_in_sample,
            trades_count_out_of_sample=period_perf.trades_count_out_of_sample
        )
        
        period_responses.append(period_response)
    
    # Create analysis period info
    analysis_period = {
        "start_date": result.start_date.strftime("%Y-%m-%d") if hasattr(result, 'start_date') else "Unknown",
        "end_date": result.end_date.strftime("%Y-%m-%d") if hasattr(result, 'end_date') else "Unknown",
        "total_periods": len(period_responses)
    }
    
    return WalkForwardValidationResponse(
        validation_id=validation_id,
        validation_method=ValidationMethodEnum(result.validation_method.value),
        account_name=account_name,
        time_bin=f"{hour:02d}:{minute_bin:02d}",
        analysis_period=analysis_period,
        period_performances=period_responses,
        overall_metrics=result.overall_metrics,
        stability_analysis=result.stability_analysis,
        overfitting_analysis=result.overfitting_analysis,
        consistency_analysis=result.consistency_analysis,
        recommendation=result.recommendation,
        generation_timestamp=result.generation_timestamp
    )


def _convert_degradation_result_to_api_response(result, robustness_id: str,
                                              account_name: str, hour: int, minute_bin: int) -> StrategyRobustnessResponse:
    """Convert degradation result to API response."""
    
    # Convert alerts
    alert_responses = []
    for alert in result.active_alerts:
        alert_response = DegradationAlertResponse(
            alert_type=alert.alert_type.value,
            severity=DegradationSeverityEnum(alert.severity.value),
            message=alert.message,
            metric_name=alert.metric_name,
            current_value=alert.current_value,
            threshold_value=alert.threshold_value,
            confidence_level=alert.confidence_level,
            detected_at=alert.detected_at,
            recommended_action=alert.recommended_action
        )
        alert_responses.append(alert_response)
    
    return StrategyRobustnessResponse(
        robustness_id=robustness_id,
        account_name=account_name,
        time_bin=f"{hour:02d}:{minute_bin:02d}",
        overall_robustness_score=result.overall_degradation_score,
        degradation_severity=DegradationSeverityEnum(result.degradation_severity.value),
        active_alerts=alert_responses,
        performance_trends=result.performance_trend,
        time_to_failure_estimate=result.time_to_failure_estimate,
        confidence_in_assessment=result.confidence_in_degradation,
        key_degraded_metrics=result.key_degraded_metrics,
        recommendation=result.recommendation,
        next_monitoring_interval_hours=result.next_monitoring_interval.total_seconds() / 3600.0,
        analysis_timestamp=result.calculation_timestamp
    )


async def _run_prediction_accuracy_analysis(account_name: str, time_bin: TimeBin,
                                          request: PredictionAccuracyRequest,
                                          db_session: Session,
                                          decay_tracker: PerformanceDecayTracker):
    """Run prediction accuracy analysis."""
    
    # Mock implementation - would get actual trades and predictions from database
    from datetime import timedelta
    import numpy as np
    
    # Generate mock data
    prediction_dates = [datetime.now() - timedelta(days=i) for i in range(request.prediction_period_days)]
    predicted_returns = [np.random.uniform(-50, 100) for _ in prediction_dates]
    
    # Mock trades (would query from database)
    actual_trades = []
    for i, date in enumerate(prediction_dates):
        trade = type('MockTrade', (), {})()
        trade.trade_id = i + 1
        trade.entry_time = date.replace(hour=time_bin.hour, minute=time_bin.minute)
        trade.net_pnl = predicted_returns[i] + np.random.uniform(-25, 25)
        trade.time_bin = time_bin
        actual_trades.append(trade)
    
    return decay_tracker.track_prediction_accuracy(
        actual_trades=actual_trades,
        predicted_returns=predicted_returns,
        prediction_dates=prediction_dates,
        account_name=account_name,
        time_bin=time_bin
    )


async def _run_retraining_analysis(account_name: str, time_bin: TimeBin,
                                 request: RetrainingAnalysisRequest,
                                 db_session: Session,
                                 decay_tracker: PerformanceDecayTracker):
    """Run retraining frequency analysis."""
    
    # Mock performance history and training dates
    performance_history, _ = _get_performance_history(account_name, time_bin, request.lookback_days, request.lookback_days, db_session)
    
    # Convert to (datetime, metrics) tuples
    perf_history_with_dates = []
    base_date = datetime.now() - timedelta(days=request.lookback_days)
    for i, metrics in enumerate(performance_history):
        date = base_date + timedelta(days=i * 5)
        perf_history_with_dates.append((date, metrics))
    
    # Mock training dates
    training_dates = [
        datetime.now() - timedelta(days=request.lookback_days),
        datetime.now() - timedelta(days=request.lookback_days // 2),
        datetime.now() - timedelta(days=request.lookback_days // 4)
    ]
    
    return decay_tracker.identify_optimal_retraining_frequency(
        performance_history=perf_history_with_dates,
        model_training_dates=training_dates,
        account_name=account_name,
        time_bin=time_bin
    )


async def _run_persistence_analysis(account_name: str, time_bin: TimeBin,
                                  db_session: Session,
                                  decay_tracker: PerformanceDecayTracker):
    """Run performance persistence analysis."""
    
    # Mock performance history
    performance_history, _ = _get_performance_history(account_name, time_bin, 60, 60, db_session)
    
    # Convert to (datetime, metrics) tuples
    perf_history_with_dates = []
    base_date = datetime.now() - timedelta(days=60)
    for i, metrics in enumerate(performance_history):
        date = base_date + timedelta(days=i * 5)
        perf_history_with_dates.append((date, metrics))
    
    return decay_tracker.test_performance_persistence(
        performance_history=perf_history_with_dates,
        account_name=account_name,
        time_bin=time_bin,
        max_lag=5
    )


def _serialize_prediction_accuracy(result) -> Dict[str, Any]:
    """Serialize prediction accuracy result."""
    return {
        "predictions_count": result.predictions_count,
        "correlation_coefficient": result.correlation_coefficient,
        "directional_accuracy": result.directional_accuracy,
        "hit_ratio": result.hit_ratio,
        "mean_squared_error": result.mean_squared_error,
        "r_squared": result.r_squared,
        "accuracy_trend": result.accuracy_trend,
        "prediction_bias": result.prediction_bias
    }


def _serialize_retraining_analysis(result) -> Dict[str, Any]:
    """Serialize retraining analysis result."""
    return {
        "current_model_age_days": result.current_model_age_days,
        "optimal_retraining_days": result.optimal_retraining_days,
        "performance_decay_rate": result.performance_decay_rate,
        "retraining_benefit_score": result.retraining_benefit_score,
        "next_recommended_retraining": result.next_recommended_retraining.isoformat(),
        "retraining_frequency_recommendation": result.retraining_frequency_recommendation
    }


def _serialize_persistence_analysis(result) -> Dict[str, Any]:
    """Serialize persistence analysis result."""
    return {
        "persistence_score": result.persistence_score,
        "mean_reversion_tendency": result.mean_reversion_tendency,
        "autocorrelation_lag_1": result.performance_autocorrelation.get(1, 0.0),
        "predictability_score": result.predictability_metrics.get("predictability_score", 0.0),
        "momentum_periods_count": len(result.momentum_periods),
        "reversal_periods_count": len(result.reversal_periods)
    }


def _calculate_overall_health_assessment(analysis_results: Dict[str, Any]) -> tuple:
    """Calculate overall health score and priority actions."""
    
    scores = []
    actions = []
    
    # Evaluate degradation assessment
    if "degradation_assessment" in analysis_results and "error" not in analysis_results["degradation_assessment"]:
        degradation = analysis_results["degradation_assessment"]
        health_score = 1.0 - degradation.overall_robustness_score  # Invert degradation score
        scores.append(health_score)
        
        if degradation.degradation_severity in ["severe", "critical"]:
            actions.append("URGENT: Address critical strategy degradation")
        elif degradation.active_alerts:
            actions.append("Monitor degradation alerts closely")
    
    # Evaluate prediction accuracy
    if "prediction_accuracy" in analysis_results and "error" not in analysis_results["prediction_accuracy"]:
        pred_acc = analysis_results["prediction_accuracy"]
        if pred_acc.get("correlation_coefficient", 0) < 0.3:
            actions.append("Investigate poor prediction accuracy")
        if pred_acc.get("accuracy_trend", 0) < -0.01:
            actions.append("Address declining prediction accuracy trend")
    
    # Evaluate retraining analysis
    if "retraining_analysis" in analysis_results and "error" not in analysis_results["retraining_analysis"]:
        retrain = analysis_results["retraining_analysis"]
        if retrain.get("performance_decay_rate", 0) > 0.01:
            actions.append("Schedule model retraining soon due to high decay rate")
    
    # Calculate overall score
    if scores:
        overall_health_score = sum(scores) / len(scores)
    else:
        overall_health_score = 0.5  # Neutral if no data
    
    # Add default action if none identified
    if not actions:
        actions.append("Continue regular monitoring")
    
    return overall_health_score, actions[:5]  # Limit to top 5 actions