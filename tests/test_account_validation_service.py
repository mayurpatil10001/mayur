"""
Unit tests for account and symbol validation service.
"""

import pytest
from datetime import datetime, date
from typing import List

from trading_platform.services.account_validation_service import (
    AccountValidationService,
    AccountValidationError,
    AccountMetadata,
    SymbolMetadata,
    ValidationViolation
)
from trading_platform.models.sierra_chart import SierraChartTradeRecord


class TestAccountValidationService:
    """Test cases for account validation service."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return AccountValidationService()
    
    @pytest.fixture
    def valid_single_symbol_records(self):
        """Create records for valid single symbol per account scenario."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        records = []
        
        # Account IPS_TM_10 trades only NQ
        for i in range(3):
            record = SierraChartTradeRecord(
                activity_type="Fills",
                date_time=base_time.replace(hour=9+i),
                trans_date_time=base_time.replace(hour=9+i),
                service_order_id=f"1234{i}",
                order_type="Market",
                quantity=1,
                order_status="Filled",
                trade_account="IPS_TM_10",
                buy_sell="Buy" if i % 2 == 0 else "Sell",
                price=18500.0,
                price2=None,
                fill_price=18500.25,
                filled_quantity=1,
                note=f"Trade {i}",
                order_action_source="Manual",
                internal_order_id=f"INT12{i}",
                symbol="NQH24",
                open_close="Open" if i % 2 == 0 else "Close",
                parent_internal_order_id=None,
                position_quantity=1 if i % 2 == 0 else 0,
                fill_execution_service_id=f"EXEC12{i}",
                high_during_position=18600.0,
                low_during_position=18400.0,
                account_balance=100000.0,
                exchange_order_id=f"EX12{i}",
                client_order_id=f"CL12{i}",
                time_in_force="DAY",
                username="trader1",
                is_automated="N"
            )
            records.append(record)
        
        # Account IPS_TM_13 trades only FDAX
        for i in range(2):
            record = SierraChartTradeRecord(
                activity_type="Fills",
                date_time=base_time.replace(hour=10+i),
                trans_date_time=base_time.replace(hour=10+i),
                service_order_id=f"5678{i}",
                order_type="Market",
                quantity=1,
                order_status="Filled",
                trade_account="IPS_TM_13",
                buy_sell="Buy" if i % 2 == 0 else "Sell",
                price=17500.0,
                price2=None,
                fill_price=17500.50,
                filled_quantity=1,
                note=f"FDAX Trade {i}",
                order_action_source="Manual",
                internal_order_id=f"INT56{i}",
                symbol="FDAXM24",
                open_close="Open" if i % 2 == 0 else "Close",
                parent_internal_order_id=None,
                position_quantity=1 if i % 2 == 0 else 0,
                fill_execution_service_id=f"EXEC56{i}",
                high_during_position=17600.0,
                low_during_position=17400.0,
                account_balance=100000.0,
                exchange_order_id=f"EX56{i}",
                client_order_id=f"CL56{i}",
                time_in_force="DAY",
                username="trader2",
                is_automated="N"
            )
            records.append(record)
        
        return records
    
    @pytest.fixture
    def invalid_multiple_symbols_records(self):
        """Create records for invalid multiple symbols per account scenario."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        records = []
        
        # Account IPS_TM_10 trades both NQ and FDAX (violation)
        symbols = ["NQH24", "FDAXM24"]
        prices = [18500.0, 17500.0]
        
        for i, (symbol, price) in enumerate(zip(symbols, prices)):
            record = SierraChartTradeRecord(
                activity_type="Fills",
                date_time=base_time.replace(hour=9+i),
                trans_date_time=base_time.replace(hour=9+i),
                service_order_id=f"1234{i}",
                order_type="Market",
                quantity=1,
                order_status="Filled",
                trade_account="IPS_TM_10",  # Same account for different symbols
                buy_sell="Buy",
                price=price,
                price2=None,
                fill_price=price + 0.25,
                filled_quantity=1,
                note=f"Mixed trade {i}",
                order_action_source="Manual",
                internal_order_id=f"INT12{i}",
                symbol=symbol,
                open_close="Open",
                parent_internal_order_id=None,
                position_quantity=1,
                fill_execution_service_id=f"EXEC12{i}",
                high_during_position=price + 100,
                low_during_position=price - 100,
                account_balance=100000.0,
                exchange_order_id=f"EX12{i}",
                client_order_id=f"CL12{i}",
                time_in_force="DAY",
                username="trader1",
                is_automated="N"
            )
            records.append(record)
        
        return records
    
    @pytest.fixture
    def valid_account_name_records(self):
        """Create records with valid account names for testing account name validation logic."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        # Create a record with valid account name
        record = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time,
            trans_date_time=base_time,
            service_order_id="12345",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_VALID",  # Valid format
            buy_sell="Buy",
            price=18500.0,
            price2=None,
            fill_price=18500.25,
            filled_quantity=1,
            note="Valid account test",
            order_action_source="Manual",
            internal_order_id="INT123",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=1,
            fill_execution_service_id="EXEC123",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100000.0,
            exchange_order_id="EX123",
            client_order_id="CL123",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        
        return [record]
    
    def test_initialization(self, service):
        """Test service initialization."""
        assert service.logger is not None
        assert service.validation_stats['total_records_validated'] == 0
        assert len(service.violations) == 0
        assert len(service.account_metadata) == 0
        assert len(service.symbol_metadata) == 0
    
    def test_validate_valid_single_symbol_accounts(self, service, valid_single_symbol_records):
        """Test validation with valid single symbol per account."""
        result = service.validate_account_symbol_separation(valid_single_symbol_records)
        
        # Should pass validation
        assert result is True
        
        # Should have no error violations
        stats = service.get_validation_summary()
        assert stats['violation_summary']['errors'] == 0
        
        # Should have extracted metadata for 2 accounts and 2 symbols
        assert stats['account_summary']['total_accounts'] == 2
        assert stats['symbol_summary']['total_symbols'] == 2
        
        # Check account metadata
        account_metadata = service.get_account_metadata()
        assert "IPS_TM_10" in account_metadata
        assert "IPS_TM_13" in account_metadata
        
        # IPS_TM_10 should trade only NQ
        ips_tm_10 = account_metadata["IPS_TM_10"]
        assert ips_tm_10.primary_symbol == "NQ"
        assert len(ips_tm_10.symbols_traded) == 1
        assert "NQ" in ips_tm_10.symbols_traded
        
        # IPS_TM_13 should trade only FDAX
        ips_tm_13 = account_metadata["IPS_TM_13"]
        assert ips_tm_13.primary_symbol == "FDAX"
        assert len(ips_tm_13.symbols_traded) == 1
        assert "FDAX" in ips_tm_13.symbols_traded
    
    def test_validate_invalid_multiple_symbols(self, service, invalid_multiple_symbols_records):
        """Test validation with invalid multiple symbols per account."""
        result = service.validate_account_symbol_separation(invalid_multiple_symbols_records)
        
        # Should fail validation
        assert result is False
        
        # Should have error violations
        stats = service.get_validation_summary()
        assert stats['violation_summary']['errors'] > 0
        
        # Should have violation for multiple symbols per account
        violations = service.get_violations("ERROR")
        assert len(violations) > 0
        
        multiple_symbol_violations = [v for v in violations if v.violation_type == "MULTIPLE_SYMBOLS_PER_ACCOUNT"]
        assert len(multiple_symbol_violations) > 0
        
        violation = multiple_symbol_violations[0]
        assert violation.account == "IPS_TM_10"
        assert "multiple symbols" in violation.description.lower()
    
    def test_validate_valid_account_names(self, service, valid_account_name_records):
        """Test validation with valid account names."""
        result = service.validate_account_symbol_separation(valid_account_name_records)
        
        # Should pass validation (valid account name)
        assert result is True
        
        # Should have no error violations
        stats = service.get_validation_summary()
        assert stats['violation_summary']['errors'] == 0
        
        # Should have extracted metadata for 1 account
        assert stats['account_summary']['total_accounts'] == 1
        
        # Check account metadata
        account_metadata = service.get_account_metadata()
        assert "IPS_TM_VALID" in account_metadata
        
        # Account should have valid format
        ips_tm_valid = account_metadata["IPS_TM_VALID"]
        assert ips_tm_valid.account_name == "IPS_TM_VALID"
        assert ips_tm_valid.primary_symbol == "NQ"
    
    def test_validate_empty_records(self, service):
        """Test validation with empty record list."""
        result = service.validate_account_symbol_separation([])
        
        # Should pass validation (no violations possible)
        assert result is True
        
        # Should have no violations
        stats = service.get_validation_summary()
        assert stats['violation_summary']['total_violations'] == 0
    
    def test_extract_account_metadata(self, service, valid_single_symbol_records):
        """Test account metadata extraction."""
        service.validate_account_symbol_separation(valid_single_symbol_records)
        
        account_metadata = service.get_account_metadata("IPS_TM_10")
        assert "IPS_TM_10" in account_metadata
        
        metadata = account_metadata["IPS_TM_10"]
        assert isinstance(metadata, AccountMetadata)
        assert metadata.account_name == "IPS_TM_10"
        assert metadata.primary_symbol == "NQ"
        assert metadata.total_trades == 3
        assert metadata.total_volume == 3
        assert isinstance(metadata.first_trade_date, date)
        assert isinstance(metadata.last_trade_date, date)
    
    def test_extract_symbol_metadata(self, service, valid_single_symbol_records):
        """Test symbol metadata extraction."""
        service.validate_account_symbol_separation(valid_single_symbol_records)
        
        symbol_metadata = service.get_symbol_metadata("NQ")
        assert "NQ" in symbol_metadata
        
        metadata = symbol_metadata["NQ"]
        assert isinstance(metadata, SymbolMetadata)
        assert metadata.symbol == "NQ"
        assert "IPS_TM_10" in metadata.accounts_trading
        assert metadata.total_trades == 3
        assert metadata.total_volume == 3
    
    def test_get_violations_by_severity(self, service, invalid_multiple_symbols_records):
        """Test getting violations filtered by severity."""
        service.validate_account_symbol_separation(invalid_multiple_symbols_records)
        
        # Get all violations
        all_violations = service.get_violations()
        assert len(all_violations) > 0
        
        # Get only errors
        error_violations = service.get_violations("ERROR")
        assert len(error_violations) > 0
        
        # Get only warnings
        warning_violations = service.get_violations("WARNING")
        # May or may not have warnings depending on data
        
        # Verify all error violations have ERROR severity
        for violation in error_violations:
            assert violation.severity == "ERROR"
    
    def test_get_validation_summary(self, service, valid_single_symbol_records):
        """Test getting comprehensive validation summary."""
        service.validate_account_symbol_separation(valid_single_symbol_records)
        
        summary = service.get_validation_summary()
        
        # Check structure
        assert 'validation_stats' in summary
        assert 'account_summary' in summary
        assert 'symbol_summary' in summary
        assert 'violation_summary' in summary
        
        # Check validation stats
        assert summary['validation_stats']['total_records_validated'] == len(valid_single_symbol_records)
        assert summary['validation_stats']['accounts_analyzed'] == 2
        assert summary['validation_stats']['symbols_analyzed'] == 2
        
        # Check account summary
        assert summary['account_summary']['total_accounts'] == 2
        assert "IPS_TM_10" in summary['account_summary']['accounts_list']
        assert "IPS_TM_13" in summary['account_summary']['accounts_list']
        
        # Check symbol summary
        assert summary['symbol_summary']['total_symbols'] == 2
        assert "NQ" in summary['symbol_summary']['symbols_list']
        assert "FDAX" in summary['symbol_summary']['symbols_list']
    
    def test_export_account_metadata_to_dict(self, service, valid_single_symbol_records):
        """Test exporting account metadata to dictionary format."""
        service.validate_account_symbol_separation(valid_single_symbol_records)
        
        exported = service.export_account_metadata_to_dict()
        
        assert isinstance(exported, list)
        assert len(exported) == 2
        
        # Check structure of exported data
        for account_data in exported:
            assert 'account_name' in account_data
            assert 'primary_symbol' in account_data
            assert 'symbols_traded' in account_data
            assert 'first_trade_date' in account_data
            assert 'last_trade_date' in account_data
            assert 'total_trades' in account_data
            assert 'total_volume' in account_data
            assert 'is_active' in account_data
            assert 'validation_warnings' in account_data
            
            # Check data types
            assert isinstance(account_data['symbols_traded'], list)
            assert isinstance(account_data['total_trades'], int)
            assert isinstance(account_data['is_active'], bool)
    
    def test_export_violations_to_dict(self, service, invalid_multiple_symbols_records):
        """Test exporting violations to dictionary format."""
        service.validate_account_symbol_separation(invalid_multiple_symbols_records)
        
        exported = service.export_violations_to_dict()
        
        assert isinstance(exported, list)
        assert len(exported) > 0
        
        # Check structure of exported data
        for violation_data in exported:
            assert 'violation_type' in violation_data
            assert 'account' in violation_data
            assert 'symbol' in violation_data
            assert 'description' in violation_data
            assert 'severity' in violation_data
            assert 'affected_records_count' in violation_data
            
            # Check data types
            assert isinstance(violation_data['affected_records_count'], int)
            assert violation_data['severity'] in ['ERROR', 'WARNING', 'INFO']
    
    def test_generate_validation_report(self, service, valid_single_symbol_records):
        """Test generating human-readable validation report."""
        service.validate_account_symbol_separation(valid_single_symbol_records)
        
        report = service.generate_validation_report()
        
        assert isinstance(report, str)
        assert len(report) > 0
        
        # Check that report contains expected sections
        assert "ACCOUNT AND SYMBOL VALIDATION REPORT" in report
        assert "VALIDATION RESULTS" in report
        assert "ACCOUNT SUMMARY" in report
        
        # Check that report contains key information
        assert "Records Validated:" in report
        assert "Accounts Analyzed:" in report
        assert "Symbols Analyzed:" in report
    
    def test_reset_validation_state(self, service, valid_single_symbol_records):
        """Test resetting validation state."""
        # Run validation to populate state
        service.validate_account_symbol_separation(valid_single_symbol_records)
        
        # Verify state is populated
        assert len(service.account_metadata) > 0
        assert service.validation_stats['total_records_validated'] > 0
        
        # Reset state
        service._reset_validation_state()
        
        # Verify state is reset
        assert len(service.account_metadata) == 0
        assert len(service.symbol_metadata) == 0
        assert len(service.violations) == 0
        assert service.validation_stats['total_records_validated'] == 0
    
    def test_unexpected_symbol_validation(self, service):
        """Test validation with unexpected symbols."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        # Create record with unexpected symbol
        record = SierraChartTradeRecord(
            activity_type="Fills", date_time=base_time, trans_date_time=base_time,
            service_order_id="12345", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
            fill_price=4500.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT123", symbol="ESH24", open_close="Open",  # ES instead of NQ/FDAX
            parent_internal_order_id=None, position_quantity=1,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        result = service.validate_account_symbol_separation([record])
        
        # Should still pass (unexpected symbol is INFO level)
        assert result is True
        
        # Should have info violations
        stats = service.get_validation_summary()
        assert stats['violation_summary']['info'] > 0
        
        # Should have violation for unexpected symbol
        violations = service.get_violations("INFO")
        assert len(violations) > 0
        
        symbol_violations = [v for v in violations if v.violation_type == "UNEXPECTED_SYMBOL"]
        assert len(symbol_violations) > 0
    
    def test_cross_contamination_detection(self, service):
        """Test detection of symbol cross-contamination between accounts."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        records = []
        
        # Both accounts trade NQ (cross-contamination)
        for i, account in enumerate(["IPS_TM_10", "IPS_TM_13"]):
            record = SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time.replace(hour=9+i), trans_date_time=base_time.replace(hour=9+i),
                service_order_id=f"1234{i}", order_type="Market", quantity=1, order_status="Filled",
                trade_account=account, buy_sell="Buy", price=None, price2=None,
                fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id=f"INT12{i}", symbol="NQH24", open_close="Open",
                parent_internal_order_id=None, position_quantity=1,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100000.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            )
            records.append(record)
        
        result = service.validate_account_symbol_separation(records)
        
        # Should pass (cross-contamination is WARNING level)
        assert result is True
        
        # Should have warning violations
        stats = service.get_validation_summary()
        assert stats['violation_summary']['warnings'] > 0
        
        # Should have violation for cross-contamination
        violations = service.get_violations("WARNING")
        cross_contamination_violations = [v for v in violations if v.violation_type == "SYMBOL_CROSS_CONTAMINATION"]
        assert len(cross_contamination_violations) > 0
    
    def test_error_handling(self, service):
        """Test error handling in validation."""
        # Test with None input
        try:
            result = service.validate_account_symbol_separation(None)
            # Should handle gracefully
            assert isinstance(result, bool)
        except (AccountValidationError, TypeError):
            # This is acceptable - service detected an issue
            pass