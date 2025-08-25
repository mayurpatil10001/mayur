"""
Unit tests for processed trade generation service.
"""

import pytest
from datetime import datetime, date
from typing import List

from trading_platform.services.processed_trade_service import (
    ProcessedTradeService,
    ProcessedTradeGenerationError,
    TradeMatchingState
)
from trading_platform.models.sierra_chart import SierraChartTradeRecord
from trading_platform.models.trading import ProcessedTrade


class TestProcessedTradeService:
    """Test cases for processed trade service."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return ProcessedTradeService()
    
    @pytest.fixture
    def complete_round_trip_fills(self):
        """Create fills for a complete round-trip trade."""
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
            parent_internal_order_id="INT123",  # Links to opening fill
            position_quantity=0,
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
    def short_round_trip_fills(self):
        """Create fills for a short round-trip trade."""
        base_time = datetime(2024, 1, 15, 14, 30, 0)
        
        # Sell to open (short)
        sell_open = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time,
            trans_date_time=base_time,
            service_order_id="12347",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Sell",
            price=18500.0,
            price2=None,
            fill_price=18500.75,
            filled_quantity=1,
            note="Sell open short",
            order_action_source="Manual",
            internal_order_id="INT125",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=-1,
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
        
        # Buy to close (cover short)
        buy_close = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time.replace(hour=15),
            trans_date_time=base_time.replace(hour=15),
            service_order_id="12348",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            price=18480.0,
            price2=None,
            fill_price=18480.25,
            filled_quantity=1,
            note="Buy close short",
            order_action_source="Manual",
            internal_order_id="INT126",
            symbol="NQH24",
            open_close="Close",
            parent_internal_order_id="INT125",  # Links to opening fill
            position_quantity=0,
            fill_execution_service_id="EXEC126",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100020.0,
            exchange_order_id="EX126",
            client_order_id="CL126",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        
        return [sell_open, buy_close]
    
    @pytest.fixture
    def unmatched_fills(self):
        """Create fills that don't have matching pairs."""
        base_time = datetime(2024, 1, 15, 11, 30, 0)
        
        # Buy to open without matching close
        buy_open = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time,
            trans_date_time=base_time,
            service_order_id="12349",
            order_type="Market",
            quantity=1,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            price=18500.0,
            price2=None,
            fill_price=18500.25,
            filled_quantity=1,
            note="Unmatched buy",
            order_action_source="Manual",
            internal_order_id="INT127",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=1,
            fill_execution_service_id="EXEC127",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100000.0,
            exchange_order_id="EX127",
            client_order_id="CL127",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        
        return [buy_open]
    
    @pytest.fixture
    def multiple_fills_same_position(self):
        """Create multiple fills for the same position (partial fills)."""
        base_time = datetime(2024, 1, 15, 12, 30, 0)
        
        fills = []
        
        # First partial fill - buy 2 contracts
        fill1 = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time,
            trans_date_time=base_time,
            service_order_id="12350",
            order_type="Market",
            quantity=3,
            order_status="Partially Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            price=18500.0,
            price2=None,
            fill_price=18500.25,
            filled_quantity=2,
            note="Partial fill 1",
            order_action_source="Manual",
            internal_order_id="INT128",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=2,
            fill_execution_service_id="EXEC128",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100000.0,
            exchange_order_id="EX128",
            client_order_id="CL128",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        fills.append(fill1)
        
        # Second partial fill - buy 1 more contract
        fill2 = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time.replace(minute=31),
            trans_date_time=base_time.replace(minute=31),
            service_order_id="12350",  # Same order
            order_type="Market",
            quantity=3,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Buy",
            price=18500.0,
            price2=None,
            fill_price=18500.50,
            filled_quantity=1,
            note="Partial fill 2",
            order_action_source="Manual",
            internal_order_id="INT128",  # Same internal order ID
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=3,
            fill_execution_service_id="EXEC129",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100000.0,
            exchange_order_id="EX128",
            client_order_id="CL128",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        fills.append(fill2)
        
        # Closing fill - sell all 3 contracts
        close_fill = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=base_time.replace(hour=13),
            trans_date_time=base_time.replace(hour=13),
            service_order_id="12351",
            order_type="Market",
            quantity=3,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Sell",
            price=18520.0,
            price2=None,
            fill_price=18520.25,
            filled_quantity=3,
            note="Close all",
            order_action_source="Manual",
            internal_order_id="INT129",
            symbol="NQH24",
            open_close="Close",
            parent_internal_order_id="INT128",  # Links to opening fills
            position_quantity=0,
            fill_execution_service_id="EXEC130",
            high_during_position=18600.0,
            low_during_position=18400.0,
            account_balance=100060.0,
            exchange_order_id="EX129",
            client_order_id="CL129",
            time_in_force="DAY",
            username="trader1",
            is_automated="N"
        )
        fills.append(close_fill)
        
        return fills
    
    def test_initialization(self, service):
        """Test service initialization."""
        assert service.logger is not None
        assert service.generation_stats['total_fills_processed'] == 0
        assert len(service.processed_trades) == 0
        assert len(service.unmatched_fills) == 0
    
    def test_generate_complete_long_trade(self, service, complete_round_trip_fills):
        """Test generating a complete long trade."""
        trades = service.generate_processed_trades(complete_round_trip_fills)
        
        assert len(trades) == 1
        
        trade = trades[0]
        assert isinstance(trade, ProcessedTrade)
        assert trade.account_name == "IPS_TM_10"
        assert trade.symbol == "NQ"
        assert trade.side == "LONG"
        assert trade.quantity == 1
        assert trade.entry_price == 18500.25
        assert trade.exit_price == 18520.50
        # P&L should be gross P&L minus commission
        gross_pnl = (18520.50 - 18500.25) * 1
        expected_commission = 2 * 1 * 2.50  # 2 fills * 1 quantity * $2.50 per contract
        expected_net_pnl = gross_pnl - expected_commission
        assert trade.profit_loss == expected_net_pnl
        assert trade.duration_minutes == 60  # 1 hour difference
        assert trade.hour_of_day == 9  # Entry time hour
        assert trade.day_of_week == 0  # Monday (2024-01-15)
        
        # Check statistics
        stats = service.get_generation_statistics()
        assert stats['total_fills_processed'] == 2
        assert stats['complete_trades_generated'] == 1
        assert stats['unmatched_fills'] == 0
    
    def test_generate_complete_short_trade(self, service, short_round_trip_fills):
        """Test generating a complete short trade."""
        trades = service.generate_processed_trades(short_round_trip_fills)
        
        assert len(trades) == 1
        
        trade = trades[0]
        assert trade.side == "SHORT"
        assert trade.entry_price == 18500.75
        assert trade.exit_price == 18480.25
        # P&L should be gross P&L minus commission
        gross_pnl = (18500.75 - 18480.25) * 1
        expected_commission = 2 * 1 * 2.50  # 2 fills * 1 quantity * $2.50 per contract
        expected_net_pnl = gross_pnl - expected_commission
        assert trade.profit_loss == expected_net_pnl
        assert trade.profit_loss > 0  # Should still be profitable after commission
    
    def test_generate_with_unmatched_fills(self, service, unmatched_fills):
        """Test generation with unmatched fills."""
        trades = service.generate_processed_trades(unmatched_fills)
        
        assert len(trades) == 0  # No complete trades
        
        unmatched = service.get_unmatched_fills()
        assert len(unmatched) == 1
        assert unmatched[0].internal_order_id == "INT127"
        
        # Check statistics
        stats = service.get_generation_statistics()
        assert stats['complete_trades_generated'] == 0
        assert stats['unmatched_fills'] == 1
    
    def test_generate_with_partial_fills(self, service, multiple_fills_same_position):
        """Test generation with multiple partial fills for same position."""
        trades = service.generate_processed_trades(multiple_fills_same_position)
        
        assert len(trades) == 1
        
        trade = trades[0]
        assert trade.quantity == 3  # Total quantity from partial fills
        
        # Weighted average entry price: (2 * 18500.25 + 1 * 18500.50) / 3
        expected_entry_price = (2 * 18500.25 + 1 * 18500.50) / 3
        assert abs(trade.entry_price - expected_entry_price) < 0.01
        
        assert trade.exit_price == 18520.25
        assert trade.side == "LONG"
    
    def test_generate_empty_fills(self, service):
        """Test generation with empty fills list."""
        trades = service.generate_processed_trades([])
        
        assert len(trades) == 0
        assert len(service.get_unmatched_fills()) == 0
    
    def test_group_fills_by_account_symbol_date(self, service, complete_round_trip_fills):
        """Test grouping fills by account, symbol, and date."""
        grouped = service._group_fills_by_account_symbol_date(complete_round_trip_fills)
        
        assert len(grouped) == 1
        
        key = ("IPS_TM_10", "NQ", date(2024, 1, 15))
        assert key in grouped
        assert len(grouped[key]) == 2
        
        # Should be sorted by datetime
        fills = grouped[key]
        assert fills[0].date_time <= fills[1].date_time
    
    def test_calculate_commission(self, service, complete_round_trip_fills):
        """Test commission calculation."""
        commission = service._calculate_commission(complete_round_trip_fills)
        
        # 2 fills * 1 quantity each * $2.50 per contract = $5.00
        expected_commission = 2 * 1 * 2.50
        assert commission == expected_commission
    
    def test_analyze_trade_patterns_empty(self, service):
        """Test trade pattern analysis with no trades."""
        patterns = service.analyze_trade_patterns()
        
        assert patterns == {}
    
    def test_analyze_trade_patterns_with_trades(self, service, complete_round_trip_fills, short_round_trip_fills):
        """Test trade pattern analysis with trades."""
        # Generate trades from both fixtures
        all_fills = complete_round_trip_fills + short_round_trip_fills
        service.generate_processed_trades(all_fills)
        
        patterns = service.analyze_trade_patterns()
        
        assert 'overall_stats' in patterns
        assert 'hourly_analysis' in patterns
        assert 'daily_analysis' in patterns
        assert 'side_analysis' in patterns
        assert 'duration_analysis' in patterns
        
        # Check overall stats
        overall = patterns['overall_stats']
        assert overall['total_trades'] == 2
        assert overall['winning_trades'] >= 0
        assert overall['losing_trades'] >= 0
        assert overall['win_rate'] >= 0.0
        
        # Check side analysis
        side_analysis = patterns['side_analysis']
        assert 'LONG' in side_analysis
        assert 'SHORT' in side_analysis
    
    def test_export_trades_to_dict(self, service, complete_round_trip_fills):
        """Test exporting trades to dictionary format."""
        service.generate_processed_trades(complete_round_trip_fills)
        
        exported = service.export_trades_to_dict()
        
        assert len(exported) == 1
        
        trade_dict = exported[0]
        assert 'trade_id' in trade_dict
        assert 'account_name' in trade_dict
        assert 'symbol' in trade_dict
        assert 'entry_time' in trade_dict
        assert 'exit_time' in trade_dict
        assert 'entry_price' in trade_dict
        assert 'exit_price' in trade_dict
        assert 'quantity' in trade_dict
        assert 'side' in trade_dict
        assert 'profit_loss' in trade_dict
        assert 'commission' in trade_dict
        assert 'duration_minutes' in trade_dict
        assert 'hour_of_day' in trade_dict
        assert 'day_of_week' in trade_dict
        
        # Check data types
        assert isinstance(trade_dict['quantity'], int)
        assert isinstance(trade_dict['profit_loss'], float)
        assert isinstance(trade_dict['hour_of_day'], int)
        assert isinstance(trade_dict['day_of_week'], int)
    
    def test_reset_generation_state(self, service, complete_round_trip_fills):
        """Test resetting generation state."""
        # Generate some trades
        service.generate_processed_trades(complete_round_trip_fills)
        
        # Verify state is populated
        assert len(service.processed_trades) > 0
        assert service.generation_stats['total_fills_processed'] > 0
        
        # Reset state
        service._reset_generation_state()
        
        # Verify state is reset
        assert len(service.processed_trades) == 0
        assert len(service.unmatched_fills) == 0
        assert service.generation_stats['total_fills_processed'] == 0
    
    def test_multiple_accounts_and_symbols(self, service):
        """Test processing fills from multiple accounts and symbols."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        fills = []
        
        # Account 1, NQ trade
        fills.extend([
            SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time, trans_date_time=base_time,
                service_order_id="123", order_type="Market", quantity=1, order_status="Filled",
                trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
                fill_price=18500.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id="INT1", symbol="NQH24", open_close="Open",
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
                internal_order_id="INT2", symbol="NQH24", open_close="Close",
                parent_internal_order_id="INT1", position_quantity=0,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100020.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            )
        ])
        
        # Account 2, FDAX trade
        fills.extend([
            SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time, trans_date_time=base_time,
                service_order_id="125", order_type="Market", quantity=1, order_status="Filled",
                trade_account="IPS_TM_13", buy_sell="Buy", price=None, price2=None,
                fill_price=17500.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id="INT3", symbol="FDAXM24", open_close="Open",
                parent_internal_order_id=None, position_quantity=1,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100000.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            ),
            SierraChartTradeRecord(
                activity_type="Fills", date_time=base_time.replace(hour=11), trans_date_time=base_time.replace(hour=11),
                service_order_id="126", order_type="Market", quantity=1, order_status="Filled",
                trade_account="IPS_TM_13", buy_sell="Sell", price=None, price2=None,
                fill_price=17520.0, filled_quantity=1, note="", order_action_source="",
                internal_order_id="INT4", symbol="FDAXM24", open_close="Close",
                parent_internal_order_id="INT3", position_quantity=0,
                fill_execution_service_id="", high_during_position=None,
                low_during_position=None, account_balance=100020.0,
                exchange_order_id="", client_order_id="", time_in_force="",
                username="", is_automated="N"
            )
        ])
        
        trades = service.generate_processed_trades(fills)
        
        assert len(trades) == 2  # One trade per account
        
        # Check that we have trades for both accounts and symbols
        accounts = {t.account_name for t in trades}
        symbols = {t.symbol for t in trades}
        
        assert "IPS_TM_10" in accounts
        assert "IPS_TM_13" in accounts
        assert "NQ" in symbols
        assert "FDAX" in symbols
        
        # Check statistics
        stats = service.get_generation_statistics()
        assert stats['accounts_processed'] == 2
        assert stats['symbols_processed'] == 2
    
    def test_quantity_mismatch_handling(self, service):
        """Test handling of quantity mismatches between opening and closing fills."""
        base_time = datetime(2024, 1, 15, 9, 30, 0)
        
        # Opening fill - buy 2 contracts
        buy_open = SierraChartTradeRecord(
            activity_type="Fills", date_time=base_time, trans_date_time=base_time,
            service_order_id="123", order_type="Market", quantity=2, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Buy", price=None, price2=None,
            fill_price=18500.0, filled_quantity=2, note="", order_action_source="",
            internal_order_id="INT1", symbol="NQH24", open_close="Open",
            parent_internal_order_id=None, position_quantity=2,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100000.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        # Closing fill - sell only 1 contract (mismatch)
        sell_close = SierraChartTradeRecord(
            activity_type="Fills", date_time=base_time.replace(hour=10), trans_date_time=base_time.replace(hour=10),
            service_order_id="124", order_type="Market", quantity=1, order_status="Filled",
            trade_account="IPS_TM_10", buy_sell="Sell", price=None, price2=None,
            fill_price=18520.0, filled_quantity=1, note="", order_action_source="",
            internal_order_id="INT2", symbol="NQH24", open_close="Close",
            parent_internal_order_id="INT1", position_quantity=1,
            fill_execution_service_id="", high_during_position=None,
            low_during_position=None, account_balance=100020.0,
            exchange_order_id="", client_order_id="", time_in_force="",
            username="", is_automated="N"
        )
        
        trades = service.generate_processed_trades([buy_open, sell_close])
        
        # Should not create a trade due to quantity mismatch
        assert len(trades) == 0
        
        # Both fills should be unmatched
        unmatched = service.get_unmatched_fills()
        assert len(unmatched) == 2  # Both opening and closing fills become unmatched
    
    def test_error_handling(self, service):
        """Test error handling in trade generation."""
        # Test with None input
        try:
            result = service.generate_processed_trades(None)
            # Should handle gracefully
            assert isinstance(result, list)
        except (ProcessedTradeGenerationError, TypeError):
            # This is acceptable - service detected an issue
            pass
    
    def test_trade_matching_state(self):
        """Test TradeMatchingState dataclass."""
        state = TradeMatchingState(
            account="IPS_TM_10",
            symbol="NQ",
            date=date(2024, 1, 15),
            open_positions={},
            completed_trades=[],
            unmatched_fills=[],
            position_quantity=0
        )
        
        assert state.account == "IPS_TM_10"
        assert state.symbol == "NQ"
        assert state.date == date(2024, 1, 15)
        assert len(state.open_positions) == 0
        assert len(state.completed_trades) == 0
        assert len(state.unmatched_fills) == 0
        assert state.position_quantity == 0