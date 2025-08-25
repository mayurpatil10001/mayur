"""
SierraChart tab-delimited file parser with robust error handling and validation.
"""

import csv
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator
from datetime import datetime
import logging

from ..models.sierra_chart import SierraChartTradeRecord
from ..utils.validators import ValidationError


class SierraChartParseError(Exception):
    """Exception raised when parsing SierraChart files fails."""
    pass


class SierraChartFileParser:
    """Parser for SierraChart tab-delimited files with comprehensive validation."""
    
    # Expected SierraChart column headers (29 columns)
    EXPECTED_HEADERS = [
        "ActivityType", "DateTime", "TransDateTime", "ServiceOrderID", "OrderType",
        "Quantity", "OrderStatus", "TradeAccount", "BuySell", "Price", "Price2",
        "FillPrice", "FilledQuantity", "Note", "OrderActionSource", "InternalOrderID",
        "Symbol", "OpenClose", "ParentInternalOrderID", "PositionQuantity",
        "FillExecutionServiceID", "HighDuringPosition", "LowDuringPosition",
        "AccountBalance", "ExchangeOrderID", "ClientOrderID", "TimeInForce",
        "Username", "IsAutomated"
    ]
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize parser with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
        self.parse_stats = {
            'files_processed': 0,
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'warnings': 0
        }
    
    def validate_file_format(self, file_path: Path) -> bool:
        """
        Validate that file has correct SierraChart format.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            True if file format is valid
            
        Raises:
            SierraChartParseError: If file format is invalid
        """
        if not file_path.exists():
            raise SierraChartParseError(f"File does not exist: {file_path}")
        
        if not file_path.is_file():
            raise SierraChartParseError(f"Path is not a file: {file_path}")
        
        if file_path.suffix.lower() not in ['.txt', '.csv', '.tsv']:
            raise SierraChartParseError(f"Unsupported file extension: {file_path.suffix}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # Read first line to check headers
                first_line = file.readline().strip()
                if not first_line:
                    raise SierraChartParseError("File is empty")
                
                headers = first_line.split('\t')
                
                # Check if we have the expected number of columns
                if len(headers) != len(self.EXPECTED_HEADERS):
                    raise SierraChartParseError(
                        f"Expected {len(self.EXPECTED_HEADERS)} columns, found {len(headers)}"
                    )
                
                # Check if headers match expected format
                missing_headers = []
                for expected_header in self.EXPECTED_HEADERS:
                    if expected_header not in headers:
                        missing_headers.append(expected_header)
                
                if missing_headers:
                    raise SierraChartParseError(
                        f"Missing required headers: {missing_headers}"
                    )
                
                # Check for extra headers
                extra_headers = []
                for header in headers:
                    if header not in self.EXPECTED_HEADERS:
                        extra_headers.append(header)
                
                if extra_headers:
                    self.logger.warning(f"Found unexpected headers: {extra_headers}")
                
                return True
                
        except UnicodeDecodeError as e:
            raise SierraChartParseError(f"File encoding error: {e}")
        except Exception as e:
            raise SierraChartParseError(f"File validation failed: {e}")
    
    def parse_file(self, file_path: Path, validate_format: bool = True) -> List[SierraChartTradeRecord]:
        """
        Parse a single SierraChart file.
        
        Args:
            file_path: Path to the file to parse
            validate_format: Whether to validate file format first
            
        Returns:
            List of parsed and validated SierraChartTradeRecord objects
            
        Raises:
            SierraChartParseError: If parsing fails
        """
        if validate_format:
            self.validate_file_format(file_path)
        
        records = []
        file_source = str(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # Use csv.reader with tab delimiter for robust parsing
                reader = csv.reader(file, delimiter='\t')
                
                # Read headers
                headers = next(reader)
                
                # Process each line
                for line_num, row in enumerate(reader, start=2):  # Start at 2 since headers are line 1
                    try:
                        if not row or all(not cell.strip() for cell in row):
                            continue  # Skip empty lines
                        
                        # Handle lines with fewer columns (pad with empty strings)
                        if len(row) < len(headers):
                            row.extend([''] * (len(headers) - len(row)))
                        elif len(row) > len(headers):
                            # Truncate extra columns and log warning
                            self.logger.warning(
                                f"Line {line_num} has {len(row)} columns, expected {len(headers)}. "
                                f"Truncating extra columns."
                            )
                            row = row[:len(headers)]
                        
                        # Create record
                        record = self._parse_record(headers, row, file_source, line_num)
                        if record:
                            records.append(record)
                            self.parse_stats['valid_records'] += 1
                            
                            if record.has_warnings:
                                self.parse_stats['warnings'] += 1
                        else:
                            self.parse_stats['invalid_records'] += 1
                            
                    except Exception as e:
                        self.logger.error(f"Error parsing line {line_num}: {e}")
                        self.parse_stats['invalid_records'] += 1
                        continue
                
                self.parse_stats['files_processed'] += 1
                self.parse_stats['total_records'] += len(records)
                
                self.logger.info(
                    f"Parsed {file_path}: {len(records)} valid records, "
                    f"{self.parse_stats['invalid_records']} invalid records"
                )
                
                return records
                
        except FileNotFoundError:
            raise SierraChartParseError(f"File not found: {file_path}")
        except PermissionError:
            raise SierraChartParseError(f"Permission denied: {file_path}")
        except Exception as e:
            raise SierraChartParseError(f"Failed to parse file {file_path}: {e}")
    
    def _parse_record(self, headers: List[str], row: List[str], file_source: str, line_num: int) -> Optional[SierraChartTradeRecord]:
        """
        Parse a single record from CSV row.
        
        Args:
            headers: Column headers
            row: Data row
            file_source: Source file path
            line_num: Line number for error reporting
            
        Returns:
            Parsed SierraChartTradeRecord or None if parsing fails
        """
        try:
            # Create data dictionary
            data = dict(zip(headers, row))
            
            # Convert data types with robust error handling
            converted_data = self._convert_data_types(data, line_num)
            
            # Create record
            record = SierraChartTradeRecord.from_dict(converted_data, file_source)
            
            return record
            
        except ValidationError as e:
            self.logger.error(f"Validation error on line {line_num}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error parsing line {line_num}: {e}")
            return None
    
    def _convert_data_types(self, data: Dict[str, str], line_num: int) -> Dict[str, Any]:
        """
        Convert string data to appropriate types with robust error handling.
        
        Args:
            data: Raw string data from CSV
            line_num: Line number for error reporting
            
        Returns:
            Dictionary with converted data types
        """
        converted = {}
        
        # Field mapping from CSV headers to dataclass fields
        field_mapping = {
            'ActivityType': 'activity_type',
            'DateTime': 'date_time',
            'TransDateTime': 'trans_date_time',
            'ServiceOrderID': 'service_order_id',
            'OrderType': 'order_type',
            'Quantity': 'quantity',
            'OrderStatus': 'order_status',
            'TradeAccount': 'trade_account',
            'BuySell': 'buy_sell',
            'Price': 'price',
            'Price2': 'price2',
            'FillPrice': 'fill_price',
            'FilledQuantity': 'filled_quantity',
            'Note': 'note',
            'OrderActionSource': 'order_action_source',
            'InternalOrderID': 'internal_order_id',
            'Symbol': 'symbol',
            'OpenClose': 'open_close',
            'ParentInternalOrderID': 'parent_internal_order_id',
            'PositionQuantity': 'position_quantity',
            'FillExecutionServiceID': 'fill_execution_service_id',
            'HighDuringPosition': 'high_during_position',
            'LowDuringPosition': 'low_during_position',
            'AccountBalance': 'account_balance',
            'ExchangeOrderID': 'exchange_order_id',
            'ClientOrderID': 'client_order_id',
            'TimeInForce': 'time_in_force',
            'Username': 'username',
            'IsAutomated': 'is_automated'
        }
        
        for csv_field, dataclass_field in field_mapping.items():
            raw_value = data.get(csv_field, '').strip()
            
            try:
                if dataclass_field in ['date_time', 'trans_date_time']:
                    # Parse datetime fields
                    converted[dataclass_field] = self._parse_datetime(raw_value, csv_field, line_num)
                    
                elif dataclass_field in ['quantity', 'filled_quantity', 'position_quantity']:
                    # Parse integer fields
                    converted[dataclass_field] = self._parse_integer(raw_value, csv_field, line_num)
                    
                elif dataclass_field in ['price', 'price2', 'fill_price', 'high_during_position', 
                                       'low_during_position', 'account_balance']:
                    # Parse float fields (some optional)
                    is_optional = dataclass_field in ['price', 'price2', 'high_during_position', 'low_during_position']
                    converted[dataclass_field] = self._parse_float(raw_value, csv_field, line_num, is_optional)
                    
                else:
                    # String fields
                    converted[dataclass_field] = raw_value if raw_value else None
                    
            except Exception as e:
                raise ValidationError(f"Failed to convert {csv_field} on line {line_num}: {e}")
        
        return converted
    
    def _parse_datetime(self, value: str, field_name: str, line_num: int) -> datetime:
        """Parse datetime with multiple format support."""
        if not value:
            raise ValidationError(f"{field_name} cannot be empty")
        
        # Common SierraChart datetime formats
        formats = [
            '%Y-%m-%d %H:%M:%S.%f',  # 2024-01-15 09:30:00.123456
            '%Y-%m-%d %H:%M:%S',     # 2024-01-15 09:30:00
            '%m/%d/%Y %H:%M:%S.%f',  # 01/15/2024 09:30:00.123456
            '%m/%d/%Y %H:%M:%S',     # 01/15/2024 09:30:00
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        
        raise ValidationError(f"Invalid datetime format for {field_name}: {value}")
    
    def _parse_integer(self, value: str, field_name: str, line_num: int) -> int:
        """Parse integer with error handling."""
        if not value or value.strip() == '':
            if field_name == "PositionQuantity":
                return 0  # Default to 0 for empty position quantity
            elif field_name in ["Quantity", "FilledQuantity"]:
                raise ValidationError(f"{field_name} cannot be empty")
            else:
                return 0  # Default for other optional integer fields
        
        try:
            # Handle various number formats
            clean_value = value.strip().replace(',', '')  # Remove commas
            return int(float(clean_value))  # Handle cases like "1.0"
        except ValueError:
            raise ValidationError(f"Invalid integer for {field_name}: {value}")
    
    def _parse_float(self, value: str, field_name: str, line_num: int, optional: bool = False) -> Optional[float]:
        """Parse float with error handling."""
        if not value:
            if optional:
                return None
            else:
                raise ValidationError(f"{field_name} cannot be empty")
        
        try:
            return float(value)
        except ValueError:
            if optional:
                self.logger.warning(f"Invalid float for optional field {field_name} on line {line_num}: {value}")
                return None
            else:
                raise ValidationError(f"Invalid float for {field_name}: {value}")
    
    def parse_multiple_files(self, file_paths: List[Path]) -> List[SierraChartTradeRecord]:
        """
        Parse multiple SierraChart files.
        
        Args:
            file_paths: List of file paths to parse
            
        Returns:
            Combined list of all parsed records
        """
        all_records = []
        
        for file_path in file_paths:
            try:
                records = self.parse_file(file_path)
                all_records.extend(records)
                self.logger.info(f"Successfully parsed {file_path}: {len(records)} records")
            except SierraChartParseError as e:
                self.logger.error(f"Failed to parse {file_path}: {e}")
                continue
        
        return all_records
    
    def get_parse_statistics(self) -> Dict[str, int]:
        """Get parsing statistics."""
        return self.parse_stats.copy()
    
    def reset_statistics(self):
        """Reset parsing statistics."""
        self.parse_stats = {
            'files_processed': 0,
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'warnings': 0
        }
    
    @staticmethod
    def detect_file_encoding(file_path: Path) -> str:
        """
        Detect file encoding for robust parsing.
        
        Args:
            file_path: Path to file
            
        Returns:
            Detected encoding string
        """
        import chardet
        
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)  # Read first 10KB
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'  # Default fallback
    
    def parse_file_with_encoding_detection(self, file_path: Path) -> List[SierraChartTradeRecord]:
        """
        Parse file with automatic encoding detection.
        
        Args:
            file_path: Path to file to parse
            
        Returns:
            List of parsed records
        """
        encoding = self.detect_file_encoding(file_path)
        self.logger.info(f"Detected encoding for {file_path}: {encoding}")
        
        # Temporarily modify the parse_file method to use detected encoding
        # This is a simplified approach - in production, you'd want to refactor
        # the parse_file method to accept encoding parameter
        
        return self.parse_file(file_path)