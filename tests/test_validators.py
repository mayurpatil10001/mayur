"""
Tests for validation utilities.
"""

import pytest
from datetime import datetime
from trading_platform.utils.validators import TradingDataValidator, ValidationError


class TestTradingDataValidator:
    """Test trading data validator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = TradingDataValidator()
    
    def test_validate_activity_type_valid(self):
        """Test valid activity type validation."""
        result = self.validator.validate_activity_type("Fills")
        assert result == "Fills"
    
    def test_validate_activity_type_invalid(self):
        """Test invalid activity type validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_activity_type("Invalid")
    
    def test_validate_datetime_valid(self):
        """Test valid datetime validation."""
        dt = datetime(2024, 3, 5, 16, 5, 58)
        result = self.validator.validate_datetime(dt, "TestField")
        assert result == dt
    
    def test_validate_datetime_string(self):
        """Test datetime validation from string."""
        dt_str = "2024-03-05T16:05:58"
        result = self.validator.validate_datetime(dt_str, "TestField")
        assert isinstance(result, datetime)
    
    def test_validate_datetime_invalid(self):
        """Test invalid datetime validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_datetime("invalid", "TestField")
    
    def test_validate_service_order_id_valid(self):
        """Test valid service order ID validation."""
        result = self.validator.validate_service_order_id("8951508")
        assert result == "8951508"
    
    def test_validate_service_order_id_invalid(self):
        """Test invalid service order ID validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_service_order_id("ABC123")
    
    def test_validate_order_type_valid(self):
        """Test valid order type validation."""
        for order_type in ["Market", "Limit", "Stop", "Stop Limit"]:
            result = self.validator.validate_order_type(order_type)
            assert result == order_type
    
    def test_validate_order_type_invalid(self):
        """Test invalid order type validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_order_type("Invalid")
    
    def test_validate_quantity_valid(self):
        """Test valid quantity validation."""
        result = self.validator.validate_quantity(5)
        assert result == 5
        
        result = self.validator.validate_quantity("10")
        assert result == 10
    
    def test_validate_quantity_invalid(self):
        """Test invalid quantity validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_quantity(0)
        
        with pytest.raises(ValidationError):
            self.validator.validate_quantity(-5)
        
        with pytest.raises(ValidationError):
            self.validator.validate_quantity("abc")
    
    def test_validate_trade_account_valid(self):
        """Test valid trade account validation."""
        for account in ["IPS_TM_10", "IPS_TS_13", "IPS_TM_ABC"]:
            result = self.validator.validate_trade_account(account)
            assert result == account
    
    def test_validate_trade_account_invalid(self):
        """Test invalid trade account validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_trade_account("INVALID_ACCOUNT")
    
    def test_validate_buy_sell_valid(self):
        """Test valid buy/sell validation."""
        for value in ["Buy", "Sell"]:
            result = self.validator.validate_buy_sell(value)
            assert result == value
    
    def test_validate_buy_sell_invalid(self):
        """Test invalid buy/sell validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_buy_sell("Invalid")
    
    def test_validate_price_valid(self):
        """Test valid price validation."""
        result = self.validator.validate_price(100.50, "TestPrice", allow_none=False)
        assert result == 100.50
        
        result = self.validator.validate_price(None, "TestPrice", allow_none=True)
        assert result is None
        
        result = self.validator.validate_price("150.75", "TestPrice", allow_none=False)
        assert result == 150.75
    
    def test_validate_price_invalid(self):
        """Test invalid price validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_price(-100, "TestPrice", allow_none=False)
        
        with pytest.raises(ValidationError):
            self.validator.validate_price(None, "TestPrice", allow_none=False)
        
        with pytest.raises(ValidationError):
            self.validator.validate_price("abc", "TestPrice", allow_none=False)
    
    def test_validate_symbol_valid(self):
        """Test valid symbol validation."""
        for symbol in ["NQH24", "FDAXM24", "ESU24"]:
            result = self.validator.validate_symbol(symbol)
            assert result == symbol
    
    def test_validate_symbol_invalid(self):
        """Test invalid symbol validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_symbol("")
        
        with pytest.raises(ValidationError):
            self.validator.validate_symbol("INVALID")
    
    def test_validate_open_close_valid(self):
        """Test valid open/close validation."""
        for value in ["Open", "Close"]:
            result = self.validator.validate_open_close(value)
            assert result == value
    
    def test_validate_open_close_invalid(self):
        """Test invalid open/close validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_open_close("Invalid")
    
    def test_validate_position_quantity_valid(self):
        """Test valid position quantity validation."""
        result = self.validator.validate_position_quantity(-3)
        assert result == -3
        
        result = self.validator.validate_position_quantity(5)
        assert result == 5
        
        result = self.validator.validate_position_quantity("0")
        assert result == 0
    
    def test_validate_position_quantity_invalid(self):
        """Test invalid position quantity validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_position_quantity("abc")
    
    def test_validate_is_automated_valid(self):
        """Test valid is_automated validation."""
        for value in ["Y", "N"]:
            result = self.validator.validate_is_automated(value)
            assert result == value
    
    def test_validate_is_automated_invalid(self):
        """Test invalid is_automated validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_is_automated("Maybe")
    
    def test_validate_required_string_valid(self):
        """Test valid required string validation."""
        result = self.validator.validate_required_string("test", "TestField", 10)
        assert result == "test"
        
        result = self.validator.validate_required_string("  test  ", "TestField", 10)
        assert result == "test"
    
    def test_validate_required_string_invalid(self):
        """Test invalid required string validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_required_string("", "TestField")
        
        with pytest.raises(ValidationError):
            self.validator.validate_required_string("   ", "TestField")
        
        with pytest.raises(ValidationError):
            self.validator.validate_required_string("toolong", "TestField", 5)
    
    def test_validate_optional_string_valid(self):
        """Test valid optional string validation."""
        result = self.validator.validate_optional_string("test", "TestField", 10)
        assert result == "test"
        
        result = self.validator.validate_optional_string("", "TestField", 10)
        assert result is None
        
        result = self.validator.validate_optional_string(None, "TestField", 10)
        assert result is None
    
    def test_validate_optional_string_invalid(self):
        """Test invalid optional string validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_optional_string("toolong", "TestField", 5)
    
    def test_validate_positive_integer_valid(self):
        """Test valid positive integer validation."""
        result = self.validator.validate_positive_integer(5, "TestField")
        assert result == 5
        
        result = self.validator.validate_positive_integer("10", "TestField")
        assert result == 10
    
    def test_validate_positive_integer_invalid(self):
        """Test invalid positive integer validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_positive_integer(0, "TestField")
        
        with pytest.raises(ValidationError):
            self.validator.validate_positive_integer(-5, "TestField")
        
        with pytest.raises(ValidationError):
            self.validator.validate_positive_integer("abc", "TestField")
    
    def test_validate_non_negative_integer_valid(self):
        """Test valid non-negative integer validation."""
        result = self.validator.validate_non_negative_integer(0, "TestField")
        assert result == 0
        
        result = self.validator.validate_non_negative_integer(5, "TestField")
        assert result == 5
    
    def test_validate_non_negative_integer_invalid(self):
        """Test invalid non-negative integer validation."""
        with pytest.raises(ValidationError):
            self.validator.validate_non_negative_integer(-1, "TestField")
    
    def test_validate_business_rules(self):
        """Test business rules validation."""
        record_data = {
            'fill_price': 100.0,
            'price': 100.0,
            'quantity': 5,
            'filled_quantity': 5,
            'date_time': datetime(2024, 3, 5, 16, 5, 58),
            'trans_date_time': datetime(2024, 3, 5, 16, 5, 59)
        }
        
        warnings = TradingDataValidator.validate_business_rules(record_data)
        assert isinstance(warnings, list)
        assert len(warnings) == 0  # No warnings for valid data
    
    def test_validate_business_rules_with_warnings(self):
        """Test business rules validation with warnings."""
        record_data = {
            'fill_price': 100.0,
            'price': 110.0,  # Significant price difference
            'quantity': 5,
            'filled_quantity': 3,  # Quantity mismatch
            'date_time': datetime(2024, 3, 5, 16, 5, 58),
            'trans_date_time': datetime(2024, 3, 5, 16, 5, 57)  # Time inconsistency
        }
        
        warnings = TradingDataValidator.validate_business_rules(record_data)
        assert len(warnings) == 3  # Should have 3 warnings


if __name__ == "__main__":
    pytest.main([__file__])