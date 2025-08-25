"""
Core trading data models for processed data with validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..utils.validators import TradingDataValidator, ValidationError


@dataclass
class ProcessedTrade:
    """Simplified trade record after processing SierraChart data into complete round trips."""
    
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
    entry_order_id: str
    exit_order_id: str
    
    def __post_init__(self):
        """Validate trade data after initialization."""
        self._validate_trade()
    
    def _validate_trade(self):
        """Validate trade data."""
        validator = TradingDataValidator()
        
        # Validate required fields
        self.trade_id = validator.validate_required_string(self.trade_id, "TradeID", 100)
        self.account_name = validator.validate_trade_account(self.account_name)
        self.symbol = validator.validate_required_string(self.symbol, "Symbol", 20)
        self.entry_order_id = validator.validate_required_string(self.entry_order_id, "EntryOrderID", 50)
        self.exit_order_id = validator.validate_required_string(self.exit_order_id, "ExitOrderID", 50)
        
        # Validate datetime fields
        self.entry_time = validator.validate_datetime(self.entry_time, "EntryTime")
        self.exit_time = validator.validate_datetime(self.exit_time, "ExitTime")
        
        # Validate that exit time is after entry time
        if self.exit_time <= self.entry_time:
            raise ValidationError("Exit time must be after entry time")
        
        # Validate numeric fields
        self.quantity = validator.validate_positive_integer(self.quantity, "Quantity")
        self.entry_price = validator.validate_price(self.entry_price, "EntryPrice", allow_none=False)
        self.exit_price = validator.validate_price(self.exit_price, "ExitPrice", allow_none=False)
        self.commission = validator.validate_price(self.commission, "Commission", allow_none=False)
        
        # Validate side
        if self.side not in ['LONG', 'SHORT']:
            raise ValidationError("Side must be 'LONG' or 'SHORT'")
        
        # Validate time-based fields
        if not (0 <= self.hour_of_day <= 23):
            raise ValidationError("Hour of day must be between 0 and 23")
        
        if not (0 <= self.day_of_week <= 6):
            raise ValidationError("Day of week must be between 0 and 6")
        
        # Validate duration
        calculated_duration = int((self.exit_time - self.entry_time).total_seconds() / 60)
        if abs(self.duration_minutes - calculated_duration) > 1:  # Allow 1 minute tolerance
            raise ValidationError(f"Duration mismatch: calculated {calculated_duration}, provided {self.duration_minutes}")
        
        # Validate profit/loss calculation
        expected_pnl = self._calculate_expected_pnl()
        if abs(self.profit_loss - expected_pnl) > 0.01:  # Allow small floating point differences
            raise ValidationError(f"P&L mismatch: calculated {expected_pnl}, provided {self.profit_loss}")
    
    def _calculate_expected_pnl(self) -> float:
        """Calculate expected P&L based on prices and side."""
        if self.side == 'LONG':
            return (self.exit_price - self.entry_price) * self.quantity - self.commission
        else:  # SHORT
            return (self.entry_price - self.exit_price) * self.quantity - self.commission
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessedTrade':
        """Create instance from dictionary with validation."""
        try:
            return cls(**data)
        except TypeError as e:
            raise ValidationError(f"Missing required fields: {e}")
        except Exception as e:
            raise ValidationError(f"Failed to create trade: {e}")
    
    @property
    def is_profitable(self) -> bool:
        """Check if the trade was profitable."""
        return self.profit_loss > 0
    
    @property
    def return_percentage(self) -> float:
        """Calculate return as percentage of entry price."""
        if self.entry_price == 0:
            return 0.0
        return (self.profit_loss / (self.entry_price * self.quantity)) * 100
    
    @property
    def is_long(self) -> bool:
        """Check if this is a long trade."""
        return self.side == 'LONG'
    
    @property
    def is_short(self) -> bool:
        """Check if this is a short trade."""
        return self.side == 'SHORT'
    
    @property
    def gross_profit_loss(self) -> float:
        """Calculate gross P&L before commission."""
        return self.profit_loss + self.commission
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'trade_id': self.trade_id,
            'account_name': self.account_name,
            'symbol': self.symbol,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'side': self.side,
            'profit_loss': self.profit_loss,
            'commission': self.commission,
            'duration_minutes': self.duration_minutes,
            'hour_of_day': self.hour_of_day,
            'day_of_week': self.day_of_week,
            'entry_order_id': self.entry_order_id,
            'exit_order_id': self.exit_order_id
        }


@dataclass
class Account:
    """Trading account information with validation."""
    
    name: str  # IPS_TM_10, IPS_TM_13, etc.
    symbol: str  # NQ, FDAX, etc.
    total_trades: int
    first_trade_date: datetime
    last_trade_date: datetime
    is_active: bool
    
    def __post_init__(self):
        """Validate account data after initialization."""
        self._validate_account()
    
    def _validate_account(self):
        """Validate account data."""
        validator = TradingDataValidator()
        
        # Validate account name
        self.name = validator.validate_trade_account(self.name)
        
        # Validate symbol
        self.symbol = validator.validate_required_string(self.symbol, "Symbol", 20)
        
        # Validate trade count
        self.total_trades = validator.validate_non_negative_integer(self.total_trades, "TotalTrades")
        
        # Validate dates
        self.first_trade_date = validator.validate_datetime(self.first_trade_date, "FirstTradeDate")
        self.last_trade_date = validator.validate_datetime(self.last_trade_date, "LastTradeDate")
        
        # Validate date order
        if self.last_trade_date < self.first_trade_date:
            raise ValidationError("Last trade date cannot be before first trade date")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Account':
        """Create instance from dictionary with validation."""
        try:
            return cls(**data)
        except TypeError as e:
            raise ValidationError(f"Missing required fields: {e}")
        except Exception as e:
            raise ValidationError(f"Failed to create account: {e}")
    
    @property
    def trading_days(self) -> int:
        """Calculate number of trading days."""
        return (self.last_trade_date - self.first_trade_date).days + 1
    
    @property
    def trades_per_day(self) -> float:
        """Calculate average trades per day."""
        return self.total_trades / self.trading_days if self.trading_days > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'symbol': self.symbol,
            'total_trades': self.total_trades,
            'first_trade_date': self.first_trade_date.isoformat(),
            'last_trade_date': self.last_trade_date.isoformat(),
            'is_active': self.is_active
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for an account or strategy with validation."""
    
    account_name: str
    symbol: str
    period_start: datetime
    period_end: datetime
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    volatility: float
    largest_win: float
    largest_loss: float
    
    def __post_init__(self):
        """Validate performance metrics after initialization."""
        self._validate_metrics()
    
    def _validate_metrics(self):
        """Validate performance metrics."""
        validator = TradingDataValidator()
        
        # Validate account and symbol
        self.account_name = validator.validate_trade_account(self.account_name)
        self.symbol = validator.validate_required_string(self.symbol, "Symbol", 20)
        
        # Validate dates
        self.period_start = validator.validate_datetime(self.period_start, "PeriodStart")
        self.period_end = validator.validate_datetime(self.period_end, "PeriodEnd")
        
        if self.period_end < self.period_start:
            raise ValidationError("Period end cannot be before period start")
        
        # Validate trade counts
        self.total_trades = validator.validate_non_negative_integer(self.total_trades, "TotalTrades")
        self.winning_trades = validator.validate_non_negative_integer(self.winning_trades, "WinningTrades")
        self.losing_trades = validator.validate_non_negative_integer(self.losing_trades, "LosingTrades")
        
        # Validate trade count consistency
        if self.winning_trades + self.losing_trades != self.total_trades:
            raise ValidationError("Winning trades + losing trades must equal total trades")
        
        # Validate percentages and ratios
        if not (0.0 <= self.win_rate <= 1.0):
            raise ValidationError("Win rate must be between 0.0 and 1.0")
        
        # Validate calculated win rate
        expected_win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
        if abs(self.win_rate - expected_win_rate) > 0.001:
            raise ValidationError(f"Win rate mismatch: calculated {expected_win_rate}, provided {self.win_rate}")
        
        # Validate volatility and drawdown are non-negative
        if self.volatility < 0:
            raise ValidationError("Volatility cannot be negative")
        
        if self.max_drawdown > 0:
            raise ValidationError("Max drawdown should be negative or zero")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceMetrics':
        """Create instance from dictionary with validation."""
        try:
            return cls(**data)
        except TypeError as e:
            raise ValidationError(f"Missing required fields: {e}")
        except Exception as e:
            raise ValidationError(f"Failed to create performance metrics: {e}")
    
    @property
    def average_trade(self) -> float:
        """Calculate average profit/loss per trade."""
        return self.total_return / self.total_trades if self.total_trades > 0 else 0.0
    
    @property
    def expectancy(self) -> float:
        """Calculate expectancy (expected value per trade)."""
        if self.total_trades == 0:
            return 0.0
        return (self.win_rate * self.average_win) - ((1 - self.win_rate) * abs(self.average_loss))
    
    @property
    def recovery_factor(self) -> float:
        """Calculate recovery factor (total return / max drawdown)."""
        return abs(self.total_return / self.max_drawdown) if self.max_drawdown != 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'account_name': self.account_name,
            'symbol': self.symbol,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'total_return': self.total_return,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'average_win': self.average_win,
            'average_loss': self.average_loss,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'volatility': self.volatility,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss
        }


