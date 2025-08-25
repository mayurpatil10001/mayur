"""
FastAPI endpoints for real-time monitoring and alerts management.

This module provides REST API endpoints for monitoring trading performance,
configuring alerts, and managing real-time data subscriptions.

Requirements: 8.1, 8.2, 10.1
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Path, Body
from pydantic import BaseModel, Field, validator
from enum import Enum

from ...services.monitoring.time_bin_monitoring_service import (
    TimeBinMonitoringService, MonitoringConfiguration, PerformanceSnapshot, 
    MonitoringAlert, AlertSeverity, AlertType
)
from ...services.monitoring.alerts_engine import AlertsEngine, AlertRule, DegradationTest, NotificationConfig
from ...services.time_bin_analyzer import TimeBin
from ..websockets.monitoring_websocket import MonitoringWebSocket

logger = logging.getLogger(__name__)

# Router for monitoring endpoints
router = APIRouter(prefix="/api", tags=["monitoring"])

# Global instances - would be dependency injected in production
monitoring_service: Optional[TimeBinMonitoringService] = None
alerts_engine: Optional[AlertsEngine] = None
monitoring_websocket: Optional[MonitoringWebSocket] = None


# Pydantic models for API requests/responses
class TimeBinIdentifier(BaseModel):
    """Time-bin identifier for API requests."""
    account_name: str = Field(..., description="Trading account name")
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    minute_bin: int = Field(..., ge=0, le=59, description="Minute bin (0-59)")


class MonitoringStatus(BaseModel):
    """Current monitoring status response."""
    is_active: bool
    monitored_time_bins: int
    active_alerts: int
    last_update: Optional[datetime]
    uptime_seconds: int


class PerformanceMetrics(BaseModel):
    """Performance metrics response."""
    timestamp: datetime
    trades_count: int
    total_pnl: float
    win_rate: float
    avg_trade_pnl: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    profit_factor: Optional[float]
    statistical_significance: Optional[float]
    p_value: Optional[float]
    market_correlation: Optional[Dict[str, float]]


class AlertConfigRequest(BaseModel):
    """Alert configuration request."""
    time_bin: TimeBinIdentifier
    performance_threshold: float = Field(default=-0.05, description="Performance degradation threshold")
    win_rate_threshold: float = Field(default=0.4, description="Win rate threshold")
    drawdown_threshold: float = Field(default=0.1, description="Maximum drawdown threshold")
    significance_threshold: float = Field(default=0.05, description="Statistical significance threshold")
    enable_email_alerts: bool = Field(default=True, description="Enable email notifications")
    enable_push_alerts: bool = Field(default=False, description="Enable push notifications")
    alert_cooldown_minutes: int = Field(default=60, description="Cooldown between alerts")


class AlertResponse(BaseModel):
    """Alert information response."""
    alert_id: str
    timestamp: datetime
    time_bin: TimeBinIdentifier
    alert_type: str
    severity: str
    message: str
    is_acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]


class ActiveAlertsResponse(BaseModel):
    """Active alerts response."""
    alerts: List[AlertResponse]
    total_count: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    last_updated: datetime


class MonitoringDataResponse(BaseModel):
    """Time-bin monitoring data response."""
    time_bin: TimeBinIdentifier
    current_metrics: Optional[PerformanceMetrics]
    recent_history: List[PerformanceMetrics]
    active_alerts: List[AlertResponse]
    monitoring_status: str
    last_updated: datetime


# Dependency functions
def get_monitoring_service() -> TimeBinMonitoringService:
    """Get monitoring service dependency."""
    if monitoring_service is None:
        raise HTTPException(
            status_code=503, 
            detail="Monitoring service not initialized"
        )
    return monitoring_service


def get_alerts_engine() -> AlertsEngine:
    """Get alerts engine dependency."""
    if alerts_engine is None:
        raise HTTPException(
            status_code=503, 
            detail="Alerts engine not initialized"
        )
    return alerts_engine


def get_monitoring_websocket() -> MonitoringWebSocket:
    """Get monitoring WebSocket dependency."""
    if monitoring_websocket is None:
        raise HTTPException(
            status_code=503, 
            detail="Monitoring WebSocket not initialized"
        )
    return monitoring_websocket


# API Endpoints
@router.get("/time-bins/{account}/{hour}/{minute_bin}/monitor", response_model=MonitoringDataResponse)
async def get_time_bin_monitoring(
    account: str = Path(..., description="Trading account name"),
    hour: int = Path(..., ge=0, le=23, description="Hour of the day"),
    minute_bin: int = Path(..., ge=0, le=59, description="Minute bin"),
    history_hours: int = Query(default=24, ge=1, le=168, description="Hours of history to include"),
    monitoring_svc: TimeBinMonitoringService = Depends(get_monitoring_service)
) -> MonitoringDataResponse:
    """
    Get real-time monitoring data for a specific time-bin.
    
    Returns current performance metrics, recent history, and active alerts
    for the specified time-bin.
    """
    try:
        time_bin = TimeBin(account, hour, minute_bin)
        
        # Get performance history
        history = monitoring_svc.get_performance_history(time_bin, hours=history_hours)
        
        # Get current metrics (latest snapshot)
        current_metrics = None
        if history:
            latest_snapshot = history[-1]
            current_metrics = PerformanceMetrics(
                timestamp=latest_snapshot.timestamp,
                trades_count=latest_snapshot.trades_count,
                total_pnl=latest_snapshot.total_pnl,
                win_rate=latest_snapshot.win_rate,
                avg_trade_pnl=latest_snapshot.avg_trade_pnl,
                max_drawdown=latest_snapshot.max_drawdown,
                sharpe_ratio=latest_snapshot.sharpe_ratio,
                profit_factor=latest_snapshot.profit_factor,
                statistical_significance=latest_snapshot.statistical_significance,
                p_value=latest_snapshot.p_value,
                market_correlation=latest_snapshot.market_correlation
            )
        
        # Convert history to response format (last 50 snapshots max)
        recent_history = []
        for snapshot in history[-50:]:
            recent_history.append(PerformanceMetrics(
                timestamp=snapshot.timestamp,
                trades_count=snapshot.trades_count,
                total_pnl=snapshot.total_pnl,
                win_rate=snapshot.win_rate,
                avg_trade_pnl=snapshot.avg_trade_pnl,
                max_drawdown=snapshot.max_drawdown,
                sharpe_ratio=snapshot.sharpe_ratio,
                profit_factor=snapshot.profit_factor,
                statistical_significance=snapshot.statistical_significance,
                p_value=snapshot.p_value,
                market_correlation=snapshot.market_correlation
            ))
        
        # Get active alerts for this time-bin
        all_alerts = monitoring_svc.get_active_alerts()
        active_alerts = []
        for alert in all_alerts:
            if (alert.time_bin.account_name == account and 
                alert.time_bin.hour == hour and 
                alert.time_bin.minute_bin == minute_bin):
                active_alerts.append(AlertResponse(
                    alert_id=alert.alert_id,
                    timestamp=alert.timestamp,
                    time_bin=TimeBinIdentifier(
                        account_name=alert.time_bin.account_name,
                        hour=alert.time_bin.hour,
                        minute_bin=alert.time_bin.minute_bin
                    ),
                    alert_type=alert.alert_type.value,
                    severity=alert.severity.value,
                    message=alert.message,
                    is_acknowledged=alert.is_acknowledged,
                    acknowledged_by=alert.acknowledged_by,
                    acknowledged_at=alert.acknowledged_at
                ))
        
        # Determine monitoring status
        monitoring_status = "active" if monitoring_svc.is_monitoring_time_bin(time_bin) else "inactive"
        
        return MonitoringDataResponse(
            time_bin=TimeBinIdentifier(account_name=account, hour=hour, minute_bin=minute_bin),
            current_metrics=current_metrics,
            recent_history=recent_history,
            active_alerts=active_alerts,
            monitoring_status=monitoring_status,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error getting monitoring data for {account}/{hour}/{minute_bin}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve monitoring data: {str(e)}"
        )


@router.post("/alerts/configure")
async def configure_alerts(
    config_request: AlertConfigRequest,
    monitoring_svc: TimeBinMonitoringService = Depends(get_monitoring_service),
    alerts_svc: AlertsEngine = Depends(get_alerts_engine)
) -> Dict[str, Any]:
    """
    Configure alert preferences for a specific time-bin.
    
    Sets up monitoring thresholds and notification preferences for 
    performance degradation detection.
    """
    try:
        time_bin = TimeBin(
            config_request.time_bin.account_name,
            config_request.time_bin.hour,
            config_request.time_bin.minute_bin
        )
        
        # Create monitoring configuration
        monitoring_config = MonitoringConfiguration(
            performance_threshold=config_request.performance_threshold,
            win_rate_threshold=config_request.win_rate_threshold,
            drawdown_threshold=config_request.drawdown_threshold,
            significance_threshold=config_request.significance_threshold,
            alert_cooldown_minutes=config_request.alert_cooldown_minutes
        )
        
        # Configure monitoring service
        monitoring_svc.configure_monitoring(time_bin, monitoring_config)
        
        # Create alert rules for the alerts engine
        alert_rules = []
        
        # Performance degradation rule
        perf_rule = AlertRule(
            rule_id=f"perf_deg_{time_bin.account_name}_{time_bin.hour}_{time_bin.minute_bin}",
            time_bin=time_bin,
            degradation_tests=[
                DegradationTest.PERFORMANCE_TTEST,
                DegradationTest.WIN_RATE_PROPORTION,
                DegradationTest.DRAWDOWN_INCREASE
            ],
            threshold=config_request.performance_threshold,
            lookback_periods=20,
            min_trades_required=10,
            alert_actions=[]
        )
        
        # Add notification actions based on preferences
        if config_request.enable_email_alerts:
            perf_rule.alert_actions.append("SEND_EMAIL")
        if config_request.enable_push_alerts:
            perf_rule.alert_actions.append("SEND_PUSH_NOTIFICATION")
        
        alert_rules.append(perf_rule)
        
        # Configure alerts engine with the rules
        for rule in alert_rules:
            alerts_svc.add_alert_rule(rule)
        
        logger.info(f"Alert configuration updated for {time_bin}")
        
        return {
            "success": True,
            "message": f"Alert configuration updated for {time_bin}",
            "time_bin": {
                "account_name": time_bin.account_name,
                "hour": time_bin.hour,
                "minute_bin": time_bin.minute_bin
            },
            "configuration": {
                "performance_threshold": config_request.performance_threshold,
                "win_rate_threshold": config_request.win_rate_threshold,
                "drawdown_threshold": config_request.drawdown_threshold,
                "significance_threshold": config_request.significance_threshold,
                "alert_cooldown_minutes": config_request.alert_cooldown_minutes,
                "email_alerts_enabled": config_request.enable_email_alerts,
                "push_alerts_enabled": config_request.enable_push_alerts
            },
            "alert_rules_created": len(alert_rules),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error configuring alerts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure alerts: {str(e)}"
        )


@router.get("/alerts/active", response_model=ActiveAlertsResponse)
async def get_active_alerts(
    account: Optional[str] = Query(None, description="Filter by account name"),
    severity: Optional[str] = Query(None, description="Filter by severity (HIGH, MEDIUM, LOW)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of alerts to return"),
    monitoring_svc: TimeBinMonitoringService = Depends(get_monitoring_service),
    alerts_svc: AlertsEngine = Depends(get_alerts_engine)
) -> ActiveAlertsResponse:
    """
    Get current active alerts across all monitored time-bins.
    
    Returns a list of active alerts with optional filtering by account or severity.
    """
    try:
        # Get alerts from both services
        all_alerts = []
        
        # Get alerts from monitoring service
        monitoring_alerts = monitoring_svc.get_active_alerts()
        all_alerts.extend(monitoring_alerts)
        
        # Get alerts from alerts engine
        engine_alerts = alerts_svc.get_active_alerts()
        all_alerts.extend(engine_alerts)
        
        # Apply filters
        filtered_alerts = all_alerts
        
        if account:
            filtered_alerts = [
                alert for alert in filtered_alerts 
                if alert.time_bin.account_name == account
            ]
        
        if severity:
            try:
                severity_enum = AlertSeverity(severity.upper())
                filtered_alerts = [
                    alert for alert in filtered_alerts 
                    if alert.severity == severity_enum
                ]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid severity value. Must be one of: HIGH, MEDIUM, LOW"
                )
        
        # Sort by timestamp (newest first) and apply limit
        filtered_alerts.sort(key=lambda x: x.timestamp, reverse=True)
        limited_alerts = filtered_alerts[:limit]
        
        # Convert to response format
        alert_responses = []
        for alert in limited_alerts:
            alert_responses.append(AlertResponse(
                alert_id=alert.alert_id,
                timestamp=alert.timestamp,
                time_bin=TimeBinIdentifier(
                    account_name=alert.time_bin.account_name,
                    hour=alert.time_bin.hour,
                    minute_bin=alert.time_bin.minute_bin
                ),
                alert_type=alert.alert_type.value,
                severity=alert.severity.value,
                message=alert.message,
                is_acknowledged=alert.is_acknowledged,
                acknowledged_by=alert.acknowledged_by,
                acknowledged_at=alert.acknowledged_at
            ))
        
        # Count alerts by severity
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for alert in filtered_alerts:
            severity_counts[alert.severity.value] += 1
        
        return ActiveAlertsResponse(
            alerts=alert_responses,
            total_count=len(filtered_alerts),
            high_severity_count=severity_counts["HIGH"],
            medium_severity_count=severity_counts["MEDIUM"],
            low_severity_count=severity_counts["LOW"],
            last_updated=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active alerts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve active alerts: {str(e)}"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str = Path(..., description="Alert ID to acknowledge"),
    acknowledged_by: str = Body(..., embed=True, description="User acknowledging the alert"),
    monitoring_svc: TimeBinMonitoringService = Depends(get_monitoring_service),
    alerts_svc: AlertsEngine = Depends(get_alerts_engine)
) -> Dict[str, Any]:
    """
    Acknowledge a specific alert.
    
    Marks an alert as acknowledged to prevent repeated notifications.
    """
    try:
        # Try to acknowledge in monitoring service first
        success = monitoring_svc.acknowledge_alert(alert_id, acknowledged_by)
        
        # If not found, try alerts engine
        if not success:
            success = alerts_svc.acknowledge_alert(alert_id, acknowledged_by)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Alert with ID {alert_id} not found"
            )
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        
        return {
            "success": True,
            "message": f"Alert {alert_id} acknowledged successfully",
            "alert_id": alert_id,
            "acknowledged_by": acknowledged_by,
            "acknowledged_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to acknowledge alert: {str(e)}"
        )


@router.get("/monitoring/status", response_model=MonitoringStatus)
async def get_monitoring_status(
    monitoring_svc: TimeBinMonitoringService = Depends(get_monitoring_service)
) -> MonitoringStatus:
    """
    Get overall monitoring system status.
    
    Returns general health and activity information about the monitoring system.
    """
    try:
        status = monitoring_svc.get_monitoring_status()
        
        return MonitoringStatus(
            is_active=status.get("is_active", False),
            monitored_time_bins=status.get("monitored_time_bins", 0),
            active_alerts=status.get("active_alerts", 0),
            last_update=status.get("last_update"),
            uptime_seconds=status.get("uptime_seconds", 0)
        )
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve monitoring status: {str(e)}"
        )


@router.websocket("/ws/monitoring/{client_id}")
async def websocket_monitoring_endpoint(
    websocket: WebSocket,
    client_id: str = Path(..., description="Client identifier for WebSocket connection"),
    ws_handler: MonitoringWebSocket = Depends(get_monitoring_websocket)
):
    """
    WebSocket endpoint for real-time monitoring updates.
    
    Provides real-time streaming of performance metrics, alerts, and system status.
    Clients can subscribe to specific time-bins and alert types.
    """
    await ws_handler.handle_websocket(websocket, client_id)


@router.websocket("/ws/monitoring")
async def websocket_monitoring_endpoint_auto_id(
    websocket: WebSocket,
    ws_handler: MonitoringWebSocket = Depends(get_monitoring_websocket)
):
    """
    WebSocket endpoint for real-time monitoring updates with auto-generated client ID.
    
    Same as the client_id version but automatically generates a unique client identifier.
    """
    await ws_handler.handle_websocket(websocket)


# Service initialization functions
def initialize_monitoring_endpoints(
    monitoring_svc: TimeBinMonitoringService,
    alerts_svc: AlertsEngine,
    websocket_handler: MonitoringWebSocket
):
    """
    Initialize the monitoring endpoints with service instances.
    
    This function should be called during application startup to inject
    the required service dependencies.
    """
    global monitoring_service, alerts_engine, monitoring_websocket
    
    monitoring_service = monitoring_svc
    alerts_engine = alerts_svc
    monitoring_websocket = websocket_handler
    
    logger.info("Monitoring endpoints initialized with service dependencies")


def shutdown_monitoring_endpoints():
    """
    Shutdown monitoring endpoints and clean up resources.
    
    This function should be called during application shutdown.
    """
    global monitoring_service, alerts_engine, monitoring_websocket
    
    if monitoring_websocket:
        # Stop WebSocket broadcasting if it's running
        import asyncio
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(monitoring_websocket.stop_broadcasting())
    
    monitoring_service = None
    alerts_engine = None
    monitoring_websocket = None
    
    logger.info("Monitoring endpoints shut down")