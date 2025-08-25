"""
Processed trade generation service for converting SierraChart fills into complete round-trip trades.
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, date
from collections import defaultdict, deque
from dataclasses import dataclass
import uuid

from ..models.sierra_chart import SierraChartTradeRecord
from ..models.trading import ProcessedTrade
from ..utils.validators import ValidationError
from .enhanced_fill_matcher import EnhancedFillMatcher


@dataclass
class TradeMatchingState:
    """State for tracking trade matching process."""
    account: str
    symbol: str
    date: date
    open_positions: Dict[str, List[SierraChartTradeRecord]]  # position_id -> list of fills
    completed_trades: List[ProcessedTrade]
    unmatched_fills: List[SierraChartTradeRecord]
    position_quantity: int


class ProcessedTradeGenerationError(Exception):
    """Exception raised during processed trade generation."""
    pass


class ProcessedTradeService:
    """Service for generating processed trades from SierraChart fills."""
    
    def __init__(self, logger: Optional[logging.Logger] = None, use_enhanced_matcher: bool = True):
        """Initialize the processed trade service."""
        self.logger = logger or logging.getLogger(__name__)
        self.use_enhanced_matcher = use_enhanced_matcher
        
        # Initialize enhanced matcher if requested
        if self.use_enhanced_matcher:
            self.enhanced_matcher = EnhancedFillMatcher(logger=self.logger)
        
        # Generation statistics
        self.generation_stats = {
            'total_fills_processed': 0,
            'complete_trades_generated': 0,
            'unmatched_fills': 0,
            'accounts_processed': 0,
            'symbols_processed': 0,
            'trading_days_processed': 0,
            'total_profit_loss': 0.0,
            'total_commission': 0.0
        }
        
        # Generated trades
        self.processed_trades: List[ProcessedTrade] = []
        self.unmatched_fills: List[SierraChartTradeRecord] = []
    
    def generate_processed_trades(self, fills: List[SierraChartTradeRecord]) -> List[ProcessedTrade]:
        """
        Generate processed trades from SierraChart fills.
        
        Args:
            fills: List of SierraChart fill records
            
        Returns:
            List of processed trades (complete round-trips)
            
        Raises:
            ProcessedTradeGenerationError: If generation fails
        """
        if not fills:
            self.logger.warning("No fills provided for processed trade generation")
            return []
        
        self.logger.info(f"Starting processed trade generation for {len(fills)} fills (enhanced_matcher={self.use_enhanced_matcher})")
        
        try:
            # Reset state
            self._reset_generation_state()
            self.generation_stats['total_fills_processed'] = len(fills)
            
            if self.use_enhanced_matcher:
                # Use enhanced fill matcher
                self.processed_trades, self.unmatched_fills = self.enhanced_matcher.process_fills(fills)
                
                # Update statistics from enhanced matcher
                enhanced_stats = self.enhanced_matcher.get_statistics()
                self.generation_stats.update({
                    'complete_trades_generated': enhanced_stats['trades_generated'],
                    'unmatched_fills': enhanced_stats['unmatched_fills'],
                    'accounts_processed': len(set(f.trade_account for f in fills)),
                    'symbols_processed': len(set(f.base_symbol for f in fills)),
                    'multi_day_positions': enhanced_stats.get('multi_day_positions', 0)
                })
            else:
                # Use legacy fill matcher
                grouped_fills = self._group_fills_by_account_symbol_date(fills)
                
                # Process each group
                for (account, symbol, trade_date), group_fills in grouped_fills.items():
                    self.logger.debug(f"Processing {account}/{symbol} on {trade_date}: {len(group_fills)} fills")
                    
                    # Generate trades for this group
                    group_trades, group_unmatched = self._process_fills_group(account, symbol, trade_date, group_fills)
                    
                    self.processed_trades.extend(group_trades)
                    self.unmatched_fills.extend(group_unmatched)
                
                # Update final statistics
                self.generation_stats['complete_trades_generated'] = len(self.processed_trades)
                self.generation_stats['unmatched_fills'] = len(self.unmatched_fills)
                self.generation_stats['accounts_processed'] = len(set(f.trade_account for f in fills))
                self.generation_stats['symbols_processed'] = len(set(f.base_symbol for f in fills))
                self.generation_stats['trading_days_processed'] = len(grouped_fills)
            
            # Calculate totals
            self.generation_stats['total_profit_loss'] = sum(t.profit_loss for t in self.processed_trades)
            self.generation_stats['total_commission'] = sum(t.commission for t in self.processed_trades)
            
            self.logger.info(
                f"Processed trade generation complete: "
                f"{len(self.processed_trades)} trades generated, "
                f"{len(self.unmatched_fills)} unmatched fills"
            )
            
            return self.processed_trades.copy()
            
        except Exception as e:
            raise ProcessedTradeGenerationError(f"Processed trade generation failed: {e}")
    
    def _group_fills_by_account_symbol_date(self, fills: List[SierraChartTradeRecord]) -> Dict[Tuple[str, str, date], List[SierraChartTradeRecord]]:
        """
        Group fills by account, symbol, and trading date.
        
        Args:
            fills: List of fills to group
            
        Returns:
            Dictionary mapping (account, symbol, date) to list of fills
        """
        grouped = defaultdict(list)
        
        for fill in fills:
            key = (fill.trade_account, fill.base_symbol, fill.date_time.date())
            grouped[key].append(fill)
        
        # Sort fills within each group by datetime
        for key in grouped:
            grouped[key].sort(key=lambda f: f.date_time)
        
        return dict(grouped)
    
    def _process_fills_group(self, account: str, symbol: str, trade_date: date, 
                           fills: List[SierraChartTradeRecord]) -> Tuple[List[ProcessedTrade], List[SierraChartTradeRecord]]:
        """
        Process a group of fills for a specific account/symbol/date.
        
        Args:
            account: Trading account
            symbol: Base symbol
            trade_date: Trading date
            fills: Fills for this group
            
        Returns:
            Tuple of (completed trades, unmatched fills)
        """
        if not fills:
            return [], []
        
        # Initialize matching state
        state = TradeMatchingState(
            account=account,
            symbol=symbol,
            date=trade_date,
            open_positions={},
            completed_trades=[],
            unmatched_fills=[],
            position_quantity=0
        )
        
        # Process fills in chronological order
        for fill in fills:
            self._process_single_fill(fill, state)
        
        # Handle any remaining open positions as unmatched
        for position_id, position_fills in state.open_positions.items():
            state.unmatched_fills.extend(position_fills)
        
        return state.completed_trades, state.unmatched_fills
    
    def _process_single_fill(self, fill: SierraChartTradeRecord, state: TradeMatchingState):
        """
        Process a single fill and update matching state.
        
        Args:
            fill: Fill to process
            state: Current matching state
        """
        if fill.is_opening:
            # Opening fill - start new position
            self._handle_opening_fill(fill, state)
        else:
            # Closing fill - try to match with existing position
            self._handle_closing_fill(fill, state)
    
    def _handle_opening_fill(self, fill: SierraChartTradeRecord, state: TradeMatchingState):
        """
        Handle an opening fill.
        
        Args:
            fill: Opening fill
            state: Current matching state
        """
        # Create new position
        position_id = fill.internal_order_id
        
        if position_id in state.open_positions:
            # Add to existing position (partial fills)
            state.open_positions[position_id].append(fill)
        else:
            # New position
            state.open_positions[position_id] = [fill]
        
        # Update position quantity
        if fill.is_buy:
            state.position_quantity += fill.filled_quantity
        else:
            state.position_quantity -= fill.filled_quantity
    
    def _handle_closing_fill(self, fill: SierraChartTradeRecord, state: TradeMatchingState):
        """
        Handle a closing fill.
        
        Args:
            fill: Closing fill
            state: Current matching state
        """
        # Try to find matching opening position
        parent_id = fill.parent_internal_order_id or fill.internal_order_id
        
        if parent_id in state.open_positions:
            # Found matching opening position
            opening_fills = state.open_positions[parent_id]
            
            # Create completed trade
            trade = self._create_processed_trade(opening_fills, [fill], state)
            if trade:
                state.completed_trades.append(trade)
                # Remove matched position only if trade was successfully created
                del state.open_positions[parent_id]
            else:
                # Trade creation failed - add closing fill to unmatched
                state.unmatched_fills.append(fill)
            
            # Update position quantity
            if fill.is_buy:
                state.position_quantity += fill.filled_quantity
            else:
                state.position_quantity -= fill.filled_quantity
        else:
            # No matching opening position found
            self.logger.warning(
                f"No matching opening position found for closing fill {fill.internal_order_id} "
                f"(parent: {parent_id}) in {state.account}/{state.symbol}"
            )
            state.unmatched_fills.append(fill)
    
    def _create_processed_trade(self, opening_fills: List[SierraChartTradeRecord], 
                              closing_fills: List[SierraChartTradeRecord],
                              state: TradeMatchingState) -> Optional[ProcessedTrade]:
        """
        Create a processed trade from opening and closing fills.
        
        Args:
            opening_fills: List of opening fills
            closing_fills: List of closing fills
            state: Current matching state
            
        Returns:
            ProcessedTrade or None if creation fails
        """
        try:
            # Calculate aggregated values
            entry_time = min(f.date_time for f in opening_fills)
            exit_time = max(f.date_time for f in closing_fills)
            
            # Calculate weighted average prices
            total_entry_quantity = sum(f.filled_quantity for f in opening_fills)
            total_exit_quantity = sum(f.filled_quantity for f in closing_fills)
            
            if total_entry_quantity != total_exit_quantity:
                self.logger.warning(
                    f"Quantity mismatch in trade: entry={total_entry_quantity}, exit={total_exit_quantity}"
                )
                return None
            
            # Weighted average entry price
            entry_price = sum(f.fill_price * f.filled_quantity for f in opening_fills) / total_entry_quantity
            
            # Weighted average exit price
            exit_price = sum(f.fill_price * f.filled_quantity for f in closing_fills) / total_exit_quantity
            
            # Determine trade side
            first_opening = opening_fills[0]
            side = "LONG" if first_opening.is_buy else "SHORT"
            
            # Calculate commission (simplified - could be enhanced)
            commission = self._calculate_commission(opening_fills + closing_fills)
            
            # Calculate profit/loss (net of commission)
            if side == "LONG":
                gross_pnl = (exit_price - entry_price) * total_entry_quantity
            else:
                gross_pnl = (entry_price - exit_price) * total_entry_quantity
            
            profit_loss = gross_pnl - commission
            
            # Calculate duration
            duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
            
            # Extract temporal features
            hour_of_day = entry_time.hour
            day_of_week = entry_time.weekday()  # 0=Monday, 6=Sunday
            
            # Generate unique trade ID
            trade_id = f"{state.account}_{state.symbol}_{entry_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Get order IDs
            entry_order_id = opening_fills[0].internal_order_id
            exit_order_id = closing_fills[0].internal_order_id
            
            # Create processed trade
            trade = ProcessedTrade(
                trade_id=trade_id,
                account_name=state.account,
                symbol=state.symbol,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=total_entry_quantity,
                side=side,
                profit_loss=profit_loss,
                commission=commission,
                duration_minutes=duration_minutes,
                hour_of_day=hour_of_day,
                day_of_week=day_of_week,
                entry_order_id=entry_order_id,
                exit_order_id=exit_order_id
            )
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Failed to create processed trade: {e}")
            return None
    
    def _calculate_commission(self, fills: List[SierraChartTradeRecord]) -> float:
        """
        Calculate commission for fills.
        
        Args:
            fills: List of fills
            
        Returns:
            Total commission
        """
        # Simplified commission calculation
        # In practice, this would depend on broker commission structure
        commission_per_contract = 2.50  # Example commission rate
        total_quantity = sum(f.filled_quantity for f in fills)
        return commission_per_contract * total_quantity
    
    def get_generation_statistics(self) -> Dict:
        """Get comprehensive generation statistics."""
        return self.generation_stats.copy()
    
    def get_processed_trades(self) -> List[ProcessedTrade]:
        """Get generated processed trades."""
        return self.processed_trades.copy()
    
    def get_unmatched_fills(self) -> List[SierraChartTradeRecord]:
        """Get unmatched fills."""
        return self.unmatched_fills.copy()
    
    def _reset_generation_state(self):
        """Reset generation state for new generation run."""
        self.generation_stats = {
            'total_fills_processed': 0,
            'complete_trades_generated': 0,
            'unmatched_fills': 0,
            'accounts_processed': 0,
            'symbols_processed': 0,
            'trading_days_processed': 0,
            'total_profit_loss': 0.0,
            'total_commission': 0.0
        }
        
        self.processed_trades.clear()
        self.unmatched_fills.clear()
    
    def analyze_trade_patterns(self) -> Dict:
        """
        Analyze patterns in generated trades.
        
        Returns:
            Dictionary with pattern analysis
        """
        if not self.processed_trades:
            return {}
        
        # Analyze by hour of day
        hourly_stats = defaultdict(lambda: {'count': 0, 'total_pnl': 0.0, 'wins': 0})
        for trade in self.processed_trades:
            hour = trade.hour_of_day
            hourly_stats[hour]['count'] += 1
            hourly_stats[hour]['total_pnl'] += trade.profit_loss
            if trade.profit_loss > 0:
                hourly_stats[hour]['wins'] += 1
        
        # Calculate hourly win rates and average P&L
        hourly_analysis = {}
        for hour, stats in hourly_stats.items():
            hourly_analysis[hour] = {
                'trade_count': stats['count'],
                'total_pnl': stats['total_pnl'],
                'average_pnl': stats['total_pnl'] / stats['count'],
                'win_rate': stats['wins'] / stats['count'],
                'wins': stats['wins'],
                'losses': stats['count'] - stats['wins']
            }
        
        # Analyze by day of week
        daily_stats = defaultdict(lambda: {'count': 0, 'total_pnl': 0.0, 'wins': 0})
        for trade in self.processed_trades:
            day = trade.day_of_week
            daily_stats[day]['count'] += 1
            daily_stats[day]['total_pnl'] += trade.profit_loss
            if trade.profit_loss > 0:
                daily_stats[day]['wins'] += 1
        
        # Calculate daily win rates and average P&L
        daily_analysis = {}
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day, stats in daily_stats.items():
            daily_analysis[day_names[day]] = {
                'trade_count': stats['count'],
                'total_pnl': stats['total_pnl'],
                'average_pnl': stats['total_pnl'] / stats['count'],
                'win_rate': stats['wins'] / stats['count'],
                'wins': stats['wins'],
                'losses': stats['count'] - stats['wins']
            }
        
        # Overall statistics
        total_trades = len(self.processed_trades)
        winning_trades = len([t for t in self.processed_trades if t.profit_loss > 0])
        losing_trades = total_trades - winning_trades
        
        total_pnl = sum(t.profit_loss for t in self.processed_trades)
        total_commission = sum(t.commission for t in self.processed_trades)
        net_pnl = total_pnl - total_commission
        
        average_duration = sum(t.duration_minutes for t in self.processed_trades) / total_trades
        
        return {
            'overall_stats': {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': winning_trades / total_trades,
                'total_pnl': total_pnl,
                'total_commission': total_commission,
                'net_pnl': net_pnl,
                'average_pnl_per_trade': total_pnl / total_trades,
                'average_duration_minutes': average_duration
            },
            'hourly_analysis': hourly_analysis,
            'daily_analysis': daily_analysis,
            'side_analysis': self._analyze_by_side(),
            'duration_analysis': self._analyze_by_duration()
        }
    
    def _analyze_by_side(self) -> Dict:
        """Analyze trades by side (LONG vs SHORT)."""
        side_stats = defaultdict(lambda: {'count': 0, 'total_pnl': 0.0, 'wins': 0})
        
        for trade in self.processed_trades:
            side = trade.side
            side_stats[side]['count'] += 1
            side_stats[side]['total_pnl'] += trade.profit_loss
            if trade.profit_loss > 0:
                side_stats[side]['wins'] += 1
        
        side_analysis = {}
        for side, stats in side_stats.items():
            if stats['count'] > 0:
                side_analysis[side] = {
                    'trade_count': stats['count'],
                    'total_pnl': stats['total_pnl'],
                    'average_pnl': stats['total_pnl'] / stats['count'],
                    'win_rate': stats['wins'] / stats['count'],
                    'wins': stats['wins'],
                    'losses': stats['count'] - stats['wins']
                }
        
        return side_analysis
    
    def _analyze_by_duration(self) -> Dict:
        """Analyze trades by duration buckets."""
        duration_buckets = {
            '0-5min': (0, 5),
            '5-15min': (5, 15),
            '15-30min': (15, 30),
            '30-60min': (30, 60),
            '1-2hr': (60, 120),
            '2hr+': (120, float('inf'))
        }
        
        bucket_stats = defaultdict(lambda: {'count': 0, 'total_pnl': 0.0, 'wins': 0})
        
        for trade in self.processed_trades:
            duration = trade.duration_minutes
            
            for bucket_name, (min_dur, max_dur) in duration_buckets.items():
                if min_dur <= duration < max_dur:
                    bucket_stats[bucket_name]['count'] += 1
                    bucket_stats[bucket_name]['total_pnl'] += trade.profit_loss
                    if trade.profit_loss > 0:
                        bucket_stats[bucket_name]['wins'] += 1
                    break
        
        duration_analysis = {}
        for bucket, stats in bucket_stats.items():
            if stats['count'] > 0:
                duration_analysis[bucket] = {
                    'trade_count': stats['count'],
                    'total_pnl': stats['total_pnl'],
                    'average_pnl': stats['total_pnl'] / stats['count'],
                    'win_rate': stats['wins'] / stats['count'],
                    'wins': stats['wins'],
                    'losses': stats['count'] - stats['wins']
                }
        
        return duration_analysis
    
    def export_trades_to_dict(self) -> List[Dict]:
        """
        Export processed trades to list of dictionaries for serialization.
        
        Returns:
            List of trade dictionaries
        """
        return [
            {
                'trade_id': trade.trade_id,
                'account_name': trade.account_name,
                'symbol': trade.symbol,
                'entry_time': trade.entry_time.isoformat(),
                'exit_time': trade.exit_time.isoformat(),
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'side': trade.side,
                'profit_loss': trade.profit_loss,
                'commission': trade.commission,
                'duration_minutes': trade.duration_minutes,
                'hour_of_day': trade.hour_of_day,
                'day_of_week': trade.day_of_week
            }
            for trade in self.processed_trades
        ]
    
    def get_enhanced_statistics(self) -> Dict:
        """
        Get enhanced statistics from the enhanced matcher.
        
        Returns:
            Enhanced statistics dictionary or empty dict if not using enhanced matcher
        """
        if self.use_enhanced_matcher and hasattr(self, 'enhanced_matcher'):
            return self.enhanced_matcher.get_statistics()
        return {}
    
    def get_position_summary(self) -> Dict:
        """
        Get position summary from the enhanced matcher.
        
        Returns:
            Position summary dictionary or empty dict if not using enhanced matcher
        """
        if self.use_enhanced_matcher and hasattr(self, 'enhanced_matcher'):
            return self.enhanced_matcher.get_position_summary()
        return {}
    
    def get_synthetic_fills(self) -> List[SierraChartTradeRecord]:
        """
        Get synthetic fills created by the enhanced matcher.
        
        Returns:
            Empty list since synthetic fills are NEVER allowed
        """
        # Synthetic fills are NEVER created - always return empty list
        return []
    
    def configure_enhanced_matcher(self, **kwargs):
        """
        Configure the enhanced matcher parameters.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        if self.use_enhanced_matcher and hasattr(self, 'enhanced_matcher'):
            self.enhanced_matcher.configure(**kwargs)
            self.logger.info(f"Enhanced matcher configured with: {kwargs}")
        else:
            self.logger.warning("Enhanced matcher not available for configuration")