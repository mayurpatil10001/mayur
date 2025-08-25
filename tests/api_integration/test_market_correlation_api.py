"""
Test suite for Market Correlation API endpoints

Tests the market correlation API endpoints with real market data integration,
validates API responses, error handling, and ensures proper integration
with benchmark comparison and VIX regime analysis services.

Requirements: 11.1, 12.3, 12.4
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from trading_platform.api.main import app
from trading_platform.services.benchmark_comparison_analyzer import (
    BetaCoefficients, AlphaMetrics, MarketNeutralityTest, CorrelationStability
)
from trading_platform.services.vix_regime_analyzer import (
    TradeRegimeAlignment, VolatilityRegime, RegimeTransition
)
from trading_platform.services.market_data_ingestion import MarketDataSeries


class TestMarketCorrelationAPI:
    """Test suite for market correlation API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test_token"}
    
    @pytest.fixture
    def sample_beta_coefficients(self):
        """Create sample beta coefficients for testing."""
        return BetaCoefficients(
            spy_beta=0.65,
            qqq_beta=0.58,
            spy_r_squared=0.42,
            qqq_r_squared=0.38,
            spy_correlation=0.65,
            qqq_correlation=0.62,
            sample_size=120,
            calculation_period_days=180
        )
    
    @pytest.fixture
    def sample_alpha_metrics(self):
        """Create sample alpha metrics for testing."""
        return AlphaMetrics(
            spy_alpha_annual=0.08,
            qqq_alpha_annual=0.06,
            spy_alpha_daily=0.0003,
            qqq_alpha_daily=0.0002,
            jensen_alpha=0.0004,
            information_ratio_spy=1.25,
            information_ratio_qqq=1.15,
            tracking_error_spy=0.06,
            tracking_error_qqq=0.05,
            treynor_ratio=0.12
        )
    
    @pytest.fixture
    def sample_market_neutrality(self):
        """Create sample market neutrality test results."""
        return MarketNeutralityTest(
            is_market_neutral_spy=True,
            is_market_neutral_qqq=True,
            spy_correlation_p_value=0.12,
            qqq_correlation_p_value=0.08,
            spy_beta_p_value=0.15,
            qqq_beta_p_value=0.11,
            market_neutrality_score=0.82,
            independence_test_statistic=1.25,
            independence_p_value=0.21
        )
    
    @pytest.fixture
    def sample_correlation_stability(self):
        """Create sample correlation stability data."""
        dates = [datetime(2024, 1, 1) + timedelta(days=i*30) for i in range(6)]
        return CorrelationStability(
            rolling_correlations_spy=[0.65, 0.58, 0.72, 0.61, 0.69, 0.63],
            rolling_correlations_qqq=[0.62, 0.55, 0.69, 0.58, 0.66, 0.60],
            correlation_dates=dates,
            correlation_volatility_spy=0.08,
            correlation_volatility_qqq=0.07,
            correlation_trend_spy=-0.02,
            correlation_trend_qqq=-0.015,
            stability_score_spy=0.78,
            stability_score_qqq=0.81,
            regime_correlation_spy={"Low": 0.45, "Medium": 0.65, "High": 0.85},
            regime_correlation_qqq={"Low": 0.42, "Medium": 0.62, "High": 0.82}
        )
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_benchmark_analyzer')
    def test_get_market_correlation_success(self, mock_analyzer, mock_auth, client, auth_headers, 
                                          sample_beta_coefficients, sample_correlation_stability):
        """Test successful market correlation analysis."""
        # Mock the analyzer methods
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.calculate_beta_coefficients.return_value = sample_beta_coefficients
        mock_analyzer_instance.calculate_correlation_stability.return_value = sample_correlation_stability
        mock_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/market-correlation",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "market correlation analysis completed" in data["message"].lower()
        
        # Verify response structure
        assert "beta_coefficients" in data["data"]
        assert "correlation_stability" in data["data"]
        assert "analysis_period" in data["data"]
        assert "analysis_timestamp" in data["data"]
        
        # Verify beta coefficients
        beta_data = data["data"]["beta_coefficients"]
        assert beta_data["spy_beta"] == 0.65
        assert beta_data["qqq_beta"] == 0.58
        assert beta_data["sample_size"] == 120
        
        # Verify correlation stability
        correlation_data = data["data"]["correlation_stability"]
        assert len(correlation_data["rolling_correlations_spy"]) == 6
        assert correlation_data["stability_score_spy"] == 0.78
        assert "regime_correlation_spy" in correlation_data
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_benchmark_analyzer')
    def test_get_market_correlation_with_date_range(self, mock_analyzer, mock_auth, client, auth_headers,
                                                  sample_beta_coefficients, sample_correlation_stability):
        """Test market correlation with date range parameters."""
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.calculate_beta_coefficients.return_value = sample_beta_coefficients
        mock_analyzer_instance.calculate_correlation_stability.return_value = sample_correlation_stability
        mock_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request with date range
        response = client.get(
            "/api/time-bins/IPS_TM_10/14/0/market-correlation?start_date=2024-01-01&end_date=2024-06-30",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify analyzer was called with correct parameters
        mock_analyzer_instance.calculate_beta_coefficients.assert_called_once()
        call_args = mock_analyzer_instance.calculate_beta_coefficients.call_args[0]
        assert call_args[0] == "IPS_TM_10"
        assert call_args[3] == 14  # hour
        assert call_args[4] == 0   # minute_bin
        
        # Verify analysis period in response
        analysis_period = data["data"]["analysis_period"]
        assert "2024-01-01" in analysis_period["start_date"]
        assert "2024-06-30" in analysis_period["end_date"]
    
    def test_get_market_correlation_invalid_minute_bin(self, client, auth_headers):
        """Test market correlation with invalid minute bin."""
        with patch('trading_platform.api.dependencies.require_read_permission') as mock_auth:
            mock_auth.return_value = {"user_id": "test_user"}
            
            response = client.get(
                "/api/time-bins/IPS_TM_10/9/15/market-correlation",  # Invalid minute bin
                headers=auth_headers
            )
            
            assert response.status_code == 400
            assert "must be 0 or 30" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_benchmark_analyzer')
    def test_get_benchmark_comparison_success(self, mock_analyzer, mock_auth, client, auth_headers,
                                            sample_beta_coefficients, sample_alpha_metrics,
                                            sample_market_neutrality, sample_correlation_stability):
        """Test successful comprehensive benchmark comparison."""
        # Mock all analyzer methods
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.calculate_beta_coefficients.return_value = sample_beta_coefficients
        mock_analyzer_instance.calculate_alpha_metrics.return_value = sample_alpha_metrics
        mock_analyzer_instance.test_market_neutrality.return_value = sample_market_neutrality
        mock_analyzer_instance.calculate_correlation_stability.return_value = sample_correlation_stability
        mock_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/benchmark-comparison",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "benchmark comparison analysis completed" in data["message"].lower()
        
        # Verify all components are present
        benchmark_data = data["data"]
        assert "beta_coefficients" in benchmark_data
        assert "alpha_metrics" in benchmark_data
        assert "market_neutrality" in benchmark_data
        assert "correlation_stability" in benchmark_data
        assert "analysis_period" in benchmark_data
        
        # Verify alpha metrics
        alpha_data = benchmark_data["alpha_metrics"]
        assert alpha_data["spy_alpha_annual"] == 0.08
        assert alpha_data["jensen_alpha"] == 0.0004
        assert alpha_data["information_ratio_spy"] == 1.25
        
        # Verify market neutrality
        neutrality_data = benchmark_data["market_neutrality"]
        assert neutrality_data["is_market_neutral_spy"] is True
        assert neutrality_data["market_neutrality_score"] == 0.82
        
        # Verify all analysis methods were called
        mock_analyzer_instance.calculate_beta_coefficients.assert_called_once()
        mock_analyzer_instance.calculate_alpha_metrics.assert_called_once()
        mock_analyzer_instance.test_market_neutrality.assert_called_once()
        mock_analyzer_instance.calculate_correlation_stability.assert_called_once()
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_benchmark_analyzer')
    def test_benchmark_comparison_insufficient_data_error(self, mock_analyzer, mock_auth, client, auth_headers):
        """Test benchmark comparison with insufficient data."""
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.calculate_beta_coefficients.side_effect = ValueError("Insufficient data for beta calculation")
        mock_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get(
            "/api/time-bins/EMPTY_ACCOUNT/9/30/benchmark-comparison",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Insufficient data" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_vix_analyzer')
    def test_get_regime_analysis_success(self, mock_vix_analyzer, mock_auth, client, auth_headers):
        """Test successful VIX regime analysis."""
        # Mock VIX analyzer
        mock_analyzer_instance = Mock()
        
        # Mock trade-regime alignments
        alignments = [
            TradeRegimeAlignment(
                trade_timestamp=datetime(2024, 1, 1, 9, 30),
                entry_price=100.0,
                vix_level=12.0,
                regime=VolatilityRegime.LOW,
                days_since_regime_start=5,
                trade_pnl=100.0
            ),
            TradeRegimeAlignment(
                trade_timestamp=datetime(2024, 1, 2, 9, 30),
                entry_price=105.0,
                vix_level=28.0,
                regime=VolatilityRegime.HIGH,
                days_since_regime_start=2,
                trade_pnl=200.0
            )
        ]
        
        mock_analyzer_instance.synchronize_vix_with_trades.return_value = alignments
        
        # Mock regime performance analysis
        regime_performance = {
            VolatilityRegime.LOW: {
                'total_trades': 1,
                'win_rate': 1.0,
                'avg_pnl': 100.0,
                'total_pnl': 100.0,
                'profit_factor': float('inf'),
                'sharpe_ratio': 1.5,
                'avg_vix_level': 12.0
            },
            VolatilityRegime.HIGH: {
                'total_trades': 1,
                'win_rate': 1.0,
                'avg_pnl': 200.0,
                'total_pnl': 200.0,
                'profit_factor': float('inf'),
                'sharpe_ratio': 2.0,
                'avg_vix_level': 28.0
            }
        }
        mock_analyzer_instance.analyze_regime_performance.return_value = regime_performance
        
        # Mock VIX data and classifications
        mock_vix_data = Mock()
        mock_analyzer_instance.fetch_vix_data.return_value = mock_vix_data
        mock_analyzer_instance.classify_volatility_regimes.return_value = []
        
        # Mock regime transitions
        transitions = [
            RegimeTransition(
                transition_date=datetime(2024, 1, 15),
                from_regime=VolatilityRegime.LOW,
                to_regime=VolatilityRegime.HIGH,
                trigger_vix_level=25.2,
                days_in_previous_regime=10
            )
        ]
        mock_analyzer_instance.detect_regime_transitions.return_value = transitions
        
        mock_vix_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/regime-analysis",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "regime analysis completed" in data["message"].lower()
        
        # Verify response structure
        regime_data = data["data"]
        assert "regime_performance" in regime_data
        assert "regime_transitions" in regime_data
        assert "regime_summary" in regime_data
        assert "analysis_period" in regime_data
        
        # Verify regime performance data
        assert len(regime_data["regime_performance"]) == 2
        
        low_regime = next(r for r in regime_data["regime_performance"] if r["regime"] == "Low")
        assert low_regime["total_trades"] == 1
        assert low_regime["avg_pnl"] == 100.0
        assert low_regime["avg_vix_level"] == 12.0
        
        # Verify regime transitions
        assert len(regime_data["regime_transitions"]) == 1
        transition = regime_data["regime_transitions"][0]
        assert transition["from_regime"] == "Low"
        assert transition["to_regime"] == "High"
        assert transition["trigger_vix_level"] == 25.2
        
        # Verify regime summary
        summary = regime_data["regime_summary"]
        assert summary["total_regimes_found"] == 2
        assert summary["most_profitable_regime"] == "High"
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_vix_analyzer')
    def test_regime_analysis_no_trades_found(self, mock_vix_analyzer, mock_auth, client, auth_headers):
        """Test regime analysis when no trades found for time bin."""
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.synchronize_vix_with_trades.return_value = []
        mock_vix_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get(
            "/api/time-bins/EMPTY_ACCOUNT/9/30/regime-analysis",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "No trades found" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_market_data_service')
    def test_sync_market_data_success(self, mock_market_service, mock_auth, client, auth_headers):
        """Test successful market data synchronization."""
        # Mock market data service
        mock_service_instance = Mock()
        
        # Mock market data series
        mock_spy_data = MarketDataSeries(
            symbol='SPY',
            data=Mock(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            total_records=252,
            missing_dates=[],
            data_quality_score=0.98
        )
        
        mock_qqq_data = MarketDataSeries(
            symbol='QQQ',
            data=Mock(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            total_records=252,
            missing_dates=[],
            data_quality_score=0.97
        )
        
        mock_vix_data = MarketDataSeries(
            symbol='VIX',
            data=Mock(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            total_records=252,
            missing_dates=[],
            data_quality_score=0.95
        )
        
        # Configure mock returns
        mock_service_instance.fetch_spy_data.return_value = mock_spy_data
        mock_service_instance.fetch_qqq_data.return_value = mock_qqq_data
        mock_service_instance.fetch_vix_data.return_value = mock_vix_data
        mock_service_instance.store_market_data.return_value = 252
        
        mock_market_service.return_value = mock_service_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request
        request_data = {
            "symbols": ["SPY", "QQQ", "VIX"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "force_refresh": False
        }
        
        response = client.post(
            "/api/time-bins/market-data/sync",
            headers=auth_headers,
            json=request_data
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "market data sync completed" in data["message"].lower()
        
        # Verify sync response data
        sync_data = data["data"]
        assert "sync_id" in sync_data
        assert sync_data["symbols_synced"] == ["SPY", "QQQ", "VIX"]
        assert sync_data["records_added"]["SPY"] == 252
        assert sync_data["records_added"]["QQQ"] == 252
        assert sync_data["records_added"]["VIX"] == 252
        assert sync_data["data_quality_scores"]["SPY"] == 0.98
        assert sync_data["data_quality_scores"]["QQQ"] == 0.97
        assert sync_data["data_quality_scores"]["VIX"] == 0.95
        assert "sync_duration_seconds" in sync_data
        assert "sync_timestamp" in sync_data
        
        # Verify all methods were called
        mock_service_instance.fetch_spy_data.assert_called_once()
        mock_service_instance.fetch_qqq_data.assert_called_once()
        mock_service_instance.fetch_vix_data.assert_called_once()
        assert mock_service_instance.store_market_data.call_count == 3
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_market_data_service')
    def test_sync_market_data_partial_failure(self, mock_market_service, mock_auth, client, auth_headers):
        """Test market data sync with partial failures."""
        mock_service_instance = Mock()
        
        # SPY succeeds
        mock_spy_data = MarketDataSeries(
            symbol='SPY',
            data=Mock(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            total_records=252,
            missing_dates=[],
            data_quality_score=0.98
        )
        mock_service_instance.fetch_spy_data.return_value = mock_spy_data
        
        # QQQ fails
        mock_service_instance.fetch_qqq_data.side_effect = Exception("Network error")
        
        # VIX succeeds but low quality
        mock_vix_data = MarketDataSeries(
            symbol='VIX',
            data=Mock(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            total_records=200,  # Missing some data
            missing_dates=[],
            data_quality_score=0.85  # Below 90%
        )
        mock_service_instance.fetch_vix_data.return_value = mock_vix_data
        
        mock_service_instance.store_market_data.return_value = 252
        mock_market_service.return_value = mock_service_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request
        request_data = {
            "symbols": ["SPY", "QQQ", "VIX"],
            "force_refresh": True
        }
        
        response = client.post(
            "/api/time-bins/market-data/sync",
            headers=auth_headers,
            json=request_data
        )
        
        # Should still succeed with warnings
        assert response.status_code == 200
        data = response.json()
        
        sync_data = data["data"]
        assert sync_data["symbols_synced"] == ["SPY", "VIX"]  # QQQ failed
        assert len(sync_data["warnings"]) == 2  # QQQ failure + VIX low quality
        assert any("Failed to sync QQQ" in w for w in sync_data["warnings"])
        assert any("VIX data quality below 90%" in w for w in sync_data["warnings"])
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_market_data_service')
    def test_sync_market_data_unsupported_symbol(self, mock_market_service, mock_auth, client, auth_headers):
        """Test market data sync with unsupported symbol."""
        mock_service_instance = Mock()
        mock_market_service.return_value = mock_service_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Make request with unsupported symbol
        request_data = {
            "symbols": ["INVALID_SYMBOL"],
            "force_refresh": False
        }
        
        response = client.post(
            "/api/time-bins/market-data/sync",
            headers=auth_headers,
            json=request_data
        )
        
        # Should succeed but with warnings
        assert response.status_code == 200
        data = response.json()
        
        sync_data = data["data"]
        assert sync_data["symbols_synced"] == []
        assert len(sync_data["warnings"]) == 1
        assert "Unsupported symbol: INVALID_SYMBOL" in sync_data["warnings"][0]
    
    def test_all_endpoints_require_authentication(self, client):
        """Test that all endpoints require authentication."""
        endpoints = [
            "/api/time-bins/IPS_TM_10/9/30/market-correlation",
            "/api/time-bins/IPS_TM_10/9/30/benchmark-comparison",
            "/api/time-bins/IPS_TM_10/9/30/regime-analysis"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 422]  # Unauthorized or validation error
    
    def test_sync_endpoint_requires_authentication(self, client):
        """Test that sync endpoint requires authentication."""
        request_data = {
            "symbols": ["SPY"],
            "force_refresh": False
        }
        
        response = client.post("/api/time-bins/market-data/sync", json=request_data)
        assert response.status_code in [401, 422]  # Unauthorized or validation error
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_parameter_validation(self, mock_auth, client, auth_headers):
        """Test parameter validation for all endpoints."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Test invalid hour
        response = client.get(
            "/api/time-bins/IPS_TM_10/25/30/market-correlation",  # Hour 25 is invalid
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Test invalid minute bin
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/45/benchmark-comparison",  # Minute bin 45 is invalid
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Test invalid date format
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/regime-analysis?start_date=invalid-date",
            headers=auth_headers
        )
        assert response.status_code == 422
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_benchmark_analyzer')
    def test_error_handling_and_logging(self, mock_analyzer, mock_auth, client, auth_headers):
        """Test proper error handling and logging."""
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.calculate_beta_coefficients.side_effect = Exception("Database connection failed")
        mock_analyzer.return_value = mock_analyzer_instance
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/market-correlation",
            headers=auth_headers
        )
        
        assert response.status_code == 500
        assert "Market correlation analysis failed" in response.json()["detail"]
    
    @pytest.mark.integration
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_end_to_end_market_analysis_workflow(self, mock_auth, client, auth_headers):
        """Integration test for complete market analysis workflow."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        with patch('trading_platform.api.routers.time_bin_analytics.get_market_data_service') as mock_market_service, \
             patch('trading_platform.api.routers.time_bin_analytics.get_benchmark_analyzer') as mock_benchmark, \
             patch('trading_platform.api.routers.time_bin_analytics.get_vix_analyzer') as mock_vix:
            
            # Setup comprehensive mocks for end-to-end test
            self._setup_comprehensive_mocks(mock_market_service, mock_benchmark, mock_vix)
            
            # 1. First sync market data
            sync_response = client.post(
                "/api/time-bins/market-data/sync",
                headers=auth_headers,
                json={"symbols": ["SPY", "QQQ", "VIX"]}
            )
            assert sync_response.status_code == 200
            
            # 2. Then analyze market correlation
            correlation_response = client.get(
                "/api/time-bins/IPS_TM_10/9/30/market-correlation",
                headers=auth_headers
            )
            assert correlation_response.status_code == 200
            
            # 3. Get comprehensive benchmark comparison
            benchmark_response = client.get(
                "/api/time-bins/IPS_TM_10/9/30/benchmark-comparison",
                headers=auth_headers
            )
            assert benchmark_response.status_code == 200
            
            # 4. Analyze regime performance
            regime_response = client.get(
                "/api/time-bins/IPS_TM_10/9/30/regime-analysis",
                headers=auth_headers
            )
            assert regime_response.status_code == 200
            
            # Verify all responses contain expected data structures
            assert "beta_coefficients" in correlation_response.json()["data"]
            assert "alpha_metrics" in benchmark_response.json()["data"]
            assert "regime_performance" in regime_response.json()["data"]
    
    def _setup_comprehensive_mocks(self, mock_market_service, mock_benchmark, mock_vix):
        """Setup comprehensive mocks for end-to-end testing."""
        # Market data service mocks
        mock_market_instance = Mock()
        mock_market_data = MarketDataSeries(
            symbol='SPY', data=Mock(), start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31), total_records=252, missing_dates=[], data_quality_score=0.98
        )
        mock_market_instance.fetch_spy_data.return_value = mock_market_data
        mock_market_instance.fetch_qqq_data.return_value = mock_market_data
        mock_market_instance.fetch_vix_data.return_value = mock_market_data
        mock_market_instance.store_market_data.return_value = 252
        mock_market_service.return_value = mock_market_instance
        
        # Benchmark analyzer mocks
        mock_benchmark_instance = Mock()
        mock_benchmark_instance.calculate_beta_coefficients.return_value = BetaCoefficients(
            spy_beta=0.65, qqq_beta=0.58, spy_r_squared=0.42, qqq_r_squared=0.38,
            spy_correlation=0.65, qqq_correlation=0.62, sample_size=120, calculation_period_days=180
        )
        mock_benchmark_instance.calculate_alpha_metrics.return_value = AlphaMetrics(
            spy_alpha_annual=0.08, qqq_alpha_annual=0.06, spy_alpha_daily=0.0003, qqq_alpha_daily=0.0002,
            jensen_alpha=0.0004, information_ratio_spy=1.25, information_ratio_qqq=1.15,
            tracking_error_spy=0.06, tracking_error_qqq=0.05, treynor_ratio=0.12
        )
        mock_benchmark_instance.test_market_neutrality.return_value = MarketNeutralityTest(
            is_market_neutral_spy=True, is_market_neutral_qqq=True, spy_correlation_p_value=0.12,
            qqq_correlation_p_value=0.08, spy_beta_p_value=0.15, qqq_beta_p_value=0.11,
            market_neutrality_score=0.82, independence_test_statistic=1.25, independence_p_value=0.21
        )
        dates = [datetime(2024, 1, 1) + timedelta(days=i*30) for i in range(6)]
        mock_benchmark_instance.calculate_correlation_stability.return_value = CorrelationStability(
            rolling_correlations_spy=[0.65, 0.58, 0.72, 0.61, 0.69, 0.63],
            rolling_correlations_qqq=[0.62, 0.55, 0.69, 0.58, 0.66, 0.60],
            correlation_dates=dates, correlation_volatility_spy=0.08, correlation_volatility_qqq=0.07,
            correlation_trend_spy=-0.02, correlation_trend_qqq=-0.015, stability_score_spy=0.78,
            stability_score_qqq=0.81, regime_correlation_spy={"Low": 0.45}, regime_correlation_qqq={"Low": 0.42}
        )
        mock_benchmark.return_value = mock_benchmark_instance
        
        # VIX analyzer mocks
        mock_vix_instance = Mock()
        alignments = [TradeRegimeAlignment(
            trade_timestamp=datetime(2024, 1, 1, 9, 30), entry_price=100.0, vix_level=12.0,
            regime=VolatilityRegime.LOW, days_since_regime_start=5, trade_pnl=100.0
        )]
        mock_vix_instance.synchronize_vix_with_trades.return_value = alignments
        mock_vix_instance.analyze_regime_performance.return_value = {
            VolatilityRegime.LOW: {'total_trades': 1, 'win_rate': 1.0, 'avg_pnl': 100.0,
                                 'total_pnl': 100.0, 'profit_factor': float('inf'), 'sharpe_ratio': 1.5, 'avg_vix_level': 12.0}
        }
        mock_vix_instance.fetch_vix_data.return_value = Mock()
        mock_vix_instance.classify_volatility_regimes.return_value = []
        mock_vix_instance.detect_regime_transitions.return_value = []
        mock_vix.return_value = mock_vix_instance


if __name__ == "__main__":
    pytest.main([__file__])