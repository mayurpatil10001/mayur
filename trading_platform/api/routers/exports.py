"""
Export API endpoints.

This module provides REST endpoints for data export operations including time-bin
trade exports, performance reports, chart generation, and export management.

Requirements: 13.1, 13.6, 10.1
"""

import os
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..dependencies import (
    get_database_session,
    get_time_bin_analyzer,
    require_read_permission,
    require_write_permission
)
from ..models.common import APIResponse, PaginationParams
from ..models.exports import (
    ExportRequest,
    ExportResponse,
    ExportProgressResponse,
    ExportResult,
    ExportHistoryResponse,
    ExportCapacityResponse,
    ExportCleanupRequest,
    ExportCleanupResponse,
    BulkExportRequest,
    BulkExportResponse,
    ExportStatus,
    ExportType,
    ExportFormat
)
from ..exceptions import DataNotFoundException, ServiceException, ValidationException
from ...services.time_bin_analyzer import TimeBinAnalyzer, TimeBin
from ...services.export_reporting.data_export_engine import DataExportEngine
from ...services.export_reporting.pdf_report_generator import PDFReportGenerator
from ...services.export_reporting.trading_report_formatter import TradingReportFormatter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for export tracking (in production, use Redis or database)
_export_jobs = {}
_bulk_export_jobs = {}


