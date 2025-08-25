"""
Tests for comprehensive validation scenarios.
"""

import pytest
from datetime import datetime
from trading_platform.models.sierra_chart import SierraChartTradeRecord
from trading_platform.models.trading import ProcessedTrade, Account, PerformanceMetrics
from trading_platform.utils.validators import TradingDataValidator, ValidationError


class TestDataIntegrityValidation:
    """Test data integrity validation scenarios."""
    
    def test_sierra_chart_record_business_rules(self):
        """Test SierraChart record business rule validation."""
        # Test quantity consistency
        with pytest.raises(ValidationError):
            SierraChartTradeRecord(
                activity_type="Fills",
                date_time=datetime(2024, 3, 5, 16, 5, 58),
                trans_date_time=datetime(2024, 3, 5, 16, 5, 59),
                service_order_id="8951508",
                order_type="Market",
                quantity=5,  # Different from filled_quantity
                order_status="Filled",
                trade_account="IPS_TM_10",
                buy_sell="Sell",
                price=None,
                price2=None,
                fill_price=17943.5,
                filled_quantity=3,  # Different from quantity
                note="",
                order_action_source="",
                internal_order_id="758655",
                symbol="NQH24",
                open_close="Open",
                parent_internal_order_id=None,
                position_quantity=-3,
                fill_execution_service_id="",
                high_during_position=None,
                low_during_position=None,
                account_balance=0.0,
                exchange_order_id="",
                client_order_id="",
                time_in_force="",
                username="",
                is_automated="Y"
            )
    
    def test_processed_trade_pnl_validation(self):
        """Test processed trade P&L calculation validation."""
        entry_time = datetime(2024, 3, 5, 16, 5, 58)
        exit_time = datetime(2024, 3, 5, 16, 7, 42)
        duration = int((exit_time - entry_time).total_seconds() / 60)
        
        # Test incorrect P&L for LONG trade
        with pytest.raises(ValidationError, match="P&L mismatch"):
            ProcessedTrade(
                trade_id="IPS_TM_10_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=100.0,
                exit_price=110.0,
                quantity=2,
                side="LONG",
                profit_loss=15.0,  # Should be (110-100)*2 = 20.0
                commission=0.0,
                duration_minutes=duration,
                hour_of_day=16,
                day_of_week=1,
                entry_order_id="758655",
                exit_order_id="758661"
            )
    
    def test_processed_trade_duration_validation(self):
        """Test processed trade duration validation."""
        entry_time = datetime(2024, 3, 5, 16, 5, 58)
        exit_time = datetime(2024, 3, 5, 16, 7, 42)  # 1 minute 44 seconds = ~1 minute
        
        # Test incorrect duration
        with pytest.raises(ValidationError, match="Duration mismatch"):
            ProcessedTrade(
                trade_id="IPS_TM_10_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=100.0,
                exit_price=110.0,
                quantity=2,
                side="LONG",
                profit_loss=20.0,
                commission=0.0,
                duration_minutes=60,  # Incorrect duration (should be ~1)
                hour_of_day=16,
                day_of_week=1,
                entry_order_id="758655",
                exit_order_id="758661"
            )
    
    def test_account_validation_edge_cases(self):
        """Test account validation edge cases."""
        # Test negative total trades
        with pytest.raises(ValidationError):
            Account(
                name="IPS_TM_10",
                symbol="NQ",
                total_trades=-1,  # Invalid negative trades
                first_trade_date=datetime(2024, 1, 1),
                last_trade_date=datetime(2024, 3, 5),
                is_active=True
            )
    
    def test_performance_metrics_consistency(self):
        """Test performance metrics consistency validation."""
        # Test win rate calculation consistency
        with pytest.raises(ValidationError, match="Win rate mismatch"):
            PerformanceMetrics(
                account_name="IPS_TM_10",
                symbol="NQ",
                period_start=datetime(2024, 1, 1),
                period_end=datetime(2024, 3, 5),
                total_return=1000.0,
                total_trades=100,
                winning_trades=60,
                losing_trades=40,
                win_rate=0.7,  # Should be 0.6 (60/100)
                average_win=25.0,
                average_loss=-15.0,
                profit_factor=1.67,
                max_drawdown=-200.0,
                sharpe_ratio=1.5,
                volatility=0.15,
                largest_win=100.0,
                largest_loss=-50.0
            )
        
        # Test positive max drawdown (should be negative)
        with pytest.raises(ValidationError, match="Max drawdown should be negative or zero"):
            PerformanceMetrics(
                account_name="IPS_TM_10",
                symbol="NQ",
                period_start=datetime(2024, 1, 1),
                period_end=datetime(2024, 3, 5),
                total_return=1000.0,
                total_trades=100,
                winning_trades=60,
                losing_trades=40,
                win_rate=0.6,
                average_win=25.0,
                average_loss=-15.0,
                profit_factor=1.67,
                max_drawdown=200.0,  # Should be negative
                sharpe_ratio=1.5,
                volatility=0.15,
                largest_win=100.0,
                largest_loss=-50.0
            )


