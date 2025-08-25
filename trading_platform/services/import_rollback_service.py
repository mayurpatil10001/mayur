#!/usr/bin/env python3
"""
Import rollback and retry service for data import operations.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from trading_platform.repositories.sierra_chart_repository import SierraChartRepository

logger = logging.getLogger(__name__)


@dataclass
class ImportSnapshot:
    """Snapshot of database state before import."""
    snapshot_id: str
    timestamp: datetime
    backup_path: str
    trade_count_before: int
    import_log_count_before: int
    description: str


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    success: bool
    snapshot_id: str
    trades_removed: int
    import_logs_removed: int
    message: str
    error: Optional[str] = None


class ImportRollbackService:
    """Service for managing import rollbacks and retries."""

    def __init__(self, backup_directory: str = "backups"):
        """Initialize the rollback service.

        Args:
            backup_directory: Directory to store database backups
        """
        self.repository = SierraChartRepository()
        self.backup_dir = Path(backup_directory)
        self.backup_dir.mkdir(exist_ok=True)
        self.snapshots_file = self.backup_dir / "snapshots.json"

    def create_snapshot(self, description: str = "") -> ImportSnapshot:
        """Create a snapshot of the current database state.

        Args:
            description: Description of the snapshot

        Returns:
            ImportSnapshot object
        """
        snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now()
        
        # Count current records
        trade_count = self._count_trades()
        import_log_count = self._count_import_logs()
        
        # Create database backup
        backup_path = self.backup_dir / f"{snapshot_id}.db"
        try:
            # Copy the database file
            db_path = Path("trading_platform.db")
            if db_path.exists():
                shutil.copy2(db_path, backup_path)
                logger.info(f"Database backup created: {backup_path}")
            else:
                logger.warning("Database file not found, creating empty backup")
                backup_path.touch()
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            raise
        
        # Create snapshot record
        snapshot = ImportSnapshot(
            snapshot_id=snapshot_id,
            timestamp=timestamp,
            backup_path=str(backup_path),
            trade_count_before=trade_count,
            import_log_count_before=import_log_count,
            description=description or f"Snapshot before import at {timestamp}"
        )
        
        # Save snapshot metadata
        self._save_snapshot(snapshot)
        
        logger.info(f"Snapshot created: {snapshot_id} ({trade_count} trades, {import_log_count} import logs)")
        return snapshot

    def rollback_to_snapshot(self, snapshot_id: str) -> RollbackResult:
        """Rollback database to a previous snapshot.

        Args:
            snapshot_id: ID of the snapshot to rollback to

        Returns:
            RollbackResult object
        """
        logger.info(f"Starting rollback to snapshot: {snapshot_id}")
        
        # Load snapshot metadata
        snapshot = self._load_snapshot(snapshot_id)
        if not snapshot:
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                trades_removed=0,
                import_logs_removed=0,
                message="Snapshot not found",
                error=f"Snapshot {snapshot_id} not found"
            )
        
        # Count current records
        current_trade_count = self._count_trades()
        current_import_log_count = self._count_import_logs()
        
        try:
            # Restore database from backup
            backup_path = Path(snapshot.backup_path)
            if not backup_path.exists():
                return RollbackResult(
                    success=False,
                    snapshot_id=snapshot_id,
                    trades_removed=0,
                    import_logs_removed=0,
                    message="Backup file not found",
                    error=f"Backup file {backup_path} not found"
                )
            
            # Close current database connection
            self.repository.close()
            
            # Replace database file
            db_path = Path("trading_platform.db")
            if db_path.exists():
                # Create a backup of current state before rollback
                current_backup = self.backup_dir / f"pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(db_path, current_backup)
                logger.info(f"Current database backed up to: {current_backup}")
            
            # Restore from snapshot
            shutil.copy2(backup_path, db_path)
            
            # Reconnect to database
            self.repository = SierraChartRepository()
            
            # Calculate removed records
            trades_removed = current_trade_count - snapshot.trade_count_before
            import_logs_removed = current_import_log_count - snapshot.import_log_count_before
            
            logger.info(f"Rollback successful: {trades_removed} trades and {import_logs_removed} import logs removed")
            
            return RollbackResult(
                success=True,
                snapshot_id=snapshot_id,
                trades_removed=trades_removed,
                import_logs_removed=import_logs_removed,
                message=f"Successfully rolled back to snapshot {snapshot_id}"
            )
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                trades_removed=0,
                import_logs_removed=0,
                message="Rollback failed",
                error=str(e)
            )

    def list_snapshots(self) -> List[ImportSnapshot]:
        """List all available snapshots.

        Returns:
            List of ImportSnapshot objects
        """
        snapshots = []
        if self.snapshots_file.exists():
            try:
                with open(self.snapshots_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for snapshot_data in data.get("snapshots", []):
                        snapshot = ImportSnapshot(
                            snapshot_id=snapshot_data["snapshot_id"],
                            timestamp=datetime.fromisoformat(snapshot_data["timestamp"]),
                            backup_path=snapshot_data["backup_path"],
                            trade_count_before=snapshot_data["trade_count_before"],
                            import_log_count_before=snapshot_data["import_log_count_before"],
                            description=snapshot_data["description"]
                        )
                        snapshots.append(snapshot)
            except Exception as e:
                logger.error(f"Error loading snapshots: {e}")
        
        return sorted(snapshots, key=lambda x: x.timestamp, reverse=True)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot and its backup file.

        Args:
            snapshot_id: ID of the snapshot to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load current snapshots
            snapshots = self.list_snapshots()
            
            # Find and remove the snapshot
            snapshot_to_delete = None
            remaining_snapshots = []
            
            for snapshot in snapshots:
                if snapshot.snapshot_id == snapshot_id:
                    snapshot_to_delete = snapshot
                else:
                    remaining_snapshots.append(snapshot)
            
            if not snapshot_to_delete:
                logger.warning(f"Snapshot {snapshot_id} not found")
                return False
            
            # Delete backup file
            backup_path = Path(snapshot_to_delete.backup_path)
            if backup_path.exists():
                backup_path.unlink()
                logger.info(f"Deleted backup file: {backup_path}")
            
            # Update snapshots file
            self._save_snapshots(remaining_snapshots)
            
            logger.info(f"Snapshot {snapshot_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting snapshot {snapshot_id}: {e}")
            return False

    def cleanup_old_snapshots(self, keep_count: int = 10) -> int:
        """Clean up old snapshots, keeping only the most recent ones.

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots deleted
        """
        snapshots = self.list_snapshots()
        if len(snapshots) <= keep_count:
            return 0
        
        # Delete oldest snapshots
        snapshots_to_delete = snapshots[keep_count:]
        deleted_count = 0
        
        for snapshot in snapshots_to_delete:
            if self.delete_snapshot(snapshot.snapshot_id):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old snapshots")
        return deleted_count

    def retry_failed_import(self, file_path: str, max_retries: int = 3) -> Dict:
        """Retry a failed import operation.

        Args:
            file_path: Path to the file to retry importing
            max_retries: Maximum number of retry attempts

        Returns:
            Dictionary with retry results
        """
        from trading_platform.services.processed_trade_import_service import ProcessedTradeImportService
        
        logger.info(f"Retrying import for file: {file_path}")
        
        import_service = ProcessedTradeImportService()
        retry_results = {
            "file_path": file_path,
            "attempts": [],
            "final_success": False,
            "total_trades_imported": 0
        }
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"Import attempt {attempt}/{max_retries} for {file_path}")
            
            try:
                # Create snapshot before retry
                snapshot = self.create_snapshot(f"Before retry attempt {attempt} for {Path(file_path).name}")
                
                # Attempt import
                trades = import_service.import_files([Path(file_path)])
                
                attempt_result = {
                    "attempt_number": attempt,
                    "success": len(trades) > 0,
                    "trades_imported": len(trades),
                    "snapshot_id": snapshot.snapshot_id,
                    "error": None
                }
                
                if len(trades) > 0:
                    logger.info(f"Import successful on attempt {attempt}: {len(trades)} trades imported")
                    retry_results["final_success"] = True
                    retry_results["total_trades_imported"] = len(trades)
                    retry_results["attempts"].append(attempt_result)
                    break
                else:
                    logger.warning(f"Import attempt {attempt} failed: no trades imported")
                    attempt_result["error"] = "No trades imported"
                    retry_results["attempts"].append(attempt_result)
                    
                    # Rollback to snapshot
                    rollback_result = self.rollback_to_snapshot(snapshot.snapshot_id)
                    if not rollback_result.success:
                        logger.error(f"Rollback failed: {rollback_result.error}")
                
            except Exception as e:
                logger.error(f"Import attempt {attempt} failed with exception: {e}")
                attempt_result = {
                    "attempt_number": attempt,
                    "success": False,
                    "trades_imported": 0,
                    "snapshot_id": snapshot.snapshot_id if 'snapshot' in locals() else None,
                    "error": str(e)
                }
                retry_results["attempts"].append(attempt_result)
                
                # Rollback if snapshot was created
                if 'snapshot' in locals():
                    rollback_result = self.rollback_to_snapshot(snapshot.snapshot_id)
                    if not rollback_result.success:
                        logger.error(f"Rollback failed: {rollback_result.error}")
        
        if retry_results["final_success"]:
            logger.info(f"Import retry successful after {len(retry_results['attempts'])} attempts")
        else:
            logger.error(f"Import retry failed after {max_retries} attempts")
        
        return retry_results

    def _count_trades(self) -> int:
        """Count total trades in database."""
        try:
            cursor = self.repository.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM sierra_chart_trades")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error counting trades: {e}")
            return 0

    def _count_import_logs(self) -> int:
        """Count total import logs in database."""
        try:
            cursor = self.repository.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM data_import_log")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error counting import logs: {e}")
            return 0

    def _save_snapshot(self, snapshot: ImportSnapshot) -> None:
        """Save snapshot metadata to file."""
        snapshots = self.list_snapshots()
        snapshots.append(snapshot)
        self._save_snapshots(snapshots)

    def _save_snapshots(self, snapshots: List[ImportSnapshot]) -> None:
        """Save all snapshots to file."""
        try:
            data = {
                "snapshots": [asdict(snapshot) for snapshot in snapshots]
            }
            # Convert datetime objects to strings
            for snapshot_data in data["snapshots"]:
                snapshot_data["timestamp"] = snapshot_data["timestamp"].isoformat()
            
            with open(self.snapshots_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving snapshots: {e}")

    def _load_snapshot(self, snapshot_id: str) -> Optional[ImportSnapshot]:
        """Load a specific snapshot by ID."""
        snapshots = self.list_snapshots()
        for snapshot in snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        return None