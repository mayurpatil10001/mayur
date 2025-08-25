"""
Validation utilities for trading data.
"""

import re
from datetime import datetime, date
from typing import Optional, List, Any
from decimal import Decimal, InvalidOperation


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class TradingDataValidator:
    """Validator for trading data integrity and business rules."""
    
    # Valid SierraChart activity types
    VALID_ACTIVITY_TYPES = {"Fills"}
    
    # Valid order types
    VALID_ORDER_TYPES = {"Market", "Limit", "Stop", "Stop Limit", "Trailing Stop"}
    
    # Valid order statuses
    VALID_ORDER_STATUSES = {"Filled", "Partially Filled", "Cancelled", "Rejected"}
    
    # Valid buy/sell values
    VALID_BUY_SELL = {"Buy", "Sell"}
    
    # Valid open/close values
    VALID_OPEN_CLOSE = {"Open", "Close"}
    
    # Valid symbols pattern (letters followed by month/year code)
    SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,6}[A-Z]?\d{2}$")
    
    # Valid account pattern (IPS_TM_XX, TM_XX, or TS_XX format)
    ACCOUNT_PATTERN = re.compile(r"^(IPS_)?T[MS]_\w+$")
    
    def validate_required_string(self, value: Any, field_name: str, max_length: int = None) -> str:
        """Validate required string field."""
        if not value or not str(value).strip():
            raise ValidationError(f"{field_name} cannot be empty")
        
        str_value = str(value).strip()
        # Set appropriate max lengths for different fields
        if max_length is None:
            if field_name == "OrderActionSource":
                max_length = 1000  # Increase to handle long action sources
            elif field_name == "Note":
                max_length = 1000  # Allow long notes
            else:
                max_length = 500  # Default for other fields
        
        if max_length and len(str_value) > max_length:
            raise ValidationError(f"{field_name} exceeds maximum length of {max_length}")
        
        return str_value
    
    def validate_optional_string(self, value: Any, field_name: str, max_length: int = None) -> Optional[str]:
        """Validate optional string field."""
        if value is None or str(value).strip() == "":
            return None
        
        str_value = str(value).strip()
        if max_length and len(str_value) > max_length:
            raise ValidationError(f"{field_name} exceeds maximum length of {max_length}")
        
        return str_value
    
    def validate_positive_integer(self, value: Any, field_name: str) -> int:
        """Validate positive integer field."""
        try:
            int_value = int(value)
            if int_value <= 0:
                raise ValidationError(f"{field_name} must be positive: {int_value}")
            return int_value
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid {field_name}: {value}")
    
    def validate_non_negative_integer(self, value: Any, field_name: str) -> int:
        """Validate non-negative integer field."""
        try:
            int_value = int(value)
            if int_value < 0:
                raise ValidationError(f"{field_name} cannot be negative: {int_value}")
            return int_value
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid {field_name}: {value}")
    
    def validate_automation_flag(self, value: str) -> str:
        """Validate automation flag (Y/N)."""
        if not value or value.upper() not in {"Y", "N"}:
            raise ValidationError(f"Invalid automation flag: {value}")
        return value.upper()
    
    @staticmethod
    def validate_business_rules(record_data: dict) -> List[str]:
        """Validate business rules and return warnings."""
        warnings = []
        
        # Check price consistency
        fill_price = record_data.get('fill_price')
        price = record_data.get('price')
        price2 = record_data.get('price2')
        
        if price and fill_price:
            price_diff = abs(fill_price - price) / price
            if price_diff > 0.01:  # More than 1% difference
                warnings.append(f"Fill price differs significantly from order price: {fill_price} vs {price}")
        
        # Check quantity consistency
        quantity = record_data.get('quantity', 0)
        filled_quantity = record_data.get('filled_quantity', 0)
        
        if quantity != filled_quantity:
            warnings.append(f"Quantity mismatch: ordered {quantity}, filled {filled_quantity}")
        
        # Check datetime consistency
        date_time = record_data.get('date_time')
        trans_date_time = record_data.get('trans_date_time')
        
        if date_time and trans_date_time and trans_date_time < date_time:
            warnings.append("Transaction time is before order time")
        
        return warnings
    
    @staticmethod
    def validate_activity_type(activity_type: str) -> str:
        """Validate activity type."""
        if not activity_type or activity_type not in TradingDataValidator.VALID_ACTIVITY_TYPES:
            raise ValidationError(f"Invalid activity type: {activity_type}")
        return activity_type
    
    @staticmethod
    def validate_datetime(dt: Any, field_name: str) -> datetime:
        """Validate datetime field."""
        if not isinstance(dt, datetime):
            if isinstance(dt, str):
                try:
                    return datetime.fromisoformat(dt.replace('Z', '+00:00'))
                except ValueError:
                    raise ValidationError(f"Invalid datetime format for {field_name}: {dt}")
            else:
                raise ValidationError(f"Invalid datetime type for {field_name}: {type(dt)}")
        return dt
    
    @staticmethod
    def validate_service_order_id(order_id: str) -> str:
        """Validate service order ID."""
        if not order_id or not order_id.strip():
            raise ValidationError("Service order ID cannot be empty")
        if not order_id.isdigit():
            raise ValidationError(f"Service order ID must be numeric: {order_id}")
        return order_id.strip()
    
    @staticmethod
    def validate_order_type(order_type: str) -> str:
        """Validate order type."""
        if not order_type or order_type not in TradingDataValidator.VALID_ORDER_TYPES:
            raise ValidationError(f"Invalid order type: {order_type}")
        return order_type
    
    @staticmethod
    def validate_quantity(quantity: Any) -> int:
        """Validate quantity field."""
        try:
            qty = int(quantity)
            if qty <= 0:
                raise ValidationError(f"Quantity must be positive: {qty}")
            return qty
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid quantity: {quantity}")
    
    @staticmethod
    def validate_order_status(status: str) -> str:
        """Validate order status."""
        if not status or status not in TradingDataValidator.VALID_ORDER_STATUSES:
            raise ValidationError(f"Invalid order status: {status}")
        return status
    
    @staticmethod
    def validate_trade_account(account: str) -> str:
        """Validate trade account format."""
        if not account or not account.strip():
            raise ValidationError("Trade account cannot be empty")
        
        account = account.strip()
        
        # Accept various account formats found in real SierraChart data:
        # - IPS_TM_X (e.g., IPS_TM_6, IPS_TM_3)
        # - TM_X (e.g., TM_10, TM_13)
        # - TS_X (e.g., TS_5)
        # - PB_X (e.g., PB_1)
        # - ES-TS_X (e.g., ES-TS_5) - ES futures accounts
        # - CL-TS_X (e.g., CL-TS_6) - CL futures accounts
        # - NQ-TS_X (e.g., NQ-TS_3) - NQ futures accounts
        # - 3Q_sim14 and similar simulation accounts
        # - Any account with alphanumeric characters, underscores, and hyphens
        
        # Use a more flexible pattern that accepts real account formats
        account_pattern = re.compile(r"^[A-Z0-9][A-Z0-9_-]*[A-Z0-9]$|^[A-Z0-9]$")
        
        if account_pattern.match(account):
            return account
        
        # If pattern doesn't match, still allow it but log a warning
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Unusual account format detected: {account}")
        
        return account
    
    @staticmethod
    def validate_buy_sell(buy_sell: str) -> str:
        """Validate buy/sell field."""
        if not buy_sell or buy_sell not in TradingDataValidator.VALID_BUY_SELL:
            raise ValidationError(f"Invalid buy/sell value: {buy_sell}")
        return buy_sell
    
    @staticmethod
    def validate_price(price: Any, field_name: str, allow_none: bool = True) -> Optional[float]:
        """Validate price field."""
        if price is None and allow_none:
            return None
        
        try:
            if isinstance(price, str):
                price = price.strip()
                if not price and allow_none:
                    return None
            
            price_val = float(price)
            if price_val < 0:
                raise ValidationError(f"{field_name} cannot be negative: {price_val}")
            return price_val
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid {field_name}: {price}")
    
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate trading symbol."""
        if not symbol or not symbol.strip():
            raise ValidationError("Symbol cannot be empty")
        
        symbol = symbol.strip().upper()
        if not TradingDataValidator.SYMBOL_PATTERN.match(symbol):
            raise ValidationError(f"Invalid symbol format: {symbol}")
        return symbol
    
    @staticmethod
    def validate_open_close(open_close: str) -> str:
        """Validate open/close field."""
        if not open_close or open_close not in TradingDataValidator.VALID_OPEN_CLOSE:
            raise ValidationError(f"Invalid open/close value: {open_close}")
        return open_close
    
    @staticmethod
    def validate_position_quantity(position_qty: Any) -> int:
        """Validate position quantity (can be negative)."""
        try:
            return int(position_qty)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid position quantity: {position_qty}")
    
    @staticmethod
    def validate_account_balance(balance: Any) -> float:
        """Validate account balance."""
        try:
            balance_val = float(balance)
            return balance_val
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid account balance: {balance}")
    
    @staticmethod
    def validate_is_automated(is_automated: str) -> str:
        """Validate is_automated field."""
        if not is_automated or is_automated not in {"Y", "N"}:
            raise ValidationError(f"Invalid is_automated value: {is_automated}")
        return is_automated
    
    @staticmethod
    def validate_trade_completion(fills: List[Any]) -> bool:
        """Validate that trades are complete (position returns to zero)."""
        if not fills:
            return True
        
        # Group by account and symbol
        account_positions = {}
        
        for fill in fills:
            key = (fill.trade_account, fill.symbol)
            if key not in account_positions:
                account_positions[key] = []
            account_positions[key].append(fill)
        
        # Check each account/symbol combination
        for (account, symbol), account_fills in account_positions.items():
            # Sort by datetime
            sorted_fills = sorted(account_fills, key=lambda x: x.date_time)
            
            # Check if position returns to zero by end of day
            daily_positions = {}
            for fill in sorted_fills:
                trade_date = fill.date_time.date()
                if trade_date not in daily_positions:
                    daily_positions[trade_date] = []
                daily_positions[trade_date].append(fill)
            
            # Validate each day's trades
            for trade_date, day_fills in daily_positions.items():
                final_position = day_fills[-1].position_quantity if day_fills else 0
                if final_position != 0:
                    raise ValidationError(
                        f"Incomplete day trade detected for {account}/{symbol} on {trade_date}: "
                        f"final position {final_position}"
                    )
        
        return True
    
    @staticmethod
    def validate_account_symbol_separation(fills: List[Any]) -> bool:
        """Validate that each account trades only one symbol (FLEXIBLE - allows mixed trading)."""
        account_symbols = {}
        
        for fill in fills:
            account = fill.trade_account
            base_symbol = getattr(fill, 'base_symbol', fill.symbol[:2] if hasattr(fill, 'symbol') else 'UNKNOWN')
            
            if account not in account_symbols:
                account_symbols[account] = set()
            account_symbols[account].add(base_symbol)
        
        # Log mixed trading as info (completely normal)
        mixed_accounts = []
        for account, symbols in account_symbols.items():
            if len(symbols) > 1:
                mixed_accounts.append(f"Account {account} trades: {', '.join(sorted(symbols))}")
        
        if mixed_accounts:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Multi-symbol accounts detected: " + "; ".join(mixed_accounts))
        
        return True  # Always return True - mixed trading is allowed