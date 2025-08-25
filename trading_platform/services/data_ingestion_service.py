"""
SierraChart data ingestion service for scanning and processing trading data files.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

from .sierra_chart_parser import SierraChartFileParser, SierraChartParseError
from ..models.sierra_chart import SierraChartTradeRecord
from ..utils.validators import ValidationError


class DataIngestionError(Exception):
    """Exception raised during data ingestion process."""
    pass


class ProgressTracker:
    """Progress tracking for file processing operations."""
    
    def __init__(self, total_files: int = 0):
        """Initialize progress tracker."""
        self.total_files = total_files
        self.processed_files = 0
        self.successful_files = 0
        self.failed_files = 0
        self.total_records = 0
        self.duplicate_records = 0
        self.start_time = datetime.now()
        self.callbacks: List[Callable] = []
    
    def add_callback(self, callback: Callable):
        """Add progress callback function."""
        self.callbacks.append(callback)
    
    def update_file_processed(self, success: bool, record_count: int = 0, duplicates: int = 0):
        """Update progress when a file is processed."""
        self.processed_files += 1
        if success:
            self.successful_files += 1
            self.total_records += record_count
            self.duplicate_records += duplicates
        else:
            self.failed_files += 1
        
        # Call progress callbacks
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception as e:
                logging.warning(f"Progress callback failed: {e}")
    
    def get_progress_percentage(self) -> float:
        """Get progress as percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_estimated_remaining_time(self) -> Optional[float]:
        """Get estimated remaining time in seconds."""
        if self.processed_files == 0:
            return None
        
        elapsed = self.get_elapsed_time()
        if elapsed == 0:
            return None
            
        rate = self.processed_files / elapsed
        remaining_files = self.total_files - self.processed_files
        
        if rate > 0:
            return remaining_files / rate
        return None
    
    def get_summary(self) -> Dict:
        """Get processing summary."""
        return {
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'successful_files': self.successful_files,
            'failed_files': self.failed_files,
            'total_records': self.total_records,
            'duplicate_records': self.duplicate_records,
            'progress_percentage': self.get_progress_percentage(),
            'elapsed_time': self.get_elapsed_time(),
            'estimated_remaining_time': self.get_estimated_remaining_time()
        }


