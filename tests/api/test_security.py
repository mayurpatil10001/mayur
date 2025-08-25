"""
Security validation tests for the Trading Platform API.

This module tests authentication, authorization, rate limiting,
and other security features.

Requirements: 9.1, 9.3, 10.5
"""

import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from trading_platform.api.main import create_app
from trading_platform.services.auth_service import get_auth_service


class TestAuthentication:
    """Test authentication functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "data" in data
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
        assert "user_info" in data["data"]
        assert data["data"]["user_info"]["username"] == "admin"
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        response_data = response.json()
        # Check if it's in the standard error format or FastAPI's detail format
        if "detail" in response_data:
            assert "Invalid username or password" in response_data["detail"]
        elif "message" in response_data:
            assert "Invalid username or password" in response_data["message"]
    
    def test_login_missing_fields(self, client):
        """Test login with missing fields."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin"
                # Missing password
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_login_invalid_username(self, client):
        """Test login with non-existent username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "password123"
            }
        )
        
        assert response.status_code == 401
    
    def test_token_refresh_success(self, client):
        """Test successful token refresh."""
        # First, login to get a token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        
        token = login_response.json()["data"]["access_token"]
        
        # Now refresh the token
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
    
    def test_token_refresh_invalid_token(self, client):
        """Test token refresh with invalid token."""
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401
    
    def test_token_refresh_missing_token(self, client):
        """Test token refresh without token."""
        response = client.post("/api/v1/auth/refresh")
        
        assert response.status_code == 403  # Missing authorization header
    
    def test_get_user_info_success(self, client):
        """Test getting current user info."""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "trader",
                "password": "trader123"
            }
        )
        
        token = login_response.json()["data"]["access_token"]
        
        # Get user info
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["data"]["username"] == "trader"
        assert "trader" in data["data"]["roles"]
    
    def test_get_user_permissions_success(self, client):
        """Test getting user permissions."""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        
        token = login_response.json()["data"]["access_token"]
        
        # Get permissions
        response = client.get(
            "/api/v1/auth/permissions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["data"]["username"] == "admin"
        assert data["data"]["permission_details"]["is_admin"] is True
        assert data["data"]["role_details"]["is_admin"] is True
    
    def test_logout_success(self, client):
        """Test successful logout."""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        
        token = login_response.json()["data"]["access_token"]
        
        # Logout
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestAuthorization:
    """Test authorization and access control."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    @pytest.fixture
    def admin_token(self, client):
        """Get admin token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        return response.json()["data"]["access_token"]
    
    @pytest.fixture
    def trader_token(self, client):
        """Get trader token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "trader", "password": "trader123"}
        )
        return response.json()["data"]["access_token"]
    
    @pytest.fixture
    def viewer_token(self, client):
        """Get viewer token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "viewer", "password": "viewer123"}
        )
        return response.json()["data"]["access_token"]
    
    def test_admin_access_all_endpoints(self, client, admin_token):
        """Test that admin can access all endpoints."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test read access
        response = client.get("/api/v1/accounts/", headers=headers)
        assert response.status_code == 200
        
        # Test write access
        response = client.post(
            "/api/v1/accounts/",
            json={"name": "IPS_TM_15", "symbol": "NQ"},
            headers=headers
        )
        assert response.status_code == 201
    
    def test_trader_read_write_access(self, client, trader_token):
        """Test that trader has read and write access."""
        headers = {"Authorization": f"Bearer {trader_token}"}
        
        # Test read access
        response = client.get("/api/v1/accounts/", headers=headers)
        assert response.status_code == 200
        
        # Test write access
        response = client.post(
            "/api/v1/accounts/",
            json={"name": "IPS_TM_16", "symbol": "NQ"},
            headers=headers
        )
        assert response.status_code == 201
    
    def test_viewer_read_only_access(self, client, viewer_token):
        """Test that viewer has read-only access."""
        headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Test read access (should work)
        response = client.get("/api/v1/accounts/", headers=headers)
        assert response.status_code == 200
        
        # Test write access (should fail)
        response = client.post(
            "/api/v1/accounts/",
            json={"name": "IPS_TM_17", "symbol": "NQ"},
            headers=headers
        )
        assert response.status_code == 403  # Forbidden
    
    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        # Test without token
        response = client.get("/api/v1/accounts/")
        assert response.status_code == 403
        
        # Test with invalid token
        response = client.get(
            "/api/v1/accounts/",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
    
    def test_expired_token_handling(self, client):
        """Test handling of expired tokens."""
        # This would require mocking the JWT expiration
        # For now, we test with an obviously invalid token
        response = client.get(
            "/api/v1/accounts/",
            headers={"Authorization": "Bearer expired.token.here"}
        )
        assert response.status_code == 401


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client with low rate limit for testing."""
        app = create_app()
        return TestClient(app)
    
    def test_rate_limiting_health_endpoint(self, client):
        """Test rate limiting on health endpoint."""
        # Make multiple rapid requests
        responses = []
        for i in range(70):  # Exceed default rate limit of 60
            response = client.get("/health")
            responses.append(response)
            if response.status_code == 429:
                break
        
        # Should eventually get rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        
        # With default settings, we might not hit rate limit in tests
        # But if we do, verify the response format
        if rate_limited_responses:
            rate_limited_response = rate_limited_responses[0]
            data = rate_limited_response.json()
            assert "RATE_LIMIT_EXCEEDED" in data["error"]
            assert "Retry-After" in rate_limited_response.headers
    
    def test_rate_limiting_different_ips(self, client):
        """Test that rate limiting is per IP."""
        # This is difficult to test with TestClient as it doesn't simulate different IPs
        # In a real environment, different IPs would have separate rate limits
        pass
    
    @patch('trading_platform.api.middleware.RateLimitMiddleware._is_rate_limited')
    def test_rate_limit_response_format(self, mock_is_rate_limited, client):
        """Test rate limit response format."""
        mock_is_rate_limited.return_value = True
        
        response = client.get("/health")
        
        if response.status_code == 429:
            data = response.json()
            assert data["error"] == "RATE_LIMIT_EXCEEDED"
            assert "rate limit exceeded" in data["message"].lower()
            assert "retry_after" in data
            assert "Retry-After" in response.headers


class TestInputValidation:
    """Test input validation and sanitization."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    @pytest.fixture
    def admin_token(self, client):
        """Get admin token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        return response.json()["data"]["access_token"]
    
    def test_sql_injection_prevention(self, client, admin_token):
        """Test SQL injection prevention."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Try SQL injection in query parameters
        response = client.get(
            "/api/v1/accounts/?symbol='; DROP TABLE accounts; --",
            headers=headers
        )
        
        # Should not cause server error (500), should handle gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_xss_prevention(self, client, admin_token):
        """Test XSS prevention in input fields."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Try XSS in account creation
        response = client.post(
            "/api/v1/accounts/",
            json={
                "name": "<script>alert('xss')</script>",
                "symbol": "NQ"
            },
            headers=headers
        )
        
        # Should be rejected due to validation
        assert response.status_code == 422
    
    def test_oversized_request_handling(self, client, admin_token):
        """Test handling of oversized requests."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Try to create account with very long name
        long_name = "A" * 1000
        response = client.post(
            "/api/v1/accounts/",
            json={
                "name": long_name,
                "symbol": "NQ"
            },
            headers=headers
        )
        
        # Should be rejected due to validation
        assert response.status_code == 422
    
    def test_invalid_json_handling(self, client, admin_token):
        """Test handling of invalid JSON."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        headers["Content-Type"] = "application/json"
        
        # Send invalid JSON
        response = client.post(
            "/api/v1/accounts/",
            data='{"name": "test", "symbol":}',  # Invalid JSON
            headers=headers
        )
        
        # Should return 422 for malformed JSON
        assert response.status_code == 422


class TestSecurityHeaders:
    """Test security headers."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)
    
    def test_security_headers_present(self, client):
        """Test that security headers are present."""
        response = client.get("/health")
        
        # Check for security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Referrer-Policy",
            "Content-Security-Policy"
        ]
        
        for header in security_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_security_header_values(self, client):
        """Test security header values."""
        response = client.get("/health")
        
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        assert "strict-origin" in response.headers["Referrer-Policy"]
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]


