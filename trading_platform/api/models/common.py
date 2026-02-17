"""
Common Pydantic models for API requests and responses.

This module contains shared models used across multiple API endpoints.

Requirements: 10.1, 10.4
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


T = TypeVar('T')


class ResponseStatus(str, Enum):
    """Response status enumeration."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    status: ResponseStatus = Field(
        description="Response status",
        example=ResponseStatus.SUCCESS
    )
    
    message: str = Field(
        description="Human-readable message",
        example="Operation completed successfully"
    )
    
    data: Optional[T] = Field(
        default=None,
        description="Response data"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response timestamp"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for tracking"
    )


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str = Field(
        description="Error type identifier",
        example="VALIDATION_ERROR"
    )
    
    message: str = Field(
        description="Human-readable error message",
        example="Invalid input data"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    
    timestamp: float = Field(
        description="Error timestamp",
        example=1640995200.0
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for tracking"
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-based)",
        example=1
    )
    
    size: int = Field(
        default=50,
        ge=1,
        le=1000000,
        description="Number of items per page",
        example=50
    )
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    items: List[T] = Field(
        description="List of items for current page"
    )
    
    total: int = Field(
        description="Total number of items",
        example=150
    )
    
    page: int = Field(
        description="Current page number",
        example=1
    )
    
    size: int = Field(
        description="Items per page",
        example=50
    )
    
    pages: int = Field(
        description="Total number of pages",
        example=3
    )
    
    has_next: bool = Field(
        description="Whether there is a next page",
        example=True
    )
    
    has_prev: bool = Field(
        description="Whether there is a previous page",
        example=False
    )


class DateRangeFilter(BaseModel):
    """Date range filter for time-based queries."""
    
    start_date: Optional[datetime] = Field(
        default=None,
        description="Start date for filtering (inclusive)",
        example="2024-01-01T00:00:00Z"
    )
    
    end_date: Optional[datetime] = Field(
        default=None,
        description="End date for filtering (inclusive)",
        example="2024-12-31T23:59:59Z"
    )
    
    def validate_range(self) -> None:
        """Validate that start_date is before end_date."""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")


class SortParams(BaseModel):
    """Sorting parameters for list endpoints."""
    
    sort_by: str = Field(
        default="created_at",
        description="Field to sort by",
        example="created_at"
    )
    
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc or desc)",
        example="desc"
    )


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(
        description="Overall system status",
        example="healthy"
    )
    
    timestamp: float = Field(
        description="Health check timestamp",
        example=1640995200.0
    )
    
    version: str = Field(
        description="API version",
        example="1.0.0"
    )
    
    database: str = Field(
        description="Database status",
        example="connected"
    )
    
    services: str = Field(
        description="Services status",
        example="operational"
    )
    
    uptime: Optional[float] = Field(
        default=None,
        description="System uptime in seconds",
        example=3600.0
    )


class ValidationErrorDetail(BaseModel):
    """Validation error detail model."""
    
    field: str = Field(
        description="Field that failed validation",
        example="email"
    )
    
    message: str = Field(
        description="Validation error message",
        example="Invalid email format"
    )
    
    value: Optional[Any] = Field(
        default=None,
        description="Value that failed validation"
    )


class BulkOperationRequest(BaseModel, Generic[T]):
    """Generic bulk operation request."""
    
    items: List[T] = Field(
        description="List of items to process",
        min_items=1,
        max_items=1000
    )
    
    validate_only: bool = Field(
        default=False,
        description="Only validate items without processing"
    )


class BulkOperationResponse(BaseModel):
    """Bulk operation response model."""
    
    total_items: int = Field(
        description="Total number of items processed",
        example=100
    )
    
    successful_items: int = Field(
        description="Number of successfully processed items",
        example=95
    )
    
    failed_items: int = Field(
        description="Number of failed items",
        example=5
    )
    
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of errors for failed items"
    )
    
    processing_time: float = Field(
        description="Total processing time in seconds",
        example=2.5
    )