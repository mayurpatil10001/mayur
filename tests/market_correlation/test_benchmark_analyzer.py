"""
Test suite for Benchmark Comparison Analyzer

Tests the BenchmarkComparisonAnalyzer calculations against known financial formulas
with real data, validates beta coefficients, alpha metrics, market neutrality,
and correlation stability analysis.

Requirements: 11.3, 11.4, 11.5, 11.6
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
import scipy.stats as stats

from trading_platform.services.benchmark_comparison_analyzer import (
    BenchmarkComparisonAnalyzer, BetaCoefficients, AlphaMetrics,
    MarketNeutralityTest, CorrelationStability
)
from trading_platform.services.market_data_ingestion import SynchronizedMarketData
from trading_platform.models.database import ProcessedTrade


class TestBenchmarkComparisonAnalyzer:
    """Test suite for BenchmarkComparisonAnalyzer service."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def analyzer(self, mock_db_session):
        """Create BenchmarkComparisonAnalyzer with mock database."""
        return BenchmarkComparisonAnalyzer(db_session=mock_db_session)
    
    @pytest.fixture
    def sample_trade_data(self):
        """Create sample trade data for testing."""
        # 30 days of sample trades with known patterns
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(30)]
        
        trades = []
        for i, trade_date in enumerate(dates):
            # Create trades with some correlation to market (beta ≈ 0.5)
            trade = Mock(spec=ProcessedTrade)
            trade.account_name = "TEST_ACCOUNT"
            trade.entry_time = datetime.combine(trade_date, datetime.min.time().replace(hour=10))
            trade.pnl = 100 + 50 * np.sin(i * 0.2) + np.random.normal(0, 20)  # Some pattern + noise
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_market_data(self):
        """Create sample synchronized market data."""
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(30)]
        
        # Generate correlated market returns
        spy_prices = [400 + 10 * np.sin(i * 0.15) + np.random.normal(0, 5) for i in range(30)]
        qqq_prices = [350 + 8 * np.sin(i * 0.18) + np.random.normal(0, 4) for i in range(30)]
        vix_levels = [20 + 5 * np.sin(i * 0.25) + np.random.normal(0, 2) for i in range(30)]
        
        # Ensure VIX levels are positive
        vix_levels = [max(5, level) for level in vix_levels]
        
        sync_data = SynchronizedMarketData(
            trade_timestamps=dates,
            spy_data={date: price for date, price in zip(dates, spy_prices)},
            qqq_data={date: price for date, price in zip(dates, qqq_prices)},
            vix_data={date: level for date, level in zip(dates, vix_levels)},
            synchronization_quality=1.0
        )
        
        return sync_data
    
    @pytest.fixture
    def known_beta_data(self):
        """Create data with known beta coefficient for validation."""
        # Generate data where strategy returns = 0.5 * market returns + noise
        # This should produce beta ≈ 0.5
        market_returns = np.random.normal(0.01, 0.02, 100)  # 1% mean, 2% std daily returns
        strategy_returns = 0.5 * market_returns + np.random.normal(0, 0.01, 100)  # Beta = 0.5
        
        return strategy_returns.tolist(), market_returns.tolist()
    
    def test_calculate_beta_coefficients_known_values(self, analyzer, known_beta_data):
        """Test beta coefficient calculation with known values."""
        strategy_returns, market_returns = known_beta_data
        
        # Mock the data retrieval
        market_data_dict = {
            'spy_returns': market_returns,
            'qqq_returns': [r * 0.8 for r in market_returns],  # Correlated but different
            'dates': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(len(market_returns))],
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns, market_data_dict)):
            result = analyzer.calculate_beta_coefficients("TEST_ACCOUNT")
            
            # Beta should be approximately 0.5 (within reasonable tolerance)
            assert isinstance(result, BetaCoefficients)
            assert 0.4 < result.spy_beta < 0.6, f"SPY beta {result.spy_beta} not close to expected 0.5"
            assert result.spy_r_squared > 0.3, f"R-squared {result.spy_r_squared} too low"
            assert abs(result.spy_correlation) > 0.5, f"Correlation {result.spy_correlation} too low"
            assert result.sample_size == len(strategy_returns)
    
    def test_calculate_beta_coefficients_insufficient_data(self, analyzer):
        """Test beta calculation with insufficient data."""
        with patch.object(analyzer, '_get_aligned_returns', return_value=([], {})):
            with pytest.raises(ValueError, match="Insufficient data"):
                analyzer.calculate_beta_coefficients("EMPTY_ACCOUNT")
    
    def test_calculate_alpha_metrics_positive_alpha(self, analyzer):
        """Test alpha metrics calculation with positive alpha strategy."""
        # Create strategy that outperforms market
        market_returns = np.random.normal(0.001, 0.02, 50)  # 0.1% daily mean
        strategy_returns = market_returns + 0.002  # Add 0.2% daily alpha
        
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': market_returns.tolist(),
            'dates': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(50)],
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns.tolist(), market_data_dict)), \
             patch.object(analyzer, 'calculate_beta_coefficients') as mock_beta:
            
            # Mock beta coefficients
            mock_beta.return_value = BetaCoefficients(
                spy_beta=1.0, qqq_beta=1.0, spy_r_squared=0.8, qqq_r_squared=0.8,
                spy_correlation=0.9, qqq_correlation=0.9, sample_size=50, calculation_period_days=50
            )
            
            result = analyzer.calculate_alpha_metrics("TEST_ACCOUNT")
            
            assert isinstance(result, AlphaMetrics)
            assert result.spy_alpha_annual > 0, "Expected positive alpha"
            assert result.qqq_alpha_annual > 0, "Expected positive alpha"
            assert result.spy_alpha_annual > 0.3, f"Alpha {result.spy_alpha_annual} seems too low"
            assert isinstance(result.jensen_alpha, (int, float))
            assert isinstance(result.information_ratio_spy, (int, float))
            assert result.tracking_error_spy > 0
    
    def test_calculate_alpha_metrics_market_matching(self, analyzer):
        """Test alpha metrics with market-matching strategy (zero alpha)."""
        # Create strategy that exactly matches market
        market_returns = np.random.normal(0.001, 0.02, 50)
        strategy_returns = market_returns  # Exactly matches market
        
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': market_returns.tolist(),
            'dates': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(50)],
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns.tolist(), market_data_dict)), \
             patch.object(analyzer, 'calculate_beta_coefficients') as mock_beta:
            
            # Perfect market correlation
            mock_beta.return_value = BetaCoefficients(
                spy_beta=1.0, qqq_beta=1.0, spy_r_squared=1.0, qqq_r_squared=1.0,
                spy_correlation=1.0, qqq_correlation=1.0, sample_size=50, calculation_period_days=50
            )
            
            result = analyzer.calculate_alpha_metrics("TEST_ACCOUNT")
            
            # Alpha should be close to zero
            assert abs(result.spy_alpha_annual) < 0.1, f"Alpha {result.spy_alpha_annual} should be near zero"
            assert result.treynor_ratio >= 0  # Should be non-negative for positive returns
    
    def test_market_neutrality_test_neutral_strategy(self, analyzer):
        """Test market neutrality with truly neutral strategy."""
        # Create uncorrelated returns (market neutral)
        market_returns = np.random.normal(0.001, 0.02, 100)
        strategy_returns = np.random.normal(0.002, 0.015, 100)  # Independent returns
        
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': market_returns.tolist(),
            'dates': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)],
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns.tolist(), market_data_dict)), \
             patch.object(analyzer, 'calculate_beta_coefficients') as mock_beta:
            
            # Near-zero beta and correlation
            mock_beta.return_value = BetaCoefficients(
                spy_beta=0.05, qqq_beta=0.03, spy_r_squared=0.01, qqq_r_squared=0.01,
                spy_correlation=0.1, qqq_correlation=0.08, sample_size=100, calculation_period_days=100
            )
            
            result = analyzer.test_market_neutrality("TEST_ACCOUNT")
            
            assert isinstance(result, MarketNeutralityTest)
            # With truly independent data, should likely pass neutrality tests
            assert result.market_neutrality_score > 0.5, f"Neutrality score {result.market_neutrality_score} too low for neutral strategy"
            assert result.spy_correlation_p_value > 0.05 or result.spy_beta_p_value > 0.05  # At least one should be non-significant
    
    def test_market_neutrality_test_correlated_strategy(self, analyzer):
        """Test market neutrality with highly correlated strategy."""
        # Create highly correlated returns
        market_returns = np.random.normal(0.001, 0.02, 100)
        strategy_returns = 1.5 * market_returns + np.random.normal(0, 0.005, 100)  # High correlation
        
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': market_returns.tolist(),
            'dates': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)],
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns.tolist(), market_data_dict)), \
             patch.object(analyzer, 'calculate_beta_coefficients') as mock_beta:
            
            # High beta and correlation
            mock_beta.return_value = BetaCoefficients(
                spy_beta=1.45, qqq_beta=1.45, spy_r_squared=0.95, qqq_r_squared=0.95,
                spy_correlation=0.98, qqq_correlation=0.98, sample_size=100, calculation_period_days=100
            )
            
            result = analyzer.test_market_neutrality("TEST_ACCOUNT")
            
            # Should fail neutrality tests
            assert result.is_market_neutral_spy is False, "Should not be market neutral to SPY"
            assert result.is_market_neutral_qqq is False, "Should not be market neutral to QQQ"
            assert result.market_neutrality_score < 0.3, f"Neutrality score {result.market_neutrality_score} too high for correlated strategy"
    
    def test_correlation_stability_stable_correlation(self, analyzer):
        """Test correlation stability with stable correlations."""
        # Create data with stable correlation over time
        market_returns = np.random.normal(0.001, 0.02, 100)
        strategy_returns = 0.6 * market_returns + np.random.normal(0, 0.01, 100)  # Stable beta ≈ 0.6
        
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)]
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': market_returns.tolist(),
            'dates': dates,
            'vix_levels': [15 + np.random.normal(0, 3) for _ in range(100)]  # Medium volatility regime
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns.tolist(), market_data_dict)):
            result = analyzer.calculate_correlation_stability("TEST_ACCOUNT")
            
            assert isinstance(result, CorrelationStability)
            assert len(result.rolling_correlations_spy) > 0
            assert len(result.rolling_correlations_qqq) > 0
            assert len(result.correlation_dates) == len(result.rolling_correlations_spy)
            
            # Stable correlation should have low volatility
            assert result.correlation_volatility_spy < 0.3, f"Correlation volatility {result.correlation_volatility_spy} too high for stable strategy"
            assert result.stability_score_spy > 0.5, f"Stability score {result.stability_score_spy} too low for stable strategy"
            
            # Check regime correlations were calculated
            assert len(result.regime_correlation_spy) > 0 or len(result.regime_correlation_qqq) > 0
    
    def test_correlation_stability_unstable_correlation(self, analyzer):
        """Test correlation stability with unstable correlations."""
        # Create data with changing correlation over time
        market_returns = np.random.normal(0.001, 0.02, 100)
        
        # First half: positive correlation, second half: negative correlation
        strategy_returns = []
        for i in range(100):
            if i < 50:
                strategy_returns.append(0.8 * market_returns[i] + np.random.normal(0, 0.01))
            else:
                strategy_returns.append(-0.5 * market_returns[i] + np.random.normal(0, 0.01))
        
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)]
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': market_returns.tolist(),
            'dates': dates,
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns, market_data_dict)):
            result = analyzer.calculate_correlation_stability("TEST_ACCOUNT")
            
            # Unstable correlation should have high volatility and low stability
            assert result.correlation_volatility_spy > 0.3, f"Expected high correlation volatility, got {result.correlation_volatility_spy}"
            assert result.stability_score_spy < 0.5, f"Expected low stability score, got {result.stability_score_spy}"
            assert abs(result.correlation_trend_spy) > 0.01, "Expected significant correlation trend"
    
    def test_correlation_stability_insufficient_data(self, analyzer):
        """Test correlation stability with insufficient data."""
        market_data_dict = {
            'spy_returns': [0.01] * 20,  # Less than required minimum
            'qqq_returns': [0.01] * 20,
            'dates': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(20)],
            'vix_levels': []
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=([0.02] * 20, market_data_dict)):
            with pytest.raises(ValueError, match="Insufficient data"):
                analyzer.calculate_correlation_stability("TEST_ACCOUNT")
    
    def test_get_aligned_returns_with_time_bin_filter(self, analyzer, sample_trade_data, sample_market_data):
        """Test aligned returns calculation with time bin filtering."""
        with patch.object(analyzer.db_session, 'query') as mock_query, \
             patch.object(analyzer.market_data_service, 'synchronize_market_data', return_value=sample_market_data):
            
            # Setup mock query chain
            mock_query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = sample_trade_data
            
            trade_returns, market_returns = analyzer._get_aligned_returns(
                "TEST_ACCOUNT", None, None, 10, 0  # 10:00-10:30 time bin
            )
            
            assert len(trade_returns) > 0
            assert 'spy_returns' in market_returns
            assert 'qqq_returns' in market_returns
            assert 'dates' in market_returns
            assert len(trade_returns) == len(market_returns['spy_returns'])
    
    def test_get_aligned_returns_no_trades(self, analyzer):
        """Test aligned returns with no trades found."""
        with patch.object(analyzer.db_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            
            with pytest.raises(ValueError, match="No trades found"):
                analyzer._get_aligned_returns("EMPTY_ACCOUNT", None, None, None, None)
    
    def test_calculate_single_beta_perfect_correlation(self, analyzer):
        """Test single beta calculation with perfect correlation."""
        market_returns = [0.01, 0.02, -0.01, 0.015, -0.005]
        strategy_returns = [0.02, 0.04, -0.02, 0.03, -0.01]  # Exactly 2x market
        
        beta, r_squared, correlation = analyzer._calculate_single_beta(
            strategy_returns, market_returns, "TEST"
        )
        
        assert abs(beta - 2.0) < 0.1, f"Beta {beta} should be close to 2.0"
        assert r_squared > 0.9, f"R-squared {r_squared} should be high for perfect correlation"
        assert abs(correlation) > 0.9, f"Correlation {correlation} should be high"
    
    def test_calculate_single_beta_zero_correlation(self, analyzer):
        """Test single beta calculation with zero correlation."""
        market_returns = [0.01, 0.02, -0.01, 0.015, -0.005]
        strategy_returns = [0.005, -0.01, 0.02, -0.008, 0.012]  # Uncorrelated
        
        beta, r_squared, correlation = analyzer._calculate_single_beta(
            strategy_returns, market_returns, "TEST"
        )
        
        assert abs(beta) < 1.0, f"Beta {beta} should be small for uncorrelated data"
        assert r_squared < 0.5, f"R-squared {r_squared} should be low for uncorrelated data"
        assert abs(correlation) < 0.5, f"Correlation {correlation} should be low"
    
    def test_risk_free_rate_configuration(self, analyzer):
        """Test that risk-free rate is properly configured."""
        assert analyzer.risk_free_rate == 0.02  # 2% default
        assert analyzer.significance_level == 0.05  # 5% default
        assert analyzer.correlation_stability_window == 30  # 30-day window
    
    @pytest.mark.integration
    def test_end_to_end_benchmark_analysis(self, analyzer):
        """Integration test for complete benchmark analysis workflow."""
        # Create comprehensive synthetic data
        np.random.seed(42)  # For reproducible results
        
        # Generate 100 days of correlated data
        market_returns = np.random.normal(0.001, 0.02, 100)
        strategy_returns = 0.7 * market_returns + np.random.normal(0.0005, 0.01, 100)  # Slight positive alpha
        
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)]
        market_data_dict = {
            'spy_returns': market_returns.tolist(),
            'qqq_returns': (market_returns * 0.9).tolist(),  # Slightly different correlation
            'dates': dates,
            'vix_levels': [15 + 5 * np.sin(i * 0.1) + np.random.normal(0, 2) for i in range(100)]
        }
        
        with patch.object(analyzer, '_get_aligned_returns', return_value=(strategy_returns.tolist(), market_data_dict)):
            
            # Test complete workflow
            beta_coeffs = analyzer.calculate_beta_coefficients("TEST_ACCOUNT")
            alpha_metrics = analyzer.calculate_alpha_metrics("TEST_ACCOUNT")
            neutrality_test = analyzer.test_market_neutrality("TEST_ACCOUNT")
            correlation_stability = analyzer.calculate_correlation_stability("TEST_ACCOUNT")
            
            # Validate all components returned proper objects
            assert isinstance(beta_coeffs, BetaCoefficients)
            assert isinstance(alpha_metrics, AlphaMetrics)
            assert isinstance(neutrality_test, MarketNeutralityTest)
            assert isinstance(correlation_stability, CorrelationStability)
            
            # Cross-validate consistency between components
            assert beta_coeffs.sample_size == 100
            assert 0.5 < beta_coeffs.spy_beta < 0.9, f"Beta {beta_coeffs.spy_beta} outside expected range"
            
            # Alpha should be positive (we added positive alpha to synthetic data)
            assert alpha_metrics.spy_alpha_annual > 0, "Expected positive alpha"
            
            # Correlation stability should be reasonable
            assert len(correlation_stability.rolling_correlations_spy) > 50, "Expected sufficient rolling correlations"
            assert correlation_stability.stability_score_spy > 0.3, "Expected reasonable stability"
    
    def test_edge_case_handling(self, analyzer):
        """Test various edge cases and error conditions."""
        # Test with extreme values
        extreme_returns = [100, -50, 200, -150, 75]  # Very volatile
        market_returns = [0.01, 0.02, -0.01, 0.015, -0.005]  # Normal market
        
        beta, r_squared, correlation = analyzer._calculate_single_beta(
            extreme_returns, market_returns, "EXTREME"
        )
        
        # Should handle extreme values gracefully
        assert isinstance(beta, (int, float))
        assert isinstance(r_squared, (int, float))
        assert isinstance(correlation, (int, float))
        assert not np.isnan(beta)
        assert not np.isnan(r_squared)
        assert not np.isnan(correlation)


if __name__ == "__main__":
    pytest.main([__file__])