"""
Time-bin analytics API endpoints.

This module provides REST endpoints for time-bin specific performance analysis
and recommendations.

Requirements: 1.1, 1.6, 4.4, 10.1
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
import logging

from ..dependencies import (
    get_database_session,
    require_read_permission
)
from ..models.common import APIResponse
from ..models.time_bin_analytics import (
    TimeBinAnalysisResponse,
    TimeBinMetricsResponse,
    SignificanceTestResponse,
    TimeBinComparisonRequest,
    TimeBinComparisonResponse,
    AccountRecommendationsRequest,
    AccountRecommendationsResponse,
    TimeBinRecommendation,
    InsufficientDataError,
    # Market Correlation Models
    MarketCorrelationResponse,
    BenchmarkComparisonResponse,
    RegimeAnalysisResponse,
    MarketDataSyncRequest,
    MarketDataSyncResponse,
    BetaCoefficientsResponse,
    AlphaMetricsResponse,
    MarketNeutralityResponse,
    CorrelationStabilityResponse,
    VixRegimePerformanceResponse,
    RegimeTransitionResponse
)
from ..exceptions import DataNotFoundException, ServiceException
from ...services.time_bin_analyzer import TimeBinAnalyzer, TimeBin
from ...services.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
from ...services.vix_regime_analyzer import VIXDataIntegration
from ...services.market_data_ingestion import MarketDataIngestion


router = APIRouter()
logger = logging.getLogger(__name__)


def get_time_bin_analyzer(db: Session = Depends(get_database_session)) -> TimeBinAnalyzer:
    """Dependency to get TimeBinAnalyzer instance."""
    return TimeBinAnalyzer(db_session=db)


def get_benchmark_analyzer(db: Session = Depends(get_database_session)) -> BenchmarkComparisonAnalyzer:
    """Dependency to get BenchmarkComparisonAnalyzer instance."""
    return BenchmarkComparisonAnalyzer(db_session=db)


def _check_wfa_gate(db: Session, account_name: str, hour: int, minute_bin: int) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Check if a time-bin passes Walk-Forward Analysis (WFA) out-of-sample gating.

    Returns:
        (is_passed, status_code, details_dict)
        status_code: 'validated', 'pending_validation', or 'failed_validation'
    """
    try:
        from ...models.time_bin_analytics import TimeBinAnalysis, WalkForwardResult

        wfr = (
            db.query(WalkForwardResult)
            .join(TimeBinAnalysis, WalkForwardResult.time_bin_analysis_id == TimeBinAnalysis.id)
            .filter(
                TimeBinAnalysis.account_name == account_name,
                TimeBinAnalysis.hour == hour,
                TimeBinAnalysis.minute_bin == minute_bin
            )
            .order_by(WalkForwardResult.created_timestamp.desc())
            .first()
        )

        if not wfr:
            return False, "pending_validation", {
                "reason": "No Walk-Forward validation record found in database. Validation run required."
            }

        # Check OOS performance gates
        sharpe_ok = wfr.oos_sharpe_ratio is not None and wfr.oos_sharpe_ratio > 0.0

        drawdown_bound = -500.0
        if wfr.oos_avg_pnl_per_trade is not None and wfr.oos_avg_pnl_per_trade > 0:
            drawdown_bound = -3.0 * wfr.oos_avg_pnl_per_trade

        drawdown_ok = True
        if wfr.oos_max_drawdown is not None:
            drawdown_ok = wfr.oos_max_drawdown > drawdown_bound

        details = {
            "oos_sharpe_ratio": wfr.oos_sharpe_ratio,
            "oos_max_drawdown": wfr.oos_max_drawdown,
            "validation_scheme": wfr.validation_scheme,
            "prediction_error": wfr.prediction_error
        }

        if sharpe_ok and drawdown_ok:
            return True, "validated", details
        else:
            details["failure_reason"] = (
                f"OOS Sharpe={wfr.oos_sharpe_ratio} (must be > 0) or "
                f"OOS MaxDD={wfr.oos_max_drawdown} (must be > {drawdown_bound:.2f})"
            )
            return False, "failed_validation", details

    except Exception as e:
        logger.warning(f"Error checking WFA gate for {account_name} {hour}:{minute_bin:02d}: {e}")
        return False, "pending_validation", {"reason": f"WFA gate query error: {str(e)}"}



def get_vix_analyzer(db: Session = Depends(get_database_session)) -> VIXDataIntegration:
    """Dependency to get VIXDataIntegration instance."""
    return VIXDataIntegration(db_session=db)


def get_market_data_service(db: Session = Depends(get_database_session)) -> MarketDataIngestion:
    """Dependency to get MarketDataIngestion instance."""
    return MarketDataIngestion(db_session=db)


