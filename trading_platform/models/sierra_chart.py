"""
SierraChart data models for raw trading data with comprehensive validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import re

from ..utils.validators import TradingDataValidator, ValidationError


@dataclass
class SierraChartTradeRecord:
    """Raw SierraChart trade record from tab-delimited files with comprehensive validation."""
    
    # Core SierraChart fields (29 columns)
    activity_type: str  # "Fills"
    date_time: datetime
    trans_date_time: datetime
    service_order_id: str
    order_type: str  # Market, Limit, Stop, Stop Limit
    quantity: int
    order_status: str  # Filled
    trade_account: str  # IPS_TM_10, IPS_TM_13, etc.
    buy_sell: str  # Buy, Sell
    price: Optional[float]
    price2: Optional[float]
    fill_price: float
    filled_quantity: int
    note: str
    order_action_source: str
    internal_order_id: str
    symbol: str  # NQH24, FDAXM24, etc.
    open_close: str  # Open, Close
    parent_internal_order_id: Optional[str]
    position_quantity: int  # Running position balance
    fill_execution_service_id: str
    high_during_position: Optional[float]
    low_during_position: Optional[float]
    account_balance: float
    exchange_order_id: str
    client_order_id: str
    time_in_force: str
    username: str
    is_automated: str  # Y/N
    
    # Metadata fields
    file_source: str = field(default="")
    import_timestamp: datetime = field(default_factory=datetime.now)
    
    # Derived fields for analysis
    trade_id: str = field(init=False, default="")
    is_complete_day_trade: bool = field(init=False, default=False)
    profit_loss: Optional[float] = field(init=False, default=None)
    validation_warnings: List[str] = field(init=False, default_factory=list)
    
    def __post_init__(self):
        """Validate data and generate derived fields after initialization."""
        try:
            self._validate_all_fields()
            self.trade_id = f"{self.trade_account}_{self.internal_order_id}"
            self._check_business_rules()
        except ValidationError as e:
            raise ValidationError(f"Invalid SierraChart record: {e}")
    
    def _validate_all_fields(self):
        """Validate all fields according to business rules."""
        validator = TradingDataValidator()
        
        # Validate required string fields
        self.activity_type = validator.validate_activity_type(self.activity_type)
        self.service_order_id = validator.validate_required_string(self.service_order_id, "ServiceOrderID", 50)
        self.order_type = validator.validate_order_type(self.order_type)
        self.order_status = validator.validate_order_status(self.order_status)
        self.trade_account = validator.validate_trade_account(self.trade_account)
        self.buy_sell = validator.validate_buy_sell(self.buy_sell)
        self.symbol = validator.validate_symbol(self.symbol)
        self.open_close = validator.validate_open_close(self.open_close)
        self.is_automated = validator.validate_automation_flag(self.is_automated)
        
        # Validate datetime fields
        self.date_time = validator.validate_datetime(self.date_time, "DateTime")
        self.trans_date_time = validator.validate_datetime(self.trans_date_time, "TransDateTime")
        
        # Validate numeric fields
        self.quantity = validator.validate_positive_integer(self.quantity, "Quantity")
        self.filled_quantity = validator.validate_non_negative_integer(self.filled_quantity, "FilledQuantity")
        self.position_quantity = validator.validate_position_quantity(self.position_quantity)
        
        # Validate price fields
        self.price = validator.validate_price(self.price, "Price", allow_none=True)
        self.price2 = validator.validate_price(self.price2, "Price2", allow_none=True)
        self.fill_price = validator.validate_price(self.fill_price, "FillPrice", allow_none=False)
        self.high_during_position = validator.validate_price(self.high_during_position, "HighDuringPosition", allow_none=True)
        self.low_during_position = validator.validate_price(self.low_during_position, "LowDuringPosition", allow_none=True)
        self.account_balance = validator.validate_price(self.account_balance, "AccountBalance", allow_none=False)
        
        # Validate optional string fields
        self.note = validator.validate_optional_string(self.note, "Note", 1000) or ""
        self.order_action_source = validator.validate_optional_string(self.order_action_source, "OrderActionSource", 1000) or ""
        self.internal_order_id = validator.validate_required_string(self.internal_order_id, "InternalOrderID", 50)
        self.parent_internal_order_id = validator.validate_optional_string(self.parent_internal_order_id, "ParentInternalOrderID", 50)
        self.fill_execution_service_id = validator.validate_optional_string(self.fill_execution_service_id, "FillExecutionServiceID", 50) or ""
        self.exchange_order_id = validator.validate_optional_string(self.exchange_order_id, "ExchangeOrderID", 50) or ""
        self.client_order_id = validator.validate_optional_string(self.client_order_id, "ClientOrderID", 50) or ""
        self.time_in_force = validator.validate_optional_string(self.time_in_force, "TimeInForce", 50) or ""
        self.username = validator.validate_optional_string(self.username, "Username", 50) or ""
    
    def _check_business_rules(self):
        """Check business rules and collect warnings."""
        record_data = {
            'fill_price': self.fill_price,
            'price': self.price,
            'price2': self.price2,
            'quantity': self.quantity,
            'filled_quantity': self.filled_quantity,
            'date_time': self.date_time,
            'trans_date_time': self.trans_date_time
        }
        
        self.validation_warnings = TradingDataValidator.validate_business_rules(record_data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], file_source: str = "") -> 'SierraChartTradeRecord':
        """Create instance from dictionary with validation."""
        try:
            # Create a copy to avoid modifying original data
            clean_data = data.copy()
            clean_data['file_source'] = file_source
            
            return cls(**clean_data)
        except TypeError as e:
            raise ValidationError(f"Missing required fields: {e}")
        except Exception as e:
            raise ValidationError(f"Failed to create record: {e}")
    
    @classmethod
    def from_tab_delimited_line(cls, line: str, headers: List[str], file_source: str = "") -> 'SierraChartTradeRecord':
        """Create instance from tab-delimited line."""
        if not line.strip():
            raise ValidationError("Empty line provided")
        
        fields = line.strip().split('\t')
        
        if len(fields) != len(headers):
            raise ValidationError(f"Expected {len(headers)} fields, got {len(fields)}")
        
        # Create dictionary from headers and fields
        data = dict(zip(headers, fields))
        
        # Convert data types
        try:
            # Convert datetime fields
            data['date_time'] = datetime.strptime(data['DateTime'], '%Y-%m-%d %H:%M:%S.%f')
            data['trans_date_time'] = datetime.strptime(data['TransDateTime'], '%Y-%m-%d %H:%M:%S.%f')
            
            # Convert numeric fields
            data['quantity'] = int(data['Quantity'])
            data['filled_quantity'] = int(data['FilledQuantity'])
            data['position_quantity'] = int(data['PositionQuantity'])
            
            # Convert price fields (handle empty strings)
            data['price'] = float(data['Price']) if data['Price'].strip() else None
            data['price2'] = float(data['Price2']) if data['Price2'].strip() else None
            data['fill_price'] = float(data['FillPrice'])
            data['high_during_position'] = float(data['HighDuringPosition']) if data['HighDuringPosition'].strip() else None
            data['low_during_position'] = float(data['LowDuringPosition']) if data['LowDuringPosition'].strip() else None
            data['account_balance'] = float(data['AccountBalance'])
            
            # Map field names to match dataclass
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
            
            # Remap fields
            mapped_data = {}
            for old_key, new_key in field_mapping.items():
                if old_key in data:
                    mapped_data[new_key] = data[old_key]
            
            return cls.from_dict(mapped_data, file_source)
            
        except (ValueError, KeyError) as e:
            raise ValidationError(f"Failed to parse line: {e}")
    
    def validate(self) -> bool:
        """Validate the record and return True if valid."""
        try:
            self._validate_all_fields()
            return True
        except ValidationError:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'activity_type': self.activity_type,
            'date_time': self.date_time.isoformat(),
            'trans_date_time': self.trans_date_time.isoformat(),
            'service_order_id': self.service_order_id,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'order_status': self.order_status,
            'trade_account': self.trade_account,
            'buy_sell': self.buy_sell,
            'price': self.price,
            'price2': self.price2,
            'fill_price': self.fill_price,
            'filled_quantity': self.filled_quantity,
            'note': self.note,
            'order_action_source': self.order_action_source,
            'internal_order_id': self.internal_order_id,
            'symbol': self.symbol,
            'open_close': self.open_close,
            'parent_internal_order_id': self.parent_internal_order_id,
            'position_quantity': self.position_quantity,
            'fill_execution_service_id': self.fill_execution_service_id,
            'high_during_position': self.high_during_position,
            'low_during_position': self.low_during_position,
            'account_balance': self.account_balance,
            'exchange_order_id': self.exchange_order_id,
            'client_order_id': self.client_order_id,
            'time_in_force': self.time_in_force,
            'username': self.username,
            'is_automated': self.is_automated,
            'file_source': self.file_source,
            'import_timestamp': self.import_timestamp.isoformat(),
            'trade_id': self.trade_id,
            'validation_warnings': self.validation_warnings
        }
        
    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self.buy_sell.lower() == "buy"
    
    @property
    def is_sell(self) -> bool:
        """Check if this is a sell order."""
        return self.buy_sell.lower() == "sell"
    
    @property
    def is_opening(self) -> bool:
        """Check if this is an opening trade."""
        return self.open_close.lower() == "open"
    
    @property
    def is_closing(self) -> bool:
        """Check if this is a closing trade."""
        return self.open_close.lower() == "close"
    
    @property
    def base_symbol(self) -> str:
        """Extract base symbol (NQ, FDAX, CL, ES) from contract symbol (NQH24, FDAXM24, CLQ25, ESU25)."""
        if self.symbol.startswith("NQ"):
            return "NQ"
        elif self.symbol.startswith("FDAX"):
            return "FDAX"
        elif self.symbol.startswith("CL"):
            return "CL"
        elif self.symbol.startswith("ES"):
            return "ES"
        else:
            # For other symbols, extract letters before numbers/month codes
            # Use a more conservative approach - look for common patterns
            match = re.match(r"([A-Z]{1,4})", self.symbol)
            if match:
                base = match.group(1)
                # Handle common futures symbols
                if base in ["GC", "SI", "HG", "NG", "ZB", "ZN", "ZF", "ZT"]:
                    return base
                # For unknown symbols, try to extract just the first 2-3 letters
                if len(base) > 3:
                    return base[:2]  # Most futures symbols are 2 letters
                return base
            return self.symbol
    
    @property
    def has_warnings(self) -> bool:
        """Check if record has validation warnings."""
        return len(self.validation_warnings) > 0
    
    @property
    def is_same_day_trade(self) -> bool:
        """Check if this could be part of a same-day trade."""
        return self.date_time.date() == self.trans_date_time.date()


@dataclass
class ProcessedTrade:
    """Represents a complete processed trade (round-trip)."""
    trade_id: str
    account_name: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    side: str  # 'LONG' or 'SHORT'
    profit_loss: float
    commission: float
    duration_minutes: int
    hour_of_day: int
    day_of_week: int