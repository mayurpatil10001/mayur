"""
Custom exceptions for the Trading Platform API.

This module defines custom exception classes for consistent error handling
across the API endpoints.

Requirements: 10.1, 10.4
"""

from typing import Any, Dict, Optional


class TradingPlatformException(Exception):
    """Base exception for trading platform errors."""
    
    def __init__(
        self,
        message: str,
        error_type: str = "TRADING_PLATFORM_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize trading platform exception.
        
        Args:
            message: Human-readable error message
            error_type: Error type identifier
            status_code: HTTP status code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.details = details or {}


class ValidationException(TradingPlatformException):
    """Exception for data validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        """
        Initialize validation exception.
        
        Args:
            message: Validation error message
            field: Field that failed validation
            value: Value that failed validation
        """
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(
            message=message,
            error_type="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class DataNotFoundException(TradingPlatformException):
    """Exception for when requested data is not found."""
    
    def __init__(self, resource: str, identifier: Any):
        """
        Initialize data not found exception.
        
        Args:
            resource: Type of resource that was not found
            identifier: Identifier used to search for resource
        """
        message = f"{resource} not found"
        details = {
            "resource": resource,
            "identifier": str(identifier)
        }
        
        super().__init__(
            message=message,
            error_type="DATA_NOT_FOUND",
            status_code=404,
            details=details
        )


class ServiceException(TradingPlatformException):
    """Exception for service layer errors."""
    
    def __init__(self, service: str, operation: str, message: str, cause: Optional[Exception] = None):
        """
        Initialize service exception.
        
        Args:
            service: Name of the service that failed
            operation: Operation that failed
            message: Error message
            cause: Original exception that caused this error
        """
        details = {
            "service": service,
            "operation": operation
        }
        
        if cause:
            details["cause"] = str(cause)
            details["cause_type"] = type(cause).__name__
        
        super().__init__(
            message=f"{service} service error during {operation}: {message}",
            error_type="SERVICE_ERROR",
            status_code=500,
            details=details
        )


class DatabaseException(TradingPlatformException):
    """Exception for database-related errors."""
    
    def __init__(self, operation: str, message: str, cause: Optional[Exception] = None):
        """
        Initialize database exception.
        
        Args:
            operation: Database operation that failed
            message: Error message
            cause: Original database exception
        """
        details = {
            "operation": operation
        }
        
        if cause:
            details["cause"] = str(cause)
            details["cause_type"] = type(cause).__name__
        
        super().__init__(
            message=f"Database error during {operation}: {message}",
            error_type="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class AuthenticationException(TradingPlatformException):
    """Exception for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed"):
        """
        Initialize authentication exception.
        
        Args:
            message: Authentication error message
        """
        super().__init__(
            message=message,
            error_type="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationException(TradingPlatformException):
    """Exception for authorization errors."""
    
    def __init__(self, required_permission: str, user_permissions: list):
        """
        Initialize authorization exception.
        
        Args:
            required_permission: Permission that was required
            user_permissions: Permissions the user has
        """
        message = f"Insufficient permissions. Required: {required_permission}"
        details = {
            "required_permission": required_permission,
            "user_permissions": user_permissions
        }
        
        super().__init__(
            message=message,
            error_type="AUTHORIZATION_ERROR",
            status_code=403,
            details=details
        )


class RateLimitException(TradingPlatformException):
    """Exception for rate limiting errors."""
    
    def __init__(self, limit: int, window: int, retry_after: int):
        """
        Initialize rate limit exception.
        
        Args:
            limit: Rate limit threshold
            window: Time window in seconds
            retry_after: Seconds to wait before retrying
        """
        message = f"Rate limit exceeded: {limit} requests per {window} seconds"
        details = {
            "limit": limit,
            "window": window,
            "retry_after": retry_after
        }
        
        super().__init__(
            message=message,
            error_type="RATE_LIMIT_ERROR",
            status_code=429,
            details=details
        )


class ConfigurationException(TradingPlatformException):
    """Exception for configuration errors."""
    
    def __init__(self, setting: str, message: str):
        """
        Initialize configuration exception.
        
        Args:
            setting: Configuration setting that is invalid
            message: Error message
        """
        details = {
            "setting": setting
        }
        
        super().__init__(
            message=f"Configuration error for '{setting}': {message}",
            error_type="CONFIGURATION_ERROR",
            status_code=500,
            details=details
        )


class ExternalServiceException(TradingPlatformException):
    """Exception for external service errors."""
    
    def __init__(self, service: str, operation: str, message: str, status_code: Optional[int] = None):
        """
        Initialize external service exception.
        
        Args:
            service: Name of external service
            operation: Operation that failed
            message: Error message
            status_code: HTTP status code from external service
        """
        details = {
            "service": service,
            "operation": operation
        }
        
        if status_code:
            details["external_status_code"] = status_code
        
        super().__init__(
            message=f"External service '{service}' error during {operation}: {message}",
            error_type="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details
        )