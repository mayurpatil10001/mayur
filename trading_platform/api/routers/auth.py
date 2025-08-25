"""
Authentication API endpoints.

This module provides REST endpoints for user authentication and authorization.

Requirements: 9.1, 9.3, 10.5
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..dependencies import security, get_current_user
from ..models.common import APIResponse
from ..exceptions import AuthenticationException, ValidationException
from ...services.auth_service import get_auth_service, UserRole, Permission


router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model."""
    
    username: str = Field(
        description="Username",
        example="trader",
        min_length=3,
        max_length=50
    )
    
    password: str = Field(
        description="Password",
        example="trader123",
        min_length=6,
        max_length=100
    )


class LoginResponse(BaseModel):
    """Login response model."""
    
    access_token: str = Field(
        description="JWT access token",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    )
    
    token_type: str = Field(
        description="Token type",
        example="bearer"
    )
    
    expires_in: int = Field(
        description="Token expiry time in seconds",
        example=86400
    )
    
    user_info: Dict[str, Any] = Field(
        description="User information",
        example={
            "user_id": "trader",
            "username": "trader",
            "email": "trader@tradingplatform.com",
            "roles": ["trader"],
            "permissions": ["read", "write", "trade", "analyze"]
        }
    )


class TokenRefreshResponse(BaseModel):
    """Token refresh response model."""
    
    access_token: str = Field(
        description="New JWT access token",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    )
    
    token_type: str = Field(
        description="Token type",
        example="bearer"
    )
    
    expires_in: int = Field(
        description="Token expiry time in seconds",
        example=86400
    )


class UserInfoResponse(BaseModel):
    """User information response model."""
    
    user_id: str = Field(
        description="User ID",
        example="trader"
    )
    
    username: str = Field(
        description="Username",
        example="trader"
    )
    
    email: str = Field(
        description="Email address",
        example="trader@tradingplatform.com"
    )
    
    roles: list[str] = Field(
        description="User roles",
        example=["trader"]
    )
    
    permissions: list[str] = Field(
        description="User permissions",
        example=["read", "write", "trade", "analyze"]
    )
    
    is_active: bool = Field(
        description="Whether user is active",
        example=True
    )
    
    last_login: datetime = Field(
        description="Last login timestamp",
        example="2024-01-01T12:00:00Z"
    )


@router.post(
    "/login",
    response_model=APIResponse[LoginResponse],
    summary="User login",
    description="Authenticate user and return JWT access token."
)
async def login(login_request: LoginRequest) -> APIResponse[LoginResponse]:
    """Authenticate user and return access token."""
    
    try:
        auth_service = get_auth_service()
        
        # Authenticate user
        user = auth_service.authenticate_user(
            username=login_request.username,
            password=login_request.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create access token
        access_token = auth_service.create_access_token(user)
        
        # Prepare response
        login_response = LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=auth_service.token_expiry_hours * 3600,  # Convert hours to seconds
            user_info={
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "roles": [role.value for role in user.roles],
                "permissions": [perm.value for perm in user.permissions],
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
        )
        
        return APIResponse[LoginResponse](
            status="success",
            message=f"User '{user.username}' authenticated successfully",
            data=login_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post(
    "/refresh",
    response_model=APIResponse[TokenRefreshResponse],
    summary="Refresh token",
    description="Refresh JWT access token."
)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> APIResponse[TokenRefreshResponse]:
    """Refresh JWT access token."""
    
    try:
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token"
            )
        
        auth_service = get_auth_service()
        
        # Refresh token
        new_token = auth_service.refresh_token(credentials.credentials)
        
        if not new_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Prepare response
        refresh_response = TokenRefreshResponse(
            access_token=new_token,
            token_type="bearer",
            expires_in=auth_service.token_expiry_hours * 3600
        )
        
        return APIResponse[TokenRefreshResponse](
            status="success",
            message="Token refreshed successfully",
            data=refresh_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post(
    "/logout",
    response_model=APIResponse[None],
    summary="User logout",
    description="Logout user (invalidate token on client side)."
)
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> APIResponse[None]:
    """Logout user."""
    
    # Note: JWT tokens are stateless, so we can't invalidate them server-side
    # without maintaining a blacklist. For now, we just return success and
    # rely on the client to discard the token.
    
    return APIResponse[None](
        status="success",
        message=f"User '{current_user['username']}' logged out successfully"
    )


@router.get(
    "/me",
    response_model=APIResponse[UserInfoResponse],
    summary="Get current user info",
    description="Get information about the currently authenticated user."
)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> APIResponse[UserInfoResponse]:
    """Get current user information."""
    
    try:
        auth_service = get_auth_service()
        
        # Get full user information
        user = auth_service.get_user_by_username(current_user["username"])
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_info = UserInfoResponse(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            roles=[role.value for role in user.roles],
            permissions=[perm.value for perm in user.permissions],
            is_active=user.is_active,
            last_login=user.last_login or datetime.now()
        )
        
        return APIResponse[UserInfoResponse](
            status="success",
            message="User information retrieved successfully",
            data=user_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user information: {str(e)}"
        )


@router.get(
    "/permissions",
    response_model=APIResponse[Dict[str, Any]],
    summary="Get user permissions",
    description="Get detailed permissions for the current user."
)
async def get_user_permissions(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> APIResponse[Dict[str, Any]]:
    """Get user permissions."""
    
    try:
        auth_service = get_auth_service()
        
        permissions_info = {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "roles": current_user["roles"],
            "permissions": current_user["permissions"],
            "permission_details": {
                "can_read": auth_service.has_permission(current_user, Permission.READ),
                "can_write": auth_service.has_permission(current_user, Permission.WRITE),
                "can_delete": auth_service.has_permission(current_user, Permission.DELETE),
                "can_trade": auth_service.has_permission(current_user, Permission.TRADE),
                "can_analyze": auth_service.has_permission(current_user, Permission.ANALYZE),
                "is_admin": auth_service.has_permission(current_user, Permission.ADMIN)
            },
            "role_details": {
                "is_admin": auth_service.has_role(current_user, UserRole.ADMIN),
                "is_trader": auth_service.has_role(current_user, UserRole.TRADER),
                "is_analyst": auth_service.has_role(current_user, UserRole.ANALYST),
                "is_viewer": auth_service.has_role(current_user, UserRole.VIEWER)
            }
        }
        
        return APIResponse[Dict[str, Any]](
            status="success",
            message="User permissions retrieved successfully",
            data=permissions_info
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user permissions: {str(e)}"
        )