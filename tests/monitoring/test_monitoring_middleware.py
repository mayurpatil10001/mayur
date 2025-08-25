"""
Tests for the monitoring middleware.

Tests API request metrics collection through middleware.

Requirements: 8.1, 8.3
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, Response
from starlette.types import ASGIApp

from trading_platform.api.middleware import MonitoringMiddleware


class TestMonitoringMiddleware:
    """Test MonitoringMiddleware."""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock ASGI app."""
        return MagicMock(spec=ASGIApp)
    
    @pytest.fixture
    def middleware(self, mock_app):
        """Create monitoring middleware instance."""
        return MonitoringMiddleware(mock_app)
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"
        return request
    
    @pytest.fixture
    def mock_response(self):
        """Create mock response."""
        response = MagicMock(spec=Response)
        response.status_code = 200
        return response
    
    @pytest.mark.asyncio
    async def test_dispatch_success(self, middleware, mock_request, mock_response):
        """Test successful request processing with metrics collection."""
        # Mock the call_next function
        call_next = AsyncMock(return_value=mock_response)
        
        with patch('trading_platform.api.middleware.metrics_collector') as mock_collector:
            with patch('trading_platform.api.middleware.time') as mock_time:
                # Mock time to control response time calculation
                mock_time.time.side_effect = [0.0, 0.150]  # 150ms response time
                
                result = await middleware.dispatch(mock_request, call_next)
                
                # Verify response is returned
                assert result == mock_response
                
                # Verify call_next was called
                call_next.assert_called_once_with(mock_request)
                
                # Verify metrics were recorded
                mock_collector.record_request_metrics.assert_called_once_with(
                    endpoint="/api/test",
                    method="GET", 
                    response_time=150.0,  # 0.150 * 1000
                    status_code=200
                )
    
    @pytest.mark.asyncio
    async def test_dispatch_error(self, middleware, mock_request):
        """Test error handling with metrics collection."""
        # Mock the call_next function to raise an exception
        test_error = Exception("Test error")
        call_next = AsyncMock(side_effect=test_error)
        
        with patch('trading_platform.api.middleware.metrics_collector') as mock_collector:
            with patch('trading_platform.api.middleware.time') as mock_time:
                # Mock time to control response time calculation
                mock_time.time.side_effect = [0.0, 0.075]  # 75ms before error
                
                # Verify exception is re-raised
                with pytest.raises(Exception) as exc_info:
                    await middleware.dispatch(mock_request, call_next)
                
                assert exc_info.value == test_error
                
                # Verify call_next was called
                call_next.assert_called_once_with(mock_request)
                
                # Verify error metrics were recorded
                mock_collector.record_request_metrics.assert_called_once_with(
                    endpoint="/api/test",
                    method="GET",
                    response_time=75.0,  # 0.075 * 1000
                    status_code=500
                )
    
    @pytest.mark.asyncio
    async def test_dispatch_different_endpoints(self, middleware, mock_response):
        """Test metrics collection for different endpoints."""
        endpoints = [
            ("/api/accounts", "GET"),
            ("/api/trades", "POST"),
            ("/api/analytics", "GET"),
            ("/health", "GET")
        ]
        
        call_next = AsyncMock(return_value=mock_response)
        
        with patch('trading_platform.api.middleware.metrics_collector') as mock_collector:
            with patch('trading_platform.api.middleware.time') as mock_time:
                mock_time.time.side_effect = [0.0, 0.1] * len(endpoints)  # 100ms each
                
                for endpoint, method in endpoints:
                    request = MagicMock(spec=Request)
                    request.url.path = endpoint
                    request.method = method
                    
                    await middleware.dispatch(request, call_next)
        
        # Verify metrics were recorded for each endpoint
        assert mock_collector.record_request_metrics.call_count == len(endpoints)
        
        # Check specific calls
        calls = mock_collector.record_request_metrics.call_args_list
        for i, (endpoint, method) in enumerate(endpoints):
            call_args = calls[i][1]  # Get keyword arguments
            assert call_args['endpoint'] == endpoint
            assert call_args['method'] == method
            assert call_args['response_time'] == 100.0
            assert call_args['status_code'] == 200
    
    @pytest.mark.asyncio
    async def test_dispatch_different_status_codes(self, middleware, mock_request):
        """Test metrics collection for different response status codes."""
        status_codes = [200, 201, 400, 404, 500]
        
        with patch('trading_platform.api.middleware.metrics_collector') as mock_collector:
            with patch('trading_platform.api.middleware.time') as mock_time:
                mock_time.time.side_effect = [0.0, 0.05] * len(status_codes)  # 50ms each
                
                for status_code in status_codes:
                    response = MagicMock(spec=Response)
                    response.status_code = status_code
                    call_next = AsyncMock(return_value=response)
                    
                    await middleware.dispatch(mock_request, call_next)
        
        # Verify metrics were recorded for each status code
        assert mock_collector.record_request_metrics.call_count == len(status_codes)
        
        # Check status codes in calls
        calls = mock_collector.record_request_metrics.call_args_list
        for i, expected_status in enumerate(status_codes):
            call_args = calls[i][1]
            assert call_args['status_code'] == expected_status
    
    @pytest.mark.asyncio
    async def test_response_time_calculation(self, middleware, mock_request, mock_response):
        """Test accurate response time calculation."""
        call_next = AsyncMock(return_value=mock_response)
        
        with patch('trading_platform.api.middleware.metrics_collector') as mock_collector:
            with patch('trading_platform.api.middleware.time') as mock_time:
                # Test different response times
                test_cases = [
                    (0.0, 0.001),   # 1ms
                    (0.0, 0.250),   # 250ms  
                    (0.0, 1.500),   # 1.5 seconds
                ]
                
                for start_time, end_time in test_cases:
                    mock_time.time.side_effect = [start_time, end_time]
                    
                    await middleware.dispatch(mock_request, call_next)
                    
                    expected_ms = (end_time - start_time) * 1000
                    
                    # Get the last call to verify response time
                    last_call = mock_collector.record_request_metrics.call_args_list[-1]
                    actual_response_time = last_call[1]['response_time']
                    
                    assert actual_response_time == expected_ms


if __name__ == "__main__":
    pytest.main([__file__])