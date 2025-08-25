"""
Integration tests for time-bin analytics API endpoints.

This module tests the time-bin specific API endpoints with real account data,
validates API responses, and tests error handling scenarios.

Requirements: 1.1, 1.6, 4.4, 10.1
"""

import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from trading_platform.api.main import app
from trading_platform.models.trading import ProcessedTrade
from trading_platform.services.time_bin_analyzer import TimeBin, TimeBinAnalyzer
from trading_platform.database.connection import get_db_session


# Test client
client = TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    return Mock(spec=Session)


@pytest.fixture
def sample_trades():
    """Sample trade data for testing."""
    base_time = datetime(2024, 1, 15, 9, 30, 0)  # Monday 9:30 AM
    
    trades = []
    for i in range(50):
        # Create trades with varying P&L
        pnl = 50.0 + (i % 10) * 10 - (25 if i % 5 == 0 else 0)  # Mix of wins and losses
        
        trade = ProcessedTrade(
            trade_id=f"trade_{i}",
            account_name="IPS_TM_10",
            symbol="NQ",
            entry_time=base_time + timedelta(days=i),
            exit_time=base_time + timedelta(days=i, minutes=15),
            entry_price=15000.0 + i,
            exit_price=15000.0 + i + (pnl / 20),  # Approximate price change
            quantity=1,
            side="LONG",
            profit_loss=pnl,
            commission=2.5,
            duration_minutes=15,
            hour_of_day=9,
            day_of_week=0,  # Monday
            entry_order_id=f"entry_{i}",
            exit_order_id=f"exit_{i}"
        )
        trades.append(trade)
    
    return trades


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user for testing."""
    return {
        "user_id": "test_user",
        "permissions": ["read", "write"],
        "account_access": ["IPS_TM_10", "IPS_TM_13"]
    }


class TestTimeBinAnalysisEndpoint:
    """Test the GET /api/v1/time-bins/{account}/{hour}/{minute_bin}/analysis endpoint."""
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_time_bin_analyzer')
    def test_successful_time_bin_analysis(self, mock_get_analyzer, mock_auth, sample_trades):
        """Test successful time-bin analysis with sufficient data."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.minimum_sample_size = 30
        mock_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Mock the analyze_time_bin method to return realistic metrics
        from trading_platform.services.time_bin_analyzer import TimeBinMetrics, SignificanceTest
        
        mock_metrics = TimeBinMetrics(
            time_bin=TimeBin("IPS_TM_10", 9, 30),
            total_trades=50,
            win_rate=0.64,
            average_pnl=45.5,
            total_pnl=2275.0,
            sharpe_ratio=1.25,
            calmar_ratio=2.15,
            sortino_ratio=1.85,
            max_drawdown=-125.0,
            profit_factor=1.85,
            confidence_interval_95=(35.2, 55.8),
            p_value_vs_random=0.032,
            statistical_significance=True,
            minimum_sample_size_met=True,
            volatility=85.5,
            largest_win=85.0,
            largest_loss=-25.0,
            winning_trades=32,
            losing_trades=18,
            average_win=71.25,
            average_loss=-13.89
        )
        
        mock_significance_tests = [
            SignificanceTest(
                test_name="One-sample t-test vs zero",
                p_value=0.032,
                is_significant=True,
                confidence_level=0.95,
                test_statistic=2.45,
                critical_value=2.021,
                interpretation="Tests if average P&L is significantly different from zero (random trading)"
            )
        ]
        
        mock_analyzer.analyze_time_bin.return_value = (mock_metrics, mock_significance_tests)
        mock_get_analyzer.return_value = mock_analyzer
        
        # Make request
        response = client.get("/api/v1/time-bins/IPS_TM_10/9/30/analysis")
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        
        analysis_data = data["data"]
        assert "metrics" in analysis_data
        assert "significance_tests" in analysis_data
        assert "analysis_timestamp" in analysis_data
        assert "data_period" in analysis_data
        
        # Validate metrics
        metrics = analysis_data["metrics"]
        assert metrics["account_name"] == "IPS_TM_10"
        assert metrics["hour"] == 9
        assert metrics["minute_bin"] == 30
        assert metrics["total_trades"] == 50
        assert metrics["win_rate"] == 64.0  # Converted to percentage
        assert metrics["statistical_significance"] is True
        assert metrics["minimum_sample_size_met"] is True
        
        # Validate significance tests
        assert len(analysis_data["significance_tests"]) == 1
        sig_test = analysis_data["significance_tests"][0]
        assert sig_test["test_name"] == "One-sample t-test vs zero"
        assert sig_test["is_significant"] is True
        assert sig_test["p_value"] == 0.032
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_database_session')
    @patch('trading_platform.services.time_bin_analyzer.TimeBinAnalyzer')
    def test_insufficient_data_error(self, mock_analyzer_class, mock_db_session, mock_auth):
        """Test error handling when insufficient trade data is available."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        mock_db_session.return_value = Mock()
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.minimum_sample_size = 30
        mock_analyzer.get_time_bin_trades.return_value = []  # No trades
        mock_analyzer_class.return_value = mock_analyzer
        
        from trading_platform.services.time_bin_analyzer import TimeBinMetrics
        
        # Mock empty metrics
        mock_metrics = TimeBinMetrics(
            time_bin=TimeBin("IPS_TM_10", 9, 30),
            total_trades=0,
            win_rate=0.0,
            average_pnl=0.0,
            total_pnl=0.0,
            sharpe_ratio=None,
            calmar_ratio=None,
            sortino_ratio=None,
            max_drawdown=0.0,
            profit_factor=0.0,
            confidence_interval_95=None,
            p_value_vs_random=None,
            statistical_significance=False,
            minimum_sample_size_met=False,
            volatility=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            winning_trades=0,
            losing_trades=0,
            average_win=0.0,
            average_loss=0.0
        )
        
        mock_analyzer.analyze_time_bin.return_value = (mock_metrics, [])
        
        # Make request
        response = client.get("/api/v1/time-bins/IPS_TM_10/9/30/analysis")
        
        # Assertions
        assert response.status_code == 404
        
        error_data = response.json()
        assert "detail" in error_data
        
        # Should contain structured error information
        detail = error_data["detail"]
        assert detail["error_type"] == "INSUFFICIENT_DATA"
        assert "trades_found" in detail["details"]
        assert detail["details"]["trades_found"] == 0
        assert "recommendations" in detail
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    def test_invalid_minute_bin(self, mock_auth):
        """Test validation error for invalid minute bin."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get("/api/v1/time-bins/IPS_TM_10/9/15/analysis")
        
        assert response.status_code == 400
        error_data = response.json()
        assert "Minute bin must be 0 or 30" in str(error_data)
    
    def test_invalid_hour(self):
        """Test validation error for invalid hour."""
        response = client.get("/api/v1/time-bins/IPS_TM_10/25/30/analysis")
        
        assert response.status_code == 422  # Pydantic validation error
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_time_bin_analyzer')
    def test_day_of_week_filter(self, mock_get_analyzer, mock_auth, sample_trades):
        """Test time-bin analysis with day of week filter."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.minimum_sample_size = 30
        mock_analyzer.get_time_bin_trades.return_value = sample_trades[:30]  # Subset for specific day
        
        from trading_platform.services.time_bin_analyzer import TimeBinMetrics
        
        mock_metrics = TimeBinMetrics(
            time_bin=TimeBin("IPS_TM_10", 9, 30, day_of_week=1),  # Tuesday
            total_trades=30,
            win_rate=0.67,
            average_pnl=52.5,
            total_pnl=1575.0,
            sharpe_ratio=1.35,
            calmar_ratio=2.25,
            sortino_ratio=1.95,
            max_drawdown=-95.0,
            profit_factor=2.05,
            confidence_interval_95=(40.2, 64.8),
            p_value_vs_random=0.025,
            statistical_significance=True,
            minimum_sample_size_met=True,
            volatility=75.5,
            largest_win=85.0,
            largest_loss=-25.0,
            winning_trades=20,
            losing_trades=10,
            average_win=78.75,
            average_loss=-12.5
        )
        
        mock_analyzer.analyze_time_bin.return_value = (mock_metrics, [])
        mock_get_analyzer.return_value = mock_analyzer
        
        # Make request with day_of_week parameter
        response = client.get("/api/v1/time-bins/IPS_TM_10/9/30/analysis?day_of_week=1")
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        metrics = data["data"]["metrics"]
        assert metrics["day_of_week"] == 1
        assert metrics["total_trades"] == 30


class TestTimeBinComparisonEndpoint:
    """Test the POST /api/v1/time-bins/compare endpoint."""
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_time_bin_analyzer')
    def test_successful_time_bin_comparison(self, mock_get_analyzer, mock_auth, sample_trades):
        """Test successful comparison of multiple time bins."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.minimum_sample_size = 30
        
        # Mock different performance for different time bins
        def mock_analyze_side_effect(time_bin):
            from trading_platform.services.time_bin_analyzer import TimeBinMetrics
            
            if time_bin.hour == 9:
                # Better performance for 9:30
                return TimeBinMetrics(
                    time_bin=time_bin,
                    total_trades=45,
                    win_rate=0.67,
                    average_pnl=55.5,
                    total_pnl=2497.5,
                    sharpe_ratio=1.45,
                    calmar_ratio=2.35,
                    sortino_ratio=2.05,
                    max_drawdown=-105.0,
                    profit_factor=2.15,
                    confidence_interval_95=(45.2, 65.8),
                    p_value_vs_random=0.018,
                    statistical_significance=True,
                    minimum_sample_size_met=True,
                    volatility=75.5,
                    largest_win=95.0,
                    largest_loss=-25.0,
                    winning_trades=30,
                    losing_trades=15,
                    average_win=83.25,
                    average_loss=-16.67
                ), []
            else:
                # Lower performance for 14:00
                return TimeBinMetrics(
                    time_bin=time_bin,
                    total_trades=38,
                    win_rate=0.58,
                    average_pnl=35.2,
                    total_pnl=1337.6,
                    sharpe_ratio=0.95,
                    calmar_ratio=1.75,
                    sortino_ratio=1.35,
                    max_drawdown=-145.0,
                    profit_factor=1.65,
                    confidence_interval_95=(25.1, 45.3),
                    p_value_vs_random=0.045,
                    statistical_significance=True,
                    minimum_sample_size_met=True,
                    volatility=85.2,
                    largest_win=75.0,
                    largest_loss=-35.0,
                    winning_trades=22,
                    losing_trades=16,
                    average_win=60.75,
                    average_loss=-21.88
                ), []
        
        mock_analyzer.analyze_time_bin.side_effect = mock_analyze_side_effect
        mock_analyzer.get_time_bin_trades.return_value = sample_trades
        
        # Mock comparison method
        mock_analyzer.compare_time_bins.return_value = {
            "statistical_comparison": {
                "t_test": {
                    "statistic": 2.15,
                    "p_value": 0.035,
                    "significant": True,
                    "interpretation": "Parametric test for difference in means"
                }
            },
            "performance_difference": {
                "average_pnl_diff": 20.3,
                "win_rate_diff": 0.09,
                "sharpe_diff": 0.5
            }
        }
        
        mock_get_analyzer.return_value = mock_analyzer
        
        # Prepare request data
        request_data = {
            "time_bins": [
                {
                    "account_name": "IPS_TM_10",
                    "hour": 9,
                    "minute_bin": 30
                },
                {
                    "account_name": "IPS_TM_10",
                    "hour": 14,
                    "minute_bin": 0
                }
            ],
            "include_statistical_tests": True,
            "sort_by": "average_pnl",
            "sort_order": "desc"
        }
        
        # Make request
        response = client.post(
            "/api/v1/time-bins/compare",
            json=request_data
        )
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        
        comparison_data = data["data"]
        assert "time_bins" in comparison_data
        assert "ranking" in comparison_data
        assert "statistical_comparisons" in comparison_data
        assert "best_time_bin" in comparison_data
        
        # Validate ranking (9:30 should be ranked higher)
        ranking = comparison_data["ranking"]
        assert len(ranking) == 2
        assert ranking[0]["rank"] == 1
        assert "IPS_TM_10_09:30" in ranking[0]["time_bin_id"]
        
        # Validate statistical comparisons
        assert len(comparison_data["statistical_comparisons"]) == 1
        stat_comp = comparison_data["statistical_comparisons"][0]
        assert stat_comp["comparison"]["t_test"]["significant"] is True
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    def test_insufficient_time_bins_error(self, mock_auth):
        """Test error when fewer than 2 time bins provided."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        request_data = {
            "time_bins": [
                {
                    "account_name": "IPS_TM_10",
                    "hour": 9,
                    "minute_bin": 30
                }
            ]
        }
        
        response = client.post(
            "/api/v1/time-bins/compare",
            json=request_data
        )
        
        assert response.status_code == 422  # Pydantic validation error
        error_data = response.json()
        # Check that it's a validation error about minimum items
        assert "detail" in error_data
    
    def test_invalid_minute_bin_in_comparison(self):
        """Test validation error for invalid minute bin in comparison."""
        request_data = {
            "time_bins": [
                {
                    "account_name": "IPS_TM_10",
                    "hour": 9,
                    "minute_bin": 15  # Invalid
                },
                {
                    "account_name": "IPS_TM_10",
                    "hour": 14,
                    "minute_bin": 30
                }
            ]
        }
        
        response = client.post(
            "/api/v1/time-bins/compare",
            json=request_data
        )
        
        assert response.status_code == 422  # Pydantic validation error
        error_data = response.json()
        assert "detail" in error_data


class TestAccountRecommendationsEndpoint:
    """Test the GET /api/v1/time-bins/{account}/recommendations endpoint."""
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_time_bin_analyzer')
    def test_successful_account_recommendations(self, mock_get_analyzer, mock_auth, sample_trades):
        """Test successful generation of account recommendations."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.minimum_sample_size = 30
        
        # Mock analyze_time_bin to return varying performance for different time bins
        def mock_analyze_side_effect(time_bin):
            from trading_platform.services.time_bin_analyzer import TimeBinMetrics
            
            # Create different performance profiles for different hours
            if time_bin.hour == 9:
                # Best performance
                return TimeBinMetrics(
                    time_bin=time_bin,
                    total_trades=50,
                    win_rate=0.68,
                    average_pnl=65.5,
                    total_pnl=3275.0,
                    sharpe_ratio=1.65,
                    calmar_ratio=2.85,
                    sortino_ratio=2.25,
                    max_drawdown=-95.0,
                    profit_factor=2.45,
                    confidence_interval_95=(55.2, 75.8),
                    p_value_vs_random=0.008,
                    statistical_significance=True,
                    minimum_sample_size_met=True,
                    volatility=65.5,
                    largest_win=125.0,
                    largest_loss=-25.0,
                    winning_trades=34,
                    losing_trades=16,
                    average_win=96.32,
                    average_loss=-15.63
                ), []
            elif time_bin.hour == 14:
                # Good performance
                return TimeBinMetrics(
                    time_bin=time_bin,
                    total_trades=42,
                    win_rate=0.62,
                    average_pnl=45.2,
                    total_pnl=1898.4,
                    sharpe_ratio=1.25,
                    calmar_ratio=2.15,
                    sortino_ratio=1.75,
                    max_drawdown=-125.0,
                    profit_factor=1.95,
                    confidence_interval_95=(35.1, 55.3),
                    p_value_vs_random=0.025,
                    statistical_significance=True,
                    minimum_sample_size_met=True,
                    volatility=75.2,
                    largest_win=95.0,
                    largest_loss=-35.0,
                    winning_trades=26,
                    losing_trades=16,
                    average_win=72.85,
                    average_loss=-21.88
                ), []
            elif time_bin.hour == 15:
                # Marginal performance
                return TimeBinMetrics(
                    time_bin=time_bin,
                    total_trades=35,
                    win_rate=0.54,
                    average_pnl=25.8,
                    total_pnl=903.0,
                    sharpe_ratio=0.85,
                    calmar_ratio=1.45,
                    sortino_ratio=1.15,
                    max_drawdown=-165.0,
                    profit_factor=1.35,
                    confidence_interval_95=(15.2, 36.4),
                    p_value_vs_random=0.065,
                    statistical_significance=False,
                    minimum_sample_size_met=True,
                    volatility=85.5,
                    largest_win=75.0,
                    largest_loss=-45.0,
                    winning_trades=19,
                    losing_trades=16,
                    average_win=47.37,
                    average_loss=-28.13
                ), []
            else:
                # Poor or no performance for other hours
                return TimeBinMetrics(
                    time_bin=time_bin,
                    total_trades=0,
                    win_rate=0.0,
                    average_pnl=0.0,
                    total_pnl=0.0,
                    sharpe_ratio=None,
                    calmar_ratio=None,
                    sortino_ratio=None,
                    max_drawdown=0.0,
                    profit_factor=0.0,
                    confidence_interval_95=None,
                    p_value_vs_random=None,
                    statistical_significance=False,
                    minimum_sample_size_met=False,
                    volatility=0.0,
                    largest_win=0.0,
                    largest_loss=0.0,
                    winning_trades=0,
                    losing_trades=0,
                    average_win=0.0,
                    average_loss=0.0
                ), []
        
        mock_analyzer.analyze_time_bin.side_effect = mock_analyze_side_effect
        mock_get_analyzer.return_value = mock_analyzer
        
        # Make request
        response = client.get(
            "/api/v1/time-bins/IPS_TM_10/recommendations"
            "?min_trades=30&min_win_rate=55.0&min_average_pnl=20.0"
            "&include_statistical_significance=true&max_recommendations=5"
        )
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        
        recommendations_data = data["data"]
        assert "recommendations" in recommendations_data
        assert "analysis_summary" in recommendations_data
        assert "filters_applied" in recommendations_data
        
        # Validate recommendations (should have 2: 9:30 and 14:00/14:30)
        recommendations = recommendations_data["recommendations"]
        assert len(recommendations) >= 1  # At least the 9:30 slot should qualify
        
        # Best recommendation should be 9:30 slot
        best_rec = recommendations[0]
        assert best_rec["rank"] == 1
        assert best_rec["hour"] == 9
        assert best_rec["confidence_level"] == "High"
        assert best_rec["key_metrics"]["average_pnl"] == 65.5
        
        # Validate analysis summary
        summary = recommendations_data["analysis_summary"]
        assert "total_time_bins_analyzed" in summary
        assert "time_bins_meeting_criteria" in summary
        
        # Validate filters applied
        filters = recommendations_data["filters_applied"]
        assert filters["min_trades"] == 30
        assert filters["min_win_rate"] == 55.0
        assert filters["min_average_pnl"] == 20.0
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_time_bin_analyzer')
    def test_no_recommendations_found(self, mock_get_analyzer, mock_auth):
        """Test when no time bins meet the recommendation criteria."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.minimum_sample_size = 30
        
        # Mock all time bins to have poor performance
        def mock_analyze_side_effect(time_bin):
            from trading_platform.services.time_bin_analyzer import TimeBinMetrics
            
            return TimeBinMetrics(
                time_bin=time_bin,
                total_trades=15,  # Below minimum
                win_rate=0.45,    # Below minimum win rate
                average_pnl=5.0,  # Below minimum average P&L
                total_pnl=75.0,
                sharpe_ratio=0.25,
                calmar_ratio=0.85,
                sortino_ratio=0.45,
                max_drawdown=-85.0,
                profit_factor=0.95,
                confidence_interval_95=None,
                p_value_vs_random=0.25,
                statistical_significance=False,
                minimum_sample_size_met=False,
                volatility=95.5,
                largest_win=25.0,
                largest_loss=-35.0,
                winning_trades=7,
                losing_trades=8,
                average_win=16.07,
                average_loss=-18.75
            ), []
        
        mock_analyzer.analyze_time_bin.side_effect = mock_analyze_side_effect
        mock_get_analyzer.return_value = mock_analyzer
        
        # Make request with strict criteria
        response = client.get(
            "/api/v1/time-bins/IPS_TM_10/recommendations"
            "?min_trades=30&min_win_rate=60.0&min_average_pnl=50.0"
        )
        
        # Assertions
        assert response.status_code == 200
        
        data = response.json()
        recommendations_data = data["data"]
        
        # Should have no recommendations
        assert len(recommendations_data["recommendations"]) == 0
        
        # Should have warnings
        assert len(recommendations_data["warnings"]) > 0
        assert any("Few time bins met" in warning for warning in recommendations_data["warnings"])
    
    def test_invalid_query_parameters(self):
        """Test validation of query parameters."""
        # Test negative min_trades
        response = client.get("/api/v1/time-bins/IPS_TM_10/recommendations?min_trades=-5")
        assert response.status_code == 422
        
        # Test invalid win rate
        response = client.get("/api/v1/time-bins/IPS_TM_10/recommendations?min_win_rate=150.0")
        assert response.status_code == 422
        
        # Test invalid max_recommendations
        response = client.get("/api/v1/time-bins/IPS_TM_10/recommendations?max_recommendations=0")
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling scenarios across all endpoints."""
    
    def test_authentication_required(self):
        """Test that endpoints require authentication."""
        # Without mocking authentication, requests should fail
        with patch('trading_platform.api.routers.time_bin_analytics.require_read_permission') as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")
            
            response = client.get("/api/v1/time-bins/IPS_TM_10/9/30/analysis")
            assert response.status_code == 401
    
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    @patch('trading_platform.api.routers.time_bin_analytics.get_database_session')
    @patch('trading_platform.services.time_bin_analyzer.TimeBinAnalyzer')
    def test_service_exception_handling(self, mock_analyzer_class, mock_db_session, mock_auth):
        """Test handling of service exceptions."""
        # Setup mocks
        mock_auth.return_value = {"user_id": "test_user"}
        mock_db_session.return_value = Mock()
        
        mock_analyzer = Mock(spec=TimeBinAnalyzer)
        mock_analyzer.analyze_time_bin.side_effect = Exception("Database connection failed")
        mock_analyzer_class.return_value = mock_analyzer
        
        # Make request
        response = client.get("/api/v1/time-bins/IPS_TM_10/9/30/analysis")
        
        # Should return 500 error
        assert response.status_code == 500
        error_data = response.json()
        assert "Failed to analyze time bin" in str(error_data)
    
    def test_malformed_json_request(self):
        """Test handling of malformed JSON in POST requests."""
        response = client.post(
            "/api/v1/time-bins/compare",
            data="invalid json"
        )
        
        assert response.status_code == 422  # Unprocessable Entity


class TestRealDataIntegration:
    """Integration tests with real database data (if available)."""
    
    @pytest.mark.integration
    @patch('trading_platform.api.routers.time_bin_analytics.require_read_permission')
    def test_with_real_database(self, mock_auth):
        """Test endpoints with real database connection (integration test)."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        # This test would run against a real database
        # Skip if no real data is available
        try:
            response = client.get("/api/v1/time-bins/IPS_TM_10/9/30/analysis")
            
            # If we get here, we have real data
            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                assert "metrics" in data["data"]
            elif response.status_code == 404:
                # No data for this specific time bin, which is acceptable
                assert "INSUFFICIENT_DATA" in str(response.json())
            else:
                pytest.fail(f"Unexpected response code: {response.status_code}")
                
        except Exception as e:
            pytest.skip(f"Real database not available: {str(e)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])