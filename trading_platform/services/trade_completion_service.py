"""
Trade completion analysis and cleaning service for SierraChart data.
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime, date
from collections import defaultdict, deque
from dataclasses import dataclass

from ..models.sierra_chart import SierraChartTradeRecord
from ..utils.validators import ValidationError


@dataclass
class PositionState:
    """Represents the state of a position at a point in time."""
    account: str
    symbol: str
    date: date
    position_quantity: int
    last_update: datetime
    fills: List[SierraChartTradeRecord]
    is_complete: bool = False


@dataclass
class IncompleteTradeInfo:
    """Information about incomplete trades that need to be removed."""
    account: str
    symbol: str
    date: date
    position_quantity: int
    affected_fills: List[SierraChartTradeRecord]
    reason: str


class TradeCompletionAnalysisError(Exception):
    """Exception raised during trade completion analysis."""
    pass


class TradeCompletionService:
    """Service for analyzing and cleaning incomplete day trades."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the trade completion service."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Analysis statistics
        self.analysis_stats = {
            'total_records_analyzed': 0,
            'complete_positions': 0,
            'incomplete_positions': 0,
            'records_removed': 0,
            'accounts_processed': 0,
            'symbols_processed': 0,
            'trading_days_analyzed': 0
        }
        
        # Tracking for incomplete trades
        self.incomplete_trades: List[IncompleteTradeInfo] = []
    
    def analyze_and_clean_trades(self, records: List[SierraChartTradeRecord]) -> List[SierraChartTradeRecord]:
        """
        Analyze trades for completion and remove incomplete day trades.
        
        Args:
            records: List of SierraChart trade records to analyze
            
        Returns:
            List of records with incomplete trades removed
            
        Raises:
            TradeCompletionAnalysisError: If analysis fails
        """
        if not records:
            self.logger.warning("No records provided for trade completion analysis")
            return []
        
        self.logger.info(f"Starting trade completion analysis for {len(records)} records")
        
        try:
            # Reset statistics
            self._reset_analysis_stats()
            self.analysis_stats['total_records_analyzed'] = len(records)
            
            # Group records by account, symbol, and date
            grouped_records = self._group_records_by_account_symbol_date(records)
            
            # Analyze each group for position completion
            incomplete_record_ids = set()
            
            for (account, symbol, trade_date), group_records in grouped_records.items():
                self.logger.debug(f"Analyzing {account}/{symbol} on {trade_date}: {len(group_records)} records")
                
                # Analyze position completion for this group
                incomplete_ids = self._analyze_position_completion(account, symbol, trade_date, group_records)
                incomplete_record_ids.update(incomplete_ids)
            
            # Filter out incomplete trades
            clean_records = []
            for record in records:
                record_id = self._generate_record_id(record)
                if record_id not in incomplete_record_ids:
                    clean_records.append(record)
                else:
                    self.analysis_stats['records_removed'] += 1
            
            # Update final statistics
            self.analysis_stats['accounts_processed'] = len(set(r.trade_account for r in records))
            self.analysis_stats['symbols_processed'] = len(set(r.base_symbol for r in records))
            self.analysis_stats['trading_days_analyzed'] = len(grouped_records)
            
            self.logger.info(
                f"Trade completion analysis complete: "
                f"{len(clean_records)} clean records, "
                f"{self.analysis_stats['records_removed']} records removed, "
                f"{self.analysis_stats['incomplete_positions']} incomplete positions found"
            )
            
            return clean_records
            
        except Exception as e:
            raise TradeCompletionAnalysisError(f"Trade completion analysis failed: {e}")
    
    def _group_records_by_account_symbol_date(self, records: List[SierraChartTradeRecord]) -> Dict[Tuple[str, str, date], List[SierraChartTradeRecord]]:
        """
        Group records by account, symbol, and trading session date.
        Trading session runs from 18:00 to 17:00 next day (17:00 is the daily cutoff).
        
        Args:
            records: List of records to group
            
        Returns:
            Dictionary mapping (account, symbol, trading_session_date) to list of records
        """
        grouped = defaultdict(list)
        
        for record in records:
            # Determine trading session date based on 17:00 cutoff
            # If time is before 17:00, it belongs to current calendar day's session
            # If time is 17:00 or after, it belongs to next calendar day's session
            trading_session_date = self._get_trading_session_date(record.date_time)
            key = (record.trade_account, record.base_symbol, trading_session_date)
            grouped[key].append(record)
        
        # Sort records within each group by datetime
        for key in grouped:
            grouped[key].sort(key=lambda r: r.date_time)
        
        return dict(grouped)
    
    def _get_trading_session_date(self, dt: datetime) -> date:
        """
        Get the trading session date for a given datetime.
        Trading session runs from 18:00 to 16:59:59 next day (cutoff at 16:59:59).
        
        Args:
            dt: Datetime to get trading session date for
            
        Returns:
            Date representing the trading session
        """
        # Cutoff is at 16:59:59 - anything at 17:00:00 or after belongs to next session
        # If time is before 17:00:00, it belongs to current day's session
        if dt.hour < 17:
            return dt.date()
        else:
            # If time is 17:00:00 or after, it belongs to next day's session
            # Trading session restarts at 18:00
            from datetime import timedelta
            return (dt + timedelta(days=1)).date()
    
    def _analyze_position_completion(self, account: str, symbol: str, trade_date: date, 
                                   records: List[SierraChartTradeRecord]) -> Set[str]:
        """
        Analyze position completion for a specific account/symbol/date combination.
        
        Args:
            account: Trading account
            symbol: Base symbol (NQ, FDAX)
            trade_date: Trading date
            records: Records for this account/symbol/date
            
        Returns:
            Set of record IDs that should be removed due to incomplete positions
        """
        if not records:
            return set()
        
        # Find the final position at end of day
        final_position = records[-1].position_quantity  # Records are sorted by time
        
        if final_position == 0:
            # Position is complete
            self.analysis_stats['complete_positions'] += 1
            return set()  # No records to remove
        else:
            # Position is incomplete - mark all records for removal
            self.analysis_stats['incomplete_positions'] += 1
            
            # Create incomplete trade info
            incomplete_info = IncompleteTradeInfo(
                account=account,
                symbol=symbol,
                date=trade_date,
                position_quantity=final_position,
                affected_fills=records.copy(),
                reason=f"Position did not return to zero (final position: {final_position})"
            )
            self.incomplete_trades.append(incomplete_info)
            
            # Return IDs of all records in this incomplete position
            record_ids = {self._generate_record_id(record) for record in records}
            
            self.logger.warning(
                f"Incomplete position detected for {account}/{symbol} on {trade_date}: "
                f"final position {final_position}, removing {len(records)} records"
            )
            
            return record_ids
    
    def _calculate_expected_position(self, current_position: int, record: SierraChartTradeRecord) -> int:
        """
        Calculate expected position quantity after applying a fill.
        
        Args:
            current_position: Current position quantity
            record: Fill record to apply
            
        Returns:
            Expected position quantity after the fill
        """
        fill_quantity = record.filled_quantity
        
        if record.is_buy:
            if record.is_opening:
                # Buy to open: increase long position
                return current_position + fill_quantity
            else:
                # Buy to close: reduce short position
                return current_position + fill_quantity
        else:  # is_sell
            if record.is_opening:
                # Sell to open: increase short position (negative)
                return current_position - fill_quantity
            else:
                # Sell to close: reduce long position
                return current_position - fill_quantity
    
    def _generate_record_id(self, record: SierraChartTradeRecord) -> str:
        """
        Generate unique identifier for a record.
        
        Args:
            record: Record to generate ID for
            
        Returns:
            Unique identifier string
        """
        return f"{record.trade_account}_{record.internal_order_id}_{record.service_order_id}"
    
    def validate_position_consistency(self, records: List[SierraChartTradeRecord]) -> List[str]:
        """
        Validate position quantity consistency across records.
        
        Args:
            records: List of records to validate
            
        Returns:
            List of validation warnings
        """
        warnings = []
        
        # Group by account and symbol
        grouped = defaultdict(list)
        for record in records:
            key = (record.trade_account, record.base_symbol)
            grouped[key].append(record)
        
        for (account, symbol), group_records in grouped.items():
            # Sort by datetime
            group_records.sort(key=lambda r: r.date_time)
            
            # Track position and validate consistency
            expected_position = 0
            
            for i, record in enumerate(group_records):
                # Calculate expected position
                expected_position = self._calculate_expected_position(expected_position, record)
                
                # Compare with actual position
                if record.position_quantity != expected_position:
                    warnings.append(
                        f"Position inconsistency in {account}/{symbol} at record {i}: "
                        f"expected {expected_position}, got {record.position_quantity}"
                    )
                    # Reset expected to actual to continue validation
                    expected_position = record.position_quantity
        
        return warnings
    
    def get_incomplete_trades_summary(self) -> Dict:
        """
        Get summary of incomplete trades found during analysis.
        
        Returns:
            Dictionary with incomplete trades summary
        """
        if not self.incomplete_trades:
            return {
                'total_incomplete_positions': 0,
                'accounts_affected': [],
                'symbols_affected': [],
                'dates_affected': [],
                'total_records_affected': 0
            }
        
        accounts_affected = set()
        symbols_affected = set()
        dates_affected = set()
        total_records = 0
        
        for incomplete in self.incomplete_trades:
            accounts_affected.add(incomplete.account)
            symbols_affected.add(incomplete.symbol)
            dates_affected.add(incomplete.date)
            total_records += len(incomplete.affected_fills)
        
        return {
            'total_incomplete_positions': len(self.incomplete_trades),
            'accounts_affected': sorted(list(accounts_affected)),
            'symbols_affected': sorted(list(symbols_affected)),
            'dates_affected': sorted([d.isoformat() for d in dates_affected]),
            'total_records_affected': total_records,
            'incomplete_details': [
                {
                    'account': inc.account,
                    'symbol': inc.symbol,
                    'date': inc.date.isoformat(),
                    'final_position': inc.position_quantity,
                    'records_count': len(inc.affected_fills),
                    'reason': inc.reason
                }
                for inc in self.incomplete_trades
            ]
        }
    
    def get_analysis_statistics(self) -> Dict:
        """Get comprehensive analysis statistics."""
        stats = self.analysis_stats.copy()
        stats['incomplete_trades_summary'] = self.get_incomplete_trades_summary()
        return stats
    
    def _reset_analysis_stats(self):
        """Reset analysis statistics."""
        self.analysis_stats = {
            'total_records_analyzed': 0,
            'complete_positions': 0,
            'incomplete_positions': 0,
            'records_removed': 0,
            'accounts_processed': 0,
            'symbols_processed': 0,
            'trading_days_analyzed': 0
        }
        self.incomplete_trades.clear()
    
    def analyze_position_flow(self, records: List[SierraChartTradeRecord]) -> Dict:
        """
        Analyze position flow for debugging and validation purposes.
        
        Args:
            records: List of records to analyze
            
        Returns:
            Dictionary with position flow analysis
        """
        if not records:
            return {}
        
        # Group by account and symbol
        grouped = defaultdict(list)
        for record in records:
            key = (record.trade_account, record.base_symbol)
            grouped[key].append(record)
        
        flow_analysis = {}
        
        for (account, symbol), group_records in grouped.items():
            # Sort by datetime
            group_records.sort(key=lambda r: r.date_time)
            
            # Analyze position flow
            position_flow = []
            current_position = 0
            
            for record in group_records:
                expected_position = self._calculate_expected_position(current_position, record)
                
                flow_entry = {
                    'datetime': record.date_time.isoformat(),
                    'internal_order_id': record.internal_order_id,
                    'buy_sell': record.buy_sell,
                    'open_close': record.open_close,
                    'filled_quantity': record.filled_quantity,
                    'position_before': current_position,
                    'position_expected': expected_position,
                    'position_actual': record.position_quantity,
                    'position_consistent': (expected_position == record.position_quantity)
                }
                
                position_flow.append(flow_entry)
                current_position = record.position_quantity
            
            # Group by trading date
            daily_flows = defaultdict(list)
            for entry in position_flow:
                trade_date = datetime.fromisoformat(entry['datetime']).date()
                daily_flows[trade_date].append(entry)
            
            # Analyze each day
            daily_analysis = {}
            for trade_date, day_flow in daily_flows.items():
                start_position = day_flow[0]['position_before'] if day_flow else 0
                end_position = day_flow[-1]['position_actual'] if day_flow else 0
                
                daily_analysis[trade_date.isoformat()] = {
                    'start_position': start_position,
                    'end_position': end_position,
                    'is_complete': (end_position == 0),
                    'total_fills': len(day_flow),
                    'position_flow': day_flow
                }
            
            flow_analysis[f"{account}_{symbol}"] = {
                'account': account,
                'symbol': symbol,
                'total_records': len(group_records),
                'daily_analysis': daily_analysis
            }
        
        return flow_analysis
    
    def detect_orphaned_positions(self, records: List[SierraChartTradeRecord]) -> List[Dict]:
        """
        Detect positions that have opening trades but no corresponding closing trades.
        
        Args:
            records: List of records to analyze
            
        Returns:
            List of orphaned position information
        """
        orphaned_positions = []
        
        # Group by account, symbol, and date
        grouped = self._group_records_by_account_symbol_date(records)
        
        for (account, symbol, trade_date), group_records in grouped.items():
            # For complete trades, check if position returns to zero
            final_position = group_records[-1].position_quantity if group_records else 0
            
            if final_position != 0:
                # Position didn't return to zero - this is orphaned
                orphaned_positions.append({
                    'account': account,
                    'symbol': symbol,
                    'date': trade_date.isoformat(),
                    'internal_order_id': 'multiple',  # Could be multiple orders
                    'remaining_quantity': final_position,
                    'records': group_records
                })
        
        return orphaned_positions