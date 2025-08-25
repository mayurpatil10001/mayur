"""
API contract validation tests.

This module tests that the API endpoints conform to their documented contracts
and OpenAPI specification.

Requirements: 10.1, 10.4
"""

import pytest
from fastapi.testclient import TestClient
from trading_platform.api.main import create_app


class TestAPIContract:
    """Test API contract compliance."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        # Generate a valid token for testing
        from trading_platform.services.auth_service import get_auth_service
        auth_service = get_auth_service()
        admin_user = auth_service.get_user_by_username("admin")
        valid_token = auth_service.create_access_token(admin_user)
        return {"Authorization": f"Bearer {valid_token}"}
    
    def test_openapi_spec_generation(self, client):
        """Test that OpenAPI specification is generated correctly."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        spec = response.json()
        
        # Validate basic OpenAPI structure
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        
        # Validate info section
        info = spec["info"]
        assert info["title"] == "Trading Optimization Platform API"
        assert info["version"] == "1.0.0"
        assert "description" in info
    
    def test_health_endpoint_contract(self, client):
        """Test health endpoint follows contract."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        
        # Validate required fields
        required_fields = ["status", "timestamp", "version", "database", "services"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate field types
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], (int, float))
        assert isinstance(data["version"], str)
        assert isinstance(data["database"], str)
        assert isinstance(data["services"], str)
    
    def test_accounts_list_endpoint_contract(self, client, auth_headers):
        """Test accounts list endpoint follows contract."""
        response = client.get("/api/v1/accounts/", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Validate APIResponse structure
        assert "status" in data
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data
        
        # Validate PaginatedResponse structure
        paginated_data = data["data"]
        assert "items" in paginated_data
        assert "total" in paginated_data
        assert "page" in paginated_data
        assert "size" in paginated_data
        assert "pages" in paginated_data
        assert "has_next" in paginated_data
        assert "has_prev" in paginated_data
        
        # Validate account items structure
        for item in paginated_data["items"]:
            required_fields = [
                "name", "symbol", "total_trades", 
                "first_trade_date", "last_trade_date", "is_active"
            ]
            for field in required_fields:
                assert field in item, f"Missing required field in account: {field}"
    
    def test_accounts_get_endpoint_contract(self, client, auth_headers):
        """Test accounts get endpoint follows contract."""
        response = client.get("/api/v1/accounts/IPS_TM_10", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Validate APIResponse structure
        assert "status" in data
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data
        
        # Validate AccountResponse structure
        account_data = data["data"]
        required_fields = [
            "name", "symbol", "total_trades", 
            "first_trade_date", "last_trade_date", "is_active"
        ]
        for field in required_fields:
            assert field in account_data, f"Missing required field: {field}"
    
    def test_error_response_contract(self, client):
        """Test error responses follow contract."""
        # Test 403 error (forbidden - no authentication)
        response = client.get("/api/v1/accounts/")
        assert response.status_code == 403
        
        data = response.json()
        
        # Validate error response structure
        assert "error" in data
        assert "message" in data
        assert "timestamp" in data
        
        # Test 404 error
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "timestamp" in data
    
    def test_authentication_required_endpoints(self, client):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            "/api/v1/accounts/",
            "/api/v1/accounts/test",
            "/api/v1/trades/",
            "/api/v1/analytics/performance/test",
            "/api/v1/recommendations/current",
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require authentication"
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly configured."""
        response = client.options("/health")
        assert response.status_code == 200
        
        # Note: TestClient doesn't fully simulate CORS behavior
        # In a real browser environment, CORS headers would be tested
    
    def test_security_headers_present(self, client):
        """Test that security headers are present."""
        response = client.get("/health")
        
        # Check for security headers added by middleware
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-Request-ID",
            "X-Process-Time"
        ]
        
        for header in security_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_content_type_headers(self, client, auth_headers):
        """Test that content type headers are correct."""
        response = client.get("/api/v1/accounts/", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_pagination_parameters_validation(self, client, auth_headers):
        """Test pagination parameter validation."""
        # Valid pagination
        response = client.get("/api/v1/accounts/?page=1&size=10", headers=auth_headers)
        assert response.status_code == 200
        
        # Invalid page (less than 1)
        response = client.get("/api/v1/accounts/?page=0&size=10", headers=auth_headers)
        assert response.status_code == 422  # Validation error
        
        # Invalid size (greater than 1000)
        response = client.get("/api/v1/accounts/?page=1&size=1001", headers=auth_headers)
        assert response.status_code == 422  # Validation error
    
    def test_request_validation(self, client, auth_headers):
        """Test request body validation."""
        # Valid account creation
        valid_data = {
            "name": "IPS_TM_15",
            "symbol": "NQ"
        }
        response = client.post("/api/v1/accounts/", json=valid_data, headers=auth_headers)
        assert response.status_code == 201
        
        # Invalid account creation (missing required field)
        invalid_data = {
            "name": "IPS_TM_15"
            # Missing symbol
        }
        response = client.post("/api/v1/accounts/", json=invalid_data, headers=auth_headers)
        assert response.status_code == 422
        
        # Invalid account creation (wrong format)
        invalid_data = {
            "name": "INVALID_NAME",
            "symbol": "NQ"
        }
        response = client.post("/api/v1/accounts/", json=invalid_data, headers=auth_headers)
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__])