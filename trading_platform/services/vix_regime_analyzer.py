"""
VIX Data Integration and Regime Classification Service

This service handles VIX data fetching, volatility regime classification,
and synchronization with trade data for advanced time-bin analytics.

Requirements: 12.1, 12.2, 12.5
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from loguru import logger

from .market_data_ingestion import MarketDataIngestion, MarketDataSeries, MarketDataValidationError
from ..models.time_bin_analytics import MarketData, RegimePerformance
from ..models.database import ProcessedTrade
from ..database.connection import get_db_session


class VolatilityRegime(Enum):
    """VIX volatility regime classifications."""
    LOW = "Low"          # VIX < 15
    MEDIUM = "Medium"    # VIX 15-25
    HIGH = "High"        # VIX > 25


@dataclass
class RegimeClassification:
    """Container for regime classification result."""
    date: datetime
    vix_level: float
    regime: VolatilityRegime
    regime_duration_days: int  # How long in current regime


@dataclass
class RegimeTransition:
    """Container for regime transition information."""
    transition_date: datetime
    from_regime: VolatilityRegime
    to_regime: VolatilityRegime
    trigger_vix_level: float
    days_in_previous_regime: int


@dataclass
class TradeRegimeAlignment:
    """Container for trade-regime alignment data."""
    trade_timestamp: datetime
    entry_price: float
    vix_level: float
    regime: VolatilityRegime
    days_since_regime_start: int
    trade_pnl: float


class VIXDataIntegration:
    """
    Service for VIX data integration and volatility regime classification.
    
    This class handles:
    - VIX data fetching using existing market data infrastructure
    - Volatility regime classification (Low <15, Medium 15-25, High >25)
    - Trade-VIX synchronization for regime-based performance analysis
    - Regime transition detection and analysis
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the VIX data integration service."""
        self.db_session = db_session or get_db_session()
        self.market_data_service = MarketDataIngestion(db_session=self.db_session)
        
        # Regime thresholds as per requirements
        self.regime_thresholds = {
            'low_upper': 15.0,      # VIX < 15 = Low
            'medium_upper': 25.0    # VIX 15-25 = Medium, VIX > 25 = High
        }
    
    def fetch_vix_data(self, start_date: datetime, end_date: datetime) -> MarketDataSeries:
        """
        Fetch VIX volatility data with comprehensive error handling.
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            MarketDataSeries: VIX data with quality metrics
        """
        logger.info(f"Fetching VIX data from {start_date.date()} to {end_date.date()}")
        
        try:
            # Use the existing market data infrastructure with fallback support
            vix_data = self.market_data_service.fetch_vix_data(start_date, end_date)
            
            # Additional VIX-specific validation
            self._validate_vix_data(vix_data)
            
            logger.info(f"Successfully fetched and validated {vix_data.total_records} VIX records")
            return vix_data
            
        except Exception as e:
            logger.error(f"Error fetching VIX data: {e}")
            raise MarketDataValidationError(f"Failed to fetch VIX data: {e}")
    
    def classify_volatility_regimes(self, vix_data: MarketDataSeries) -> List[RegimeClassification]:
        """
        Classify volatility regimes based on VIX levels.
        
        Regime Classification:
        - Low: VIX < 15
        - Medium: VIX 15-25  
        - High: VIX > 25
        
        Args:
            vix_data: VIX market data series
            
        Returns:
            List[RegimeClassification]: Regime classifications for each date
        """
        logger.info(f"Classifying volatility regimes for {len(vix_data.data)} VIX records")
        
        try:
            classifications = []
            current_regime = None
            regime_start_date = None
            
            # Sort data by date to ensure chronological processing
            sorted_data = vix_data.data.sort_index()
            
            for date, row in sorted_data.iterrows():
                vix_close = float(row['Close'])
                
                # Classify regime based on VIX level
                if vix_close < self.regime_thresholds['low_upper']:
                    regime = VolatilityRegime.LOW
                elif vix_close <= self.regime_thresholds['medium_upper']:
                    regime = VolatilityRegime.MEDIUM
                else:
                    regime = VolatilityRegime.HIGH
                
                # Track regime duration
                if current_regime != regime:
                    current_regime = regime
                    regime_start_date = date
                    regime_duration = 1
                else:
                    regime_duration = (date - regime_start_date).days + 1
                
                classification = RegimeClassification(
                    date=date,
                    vix_level=vix_close,
                    regime=regime,
                    regime_duration_days=regime_duration
                )
                classifications.append(classification)
            
            # Log regime distribution
            regime_counts = {}
            for classification in classifications:
                regime_counts[classification.regime.value] = regime_counts.get(classification.regime.value, 0) + 1
            
            logger.info(f"Regime distribution: {regime_counts}")
            return classifications
            
        except Exception as e:
            logger.error(f"Error classifying volatility regimes: {e}")
            raise MarketDataValidationError(f"Failed to classify volatility regimes: {e}")
    
    def synchronize_vix_with_trades(self, account_name: str, 
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None) -> List[TradeRegimeAlignment]:
        """
        Synchronize VIX data with trades for regime-based performance analysis.
        
        Args:
            account_name: Account to analyze trades for
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List[TradeRegimeAlignment]: Trade-regime alignment data
        """
        logger.info(f"Synchronizing VIX data with trades for account {account_name}")
        
        try:
            # Get trade timestamps
            trade_timestamps = self.market_data_service.get_trade_timestamps_for_account(
                account_name, start_date, end_date
            )
            
            if not trade_timestamps:
                logger.warning(f"No trades found for account {account_name}")
                return []
            
            # Get trade details with P&L
            trades = self._get_trade_details(account_name, start_date, end_date)
            
            # Determine VIX data date range
            min_date = min(trade_timestamps).replace(hour=0, minute=0, second=0, microsecond=0)
            max_date = max(trade_timestamps).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Fetch and classify VIX data
            vix_data = self.fetch_vix_data(min_date, max_date)
            regime_classifications = self.classify_volatility_regimes(vix_data)
            
            # Create lookup dictionary for regime classifications
            regime_lookup = {
                classification.date.date(): classification 
                for classification in regime_classifications
            }
            
            # Align trades with VIX regimes
            alignments = []
            for trade in trades:
                trade_date = trade['entry_time'].date()
                
                # Find VIX data for trade date (with fallback to previous trading day)
                regime_classification = self._get_regime_for_date(regime_lookup, trade_date)
                
                if regime_classification:
                    alignment = TradeRegimeAlignment(
                        trade_timestamp=trade['entry_time'],
                        entry_price=trade['entry_price'],
                        vix_level=regime_classification.vix_level,
                        regime=regime_classification.regime,
                        days_since_regime_start=regime_classification.regime_duration_days,
                        trade_pnl=trade['pnl']
                    )
                    alignments.append(alignment)
                else:
                    logger.warning(f"No VIX regime data found for trade on {trade_date}")
            
            logger.info(f"Successfully aligned {len(alignments)} trades with VIX regimes")
            return alignments
            
        except Exception as e:
            logger.error(f"Error synchronizing VIX with trades: {e}")
            raise MarketDataValidationError(f"Failed to synchronize VIX with trades: {e}")
    
    def detect_regime_transitions(self, regime_classifications: List[RegimeClassification]) -> List[RegimeTransition]:
        """
        Detect regime transitions and analyze transition patterns.
        
        Args:
            regime_classifications: List of daily regime classifications
            
        Returns:
            List[RegimeTransition]: Detected regime transitions
        """
        logger.info(f"Detecting regime transitions from {len(regime_classifications)} classifications")
        
        try:
            transitions = []
            
            if len(regime_classifications) < 2:
                return transitions
            
            # Sort by date to ensure chronological processing
            sorted_classifications = sorted(regime_classifications, key=lambda x: x.date)
            
            previous_regime = sorted_classifications[0].regime
            regime_start_date = sorted_classifications[0].date
            
            for i in range(1, len(sorted_classifications)):
                current_classification = sorted_classifications[i]
                current_regime = current_classification.regime
                
                # Check for regime change
                if current_regime != previous_regime:
                    days_in_previous = (current_classification.date - regime_start_date).days
                    
                    transition = RegimeTransition(
                        transition_date=current_classification.date,
                        from_regime=previous_regime,
                        to_regime=current_regime,
                        trigger_vix_level=current_classification.vix_level,
                        days_in_previous_regime=days_in_previous
                    )
                    transitions.append(transition)
                    
                    # Update tracking variables
                    previous_regime = current_regime
                    regime_start_date = current_classification.date
            
            # Log transition summary
            transition_summary = {}
            for transition in transitions:
                key = f"{transition.from_regime.value} -> {transition.to_regime.value}"
                transition_summary[key] = transition_summary.get(key, 0) + 1
            
            logger.info(f"Detected {len(transitions)} regime transitions: {transition_summary}")
            return transitions
            
        except Exception as e:
            logger.error(f"Error detecting regime transitions: {e}")
            raise MarketDataValidationError(f"Failed to detect regime transitions: {e}")
    
    def analyze_regime_performance(self, alignments: List[TradeRegimeAlignment]) -> Dict[VolatilityRegime, Dict[str, float]]:
        """
        Analyze trading performance by volatility regime.
        
        Args:
            alignments: Trade-regime alignment data
            
        Returns:
            Dict[VolatilityRegime, Dict[str, float]]: Performance metrics by regime
        """
        logger.info(f"Analyzing regime performance for {len(alignments)} aligned trades")
        
        try:
            regime_performance = {}
            
            # Group trades by regime
            regime_trades = {}
            for alignment in alignments:
                regime = alignment.regime
                if regime not in regime_trades:
                    regime_trades[regime] = []
                regime_trades[regime].append(alignment)
            
            # Calculate performance metrics for each regime
            for regime, trades in regime_trades.items():
                pnl_values = [trade.trade_pnl for trade in trades]
                
                total_trades = len(trades)
                winning_trades = sum(1 for pnl in pnl_values if pnl > 0)
                win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
                
                total_pnl = sum(pnl_values)
                avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
                
                winning_pnl = sum(pnl for pnl in pnl_values if pnl > 0)
                losing_pnl = abs(sum(pnl for pnl in pnl_values if pnl < 0))
                profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else float('inf')
                
                # Calculate Sharpe-like ratio (avg return / std of returns)
                import statistics
                sharpe_ratio = None
                if total_trades > 1:
                    try:
                        std_pnl = statistics.stdev(pnl_values)
                        sharpe_ratio = avg_pnl / std_pnl if std_pnl > 0 else None
                    except:
                        sharpe_ratio = None
                
                regime_performance[regime] = {
                    'total_trades': total_trades,
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'total_pnl': total_pnl,
                    'profit_factor': profit_factor,
                    'sharpe_ratio': sharpe_ratio,
                    'avg_vix_level': statistics.mean([trade.vix_level for trade in trades])
                }
            
            # Log performance summary
            for regime, metrics in regime_performance.items():
                logger.info(
                    f"{regime.value} regime: {metrics['total_trades']} trades, "
                    f"{metrics['win_rate']:.1%} win rate, "
                    f"${metrics['avg_pnl']:.2f} avg P&L"
                )
            
            return regime_performance
            
        except Exception as e:
            logger.error(f"Error analyzing regime performance: {e}")
            raise MarketDataValidationError(f"Failed to analyze regime performance: {e}")
    
    def _validate_vix_data(self, vix_data: MarketDataSeries):
        """Validate VIX-specific data constraints."""
        try:
            # Check for reasonable VIX ranges
            vix_closes = vix_data.data['Close']
            
            if (vix_closes < 5).any():
                logger.warning("Found unusually low VIX values (< 5)")
            
            if (vix_closes > 80).any():
                logger.warning("Found unusually high VIX values (> 80)")
            
            # Check for negative values
            if (vix_closes <= 0).any():
                raise MarketDataValidationError("Found non-positive VIX values")
            
        except Exception as e:
            logger.error(f"VIX data validation failed: {e}")
            raise MarketDataValidationError(f"VIX data validation failed: {e}")
    
    def _get_trade_details(self, account_name: str, start_date: Optional[datetime], 
                          end_date: Optional[datetime]) -> List[Dict]:
        """Get detailed trade information including P&L."""
        try:
            query = self.db_session.query(ProcessedTrade).filter(
                ProcessedTrade.account_name == account_name
            )
            
            if start_date:
                query = query.filter(ProcessedTrade.entry_time >= start_date)
            if end_date:
                query = query.filter(ProcessedTrade.entry_time <= end_date)
            
            trades = query.all()
            
            trade_details = []
            for trade in trades:
                trade_details.append({
                    'entry_time': trade.entry_time,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'pnl': trade.pnl
                })
            
            return trade_details
            
        except Exception as e:
            logger.error(f"Error getting trade details: {e}")
            return []
    
    def _get_regime_for_date(self, regime_lookup: Dict, trade_date) -> Optional[RegimeClassification]:
        """Get regime classification for a specific date with fallback logic."""
        # Try exact date match first
        if trade_date in regime_lookup:
            return regime_lookup[trade_date]
        
        # Try previous trading days (for weekend trades)
        for i in range(1, 4):
            prev_date = trade_date - timedelta(days=i)
            if prev_date in regime_lookup:
                logger.debug(f"Using {prev_date} VIX regime for trade on {trade_date}")
                return regime_lookup[prev_date]
        
        return None