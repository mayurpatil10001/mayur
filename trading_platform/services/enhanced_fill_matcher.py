"""
Enhanced fill matching service for handling complex trading scenarios.

This service addresses the limitations of the basic fill matcher by:
1. Supporting multi-day positions
2. Handling partial fills and complex order patterns
3. Tracking positions across time periods
4. NEVER creating synthetic fills - only matches actual fills
"""

import logging
from typing import List, Dict, Set, Optional, Tuple, DefaultDict
from datetime import datetime, date, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
import uuid

from ..models.sierra_chart import SierraChartTradeRecord
from ..models.trading import ProcessedTrade
from ..utils.validators import ValidationError


@dataclass
class PositionTracker:
    """Tracks position state across time periods."""
    account: str
    symbol: str
    current_quantity: int = 0
    average_price: float = 0.0
    first_fill_time: Optional[datetime] = None
    last_fill_time: Optional[datetime] = None
    fills: List[SierraChartTradeRecord] = field(default_factory=list)
    
    def add_fill(self, fill: SierraChartTradeRecord):
        """Add a fill to this position tracker."""
        self.fills.append(fill)
        
        # Update timing
        if self.first_fill_time is None or fill.date_time < self.first_fill_time:
            self.first_fill_time = fill.date_time
        if self.last_fill_time is None or fill.date_time > self.last_fill_time:
            self.last_fill_time = fill.date_time
        
        # Update position
        if fill.is_buy:
            new_quantity = self.current_quantity + fill.filled_quantity
            if self.current_quantity >= 0:  # Adding to long or starting long
                self.average_price = (
                    (self.average_price * self.current_quantity + fill.fill_price * fill.filled_quantity) 
                    / new_quantity
                ) if new_quantity != 0 else 0.0
            else:  # Covering short
                if new_quantity >= 0:  # Fully covered or flipped to long
                    self.average_price = fill.fill_price if new_quantity > 0 else 0.0
        else:  # Sell
            new_quantity = self.current_quantity - fill.filled_quantity
            if self.current_quantity <= 0:  # Adding to short or starting short
                self.average_price = (
                    (abs(self.average_price) * abs(self.current_quantity) + fill.fill_price * fill.filled_quantity) 
                    / abs(new_quantity)
                ) if new_quantity != 0 else 0.0
            else:  # Selling long
                if new_quantity <= 0:  # Fully sold or flipped to short
                    self.average_price = fill.fill_price if new_quantity < 0 else 0.0
        
        self.current_quantity = new_quantity
    
    def is_flat(self) -> bool:
        """Check if position is flat (zero quantity)."""
        return self.current_quantity == 0
    
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.current_quantity > 0
    
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.current_quantity < 0


@dataclass
class TradeCandidate:
    """Represents a potential trade match."""
    opening_fills: List[SierraChartTradeRecord]
    closing_fills: List[SierraChartTradeRecord]
    entry_price: float
    exit_price: float
    quantity: int
    side: str
    confidence_score: float  # 0.0 to 1.0, higher is better match


class EnhancedFillMatchingError(Exception):
    """Exception raised during enhanced fill matching."""
    pass