@router.get(
    "/{account}/{hour}/{minute_bin}/analysis",
    response_model=APIResponse[TimeBinAnalysisResponse],
    summary="Get time-bin analysis",
    description="Analyze performance for a specific account/30-minute time bin combination with statistical significance testing."
)
async def get_time_bin_analysis(
    account: str = Path(..., description="Account name", example="IPS_TM_10"),
    hour: int = Path(..., description="Hour of day (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(..., description="Minute bin (0 or 30)", example=30),
    day_of_week: Optional[int] = Query(None, description="Day of week (0=Monday, 6=Sunday)", ge=0, le=6),
    db: Session = Depends(get_database_session),
    analyzer: TimeBinAnalyzer = Depends(get_time_bin_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[TimeBinAnalysisResponse]:
    """
    Get comprehensive analysis for a specific time bin.
    
    Requirements:
    - 1.1: Retrieve and display trades within specific 30-minute window
    - 1.2: Calculate Sharpe, Calmar, Sortino ratios for time window
    - 1.3: Calculate rolling performance metrics
    - 4.4: Statistical significance based on trade sample
    """
    
    logger.info(f"[TIME-BIN ANALYSIS] Analyzing {account} {hour:02d}:{minute_bin:02d}")
    
    try:
        # Validate minute_bin
        if minute_bin not in [0, 30]:
            raise HTTPException(
                status_code=400, 
                detail="Minute bin must be 0 or 30"
            )
        
        # Create time bin
        time_bin = TimeBin(
            account_name=account,
            hour=hour,
            minute_bin=minute_bin,
            day_of_week=day_of_week
        )
        
        # Perform analysis
        metrics, significance_tests = analyzer.analyze_time_bin(time_bin)
        
        # Check for insufficient data
        if metrics.total_trades == 0:
            error_details = InsufficientDataError(
                error_type="INSUFFICIENT_DATA",
                message=f"No trades found for time bin {time_bin}",
                details={
                    "trades_found": 0,
                    "minimum_required": analyzer.minimum_sample_size,
                    "time_bin": str(time_bin),
                    "suggestion": "Try a different time window or account with more trading history"
                },
                recommendations=[
                    "Check if the account name is correct",
                    "Verify that trading occurred during this time window",
                    "Try analyzing a broader time period",
                    "Consider using a different account with more activity"
                ]
            )
            
            raise HTTPException(
                status_code=404,
                detail=error_details.dict()
            )
        
        # Get data period information
        trades = analyzer.get_time_bin_trades(time_bin)
        data_period = {}
        if trades:
            entry_times = [trade.entry_time for trade in trades]
            data_period = {
                "earliest_trade": min(entry_times).isoformat(),
                "latest_trade": max(entry_times).isoformat(),
                "total_trading_days": len(set(trade.entry_time.date() for trade in trades))
            }
        
        # Convert metrics to response model
        metrics_response = TimeBinMetricsResponse(
            time_bin_id=str(time_bin),
            account_name=metrics.time_bin.account_name,
            hour=metrics.time_bin.hour,
            minute_bin=metrics.time_bin.minute_bin,
            day_of_week=metrics.time_bin.day_of_week,
            total_trades=metrics.total_trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            win_rate=metrics.win_rate * 100,  # Convert to percentage
            total_pnl=metrics.total_pnl,
            average_pnl=metrics.average_pnl,
            average_win=metrics.average_win,
            average_loss=metrics.average_loss,
            max_drawdown=metrics.max_drawdown,
            volatility=metrics.volatility,
            profit_factor=metrics.profit_factor,
            largest_win=metrics.largest_win,
            largest_loss=metrics.largest_loss,
            sharpe_ratio=metrics.sharpe_ratio,
            calmar_ratio=metrics.calmar_ratio,
            sortino_ratio=metrics.sortino_ratio,
            confidence_interval_95=metrics.confidence_interval_95,
            p_value_vs_random=metrics.p_value_vs_random,
            statistical_significance=metrics.statistical_significance,
            minimum_sample_size_met=metrics.minimum_sample_size_met,
            expectancy=metrics.expectancy,
            recovery_factor=metrics.recovery_factor
        )
        
        # Convert significance tests to response models
        significance_responses = [
            SignificanceTestResponse(
                test_name=test.test_name,
                p_value=test.p_value,
                is_significant=test.is_significant,
                confidence_level=test.confidence_level,
                test_statistic=test.test_statistic,
                critical_value=test.critical_value,
                interpretation=test.interpretation
            )
            for test in significance_tests
        ]
        
        # Create analysis response
        analysis_response = TimeBinAnalysisResponse(
            metrics=metrics_response,
            significance_tests=significance_responses,
            analysis_timestamp=datetime.now(),
            data_period=data_period
        )
        
        logger.info(f"[TIME-BIN ANALYSIS] SUCCESS: {account} {hour:02d}:{minute_bin:02d} - {metrics.total_trades} trades")
        
        return APIResponse[TimeBinAnalysisResponse](
            status="success",
            message=f"Time-bin analysis completed for {account} {hour:02d}:{minute_bin:02d}",
            data=analysis_response
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[TIME-BIN ANALYSIS] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[TIME-BIN ANALYSIS] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze time bin: {str(e)}")


@router.post(
    "/compare",
    response_model=APIResponse[TimeBinComparisonResponse],
    summary="Compare multiple time bins",
    description="Compare performance across multiple account/time-bin combinations with statistical testing."
)
async def compare_time_bins(
    request: TimeBinComparisonRequest,
    db: Session = Depends(get_database_session),
    analyzer: TimeBinAnalyzer = Depends(get_time_bin_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[TimeBinComparisonResponse]:
    """
    Compare multiple time bins with statistical analysis.
    
    Requirements:
    - 1.5: Statistical tests for performance differences between time windows
    - 5.2: Multiple comparison correction for statistical rigor
    """
    
    logger.info(f"[TIME-BIN COMPARISON] Comparing {len(request.time_bins)} time bins")
    
    try:
        if len(request.time_bins) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 time bins required for comparison"
            )
        
        # Analyze each time bin
        time_bin_analyses = []
        time_bin_objects = []
        
        for tb_request in request.time_bins:
            # Validate minute_bin
            if tb_request.minute_bin not in [0, 30]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid minute_bin {tb_request.minute_bin} for {tb_request.account_name}. Must be 0 or 30."
                )
            
            # Create time bin
            time_bin = TimeBin(
                account_name=tb_request.account_name,
                hour=tb_request.hour,
                minute_bin=tb_request.minute_bin,
                day_of_week=tb_request.day_of_week
            )
            time_bin_objects.append(time_bin)
            
            # Analyze time bin
            metrics, significance_tests = analyzer.analyze_time_bin(time_bin)
            
            # Get data period
            trades = analyzer.get_time_bin_trades(time_bin)
            data_period = {}
            if trades:
                entry_times = [trade.entry_time for trade in trades]
                data_period = {
                    "earliest_trade": min(entry_times).isoformat(),
                    "latest_trade": max(entry_times).isoformat(),
                    "total_trading_days": len(set(trade.entry_time.date() for trade in trades))
                }
            
            # Convert to response models
            metrics_response = TimeBinMetricsResponse(
                time_bin_id=str(time_bin),
                account_name=metrics.time_bin.account_name,
                hour=metrics.time_bin.hour,
                minute_bin=metrics.time_bin.minute_bin,
                day_of_week=metrics.time_bin.day_of_week,
                total_trades=metrics.total_trades,
                winning_trades=metrics.winning_trades,
                losing_trades=metrics.losing_trades,
                win_rate=metrics.win_rate * 100,
                total_pnl=metrics.total_pnl,
                average_pnl=metrics.average_pnl,
                average_win=metrics.average_win,
                average_loss=metrics.average_loss,
                max_drawdown=metrics.max_drawdown,
                volatility=metrics.volatility,
                profit_factor=metrics.profit_factor,
                largest_win=metrics.largest_win,
                largest_loss=metrics.largest_loss,
                sharpe_ratio=metrics.sharpe_ratio,
                calmar_ratio=metrics.calmar_ratio,
                sortino_ratio=metrics.sortino_ratio,
                confidence_interval_95=metrics.confidence_interval_95,
                p_value_vs_random=metrics.p_value_vs_random,
                statistical_significance=metrics.statistical_significance,
                minimum_sample_size_met=metrics.minimum_sample_size_met,
                expectancy=metrics.expectancy,
                recovery_factor=metrics.recovery_factor
            )
            
            significance_responses = [
                SignificanceTestResponse(
                    test_name=test.test_name,
                    p_value=test.p_value,
                    is_significant=test.is_significant,
                    confidence_level=test.confidence_level,
                    test_statistic=test.test_statistic,
                    critical_value=test.critical_value,
                    interpretation=test.interpretation
                )
                for test in significance_tests
            ]
            
            analysis_response = TimeBinAnalysisResponse(
                metrics=metrics_response,
                significance_tests=significance_responses,
                analysis_timestamp=datetime.now(),
                data_period=data_period
            )
            
            time_bin_analyses.append(analysis_response)
        
        # Create ranking based on sort criteria
        sort_key = request.sort_by
        reverse_sort = request.sort_order == "desc"
        
        # Get sort values
        sort_values = []
        for analysis in time_bin_analyses:
            if hasattr(analysis.metrics, sort_key):
                value = getattr(analysis.metrics, sort_key)
                sort_values.append((analysis, value if value is not None else -float('inf')))
            else:
                sort_values.append((analysis, -float('inf')))
        
        # Sort by the specified metric
        sort_values.sort(key=lambda x: x[1], reverse=reverse_sort)
        
        # Create ranking
        ranking = []
        for rank, (analysis, value) in enumerate(sort_values, 1):
            ranking.append({
                "rank": rank,
                "time_bin_id": analysis.metrics.time_bin_id,
                "value": value if value != -float('inf') else None
            })
        
        # Statistical comparisons (if requested)
        statistical_comparisons = []
        if request.include_statistical_tests and len(time_bin_objects) >= 2:
            # Perform pairwise comparisons
            for i in range(len(time_bin_objects)):
                for j in range(i + 1, len(time_bin_objects)):
                    comparison = analyzer.compare_time_bins(time_bin_objects[i], time_bin_objects[j])
                    
                    if "error" not in comparison:
                        statistical_comparisons.append({
                            "time_bin_1": str(time_bin_objects[i]),
                            "time_bin_2": str(time_bin_objects[j]),
                            "comparison": comparison["statistical_comparison"],
                            "performance_difference": comparison["performance_difference"]
                        })
        
        # Identify best time bin
        best_analysis = sort_values[0][0] if sort_values else None
        best_time_bin = None
        if best_analysis:
            best_time_bin = {
                "time_bin_id": best_analysis.metrics.time_bin_id,
                "metric_value": sort_values[0][1],
                "statistical_significance": best_analysis.metrics.statistical_significance
            }
        
        # Create comparison response
        comparison_response = TimeBinComparisonResponse(
            time_bins=time_bin_analyses,
            ranking=ranking,
            statistical_comparisons=statistical_comparisons if request.include_statistical_tests else None,
            best_time_bin=best_time_bin
        )
        
        logger.info(f"[TIME-BIN COMPARISON] SUCCESS: Compared {len(request.time_bins)} time bins")
        
        return APIResponse[TimeBinComparisonResponse](
            status="success",
            message=f"Successfully compared {len(request.time_bins)} time bins",
            data=comparison_response
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[TIME-BIN COMPARISON] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[TIME-BIN COMPARISON] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compare time bins: {str(e)}")


@router.get(
    "/{account}/recommendations",
    response_model=APIResponse[AccountRecommendationsResponse],
    summary="Get account recommendations",
    description="Get recommended time bins for an account based on performance criteria and statistical significance."
)
async def get_account_recommendations(
    account: str = Path(..., description="Account name", example="IPS_TM_10"),
    min_trades: int = Query(30, description="Minimum trades required", ge=10),
    min_win_rate: float = Query(50.0, description="Minimum win rate percentage", ge=0.0, le=100.0),
    min_average_pnl: float = Query(0.0, description="Minimum average P&L"),
    include_statistical_significance: bool = Query(True, description="Require statistical significance"),
    max_recommendations: int = Query(10, description="Maximum recommendations", ge=1, le=50),
    db: Session = Depends(get_database_session),
    analyzer: TimeBinAnalyzer = Depends(get_time_bin_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[AccountRecommendationsResponse]:
    """
    Get time-bin recommendations for an account.
    
    Requirements:
    - 1.6: Provide intelligent trading suggestions for specific time windows
    - 4.4: Statistical significance of time-bin performance
    - 5.1: Statistical confidence testing
    """
    
    logger.info(f"[ACCOUNT RECOMMENDATIONS] Getting recommendations for {account}")

    try:
        # --- Collect all slots and apply BH correction in one family ---
        # BH requires the complete set of p-values to be evaluated together.
        # analyze_all_bins_with_bh() does this correctly and sets
        # metrics.adjusted_p_value and metrics.bh_significant on each result.
        all_results = analyzer.analyze_all_bins_with_bh(account=account)

        # Analyze each time bin and filter by criteria
        candidate_recommendations = []
        total_analyzed = 0
        meeting_criteria = 0
        warnings = []

        for metrics, significance_tests in all_results:
            # Skip sentinel entries (exceptions during individual slot analysis)
            if metrics is None:
                continue

            total_analyzed += 1
            time_bin = metrics.time_bin

            # Skip if no trades
            if metrics.total_trades == 0:
                continue

            # Apply filters
            meets_criteria = True

            # Minimum trades filter
            if metrics.total_trades < min_trades:
                meets_criteria = False

            # Win rate filter
            if metrics.win_rate * 100 < min_win_rate:
                meets_criteria = False

            # Average P&L filter
            if metrics.average_pnl < min_average_pnl:
                meets_criteria = False

            # Statistical significance filter (BH-corrected gate)
            if include_statistical_significance and not metrics.bh_significant:
                meets_criteria = False

            if meets_criteria:
                meeting_criteria += 1

                # Calculate recommendation score (weighted combination of metrics)
                score = (
                    metrics.average_pnl * 0.4 +
                    (metrics.win_rate * 100) * 0.3 +
                    (metrics.sharpe_ratio or 0) * 10 * 0.2 +
                    metrics.profit_factor * 5 * 0.1
                )

                # Determine confidence level
                if metrics.bh_significant and metrics.minimum_sample_size_met:
                    if metrics.total_trades >= 100:
                        confidence = "High"
                    elif metrics.total_trades >= 50:
                        confidence = "Medium"
                    else:
                        confidence = "Low"
                else:
                    confidence = "Low"

                # Determine risk assessment
                if abs(metrics.max_drawdown) > metrics.average_pnl * 10:
                    risk = "High"
                elif abs(metrics.max_drawdown) > metrics.average_pnl * 5:
                    risk = "Medium"
                else:
                    risk = "Low"

                # Create recommendation reason
                reasons = []
                if metrics.average_pnl > min_average_pnl * 2:
                    reasons.append("strong average P&L")
                if metrics.win_rate > 0.6:
                    reasons.append("good win rate")
                if metrics.bh_significant:
                    reasons.append("FDR-corrected statistical significance")
                if metrics.sharpe_ratio and metrics.sharpe_ratio > 1.0:
                    reasons.append("good risk-adjusted returns")

                recommendation_reason = (
                    f"Recommended due to {', '.join(reasons) if reasons else 'meeting basic criteria'}"
                )

                candidate_recommendations.append({
                    "time_bin": time_bin,
                    "metrics": metrics,
                    "score": score,
                    "confidence": confidence,
                    "risk": risk,
                    "reason": recommendation_reason
                })
        
        # Sort by score and take top recommendations
        candidate_recommendations.sort(key=lambda x: x["score"], reverse=True)

        # --- Walk-Forward Analysis (WFA) Gating ---
        # Gate recommendations: candidates must pass out-of-sample validation.
        # Candidates without WFA records go to pending_validation.
        # Candidates with failing OOS Sharpe/MaxDD go to failed_wfa.
        validated_candidates = []
        pending_validation_list = []
        failed_wfa_list = []

        for rec in candidate_recommendations:
            tb = rec["time_bin"]
            is_passed, status, wfa_details = _check_wfa_gate(db, account, tb.hour, tb.minute_bin)

            slot_info = {
                "time_bin_id": str(tb),
                "hour": tb.hour,
                "minute_bin": tb.minute_bin,
                "score": rec["score"],
                "average_pnl": rec["metrics"].average_pnl,
                "win_rate": rec["metrics"].win_rate * 100,
                "wfa_details": wfa_details
            }

            if is_passed:
                validated_candidates.append(rec)
            elif status == "pending_validation":
                pending_validation_list.append(slot_info)
            else:
                failed_wfa_list.append(slot_info)

        top_recommendations = validated_candidates[:max_recommendations]

        # Check for warnings
        if meeting_criteria < 5:
            warnings.append(
                "Few time bins met the specified criteria (BH-corrected). "
                "Consider relaxing filters or running more trades."
            )

        if pending_validation_list:
            warnings.append(
                f"{len(pending_validation_list)} time bins met statistical criteria but are pending Walk-Forward Analysis (WFA) validation."
            )

        if failed_wfa_list:
            warnings.append(
                f"{len(failed_wfa_list)} time bins were rejected due to failing Walk-Forward out-of-sample validation."
            )

        if total_analyzed < 48:
            warnings.append("Some time bins could not be analyzed due to data issues.")

        insufficient_data_count = sum(
            1 for rec in candidate_recommendations
            if not rec["metrics"].minimum_sample_size_met
        )
        if insufficient_data_count > 0:
            warnings.append(
                f"{insufficient_data_count} time bins had insufficient data for statistical significance testing"
            )

        # Convert to response models
        recommendations = []
        for rank, rec in enumerate(top_recommendations, 1):
            time_bin = rec["time_bin"]
            metrics = rec["metrics"]

            recommendation = TimeBinRecommendation(
                rank=rank,
                time_bin_id=str(time_bin),
                hour=time_bin.hour,
                minute_bin=time_bin.minute_bin,
                day_of_week=time_bin.day_of_week,
                score=rec["score"],
                key_metrics={
                    "average_pnl": metrics.average_pnl,
                    "win_rate": metrics.win_rate * 100,
                    "total_trades": float(metrics.total_trades),
                    "sharpe_ratio": float(metrics.sharpe_ratio or 0.0),
                    # BH-corrected significance (the decision field)
                    "adjusted_p_value": float(metrics.adjusted_p_value) if metrics.adjusted_p_value is not None else -1.0,
                    "raw_p_value": float(metrics.p_value_vs_random) if metrics.p_value_vs_random is not None else -1.0,
                    "bh_significant": 1.0 if metrics.bh_significant else 0.0,
                },
                confidence_level=rec["confidence"],
                risk_assessment=rec["risk"],
                recommendation_reason=rec["reason"]
            )
            recommendations.append(recommendation)
        
        # Create analysis summary
        analysis_summary = {
            "total_time_bins_analyzed": total_analyzed,
            "time_bins_meeting_criteria": meeting_criteria,
            "time_bins_wfa_validated": len(validated_candidates),
            "time_bins_wfa_pending": len(pending_validation_list),
            "time_bins_wfa_failed": len(failed_wfa_list),
            "best_overall_metric": "average_pnl",
            "analysis_period_days": 365
        }
        
        # Create filters applied summary
        filters_applied = {
            "min_trades": min_trades,
            "min_win_rate": min_win_rate,
            "min_average_pnl": min_average_pnl,
            "statistical_significance_required": include_statistical_significance,
            "walk_forward_gating_enabled": True
        }
        
        # Create response
        recommendations_response = AccountRecommendationsResponse(
            account_name=account,
            recommendations=recommendations,
            analysis_summary=analysis_summary,
            filters_applied=filters_applied,
            warnings=warnings,
            pending_validation=pending_validation_list,
            failed_wfa=failed_wfa_list
        )
        
        logger.info(f"[ACCOUNT RECOMMENDATIONS] SUCCESS: {account} - {len(recommendations)} recommendations")
        
        return APIResponse[AccountRecommendationsResponse](
            status="success",
            message=f"Generated {len(recommendations)} recommendations for {account}",
            data=recommendations_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ACCOUNT RECOMMENDATIONS] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


# Market Correlation and Benchmark Analysis Endpoints

@router.get(
    "/{account}/{hour}/{minute_bin}/market-correlation",
    response_model=APIResponse[MarketCorrelationResponse],
    summary="Get market correlation analysis",
    description="Analyze market correlation and beta coefficients for a specific time-bin strategy."
)
async def get_market_correlation(
    account: str = Path(..., description="Account name", example="IPS_TM_10"),
    hour: int = Path(..., description="Hour of day (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(..., description="Minute bin (0 or 30)", example=30),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis"),
    db: Session = Depends(get_database_session),
    benchmark_analyzer: BenchmarkComparisonAnalyzer = Depends(get_benchmark_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[MarketCorrelationResponse]:
    """
    Get market correlation analysis for a specific time-bin.
    
    Requirements:
    - 11.3: Beta coefficient calculations for market correlation
    - 11.6: Correlation stability analysis for time-varying analysis
    """
    
    logger.info(f"[MARKET CORRELATION] Analyzing {account} {hour}:{minute_bin:02d}")
    
    try:
        # Validate minute bin
        if minute_bin not in [0, 30]:
            raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
        
        # Calculate beta coefficients
        beta_coefficients = benchmark_analyzer.calculate_beta_coefficients(
            account, start_date, end_date, hour, minute_bin
        )
        
        # Calculate correlation stability
        correlation_stability = benchmark_analyzer.calculate_correlation_stability(
            account, start_date, end_date, hour, minute_bin
        )
        
        # Determine analysis period
        analysis_period = {
            "start_date": start_date.isoformat() if start_date else "automatic",
            "end_date": end_date.isoformat() if end_date else "automatic",
            "calculation_period_days": beta_coefficients.calculation_period_days,
            "sample_size": beta_coefficients.sample_size
        }
        
        # Convert to response models
        beta_response = BetaCoefficientsResponse(
            spy_beta=beta_coefficients.spy_beta,
            qqq_beta=beta_coefficients.qqq_beta,
            spy_r_squared=beta_coefficients.spy_r_squared,
            qqq_r_squared=beta_coefficients.qqq_r_squared,
            spy_correlation=beta_coefficients.spy_correlation,
            qqq_correlation=beta_coefficients.qqq_correlation,
            sample_size=beta_coefficients.sample_size,
            calculation_period_days=beta_coefficients.calculation_period_days
        )
        
        correlation_response = CorrelationStabilityResponse(
            rolling_correlations_spy=correlation_stability.rolling_correlations_spy,
            rolling_correlations_qqq=correlation_stability.rolling_correlations_qqq,
            correlation_dates=correlation_stability.correlation_dates,
            correlation_volatility_spy=correlation_stability.correlation_volatility_spy,
            correlation_volatility_qqq=correlation_stability.correlation_volatility_qqq,
            correlation_trend_spy=correlation_stability.correlation_trend_spy,
            correlation_trend_qqq=correlation_stability.correlation_trend_qqq,
            stability_score_spy=correlation_stability.stability_score_spy,
            stability_score_qqq=correlation_stability.stability_score_qqq,
            regime_correlation_spy=correlation_stability.regime_correlation_spy,
            regime_correlation_qqq=correlation_stability.regime_correlation_qqq
        )
        
        market_correlation_response = MarketCorrelationResponse(
            beta_coefficients=beta_response,
            correlation_stability=correlation_response,
            analysis_period=analysis_period
        )
        
        logger.info(f"[MARKET CORRELATION] SUCCESS: {account} {hour}:{minute_bin:02d}")
        
        return APIResponse[MarketCorrelationResponse](
            status="success",
            message=f"Market correlation analysis completed for {account} {hour}:{minute_bin:02d}",
            data=market_correlation_response
        )
        
    except ValueError as e:
        logger.error(f"[MARKET CORRELATION] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[MARKET CORRELATION] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Market correlation analysis failed: {str(e)}")


@router.get(
    "/{account}/{hour}/{minute_bin}/benchmark-comparison",
    response_model=APIResponse[BenchmarkComparisonResponse],
    summary="Get comprehensive benchmark comparison",
    description="Complete benchmark comparison analysis including beta, alpha, neutrality tests, and correlation stability."
)
async def get_benchmark_comparison(
    account: str = Path(..., description="Account name", example="IPS_TM_10"),
    hour: int = Path(..., description="Hour of day (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(..., description="Minute bin (0 or 30)", example=30),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis"),
    db: Session = Depends(get_database_session),
    benchmark_analyzer: BenchmarkComparisonAnalyzer = Depends(get_benchmark_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[BenchmarkComparisonResponse]:
    """
    Get comprehensive benchmark comparison analysis.
    
    Requirements:
    - 11.3: Beta coefficient calculations for market correlation
    - 11.4: Alpha metrics for risk-adjusted returns
    - 11.5: Market neutrality testing for independence testing
    - 11.6: Correlation stability analysis for time-varying analysis
    """
    
    logger.info(f"[BENCHMARK COMPARISON] Analyzing {account} {hour}:{minute_bin:02d}")
    
    try:
        # Validate minute bin
        if minute_bin not in [0, 30]:
            raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
        
        # Calculate all benchmark metrics
        beta_coefficients = benchmark_analyzer.calculate_beta_coefficients(
            account, start_date, end_date, hour, minute_bin
        )
        
        alpha_metrics = benchmark_analyzer.calculate_alpha_metrics(
            account, start_date, end_date, hour, minute_bin
        )
        
        market_neutrality = benchmark_analyzer.test_market_neutrality(
            account, start_date, end_date, hour, minute_bin
        )
        
        correlation_stability = benchmark_analyzer.calculate_correlation_stability(
            account, start_date, end_date, hour, minute_bin
        )
        
        # Determine analysis period
        analysis_period = {
            "start_date": start_date.isoformat() if start_date else "automatic",
            "end_date": end_date.isoformat() if end_date else "automatic",
            "calculation_period_days": beta_coefficients.calculation_period_days,
            "sample_size": beta_coefficients.sample_size
        }
        
        # Convert to response models
        beta_response = BetaCoefficientsResponse(
            spy_beta=beta_coefficients.spy_beta,
            qqq_beta=beta_coefficients.qqq_beta,
            spy_r_squared=beta_coefficients.spy_r_squared,
            qqq_r_squared=beta_coefficients.qqq_r_squared,
            spy_correlation=beta_coefficients.spy_correlation,
            qqq_correlation=beta_coefficients.qqq_correlation,
            sample_size=beta_coefficients.sample_size,
            calculation_period_days=beta_coefficients.calculation_period_days
        )
        
        alpha_response = AlphaMetricsResponse(
            spy_alpha_annual=alpha_metrics.spy_alpha_annual,
            qqq_alpha_annual=alpha_metrics.qqq_alpha_annual,
            spy_alpha_daily=alpha_metrics.spy_alpha_daily,
            qqq_alpha_daily=alpha_metrics.qqq_alpha_daily,
            jensen_alpha=alpha_metrics.jensen_alpha,
            information_ratio_spy=alpha_metrics.information_ratio_spy,
            information_ratio_qqq=alpha_metrics.information_ratio_qqq,
            tracking_error_spy=alpha_metrics.tracking_error_spy,
            tracking_error_qqq=alpha_metrics.tracking_error_qqq,
            treynor_ratio=alpha_metrics.treynor_ratio
        )
        
        neutrality_response = MarketNeutralityResponse(
            is_market_neutral_spy=market_neutrality.is_market_neutral_spy,
            is_market_neutral_qqq=market_neutrality.is_market_neutral_qqq,
            spy_correlation_p_value=market_neutrality.spy_correlation_p_value,
            qqq_correlation_p_value=market_neutrality.qqq_correlation_p_value,
            spy_beta_p_value=market_neutrality.spy_beta_p_value,
            qqq_beta_p_value=market_neutrality.qqq_beta_p_value,
            market_neutrality_score=market_neutrality.market_neutrality_score,
            independence_test_statistic=market_neutrality.independence_test_statistic,
            independence_p_value=market_neutrality.independence_p_value
        )
        
        correlation_response = CorrelationStabilityResponse(
            rolling_correlations_spy=correlation_stability.rolling_correlations_spy,
            rolling_correlations_qqq=correlation_stability.rolling_correlations_qqq,
            correlation_dates=correlation_stability.correlation_dates,
            correlation_volatility_spy=correlation_stability.correlation_volatility_spy,
            correlation_volatility_qqq=correlation_stability.correlation_volatility_qqq,
            correlation_trend_spy=correlation_stability.correlation_trend_spy,
            correlation_trend_qqq=correlation_stability.correlation_trend_qqq,
            stability_score_spy=correlation_stability.stability_score_spy,
            stability_score_qqq=correlation_stability.stability_score_qqq,
            regime_correlation_spy=correlation_stability.regime_correlation_spy,
            regime_correlation_qqq=correlation_stability.regime_correlation_qqq
        )
        
        benchmark_response = BenchmarkComparisonResponse(
            beta_coefficients=beta_response,
            alpha_metrics=alpha_response,
            market_neutrality=neutrality_response,
            correlation_stability=correlation_response,
            analysis_period=analysis_period
        )
        
        logger.info(f"[BENCHMARK COMPARISON] SUCCESS: {account} {hour}:{minute_bin:02d}")
        
        return APIResponse[BenchmarkComparisonResponse](
            status="success",
            message=f"Benchmark comparison analysis completed for {account} {hour}:{minute_bin:02d}",
            data=benchmark_response
        )
        
    except ValueError as e:
        logger.error(f"[BENCHMARK COMPARISON] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[BENCHMARK COMPARISON] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Benchmark comparison analysis failed: {str(e)}")


@router.get(
    "/{account}/{hour}/{minute_bin}/regime-analysis",
    response_model=APIResponse[RegimeAnalysisResponse],
    summary="Get VIX regime-specific performance analysis",
    description="Analyze trading performance across different VIX volatility regimes."
)
async def get_regime_analysis(
    account: str = Path(..., description="Account name", example="IPS_TM_10"),
    hour: int = Path(..., description="Hour of day (0-23)", example=9, ge=0, le=23),
    minute_bin: int = Path(..., description="Minute bin (0 or 30)", example=30),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis"),
    db: Session = Depends(get_database_session),
    vix_analyzer: VIXDataIntegration = Depends(get_vix_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[RegimeAnalysisResponse]:
    """
    Get VIX regime-specific performance analysis.
    
    Requirements:
    - 12.1: VIX data integration with volatility regime classification
    - 12.3: Regime-specific performance analysis
    - 12.4: Regime transition detection and analysis
    """
    
    logger.info(f"[REGIME ANALYSIS] Analyzing {account} {hour}:{minute_bin:02d}")
    
    try:
        # Validate minute bin
        if minute_bin not in [0, 30]:
            raise HTTPException(status_code=400, detail="Minute bin must be 0 or 30")
        
        # Get VIX-trade alignments
        alignments = vix_analyzer.synchronize_vix_with_trades(account, start_date, end_date)
        
        # Filter alignments by time bin if specified
        if hour is not None and minute_bin is not None:
            filtered_alignments = []
            for alignment in alignments:
                trade_hour = alignment.trade_timestamp.hour
                trade_minute = alignment.trade_timestamp.minute
                trade_minute_bin = 0 if trade_minute < 30 else 30
                
                if trade_hour == hour and trade_minute_bin == minute_bin:
                    filtered_alignments.append(alignment)
            alignments = filtered_alignments
        
        if not alignments:
            raise HTTPException(
                status_code=404,
                detail=f"No trades found for {account} in time bin {hour}:{minute_bin:02d}"
            )
        
        # Analyze performance by regime
        regime_performance = vix_analyzer.analyze_regime_performance(alignments)
        
        # Get VIX data for transition analysis
        min_date = min(alignment.trade_timestamp for alignment in alignments)
        max_date = max(alignment.trade_timestamp for alignment in alignments)
        vix_data = vix_analyzer.fetch_vix_data(min_date, max_date)
        regime_classifications = vix_analyzer.classify_volatility_regimes(vix_data)
        regime_transitions = vix_analyzer.detect_regime_transitions(regime_classifications)
        
        # Convert to response models
        regime_responses = []
        for regime, metrics in regime_performance.items():
            regime_response = VixRegimePerformanceResponse(
                regime=regime.value,
                total_trades=metrics['total_trades'],
                win_rate=metrics['win_rate'],
                avg_pnl=metrics['avg_pnl'],
                total_pnl=metrics['total_pnl'],
                profit_factor=metrics['profit_factor'],
                sharpe_ratio=metrics['sharpe_ratio'],
                avg_vix_level=metrics['avg_vix_level']
            )
            regime_responses.append(regime_response)
        
        transition_responses = []
        for transition in regime_transitions:
            transition_response = RegimeTransitionResponse(
                transition_date=transition.transition_date,
                from_regime=transition.from_regime.value,
                to_regime=transition.to_regime.value,
                trigger_vix_level=transition.trigger_vix_level,
                days_in_previous_regime=transition.days_in_previous_regime
            )
            transition_responses.append(transition_response)
        
        # Calculate regime summary
        best_regime = max(regime_performance.items(), key=lambda x: x[1]['total_pnl'], default=(None, None))
        most_active_regime = max(regime_performance.items(), key=lambda x: x[1]['total_trades'], default=(None, None))
        
        regime_summary = {
            "total_regimes_found": len(regime_performance),
            "most_profitable_regime": best_regime[0].value if best_regime[0] else "Unknown",
            "most_active_regime": most_active_regime[0].value if most_active_regime[0] else "Unknown",
            "regime_stability_score": 1.0 - (len(regime_transitions) / max(len(regime_classifications), 1)),
            "total_transitions": len(regime_transitions)
        }
        
        # Analysis period
        analysis_period = {
            "start_date": min_date.isoformat(),
            "end_date": max_date.isoformat(),
            "total_days": (max_date - min_date).days + 1,
            "total_trades": len(alignments)
        }
        
        regime_analysis_response = RegimeAnalysisResponse(
            regime_performance=regime_responses,
            regime_transitions=transition_responses,
            regime_summary=regime_summary,
            analysis_period=analysis_period
        )
        
        logger.info(f"[REGIME ANALYSIS] SUCCESS: {account} {hour}:{minute_bin:02d} - {len(regime_responses)} regimes")
        
        return APIResponse[RegimeAnalysisResponse](
            status="success",
            message=f"Regime analysis completed for {account} {hour}:{minute_bin:02d}",
            data=regime_analysis_response
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[REGIME ANALYSIS] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[REGIME ANALYSIS] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Regime analysis failed: {str(e)}")


@router.post(
    "/market-data/sync",
    response_model=APIResponse[MarketDataSyncResponse],
    summary="Synchronize market data",
    description="Synchronize SPY/QQQ/VIX market data for correlation analysis."
)
async def sync_market_data(
    request: MarketDataSyncRequest,
    db: Session = Depends(get_database_session),
    market_data_service: MarketDataIngestion = Depends(get_market_data_service),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[MarketDataSyncResponse]:
    """
    Synchronize market data for correlation analysis.
    
    Requirements:
    - 11.1: Market data fetching and synchronization
    - 11.2: SPY/QQQ data integration
    """
    
    logger.info(f"[MARKET DATA SYNC] Syncing {request.symbols}")
    
    try:
        # Generate sync ID
        from datetime import datetime
        sync_id = f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Default date range if not provided
        if not request.start_date:
            request.start_date = datetime.now() - timedelta(days=365)
        if not request.end_date:
            request.end_date = datetime.now()
        
        # Sync each symbol
        symbols_synced = []
        records_added = {}
        records_updated = {}
        data_quality_scores = {}
        warnings = []
        
        start_time = datetime.now()
        
        for symbol in request.symbols:
            try:
                if symbol.upper() == 'SPY':
                    data = market_data_service.fetch_spy_data(request.start_date, request.end_date)
                elif symbol.upper() == 'QQQ':
                    data = market_data_service.fetch_qqq_data(request.start_date, request.end_date)
                elif symbol.upper() == 'VIX':
                    data = market_data_service.fetch_vix_data(request.start_date, request.end_date)
                else:
                    warnings.append(f"Unsupported symbol: {symbol}")
                    continue
                
                # Store market data
                stored_count = market_data_service.store_market_data(data)
                
                symbols_synced.append(symbol.upper())
                records_added[symbol.upper()] = stored_count
                records_updated[symbol.upper()] = 0  # Placeholder - would need to track updates
                data_quality_scores[symbol.upper()] = data.data_quality_score
                
                if data.data_quality_score < 0.9:
                    warnings.append(f"{symbol} data quality below 90%: {data.data_quality_score:.2%}")
                
            except Exception as e:
                logger.warning(f"[MARKET DATA SYNC] Error syncing {symbol}: {str(e)}")
                warnings.append(f"Failed to sync {symbol}: {str(e)}")
        
        sync_duration = (datetime.now() - start_time).total_seconds()
        
        sync_response = MarketDataSyncResponse(
            sync_id=sync_id,
            symbols_synced=symbols_synced,
            records_added=records_added,
            records_updated=records_updated,
            data_quality_scores=data_quality_scores,
            sync_duration_seconds=sync_duration,
            warnings=warnings
        )
        
        logger.info(f"[MARKET DATA SYNC] SUCCESS: Synced {len(symbols_synced)} symbols in {sync_duration:.1f}s")
        
        return APIResponse[MarketDataSyncResponse](
            status="success",
            message=f"Market data sync completed for {len(symbols_synced)} symbols",
            data=sync_response
        )
        
    except Exception as e:
        logger.error(f"[MARKET DATA SYNC] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Market data sync failed: {str(e)}")