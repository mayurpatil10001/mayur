"""
Parser for SierraChart processed trade files (27-column format).
"""

import logging
import csv
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from ..models.sierra_chart import ProcessedTrade
from ..utils.validators import ValidationError


@dataclass
class SierraChartProcessedTradeRecord:
    """Represents a processed trade record from SierraChart."""
    symbol: str
    trade_type: str  # "Long" or "Short"
    entry_datetime: datetime
    exit_datetime: datetime
    entry_price: float
    exit_price: float
    trade_quantity: int
    max_open_quantity: int
    max_closed_quantity: int
    profit_loss: float
    cumulative_profit_loss: float
    duration: str  # "HH:MM:SS" format
    commission: float
    high_price_while_open: float
    low_price_while_open: float
    exit_efficiency: str  # Percentage string
    entry_efficiency: str  # Percentage string
    flat_to_flat_profit_loss: float
    flat_to_flat_max_open_profit: float
    flat_to_flat_max_open_loss: float
    max_open_profit: float
    max_open_loss: float
    note: str
    total_efficiency: str  # Percentage string
    open_position_quantity: int
    close_position_quantity: int
    account: str


class ProcessedTradeParseError(Exception):
    """Exception raised during processed trade parsing."""
    pass


class SierraChartProcessedTradeParser:
    """Parser for SierraChart processed trade files."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the parser."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Expected column headers
        self.expected_headers = [
            "Symbol", "Trade Type", "Entry DateTime", "Exit DateTime", "Entry Price",
            "Exit Price", "Trade Quantity", "Max Open Quantity", "Max Closed Quantity",
            "Profit/Loss (C)", "Cumulative Profit/Loss (C)", "Duration", "Commission (C)",
            "High Price While Open", "Low Price While Open", "Exit Efficiency",
            "Entry Efficiency", "FlatToFlat Profit/Loss (C)", "FlatToFlat Max Open Profit (C)",
            "FlatToFlat Max Open Loss (C)", "Max Open Profit (C)", "Max Open Loss (C)",
            "Note", "Total Efficiency", "Open Position Quantity", "Close Position Quantity",
            "Account"
        ]
    
    def parse_file(self, file_path: Path) -> List[SierraChartProcessedTradeRecord]:
        """
        Parse a SierraChart processed trade file.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            List of parsed trade records
            
        Raises:
            ProcessedTradeParseError: If parsing fails
        """
        try:
            self.logger.info(f"Parsing processed trade file: {file_path}")
            
            records = []
            
            with open(file_path, 'r', encoding='utf-8') as file:
                # Read the file content
                content = file.read().strip()
                
                if not content:
                    self.logger.warning(f"Empty file: {file_path}")
                    return []
                
                # Split into lines
                lines = content.split('\n')
                
                if len(lines) < 2:
                    self.logger.warning(f"File has no data rows: {file_path}")
                    return []
                
                # Parse header
                header_line = lines[0]
                headers = [h.strip() for h in header_line.split('\t')]
                
                self.logger.debug(f"Found {len(headers)} columns in header")
                
                # Validate header count
                if len(headers) < 27:
                    raise ProcessedTradeParseError(f"Expected at least 27 columns, found {len(headers)}")
                
                # Parse data rows
                for line_num, line in enumerate(lines[1:], start=2):
                    if not line.strip():
                        continue  # Skip empty lines
                    
                    try:
                        record = self._parse_line(line, line_num)
                        if record:
                            records.append(record)
                    except Exception as e:
                        self.logger.error(f"Error parsing line {line_num} in {file_path}: {e}")
                        continue
            
            self.logger.info(f"Successfully parsed {len(records)} records from {file_path}")
            return records
            
        except Exception as e:
            raise ProcessedTradeParseError(f"Failed to parse file {file_path}: {e}")
    
    def _parse_line(self, line: str, line_num: int) -> Optional[SierraChartProcessedTradeRecord]:
        """
        Parse a single line of trade data.
        
        Args:
            line: Line to parse
            line_num: Line number for error reporting
            
        Returns:
            Parsed trade record or None if invalid
        """
        try:
            # Split by tab
            fields = line.split('\t')
            
            if len(fields) < 27:
                self.logger.warning(f"Line {line_num}: Expected at least 27 fields, found {len(fields)}")
                return None
            
            # Parse each field
            record = SierraChartProcessedTradeRecord(
                symbol=self._parse_string(fields[0], "Symbol"),
                trade_type=self._parse_string(fields[1], "Trade Type"),
                entry_datetime=self._parse_datetime(fields[2], "Entry DateTime"),
                exit_datetime=self._parse_datetime(fields[3], "Exit DateTime"),
                entry_price=self._parse_float(fields[4], "Entry Price"),
                exit_price=self._parse_float(fields[5], "Exit Price"),
                trade_quantity=self._parse_int(fields[6], "Trade Quantity"),
                max_open_quantity=self._parse_int(fields[7], "Max Open Quantity"),
                max_closed_quantity=self._parse_int(fields[8], "Max Closed Quantity"),
                profit_loss=self._parse_float(fields[9], "Profit/Loss"),
                cumulative_profit_loss=self._parse_float(fields[10], "Cumulative Profit/Loss"),
                duration=self._parse_string(fields[11], "Duration"),
                commission=self._parse_float(fields[12], "Commission"),
                high_price_while_open=self._parse_float(fields[13], "High Price While Open"),
                low_price_while_open=self._parse_float(fields[14], "Low Price While Open"),
                exit_efficiency=self._parse_string(fields[15], "Exit Efficiency"),
                entry_efficiency=self._parse_string(fields[16], "Entry Efficiency"),
                flat_to_flat_profit_loss=self._parse_float(fields[17], "FlatToFlat Profit/Loss"),
                flat_to_flat_max_open_profit=self._parse_float(fields[18], "FlatToFlat Max Open Profit"),
                flat_to_flat_max_open_loss=self._parse_float(fields[19], "FlatToFlat Max Open Loss"),
                max_open_profit=self._parse_float(fields[20], "Max Open Profit"),
                max_open_loss=self._parse_float(fields[21], "Max Open Loss"),
                note=self._parse_string(fields[22], "Note"),
                total_efficiency=self._parse_string(fields[23], "Total Efficiency"),
                open_position_quantity=self._parse_int(fields[24], "Open Position Quantity"),
                close_position_quantity=self._parse_int(fields[25], "Close Position Quantity"),
                account=self._parse_string(fields[26], "Account")
            )
            
            # Validate the record
            self._validate_record(record, line_num)
            
            return record
            
        except Exception as e:
            self.logger.error(f"Error parsing line {line_num}: {e}")
            return None
    
    def _parse_string(self, value: str, field_name: str) -> str:
        """Parse string field."""
        if not value or value.strip() == "":
            return ""
        return value.strip()
    
    def _parse_int(self, value: str, field_name: str) -> int:
        """Parse integer field."""
        if not value or value.strip() == "":
            return 0
        try:
            clean_value = value.strip()
            # Handle percentage values by removing the % sign
            if clean_value.endswith('%'):
                clean_value = clean_value[:-1]
            # Handle values with 'F' suffix (futures format)
            if clean_value.endswith(' F'):
                clean_value = clean_value[:-2]
            return int(float(clean_value))  # Handle decimal integers
        except ValueError:
            raise ValidationError(f"Invalid {field_name}: {value}")
    
    def _parse_float(self, value: str, field_name: str) -> float:
        """Parse float field."""
        if not value or value.strip() == "":
            return 0.0
        try:
            # Handle percentage values by removing the % sign
            clean_value = value.strip()
            if clean_value.endswith('%'):
                clean_value = clean_value[:-1]
            # Handle values with 'F' suffix (futures format)
            if clean_value.endswith(' F'):
                clean_value = clean_value[:-2]
            return float(clean_value)
        except ValueError:
            raise ValidationError(f"Invalid {field_name}: {value}")
    
    def _parse_datetime(self, value: str, field_name: str) -> datetime:
        """Parse datetime field."""
        if not value or value.strip() == "":
            raise ValidationError(f"{field_name} cannot be empty")
        
        try:
            # Try different datetime formats
            value = value.strip()
            
            # Format: "2024-03-03  18:23:05.473 BP"
            if " BP" in value or " EP" in value:
                value = value.replace(" BP", "").replace(" EP", "").strip()
            
            # Handle multiple spaces
            while "  " in value:
                value = value.replace("  ", " ")
            
            # Try parsing with microseconds
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                pass
            
            # Try parsing without microseconds
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
            
            # Try parsing date only
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                pass
            
            raise ValidationError(f"Unable to parse datetime: {value}")
            
        except Exception as e:
            raise ValidationError(f"Invalid {field_name}: {value} - {e}")
    
    def _validate_record(self, record: SierraChartProcessedTradeRecord, line_num: int):
        """Validate a parsed record."""
        # Basic validations
        if not record.symbol:
            raise ValidationError(f"Line {line_num}: Symbol cannot be empty")
        
        if not record.account:
            raise ValidationError(f"Line {line_num}: Account cannot be empty")
        
        if record.trade_quantity <= 0:
            raise ValidationError(f"Line {line_num}: Trade quantity must be positive")
        
        if record.entry_datetime >= record.exit_datetime:
            raise ValidationError(f"Line {line_num}: Entry time must be before exit time")
        
        if record.entry_price <= 0 or record.exit_price <= 0:
            raise ValidationError(f"Line {line_num}: Prices must be positive")
    
    def convert_to_processed_trade(self, record: SierraChartProcessedTradeRecord, filename: str = None) -> ProcessedTrade:
        """
        Convert SierraChart processed trade record to our ProcessedTrade model.
        
        Args:
            record: SierraChart processed trade record
            
        Returns:
            ProcessedTrade object
        """
        # Extract base symbol (e.g., "NQH24" -> "NQ")
        base_symbol = record.symbol[:2] if len(record.symbol) >= 2 else record.symbol
        
        # Calculate duration in minutes
        duration_minutes = int((record.exit_datetime - record.entry_datetime).total_seconds() / 60)
        
        # Determine side
        side = "LONG" if record.trade_type.upper() in ["LONG", "BUY"] else "SHORT"
        
        # Extract account name from filename if the record account is just a number
        account_name = record.account
        if filename and record.account.isdigit():
            # Extract account name from filename like "NQ_IPS_TM_10_20240101-20250716.txt"
            import re
            filename_parts = filename.split('_')
            if len(filename_parts) >= 3:
                # Try to find account pattern in filename
                account_pattern = re.search(r'([A-Z]+_[A-Z]+_\d+|[A-Z]+_\d+|PB_\d+)', filename)
                if account_pattern:
                    account_name = account_pattern.group(1)
                    self.logger.debug(f"Extracted account name '{account_name}' from filename '{filename}' (was '{record.account}')")
        
        # Generate unique trade ID using more fields to avoid duplicates
        unique_string = f"{account_name}_{record.symbol}_{record.entry_datetime.isoformat()}_{record.exit_datetime.isoformat()}_{record.entry_price}_{record.exit_price}_{record.trade_quantity}_{record.profit_loss}_{record.commission}_{record.duration}"
        trade_id = f"{account_name}_{record.symbol}_{record.entry_datetime.strftime('%Y%m%d_%H%M%S_%f')}_{abs(hash(unique_string)) % 1000000}"
        
        return ProcessedTrade(
            trade_id=trade_id,
            account_name=account_name,
            symbol=base_symbol,
            entry_time=record.entry_datetime,
            exit_time=record.exit_datetime,
            entry_price=record.entry_price,
            exit_price=record.exit_price,
            quantity=record.trade_quantity,
            side=side,
            profit_loss=record.profit_loss,
            commission=record.commission,
            duration_minutes=duration_minutes,
            hour_of_day=record.entry_datetime.hour,
            day_of_week=record.entry_datetime.weekday()
        )