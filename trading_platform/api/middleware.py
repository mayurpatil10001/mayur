"""
Custom middleware for the Trading Platform API.

This module provides custom middleware for logging, error handling,
and request processing.

Requirements: 10.1, 10.4
"""

import time
import logging
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .exceptions import TradingPlatformException
from ..services.monitoring.metrics_collector import metrics_collector


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    def __init__(self, app: ASGIApp):
        """Initialize logging middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"from {client_ip} - Query: {dict(request.query_params)}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Response {request_id}: {response.status_code} "
                f"in {process_time:.4f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            logger.error(
                f"Error {request_id}: {type(e).__name__}: {str(e)} "
                f"in {process_time:.4f}s",
                exc_info=True
            )
            
            # Re-raise to be handled by error middleware
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for consistent error handling."""
    
    def __init__(self, app: ASGIApp):
        """Initialize error handling middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with error handling."""
        try:
            return await call_next(request)
            
        except TradingPlatformException as e:
            # Handle custom trading platform exceptions
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.error_type,
                    "message": e.message,
                    "details": e.details,
                    "timestamp": time.time(),
                    "request_id": getattr(request.state, "request_id", None)
                }
            )
            
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "timestamp": time.time(),
                    "request_id": getattr(request.state, "request_id", None)
                }
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: ASGI application
            requests_per_minute: Maximum requests per minute per IP
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}  # In production, use Redis or similar
        self.window_size = 60  # 1 minute window
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries
        self._clean_old_entries(current_time)
        
        # Check rate limit
        if self._is_rate_limited(client_ip, current_time):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                    "retry_after": 60,
                    "timestamp": current_time
                },
                headers={"Retry-After": "60"}
            )
        
        # Record request
        self._record_request(client_ip, current_time)
        
        return await call_next(request)
    
    def _clean_old_entries(self, current_time: float) -> None:
        """Remove old entries from request counts."""
        cutoff_time = current_time - self.window_size
        
        for ip in list(self.request_counts.keys()):
            self.request_counts[ip] = [
                timestamp for timestamp in self.request_counts[ip]
                if timestamp > cutoff_time
            ]
            
            if not self.request_counts[ip]:
                del self.request_counts[ip]
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if client IP is rate limited."""
        if client_ip not in self.request_counts:
            return False
        
        return len(self.request_counts[client_ip]) >= self.requests_per_minute
    
    def _record_request(self, client_ip: str, current_time: float) -> None:
        """Record a request for the client IP."""
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        self.request_counts[client_ip].append(current_time)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    def __init__(self, app: ASGIApp):
        """Initialize security headers middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers."""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        
        return response


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting API metrics and monitoring."""
    
    def __init__(self, app: ASGIApp):
        """Initialize monitoring middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Record metrics
            metrics_collector.record_request_metrics(
                endpoint=request.url.path,
                method=request.method,
                response_time=response_time,
                status_code=response.status_code
            )
            
            return response
            
        except Exception as e:
            # Record error metrics
            response_time = (time.time() - start_time) * 1000
            metrics_collector.record_request_metrics(
                endpoint=request.url.path,
                method=request.method,
                response_time=response_time,
                status_code=500
            )
            
            # Re-raise to be handled by error middleware
            raise