"""
Tests for API dependency injection system.

This module tests the dependency injection functions and service container.

Requirements: 10.1, 10.4
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from trading_platform.api.dependencies import (
    ServiceContainer,
    get_service_container,
    get_current_user,
    require_permission,
    require_role
)


class TestServiceContainer:
    """Test the service container functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock()
    
    @patch('trading_platform.api.dependencies.SierraChartDataIngestionService')
    @patch('trading_platform.api.dependencies.PerformanceMetricsCalculator')
    @patch('trading_platform.api.dependencies.TemporalAnalysisService')
    @patch('trading_platform.api.dependencies.AccountComparisonService')
    @patch('trading_platform.api.dependencies.ModelTrainer')
    @patch('trading_platform.api.dependencies.PredictionService')
    @patch('trading_platform.api.dependencies.MonteCarloSimulator')
    @patch('trading_platform.api.dependencies.RiskCalculator')
    @patch('trading_platform.api.dependencies.RecommendationService')
    def test_service_container_initialization(
        self,
        mock_recommendation_service,
        mock_risk_calculator,
        mock_monte_carlo_simulator,
        mock_prediction_service,
        mock_model_trainer,
        mock_account_comparator,
        mock_temporal_analyzer,
        mock_performance_calculator,
        mock_data_ingestion,
        mock_db_session
    ):
        """Test service container initializes all services."""
        container = ServiceContainer(mock_db_session)
        
        # Verify all services are initialized
        assert container.data_ingestion is not None
        assert container.performance_calculator is not None
        assert container.temporal_analyzer is not None
        assert container.account_comparator is not None
        assert container.model_trainer is not None
        assert container.prediction_service is not None
        assert container.monte_carlo_simulator is not None
        assert container.risk_calculator is not None
        assert container.recommendation_service is not None
        
        # Verify service constructors were called
        mock_data_ingestion.assert_called_once()
        mock_performance_calculator.assert_called_once()
        mock_temporal_analyzer.assert_called_once()
        mock_account_comparator.assert_called_once()
        mock_model_trainer.assert_called_once()
        mock_prediction_service.assert_called_once()
        mock_monte_carlo_simulator.assert_called_once()
        mock_risk_calculator.assert_called_once()
        mock_recommendation_service.assert_called_once()
    
    def test_service_container_get_service(self, mock_db_session):
        """Test getting services by name."""
        with patch.multiple(
            'trading_platform.api.dependencies',
            SierraChartDataIngestionService=Mock(),
            PerformanceMetricsCalculator=Mock(),
            TemporalAnalysisService=Mock(),
            AccountComparisonService=Mock(),
            ModelTrainer=Mock(),
            PredictionService=Mock(),
            MonteCarloSimulator=Mock(),
            RiskCalculator=Mock(),
            RecommendationService=Mock()
        ):
            container = ServiceContainer(mock_db_session)
            
            # Test getting existing service
            service = container.get_service('data_ingestion')
            assert service is not None
            
            # Test getting non-existent service
            with pytest.raises(ValueError, match="Service 'nonexistent' not found"):
                container.get_service('nonexistent')
    
    def test_service_container_initialization_error(self, mock_db_session):
        """Test service container handles initialization errors."""
        with patch('trading_platform.api.dependencies.SierraChartDataIngestionService', side_effect=Exception("Service init failed")):
            with pytest.raises(Exception, match="Service init failed"):
                ServiceContainer(mock_db_session)


