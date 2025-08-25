"""
SierraChart trade data models for completed trade records.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import re

from ..utils.validators import TradingDataValidator, ValidationError


@dataclass
class SierraChartTradeRecord:
    """SierraChart completed trade record from trade files with comprehensive validation."""
    
    # Core SierraChart trade fields (27 columns)
    symbol: str  # CLQ25, NQU25, etc.
    trade_type: str  # Long, Short
    entry_datetime: datetime
    exit_datetime: datetime
    entry_price: float
    exit_price: float
    trade_quantity: int
    max_open_quantity: int
    max_closed_quantity: int
    profit_loss: float  # Already calculated P&L in currency
    cumulative_profit_loss: float
    duration: str  # HH:MM:SS format
    commission: float
    high_price_while_open: float
    low_price_while_open: float
    exit_efficiency: str  # Percentage
    account: str  # IPS_TM_6, TM_3, etc.
    entry_efficiency: str  # Percentage
    flat_to_flat_profit_loss: float
    flat_to_flat_max_open_profit: float
    flat_to_flat_max_open_loss: float
    max_open_profit: float
    max_open_loss: float
    note: str
    total_efficiency: str  # Percentage
    open_position_quantity: int
    close_position_quantity: int
    
    # Metadata fields
    file_source: str = field(default="")
    import_timestamp: datetime = field(default_factory=datetime.now)
    
    # Derived fields for analysis
    trade_id: str = field(init=False, default="")
    base_symbol: str = field(init=False, default="")
    duration_minutes: int = field(init=False, default=0)
    validation_warnings: List[str] = field(init=False, default_factory=list)
    
    def __post_init__(self):
        """Validate data and generate derived fields after initialization."""
        try:
            self._validate_all_fields()
            self.trade_id = f"{self.account}_{self.entry_datetime.strftime('%Y%m%d_%H%M%S')}_{hash(str(self))}"
            self.base_symbol = self._extract_base_symbol()
            self.duration_minutes = self._calculate_duration_minutes()
            self._check_business_rules()
        except ValidationError as e:
            raise ValidationError(f"Invalid SierraChart trade record: {e}")
    
    def _validate_all_fields(self):
        """Validate all fields according to business rules."""
        validator = TradingDataValidator()
        
        # Validate required string fields
        self.symbol = validator.validate_required_string(self.symbol, "Symbol", 20)
        self.trade_type = validator.validate_required_string(self.trade_type, "TradeType", 10)
        self.account = validator.validate_trade_account(self.account)
        
        # Validate datetime fields
        self.entry_datetime = validator.validate_datetime(self.entry_datetime, "EntryDateTime")
        self.exit_datetime = validator.validate_datetime(self.exit_datetime, "ExitDateTime")
        
        # Validate that exit is after entry
        if self.exit_datetime <= self.entry_datetime:
            raise ValidationError("Exit datetime must be after entry datetime")
        
        # Validate numeric fields
        self.trade_quantity = validator.validate_positive_integer(self.trade_quantity, "TradeQuantity")
        self.max_open_quantity = validator.validate_positive_integer(self.max_open_quantity, "MaxOpenQuantity")
        self.max_closed_quantity = validator.validate_positive_integer(self.max_closed_quantity, "MaxClosedQuantity")
        
        # Validate price fields
        self.entry_price = validator.validate_price(self.entry_price, "EntryPrice", allow_none=False)
        self.exit_price = validator.validate_price(self.exit_price, "ExitPrice", allow_none=False)
        self.high_price_while_open = validator.validate_price(self.high_price_while_open, "HighPriceWhileOpen", allow_none=False)
        self.low_price_while_open = validator.validate_price(self.low_price_while_open, "LowPriceWhileOpen", allow_none=False)
        
        # Validate P&L fields (can be negative)
        if not isinstance(self.profit_loss, (int, float)):
            raise ValidationError("Profit/Loss must be a number")
        if not isinstance(self.cumulative_profit_loss, (int, float)):
            raise ValidationError("Cumulative Profit/Loss must be a number")
        if not isinstance(self.commission, (int, float)) or self.commission < 0:
            raise ValidationError("Commission must be a non-negative number")
        
        # Validate trade type
        if self.trade_type not in ['Long', 'Short']:
            raise ValidationError("Trade type must be 'Long' or 'Short'")
        
        # Validate optional string fields
        self.duration = validator.validate_optional_string(self.duration, "Duration", 20) or ""
        self.exit_efficiency = validator.validate_optional_string(self.exit_efficiency, "ExitEfficiency", 20) or ""
        self.entry_efficiency = validator.validate_optional_string(self.entry_efficiency, "EntryEfficiency", 20) or ""
        self.note = validator.validate_optional_string(self.note, "Note", 1000) or ""
        self.total_efficiency = validator.validate_optional_string(self.total_efficiency, "TotalEfficiency", 20) or ""
    
    def _extract_base_symbol(self) -> str:
        """Extract base symbol from contract symbol."""
        if self.symbol.startswith("NQ"):
            return "NQ"
        elif self.symbol.startswith("CL"):
            return "CL"
        elif self.symbol.startswith("ES"):
            return "ES"
        elif self.symbol.startswith("FDAX"):
            return "FDAX"
        else:
            # Extract letters before numbers/month codes
            match = re.match(r"([A-Z]{1,4})", self.symbol)
            if match:
                return match.group(1)
            return self.symbol
    
    def _calculate_duration_minutes(self) -> int:
        """Calculate duration in minutes from entry to exit."""
        return int((self.exit_datetime - self.entry_datetime).total_seconds() / 60)
    
    def _check_business_rules(self):
        """Check business rules and collect warnings."""
        warnings = []
        
        # Check price consistency
        if self.high_price_while_open < max(self.entry_price, self.exit_price):
            warnings.append("High price while open is less than entry/exit prices")
        
        if self.low_price_while_open > min(self.entry_price, self.exit_price):
            warnings.append("Low price while open is greater than entry/exit prices")
        
        # Check quantity consistency
        if self.max_open_quantity < self.trade_quantity:
            warnings.append("Max open quantity is less than trade quantity")
        
        if self.max_closed_quantity < self.trade_quantity:
            warnings.append("Max closed quantity is less than trade quantity")
        
        # Check P&L calculation (simplified)
        if self.trade_type == "Long":
            expected_gross_pnl = (self.exit_price - self.entry_price) * self.trade_quantity
        else:  # Short
            expected_gross_pnl = (self.entry_price - self.exit_price) * self.trade_quantity
        
        expected_net_pnl = expected_gross_pnl - self.commission
        
        # Allow for some tolerance in P&L calculation due to different multipliers/rounding
        if abs(self.profit_loss - expected_net_pnl) > (abs(expected_net_pnl) * 0.1):  # 10% tolerance
            warnings.append(f"P&L calculation may be incorrect: expected ~{expected_net_pnl:.2f}, got {self.profit_loss:.2f}")
        
        self.validation_warnings = warnings
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], file_source: str = "") -> 'SierraChartTradeRecord':
        """Create instance from dictionary with validation."""
        try:
            clean_data = data.copy()
            clean_data['file_source'] = file_source
            return cls(**clean_data)
        except TypeError as e:
            raise ValidationError(f"Missing required fields: {e}")
        except Exception as e:
            raise ValidationError(f"Failed to create trade record: {e}")
    
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
            data['entry_datetime'] = datetime.strptime(data['Entry DateTime'][:19], '%Y-%m-%d %H:%M:%S')
            data['exit_datetime'] = datetime.strptime(data['Exit DateTime'][:19], '%Y-%m-%d %H:%M:%S')
            
            # Convert numeric fields
            data['trade_quantity'] = int(data['Trade Quantity'])
            data['max_open_quantity'] = int(data['Max Open Quantity'])
            data['max_closed_quantity'] = int(data['Max Closed Quantity'])
            data['open_position_quantity'] = int(data['Open Position Quantity'])
            data['close_position_quantity'] = int(data['Close Position Quantity'])
            
            # Convert price fields
            data['entry_price'] = float(data['Entry Price'])
            data['exit_price'] = float(data['Exit Price'])
            data['profit_loss'] = float(data['Profit/Loss (C)'])
            data['cumulative_profit_loss'] = float(data['Cumulative Profit/Loss (C)'])
            data['commission'] = float(data['Commission (C)']) if data['Commission (C)'].strip() else 0.0
            data['high_price_while_open'] = float(data['High Price While Open'])
            data['low_price_while_open'] = float(data['Low Price While Open'])
            data['flat_to_flat_profit_loss'] = float(data['FlatToFlat Profit/Loss (C)'])
            data['flat_to_flat_max_open_profit'] = float(data['FlatToFlat Max Open Profit (C)'])
            data['flat_to_flat_max_open_loss'] = float(data['FlatToFlat Max Open Loss (C)'])
            data['max_open_profit'] = float(data['Max Open Profit (C)'])
            data['max_open_loss'] = float(data['Max Open Loss (C)'])
            
            # Map field names to match dataclass
            field_mapping = {
                'Symbol': 'symbol',
                'Trade Type': 'trade_type',
                'Entry DateTime': 'entry_datetime',
                'Exit DateTime': 'exit_datetime',
                'Entry Price': 'entry_price',
                'Exit Price': 'exit_price',
                'Trade Quantity': 'trade_quantity',
                'Max Open Quantity': 'max_open_quantity',
                'Max Closed Quantity': 'max_closed_quantity',
                'Profit/Loss (C)': 'profit_loss',
                'Cumulative Profit/Loss (C)': 'cumulative_profit_loss',
                'Duration': 'duration',
                'Commission (C)': 'commission',
                'High Price While Open': 'high_price_while_open',
                'Low Price While Open': 'low_price_while_open',
                'Exit Efficiency': 'exit_efficiency',
                'Account': 'account',
                'Entry Efficiency': 'entry_efficiency',
                'FlatToFlat Profit/Loss (C)': 'flat_to_flat_profit_loss',
                'FlatToFlat Max Open Profit (C)': 'flat_to_flat_max_open_profit',
                'FlatToFlat Max Open Loss (C)': 'flat_to_flat_max_open_loss',
                'Max Open Profit (C)': 'max_open_profit',
                'Max Open Loss (C)': 'max_open_loss',
                'Note': 'note',
                'Total Efficiency': 'total_efficiency',
                'Open Position Quantity': 'open_position_quantity',
                'Close Position Quantity': 'close_position_quantity'
            }
            
            # Remap fields
            mapped_data = {}
            for old_key, new_key in field_mapping.items():
                if old_key in data:
                    mapped_data[new_key] = data[old_key]
            
            return cls.from_dict(mapped_data, file_source)
            
        except (ValueError, KeyError) as e:
            raise ValidationError(f"Failed to parse trade line: {e}")
    
    @property
    def is_long(self) -> bool:
        """Check if this is a long trade."""
        return self.trade_type.lower() == "long"
    
    @property
    def is_short(self) -> bool:
        """Check if this is a short trade."""
        return self.trade_type.lower() == "short"
    
    @property
    def is_profitable(self) -> bool:
        """Check if the trade was profitable."""
        return self.profit_loss > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if record has validation warnings."""
        return len(self.validation_warnings) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'trade_type': self.trade_type,
            'entry_datetime': self.entry_datetime.isoformat(),
            'exit_datetime': self.exit_datetime.isoformat(),
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'trade_quantity': self.trade_quantity,
            'max_open_quantity': self.max_open_quantity,
            'max_closed_quantity': self.max_closed_quantity,
            'profit_loss': self.profit_loss,
            'cumulative_profit_loss': self.cumulative_profit_loss,
            'duration': self.duration,
            'commission': self.commission,
            'high_price_while_open': self.high_price_while_open,
            'low_price_while_open': self.low_price_while_open,
            'exit_efficiency': self.exit_efficiency,
            'account': self.account,
            'entry_efficiency': self.entry_efficiency,
            'flat_to_flat_profit_loss': self.flat_to_flat_profit_loss,
            'flat_to_flat_max_open_profit': self.flat_to_flat_max_open_profit,
            'flat_to_flat_max_open_loss': self.flat_to_flat_max_open_loss,
            'max_open_profit': self.max_open_profit,
            'max_open_loss': self.max_open_loss,
            'note': self.note,
            'total_efficiency': self.total_efficiency,
            'open_position_quantity': self.open_position_quantity,
            'close_position_quantity': self.close_position_quantity,
            'file_source': self.file_source,
            'import_timestamp': self.import_timestamp.isoformat(),
            'trade_id': self.trade_id,
            'base_symbol': self.base_symbol,
            'duration_minutes': self.duration_minutes,
            'validation_warnings': self.validation_warnings
        }
