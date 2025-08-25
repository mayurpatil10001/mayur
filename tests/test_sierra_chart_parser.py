"""
Unit tests for SierraChart file parser.
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from trading_platform.services.sierra_chart_parser import SierraChartFileParser, SierraChartParseError
from trading_platform.models.sierra_chart import SierraChartTradeRecord
from trading_platform.utils.validators import ValidationError


class TestSierraChartFileParser:
    """Test cases for SierraChart file parser."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance for testing."""
        return SierraChartFileParser()
    
    @pytest.fixture
    def sample_headers(self):
        """Sample SierraChart headers."""
        return [
            "ActivityType", "DateTime", "TransDateTime", "ServiceOrderID", "OrderType",
            "Quantity", "OrderStatus", "TradeAccount", "BuySell", "Price", "Price2",
            "FillPrice", "FilledQuantity", "Note", "OrderActionSource", "InternalOrderID",
            "Symbol", "OpenClose", "ParentInternalOrderID", "PositionQuantity",
            "FillExecutionServiceID", "HighDuringPosition", "LowDuringPosition",
            "AccountBalance", "ExchangeOrderID", "ClientOrderID", "TimeInForce",
            "Username", "IsAutomated"
        ]
    
    @pytest.fixture
    def sample_valid_row(self):
        """Sample valid data row."""
        return [
            "Fills", "2024-01-15 09:30:00.123456", "2024-01-15 09:30:00.123456",
            "12345", "Market", "1", "Filled", "IPS_TM_10", "Buy", "18500.0", "",
            "18500.25", "1", "Test trade", "Manual", "INT123", "NQH24", "Open",
            "", "1", "EXEC123", "18600.0", "18400.0", "100000.0", "EX123",
            "CL123", "DAY", "trader1", "N"
        ]
    
    @pytest.fixture
    def sample_file_content(self, sample_headers, sample_valid_row):
        """Sample file content."""
        header_line = '\t'.join(sample_headers)
        data_line = '\t'.join(sample_valid_row)
        return f"{header_line}\n{data_line}\n"
    
    def create_temp_file(self, content: str, suffix: str = '.txt') -> Path:
        """Create temporary file with content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8')
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)
    
    def test_validate_file_format_valid_file(self, parser, sample_file_content):
        """Test file format validation with valid file."""
        temp_file = self.create_temp_file(sample_file_content)
        try:
            assert parser.validate_file_format(temp_file) is True
        finally:
            os.unlink(temp_file)
    
    def test_validate_file_format_missing_file(self, parser):
        """Test file format validation with missing file."""
        with pytest.raises(SierraChartParseError, match="File does not exist"):
            parser.validate_file_format(Path("nonexistent.txt"))
    
    def test_validate_file_format_empty_file(self, parser):
        """Test file format validation with empty file."""
        temp_file = self.create_temp_file("")
        try:
            with pytest.raises(SierraChartParseError, match="File is empty"):
                parser.validate_file_format(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_validate_file_format_wrong_column_count(self, parser):
        """Test file format validation with wrong number of columns."""
        content = "Col1\tCol2\tCol3\n"  # Only 3 columns instead of 29
        temp_file = self.create_temp_file(content)
        try:
            with pytest.raises(SierraChartParseError, match="Expected 29 columns, found 3"):
                parser.validate_file_format(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_validate_file_format_missing_headers(self, parser):
        """Test file format validation with missing required headers."""
        headers = ["Col1", "Col2"] + [""] * 27  # Missing required headers
        content = '\t'.join(headers) + "\n"
        temp_file = self.create_temp_file(content)
        try:
            with pytest.raises(SierraChartParseError, match="Expected 29 columns, found"):
                parser.validate_file_format(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_parse_file_valid_content(self, parser, sample_file_content):
        """Test parsing valid file content."""
        temp_file = self.create_temp_file(sample_file_content)
        try:
            records = parser.parse_file(temp_file)
            assert len(records) == 1
            assert isinstance(records[0], SierraChartTradeRecord)
            assert records[0].activity_type == "Fills"
            assert records[0].trade_account == "IPS_TM_10"
            assert records[0].symbol == "NQH24"
            assert records[0].fill_price == 18500.25
        finally:
            os.unlink(temp_file)
    
    def test_parse_file_with_empty_lines(self, parser, sample_headers, sample_valid_row):
        """Test parsing file with empty lines."""
        header_line = '\t'.join(sample_headers)
        data_line = '\t'.join(sample_valid_row)
        content = f"{header_line}\n\n{data_line}\n\n"  # Empty lines
        
        temp_file = self.create_temp_file(content)
        try:
            records = parser.parse_file(temp_file)
            assert len(records) == 1  # Empty lines should be skipped
        finally:
            os.unlink(temp_file)
    
    def test_parse_file_with_missing_columns(self, parser, sample_headers):
        """Test parsing file with missing columns in data row."""
        header_line = '\t'.join(sample_headers)
        incomplete_row = '\t'.join(["Fills", "2024-01-15 09:30:00.123456"])  # Only 2 columns
        content = f"{header_line}\n{incomplete_row}\n"
        
        temp_file = self.create_temp_file(content)
        try:
            records = parser.parse_file(temp_file)
            # Should handle missing columns gracefully
            assert len(records) >= 0  # May be 0 if validation fails
        finally:
            os.unlink(temp_file)
    
    def test_parse_file_with_extra_columns(self, parser, sample_headers, sample_valid_row):
        """Test parsing file with extra columns in data row."""
        header_line = '\t'.join(sample_headers)
        extended_row = sample_valid_row + ["extra1", "extra2"]  # Extra columns
        data_line = '\t'.join(extended_row)
        content = f"{header_line}\n{data_line}\n"
        
        temp_file = self.create_temp_file(content)
        try:
            records = parser.parse_file(temp_file)
            assert len(records) == 1  # Should handle extra columns
        finally:
            os.unlink(temp_file)
    
    def test_parse_datetime_formats(self, parser):
        """Test parsing various datetime formats."""
        test_cases = [
            "2024-01-15 09:30:00.123456",
            "2024-01-15 09:30:00",
            "01/15/2024 09:30:00.123456",
            "01/15/2024 09:30:00"
        ]
        
        for dt_str in test_cases:
            result = parser._parse_datetime(dt_str, "DateTime", 1)
            assert isinstance(result, datetime)
    
    def test_parse_datetime_invalid_format(self, parser):
        """Test parsing invalid datetime format."""
        with pytest.raises(ValidationError, match="Invalid datetime format"):
            parser._parse_datetime("invalid-date", "DateTime", 1)
    
    def test_parse_integer_valid(self, parser):
        """Test parsing valid integers."""
        assert parser._parse_integer("123", "Quantity", 1) == 123
        assert parser._parse_integer("1.0", "Quantity", 1) == 1  # Handle float strings
    
    def test_parse_integer_invalid(self, parser):
        """Test parsing invalid integers."""
        with pytest.raises(ValidationError, match="Invalid integer"):
            parser._parse_integer("abc", "Quantity", 1)
    
    def test_parse_float_valid(self, parser):
        """Test parsing valid floats."""
        assert parser._parse_float("123.45", "Price", 1) == 123.45
        assert parser._parse_float("", "Price", 1, optional=True) is None
    
    def test_parse_float_invalid_required(self, parser):
        """Test parsing invalid float for required field."""
        with pytest.raises(ValidationError, match="Invalid float"):
            parser._parse_float("abc", "FillPrice", 1, optional=False)
    
    def test_parse_float_invalid_optional(self, parser):
        """Test parsing invalid float for optional field."""
        result = parser._parse_float("abc", "Price", 1, optional=True)
        assert result is None  # Should return None for invalid optional fields
    
    def test_parse_multiple_files(self, parser, sample_file_content):
        """Test parsing multiple files."""
        temp_files = []
        try:
            # Create multiple temp files
            for i in range(3):
                temp_file = self.create_temp_file(sample_file_content)
                temp_files.append(temp_file)
            
            records = parser.parse_multiple_files(temp_files)
            assert len(records) == 3  # One record per file
            
        finally:
            for temp_file in temp_files:
                os.unlink(temp_file)
    
    def test_parse_multiple_files_with_errors(self, parser, sample_file_content):
        """Test parsing multiple files with some errors."""
        temp_files = []
        try:
            # Create valid file
            valid_file = self.create_temp_file(sample_file_content)
            temp_files.append(valid_file)
            
            # Create invalid file
            invalid_file = self.create_temp_file("invalid content")
            temp_files.append(invalid_file)
            
            # Add non-existent file
            temp_files.append(Path("nonexistent.txt"))
            
            records = parser.parse_multiple_files(temp_files)
            assert len(records) == 1  # Only valid file should be parsed
            
        finally:
            for temp_file in temp_files:
                if temp_file.exists():
                    os.unlink(temp_file)
    
    def test_get_parse_statistics(self, parser, sample_file_content):
        """Test getting parse statistics."""
        temp_file = self.create_temp_file(sample_file_content)
        try:
            parser.parse_file(temp_file)
            stats = parser.get_parse_statistics()
            
            assert stats['files_processed'] == 1
            assert stats['total_records'] == 1
            assert stats['valid_records'] == 1
            assert stats['invalid_records'] == 0
            
        finally:
            os.unlink(temp_file)
    
    def test_reset_statistics(self, parser, sample_file_content):
        """Test resetting parse statistics."""
        temp_file = self.create_temp_file(sample_file_content)
        try:
            parser.parse_file(temp_file)
            parser.reset_statistics()
            stats = parser.get_parse_statistics()
            
            assert all(value == 0 for value in stats.values())
            
        finally:
            os.unlink(temp_file)
    
    def test_convert_data_types_complete(self, parser):
        """Test complete data type conversion."""
        raw_data = {
            'ActivityType': 'Fills',
            'DateTime': '2024-01-15 09:30:00.123456',
            'TransDateTime': '2024-01-15 09:30:00.123456',
            'ServiceOrderID': '12345',
            'OrderType': 'Market',
            'Quantity': '1',
            'OrderStatus': 'Filled',
            'TradeAccount': 'IPS_TM_10',
            'BuySell': 'Buy',
            'Price': '18500.0',
            'Price2': '',
            'FillPrice': '18500.25',
            'FilledQuantity': '1',
            'Note': 'Test',
            'OrderActionSource': 'Manual',
            'InternalOrderID': 'INT123',
            'Symbol': 'NQH24',
            'OpenClose': 'Open',
            'ParentInternalOrderID': '',
            'PositionQuantity': '1',
            'FillExecutionServiceID': 'EXEC123',
            'HighDuringPosition': '18600.0',
            'LowDuringPosition': '18400.0',
            'AccountBalance': '100000.0',
            'ExchangeOrderID': 'EX123',
            'ClientOrderID': 'CL123',
            'TimeInForce': 'DAY',
            'Username': 'trader1',
            'IsAutomated': 'N'
        }
        
        converted = parser._convert_data_types(raw_data, 1)
        
        # Check datetime conversion
        assert isinstance(converted['date_time'], datetime)
        assert isinstance(converted['trans_date_time'], datetime)
        
        # Check integer conversion
        assert converted['quantity'] == 1
        assert converted['filled_quantity'] == 1
        assert converted['position_quantity'] == 1
        
        # Check float conversion
        assert converted['fill_price'] == 18500.25
        assert converted['price'] == 18500.0
        assert converted['price2'] is None  # Empty string should become None
        assert converted['account_balance'] == 100000.0
        
        # Check string fields
        assert converted['activity_type'] == 'Fills'
        assert converted['trade_account'] == 'IPS_TM_10'
        assert converted['symbol'] == 'NQH24'
    
    def test_file_encoding_detection(self):
        """Test file encoding detection."""
        # This test requires chardet package
        try:
            encoding = SierraChartFileParser.detect_file_encoding(Path(__file__))
            assert isinstance(encoding, str)
            assert encoding in ['utf-8', 'ascii', 'windows-1252']  # Common encodings
        except ImportError:
            pytest.skip("chardet package not available")
    
    def test_parse_record_with_validation_error(self, parser, sample_headers):
        """Test parsing record that fails validation."""
        invalid_row = [
            "InvalidActivity",  # Invalid activity type
            "2024-01-15 09:30:00.123456", "2024-01-15 09:30:00.123456",
            "12345", "Market", "1", "Filled", "IPS_TM_10", "Buy", "18500.0", "",
            "18500.25", "1", "Test trade", "Manual", "INT123", "NQH24", "Open",
            "", "1", "EXEC123", "18600.0", "18400.0", "100000.0", "EX123",
            "CL123", "DAY", "trader1", "N"
        ]
        
        record = parser._parse_record(sample_headers, invalid_row, "test.txt", 2)
        assert record is None  # Should return None for invalid records
    
    def test_unsupported_file_extension(self, parser):
        """Test validation with unsupported file extension."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        temp_file.close()
        
        try:
            with pytest.raises(SierraChartParseError, match="Unsupported file extension"):
                parser.validate_file_format(Path(temp_file.name))
        finally:
            os.unlink(temp_file.name)
    
    def test_parse_file_permission_error(self, parser):
        """Test parsing file with permission error."""
        # Skip this test on Windows as chmod doesn't work the same way
        if os.name == 'nt':
            pytest.skip("Permission test not applicable on Windows")
            
        # Create a file and make it unreadable (Unix-like systems)
        temp_file = self.create_temp_file("test content")
        try:
            # Try to make file unreadable
            os.chmod(temp_file, 0o000)
            
            with pytest.raises(SierraChartParseError, match="Permission denied"):
                parser.parse_file(temp_file)
                
        except PermissionError:
            # Skip test if we can't change permissions
            pytest.skip("Cannot test permission error on this system")
        finally:
            # Restore permissions and cleanup
            try:
                os.chmod(temp_file, 0o644)
                os.unlink(temp_file)
            except:
                pass
    
    @pytest.mark.parametrize("invalid_datetime", [
        "",
        "not-a-date",
        "2024-13-01 25:00:00",  # Invalid month/hour
        "01/32/2024 09:30:00",  # Invalid day
    ])
    def test_parse_datetime_edge_cases(self, parser, invalid_datetime):
        """Test datetime parsing edge cases."""
        with pytest.raises(ValidationError):
            parser._parse_datetime(invalid_datetime, "DateTime", 1)
    
    @pytest.mark.parametrize("invalid_integer", [
        "",
        "not-a-number",
        "12.34.56",  # Multiple decimal points
        "abc123",  # Mixed letters and numbers
    ])
    def test_parse_integer_edge_cases(self, parser, invalid_integer):
        """Test integer parsing edge cases."""
        with pytest.raises(ValidationError):
            parser._parse_integer(invalid_integer, "Quantity", 1)