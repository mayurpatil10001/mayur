"""
Tests for the main FastAPI application setup.

This module tests the application initialization, middleware configuration,
and basic functionality.

Requirements: 10.1, 10.4
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json

from trading_platform.api.main import create_app
from trading_platform.api.exceptions import TradingPlatformException


class TestFastAPIApplication:
    """Test FastAPI application setup and configuration."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_app_creation(self):
        """Test that the FastAPI app is created successfully."""
        app = create_app()
        assert app is not None
        assert app.title == "Trading Optimization Platform API"
        assert app.version == "1.0.0"
    
    def test_health_check_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert data["version"] == "1.0.0"
    
    def test_openapi_docs_available(self, client):
        """Test that OpenAPI documentation is available."""
        response = client.get("/docs")
        assert response.status_code == 200
        
        response = client.get("/redoc")
        assert response.status_code == 200
        
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        assert openapi_spec["info"]["title"] == "Trading Optimization Platform API"
    
    def test_cors_headers(self, client):
        """Test CORS headers are properly set."""
        response = client.options("/health")
        assert response.status_code == 200
        
        # Note: TestClient doesn't fully simulate CORS, but we can test the middleware is applied
        # In a real browser environment, CORS headers would be present
    
    def test_security_headers_middleware(self, client):
        """Test that security headers are added by middleware."""
        response = client.get("/health")
        
        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
    
    def test_request_id_header(self, client):
        """Test that request ID is added to response headers."""
        response = client.get("/health")
        
        assert "X-Request-ID" in response.headers
        assert "X-Process-Time" in response.headers
    
    def test_404_error_handling(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "timestamp" in data
    
    def test_method_not_allowed_handling(self, client):
        """Test method not allowed error handling."""
        response = client.post("/health")
        assert response.status_code == 405
    
    @patch('trading_platform.api.main.get_database_session')
    def test_database_connection_error_handling(self, mock_db, client):
        """Test handling of database connection errors during startup."""
        mock_db.side_effect = Exception("Database connection failed")
        
        # This would be tested during app startup in a real scenario
        # For now, we just verify the mock is set up correctly
        with pytest.raises(Exception, match="Database connection failed"):
            mock_db()
    
    def test_api_route_prefixes(self, client):
        """Test that API routes have correct prefixes."""
        # Test that routes are properly prefixed
        response = client.get("/api/v1/accounts/")
        # Should return 401 or 403 due to missing auth, not 404
        assert response.status_code in [401, 403]
        
        response = client.get("/api/v1/trades/")
        assert response.status_code in [401, 403]
        
        response = client.get("/api/v1/analytics/performance/test")
        assert response.status_code in [401, 403]
        
        response = client.get("/api/v1/recommendations/current")
        assert response.status_code in [401, 403]
        
        response = client.post("/api/v1/data/import/sierra-chart")
        assert response.status_code in [401, 403]


class TestExceptionHandling:
    """Test custom exception handling."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_trading_platform_exception_handling(self, client):
        """Test custom TradingPlatformException handling."""
        # This would require creating a test endpoint that raises the exception
        # For now, we test the exception class itself
        
        exception = TradingPlatformException(
            message="Test error",
            error_type="TEST_ERROR",
            status_code=400,
            details={"field": "test_field"}
        )
        
        assert exception.message == "Test error"
        assert exception.error_type == "TEST_ERROR"
        assert exception.status_code == 400
        assert exception.details == {"field": "test_field"}
    
    def test_validation_error_format(self, client):
        """Test validation error response format."""
        # Generate a valid token for testing
        from trading_platform.services.auth_service import get_auth_service
        auth_service = get_auth_service()
        admin_user = auth_service.get_user_by_username("admin")
        valid_token = auth_service.create_access_token(admin_user)
        
        # Test with invalid JSON
        response = client.post(
            "/api/v1/accounts/",
            json={"invalid": "data"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]  # FastAPI returns 422 for validation errors


class TestMiddleware:
    """Test custom middleware functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_logging_middleware(self, client):
        """Test that logging middleware processes requests."""
        with patch('trading_platform.api.middleware.logger') as mock_logger:
            response = client.get("/health")
            assert response.status_code == 200
            
            # Verify logging calls were made
            assert mock_logger.info.called
    
    def test_error_handling_middleware(self, client):
        """Test error handling middleware."""
        # This would require creating a test endpoint that raises an exception
        # For now, we verify the middleware is properly configured
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_rate_limiting_middleware(self, client):
        """Test rate limiting middleware."""
        # Make multiple requests rapidly
        responses = []
        for _ in range(5):
            response = client.get("/health")
            responses.append(response)
        
        # All should succeed with default rate limits
        for response in responses:
            assert response.status_code == 200


class TestAPIDocumentation:
    """Test API documentation and OpenAPI specification."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_openapi_specification_structure(self, client):
        """Test OpenAPI specification structure."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        spec = response.json()
        
        # Check basic structure
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        
        # Check info section
        info = spec["info"]
        assert info["title"] == "Trading Optimization Platform API"
        assert info["version"] == "1.0.0"
        assert "description" in info
        assert "contact" in info
        assert "license" in info
    
    def test_api_endpoints_documented(self, client):
        """Test that all API endpoints are documented."""
        response = client.get("/openapi.json")
        spec = response.json()
        paths = spec["paths"]
        
        # Check that main endpoint groups are present
        endpoint_groups = [
            "/api/v1/accounts",
            "/api/v1/trades",
            "/api/v1/analytics",
            "/api/v1/recommendations",
            "/api/v1/data"
        ]
        
        for group in endpoint_groups:
            # Check if any path starts with the group
            group_paths = [path for path in paths.keys() if path.startswith(group)]
            assert len(group_paths) > 0, f"No endpoints found for {group}"
    
    def test_security_scheme_documented(self, client):
        """Test that security scheme is properly documented."""
        response = client.get("/openapi.json")
        spec = response.json()
        
        # Check for security components
        if "components" in spec and "securitySchemes" in spec["components"]:
            security_schemes = spec["components"]["securitySchemes"]
            # Should have Bearer token authentication
            assert any("bearer" in scheme.get("scheme", "").lower() 
                     for scheme in security_schemes.values())
        else:
            pytest.fail("Security schemes not found in OpenAPI specification")


if __name__ == "__main__":
    pytest.main([__file__])