class ExportManager:
    """Manages export operations and job tracking."""
    
    def __init__(self):
        self.data_export_engine = None
        self.pdf_generator = None
        self.chart_formatter = None
    
    def initialize_services(self, db_session: Session):
        """Initialize export services with database session."""
        if not self.data_export_engine:
            self.data_export_engine = DataExportEngine(db_session)
        if not self.pdf_generator:
            self.pdf_generator = PDFReportGenerator(db_session)
        if not self.chart_formatter:
            self.chart_formatter = TradingReportFormatter(db_session)
    
    async def create_export_job(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        export_request: ExportRequest,
        db_session: Session
    ) -> str:
        """Create and queue an export job."""
        export_id = f"exp_{uuid.uuid4().hex[:12]}"
        
        # Initialize services
        self.initialize_services(db_session)
        
        # Create job record
        job_info = {
            "export_id": export_id,
            "account_name": account_name,
            "hour": hour,
            "minute_bin": minute_bin,
            "export_request": export_request,
            "status": ExportStatus.PENDING,
            "progress": 0.0,
            "current_step": "Queued for processing",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "file_path": None,
            "file_size": 0,
            "error_message": None
        }
        
        _export_jobs[export_id] = job_info
        
        return export_id
    
    async def process_export_job(
        self,
        export_id: str,
        db_session: Session
    ):
        """Process an export job in the background."""
        if export_id not in _export_jobs:
            logger.error(f"Export job {export_id} not found")
            return
        
        job = _export_jobs[export_id]
        
        try:
            # Update status
            job["status"] = ExportStatus.IN_PROGRESS
            job["current_step"] = "Starting export"
            job["updated_at"] = datetime.utcnow()
            
            # Initialize services
            self.initialize_services(db_session)
            
            account_name = job["account_name"]
            hour = job["hour"] 
            minute_bin = job["minute_bin"]
            export_request = job["export_request"]
            
            # Create TimeBin object
            time_bin = TimeBin(
                account_name=account_name,
                hour=hour,
                minute_bin=minute_bin
            )
            
            # Update progress
            job["progress"] = 20.0
            job["current_step"] = "Retrieving trade data"
            job["updated_at"] = datetime.utcnow()
            
            # Get trade data
            time_bin_analyzer = TimeBinAnalyzer(db_session)
            trades = time_bin_analyzer.get_time_bin_trades(
                time_bin,
                start_date=export_request.start_date,
                end_date=export_request.end_date
            )
            
            if not trades:
                raise DataNotFoundException(f"No trades found for time bin {hour}:{minute_bin:02d}")
            
            # Update progress
            job["progress"] = 40.0
            job["current_step"] = f"Processing {len(trades)} trades"
            job["updated_at"] = datetime.utcnow()
            
            # Generate export based on type and format
            if export_request.export_type == ExportType.TIME_BIN_TRADES:
                file_path = await self._export_time_bin_trades(
                    export_id, trades, export_request, job
                )
            elif export_request.export_type == ExportType.PERFORMANCE_REPORT:
                file_path = await self._export_performance_report(
                    export_id, trades, time_bin, export_request, job
                )
            elif export_request.export_type == ExportType.COMPREHENSIVE_PACKAGE:
                file_path = await self._export_comprehensive_package(
                    export_id, trades, time_bin, export_request, job
                )
            else:
                raise ValidationException(f"Export type {export_request.export_type} not supported")
            
            # Update completion
            job["status"] = ExportStatus.COMPLETED
            job["progress"] = 100.0
            job["current_step"] = "Export completed"
            job["file_path"] = file_path
            job["file_size"] = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            job["updated_at"] = datetime.utcnow()
            
            logger.info(f"Export {export_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Export {export_id} failed: {str(e)}")
            job["status"] = ExportStatus.FAILED
            job["error_message"] = str(e)
            job["current_step"] = f"Failed: {str(e)}"
            job["updated_at"] = datetime.utcnow()
    
    async def _export_time_bin_trades(
        self,
        export_id: str,
        trades,
        export_request: ExportRequest,
        job: dict
    ) -> str:
        """Export time bin trades data."""
        job["progress"] = 60.0
        job["current_step"] = "Generating trade export"
        job["updated_at"] = datetime.utcnow()
        
        # Create export directory if it doesn't exist
        export_dir = "exports"
        os.makedirs(export_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = export_request.custom_filename or f"trades_{export_id}_{timestamp}"
        
        if export_request.export_format == ExportFormat.CSV:
            file_path = os.path.join(export_dir, f"{filename}.csv")
            self.data_export_engine.export_time_bin_trades(
                trades=trades,
                output_path=file_path,
                format_type="csv"
            )
        elif export_request.export_format == ExportFormat.EXCEL:
            file_path = os.path.join(export_dir, f"{filename}.xlsx")
            self.data_export_engine.export_time_bin_trades(
                trades=trades,
                output_path=file_path,
                format_type="excel"
            )
        elif export_request.export_format == ExportFormat.JSON:
            file_path = os.path.join(export_dir, f"{filename}.json")
            self.data_export_engine.export_time_bin_trades(
                trades=trades,
                output_path=file_path,
                format_type="json"
            )
        else:
            raise ValidationException(f"Export format {export_request.export_format} not supported for trade data")
        
        job["progress"] = 90.0
        job["current_step"] = "Finalizing export"
        job["updated_at"] = datetime.utcnow()
        
        return file_path
    
    async def _export_performance_report(
        self,
        export_id: str,
        trades,
        time_bin: TimeBin,
        export_request: ExportRequest,
        job: dict
    ) -> str:
        """Export performance report."""
        job["progress"] = 60.0
        job["current_step"] = "Generating performance report"
        job["updated_at"] = datetime.utcnow()
        
        export_dir = "exports"
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = export_request.custom_filename or f"performance_{export_id}_{timestamp}"
        
        if export_request.export_format == ExportFormat.PDF:
            file_path = os.path.join(export_dir, f"{filename}.pdf")
            
            # Generate PDF report
            metadata = self.pdf_generator.generate_time_bin_report(
                account_name=time_bin.account_name,
                hour=time_bin.hour,
                minute_bin=time_bin.minute_bin,
                output_path=file_path,
                start_date=export_request.start_date,
                end_date=export_request.end_date
            )
            
            job["progress"] = 90.0
            job["current_step"] = "PDF report generated"
            job["updated_at"] = datetime.utcnow()
            
        else:
            raise ValidationException(f"Export format {export_request.export_format} not supported for performance reports")
        
        return file_path
    
    async def _export_comprehensive_package(
        self,
        export_id: str,
        trades,
        time_bin: TimeBin,
        export_request: ExportRequest,
        job: dict
    ) -> str:
        """Export comprehensive package with multiple formats."""
        job["progress"] = 60.0
        job["current_step"] = "Creating comprehensive package"
        job["updated_at"] = datetime.utcnow()
        
        export_dir = "exports"
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = export_request.custom_filename or f"package_{export_id}_{timestamp}"
        
        # Create package using DataExportEngine
        package_path = self.data_export_engine.create_export_package(
            time_bin=time_bin,
            output_dir=export_dir,
            package_name=package_name,
            start_date=export_request.start_date,
            end_date=export_request.end_date,
            include_charts=export_request.include_charts
        )
        
        job["progress"] = 90.0
        job["current_step"] = "Package created"
        job["updated_at"] = datetime.utcnow()
        
        return package_path


# Initialize export manager
export_manager = ExportManager()


@router.post(
    "/time-bins/{account_name}/{hour}/{minute_bin}/export",
    response_model=APIResponse[ExportResponse],
    summary="Create data export",
    description="Create an export job for time-bin trading data."
)
async def create_export(
    background_tasks: BackgroundTasks,
    account_name: str = Path(..., description="Account name"),
    hour: int = Path(..., ge=0, le=23, description="Hour of the time bin"),
    minute_bin: int = Path(..., ge=0, le=59, description="Minute of the time bin"),
    export_request: ExportRequest = ...,
    db: Session = Depends(get_database_session),
    _: dict = Depends(require_read_permission)
):
    """Create a new export job."""
    try:
        # Create export job
        export_id = await export_manager.create_export_job(
            account_name=account_name,
            hour=hour,
            minute_bin=minute_bin,
            export_request=export_request,
            db_session=db
        )
        
        # Start background processing
        background_tasks.add_task(
            export_manager.process_export_job,
            export_id,
            db
        )
        
        # Estimate completion time based on export type
        estimated_minutes = 2 if export_request.export_type == ExportType.TIME_BIN_TRADES else 5
        estimated_completion = datetime.utcnow() + timedelta(minutes=estimated_minutes)
        
        response = ExportResponse(
            export_id=export_id,
            status=ExportStatus.PENDING,
            status_url=f"/api/exports/{export_id}/status",
            estimated_completion_time=estimated_completion,
            message="Export queued for processing"
        )
        
        return APIResponse(
            success=True,
            data=response,
            message="Export job created successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to create export: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create export: {str(e)}"
        )


@router.get(
    "/{export_id}/status",
    response_model=APIResponse[ExportProgressResponse],
    summary="Get export status",
    description="Get the current status and progress of an export job."
)
async def get_export_status(
    export_id: str = Path(..., description="Export job ID"),
    _: dict = Depends(require_read_permission)
):
    """Get export job status and progress."""
    if export_id not in _export_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found"
        )
    
    job = _export_jobs[export_id]
    
    progress_response = ExportProgressResponse(
        export_id=export_id,
        status=job["status"],
        progress_percentage=job["progress"],
        current_step=job["current_step"],
        estimated_completion_time=None,  # Calculate based on current progress
        message=job.get("error_message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"]
    )
    
    return APIResponse(
        success=True,
        data=progress_response,
        message="Export status retrieved successfully"
    )


