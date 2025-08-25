"""
Pydantic models for export-related API endpoints.

This module contains request/response models for data export endpoints including
time-bin data exports, PDF reports, chart generation, and export history management.

Requirements: 13.1, 13.6, 10.1
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
import uuid


class ExportFormat(str, Enum):
    """Export format options."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PDF = "pdf"
    PNG = "png"
    
    
class ExportType(str, Enum):
    """Export type options."""
    TIME_BIN_TRADES = "time_bin_trades"
    ANALYSIS_RESULTS = "analysis_results"
    MARKET_CORRELATION = "market_correlation"
    PERFORMANCE_REPORT = "performance_report"
    COMPREHENSIVE_PACKAGE = "comprehensive_package"


class ExportStatus(str, Enum):
    """Export status options."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ChartType(str, Enum):
    """Chart type options for export."""
    EQUITY_CURVE = "equity_curve"
    DRAWDOWN = "drawdown"
    MONTHLY_RETURNS = "monthly_returns"
    PERFORMANCE_METRICS = "performance_metrics"


class ExportRequest(BaseModel):
    """Request model for data export."""
    
    export_type: ExportType = Field(
        description="Type of export to generate",
        example="time_bin_trades"
    )
    
    export_format: ExportFormat = Field(
        description="Output format for the export",
        example="csv"
    )
    
    start_date: Optional[date] = Field(
        None,
        description="Start date for data filter",
        example="2024-01-01"
    )
    
    end_date: Optional[date] = Field(
        None,
        description="End date for data filter", 
        example="2024-01-31"
    )
    
    include_charts: bool = Field(
        default=False,
        description="Whether to include visual charts in the export"
    )
    
    chart_types: Optional[List[ChartType]] = Field(
        None,
        description="Types of charts to include if include_charts is True"
    )
    
    compression: bool = Field(
        default=False,
        description="Whether to compress the export file"
    )
    
    email_notification: bool = Field(
        default=False,
        description="Whether to send email when export is ready"
    )
    
    custom_filename: Optional[str] = Field(
        None,
        description="Custom filename for the export",
        max_length=100
    )
    
    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        """Validate that end_date is after start_date."""
        if v and 'start_date' in values and values['start_date']:
            if v <= values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v
    
    @validator('chart_types')
    def chart_types_required_if_include_charts(cls, v, values):
        """Validate that chart_types is provided if include_charts is True."""
        if values.get('include_charts') and not v:
            raise ValueError('chart_types must be specified when include_charts is True')
        return v


class ExportConfiguration(BaseModel):
    """Configuration options for export generation."""
    
    decimal_places: int = Field(
        default=4,
        ge=0,
        le=10,
        description="Number of decimal places for numeric values"
    )
    
    include_metadata: bool = Field(
        default=True,
        description="Whether to include metadata in the export"
    )
    
    timezone: str = Field(
        default="UTC",
        description="Timezone for timestamp formatting"
    )
    
    currency_symbol: str = Field(
        default="$",
        description="Currency symbol for monetary values"
    )
    
    page_size: Optional[str] = Field(
        "letter",
        description="Page size for PDF exports",
        pattern="^(letter|A4|legal)$"
    )
    
    chart_dpi: int = Field(
        default=300,
        ge=72,
        le=600,
        description="DPI for chart image generation"
    )


class ExportProgressResponse(BaseModel):
    """Progress tracking response for export operations."""
    
    export_id: str = Field(
        description="Unique identifier for the export",
        example="exp_12345-abcd-6789-efgh"
    )
    
    status: ExportStatus = Field(
        description="Current status of the export"
    )
    
    progress_percentage: float = Field(
        description="Completion percentage (0-100)",
        ge=0,
        le=100,
        example=75.5
    )
    
    current_step: str = Field(
        description="Current processing step",
        example="Generating charts"
    )
    
    estimated_completion_time: Optional[datetime] = Field(
        None,
        description="Estimated completion timestamp"
    )
    
    message: Optional[str] = Field(
        None,
        description="Status message or error details"
    )
    
    created_at: datetime = Field(
        description="Export creation timestamp"
    )
    
    updated_at: datetime = Field(
        description="Last update timestamp"
    )


class ExportResult(BaseModel):
    """Result model for completed exports."""
    
    export_id: str = Field(
        description="Unique identifier for the export"
    )
    
    download_url: str = Field(
        description="URL to download the export file",
        example="/api/exports/exp_12345/download"
    )
    
    file_name: str = Field(
        description="Name of the generated file",
        example="time_bin_trades_2024-01-01_2024-01-31.csv"
    )
    
    file_size_bytes: int = Field(
        description="Size of the export file in bytes",
        example=1048576
    )
    
    mime_type: str = Field(
        description="MIME type of the export file",
        example="text/csv"
    )
    
    export_type: ExportType = Field(
        description="Type of export that was generated"
    )
    
    export_format: ExportFormat = Field(
        description="Format of the export file"
    )
    
    expires_at: datetime = Field(
        description="Expiration timestamp for the download link"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the export"
    )


class ExportHistoryItem(BaseModel):
    """Historical export information."""
    
    export_id: str = Field(
        description="Unique identifier for the export"
    )
    
    account_name: str = Field(
        description="Account name for the export"
    )
    
    time_bin_hour: int = Field(
        description="Hour of the time bin",
        ge=0,
        le=23
    )
    
    time_bin_minute: int = Field(
        description="Minute of the time bin",
        ge=0,
        le=59
    )
    
    export_type: ExportType = Field(
        description="Type of export"
    )
    
    export_format: ExportFormat = Field(
        description="Format of export"
    )
    
    status: ExportStatus = Field(
        description="Current status"
    )
    
    created_at: datetime = Field(
        description="Creation timestamp"
    )
    
    completed_at: Optional[datetime] = Field(
        None,
        description="Completion timestamp"
    )
    
    file_size_bytes: Optional[int] = Field(
        None,
        description="Size of generated file in bytes"
    )
    
    download_count: int = Field(
        default=0,
        description="Number of times file was downloaded"
    )
    
    expires_at: Optional[datetime] = Field(
        None,
        description="Expiration timestamp"
    )


class ExportHistoryResponse(BaseModel):
    """Response model for export history."""
    
    exports: List[ExportHistoryItem] = Field(
        description="List of historical exports"
    )
    
    total_count: int = Field(
        description="Total number of exports"
    )
    
    page: int = Field(
        default=1,
        description="Current page number"
    )
    
    page_size: int = Field(
        default=20,
        description="Number of items per page"
    )
    
    total_pages: int = Field(
        description="Total number of pages"
    )


class ExportResponse(BaseModel):
    """Response model for export creation."""
    
    export_id: str = Field(
        description="Unique identifier for the export"
    )
    
    status: ExportStatus = Field(
        description="Initial status of the export"
    )
    
    status_url: str = Field(
        description="URL to check export status",
        example="/api/exports/exp_12345/status"
    )
    
    estimated_completion_time: Optional[datetime] = Field(
        None,
        description="Estimated completion time"
    )
    
    message: str = Field(
        description="Initial status message",
        example="Export queued for processing"
    )


class BulkExportRequest(BaseModel):
    """Request model for bulk export operations."""
    
    account_names: List[str] = Field(
        description="List of account names to export",
        min_items=1,
        max_items=10
    )
    
    time_bins: List[Dict[str, int]] = Field(
        description="List of time bins (hour, minute_bin pairs)",
        example=[{"hour": 9, "minute_bin": 30}, {"hour": 14, "minute_bin": 0}]
    )
    
    export_request: ExportRequest = Field(
        description="Export configuration to apply to all items"
    )
    
    create_combined_file: bool = Field(
        default=False,
        description="Whether to create a single combined file"
    )
    
    @validator('time_bins')
    def validate_time_bins(cls, v):
        """Validate time bin format."""
        for time_bin in v:
            if not isinstance(time_bin, dict):
                raise ValueError('time_bins must contain dict objects')
            if 'hour' not in time_bin or 'minute_bin' not in time_bin:
                raise ValueError('time_bins must contain hour and minute_bin keys')
            if not (0 <= time_bin['hour'] <= 23):
                raise ValueError('hour must be between 0 and 23')
            if not (0 <= time_bin['minute_bin'] <= 59):
                raise ValueError('minute_bin must be between 0 and 59')
        return v


class BulkExportResponse(BaseModel):
    """Response model for bulk export operations."""
    
    bulk_export_id: str = Field(
        description="Unique identifier for the bulk export"
    )
    
    individual_export_ids: List[str] = Field(
        description="List of individual export IDs"
    )
    
    total_exports: int = Field(
        description="Total number of exports in the bulk operation"
    )
    
    status_url: str = Field(
        description="URL to check bulk export status"
    )
    
    estimated_completion_time: Optional[datetime] = Field(
        None,
        description="Estimated completion time for all exports"
    )


class ExportCapacityResponse(BaseModel):
    """Response model for export system capacity."""
    
    active_exports: int = Field(
        description="Number of currently active exports"
    )
    
    max_concurrent_exports: int = Field(
        description="Maximum concurrent exports allowed"
    )
    
    queue_length: int = Field(
        description="Number of exports in queue"
    )
    
    available_capacity: int = Field(
        description="Available export slots"
    )
    
    estimated_queue_time: Optional[int] = Field(
        None,
        description="Estimated queue time in seconds"
    )
    
    system_health: str = Field(
        description="Overall system health status",
        example="healthy"
    )


class ExportCleanupRequest(BaseModel):
    """Request model for export cleanup operations."""
    
    older_than_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Delete exports older than this many days"
    )
    
    status_filter: Optional[List[ExportStatus]] = Field(
        None,
        description="Only clean up exports with these statuses"
    )
    
    dry_run: bool = Field(
        default=True,
        description="Whether to perform a dry run (show what would be deleted)"
    )


class ExportCleanupResponse(BaseModel):
    """Response model for export cleanup operations."""
    
    files_deleted: int = Field(
        description="Number of files deleted"
    )
    
    space_freed_bytes: int = Field(
        description="Amount of disk space freed in bytes"
    )
    
    cleanup_duration_seconds: float = Field(
        description="Time taken for cleanup operation"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered during cleanup"
    )
    
    dry_run: bool = Field(
        description="Whether this was a dry run"
    )


# Export format specific models
class CSVExportOptions(BaseModel):
    """Options specific to CSV exports."""
    
    delimiter: str = Field(
        default=",",
        description="CSV delimiter character"
    )
    
    include_headers: bool = Field(
        default=True,
        description="Whether to include column headers"
    )
    
    quote_all_fields: bool = Field(
        default=False,
        description="Whether to quote all CSV fields"
    )


class ExcelExportOptions(BaseModel):
    """Options specific to Excel exports."""
    
    sheet_name: str = Field(
        default="Data",
        description="Name of the Excel worksheet"
    )
    
    include_charts: bool = Field(
        default=False,
        description="Whether to include Excel charts"
    )
    
    freeze_header_row: bool = Field(
        default=True,
        description="Whether to freeze the header row"
    )


class PDFExportOptions(BaseModel):
    """Options specific to PDF exports."""
    
    include_executive_summary: bool = Field(
        default=True,
        description="Whether to include executive summary"
    )
    
    include_statistical_analysis: bool = Field(
        default=True,
        description="Whether to include statistical analysis section"
    )
    
    include_market_correlation: bool = Field(
        default=True,
        description="Whether to include market correlation analysis"
    )
    
    include_trade_details: bool = Field(
        default=True,
        description="Whether to include detailed trade information"
    )