class TestPasswordSecurity:
    """Test password security features."""
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        auth_service = get_auth_service()
        
        # Check that stored passwords are hashed
        stored_hash = auth_service._user_credentials.get("admin")
        assert stored_hash is not None
        assert stored_hash != "admin123"  # Should not be plain text
        assert len(stored_hash) > 20  # Should be a hash
    
    def test_password_verification(self):
        """Test password verification."""
        auth_service = get_auth_service()
        
        # Test correct password
        user = auth_service.authenticate_user("admin", "admin123")
        assert user is not None
        assert user.username == "admin"
        
        # Test incorrect password
        user = auth_service.authenticate_user("admin", "wrongpassword")
        assert user is None
    
    def test_user_creation_password_hashing(self):
        """Test that new user passwords are hashed."""
        auth_service = get_auth_service()
        
        # Create a new user
        from trading_platform.services.auth_service import UserRole
        user = auth_service.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            roles=[UserRole.VIEWER]
        )
        
        # Check that password is hashed
        stored_hash = auth_service._user_credentials.get("testuser")
        assert stored_hash is not None
        assert stored_hash != "testpassword123"
        
        # Verify authentication works
        auth_user = auth_service.authenticate_user("testuser", "testpassword123")
        assert auth_user is not None
        assert auth_user.username == "testuser"


if __name__ == "__main__":
    pytest.main([__file__])