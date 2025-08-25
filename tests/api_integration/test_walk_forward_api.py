"""
Test suite for Walk-Forward Analysis API endpoints.

Comprehensive testing of walk-forward validation API, strategy robustness
assessment, performance decay analysis, and background processing with
real-world scenarios and edge cases.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from trading_platform.api.main import app
from trading_platform.services.walk_forward.out_of_sample_validator import (
    OutOfSampleValidator,
    WalkForwardValidationResult,
    PeriodPerformance,
    ValidationMethodEnum as ServiceValidationMethod,
    PerformanceMetrics
)
from trading_platform.services.walk_forward.performance_decay_tracker import (
    PerformanceDecayTracker,
    StrategyDegradationResult,
    PredictionAccuracyResult,
    RetrainingAnalysisResult,
    PersistenceTestResult,
    DegradationSeverity,
    AlertType,
    DegradationAlert
)
from trading_platform.services.time_bin_analyzer import TimeBin


class TestWalkForwardAPI:
    """Test suite for Walk-Forward Analysis API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test_token"}
    
    @pytest.fixture
    def sample_validation_request(self):
        """Create sample walk-forward validation request."""
        return {
            "validation_method": "anchored_walk_forward",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "min_in_sample_days": 30,
            "out_of_sample_days": 10,
            "step_days": 5,
            "min_trades_threshold": 10,
            "performance_stability_threshold": 0.3,
            "overfitting_detection_threshold": 0.5,
            "confidence_level": 0.95
        }
    
    @pytest.fixture
    def sample_validation_result(self):
        """Create sample validation result."""
        
        # Create mock performance metrics
        in_sample_metrics = PerformanceMetrics(
            total_trades=30,
            winning_trades=18,
            losing_trades=12,
            win_rate=0.6,
            average_pnl=125.0,
            total_pnl=3750.0,
            average_winner=250.0,
            average_loser=-100.0,
            largest_winner=500.0,
            largest_loser=-200.0,
            profit_factor=2.25,
            sharpe_ratio=1.35,
            max_drawdown_pct=8.5,
            max_consecutive_losses=3,
            total_commission=75.0,
            avg_trade_duration_minutes=28.0,
            longest_drawdown_period_days=3,
            calmar_ratio=0.159
        )
        
        out_of_sample_metrics = PerformanceMetrics(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            average_pnl=115.0,
            total_pnl=1150.0,
            average_winner=230.0,
            average_loser=-95.0,
            largest_winner=450.0,
            largest_loser=-180.0,
            profit_factor=2.1,
            sharpe_ratio=1.25,
            max_drawdown_pct=9.0,
            max_consecutive_losses=2,
            total_commission=25.0,
            avg_trade_duration_minutes=26.0,
            longest_drawdown_period_days=2,
            calmar_ratio=0.139
        )
        
        # Create period performance
        period_performance = PeriodPerformance(
            period_id="period_1",
            in_sample_start=datetime(2024, 1, 1),
            in_sample_end=datetime(2024, 1, 31),
            out_of_sample_start=datetime(2024, 2, 1),
            out_of_sample_end=datetime(2024, 2, 10),
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_of_sample_metrics,
            trades_count_in_sample=30,
            trades_count_out_of_sample=10
        )
        
        # Create validation result
        result = Mock(spec=WalkForwardValidationResult)
        result.validation_method = ServiceValidationMethod.ANCHORED_WALK_FORWARD
        result.account_name = "TEST_ACCOUNT"
        result.time_bin = TimeBin.HOUR_9_MINUTE_30
        result.period_performances = [period_performance]
        result.overall_metrics = {
            "avg_out_of_sample_sharpe": 1.25,
            "avg_out_of_sample_win_rate": 0.6,
            "overall_robustness_score": 0.78
        }
        result.stability_analysis = {
            "sharpe_ratio_std": 0.15,
            "sharpe_ratio_cv": 0.12,
            "performance_consistency": 0.85
        }
        result.overfitting_analysis = {
            "avg_sharpe_gap": 0.1,
            "overfitting_risk_score": 0.2,
            "periods_with_large_gaps": 0
        }
        result.consistency_analysis = {
            "positive_period_ratio": 1.0,
            "good_sharpe_period_ratio": 1.0,
            "overall_consistency_score": 0.9
        }
        result.recommendation = "RECOMMENDED - Strategy demonstrates good robustness"
        result.generation_timestamp = datetime.now()
        result.start_date = datetime(2024, 1, 1)
        result.end_date = datetime(2024, 6, 30)
        
        return result