@dataclass
class TradingRecommendation:
    """Trading recommendation with supporting data and validation."""
    
    timestamp: datetime
    account_name: str
    symbol: str
    recommended_action: str  # 'TRADE', 'AVOID'
    confidence_score: float
    expected_return: float
    expected_risk: float
    reasoning: str
    hour_of_day: int
    day_of_week: int
    historical_win_rate: float
    avg_profit_this_time: float
    
    def __post_init__(self):
        """Validate recommendation data after initialization."""
        self._validate_recommendation()
    
    def _validate_recommendation(self):
        """Validate recommendation data."""
        validator = TradingDataValidator()
        
        # Validate account and symbol
        self.account_name = validator.validate_trade_account(self.account_name)
        self.symbol = validator.validate_required_string(self.symbol, "Symbol", 20)
        
        # Validate timestamp
        self.timestamp = validator.validate_datetime(self.timestamp, "Timestamp")
        
        # Validate action
        if self.recommended_action not in ['TRADE', 'AVOID']:
            raise ValidationError("Recommended action must be 'TRADE' or 'AVOID'")
        
        # Validate confidence score
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValidationError("Confidence score must be between 0.0 and 1.0")
        
        # Validate win rate
        if not (0.0 <= self.historical_win_rate <= 1.0):
            raise ValidationError("Historical win rate must be between 0.0 and 1.0")
        
        # Validate time fields
        if not (0 <= self.hour_of_day <= 23):
            raise ValidationError("Hour of day must be between 0 and 23")
        
        if not (0 <= self.day_of_week <= 6):
            raise ValidationError("Day of week must be between 0 and 6")
        
        # Validate reasoning
        self.reasoning = validator.validate_required_string(self.reasoning, "Reasoning", 1000)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingRecommendation':
        """Create instance from dictionary with validation."""
        try:
            return cls(**data)
        except TypeError as e:
            raise ValidationError(f"Missing required fields: {e}")
        except Exception as e:
            raise ValidationError(f"Failed to create recommendation: {e}")
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk-reward ratio."""
        return abs(self.expected_return / self.expected_risk) if self.expected_risk != 0 else 0.0
    
    @property
    def should_trade(self) -> bool:
        """Determine if recommendation suggests trading."""
        return self.recommended_action.upper() == 'TRADE'
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence recommendation."""
        return self.confidence_score >= 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'account_name': self.account_name,
            'symbol': self.symbol,
            'recommended_action': self.recommended_action,
            'confidence_score': self.confidence_score,
            'expected_return': self.expected_return,
            'expected_risk': self.expected_risk,
            'reasoning': self.reasoning,
            'hour_of_day': self.hour_of_day,
            'day_of_week': self.day_of_week,
            'historical_win_rate': self.historical_win_rate,
            'avg_profit_this_time': self.avg_profit_this_time
        }