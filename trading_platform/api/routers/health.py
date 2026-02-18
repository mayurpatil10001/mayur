"""
Health check and monitoring API endpoints.

Provides system health status, metrics, and monitoring information.

Requirements: 8.1, 8.3
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
from typing import Dict, Any, List, Optional
from datetime import datetime

from ...services.monitoring.health_monitor import health_monitor
from ...services.monitoring.metrics_collector import metrics_collector
from ...services.monitoring.alert_manager import get_alert_manager, AlertRule, AlertSeverity, NotificationChannel
from ..dependencies import require_read_permission
from ..models.common import APIResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=APIResponse[Dict[str, str]],
    summary="Basic health check",
    description="Returns basic system health status"
)
async def health_check():
    """Basic health check endpoint."""
    is_healthy = health_monitor.is_healthy()
    status = "healthy" if is_healthy else "unhealthy"
    
    return APIResponse(
        status="success",
        message="System is healthy",
        data={
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "trading-optimization-platform"
        }
    )


@router.get(
    "/detailed",
    response_model=APIResponse[Dict[str, Any]],
    summary="Detailed health check",
    description="Returns comprehensive health information including all services and metrics"
)
async def detailed_health_check(
    current_user: dict = Depends(require_read_permission)
):
    """Detailed health check with full system information."""
    try:
        health_summary = health_monitor.get_health_summary()
        
        return APIResponse(
            status="success",
            message="Detailed health status retrieved",
            data=health_summary
        )
        
    except Exception as e:
        return APIResponse(
            success=False,
            error=f"Failed to get health status: {str(e)}",
            data={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get(
    "/metrics",
    response_model=APIResponse[Dict[str, Any]],
    summary="System metrics",
    description="Returns system performance metrics and statistics"
)
async def get_metrics(
    minutes: int = Query(60, description="Time period in minutes", ge=1, le=1440),
    current_user: dict = Depends(require_read_permission)
):
    """Get system metrics for the specified time period."""
    try:
        # Get metrics summary
        metrics_summary = metrics_collector.get_summary()
        
        # Get recent metrics history
        recent_metrics = metrics_collector.get_metrics_for_period(minutes)
        
        # Get system metrics from health monitor
        system_metrics_history = health_monitor.get_metrics_history(minutes)
        
        return APIResponse(
            status="success",
            message=f"Metrics retrieved for last {minutes} minutes",
            data={
                "period_minutes": minutes,
                "timestamp": datetime.utcnow().isoformat(),
                "metrics_summary": metrics_summary,
                "recent_metrics": recent_metrics,
                "system_metrics": [m.to_dict() for m in system_metrics_history]
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get(
    "/metrics/prometheus",
    response_class=PlainTextResponse,
    summary="Prometheus metrics",
    description="Returns metrics in Prometheus format"
)
async def get_prometheus_metrics(
    current_user: dict = Depends(require_read_permission)
):
    """Get metrics in Prometheus format."""
    try:
        prometheus_metrics = metrics_collector.get_prometheus_metrics()
        return prometheus_metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Prometheus metrics: {str(e)}"
        )


@router.get(
    "/services",
    response_model=APIResponse[Dict[str, Any]],
    summary="Service health status",
    description="Returns health status of individual services"
)
async def get_service_health(
    current_user: dict = Depends(require_read_permission)
):
    """Get health status of all services."""
    try:
        service_health = health_monitor.get_service_health_status()
        
        return APIResponse(
            success=True,
            data={
                "overall_status": health_monitor.get_overall_health_status(),
                "timestamp": datetime.utcnow().isoformat(),
                "services": {name: service.to_dict() for name, service in service_health.items()}
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get service health: {str(e)}"
        )


@router.get(
    "/endpoints",
    response_model=APIResponse[Dict[str, Any]],
    summary="API endpoint metrics",
    description="Returns performance metrics for API endpoints"
)
async def get_endpoint_metrics(
    current_user: dict = Depends(require_read_permission)
):
    """Get performance metrics for API endpoints."""
    try:
        endpoint_metrics = metrics_collector.get_endpoint_metrics()
        
        return APIResponse(
            success=True,
            data={
                "timestamp": datetime.utcnow().isoformat(),
                "endpoints": endpoint_metrics
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get endpoint metrics: {str(e)}"
        )


@router.post(
    "/monitoring/start",
    response_model=APIResponse[Dict[str, str]],
    summary="Start monitoring",
    description="Start the health monitoring service"
)
async def start_monitoring(
    current_user: dict = Depends(require_read_permission)
):
    """Start the health monitoring service."""
    try:
        await health_monitor.start_monitoring()
        
        return APIResponse(
            success=True,
            data={
                "status": "started",
                "message": "Health monitoring service started",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start monitoring: {str(e)}"
        )


@router.post(
    "/monitoring/stop",
    response_model=APIResponse[Dict[str, str]],
    summary="Stop monitoring",
    description="Stop the health monitoring service"
)
async def stop_monitoring(
    current_user: dict = Depends(require_read_permission)
):
    """Stop the health monitoring service."""
    try:
        await health_monitor.stop_monitoring()
        
        return APIResponse(
            success=True,
            data={
                "status": "stopped",
                "message": "Health monitoring service stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop monitoring: {str(e)}"
        )


@router.get(
    "/system/resources",
    response_model=APIResponse[Dict[str, Any]], 
    summary="System resource usage",
    description="Returns current system resource usage"
)
async def get_system_resources(
    current_user: dict = Depends(require_read_permission)
):
    """Get current system resource usage."""
    try:
        current_metrics = health_monitor.get_current_metrics()
        
        if not current_metrics:
            raise HTTPException(
                status_code=503,
                detail="System metrics not available"
            )
            
        return APIResponse(
            success=True,
            data=current_metrics.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system resources: {str(e)}"
        )


# Alert management endpoints

@router.get(
    "/alerts",
    response_model=APIResponse[Dict[str, Any]],
    summary="Get alert summary",
    description="Returns summary of alert system status and active alerts"
)
async def get_alert_summary(
    current_user: dict = Depends(require_read_permission)
):
    """Get comprehensive alert summary."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        summary = alert_manager_instance.get_alert_summary()
        
        return APIResponse(
            success=True,
            data=summary
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get alert summary: {str(e)}"
        )