class TestValidatorEdgeCases:
    """Test validator edge cases and boundary conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = TradingDataValidator()
    
    def test_price_validation_edge_cases(self):
        """Test price validation edge cases."""
        # Test zero price (should be valid)
        result = self.validator.validate_price(0.0, "TestPrice", allow_none=False)
        assert result == 0.0
        
        # Test very small price
        result = self.validator.validate_price(0.0001, "TestPrice", allow_none=False)
        assert result == 0.0001
        
        # Test empty string with allow_none=True
        result = self.validator.validate_price("", "TestPrice", allow_none=True)
        assert result is None
        
        # Test empty string with allow_none=False
        with pytest.raises(ValidationError):
            self.validator.validate_price("", "TestPrice", allow_none=False)
    
    def test_string_validation_edge_cases(self):
        """Test string validation edge cases."""
        # Test whitespace-only string
        with pytest.raises(ValidationError):
            self.validator.validate_required_string("   ", "TestField")
        
        # Test exactly at max length
        result = self.validator.validate_required_string("12345", "TestField", 5)
        assert result == "12345"
        
        # Test one character over max length
        with pytest.raises(ValidationError):
            self.validator.validate_required_string("123456", "TestField", 5)
    
    def test_integer_validation_edge_cases(self):
        """Test integer validation edge cases."""
        # Test string representation of integer
        result = self.validator.validate_positive_integer("5", "TestField")
        assert result == 5
        
        # Test float that's actually an integer
        result = self.validator.validate_positive_integer(5.0, "TestField")
        assert result == 5
        
        # Test float with decimal part
        with pytest.raises(ValidationError):
            self.validator.validate_positive_integer(5.5, "TestField")
    
    def test_datetime_validation_edge_cases(self):
        """Test datetime validation edge cases."""
        # Test ISO format string with timezone
        dt_str = "2024-03-05T16:05:58+00:00"
        result = self.validator.validate_datetime(dt_str, "TestField")
        assert isinstance(result, datetime)
        
        # Test ISO format string with Z timezone
        dt_str = "2024-03-05T16:05:58Z"
        result = self.validator.validate_datetime(dt_str, "TestField")
        assert isinstance(result, datetime)
        
        # Test invalid datetime string
        with pytest.raises(ValidationError):
            self.validator.validate_datetime("not-a-date", "TestField")
    
    def test_symbol_validation_patterns(self):
        """Test symbol validation patterns."""
        # Test valid symbols
        valid_symbols = ["NQH24", "FDAXM24", "ESU24", "RTYM24"]
        for symbol in valid_symbols:
            result = self.validator.validate_symbol(symbol)
            assert result == symbol
        
        # Test invalid symbols
        invalid_symbols = ["NQ", "FDAX24", "ES2024", "RTY", ""]
        for symbol in invalid_symbols:
            with pytest.raises(ValidationError):
                self.validator.validate_symbol(symbol)
    
    def test_account_validation_patterns(self):
        """Test account validation patterns."""
        # Test valid account patterns
        valid_accounts = ["IPS_TM_10", "IPS_TS_13", "IPS_TM_ABC", "IPS_TM_123"]
        for account in valid_accounts:
            result = self.validator.validate_trade_account(account)
            assert result == account
        
        # Test invalid account patterns
        invalid_accounts = ["IPS_10", "TM_10", "IPS_XX_10", "INVALID", ""]
        for account in invalid_accounts:
            with pytest.raises(ValidationError):
                self.validator.validate_trade_account(account)


class TestBusinessRuleValidation:
    """Test business rule validation scenarios."""
    
    def test_trade_completion_validation(self):
        """Test trade completion validation logic."""
        # Create mock fills for testing
        class MockFill:
            def __init__(self, account, symbol, date_time, position_qty):
                self.trade_account = account
                self.symbol = symbol
                self.date_time = date_time
                self.position_quantity = position_qty
        
        # Test complete day trade (position returns to zero)
        fills = [
            MockFill("IPS_TM_10", "NQH24", datetime(2024, 3, 5, 16, 5, 58), -3),  # Open short
            MockFill("IPS_TM_10", "NQH24", datetime(2024, 3, 5, 16, 7, 42), 0),   # Close position
        ]
        
        result = TradingDataValidator.validate_trade_completion(fills)
        assert result is True
        
        # Test incomplete day trade (position doesn't return to zero)
        incomplete_fills = [
            MockFill("IPS_TM_10", "NQH24", datetime(2024, 3, 5, 16, 5, 58), -3),  # Open short
            MockFill("IPS_TM_10", "NQH24", datetime(2024, 3, 5, 16, 7, 42), -1),  # Partial close
        ]
        
        with pytest.raises(ValidationError, match="Incomplete day trade detected"):
            TradingDataValidator.validate_trade_completion(incomplete_fills)
    
    def test_account_symbol_separation(self):
        """Test account/symbol separation validation."""
        # Create mock fills for testing
        class MockFill:
            def __init__(self, account, symbol):
                self.trade_account = account
                self.base_symbol = symbol
        
        # Test valid separation (each account trades one symbol)
        valid_fills = [
            MockFill("IPS_TM_10", "NQ"),
            MockFill("IPS_TM_10", "NQ"),
            MockFill("IPS_TM_13", "FDAX"),
            MockFill("IPS_TM_13", "FDAX"),
        ]
        
        result = TradingDataValidator.validate_account_symbol_separation(valid_fills)
        assert result is True
        
        # Test invalid separation (account trades multiple symbols)
        invalid_fills = [
            MockFill("IPS_TM_10", "NQ"),
            MockFill("IPS_TM_10", "FDAX"),  # Same account, different symbol
        ]
        
        with pytest.raises(ValidationError, match="Account/symbol separation violations"):
            TradingDataValidator.validate_account_symbol_separation(invalid_fills)


if __name__ == "__main__":
    pytest.main([__file__])