class SierraChartDataIngestionService:
    """Service for ingesting SierraChart data from multiple directories."""
    
    # Default SierraChart directories
    DEFAULT_DIRECTORIES = [
        r"D:\SierraChart_Simulated_Feed\SavedTradeActivity",
        r"D:\SierraChart_Delayed_Simulated\SavedTradeActivity",
        r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\SavedTradeActivity",
        r"D:\SierraChart_Simulated_Feed\SierraChartInstance_5\SavedTradeActivity"
    ]
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {'.txt', '.csv', '.tsv'}
    
    # Expected symbols for validation
    EXPECTED_SYMBOLS = {'NQ', 'FDAX', 'CL', 'ES'}  # Base symbols
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the data ingestion service."""
        self.logger = logger or logging.getLogger(__name__)
        self.parser = SierraChartFileParser(self.logger)
        
        # Duplicate detection tracking
        self.seen_records: Set[str] = set()  # Track unique record identifiers
        self.duplicate_stats = {
            'service_order_duplicates': 0,
            'internal_order_duplicates': 0,
            'exact_duplicates': 0
        }
        
        # Processing statistics
        self.ingestion_stats = {
            'directories_scanned': 0,
            'files_found': 0,
            'files_processed': 0,
            'total_records': 0,
            'valid_records': 0,
            'duplicate_records': 0,
            'processing_errors': 0
        }
    
    def scan_directories(self, directories: Optional[List[str]] = None) -> List[Path]:
        """
        Scan directories for SierraChart files.
        
        Args:
            directories: List of directory paths to scan. Uses defaults if None.
            
        Returns:
            List of file paths found
            
        Raises:
            DataIngestionError: If scanning fails
        """
        if directories is None:
            directories = self.DEFAULT_DIRECTORIES
        
        all_files = []
        
        for directory in directories:
            try:
                dir_path = Path(directory)
                if not dir_path.exists():
                    self.logger.warning(f"Directory does not exist: {directory}")
                    continue
                
                if not dir_path.is_dir():
                    self.logger.warning(f"Path is not a directory: {directory}")
                    continue
                
                # Find all supported files
                files_in_dir = []
                for ext in self.SUPPORTED_EXTENSIONS:
                    pattern = f"*{ext}"
                    files_in_dir.extend(dir_path.glob(pattern))
                
                # Filter for files that might contain NQ or FDAX data
                relevant_files = []
                for file_path in files_in_dir:
                    if self._is_relevant_file(file_path):
                        relevant_files.append(file_path)
                
                all_files.extend(relevant_files)
                self.ingestion_stats['directories_scanned'] += 1
                
                self.logger.info(
                    f"Scanned {directory}: found {len(relevant_files)} relevant files "
                    f"out of {len(files_in_dir)} total files"
                )
                
            except Exception as e:
                self.logger.error(f"Error scanning directory {directory}: {e}")
                continue
        
        self.ingestion_stats['files_found'] = len(all_files)
        self.logger.info(f"Total files found across all directories: {len(all_files)}")
        
        return all_files
    
    def _is_relevant_file(self, file_path: Path) -> bool:
        """
        Check if file is relevant for NQ/FDAX trading data.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file appears to contain relevant trading data
        """
        filename = file_path.name.upper()
        
        # Check if filename contains expected symbols
        for symbol in self.EXPECTED_SYMBOLS:
            if symbol in filename:
                return True
        
        # Check if it's a general trading activity file
        if any(keyword in filename for keyword in ['TRADE', 'ACTIVITY', 'FILL', 'ORDER']):
            return True
        
        # If we can't determine from filename, assume it might be relevant
        # The parser will validate the actual content
        return True
    
    def ingest_files(self, file_paths: List[Path], 
                    max_workers: int = 4,
                    progress_callback: Optional[Callable] = None) -> List[SierraChartTradeRecord]:
        """
        Ingest multiple SierraChart files with parallel processing.
        
        Args:
            file_paths: List of file paths to process
            max_workers: Maximum number of worker threads
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of all ingested and deduplicated records
            
        Raises:
            DataIngestionError: If ingestion fails
        """
        if not file_paths:
            self.logger.warning("No files provided for ingestion")
            return []
        
        # Initialize progress tracker
        progress = ProgressTracker(len(file_paths))
        if progress_callback:
            progress.add_callback(progress_callback)
        
        all_records = []
        
        # Process files in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all file processing tasks
            future_to_file = {
                executor.submit(self._process_single_file, file_path): file_path
                for file_path in file_paths
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    records, duplicates = future.result()
                    if records:
                        all_records.extend(records)
                        progress.update_file_processed(True, len(records), duplicates)
                        self.logger.info(
                            f"Processed {file_path}: {len(records)} records, {duplicates} duplicates"
                        )
                    else:
                        progress.update_file_processed(False)
                        self.logger.warning(f"No valid records found in {file_path}")
                        
                except Exception as e:
                    progress.update_file_processed(False)
                    self.logger.error(f"Failed to process {file_path}: {e}")
                    self.ingestion_stats['processing_errors'] += 1
        
        # Update final statistics
        self.ingestion_stats['files_processed'] = progress.successful_files
        self.ingestion_stats['total_records'] = len(all_records)
        self.ingestion_stats['valid_records'] = len(all_records)
        self.ingestion_stats['duplicate_records'] = progress.duplicate_records
        
        self.logger.info(f"Ingestion complete: {len(all_records)} total records processed")
        
        return all_records
    
    def _process_single_file(self, file_path: Path) -> Tuple[List[SierraChartTradeRecord], int]:
        """
        Process a single file and return records with duplicate count.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            Tuple of (records, duplicate_count)
        """
        try:
            # Parse the file
            raw_records = self.parser.parse_file(file_path)
            
            # Remove duplicates and validate
            unique_records = []
            duplicates = 0
            
            for record in raw_records:
                if self._is_duplicate(record):
                    duplicates += 1
                    continue
                
                # Validate symbol is expected
                if not self._is_expected_symbol(record):
                    self.logger.warning(
                        f"Unexpected symbol {record.symbol} in {file_path}, skipping record"
                    )
                    continue
                
                unique_records.append(record)
                self._mark_as_seen(record)
            
            return unique_records, duplicates
            
        except SierraChartParseError as e:
            self.logger.error(f"Parse error for {file_path}: {e}")
            return [], 0
        except Exception as e:
            self.logger.error(f"Unexpected error processing {file_path}: {e}")
            return [], 0
    
    def _is_duplicate(self, record: SierraChartTradeRecord) -> bool:
        """
        Check if record is a duplicate using ServiceOrderID and InternalOrderID.
        
        Args:
            record: Record to check
            
        Returns:
            True if record is a duplicate
        """
        # Create unique identifier combining multiple fields
        unique_id = self._generate_record_id(record)
        
        if unique_id in self.seen_records:
            # Determine type of duplicate
            service_id = f"service_{record.service_order_id}"
            internal_id = f"internal_{record.internal_order_id}"
            
            if service_id in self.seen_records:
                self.duplicate_stats['service_order_duplicates'] += 1
            elif internal_id in self.seen_records:
                self.duplicate_stats['internal_order_duplicates'] += 1
            else:
                self.duplicate_stats['exact_duplicates'] += 1
            
            return True
        
        return False
    
    def _mark_as_seen(self, record: SierraChartTradeRecord):
        """Mark record as seen for duplicate detection."""
        unique_id = self._generate_record_id(record)
        self.seen_records.add(unique_id)
        
        # Also track individual IDs
        self.seen_records.add(f"service_{record.service_order_id}")
        self.seen_records.add(f"internal_{record.internal_order_id}")
    
    def _generate_record_id(self, record: SierraChartTradeRecord) -> str:
        """
        Generate unique identifier for a record.
        
        Args:
            record: Record to generate ID for
            
        Returns:
            Unique identifier string
        """
        # Combine multiple fields to create unique identifier
        id_components = [
            record.service_order_id,
            record.internal_order_id,
            record.trade_account,
            record.symbol,
            record.date_time.isoformat(),
            str(record.fill_price),
            str(record.filled_quantity),
            record.buy_sell,
            record.open_close
        ]
        
        # Create hash of combined components
        combined = "|".join(id_components)
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _is_expected_symbol(self, record: SierraChartTradeRecord) -> bool:
        """
        Check if record contains expected symbol (NQ, FDAX, CL, ES).
        
        Args:
            record: Record to check
            
        Returns:
            True if symbol is expected
        """
        base_symbol = record.base_symbol
        is_expected = base_symbol in self.EXPECTED_SYMBOLS
        
        # Debug logging for CL symbols to diagnose the issue
        if not is_expected and base_symbol.startswith('CL'):
            self.logger.debug(f"CL symbol debug: full_symbol='{record.symbol}', base_symbol='{base_symbol}', expected_symbols={self.EXPECTED_SYMBOLS}")
        
        return is_expected
    
    def ingest_from_default_directories(self, 
                                      max_workers: int = 4,
                                      progress_callback: Optional[Callable] = None) -> List[SierraChartTradeRecord]:
        """
        Convenience method to ingest from default SierraChart directories.
        
        Args:
            max_workers: Maximum number of worker threads
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of all ingested records
        """
        file_paths = self.scan_directories()
        return self.ingest_files(file_paths, max_workers, progress_callback)
    
    def get_ingestion_statistics(self) -> Dict:
        """Get comprehensive ingestion statistics."""
        stats = self.ingestion_stats.copy()
        stats.update({
            'duplicate_breakdown': self.duplicate_stats.copy(),
            'parser_stats': self.parser.get_parse_statistics()
        })
        return stats
    
    def reset_statistics(self):
        """Reset all statistics and duplicate tracking."""
        self.seen_records.clear()
        self.duplicate_stats = {
            'service_order_duplicates': 0,
            'internal_order_duplicates': 0,
            'exact_duplicates': 0
        }
        self.ingestion_stats = {
            'directories_scanned': 0,
            'files_found': 0,
            'files_processed': 0,
            'total_records': 0,
            'valid_records': 0,
            'duplicate_records': 0,
            'processing_errors': 0
        }
        self.parser.reset_statistics()
    
    def validate_directories(self, directories: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Validate that directories exist and are accessible.
        
        Args:
            directories: List of directories to validate. Uses defaults if None.
            
        Returns:
            Dictionary mapping directory paths to validation status
        """
        if directories is None:
            directories = self.DEFAULT_DIRECTORIES
        
        validation_results = {}
        
        for directory in directories:
            try:
                dir_path = Path(directory)
                is_valid = (
                    dir_path.exists() and 
                    dir_path.is_dir() and 
                    os.access(dir_path, os.R_OK)
                )
                validation_results[directory] = is_valid
                
                if not is_valid:
                    if not dir_path.exists():
                        self.logger.warning(f"Directory does not exist: {directory}")
                    elif not dir_path.is_dir():
                        self.logger.warning(f"Path is not a directory: {directory}")
                    elif not os.access(dir_path, os.R_OK):
                        self.logger.warning(f"Directory is not readable: {directory}")
                        
            except Exception as e:
                self.logger.error(f"Error validating directory {directory}: {e}")
                validation_results[directory] = False
        
        return validation_results
    
    def get_file_summary(self, file_paths: List[Path]) -> Dict:
        """
        Get summary information about files to be processed.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Summary dictionary with file information
        """
        summary = {
            'total_files': len(file_paths),
            'total_size_bytes': 0,
            'file_extensions': {},
            'directories': set(),
            'oldest_file': None,
            'newest_file': None
        }
        
        for file_path in file_paths:
            try:
                if file_path.exists():
                    # File size
                    size = file_path.stat().st_size
                    summary['total_size_bytes'] += size
                    
                    # Extension
                    ext = file_path.suffix.lower()
                    summary['file_extensions'][ext] = summary['file_extensions'].get(ext, 0) + 1
                    
                    # Directory
                    summary['directories'].add(str(file_path.parent))
                    
                    # Modification time
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if summary['oldest_file'] is None or mtime < summary['oldest_file']:
                        summary['oldest_file'] = mtime
                    if summary['newest_file'] is None or mtime > summary['newest_file']:
                        summary['newest_file'] = mtime
                        
            except Exception as e:
                self.logger.warning(f"Error getting info for {file_path}: {e}")
        
        summary['directories'] = list(summary['directories'])
        return summary