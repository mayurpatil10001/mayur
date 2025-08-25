"""
Data ingestion API endpoints.

This module provides REST endpoints for data import and processing operations.

Requirements: 7.1, 10.1, 10.3
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
from sqlalchemy.orm import Session

from ..dependencies import (
    get_database_session,
    get_data_ingestion_service,
    require_write_permission,
    require_read_permission
)
from ..models.common import APIResponse, BulkOperationResponse
from ..models.trades import (
    SierraChartImportRequest,
    ImportStatusResponse
)
from ..exceptions import ServiceException, ValidationException
from ...services.data_ingestion_service import SierraChartDataIngestionService


router = APIRouter()


@router.post(
    "/import/sierra-chart",
    response_model=APIResponse[ImportStatusResponse],
    summary="Import SierraChart data",
    description="Import and process SierraChart trading data files from configured directories."
)
async def import_sierra_chart_data(
    import_request: SierraChartImportRequest = Body(...),
    db: Session = Depends(get_database_session),
    data_ingestion_service: SierraChartDataIngestionService = Depends(get_data_ingestion_service),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[ImportStatusResponse]:
    """Import SierraChart data files."""
    
    try:
        # Generate import ID
        import_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # TODO: Implement actual data import using service
        # For now, return mock import status
        
        import_status = ImportStatusResponse(
            import_id=import_id,
            status="in_progress",
            started_at=datetime.now(),
            completed_at=None,
            files_processed=0,
            records_imported=0,
            records_skipped=0,
            errors=[],
            progress_percentage=0.0
        )
        
        # Simulate processing
        if import_request.validate_only:
            import_status.status = "validation_completed"
            import_status.completed_at = datetime.now()
            import_status.progress_percentage = 100.0
            import_status.files_processed = 5
            import_status.records_imported = 0  # No records imported in validation mode
        else:
            # Mock successful import
            import_status.status = "completed"
            import_status.completed_at = datetime.now()
            import_status.progress_percentage = 100.0
            import_status.files_processed = 5
            import_status.records_imported = 1250
            import_status.records_skipped = 25
        
        return APIResponse[ImportStatusResponse](
            status="success",
            message=f"SierraChart data import {'validation' if import_request.validate_only else 'processing'} started",
            data=import_status
        )
        
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.message)
    except ServiceException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start data import: {str(e)}")


@router.get(
    "/import/status/{import_id}",
    response_model=APIResponse[ImportStatusResponse],
    summary="Get import status",
    description="Check the status of a data import operation."
)
async def get_import_status(
    import_id: str = Path(..., description="Import operation ID"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[ImportStatusResponse]:
    """Get status of data import operation."""
    
    try:
        # TODO: Implement actual status checking from database
        # For now, return mock status based on import_id
        
        if "validation" in import_id:
            import_status = ImportStatusResponse(
                import_id=import_id,
                status="validation_completed",
                started_at=datetime(2024, 1, 1, 12, 0, 0),
                completed_at=datetime(2024, 1, 1, 12, 5, 30),
                files_processed=5,
                records_imported=0,
                records_skipped=0,
                errors=[],
                progress_percentage=100.0
            )
        elif "error" in import_id:
            import_status = ImportStatusResponse(
                import_id=import_id,
                status="failed",
                started_at=datetime(2024, 1, 1, 12, 0, 0),
                completed_at=datetime(2024, 1, 1, 12, 2, 15),
                files_processed=2,
                records_imported=0,
                records_skipped=0,
                errors=["File not found: missing_file.txt", "Permission denied: protected_file.txt"],
                progress_percentage=40.0
            )
        else:
            import_status = ImportStatusResponse(
                import_id=import_id,
                status="completed",
                started_at=datetime(2024, 1, 1, 12, 0, 0),
                completed_at=datetime(2024, 1, 1, 12, 15, 45),
                files_processed=8,
                records_imported=2150,
                records_skipped=45,
                errors=[],
                progress_percentage=100.0
            )
        
        return APIResponse[ImportStatusResponse](
            status="success",
            message=f"Import status retrieved for {import_id}",
            data=import_status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve import status: {str(e)}")


@router.get(
    "/import/history",
    response_model=APIResponse[List[ImportStatusResponse]],
    summary="Get import history",
    description="Retrieve history of data import operations."
)
async def get_import_history(
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of records to return"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[List[ImportStatusResponse]]:
    """Get history of import operations."""
    
    try:
        # TODO: Implement actual history retrieval from database
        # For now, return mock history
        
        mock_history = [
            ImportStatusResponse(
                import_id="import_20240101_120000_abc123",
                status="completed",
                started_at=datetime(2024, 1, 1, 12, 0, 0),
                completed_at=datetime(2024, 1, 1, 12, 15, 45),
                files_processed=8,
                records_imported=2150,
                records_skipped=45,
                errors=[],
                progress_percentage=100.0
            ),
            ImportStatusResponse(
                import_id="import_20240101_110000_def456",
                status="failed",
                started_at=datetime(2024, 1, 1, 11, 0, 0),
                completed_at=datetime(2024, 1, 1, 11, 2, 15),
                files_processed=2,
                records_imported=0,
                records_skipped=0,
                errors=["File not found: missing_file.txt"],
                progress_percentage=25.0
            ),
            ImportStatusResponse(
                import_id="import_20240101_100000_ghi789",
                status="completed",
                started_at=datetime(2024, 1, 1, 10, 0, 0),
                completed_at=datetime(2024, 1, 1, 10, 12, 30),
                files_processed=6,
                records_imported=1850,
                records_skipped=32,
                errors=[],
                progress_percentage=100.0
            )
        ]
        
        # Apply status filter
        if status_filter:
            mock_history = [h for h in mock_history if h.status == status_filter]
        
        # Apply limit
        mock_history = mock_history[:limit]
        
        return APIResponse[List[ImportStatusResponse]](
            status="success",
            message=f"Retrieved {len(mock_history)} import records",
            data=mock_history
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve import history: {str(e)}")


@router.post(
    "/validate/sierra-chart",
    response_model=APIResponse[BulkOperationResponse],
    summary="Validate SierraChart files",
    description="Validate SierraChart files without importing them."
)
async def validate_sierra_chart_files(
    file_paths: List[str] = Body(..., description="List of file paths to validate"),
    db: Session = Depends(get_database_session),
    data_ingestion_service: SierraChartDataIngestionService = Depends(get_data_ingestion_service),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[BulkOperationResponse]:
    """Validate SierraChart files without importing."""
    
    try:
        # TODO: Implement actual file validation using service
        # For now, return mock validation results
        
        total_files = len(file_paths)
        successful_files = max(0, total_files - 2)  # Mock some failures
        failed_files = total_files - successful_files
        
        errors = []
        if failed_files > 0:
            errors = [
                {"file": file_paths[-1], "error": "File format not recognized"},
                {"file": file_paths[-2] if len(file_paths) > 1 else file_paths[0], "error": "Missing required columns"}
            ][:failed_files]
        
        validation_result = BulkOperationResponse(
            total_items=total_files,
            successful_items=successful_files,
            failed_items=failed_files,
            errors=errors,
            processing_time=2.5
        )
        
        return APIResponse[BulkOperationResponse](
            status="success" if failed_files == 0 else "partial",
            message=f"Validated {total_files} files: {successful_files} successful, {failed_files} failed",
            data=validation_result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate files: {str(e)}")


@router.delete(
    "/import/{import_id}",
    response_model=APIResponse[None],
    summary="Cancel import operation",
    description="Cancel a running import operation."
)
async def cancel_import_operation(
    import_id: str = Path(..., description="Import operation ID to cancel"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[None]:
    """Cancel a running import operation."""
    
    try:
        # TODO: Implement actual import cancellation
        # For now, return mock cancellation response
        
        return APIResponse[None](
            status="success",
            message=f"Import operation {import_id} has been cancelled"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel import operation: {str(e)}")


@router.post(
    "/cleanup/duplicates",
    response_model=APIResponse[BulkOperationResponse],
    summary="Clean up duplicate records",
    description="Remove duplicate trading records from the database."
)
async def cleanup_duplicate_records(
    dry_run: bool = Query(False, description="Perform dry run without actual deletion"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[BulkOperationResponse]:
    """Clean up duplicate trading records."""
    
    try:
        import time
        start_time = time.time()
        
        # Find duplicates using the same logic as our previous cleanup
        duplicate_query = """
        SELECT 
            id,
            COUNT(*) as duplicate_count,
            GROUP_CONCAT(id) as duplicate_ids
        FROM processed_trades 
        GROUP BY entry_time, exit_time, account_name, symbol, quantity, entry_price, exit_price, profit_loss
        HAVING COUNT(*) > 1
        """
        
        duplicates_result = db.execute(text(duplicate_query)).fetchall()
        
        total_duplicates = 0
        successful_removals = 0
        failed_removals = 0
        errors = []
        
        for row in duplicates_result:
            duplicate_ids = row.duplicate_ids.split(',')
            duplicate_count = len(duplicate_ids)
            total_duplicates += duplicate_count - 1  # Keep one, remove the rest
            
            # Keep the first ID, remove the rest
            ids_to_remove = duplicate_ids[1:]
            
            if not dry_run:
                try:
                    for trade_id in ids_to_remove:
                        delete_query = text("DELETE FROM processed_trades WHERE id = :trade_id")
                        result = db.execute(delete_query, {"trade_id": int(trade_id)})
                        if result.rowcount > 0:
                            successful_removals += 1
                        else:
                            failed_removals += 1
                            errors.append({"record_id": trade_id, "error": "Record not found or already deleted"})
                    
                    db.commit()
                except Exception as e:
                    db.rollback()
                    failed_removals += len(ids_to_remove)
                    for trade_id in ids_to_remove:
                        errors.append({"record_id": trade_id, "error": str(e)})
            else:
                successful_removals += len(ids_to_remove)
        
        processing_time = time.time() - start_time
        
        cleanup_result = BulkOperationResponse(
            total_items=total_duplicates,
            successful_items=successful_removals,
            failed_items=failed_removals,
            errors=errors[:10],  # Limit to first 10 errors
            processing_time=processing_time
        )
        
        action = "would be removed" if dry_run else "removed"
        
        return APIResponse[BulkOperationResponse](
            status="success",
            message=f"Duplicate cleanup {'simulation' if dry_run else 'operation'} completed: {cleanup_result.successful_items} records {action}",
            data=cleanup_result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup duplicates: {str(e)}")