@router.get(
    "/alerts/active",
    response_model=APIResponse[List[Dict[str, Any]]],
    summary="Get active alerts",
    description="Returns all currently active alerts"
)
async def get_active_alerts(
    current_user: dict = Depends(require_read_permission)
):
    """Get all active alerts."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        active_alerts = alert_manager_instance.get_active_alerts()
        
        return APIResponse(
            success=True,
            data=[alert.to_dict() for alert in active_alerts]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active alerts: {str(e)}"
        )


@router.get(
    "/alerts/history",
    response_model=APIResponse[List[Dict[str, Any]]],
    summary="Get alert history",
    description="Returns alert history for specified time period"
)
async def get_alert_history(
    hours: int = Query(24, description="Time period in hours", ge=1, le=168),
    current_user: dict = Depends(require_read_permission)
):
    """Get alert history for specified time period."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        alert_history = alert_manager_instance.get_alert_history(hours)
        
        return APIResponse(
            success=True,
            data=[alert.to_dict() for alert in alert_history]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get alert history: {str(e)}"
        )


@router.get(
    "/alerts/rules",
    response_model=APIResponse[List[Dict[str, Any]]],
    summary="Get alert rules",
    description="Returns all configured alert rules"
)
async def get_alert_rules(
    current_user: dict = Depends(require_read_permission)
):
    """Get all alert rules."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        rules = alert_manager_instance.get_alert_rules()
        
        return APIResponse(
            success=True,
            data=[{
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "metric_name": rule.metric_name,
                "condition": rule.condition,
                "threshold": rule.threshold,
                "severity": rule.severity.value,
                "duration_minutes": rule.duration_minutes,
                "enabled": rule.enabled,
                "tags": rule.tags
            } for rule in rules.values()]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get alert rules: {str(e)}"
        )


@router.post(
    "/alerts/monitoring/start",
    response_model=APIResponse[Dict[str, str]],
    summary="Start alert monitoring",
    description="Start the alert monitoring service"
)
async def start_alert_monitoring(
    current_user: dict = Depends(require_read_permission)
):
    """Start alert monitoring service."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        await alert_manager_instance.start_monitoring()
        
        return APIResponse(
            success=True,
            data={
                "status": "started",
                "message": "Alert monitoring service started",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start alert monitoring: {str(e)}"
        )


@router.post(
    "/alerts/monitoring/stop",
    response_model=APIResponse[Dict[str, str]],
    summary="Stop alert monitoring",
    description="Stop the alert monitoring service"
)
async def stop_alert_monitoring(
    current_user: dict = Depends(require_read_permission)
):
    """Stop alert monitoring service."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        await alert_manager_instance.stop_monitoring()
        
        return APIResponse(
            success=True,
            data={
                "status": "stopped",
                "message": "Alert monitoring service stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop alert monitoring: {str(e)}"
        )


@router.post(
    "/alerts/{rule_id}/suppress",
    response_model=APIResponse[Dict[str, str]],
    summary="Suppress alert",
    description="Suppress an active alert"
)
async def suppress_alert(
    rule_id: str,
    current_user: dict = Depends(require_read_permission)
):
    """Suppress an active alert."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        alert_manager_instance.suppress_alert(rule_id)
        
        return APIResponse(
            success=True,
            data={
                "status": "suppressed",
                "message": f"Alert {rule_id} has been suppressed",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to suppress alert: {str(e)}"
        )


@router.get(
    "/alerts/channels",
    response_model=APIResponse[List[Dict[str, Any]]],
    summary="Get notification channels",
    description="Returns all configured notification channels"
)
async def get_notification_channels(
    current_user: dict = Depends(require_read_permission)
):
    """Get all notification channels."""
    try:
        alert_manager_instance = get_alert_manager(health_monitor, metrics_collector)
        channels = alert_manager_instance.get_notification_channels()
        
        return APIResponse(
            success=True,
            data=[{
                "channel_id": channel.channel_id,
                "name": channel.name,
                "channel_type": channel.channel_type,
                "enabled": channel.enabled,
                "severity_filter": [s.value for s in channel.severity_filter]
            } for channel in channels.values()]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get notification channels: {str(e)}"
        )