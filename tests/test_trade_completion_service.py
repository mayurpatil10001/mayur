"""
Unit tests for trade completion analysis service.
"""

import pytest
from datetime import datetime, date
from typing import List

from trading_platform.services.trade_completion_service import (
    TradeCompletionService,
    TradeCompletionAnalysisError,
    PositionState,
    IncompleteTradeInfo
)
from trading_platform.models.sierra_chart import SierraChartTradeRecord


class TestTradeCompletionService:
    """Test cases for trade completion service."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return TradeCompletionService()
    
    @pytest.fixture
    def complete_day_trade_records(self):
        """Create records for a complete day trade (buy open, sell close)."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        # Buy to open
        buy_open = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time,
            trans_date_time=base_time,
            service_order_id="12345",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            price=18500.0,
            price2=None,
            fill_price=18500.25,
            filled_quantity=1,
            note="Buy open",
            order_action_source="Manual",
            internal_order_id="INT123",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=1,  # Position becomes +1
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
        
        # Sell to close
        sell_close = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time.replace(hour=10),
            trans_date_time=base_time.replace(hour=10),
            service_order_id="12346",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Sell",
            price=18520.0,
            price2=None,
            fill_price=18520.50,
            filled_quantity=1,
            note="Sell close",
            order_action_source="Manual",
            internal_order_id="INT124",
            symbol="NQH24",
            open_close="Close",
            parent_internal_order_id="INT123",
            position_quantity=0,  # Position returns to 0
            fill_execution_service_id="EXEC124",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100020.0,
            exchange_order_id="EX124",
            client_order_id="CL124",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        
        return [buy_open, sell_close]
    
    @pytest.fixture
    def incomplete_day_trade_records(self):
        """Create records for an incomplete day trade (buy open only)."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        # Buy to open (no corresponding close)
        buy_open = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time,
            trans_date_time=base_time,
            service_order_id="12347",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            price=18500.0,
            price2=None,
            fill_price=18500.25,
            filled_quantity=1,
            note="Buy open incomplete",
            order_action_source="Manual",
            internal_order_id="INT125",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=1,  # Position stays at +1 (incomplete)
            fill_execution_service_id="EXEC125",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100000.0,
            exchange_order_id="EX125",
            client_order_id="CL125",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        
        return [buy_open]
    
    @pytest.fixture
    def mixed_records(self, complete_day_trade_records, incomplete_day_trade_records):
        """Create mixed records with both complete and incomplete trades."""
        # The complete trade has times 9:30 and 10:30, incomplete trade has 9:30
        # When sorted by time, the order will be: 9:30 (buy open), 9:30 (incomplete buy), 10:30 (sell close)
        # The final position will be 0 (from the sell close at 10:30), so it should be complete
        return complete_day_trade_records + incomplete_day_trade_records
    
    def test_initialization(self, service):
        """Test service initialization."""
        assert service.logger is not None
        assert service.analysis_stats['total_records_analyzed'] == 0
        assert len(service.incomplete_trades) == 0
    
    def test_analyze_complete_day_trade(self, service, complete_day_trade_records):
        """Test analysis of complete day trade."""
        result = service.analyze_and_clean_trades(complete_day_trade_records)
        
        # All records should be kept (complete trade)
        assert len(result) == 2
        assert result == complete_day_trade_records
        
        # Statistics should reflect complete position
        stats = service.get_analysis_statistics()
        assert stats['total_records_analyzed'] == 2
        assert stats['complete_positions'] == 1
        assert stats['incomplete_positions'] == 0
        assert stats['records_removed'] == 0
    
    def test_analyze_incomplete_day_trade(self, service, incomplete_day_trade_records):
        """Test analysis of incomplete day trade."""
        result = service.analyze_and_clean_trades(incomplete_day_trade_records)
        
        # All records should be removed (incomplete trade)
        assert len(result) == 0
        
        # Statistics should reflect incomplete position
        stats = service.get_analysis_statistics()
        assert stats['total_records_analyzed'] == 1
        assert stats['complete_positions'] == 0
        assert stats['incomplete_positions'] == 1
        assert stats['records_removed'] == 1
    
    def test_analyze_mixed_trades(self, service, mixed_records):
        """Test analysis of mixed complete and incomplete trades."""
        result = service.analyze_and_clean_trades(mixed_records)
        
        # Since all records are from same account/symbol/date, and when sorted by time,
        # the final position is 0 (from the sell close at 10:30), the position is complete
        # All records should be kept
        assert len(result) == 3
        
        # Statistics should reflect complete position (all records treated as one group)
        stats = service.get_analysis_statistics()
        assert stats['total_records_analyzed'] == 3
        assert stats['complete_positions'] == 1
        assert stats['incomplete_positions'] == 0
        assert stats['records_removed'] == 0
    
    def test_analyze_empty_records(self, service):
        """Test analysis with empty record list."""
        result = service.analyze_and_clean_trades([])
        
        assert len(result) == 0
        assert service.analysis_stats['total_records_analyzed'] == 0
    
    def test_group_records_by_account_symbol_date(self, service, mixed_records):
        """Test grouping records by account, symbol, and date."""
        grouped = service._group_records_by_account_symbol_date(mixed_records)
        
        # Should have one group (same account, symbol, date)
        assert len(grouped) == 1
        
        key = ("IPS_TM_10", "NQ", date(2024, 1, 15))
        assert key in grouped
        assert len(grouped[key]) == 3
        
        # Records should be sorted by datetime
        group_records = grouped[key]
        for i in range(1, len(group_records)):
            assert group_records[i-1].date_time <= group_records[i].date_time
    
    def test_calculate_expected_position_buy_open(self, service):
        """Test expected position calculation for buy to open."""
        record = SierraChartTradeRecord(
            activity_type="Fills", date_time=datetime.now(), trans_date_time=datetime.now(),
            service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
            fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT123", symbol="NQH24", open_close="Open",
            parent_internal_order_id=None, position_quantity=1,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        # Starting from 0, buy 1 to open should result in +1
        expected = service._calculate_expected_position(0, record)
        assert expected == 1
    
    def test_calculate_expected_position_sell_close(self, service):
        """Test expected position calculation for sell to close."""
        record = SierraChartTradeRecord(
            activity_type="Fills", date_time=datetime.now(), trans_date_time=datetime.now(),
            service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Sell", price=None, price2=None,
            fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT123", symbol="NQH24", open_close="Close",
            parent_internal_order_id=None, position_quantity=0,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        # Starting from +1, sell 1 to close should result in 0
        expected = service._calculate_expected_position(1, record)
        assert expected == 0
    
    def test_calculate_expected_position_sell_open(self, service):
        """Test expected position calculation for sell to open (short)."""
        record = SierraChartTradeRecord(
            activity_type="Fills", date_time=datetime.now(), trans_date_time=datetime.now(),
            service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Sell", price=None, price2=None,
            fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT123", symbol="NQH24", open_close="Open",
            parent_internal_order_id=None, position_quantity=-1,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        # Starting from 0, sell 1 to open should result in -1
        expected = service._calculate_expected_position(0, record)
        assert expected == -1
    
    def test_calculate_expected_position_buy_close_short(self, service):
        """Test expected position calculation for buy to close short position."""
        record = SierraChartTradeRecord(
            activity_type="Fills", date_time=datetime.now(), trans_date_time=datetime.now(),
            service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
            fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT123", symbol="NQH24", open_close="Close",
            parent_internal_order_id=None, position_quantity=0,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        # Starting from -1, buy 1 to close should result in 0
        expected = service._calculate_expected_position(-1, record)
        assert expected == 0
    
    def test_generate_record_id(self, service, complete_day_trade_records):
        """Test record ID generation."""
        record = complete_day_trade_records[0]
        record_id = service._generate_record_id(record)
        
        expected_id = f"{record.trade_account}_{record.internal_order_id}_{record.service_order_id}"
        assert record_id == expected_id
        
        # Different records should have different IDs
        record2 = complete_day_trade_records[1]
        record_id2 = service._generate_record_id(record2)
        assert record_id != record_id2
    
    def test_validate_position_consistency_valid(self, service, complete_day_trade_records):
        """Test position consistency validation with valid records."""
        warnings = service.validate_position_consistency(complete_day_trade_records)
        
        # Should have no warnings for consistent positions
        assert len(warnings) == 0
    
    def test_validate_position_consistency_invalid(self, service):
        """Test position consistency validation with invalid records."""
        # Create records with inconsistent position quantities
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        record1 = SierraChartTradeRecord(
            activity_type="Fills", date_time=base_time, trans_date_time=base_time,
            service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
            fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT123", symbol="NQH24", open_close="Open",
            parent_internal_order_id=None, position_quantity=2,  # Should be 1
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        warnings = service.validate_position_consistency([record1])
        
        # Should have warnings for inconsistent positions
        assert len(warnings) > 0
        assert "Position inconsistency" in warnings[0]
    
    def test_get_incomplete_trades_summary_empty(self, service):
        """Test incomplete trades summary with no incomplete trades."""
        summary = service.get_incomplete_trades_summary()
        
        assert summary['total_incomplete_positions'] == 0
        assert len(summary['accounts_affected']) == 0
        assert len(summary['symbols_affected']) == 0
        assert len(summary['dates_affected']) == 0
        assert summary['total_records_affected'] == 0
    
    def test_get_incomplete_trades_summary_with_data(self, service, incomplete_day_trade_records):
        """Test incomplete trades summary with incomplete trades."""
        # Analyze incomplete trades to populate summary
        service.analyze_and_clean_trades(incomplete_day_trade_records)
        
        summary = service.get_incomplete_trades_summary()
        
        assert summary['total_incomplete_positions'] == 1
        assert "IPS_TM_10" in summary['accounts_affected']
        assert "NQ" in summary['symbols_affected']
        assert "2024-01-15" in summary['dates_affected']
        assert summary['total_records_affected'] == 1
        assert len(summary['incomplete_details']) == 1
    
    def test_get_analysis_statistics(self, service, mixed_records):
        """Test getting comprehensive analysis statistics."""
        service.analyze_and_clean_trades(mixed_records)
        
        stats = service.get_analysis_statistics()
        
        # Should include all analysis stats
        assert 'total_records_analyzed' in stats
        assert 'complete_positions' in stats
        assert 'incomplete_positions' in stats
        assert 'records_removed' in stats
        assert 'accounts_processed' in stats
        assert 'symbols_processed' in stats
        assert 'trading_days_analyzed' in stats
        
        # Should include incomplete trades summary
        assert 'incomplete_trades_summary' in stats
    
    def test_analyze_position_flow(self, service, complete_day_trade_records):
        """Test position flow analysis."""
        flow_analysis = service.analyze_position_flow(complete_day_trade_records)
        
        # Should have one account/symbol combination
        assert len(flow_analysis) == 1
        
        key = "IPS_TM_10_NQ"
        assert key in flow_analysis
        
        analysis = flow_analysis[key]
        assert analysis['account'] == "IPS_TM_10"
        assert analysis['symbol'] == "NQ"
        assert analysis['total_records'] == 2
        
        # Should have daily analysis
        assert 'daily_analysis' in analysis
        daily_data = analysis['daily_analysis']
        
        # Should have one day
        assert len(daily_data) == 1
        
        day_key = "2024-01-15"
        assert day_key in daily_data
        
        day_analysis = daily_data[day_key]
        assert day_analysis['start_position'] == 0
        assert day_analysis['end_position'] == 0
        assert day_analysis['is_complete'] is True
        assert day_analysis['total_fills'] == 2
    
    def test_analyze_position_flow_empty(self, service):
        """Test position flow analysis with empty records."""
        flow_analysis = service.analyze_position_flow([])
        
        assert len(flow_analysis) == 0
    
    def test_detect_orphaned_positions_none(self, service, complete_day_trade_records):
        """Test orphaned position detection with complete trades."""
        orphaned = service.detect_orphaned_positions(complete_day_trade_records)
        
        # Complete trades should have no orphaned positions
        assert len(orphaned) == 0
    
    def test_detect_orphaned_positions_found(self, service, incomplete_day_trade_records):
        """Test orphaned position detection with incomplete trades."""
        orphaned = service.detect_orphaned_positions(incomplete_day_trade_records)
        
        # Incomplete trade should be detected as orphaned
        assert len(orphaned) == 1
        
        orphan = orphaned[0]
        assert orphan['account'] == "IPS_TM_10"
        assert orphan['symbol'] == "NQ"
        assert orphan['date'] == "2024-01-15"
        assert orphan['internal_order_id'] == "multiple"  # Updated logic uses 'multiple'
        assert orphan['remaining_quantity'] == 1
        assert len(orphan['records']) == 1
    
    def test_multiple_accounts_and_symbols(self, service):
        """Test analysis with multiple accounts and symbols."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        # Complete trade for account 1, NQ
        records = [
            SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time, trans_date_time=base_time,
                service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
                trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
                fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id="INT123", symbol="NQH24", open_close="Open",
                parent_internal_order_id=None, position_quantity=1,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100000.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            ),
            SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time.replace(hour=10), trans_date_time=base_time.replace(hour=10),
                service_order_id="124", order_type="Market", quantity=1, order_status="Filled",
                trade_account="IPS_TM_10", buy_sell="Sell", price=None, price2=None,
                fill_price=18520.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id="INT124", symbol="NQH24", open_close="Close",
                parent_internal_order_id="INT123", position_quantity=0,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100020.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            ),
            # Incomplete trade for account 2, FDAX
            SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time, trans_date_time=base_time,
                service_order_id="125", order_type="Market", quantity=1, order_status="Filled",
                trade_account="IPS_TM_13", buy_sell="Buy", price=None, price2=None,
                fill_price=17500.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id="INT125", symbol="FDAXM24", open_close="Open",
                parent_internal_order_id=None, position_quantity=1,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100000.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            )
        ]
        
        result = service.analyze_and_clean_trades(records)
        
        # Only complete trade should remain
        assert len(result) == 2
        
        stats = service.get_analysis_statistics()
        assert stats['accounts_processed'] == 2
        assert stats['symbols_processed'] == 2
        assert stats['complete_positions'] == 1
        assert stats['incomplete_positions'] == 1
    
    def test_reset_analysis_stats(self, service, incomplete_day_trade_records):
        """Test resetting analysis statistics."""
        # Run analysis to populate stats
        service.analyze_and_clean_trades(incomplete_day_trade_records)
        
        # Verify stats are populated
        assert service.analysis_stats['total_records_analyzed'] > 0
        assert len(service.incomplete_trades) > 0
        
        # Reset stats
        service._reset_analysis_stats()
        
        # Verify stats are reset
        assert service.analysis_stats['total_records_analyzed'] == 0
        assert len(service.incomplete_trades) == 0
    
    def test_error_handling(self, service):
        """Test error handling in analysis."""
        # Test with None input to trigger error handling
        try:
            result = service.analyze_and_clean_trades(None)
            # Should return empty list or raise error
            assert isinstance(result, list)
        except (TradeCompletionAnalysisError, TypeError):
            # This is acceptable - service detected an issue
            pass
        
        # Test with empty list (should work fine)
        result = service.analyze_and_clean_trades([])
        assert isinstance(result, list)
        assert len(result) == 0