class EnhancedFillMatcher:
    """Enhanced fill matching service for complex trading scenarios."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the enhanced fill matcher."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Configuration
        self.config = {
            'max_position_days': 30,  # Maximum days to track a position
            'min_trade_confidence': 0.5,  # Minimum confidence to create a trade
            'strict_day_trading': False,  # Require positions to close same day
            'commission_per_contract': 2.50  # Default commission rate
        }
        
        # State tracking
        self.position_trackers: Dict[Tuple[str, str], PositionTracker] = {}  # (account, symbol) -> tracker
        self.processed_trades: List[ProcessedTrade] = []
        self.unmatched_fills: List[SierraChartTradeRecord] = []
        
        # Statistics
        self.stats = {
            'total_fills_processed': 0,
            'trades_generated': 0,
            'unmatched_fills': 0,
            'position_trackers_created': 0,
            'multi_day_positions': 0
        }
    
    def process_fills(self, fills: List[SierraChartTradeRecord]) -> Tuple[List[ProcessedTrade], List[SierraChartTradeRecord]]:
        """
        Process fills using enhanced matching algorithm.
        
        Args:
            fills: List of SierraChart fill records
            
        Returns:
            Tuple of (processed trades, unmatched fills)
        """
        if not fills:
            return [], []
        
        self.logger.info(f"Starting enhanced fill matching for {len(fills)} fills")
        
        # Reset state
        self._reset_state()
        self.stats['total_fills_processed'] = len(fills)
        
        # Sort fills by datetime to process chronologically
        sorted_fills = sorted(fills, key=lambda f: f.date_time)
        
        # Process fills chronologically to build position tracking
        for fill in sorted_fills:
            self._process_fill(fill)
        
        # Generate trades from position history
        self._generate_trades_from_positions()
        
        # Update final statistics
        self.stats['trades_generated'] = len(self.processed_trades)
        self.stats['unmatched_fills'] = len(self.unmatched_fills)
        
        self.logger.info(
            f"Enhanced fill matching complete: "
            f"{len(self.processed_trades)} trades generated, "
            f"{len(self.unmatched_fills)} unmatched fills"
        )
        
        return self.processed_trades.copy(), self.unmatched_fills.copy()
    
    def _reset_state(self):
        """Reset internal state for new processing run."""
        self.position_trackers.clear()
        self.processed_trades.clear()
        self.unmatched_fills.clear()
        
        self.stats = {
            'total_fills_processed': 0,
            'trades_generated': 0,
            'unmatched_fills': 0,
            'position_trackers_created': 0,
            'multi_day_positions': 0
        }
    
    def _process_fill(self, fill: SierraChartTradeRecord):
        """
        Process a single fill and update position tracking.
        
        Args:
            fill: Fill to process
        """
        key = (fill.trade_account, fill.base_symbol)
        
        # Get or create position tracker
        if key not in self.position_trackers:
            self.position_trackers[key] = PositionTracker(
                account=fill.trade_account,
                symbol=fill.base_symbol
            )
            self.stats['position_trackers_created'] += 1
        
        tracker = self.position_trackers[key]
        
        # Check if this creates a multi-day position
        if tracker.last_fill_time and fill.date_time.date() != tracker.last_fill_time.date():
            self.stats['multi_day_positions'] += 1
        
        # Add fill to tracker
        tracker.add_fill(fill)
        
        self.logger.debug(
            f"Processed fill for {key}: {fill.buy_sell} {fill.filled_quantity} @ {fill.fill_price}, "
            f"position now: {tracker.current_quantity}"
        )
    
    def _generate_trades_from_positions(self):
        """Generate trades from position tracking history."""
        for key, tracker in self.position_trackers.items():
            if not tracker.fills:
                continue
            
            self.logger.debug(f"Generating trades for {key}: {len(tracker.fills)} fills")
            
            # Analyze fill sequence to identify complete trades
            trades = self._extract_trades_from_fills(tracker.fills, tracker.account, tracker.symbol)
            self.processed_trades.extend(trades)
    
    def _extract_trades_from_fills(self, fills: List[SierraChartTradeRecord], 
                                 account: str, symbol: str) -> List[ProcessedTrade]:
        """
        Extract complete trades from a sequence of fills.
        
        Args:
            fills: Chronologically sorted fills for an account/symbol
            account: Trading account
            symbol: Base symbol
            
        Returns:
            List of processed trades
        """
        trades = []
        position_quantity = 0
        position_fills = []  # Fills that contribute to current position
        
        for fill in fills:
            position_fills.append(fill)
            
            # Update position quantity
            if fill.is_buy:
                position_quantity += fill.filled_quantity
            else:
                position_quantity -= fill.filled_quantity
            
            # Check if position is flat (complete trade)
            if position_quantity == 0 and len(position_fills) >= 2:
                # We have a complete round trip
                trade = self._create_trade_from_fills(position_fills, account, symbol)
                if trade:
                    trades.append(trade)
                    self.logger.debug(f"Created complete trade: {trade.trade_id}")
                
                # Reset for next trade
                position_fills = []
            
            # Handle orphaned closing fills (position goes flat but we started with a position)
            elif position_quantity == 0 and len(position_fills) == 1 and not fill.is_opening:
                # This is likely a closing fill without a matching opening fill
                # NEVER create synthetic fills - add to unmatched instead
                self.logger.debug(f"Orphaned closing fill found - adding to unmatched: {fill.internal_order_id}")
                self.unmatched_fills.append(fill)
                position_fills = []
        
        # Handle remaining position fills as unmatched
        if position_fills:
            self.logger.debug(f"Adding {len(position_fills)} remaining fills to unmatched")
            self.unmatched_fills.extend(position_fills)
        
        return trades
    
    def _create_trade_from_fills(self, fills: List[SierraChartTradeRecord], 
                               account: str, symbol: str) -> Optional[ProcessedTrade]:
        """
        Create a processed trade from a sequence of fills.
        
        Args:
            fills: Fills that make up the complete trade
            account: Trading account
            symbol: Base symbol
            
        Returns:
            ProcessedTrade or None if creation fails
        """
        if len(fills) < 2:
            return None
        
        try:
            # Separate opening and closing fills
            opening_fills = []
            closing_fills = []
            
            position_qty = 0
            for fill in fills:
                if fill.is_buy:
                    position_qty += fill.filled_quantity
                else:
                    position_qty -= fill.filled_quantity
                
                # Determine if this is opening or closing based on position direction
                if len(opening_fills) == 0 or (
                    (position_qty > 0 and fill.is_buy) or 
                    (position_qty < 0 and not fill.is_buy)
                ):
                    opening_fills.append(fill)
                else:
                    closing_fills.append(fill)
            
            if not opening_fills or not closing_fills:
                # Fallback: split fills in half
                mid_point = len(fills) // 2
                opening_fills = fills[:mid_point]
                closing_fills = fills[mid_point:]
            
            # Calculate trade metrics
            entry_time = min(f.date_time for f in opening_fills)
            exit_time = max(f.date_time for f in closing_fills)
            
            # Calculate weighted average prices
            total_entry_qty = sum(f.filled_quantity for f in opening_fills)
            total_exit_qty = sum(f.filled_quantity for f in closing_fills)
            
            entry_price = sum(f.fill_price * f.filled_quantity for f in opening_fills) / total_entry_qty
            exit_price = sum(f.fill_price * f.filled_quantity for f in closing_fills) / total_exit_qty
            
            # Use the smaller quantity (handles partial fills)
            quantity = min(total_entry_qty, total_exit_qty)
            
            # Determine side
            first_opening = opening_fills[0]
            side = "LONG" if first_opening.is_buy else "SHORT"
            
            # Calculate P&L
            if side == "LONG":
                gross_pnl = (exit_price - entry_price) * quantity
            else:
                gross_pnl = (entry_price - exit_price) * quantity
            
            commission = self.config['commission_per_contract'] * quantity * 2  # Round trip
            profit_loss = gross_pnl - commission
            
            # Calculate duration
            duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
            
            # Generate trade ID
            trade_id = f"{account}_{symbol}_{entry_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Create trade
            trade = ProcessedTrade(
                trade_id=trade_id,
                account_name=account,
                symbol=symbol,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit_loss,
                commission=commission,
                duration_minutes=duration_minutes,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=opening_fills[0].internal_order_id,
                exit_order_id=closing_fills[0].internal_order_id
            )
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Failed to create trade from fills: {e}")
            return None
    

    
    def get_statistics(self) -> Dict:
        """Get comprehensive matching statistics."""
        return {
            **self.stats,
            'position_trackers': len(self.position_trackers),
            'success_rate': self.stats['trades_generated'] / max(1, self.stats['total_fills_processed'] // 2)
        }
    
    def get_position_summary(self) -> Dict:
        """Get summary of current position states."""
        summary = {}
        for (account, symbol), tracker in self.position_trackers.items():
            summary[f"{account}_{symbol}"] = {
                'current_quantity': tracker.current_quantity,
                'average_price': tracker.average_price,
                'total_fills': len(tracker.fills),
                'first_fill': tracker.first_fill_time.isoformat() if tracker.first_fill_time else None,
                'last_fill': tracker.last_fill_time.isoformat() if tracker.last_fill_time else None,
                'is_flat': tracker.is_flat(),
                'position_type': 'LONG' if tracker.is_long() else 'SHORT' if tracker.is_short() else 'FLAT'
            }
        return summary
    
    def configure(self, **kwargs):
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                self.logger.info(f"Updated config: {key} = {value}")
            else:
                self.logger.warning(f"Unknown config parameter: {key}")