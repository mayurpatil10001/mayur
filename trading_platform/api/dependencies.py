"""
Dependency injection for FastAPI endpoints.

This module provides dependency injection functions for database sessions,
service instances, and other shared resources.

Requirements: 10.1, 10.4
"""

from functools import lru_cache
from typing import Generator, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging

from ..database.database import get_db_session
from ..services.data_ingestion_service import SierraChartDataIngestionService
from ..services.performance_metrics_calculator import PerformanceMetricsCalculator
from ..services.temporal_analysis_service import TemporalAnalysisService
from ..services.account_comparison_service import AccountComparisonService
from ..services.machine_learning.prediction_service import PredictionService
from ..services.machine_learning.model_trainer import ModelTrainer
# Temporarily disabled Monte Carlo imports to fix startup issues
# from ..services.monte_carlo.monte_carlo_simulator import MonteCarloSimulator
# from ..services.monte_carlo.risk_calculator import RiskCalculator
from ..services.recommendation.recommendation_service import RecommendationService
from ..services.auth_service import Permission, UserRole
from ..config import config


logger = logging.getLogger(__name__)

# Security scheme for JWT authentication
security = HTTPBearer(auto_error=False)


class ServiceContainer:
    """Container for all application services."""
    
    def __init__(self, db_session: Session):
        """Initialize service container with database session."""
        self.db_session = db_session
        self._services: Dict[str, Any] = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all services with proper dependencies."""
        try:
            # Data services
            self._services['data_ingestion'] = SierraChartDataIngestionService()
            self._services['performance_calculator'] = PerformanceMetricsCalculator()
            self._services['temporal_analyzer'] = TemporalAnalysisService()
            self._services['account_comparator'] = AccountComparisonService()
            
            # Machine learning services
            self._services['model_trainer'] = ModelTrainer()
            self._services['prediction_service'] = PredictionService()
            
            # Monte Carlo services - temporarily disabled
            # self._services['monte_carlo_simulator'] = MonteCarloSimulator()
            # self._services['risk_calculator'] = RiskCalculator()
            
            # Recommendation service
            self._services['recommendation_service'] = RecommendationService()
            
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    def get_service(self, service_name: str) -> Any:
        """Get service by name."""
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not found")
        return self._services[service_name]
    
    @property
    def data_ingestion(self) -> SierraChartDataIngestionService:
        """Get data ingestion service."""
        return self._services['data_ingestion']
    
    @property
    def performance_calculator(self) -> PerformanceMetricsCalculator:
        """Get performance metrics calculator."""
        return self._services['performance_calculator']
    
    @property
    def temporal_analyzer(self) -> TemporalAnalysisService:
        """Get temporal analysis service."""
        return self._services['temporal_analyzer']
    
    @property
    def account_comparator(self) -> AccountComparisonService:
        """Get account comparison service."""
        return self._services['account_comparator']
    
    @property
    def model_trainer(self) -> ModelTrainer:
        """Get model trainer service."""
        return self._services['model_trainer']
    
    @property
    def prediction_service(self) -> PredictionService:
        """Get prediction service."""
        return self._services['prediction_service']
    
    # Temporarily disabled Monte Carlo properties
    # @property
    # def monte_carlo_simulator(self) -> MonteCarloSimulator:
    #     """Get Monte Carlo simulator."""
    #     return self._services['monte_carlo_simulator']
    # 
    # @property
    # def risk_calculator(self) -> RiskCalculator:
    #     """Get risk calculator."""
    #     return self._services['risk_calculator']
    
    @property
    def recommendation_service(self) -> RecommendationService:
        """Get recommendation service."""
        return self._services['recommendation_service']


# Global service container instance
_service_container: ServiceContainer = None


def get_database_session() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    
    Yields:
        Database session
    """
    db_gen = get_db_session()
    db = next(db_gen)
    try:
        yield db
    finally:
        db.close()


@lru_cache()
def get_service_container() -> ServiceContainer:
    """
    Get or create service container singleton.
    
    Returns:
        ServiceContainer instance
    """
    global _service_container
    
    if _service_container is None:
        # Create a database session for service initialization
        db_session = next(get_database_session())
        _service_container = ServiceContainer(db_session)
    
    return _service_container


def get_data_ingestion_service(
    container: ServiceContainer = Depends(get_service_container)
) -> SierraChartDataIngestionService:
    """Get data ingestion service dependency."""
    return container.data_ingestion


def get_performance_calculator(
    container: ServiceContainer = Depends(get_service_container)
) -> PerformanceMetricsCalculator:
    """Get performance metrics calculator dependency."""
    return container.performance_calculator


def get_temporal_analyzer(
    container: ServiceContainer = Depends(get_service_container)
) -> TemporalAnalysisService:
    """Get temporal analysis service dependency."""
    return container.temporal_analyzer


def get_account_comparator(
    container: ServiceContainer = Depends(get_service_container)
) -> AccountComparisonService:
    """Get account comparison service dependency."""
    return container.account_comparator


def get_model_trainer(
    container: ServiceContainer = Depends(get_service_container)
) -> ModelTrainer:
    """Get model trainer service dependency."""
    return container.model_trainer


def get_prediction_service(
    container: ServiceContainer = Depends(get_service_container)
) -> PredictionService:
    """Get prediction service dependency."""
    return container.prediction_service


# Temporarily disabled Monte Carlo dependency functions
# def get_monte_carlo_simulator(
#     container: ServiceContainer = Depends(get_service_container)
# ) -> MonteCarloSimulator:
#     """Get Monte Carlo simulator dependency."""
#     return container.monte_carlo_simulator
# 
# 
# def get_risk_calculator(
#     container: ServiceContainer = Depends(get_service_container)
# ) -> RiskCalculator:
#     """Get risk calculator dependency."""
#     return container.risk_calculator


def get_recommendation_service(
    container: ServiceContainer = Depends(get_service_container)
) -> RecommendationService:
    """Get recommendation service dependency."""
    return container.recommendation_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    from ..config import config
    
    # In development mode, return a default user without checking credentials
    if getattr(config, 'DEVELOPMENT_MODE', True):
        return {
            "user_id": "dev_user",
            "username": "developer",
            "permissions": ["read", "write", "admin"],
            "role": "admin"
        }
    
    from ..services.auth_service import get_auth_service
    
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify JWT token
    auth_service = get_auth_service()
    token_data = auth_service.verify_token(credentials.credentials)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


def require_permission(permission: str):
    """
    Dependency factory for permission-based access control.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    async def permission_dependency(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has required permission."""
        user_permissions = current_user.get("permissions", [])
        
        if permission not in user_permissions and "admin" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        
        return current_user
    
    return permission_dependency


def require_role(role: str):
    """
    Dependency factory for role-based access control.
    
    Args:
        role: Required role
        
    Returns:
        Dependency function
    """
    async def role_dependency(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has required role."""
        user_roles = current_user.get("roles", [])
        
        if role not in user_roles and "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role}"
            )
        
        return current_user
    
    return role_dependency


# Common permission dependencies
require_read_permission = require_permission("read")
require_write_permission = require_permission("write")
require_admin_permission = require_permission("admin")

# Common role dependencies
require_trader_role = require_role("trader")
require_admin_role = require_role("admin")


def get_time_bin_analyzer():
    """Get time bin analyzer dependency (placeholder)."""
    # Placeholder function to fix import error
    # TODO: Implement actual time bin analyzer
    return None