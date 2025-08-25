"""
Tests for monitoring API endpoints.

This module tests the FastAPI endpoints for real-time monitoring,
alert configuration, and WebSocket connections.

Requirements: 8.1, 8.2, 10.1
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import websockets

from trading_platform.api.endpoints.monitoring import (
    router, initialize_monitoring_endpoints, shutdown_monitoring_endpoints,
    TimeBinIdentifier, AlertConfigRequest, MonitoringStatus
)
from trading_platform.services.monitoring.time_bin_monitoring_service import (
    TimeBinMonitoringService, MonitoringConfiguration, PerformanceSnapshot,
    MonitoringAlert, AlertSeverity, AlertType
)
from trading_platform.services.monitoring.alerts_engine import AlertsEngine, AlertRule
from trading_platform.services.time_bin_analyzer import TimeBin
from trading_platform.api.websockets.monitoring_websocket import MonitoringWebSocket


class TestMonitoringEndpoints:
    """Test suite for monitoring API endpoints."""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI app with monitoring router."""
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def mock_monitoring_service(self):
        """Create mock monitoring service."""
        mock_service = Mock(spec=TimeBinMonitoringService)
        
        # Mock performance snapshots
        mock_snapshots = [
            PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(hours=i),
                time_bin=TimeBin("TestAccount", 9, 30),
                trades_count=10 + i,
                total_pnl=100.0 - i * 10,
                win_rate=0.6 - i * 0.01,
                avg_trade_pnl=10.0 - i,
                max_drawdown=0.05 + i * 0.01,
                sharpe_ratio=1.5 - i * 0.1,
                profit_factor=1.8 - i * 0.1,
                statistical_significance=0.03 + i * 0.001,
                p_value=0.02 + i * 0.001,
                market_correlation={"SPY": 0.5, "QQQ": 0.4}
            )
            for i in range(5)
        ]
        
        mock_service.get_performance_history.return_value = mock_snapshots
        mock_service.get_active_alerts.return_value = []
        mock_service.is_monitoring_time_bin.return_value = True
        mock_service.configure_monitoring.return_value = None
        mock_service.acknowledge_alert.return_value = True
        mock_service.get_monitoring_status.return_value = {
            "is_active": True,
            "monitored_time_bins": 5,
            "active_alerts": 2,
            "last_update": datetime.now(),
            "uptime_seconds": 3600
        }
        
        return mock_service
    
    @pytest.fixture
    def mock_alerts_engine(self):
        """Create mock alerts engine."""
        mock_engine = Mock(spec=AlertsEngine)
        
        # Mock alert
        mock_alert = MonitoringAlert(
            alert_id="test_alert_1",
            timestamp=datetime.now(),
            time_bin=TimeBin("TestAccount", 9, 30),
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.HIGH,
            message="Performance degradation detected",
            metric_values={"current_pnl": -50.0, "threshold": -40.0}
        )
        
        mock_engine.get_active_alerts.return_value = [mock_alert]
        mock_engine.add_alert_rule.return_value = None
        mock_engine.acknowledge_alert.return_value = True
        
        return mock_engine
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket handler."""
        mock_ws = Mock(spec=MonitoringWebSocket)
        mock_ws.handle_websocket = AsyncMock()
        return mock_ws
    
    @pytest.fixture
    def client(self, app, mock_monitoring_service, mock_alerts_engine, mock_websocket):
        """Create test client with mocked services."""
        initialize_monitoring_endpoints(
            mock_monitoring_service,
            mock_alerts_engine,
            mock_websocket
        )
        
        with TestClient(app) as client:
            yield client
        
        shutdown_monitoring_endpoints()
    
    def test_get_time_bin_monitoring_success(self, client, mock_monitoring_service):
        """Test successful retrieval of time-bin monitoring data."""
        response = client.get("/api/time-bins/TestAccount/9/30/monitor")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["time_bin"]["account_name"] == "TestAccount"
        assert data["time_bin"]["hour"] == 9
        assert data["time_bin"]["minute_bin"] == 30
        assert data["monitoring_status"] == "active"
        assert data["current_metrics"] is not None
        assert len(data["recent_history"]) == 5
        assert data["active_alerts"] == []
        
        # Verify service was called correctly
        mock_monitoring_service.get_performance_history.assert_called_once()
        mock_monitoring_service.is_monitoring_time_bin.assert_called_once()
    
    def test_get_time_bin_monitoring_with_history_param(self, client, mock_monitoring_service):
        """Test time-bin monitoring with custom history parameter."""
        response = client.get("/api/time-bins/TestAccount/9/30/monitor?history_hours=48")
        
        assert response.status_code == 200
        
        # Verify history parameter was passed correctly
        call_args = mock_monitoring_service.get_performance_history.call_args
        assert call_args[1]["hours"] == 48
    
    def test_get_time_bin_monitoring_invalid_params(self, client):
        """Test time-bin monitoring with invalid parameters."""
        # Invalid hour
        response = client.get("/api/time-bins/TestAccount/25/30/monitor")
        assert response.status_code == 422
        
        # Invalid minute bin
        response = client.get("/api/time-bins/TestAccount/9/60/monitor")
        assert response.status_code == 422
    
    def test_configure_alerts_success(self, client, mock_monitoring_service, mock_alerts_engine):
        """Test successful alert configuration."""
        config_data = {
            "time_bin": {
                "account_name": "TestAccount",
                "hour": 9,
                "minute_bin": 30
            },
            "performance_threshold": -0.08,
            "win_rate_threshold": 0.35,
            "drawdown_threshold": 0.15,
            "significance_threshold": 0.03,
            "enable_email_alerts": True,
            "enable_push_alerts": False,
            "alert_cooldown_minutes": 90
        }
        
        response = client.post("/api/alerts/configure", json=config_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["time_bin"]["account_name"] == "TestAccount"
        assert data["configuration"]["performance_threshold"] == -0.08
        assert data["alert_rules_created"] == 1
        
        # Verify services were called
        mock_monitoring_service.configure_monitoring.assert_called_once()
        mock_alerts_engine.add_alert_rule.assert_called_once()
    
    def test_configure_alerts_validation_error(self, client):
        """Test alert configuration with validation errors."""
        # Missing required field
        config_data = {
            "time_bin": {
                "account_name": "TestAccount",
                "hour": 9
                # missing minute_bin
            }
        }
        
        response = client.post("/api/alerts/configure", json=config_data)
        assert response.status_code == 422
    
    def test_get_active_alerts_success(self, client, mock_monitoring_service, mock_alerts_engine):
        """Test successful retrieval of active alerts."""
        response = client.get("/api/alerts/active")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert data["total_count"] == 1
        assert data["high_severity_count"] == 1
        assert data["medium_severity_count"] == 0
        assert data["low_severity_count"] == 0
        
        alert = data["alerts"][0]
        assert alert["alert_id"] == "test_alert_1"
        assert alert["alert_type"] == "PERFORMANCE_DEGRADATION"
        assert alert["severity"] == "HIGH"
    
    def test_get_active_alerts_with_filters(self, client, mock_monitoring_service, mock_alerts_engine):
        """Test active alerts with filtering parameters."""
        response = client.get("/api/alerts/active?account=TestAccount&severity=HIGH&limit=50")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filtering logic would be applied
        assert "alerts" in data
    
    def test_get_active_alerts_invalid_severity(self, client):
        """Test active alerts with invalid severity filter."""
        response = client.get("/api/alerts/active?severity=INVALID")
        
        assert response.status_code == 400
        assert "Invalid severity value" in response.json()["detail"]
    
    def test_acknowledge_alert_success(self, client, mock_monitoring_service):
        """Test successful alert acknowledgment."""
        response = client.post(
            "/api/alerts/test_alert_1/acknowledge",
            json={"acknowledged_by": "test_user"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["alert_id"] == "test_alert_1"
        assert data["acknowledged_by"] == "test_user"
        
        # Verify service was called
        mock_monitoring_service.acknowledge_alert.assert_called_once_with(
            "test_alert_1", "test_user"
        )
    
    def test_acknowledge_alert_not_found(self, client, mock_monitoring_service, mock_alerts_engine):
        """Test acknowledgment of non-existent alert."""
        mock_monitoring_service.acknowledge_alert.return_value = False
        mock_alerts_engine.acknowledge_alert.return_value = False
        
        response = client.post(
            "/api/alerts/nonexistent_alert/acknowledge",
            json={"acknowledged_by": "test_user"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_get_monitoring_status_success(self, client, mock_monitoring_service):
        """Test successful retrieval of monitoring status."""
        response = client.get("/api/monitoring/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_active"] is True
        assert data["monitored_time_bins"] == 5
        assert data["active_alerts"] == 2
        assert data["uptime_seconds"] == 3600
        
        mock_monitoring_service.get_monitoring_status.assert_called_once()
    
    def test_service_not_initialized_error(self):
        """Test endpoints when services are not initialized."""
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as client:
            response = client.get("/api/time-bins/TestAccount/9/30/monitor")
            assert response.status_code == 503
            assert "not initialized" in response.json()["detail"]


class TestMonitoringWebSocketEndpoints:
    """Test suite for monitoring WebSocket endpoints."""
    
    @pytest.fixture
    def app(self):
        """Create FastAPI app with monitoring router."""
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def mock_websocket_handler(self):
        """Create mock WebSocket handler."""
        mock_handler = Mock(spec=MonitoringWebSocket)
        mock_handler.handle_websocket = AsyncMock()
        return mock_handler
    
    @pytest.fixture
    def client(self, app, mock_websocket_handler):
        """Create test client with mocked WebSocket handler."""
        # Initialize with minimal mocks for other services
        mock_monitoring = Mock()
        mock_alerts = Mock()
        
        initialize_monitoring_endpoints(
            mock_monitoring,
            mock_alerts,
            mock_websocket_handler
        )
        
        with TestClient(app) as client:
            yield client, mock_websocket_handler
        
        shutdown_monitoring_endpoints()
    
    def test_websocket_endpoint_with_client_id(self, client):
        """Test WebSocket endpoint with explicit client ID."""
        test_client, mock_handler = client
        
        with test_client.websocket_connect("/api/ws/monitoring/test_client_123") as websocket:
            # Connection should be handled by the mock handler
            pass
        
        # Verify handler was called with correct parameters
        mock_handler.handle_websocket.assert_called_once()
        call_args = mock_handler.handle_websocket.call_args
        assert call_args[0][1] == "test_client_123"  # client_id parameter
    
    def test_websocket_endpoint_auto_id(self, client):
        """Test WebSocket endpoint with auto-generated client ID."""
        test_client, mock_handler = client
        
        with test_client.websocket_connect("/api/ws/monitoring") as websocket:
            # Connection should be handled by the mock handler
            pass
        
        # Verify handler was called without client_id
        mock_handler.handle_websocket.assert_called_once()
        call_args = mock_handler.handle_websocket.call_args
        assert len(call_args[0]) == 1  # Only websocket parameter


class TestPydanticModels:
    """Test suite for Pydantic models used in monitoring endpoints."""
    
    def test_time_bin_identifier_validation(self):
        """Test TimeBinIdentifier validation."""
        # Valid data
        valid_data = {
            "account_name": "TestAccount",
            "hour": 9,
            "minute_bin": 30
        }
        time_bin = TimeBinIdentifier(**valid_data)
        assert time_bin.account_name == "TestAccount"
        assert time_bin.hour == 9
        assert time_bin.minute_bin == 30
        
        # Invalid hour
        with pytest.raises(ValueError):
            TimeBinIdentifier(account_name="Test", hour=25, minute_bin=30)
        
        # Invalid minute_bin
        with pytest.raises(ValueError):
            TimeBinIdentifier(account_name="Test", hour=9, minute_bin=60)
    
    def test_alert_config_request_defaults(self):
        """Test AlertConfigRequest with default values."""
        minimal_data = {
            "time_bin": {
                "account_name": "TestAccount",
                "hour": 9,
                "minute_bin": 30
            }
        }
        
        config = AlertConfigRequest(**minimal_data)
        
        # Check default values
        assert config.performance_threshold == -0.05
        assert config.win_rate_threshold == 0.4
        assert config.drawdown_threshold == 0.1
        assert config.significance_threshold == 0.05
        assert config.enable_email_alerts is True
        assert config.enable_push_alerts is False
        assert config.alert_cooldown_minutes == 60
    
    def test_monitoring_status_model(self):
        """Test MonitoringStatus model."""
        status_data = {
            "is_active": True,
            "monitored_time_bins": 10,
            "active_alerts": 3,
            "last_update": datetime.now(),
            "uptime_seconds": 7200
        }
        
        status = MonitoringStatus(**status_data)
        
        assert status.is_active is True
        assert status.monitored_time_bins == 10
        assert status.active_alerts == 3
        assert status.uptime_seconds == 7200


class TestEndpointIntegration:
    """Integration tests for monitoring endpoints."""
    
    @pytest.fixture
    def real_services(self):
        """Create real service instances for integration testing."""
        # Note: In a real test environment, these would be properly configured
        # For now, we'll use mocks but this shows the integration pattern
        monitoring_service = Mock(spec=TimeBinMonitoringService)
        alerts_engine = Mock(spec=AlertsEngine)
        websocket_handler = Mock(spec=MonitoringWebSocket)
        
        return monitoring_service, alerts_engine, websocket_handler
    
    def test_full_monitoring_workflow(self, real_services):
        """Test complete monitoring workflow with realistic data."""
        monitoring_service, alerts_engine, websocket_handler = real_services
        
        # Setup realistic mock responses
        time_bin = TimeBin("PROD_ACCOUNT", 14, 45)
        
        # Mock performance history
        recent_snapshots = [
            PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(minutes=i*5),
                time_bin=time_bin,
                trades_count=i + 5,
                total_pnl=1000.0 - i * 50,
                win_rate=0.65 - i * 0.02,
                avg_trade_pnl=20.0 - i * 2,
                max_drawdown=0.03 + i * 0.005,
                sharpe_ratio=2.1 - i * 0.1,
                profit_factor=2.5 - i * 0.1,
                statistical_significance=0.02,
                p_value=0.01,
                market_correlation={"SPY": 0.6, "QQQ": 0.5, "VIX": -0.3}
            )
            for i in range(12)  # Last hour of data
        ]
        
        monitoring_service.get_performance_history.return_value = recent_snapshots
        monitoring_service.is_monitoring_time_bin.return_value = True
        monitoring_service.get_active_alerts.return_value = []
        
        # Create app and client
        app = FastAPI()
        app.include_router(router)
        
        initialize_monitoring_endpoints(
            monitoring_service,
            alerts_engine,
            websocket_handler
        )
        
        try:
            with TestClient(app) as client:
                # Test monitoring endpoint
                response = client.get("/api/time-bins/PROD_ACCOUNT/14/45/monitor?history_hours=1")
                assert response.status_code == 200
                
                data = response.json()
                assert len(data["recent_history"]) == 12
                assert data["current_metrics"]["trades_count"] == 5
                assert data["monitoring_status"] == "active"
                
        finally:
            shutdown_monitoring_endpoints()
    
    @pytest.mark.asyncio
    async def test_websocket_message_handling(self):
        """Test WebSocket message handling integration."""
        # This would test the actual WebSocket message flow
        # For now, we'll verify the structure is correct
        
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        # Create handler
        handler = MonitoringWebSocket()
        
        # Test connection handling structure
        assert hasattr(handler, 'handle_websocket')
        assert hasattr(handler, 'connection_manager')
        assert callable(handler.handle_websocket)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])