@router.get(
    "/{export_id}/download",
    summary="Download export file",
    description="Download the generated export file."
)
async def download_export(
    export_id: str = Path(..., description="Export job ID"),
    _: dict = Depends(require_read_permission)
):
    """Download completed export file."""
    if export_id not in _export_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found"
        )
    
    job = _export_jobs[export_id]
    
    if job["status"] != ExportStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export is not ready for download. Status: {job['status']}"
        )
    
    if not job["file_path"] or not os.path.exists(job["file_path"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found"
        )
    
    filename = os.path.basename(job["file_path"])
    
    return FileResponse(
        path=job["file_path"],
        filename=filename,
        media_type='application/octet-stream'
    )


@router.delete(
    "/{export_id}",
    response_model=APIResponse[dict],
    summary="Cancel export",
    description="Cancel a pending or in-progress export job."
)
async def cancel_export(
    export_id: str = Path(..., description="Export job ID"),
    _: dict = Depends(require_write_permission)
):
    """Cancel an export job."""
    if export_id not in _export_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found"
        )
    
    job = _export_jobs[export_id]
    
    if job["status"] in [ExportStatus.COMPLETED, ExportStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel export with status: {job['status']}"
        )
    
    # Cancel the job
    job["status"] = ExportStatus.FAILED
    job["current_step"] = "Cancelled by user"
    job["error_message"] = "Export cancelled by user"
    job["updated_at"] = datetime.utcnow()
    
    return APIResponse(
        success=True,
        data={"export_id": export_id, "status": "cancelled"},
        message="Export cancelled successfully"
    )