class TestAuthentication:
    """Test authentication and authorization dependencies."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test getting current user with valid token."""
        # Generate a valid token for testing
        from trading_platform.services.auth_service import get_auth_service
        auth_service = get_auth_service()
        admin_user = auth_service.get_user_by_username("admin")
        valid_token = auth_service.create_access_token(admin_user)
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )
        
        user = await get_current_user(credentials)
        
        assert user["user_id"] == "admin"
        assert user["username"] == "admin"
        assert "admin" in user["roles"]
        assert "read" in user["permissions"]
    
    @pytest.mark.asyncio
    async def test_get_current_user_missing_token(self):
        """Test getting current user with missing token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=""
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Invalid or expired authentication token" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_permission_valid(self):
        """Test permission requirement with valid permission."""
        mock_user = {
            "user_id": "test-user",
            "permissions": ["read", "write"]
        }
        
        permission_dep = require_permission("read")
        user = await permission_dep(mock_user)
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_require_permission_admin_bypass(self):
        """Test permission requirement with admin role bypass."""
        mock_user = {
            "user_id": "admin-user",
            "permissions": ["admin"]
        }
        
        permission_dep = require_permission("special_permission")
        user = await permission_dep(mock_user)
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_require_permission_insufficient(self):
        """Test permission requirement with insufficient permissions."""
        mock_user = {
            "user_id": "test-user",
            "permissions": ["read"]
        }
        
        permission_dep = require_permission("write")
        
        with pytest.raises(HTTPException) as exc_info:
            await permission_dep(mock_user)
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_role_valid(self):
        """Test role requirement with valid role."""
        mock_user = {
            "user_id": "test-user",
            "roles": ["trader", "analyst"]
        }
        
        role_dep = require_role("trader")
        user = await role_dep(mock_user)
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_require_role_admin_bypass(self):
        """Test role requirement with admin role bypass."""
        mock_user = {
            "user_id": "admin-user",
            "roles": ["admin"]
        }
        
        role_dep = require_role("special_role")
        user = await role_dep(mock_user)
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_require_role_insufficient(self):
        """Test role requirement with insufficient role."""
        mock_user = {
            "user_id": "test-user",
            "roles": ["viewer"]
        }
        
        role_dep = require_role("trader")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_dep(mock_user)
        
        assert exc_info.value.status_code == 403
        assert "Insufficient role" in str(exc_info.value.detail)


class TestDatabaseDependencies:
    """Test database-related dependencies."""
    
    @patch('trading_platform.api.dependencies.get_db_session')
    def test_get_database_session(self, mock_get_db_session):
        """Test database session dependency."""
        mock_session = Mock()
        mock_get_db_session.return_value = mock_session
        
        from trading_platform.api.dependencies import get_database_session
        
        # Test the generator
        session_gen = get_database_session()
        session = next(session_gen)
        
        assert session == mock_session
        
        # Test cleanup
        try:
            next(session_gen)
        except StopIteration:
            pass  # Expected
        
        mock_session.close.assert_called_once()


class TestServiceDependencies:
    """Test service dependency functions."""
    
    @pytest.fixture
    def mock_container(self):
        """Create mock service container."""
        container = Mock()
        container.data_ingestion = Mock()
        container.performance_calculator = Mock()
        container.temporal_analyzer = Mock()
        container.account_comparator = Mock()
        container.model_trainer = Mock()
        container.prediction_service = Mock()
        container.monte_carlo_simulator = Mock()
        container.risk_calculator = Mock()
        container.recommendation_service = Mock()
        return container
    
    def test_get_data_ingestion_service(self, mock_container):
        """Test data ingestion service dependency."""
        from trading_platform.api.dependencies import get_data_ingestion_service
        
        service = get_data_ingestion_service(mock_container)
        assert service == mock_container.data_ingestion
    
    def test_get_performance_calculator(self, mock_container):
        """Test performance calculator dependency."""
        from trading_platform.api.dependencies import get_performance_calculator
        
        service = get_performance_calculator(mock_container)
        assert service == mock_container.performance_calculator
    
    def test_get_temporal_analyzer(self, mock_container):
        """Test temporal analyzer dependency."""
        from trading_platform.api.dependencies import get_temporal_analyzer
        
        service = get_temporal_analyzer(mock_container)
        assert service == mock_container.temporal_analyzer
    
    def test_get_account_comparator(self, mock_container):
        """Test account comparator dependency."""
        from trading_platform.api.dependencies import get_account_comparator
        
        service = get_account_comparator(mock_container)
        assert service == mock_container.account_comparator
    
    def test_get_model_trainer(self, mock_container):
        """Test model trainer dependency."""
        from trading_platform.api.dependencies import get_model_trainer
        
        service = get_model_trainer(mock_container)
        assert service == mock_container.model_trainer
    
    def test_get_prediction_service(self, mock_container):
        """Test prediction service dependency."""
        from trading_platform.api.dependencies import get_prediction_service
        
        service = get_prediction_service(mock_container)
        assert service == mock_container.prediction_service
    
    def test_get_monte_carlo_simulator(self, mock_container):
        """Test Monte Carlo simulator dependency."""
        from trading_platform.api.dependencies import get_monte_carlo_simulator
        
        service = get_monte_carlo_simulator(mock_container)
        assert service == mock_container.monte_carlo_simulator
    
    def test_get_risk_calculator(self, mock_container):
        """Test risk calculator dependency."""
        from trading_platform.api.dependencies import get_risk_calculator
        
        service = get_risk_calculator(mock_container)
        assert service == mock_container.risk_calculator
    
    def test_get_recommendation_service(self, mock_container):
        """Test recommendation service dependency."""
        from trading_platform.api.dependencies import get_recommendation_service
        
        service = get_recommendation_service(mock_container)
        assert service == mock_container.recommendation_service


if __name__ == "__main__":
    pytest.main([__file__])