class TestWalkForwardValidation:
    """Test walk-forward validation endpoints."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_out_of_sample_validator')
    def test_run_walk_forward_validation_success(self, mock_validator, mock_auth,
                                               client, auth_headers, sample_validation_request,
                                               sample_validation_result):
        """Test successful walk-forward validation."""
        
        # Mock authentication
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock validator
        mock_validator_instance = Mock(spec=OutOfSampleValidator)
        mock_validator_instance.anchored_walk_forward.return_value = sample_validation_result
        mock_validator.return_value = mock_validator_instance
        
        # Make request
        response = client.post(
            "/api/time-bins/TEST_ACCOUNT/9/30/walk-forward",
            headers=auth_headers,
            json=sample_validation_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "completed successfully" in data["message"]
        
        # Verify response structure
        validation_data = data["data"]
        assert validation_data["account_name"] == "TEST_ACCOUNT"
        assert validation_data["time_bin"] == "09:30"
        assert validation_data["validation_method"] == "anchored_walk_forward"
        assert len(validation_data["period_performances"]) == 1
        assert "overall_metrics" in validation_data
        assert "stability_analysis" in validation_data
        assert "overfitting_analysis" in validation_data
        assert "recommendation" in validation_data
        
        # Verify validator was called
        mock_validator_instance.anchored_walk_forward.assert_called_once()
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_out_of_sample_validator')
    def test_run_validation_different_methods(self, mock_validator, mock_auth,
                                            client, auth_headers, sample_validation_result):
        """Test validation with different methods."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        validation_methods = [
            ("anchored_walk_forward", "anchored_walk_forward"),
            ("rolling_window", "rolling_window_validation"),
            ("expanding_window", "expanding_window_validation"),
            ("time_series_cv", "time_series_cross_validation")
        ]
        
        for api_method, service_method in validation_methods:
            # Mock validator for each method
            mock_validator_instance = Mock(spec=OutOfSampleValidator)
            setattr(mock_validator_instance, service_method, Mock(return_value=sample_validation_result))
            mock_validator.return_value = mock_validator_instance
            
            request_data = {
                "validation_method": api_method,
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "min_in_sample_days": 20,
                "out_of_sample_days": 5
            }
            
            if api_method == "time_series_cv":
                request_data["n_splits"] = 3
                request_data["test_size_ratio"] = 0.3
                request_data["gap_days"] = 1
            
            response = client.post(
                f"/api/time-bins/TEST_ACCOUNT/14/0/walk-forward",
                headers=auth_headers,
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            
            # Verify correct method was called
            method_mock = getattr(mock_validator_instance, service_method)
            method_mock.assert_called_once()
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_validation_background_processing(self, mock_auth, client, auth_headers):
        """Test validation with background processing."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        request_data = {
            "validation_method": "anchored_walk_forward",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",  # Long period
            "min_in_sample_days": 60,
            "out_of_sample_days": 20
        }
        
        background_request = {
            "process_type": "walk_forward_validation",
            "priority": 1,
            "max_execution_time_minutes": 30,
            "enable_progress_tracking": True
        }
        
        # Mock background processing (would need more complex setup in real test)
        with patch('trading_platform.api.routers.walk_forward_analytics._estimate_validation_time') as mock_estimate:
            mock_estimate.return_value = 10  # Force background processing
            
            response = client.post(
                "/api/time-bins/LONG_TEST/9/30/walk-forward",
                headers=auth_headers,
                json=request_data,
                params={"background_process": background_request}
            )
            
            # Should return background process response for long-running validation
            assert response.status_code in [200, 202]  # Success or Accepted
    
    def test_validation_invalid_minute_bin(self, client, auth_headers, sample_validation_request):
        """Test validation with invalid minute bin."""
        
        with patch('trading_platform.api.dependencies.require_read_permission') as mock_auth:
            mock_auth.return_value = {"user_id": "test_user"}
            
            response = client.post(
                "/api/time-bins/TEST_ACCOUNT/9/15/walk-forward",  # Invalid minute bin
                headers=auth_headers,
                json=sample_validation_request
            )
            
            assert response.status_code == 400
            assert "must be 0 or 30" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_out_of_sample_validator')
    def test_validation_service_error(self, mock_validator, mock_auth,
                                    client, auth_headers, sample_validation_request):
        """Test validation when service throws error."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_validator_instance = Mock(spec=OutOfSampleValidator)
        mock_validator_instance.anchored_walk_forward.side_effect = ValueError("Insufficient data")
        mock_validator.return_value = mock_validator_instance
        
        response = client.post(
            "/api/time-bins/EMPTY_ACCOUNT/9/30/walk-forward",
            headers=auth_headers,
            json=sample_validation_request
        )
        
        assert response.status_code == 400
        assert "Insufficient data" in response.json()["detail"]


class TestStrategyRobustness:
    """Test strategy robustness assessment endpoints."""
    
    @pytest.fixture
    def sample_degradation_result(self):
        """Create sample degradation result."""
        
        alert = DegradationAlert(
            alert_type=AlertType.PERFORMANCE_DROP,
            severity=DegradationSeverity.MODERATE,
            message="Sharpe Ratio has decreased significantly",
            metric_name="sharpe_ratio",
            current_value=0.85,
            threshold_value=1.25,
            confidence_level=0.92,
            detected_at=datetime.now(),
            recommended_action="WARNING: Monitor closely"
        )
        
        result = Mock(spec=StrategyDegradationResult)
        result.overall_degradation_score = 0.45
        result.degradation_severity = DegradationSeverity.MODERATE
        result.active_alerts = [alert]
        result.performance_trend = {
            "sharpe_ratio_trend": -0.02,
            "win_rate_trend": -0.01,
            "average_pnl_trend": -8.5
        }
        result.degradation_rate = 0.05
        result.time_to_failure_estimate = 35.0
        result.confidence_in_degradation = 0.88
        result.key_degraded_metrics = ["sharpe_ratio", "win_rate"]
        result.recent_performance_change = {"sharpe_ratio_recent_change": -0.15}
        result.historical_context = {"historical_sharpe_mean": 1.2}
        result.recommendation = "MODERATE DEGRADATION DETECTED: Reduce position sizes"
        result.next_monitoring_interval = timedelta(hours=24)
        result.calculation_timestamp = datetime.now()
        
        return result
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_decay_tracker')
    @patch('trading_platform.api.routers.walk_forward_analytics._get_performance_history')
    def test_get_strategy_robustness_success(self, mock_get_history, mock_tracker, mock_auth,
                                           client, auth_headers, sample_degradation_result):
        """Test successful strategy robustness assessment."""
        
        # Mock authentication
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock performance history
        mock_get_history.return_value = ([Mock()], [Mock()])  # Recent, historical
        
        # Mock tracker
        mock_tracker_instance = Mock(spec=PerformanceDecayTracker)
        mock_tracker_instance.detect_strategy_degradation.return_value = sample_degradation_result
        mock_tracker.return_value = mock_tracker_instance
        
        # Make request
        response = client.get(
            "/api/time-bins/TEST_ACCOUNT/9/30/robustness",
            headers=auth_headers,
            params={
                "lookback_days": 30,
                "baseline_days": 90,
                "sensitivity": 0.05
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "assessment completed" in data["message"]
        
        # Verify response structure
        robustness_data = data["data"]
        assert robustness_data["account_name"] == "TEST_ACCOUNT"
        assert robustness_data["time_bin"] == "09:30"
        assert robustness_data["degradation_severity"] == "moderate"
        assert len(robustness_data["active_alerts"]) == 1
        assert "performance_trends" in robustness_data
        assert "recommendation" in robustness_data
        
        # Verify alert structure
        alert = robustness_data["active_alerts"][0]
        assert alert["alert_type"] == "performance_drop"
        assert alert["severity"] == "moderate"
        assert alert["metric_name"] == "sharpe_ratio"
        assert alert["current_value"] == 0.85
        
        # Verify tracker was called
        mock_tracker_instance.detect_strategy_degradation.assert_called_once()
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics._get_performance_history')
    def test_robustness_insufficient_data(self, mock_get_history, mock_auth,
                                        client, auth_headers):
        """Test robustness assessment with insufficient data."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        mock_get_history.return_value = (None, None)  # No data
        
        response = client.get(
            "/api/time-bins/EMPTY_ACCOUNT/9/30/robustness",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "Insufficient performance data" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_decay_tracker')
    @patch('trading_platform.api.routers.walk_forward_analytics._get_performance_history')
    def test_robustness_different_severities(self, mock_get_history, mock_tracker, mock_auth,
                                           client, auth_headers):
        """Test robustness assessment with different degradation severities."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        mock_get_history.return_value = ([Mock()], [Mock()])
        
        severities = [
            DegradationSeverity.NONE,
            DegradationSeverity.MILD,
            DegradationSeverity.MODERATE,
            DegradationSeverity.SEVERE,
            DegradationSeverity.CRITICAL
        ]
        
        for severity in severities:
            # Mock different severity results
            result = Mock(spec=StrategyDegradationResult)
            result.overall_degradation_score = {
                DegradationSeverity.NONE: 0.05,
                DegradationSeverity.MILD: 0.25,
                DegradationSeverity.MODERATE: 0.45,
                DegradationSeverity.SEVERE: 0.7,
                DegradationSeverity.CRITICAL: 0.9
            }[severity]
            result.degradation_severity = severity
            result.active_alerts = []
            result.performance_trend = {}
            result.time_to_failure_estimate = None
            result.confidence_in_degradation = 0.8
            result.key_degraded_metrics = []
            result.recommendation = f"{severity.value.upper()} degradation detected"
            result.next_monitoring_interval = timedelta(hours=24)
            result.calculation_timestamp = datetime.now()
            
            mock_tracker_instance = Mock(spec=PerformanceDecayTracker)
            mock_tracker_instance.detect_strategy_degradation.return_value = result
            mock_tracker.return_value = mock_tracker_instance
            
            response = client.get(
                f"/api/time-bins/TEST_{severity.value.upper()}/9/30/robustness",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["degradation_severity"] == severity.value


class TestDecayAnalysis:
    """Test comprehensive decay analysis endpoints."""
    
    @pytest.fixture
    def sample_prediction_result(self):
        """Create sample prediction accuracy result."""
        result = Mock(spec=PredictionAccuracyResult)
        result.predictions_count = 30
        result.correlation_coefficient = 0.75
        result.directional_accuracy = 0.68
        result.hit_ratio = 0.55
        result.mean_squared_error = 125.5
        result.r_squared = 0.56
        result.accuracy_trend = -0.02
        result.prediction_bias = 5.2
        return result
    
    @pytest.fixture
    def sample_retraining_result(self):
        """Create sample retraining analysis result."""
        result = Mock(spec=RetrainingAnalysisResult)
        result.current_model_age_days = 45
        result.optimal_retraining_days = 21
        result.performance_decay_rate = 0.008
        result.retraining_benefit_score = 0.15
        result.next_recommended_retraining = datetime.now() + timedelta(days=21)
        result.retraining_frequency_recommendation = "Retrain every 3 weeks"
        return result
    
    @pytest.fixture
    def sample_persistence_result(self):
        """Create sample persistence analysis result."""
        result = Mock(spec=PersistenceTestResult)
        result.persistence_score = 0.45
        result.mean_reversion_tendency = 0.35
        result.performance_autocorrelation = {1: 0.25, 2: 0.15, 3: 0.08}
        result.predictability_metrics = {"predictability_score": 0.60}
        result.momentum_periods = [(datetime.now(), datetime.now())]
        result.reversal_periods = []
        return result
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_decay_tracker')
    @patch('trading_platform.api.routers.walk_forward_analytics._get_performance_history')
    @patch('trading_platform.api.routers.walk_forward_analytics._run_prediction_accuracy_analysis')
    @patch('trading_platform.api.routers.walk_forward_analytics._run_retraining_analysis')
    @patch('trading_platform.api.routers.walk_forward_analytics._run_persistence_analysis')
    def test_get_decay_analysis_comprehensive(self, mock_persistence, mock_retraining, 
                                            mock_prediction, mock_get_history, mock_tracker, 
                                            mock_auth, client, auth_headers,
                                            sample_prediction_result, sample_retraining_result,
                                            sample_persistence_result, sample_degradation_result):
        """Test comprehensive decay analysis."""
        
        # Mock authentication
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock all analysis components
        mock_prediction.return_value = sample_prediction_result
        mock_retraining.return_value = sample_retraining_result
        mock_persistence.return_value = sample_persistence_result
        mock_get_history.return_value = ([Mock()], [Mock()])
        
        # Mock tracker for degradation analysis
        mock_tracker_instance = Mock(spec=PerformanceDecayTracker)
        mock_tracker_instance.detect_strategy_degradation.return_value = sample_degradation_result
        mock_tracker.return_value = mock_tracker_instance
        
        # Request with all analysis components
        response = client.get(
            "/api/time-bins/COMPREHENSIVE_TEST/9/30/decay-analysis",
            headers=auth_headers,
            params={
                "include_persistence": True,
                "include_degradation": True
            },
            json={
                "prediction_accuracy": {
                    "prediction_period_days": 30,
                    "include_confidence_intervals": True
                },
                "retraining_analysis": {
                    "lookback_days": 90,
                    "retraining_cost_factor": 1.5
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "decay analysis completed" in data["message"]
        
        # Verify response structure
        analysis_data = data["data"]
        assert analysis_data["account_name"] == "COMPREHENSIVE_TEST"
        assert analysis_data["time_bin"] == "09:30"
        assert "prediction_accuracy" in analysis_data
        assert "retraining_analysis" in analysis_data
        assert "degradation_assessment" in analysis_data
        assert "persistence_analysis" in analysis_data
        assert "overall_health_score" in analysis_data
        assert "priority_actions" in analysis_data
        
        # Verify prediction accuracy structure
        pred_acc = analysis_data["prediction_accuracy"]
        assert pred_acc["correlation_coefficient"] == 0.75
        assert pred_acc["directional_accuracy"] == 0.68
        
        # Verify retraining analysis structure
        retrain = analysis_data["retraining_analysis"]
        assert retrain["optimal_retraining_days"] == 21
        assert retrain["performance_decay_rate"] == 0.008
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_decay_analysis_minimal_request(self, mock_auth, client, auth_headers):
        """Test decay analysis with minimal request (no optional components)."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get(
            "/api/time-bins/MINIMAL_TEST/14/0/decay-analysis",
            headers=auth_headers,
            params={
                "include_persistence": False,
                "include_degradation": False
            }
        )
        
        # Should still succeed with basic analysis
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Should have minimal structure
        analysis_data = data["data"]
        assert "overall_health_score" in analysis_data
        assert "priority_actions" in analysis_data
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics._run_prediction_accuracy_analysis')
    def test_decay_analysis_partial_failures(self, mock_prediction, mock_auth, 
                                           client, auth_headers):
        """Test decay analysis when some components fail."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        mock_prediction.side_effect = Exception("Prediction analysis failed")
        
        response = client.get(
            "/api/time-bins/PARTIAL_FAIL_TEST/9/30/decay-analysis",
            headers=auth_headers,
            json={
                "prediction_accuracy": {
                    "prediction_period_days": 30
                }
            }
        )
        
        # Should still succeed overall with error noted
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Should have error in prediction accuracy component
        if "prediction_accuracy" in data["data"]:
            assert "error" in data["data"]["prediction_accuracy"]


class TestBackgroundProcessing:
    """Test background processing capabilities."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_get_background_process_results_not_found(self, mock_auth, client, auth_headers):
        """Test getting results for non-existent background process."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get(
            "/api/time-bins/TEST_ACCOUNT/9/30/walk-forward/results/nonexistent_process",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "Process not found" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_cancel_background_process_not_found(self, mock_auth, client, auth_headers):
        """Test cancelling non-existent background process."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.delete(
            "/api/time-bins/TEST_ACCOUNT/9/30/walk-forward/nonexistent_process",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "Process not found" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_get_active_processes_empty(self, mock_auth, client, auth_headers):
        """Test getting active processes when none exist."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        response = client.get(
            "/api/time-bins/walk-forward/active-processes",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"] == []  # No active processes


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""
    
    def test_endpoints_require_authentication(self, client):
        """Test that all endpoints require authentication."""
        
        endpoints_methods = [
            ("POST", "/api/time-bins/TEST/9/30/walk-forward"),
            ("GET", "/api/time-bins/TEST/9/30/walk-forward/results/proc_123"),
            ("GET", "/api/time-bins/TEST/9/30/robustness"),
            ("GET", "/api/time-bins/TEST/9/30/decay-analysis"),
            ("DELETE", "/api/time-bins/TEST/9/30/walk-forward/proc_123"),
            ("GET", "/api/time-bins/walk-forward/active-processes")
        ]
        
        for method, endpoint in endpoints_methods:
            if method == "POST":
                response = client.post(endpoint, json={"validation_method": "anchored_walk_forward"})
            elif method == "DELETE":
                response = client.delete(endpoint)
            else:
                response = client.get(endpoint)
            
            assert response.status_code in [401, 422]  # Unauthorized or validation error
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_parameter_validation(self, mock_auth, client, auth_headers):
        """Test parameter validation for all endpoints."""
        
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Test invalid hour
        response = client.post(
            "/api/time-bins/TEST/25/30/walk-forward",  # Hour 25 is invalid
            headers=auth_headers,
            json={"validation_method": "anchored_walk_forward"}
        )
        assert response.status_code == 422
        
        # Test invalid validation method
        response = client.post(
            "/api/time-bins/TEST/9/30/walk-forward",
            headers=auth_headers,
            json={"validation_method": "invalid_method"}
        )
        assert response.status_code == 422
        
        # Test invalid date format
        response = client.post(
            "/api/time-bins/TEST/9/30/walk-forward",
            headers=auth_headers,
            json={
                "validation_method": "anchored_walk_forward",
                "start_date": "invalid-date",
                "end_date": "2024-06-30"
            }
        )
        assert response.status_code == 422
        
        # Test invalid parameters for robustness endpoint
        response = client.get(
            "/api/time-bins/TEST/9/30/robustness",
            headers=auth_headers,
            params={"lookback_days": 500}  # Too many days
        )
        assert response.status_code == 422


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_out_of_sample_validator')
    @patch('trading_platform.api.routers.walk_forward_analytics.get_decay_tracker')
    @patch('trading_platform.api.routers.walk_forward_analytics._get_performance_history')
    def test_complete_analysis_workflow(self, mock_get_history, mock_tracker, 
                                      mock_validator, mock_auth, client, auth_headers,
                                      sample_validation_result, sample_degradation_result):
        """Test complete analysis workflow from validation to robustness to decay analysis."""
        
        mock_auth.return_value = {"user_id": "integration_user"}
        mock_get_history.return_value = ([Mock()], [Mock()])
        
        # Mock validator
        mock_validator_instance = Mock(spec=OutOfSampleValidator)
        mock_validator_instance.anchored_walk_forward.return_value = sample_validation_result
        mock_validator.return_value = mock_validator_instance
        
        # Mock tracker
        mock_tracker_instance = Mock(spec=PerformanceDecayTracker)
        mock_tracker_instance.detect_strategy_degradation.return_value = sample_degradation_result
        mock_tracker.return_value = mock_tracker_instance
        
        account = "INTEGRATION_TEST"
        hour = 9
        minute_bin = 30
        
        # 1. Run walk-forward validation
        validation_request = {
            "validation_method": "anchored_walk_forward",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "min_in_sample_days": 30,
            "out_of_sample_days": 10
        }
        
        validation_response = client.post(
            f"/api/time-bins/{account}/{hour}/{minute_bin}/walk-forward",
            headers=auth_headers,
            json=validation_request
        )
        
        assert validation_response.status_code == 200
        validation_data = validation_response.json()
        assert validation_data["status"] == "success"
        
        # 2. Check strategy robustness
        robustness_response = client.get(
            f"/api/time-bins/{account}/{hour}/{minute_bin}/robustness",
            headers=auth_headers,
            params={"lookback_days": 30, "baseline_days": 90}
        )
        
        assert robustness_response.status_code == 200
        robustness_data = robustness_response.json()
        assert robustness_data["status"] == "success"
        
        # 3. Run comprehensive decay analysis
        decay_response = client.get(
            f"/api/time-bins/{account}/{hour}/{minute_bin}/decay-analysis",
            headers=auth_headers,
            params={"include_persistence": True, "include_degradation": True}
        )
        
        assert decay_response.status_code == 200
        decay_data = decay_response.json()
        assert decay_data["status"] == "success"
        
        # Verify all analyses provide consistent account/time_bin information
        assert validation_data["data"]["account_name"] == account
        assert robustness_data["data"]["account_name"] == account
        assert decay_data["data"]["account_name"] == account
        
        assert validation_data["data"]["time_bin"] == f"{hour:02d}:{minute_bin:02d}"
        assert robustness_data["data"]["time_bin"] == f"{hour:02d}:{minute_bin:02d}"
        assert decay_data["data"]["time_bin"] == f"{hour:02d}:{minute_bin:02d}"
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    def test_cross_validation_integration(self, mock_auth, client, auth_headers):
        """Test cross-validation specific integration."""
        
        mock_auth.return_value = {"user_id": "cv_test_user"}
        
        cv_request = {
            "validation_method": "time_series_cv",
            "start_date": "2024-01-01",
            "end_date": "2024-04-30",
            "n_splits": 5,
            "test_size_ratio": 0.2,
            "gap_days": 2,
            "min_trades_threshold": 15,
            "confidence_level": 0.99
        }
        
        with patch('trading_platform.api.routers.walk_forward_analytics.get_out_of_sample_validator') as mock_validator:
            # Mock cross-validation result
            cv_result = Mock()
            cv_result.validation_method = ServiceValidationMethod.TIME_SERIES_CV
            cv_result.account_name = "CV_TEST"
            cv_result.time_bin = TimeBin.HOUR_14_MINUTE_0
            cv_result.period_performances = []
            cv_result.overall_metrics = {"cv_mean_sharpe": 1.15, "cv_std_sharpe": 0.25}
            cv_result.stability_analysis = {}
            cv_result.overfitting_analysis = {}
            cv_result.consistency_analysis = {}
            cv_result.recommendation = "CROSS_VALIDATION: Good consistency across folds"
            cv_result.generation_timestamp = datetime.now()
            cv_result.start_date = datetime(2024, 1, 1)
            cv_result.end_date = datetime(2024, 4, 30)
            
            mock_validator_instance = Mock(spec=OutOfSampleValidator)
            mock_validator_instance.time_series_cross_validation.return_value = cv_result
            mock_validator.return_value = mock_validator_instance
            
            response = client.post(
                "/api/time-bins/CV_TEST/14/0/walk-forward",
                headers=auth_headers,
                json=cv_request
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["validation_method"] == "time_series_cv"
            
            # Verify cross-validation was called with correct config
            mock_validator_instance.time_series_cross_validation.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])