@router.get(
    "/history",
    response_model=APIResponse[ExportHistoryResponse],
    summary="Get export history",
    description="Get a paginated list of historical exports."
)
async def get_export_history(
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    status_filter: Optional[List[ExportStatus]] = Query(None, description="Filter by status"),
    pagination: PaginationParams = Depends(),
    _: dict = Depends(require_read_permission)
):
    """Get export history with optional filtering."""
    # Filter exports based on criteria
    filtered_jobs = []
    
    for job in _export_jobs.values():
        if account_name and job["account_name"] != account_name:
            continue
        if status_filter and job["status"] not in status_filter:
            continue
        filtered_jobs.append(job)
    
    # Sort by creation date (newest first)
    filtered_jobs.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Apply pagination
    start_idx = (pagination.page - 1) * pagination.page_size
    end_idx = start_idx + pagination.page_size
    page_jobs = filtered_jobs[start_idx:end_idx]
    
    # Convert to response format
    history_items = []
    for job in page_jobs:
        item = ExportHistoryItem(
            export_id=job["export_id"],
            account_name=job["account_name"],
            time_bin_hour=job["hour"],
            time_bin_minute=job["minute_bin"],
            export_type=job["export_request"].export_type,
            export_format=job["export_request"].export_format,
            status=job["status"],
            created_at=job["created_at"],
            completed_at=job["updated_at"] if job["status"] == ExportStatus.COMPLETED else None,
            file_size_bytes=job["file_size"],
            download_count=0,  # TODO: Track download counts
            expires_at=None  # TODO: Implement expiration
        )
        history_items.append(item)
    
    total_pages = (len(filtered_jobs) + pagination.page_size - 1) // pagination.page_size
    
    history_response = ExportHistoryResponse(
        exports=history_items,
        total_count=len(filtered_jobs),
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages
    )
    
    return APIResponse(
        success=True,
        data=history_response,
        message="Export history retrieved successfully"
    )


@router.get(
    "/capacity",
    response_model=APIResponse[ExportCapacityResponse],
    summary="Get export capacity",
    description="Get information about export system capacity and performance."
)
async def get_export_capacity(
    _: dict = Depends(require_read_permission)
):
    """Get export system capacity information."""
    active_count = sum(1 for job in _export_jobs.values() if job["status"] == ExportStatus.IN_PROGRESS)
    pending_count = sum(1 for job in _export_jobs.values() if job["status"] == ExportStatus.PENDING)
    
    max_concurrent = 5  # Configuration setting
    available = max(0, max_concurrent - active_count)
    
    capacity_response = ExportCapacityResponse(
        active_exports=active_count,
        max_concurrent_exports=max_concurrent,
        queue_length=pending_count,
        available_capacity=available,
        estimated_queue_time=pending_count * 120 if pending_count > 0 else None,  # 2 minutes per job estimate
        system_health="healthy" if active_count < max_concurrent else "at_capacity"
    )
    
    return APIResponse(
        success=True,
        data=capacity_response,
        message="Export capacity information retrieved successfully"
    )


@router.post(
    "/cleanup",
    response_model=APIResponse[ExportCleanupResponse],
    summary="Cleanup old exports",
    description="Clean up old export files and job records."
)
async def cleanup_exports(
    cleanup_request: ExportCleanupRequest,
    _: dict = Depends(require_write_permission)
):
    """Clean up old export files and records."""
    cutoff_date = datetime.utcnow() - timedelta(days=cleanup_request.older_than_days)
    
    files_to_delete = []
    space_to_free = 0
    
    for export_id, job in _export_jobs.items():
        # Check if job meets cleanup criteria
        if job["created_at"] > cutoff_date:
            continue
        
        if cleanup_request.status_filter and job["status"] not in cleanup_request.status_filter:
            continue
        
        # Add to cleanup list
        if job["file_path"] and os.path.exists(job["file_path"]):
            files_to_delete.append((export_id, job["file_path"]))
            space_to_free += os.path.getsize(job["file_path"])
    
    errors = []
    files_deleted = 0
    
    if not cleanup_request.dry_run:
        start_time = datetime.utcnow()
        
        # Delete files and job records
        for export_id, file_path in files_to_delete:
            try:
                os.remove(file_path)
                del _export_jobs[export_id]
                files_deleted += 1
            except Exception as e:
                errors.append(f"Failed to delete {file_path}: {str(e)}")
        
        cleanup_duration = (datetime.utcnow() - start_time).total_seconds()
    else:
        files_deleted = len(files_to_delete)
        cleanup_duration = 0.0
    
    cleanup_response = ExportCleanupResponse(
        files_deleted=files_deleted,
        space_freed_bytes=space_to_free if not cleanup_request.dry_run else 0,
        cleanup_duration_seconds=cleanup_duration,
        errors=errors,
        dry_run=cleanup_request.dry_run
    )
    
    return APIResponse(
        success=True,
        data=cleanup_response,
        message=f"Cleanup {'simulation' if cleanup_request.dry_run else 'operation'} completed"
    )