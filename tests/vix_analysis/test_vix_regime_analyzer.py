"""
Test suite for VIX Regime Analyzer

Tests the VIXDataIntegration class with historical VIX data,
validates regime classification accuracy, and ensures trade synchronization.

Requirements: 12.1, 12.2, 12.5
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from trading_platform.services.vix_regime_analyzer import (
    VIXDataIntegration, VolatilityRegime, RegimeClassification,
    RegimeTransition, TradeRegimeAlignment
)
from trading_platform.services.market_data_ingestion import MarketDataSeries, MarketDataValidationError
from trading_platform.models.database import ProcessedTrade


class TestVIXDataIntegration:
    """Test suite for VIXDataIntegration service."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def vix_service(self, mock_db_session):
        """Create VIXDataIntegration service with mock database."""
        return VIXDataIntegration(db_session=mock_db_session)
    
    @pytest.fixture
    def sample_vix_data(self):
        """Create sample VIX data for testing regime classification."""
        dates = pd.date_range(start='2024-01-01', end='2024-01-10', freq='D')
        # Mix of different regime levels
        vix_levels = [12.5, 14.0, 16.5, 18.0, 28.5, 35.0, 22.0, 19.5, 13.5, 11.0]
        
        data = pd.DataFrame({
            'Open': [v * 0.98 for v in vix_levels],
            'High': [v * 1.05 for v in vix_levels],
            'Low': [v * 0.95 for v in vix_levels],
            'Close': vix_levels,
            'Volume': [1000000] * len(vix_levels)
        }, index=dates)
        
        return MarketDataSeries(
            symbol='VIX',
            data=data,
            start_date=dates[0],
            end_date=dates[-1],
            total_records=len(data),
            missing_dates=[],
            data_quality_score=1.0
        )
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data for synchronization testing."""
        trades = [
            {
                'entry_time': datetime(2024, 1, 1, 9, 30),
                'entry_price': 100.0,
                'exit_price': 102.0,
                'quantity': 100,
                'pnl': 200.0
            },
            {
                'entry_time': datetime(2024, 1, 5, 14, 15),
                'entry_price': 105.0,
                'exit_price': 103.0,
                'quantity': 100,
                'pnl': -200.0
            },
            {
                'entry_time': datetime(2024, 1, 8, 11, 45),
                'entry_price': 98.0,
                'exit_price': 99.5,
                'quantity': 200,
                'pnl': 300.0
            }
        ]
        return trades
    
    def test_fetch_vix_data_success(self, vix_service, sample_vix_data):
        """Test successful VIX data fetching."""
        # Mock the market data service
        with patch.object(vix_service.market_data_service, 'fetch_vix_data', return_value=sample_vix_data):
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 10)
            
            result = vix_service.fetch_vix_data(start_date, end_date)
            
            assert result == sample_vix_data
            assert result.symbol == 'VIX'
            assert result.total_records == 10
    
    def test_fetch_vix_data_validation_error(self, vix_service):
        """Test VIX data fetching with validation errors."""
        # Mock market data service to raise an error
        with patch.object(vix_service.market_data_service, 'fetch_vix_data', 
                         side_effect=MarketDataValidationError("Test error")):
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 10)
            
            with pytest.raises(MarketDataValidationError):
                vix_service.fetch_vix_data(start_date, end_date)
    
    def test_classify_volatility_regimes(self, vix_service, sample_vix_data):
        """Test volatility regime classification accuracy."""
        classifications = vix_service.classify_volatility_regimes(sample_vix_data)
        
        assert len(classifications) == 10
        
        # Check specific regime classifications based on test data
        expected_regimes = [
            VolatilityRegime.LOW,     # 12.5
            VolatilityRegime.LOW,     # 14.0
            VolatilityRegime.MEDIUM,  # 16.5
            VolatilityRegime.MEDIUM,  # 18.0
            VolatilityRegime.HIGH,    # 28.5
            VolatilityRegime.HIGH,    # 35.0
            VolatilityRegime.MEDIUM,  # 22.0
            VolatilityRegime.MEDIUM,  # 19.5
            VolatilityRegime.LOW,     # 13.5
            VolatilityRegime.LOW      # 11.0
        ]
        
        for i, (classification, expected_regime) in enumerate(zip(classifications, expected_regimes)):
            assert classification.regime == expected_regime, f"Regime mismatch at index {i}"
            assert classification.vix_level == sample_vix_data.data.iloc[i]['Close']
            assert isinstance(classification.regime_duration_days, int)
    
    def test_regime_thresholds(self, vix_service):
        """Test regime classification thresholds."""
        # Test boundary conditions
        test_cases = [
            (10.0, VolatilityRegime.LOW),
            (14.9, VolatilityRegime.LOW),
            (15.0, VolatilityRegime.MEDIUM),
            (20.0, VolatilityRegime.MEDIUM),
            (25.0, VolatilityRegime.MEDIUM),
            (25.1, VolatilityRegime.HIGH),
            (50.0, VolatilityRegime.HIGH)
        ]
        
        for vix_level, expected_regime in test_cases:
            # Create test data with single VIX level
            dates = pd.date_range(start='2024-01-01', end='2024-01-01', freq='D')
            data = pd.DataFrame({
                'Open': [vix_level],
                'High': [vix_level],
                'Low': [vix_level],
                'Close': [vix_level],
                'Volume': [1000000]
            }, index=dates)
            
            test_data = MarketDataSeries(
                symbol='VIX', data=data, start_date=dates[0], end_date=dates[0],
                total_records=1, missing_dates=[], data_quality_score=1.0
            )
            
            classifications = vix_service.classify_volatility_regimes(test_data)
            assert len(classifications) == 1
            assert classifications[0].regime == expected_regime, f"Failed for VIX level {vix_level}"
    
    def test_detect_regime_transitions(self, vix_service, sample_vix_data):
        """Test regime transition detection algorithm."""
        # First classify regimes
        classifications = vix_service.classify_volatility_regimes(sample_vix_data)
        
        # Detect transitions
        transitions = vix_service.detect_regime_transitions(classifications)
        
        # Based on our test data, we should have several transitions
        assert len(transitions) > 0
        
        # Validate transition structure
        for transition in transitions:
            assert isinstance(transition.transition_date, datetime)
            assert isinstance(transition.from_regime, VolatilityRegime)
            assert isinstance(transition.to_regime, VolatilityRegime)
            assert transition.from_regime != transition.to_regime
            assert transition.days_in_previous_regime >= 0
            assert transition.trigger_vix_level > 0
    
    def test_synchronize_vix_with_trades_success(self, vix_service, sample_trades, sample_vix_data):
        """Test successful VIX-trade synchronization."""
        # Mock database queries
        mock_trade_objects = []
        for trade_data in sample_trades:
            mock_trade = Mock(spec=ProcessedTrade)
            mock_trade.entry_time = trade_data['entry_time']
            mock_trade.entry_price = trade_data['entry_price']
            mock_trade.exit_price = trade_data['exit_price']
            mock_trade.quantity = trade_data['quantity']
            mock_trade.pnl = trade_data['pnl']
            mock_trade_objects.append(mock_trade)
        
        with patch.object(vix_service.market_data_service, 'get_trade_timestamps_for_account') as mock_timestamps, \
             patch.object(vix_service, '_get_trade_details', return_value=sample_trades), \
             patch.object(vix_service, 'fetch_vix_data', return_value=sample_vix_data), \
             patch.object(vix_service, 'classify_volatility_regimes') as mock_classify:
            
            # Setup mocks
            mock_timestamps.return_value = [trade['entry_time'] for trade in sample_trades]
            
            # Create mock classifications
            mock_classifications = []
            for i, trade in enumerate(sample_trades):
                classification = RegimeClassification(
                    date=trade['entry_time'],
                    vix_level=sample_vix_data.data.iloc[i % len(sample_vix_data.data)]['Close'],
                    regime=VolatilityRegime.MEDIUM,
                    regime_duration_days=5
                )
                mock_classifications.append(classification)
            
            mock_classify.return_value = mock_classifications
            
            # Test synchronization
            alignments = vix_service.synchronize_vix_with_trades('TEST_ACCOUNT')
            
            assert len(alignments) == len(sample_trades)
            for alignment in alignments:
                assert isinstance(alignment, TradeRegimeAlignment)
                assert alignment.regime in [VolatilityRegime.LOW, VolatilityRegime.MEDIUM, VolatilityRegime.HIGH]
                assert alignment.vix_level > 0
                assert alignment.days_since_regime_start >= 0
    
    def test_synchronize_vix_with_trades_no_trades(self, vix_service):
        """Test VIX-trade synchronization with no trades."""
        with patch.object(vix_service.market_data_service, 'get_trade_timestamps_for_account', return_value=[]):
            alignments = vix_service.synchronize_vix_with_trades('EMPTY_ACCOUNT')
            assert alignments == []
    
    def test_analyze_regime_performance(self, vix_service):
        """Test regime performance analysis."""
        # Create test alignments with different regimes and P&L
        alignments = [
            TradeRegimeAlignment(
                trade_timestamp=datetime(2024, 1, 1),
                entry_price=100.0,
                vix_level=12.0,
                regime=VolatilityRegime.LOW,
                days_since_regime_start=5,
                trade_pnl=100.0
            ),
            TradeRegimeAlignment(
                trade_timestamp=datetime(2024, 1, 2),
                entry_price=105.0,
                vix_level=13.5,
                regime=VolatilityRegime.LOW,
                days_since_regime_start=6,
                trade_pnl=-50.0
            ),
            TradeRegimeAlignment(
                trade_timestamp=datetime(2024, 1, 3),
                entry_price=98.0,
                vix_level=28.0,
                regime=VolatilityRegime.HIGH,
                days_since_regime_start=2,
                trade_pnl=200.0
            ),
            TradeRegimeAlignment(
                trade_timestamp=datetime(2024, 1, 4),
                entry_price=102.0,
                vix_level=32.0,
                regime=VolatilityRegime.HIGH,
                days_since_regime_start=3,
                trade_pnl=-100.0
            )
        ]
        
        performance = vix_service.analyze_regime_performance(alignments)
        
        # Should have performance for LOW and HIGH regimes
        assert len(performance) == 2
        assert VolatilityRegime.LOW in performance
        assert VolatilityRegime.HIGH in performance
        
        # Check LOW regime performance
        low_perf = performance[VolatilityRegime.LOW]
        assert low_perf['total_trades'] == 2
        assert low_perf['win_rate'] == 0.5  # 1 win out of 2 trades
        assert low_perf['avg_pnl'] == 25.0   # (100 + (-50)) / 2
        assert low_perf['total_pnl'] == 50.0
        
        # Check HIGH regime performance
        high_perf = performance[VolatilityRegime.HIGH]
        assert high_perf['total_trades'] == 2
        assert high_perf['win_rate'] == 0.5  # 1 win out of 2 trades
        assert high_perf['avg_pnl'] == 50.0   # (200 + (-100)) / 2
        assert high_perf['total_pnl'] == 100.0
    
    def test_vix_data_validation_negative_values(self, vix_service):
        """Test VIX data validation with negative values."""
        # Create data with negative VIX values
        dates = pd.date_range(start='2024-01-01', end='2024-01-02', freq='D')
        data = pd.DataFrame({
            'Open': [15.0, -5.0],
            'High': [16.0, -3.0],
            'Low': [14.0, -8.0],
            'Close': [15.5, -5.0],
            'Volume': [1000000, 1100000]
        }, index=dates)
        
        invalid_data = MarketDataSeries(
            symbol='VIX', data=data, start_date=dates[0], end_date=dates[-1],
            total_records=2, missing_dates=[], data_quality_score=1.0
        )
        
        with pytest.raises(MarketDataValidationError):
            vix_service._validate_vix_data(invalid_data)
    
    def test_vix_data_validation_extreme_values(self, vix_service):
        """Test VIX data validation with extreme values."""
        # Create data with extreme VIX values (should warn but not fail)
        dates = pd.date_range(start='2024-01-01', end='2024-01-02', freq='D')
        data = pd.DataFrame({
            'Open': [2.0, 90.0],    # Very low and very high
            'High': [3.0, 95.0],
            'Low': [1.0, 85.0],
            'Close': [2.5, 90.0],
            'Volume': [1000000, 1100000]
        }, index=dates)
        
        extreme_data = MarketDataSeries(
            symbol='VIX', data=data, start_date=dates[0], end_date=dates[-1],
            total_records=2, missing_dates=[], data_quality_score=1.0
        )
        
        # Should not raise exception, just warnings
        vix_service._validate_vix_data(extreme_data)
    
    def test_get_regime_for_date_exact_match(self, vix_service):
        """Test regime lookup with exact date match."""
        test_date = date(2024, 1, 1)
        classification = RegimeClassification(
            date=datetime(2024, 1, 1),
            vix_level=15.0,
            regime=VolatilityRegime.MEDIUM,
            regime_duration_days=3
        )
        
        regime_lookup = {test_date: classification}
        result = vix_service._get_regime_for_date(regime_lookup, test_date)
        
        assert result == classification
    
    def test_get_regime_for_date_fallback(self, vix_service):
        """Test regime lookup with fallback to previous days."""
        test_date = date(2024, 1, 3)  # Weekend
        friday_date = date(2024, 1, 1)  # Previous trading day
        
        classification = RegimeClassification(
            date=datetime(2024, 1, 1),
            vix_level=20.0,
            regime=VolatilityRegime.MEDIUM,
            regime_duration_days=1
        )
        
        regime_lookup = {friday_date: classification}
        result = vix_service._get_regime_for_date(regime_lookup, test_date)
        
        assert result == classification
    
    def test_get_regime_for_date_no_match(self, vix_service):
        """Test regime lookup with no available data."""
        test_date = date(2024, 1, 10)
        regime_lookup = {date(2024, 1, 1): Mock()}  # Different date
        
        result = vix_service._get_regime_for_date(regime_lookup, test_date)
        assert result is None
    
    def test_empty_regime_classifications(self, vix_service):
        """Test transition detection with empty classifications."""
        transitions = vix_service.detect_regime_transitions([])
        assert transitions == []
    
    def test_single_regime_classification(self, vix_service):
        """Test transition detection with single classification."""
        classification = RegimeClassification(
            date=datetime(2024, 1, 1),
            vix_level=15.0,
            regime=VolatilityRegime.MEDIUM,
            regime_duration_days=1
        )
        
        transitions = vix_service.detect_regime_transitions([classification])
        assert transitions == []
    
    def test_regime_duration_tracking(self, vix_service):
        """Test regime duration tracking in classifications."""
        # Create VIX data that stays in same regime for several days
        dates = pd.date_range(start='2024-01-01', end='2024-01-05', freq='D')
        vix_levels = [16.0, 17.0, 18.0, 16.5, 17.5]  # All in MEDIUM regime
        
        data = pd.DataFrame({
            'Open': vix_levels,
            'High': [v * 1.02 for v in vix_levels],
            'Low': [v * 0.98 for v in vix_levels],
            'Close': vix_levels,
            'Volume': [1000000] * len(vix_levels)
        }, index=dates)
        
        test_data = MarketDataSeries(
            symbol='VIX', data=data, start_date=dates[0], end_date=dates[-1],
            total_records=len(data), missing_dates=[], data_quality_score=1.0
        )
        
        classifications = vix_service.classify_volatility_regimes(test_data)
        
        # All should be MEDIUM regime with increasing duration
        assert len(classifications) == 5
        for i, classification in enumerate(classifications):
            assert classification.regime == VolatilityRegime.MEDIUM
            assert classification.regime_duration_days == i + 1
    
    @pytest.mark.integration
    def test_end_to_end_vix_analysis(self, vix_service, sample_vix_data, sample_trades):
        """Integration test for complete VIX analysis workflow."""
        with patch.object(vix_service.market_data_service, 'get_trade_timestamps_for_account') as mock_timestamps, \
             patch.object(vix_service, '_get_trade_details', return_value=sample_trades), \
             patch.object(vix_service, 'fetch_vix_data', return_value=sample_vix_data):
            
            mock_timestamps.return_value = [trade['entry_time'] for trade in sample_trades]
            
            # Complete workflow
            # 1. Synchronize VIX with trades
            alignments = vix_service.synchronize_vix_with_trades('TEST_ACCOUNT')
            
            # 2. Analyze regime performance
            if alignments:  # Only if we have alignments
                performance = vix_service.analyze_regime_performance(alignments)
                assert isinstance(performance, dict)
                
                # Check that performance metrics are reasonable
                for regime, metrics in performance.items():
                    assert metrics['total_trades'] > 0
                    assert 0 <= metrics['win_rate'] <= 1
                    assert isinstance(metrics['avg_pnl'], (int, float))


if __name__ == "__main__":
    pytest.main([__file__])