"""
Authentication and authorization service.

This module provides JWT-based authentication and role-based access control.

Requirements: 9.1, 9.3, 10.5
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import secrets
import logging

from ..config import config


logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    TRADER = "trader"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Permission enumeration."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    TRADE = "trade"
    ANALYZE = "analyze"


@dataclass
class User:
    """User data class."""
    user_id: str
    username: str
    email: str
    roles: List[UserRole]
    permissions: List[Permission]
    is_active: bool = True
    created_at: datetime = None
    last_login: datetime = None


class AuthenticationService:
    """JWT-based authentication service."""
    
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize authentication service.
        
        Args:
            secret_key: JWT secret key (defaults to config value)
            algorithm: JWT algorithm
        """
        self.secret_key = secret_key or getattr(config, 'JWT_SECRET_KEY', self._generate_secret_key())
        self.algorithm = algorithm
        self.token_expiry_hours = getattr(config, 'JWT_EXPIRY_HOURS', 24)
        
        # Mock user database (in production, this would be a real database)
        self._users: Dict[str, User] = self._initialize_mock_users()
        self._user_credentials: Dict[str, str] = self._initialize_mock_credentials()
        
        logger.info("Authentication service initialized")
    
    def _generate_secret_key(self) -> str:
        """Generate a secure secret key."""
        return secrets.token_urlsafe(32)
    
    def _initialize_mock_users(self) -> Dict[str, User]:
        """Initialize mock users for development."""
        return {
            "admin": User(
                user_id="admin",
                username="admin",
                email="admin@tradingplatform.com",
                roles=[UserRole.ADMIN],
                permissions=[Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN, Permission.TRADE, Permission.ANALYZE],
                created_at=datetime.now()
            ),
            "trader": User(
                user_id="trader",
                username="trader",
                email="trader@tradingplatform.com",
                roles=[UserRole.TRADER],
                permissions=[Permission.READ, Permission.WRITE, Permission.TRADE, Permission.ANALYZE],
                created_at=datetime.now()
            ),
            "analyst": User(
                user_id="analyst",
                username="analyst",
                email="analyst@tradingplatform.com",
                roles=[UserRole.ANALYST],
                permissions=[Permission.READ, Permission.ANALYZE],
                created_at=datetime.now()
            ),
            "viewer": User(
                user_id="viewer",
                username="viewer",
                email="viewer@tradingplatform.com",
                roles=[UserRole.VIEWER],
                permissions=[Permission.READ],
                created_at=datetime.now()
            )
        }
    
    def _initialize_mock_credentials(self) -> Dict[str, str]:
        """Initialize mock user credentials (hashed passwords)."""
        credentials = {}
        
        # Hash passwords for mock users
        for username in ["admin", "trader", "analyst", "viewer"]:
            password = f"{username}123"  # Simple passwords for development
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            credentials[username] = hashed.decode('utf-8')
        
        return credentials
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            # Check if user exists
            if username not in self._users:
                logger.warning(f"Authentication failed: user '{username}' not found")
                return None
            
            # Check if user is active
            user = self._users[username]
            if not user.is_active:
                logger.warning(f"Authentication failed: user '{username}' is inactive")
                return None
            
            # Verify password
            stored_hash = self._user_credentials.get(username)
            if not stored_hash:
                logger.warning(f"Authentication failed: no credentials for user '{username}'")
                return None
            
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                logger.warning(f"Authentication failed: invalid password for user '{username}'")
                return None
            
            # Update last login
            user.last_login = datetime.now()
            
            logger.info(f"User '{username}' authenticated successfully")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error for user '{username}': {e}")
            return None
    
    def create_access_token(self, user: User) -> str:
        """
        Create JWT access token for user.
        
        Args:
            user: User object
            
        Returns:
            JWT token string
        """
        try:
            # Token payload
            payload = {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "roles": [role.value for role in user.roles],
                "permissions": [perm.value for perm in user.permissions],
                "exp": datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
                "iat": datetime.utcnow(),
                "iss": "trading-platform-api"
            }
            
            # Create token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Access token created for user '{user.username}'")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create access token for user '{user.username}': {e}")
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if user still exists and is active
            username = payload.get("username")
            if username not in self._users or not self._users[username].is_active:
                logger.warning(f"Token verification failed: user '{username}' not found or inactive")
                return None
            
            logger.debug(f"Token verified successfully for user '{username}'")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: invalid token - {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def refresh_token(self, token: str) -> Optional[str]:
        """
        Refresh JWT token.
        
        Args:
            token: Current JWT token
            
        Returns:
            New JWT token if refresh successful, None otherwise
        """
        try:
            # Verify current token (allow expired tokens for refresh)
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], options={"verify_exp": False})
            
            username = payload.get("username")
            if username not in self._users:
                return None
            
            user = self._users[username]
            if not user.is_active:
                return None
            
            # Create new token
            new_token = self.create_access_token(user)
            
            logger.info(f"Token refreshed for user '{username}'")
            return new_token
            
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    def has_permission(self, user_data: Dict[str, Any], required_permission: Permission) -> bool:
        """
        Check if user has required permission.
        
        Args:
            user_data: User data from token
            required_permission: Required permission
            
        Returns:
            True if user has permission, False otherwise
        """
        user_permissions = user_data.get("permissions", [])
        
        # Admin permission grants all access
        if Permission.ADMIN.value in user_permissions:
            return True
        
        # Check specific permission
        return required_permission.value in user_permissions
    
    def has_role(self, user_data: Dict[str, Any], required_role: UserRole) -> bool:
        """
        Check if user has required role.
        
        Args:
            user_data: User data from token
            required_role: Required role
            
        Returns:
            True if user has role, False otherwise
        """
        user_roles = user_data.get("roles", [])
        
        # Admin role grants all access
        if UserRole.ADMIN.value in user_roles:
            return True
        
        # Check specific role
        return required_role.value in user_roles
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User object if found, None otherwise
        """
        for user in self._users.values():
            if user.user_id == user_id:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.
        
        Args:
            username: Username
            
        Returns:
            User object if found, None otherwise
        """
        return self._users.get(username)
    
    def create_user(self, username: str, email: str, password: str, roles: List[UserRole]) -> User:
        """
        Create new user.
        
        Args:
            username: Username
            email: Email address
            password: Password
            roles: User roles
            
        Returns:
            Created user object
            
        Raises:
            ValueError: If user already exists
        """
        if username in self._users:
            raise ValueError(f"User '{username}' already exists")
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self._user_credentials[username] = hashed_password.decode('utf-8')
        
        # Determine permissions based on roles
        permissions = self._get_permissions_for_roles(roles)
        
        # Create user
        user = User(
            user_id=username,  # Using username as ID for simplicity
            username=username,
            email=email,
            roles=roles,
            permissions=permissions,
            created_at=datetime.now()
        )
        
        self._users[username] = user
        
        logger.info(f"User '{username}' created with roles: {[r.value for r in roles]}")
        return user
    
    def _get_permissions_for_roles(self, roles: List[UserRole]) -> List[Permission]:
        """Get permissions for given roles."""
        permissions = set()
        
        for role in roles:
            if role == UserRole.ADMIN:
                permissions.update([Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN, Permission.TRADE, Permission.ANALYZE])
            elif role == UserRole.TRADER:
                permissions.update([Permission.READ, Permission.WRITE, Permission.TRADE, Permission.ANALYZE])
            elif role == UserRole.ANALYST:
                permissions.update([Permission.READ, Permission.ANALYZE])
            elif role == UserRole.VIEWER:
                permissions.add(Permission.READ)
        
        return list(permissions)
    
    def deactivate_user(self, username: str) -> bool:
        """
        Deactivate user.
        
        Args:
            username: Username
            
        Returns:
            True if user was deactivated, False if user not found
        """
        if username in self._users:
            self._users[username].is_active = False
            logger.info(f"User '{username}' deactivated")
            return True
        return False
    
    def activate_user(self, username: str) -> bool:
        """
        Activate user.
        
        Args:
            username: Username
            
        Returns:
            True if user was activated, False if user not found
        """
        if username in self._users:
            self._users[username].is_active = True
            logger.info(f"User '{username}' activated")
            return True
        return False


# Global authentication service instance
_auth_service: Optional[AuthenticationService] = None


def get_auth_service() -> AuthenticationService:
    """Get or create authentication service singleton."""
    global _auth_service
    
    if _auth_service is None:
        _auth_service = AuthenticationService()
    
    return _auth_service