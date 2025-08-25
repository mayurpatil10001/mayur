"""
Test suite for Monte Carlo Analytics API endpoints

Comprehensive testing of Monte Carlo simulation API endpoints including
parallel processing performance, API response accuracy, progress tracking,
and cancellation capabilities with real-world scenarios.

Requirements: 2.1, 2.6, 14.1
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from trading_platform.api.main import app
from trading_platform.services.monte_carlo.parallel_monte_carlo_engine import (
    ParallelMonteCarloEngine, SimulationStatus, SimulationType,
    SimulationProgress, MonteCarloSimulationResult
)
from trading_platform.services.monte_carlo.risk_metrics_calculator import (
    ComprehensiveRiskReport, VaRResult, ExpectedShortfallResult, 
    TailRiskMetrics, ProbabilityMetrics
)
from trading_platform.services.monte_carlo.time_bin_scenario_generator import (
    ScenarioSet, ScenarioType, ScenarioGenerationConfig
)


class TestMonteCarloAPI:
    """Test suite for Monte Carlo API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test_token"}
    
    @pytest.fixture
    def sample_simulation_request(self):
        """Create sample Monte Carlo simulation request."""
        return {
            "simulation_type": "comprehensive",
            "num_scenarios": 1000,
            "scenario_length": 30,
            "confidence_levels": [0.95, 0.99],
            "portfolio_value": 100000,
            "random_seed": 42,
            "parallel_processing": True,
            "max_workers": 2,
            "enable_progress_tracking": True
        }
    
    @pytest.fixture
    def sample_progress(self):
        """Create sample simulation progress."""
        return SimulationProgress(
            simulation_id="sim_test_123",
            status=SimulationStatus.RUNNING,
            current_step="Generating scenarios",
            steps_completed=2,
            total_steps=5,
            progress_percentage=40.0,
            start_time=datetime.now(),
            estimated_completion=datetime.now() + timedelta(minutes=5),
            elapsed_time=120.0,
            scenarios_generated=400,
            total_scenarios_target=1000,
            current_operation="Bootstrap resampling",
            worker_count=2,
            memory_usage_mb=256.5
        )
    
    @pytest.fixture
    def sample_risk_report(self):
        """Create sample comprehensive risk report."""
        # Create mock VaR results
        var_results = {
            "95.0%": VaRResult(
                confidence_level=0.95,
                var_absolute=-2500.0,
                var_percentage=-2.5,
                calculation_method="monte_carlo",
                sample_size=1000,
                calculation_timestamp=datetime.now(),
                percentile_rank=5.0
            )
        }
        
        # Create mock ES results
        es_results = {
            "95.0%": ExpectedShortfallResult(
                confidence_level=0.95,
                expected_shortfall=-3200.0,
                var_threshold=-2500.0,
                tail_scenarios_count=50,
                calculation_method="monte_carlo",
                sample_size=1000,
                calculation_timestamp=datetime.now()
            )
        }
        
        # Create mock tail metrics
        tail_metrics = TailRiskMetrics(
            extreme_value_model="empirical",
            model_parameters={},
            return_level_99_9=-5200.0,
            return_level_99_95=-6800.0,
            return_level_99_99=-9500.0,
            tail_index=None,
            model_fit_quality={},
            calculation_timestamp=datetime.now(),
            worst_historical_loss=-4200.0,
            tail_concentration=0.35
        )
        
        # Create mock probability metrics
        prob_metrics = ProbabilityMetrics(
            probability_of_profit=0.62,
            probability_of_loss=0.38,
            probability_large_loss={"loss_gt_1000": 0.15},
            probability_large_gain={"gain_gt_1000": 0.18},
            expected_positive_return=850.0,
            expected_negative_return=-620.0,
            gain_loss_ratio=1.37,
            kelly_criterion=0.08,
            calculation_timestamp=datetime.now()
        )
        
        return ComprehensiveRiskReport(
            var_results=var_results,
            expected_shortfall_results=es_results,
            tail_risk_metrics=tail_metrics,
            probability_metrics=prob_metrics,
            scenario_summary={
                'total_scenarios': 1000,
                'mean_return': 125.5,
                'std_return': 485.2,
                'skewness': -0.15,
                'kurtosis': 2.8,
                'min_scenario': -4200.0,
                'max_scenario': 3800.0,
                'median_scenario': 98.5
            },
            risk_decomposition={
                'worst_1_percent': -3200.0,
                'worst_5_percent': -2100.0,
                'worst_10_percent': -1650.0,
                'best_10_percent': 1950.0,
                'middle_80_percent': 145.0,
                'interquartile_range': 680.0,
                'range_ratio': 12.5
            },
            regime_risk_analysis=None,
            calculation_config={"confidence_levels": [0.95, 0.99]},
            generation_timestamp=datetime.now()
        )


class TestMonteCarloSimulation:
    """Test Monte Carlo simulation endpoints."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_run_monte_carlo_simulation_success(self, mock_engine, mock_auth, 
                                              client, auth_headers, sample_simulation_request,
                                              sample_risk_report):
        """Test successful Monte Carlo simulation."""
        # Mock authentication
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock engine
        mock_engine_instance = Mock(spec=ParallelMonteCarloEngine)
        
        # Create mock simulation result
        mock_scenario_set = Mock(spec=ScenarioSet)
        mock_scenario_set.scenarios.size = 1000
        
        mock_result = Mock(spec=MonteCarloSimulationResult)
        mock_result.simulation_id = "sim_test_123"
        mock_result.request.simulation_type = SimulationType.COMPREHENSIVE
        mock_result.scenario_set = mock_scenario_set
        mock_result.risk_report = sample_risk_report
        mock_result.performance_metrics = {"total_execution_time": 125.5}
        mock_result.generation_timestamp = datetime.now()
        mock_result.progress.status = SimulationStatus.COMPLETED
        mock_result.progress.simulation_id = "sim_test_123"
        mock_result.progress.current_step = "Completed"
        mock_result.progress.steps_completed = 5
        mock_result.progress.total_steps = 5
        mock_result.progress.progress_percentage = 100.0
        mock_result.progress.start_time = datetime.now()
        mock_result.progress.estimated_completion = None
        mock_result.progress.elapsed_time = 125.5
        mock_result.progress.scenarios_generated = 1000
        mock_result.progress.total_scenarios_target = 1000
        mock_result.progress.current_operation = "Complete"
        mock_result.progress.worker_count = 2
        mock_result.progress.memory_usage_mb = 256.5
        mock_result.progress.error_message = None
        
        # Mock async run_simulation
        async def mock_run_simulation(request):
            return mock_result
        
        mock_engine_instance.run_simulation = AsyncMock(side_effect=mock_run_simulation)
        mock_engine.return_value = mock_engine_instance
        
        # Make request
        response = client.post(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo",
            headers=auth_headers,
            json=sample_simulation_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "Monte Carlo simulation completed" in data["message"]
        
        # Verify response structure
        sim_data = data["data"]
        assert sim_data["simulation_id"] == "sim_test_123"
        assert sim_data["simulation_type"] == "comprehensive"
        assert sim_data["status"] == "completed"
        assert sim_data["account_name"] == "IPS_TM_10"
        assert sim_data["time_bin"] == "09:30"
        
        # Verify risk report is included
        assert "risk_report" in sim_data
        risk_report = sim_data["risk_report"]
        assert "var_results" in risk_report
        assert "expected_shortfall_results" in risk_report
        assert "tail_risk_metrics" in risk_report
        assert "probability_metrics" in risk_report
        
        # Verify engine was called correctly
        mock_engine_instance.run_simulation.assert_called_once()
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_run_simulation_with_different_types(self, mock_engine, mock_auth, 
                                                client, auth_headers, sample_risk_report):
        """Test simulation with different simulation types."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        simulation_types = ["bootstrap", "parametric", "regime_conditional", "comprehensive"]
        
        for sim_type in simulation_types:
            # Mock engine for each type
            mock_engine_instance = Mock(spec=ParallelMonteCarloEngine)
            
            mock_result = Mock()
            mock_result.simulation_id = f"sim_{sim_type}_123"
            mock_result.request.simulation_type = SimulationType.BOOTSTRAP  # Mock value
            mock_result.risk_report = sample_risk_report
            mock_result.performance_metrics = {}
            mock_result.generation_timestamp = datetime.now()
            
            # Mock progress
            mock_result.progress = Mock()
            mock_result.progress.status = SimulationStatus.COMPLETED
            mock_result.progress.simulation_id = f"sim_{sim_type}_123"
            mock_result.progress.current_step = "Complete"
            mock_result.progress.steps_completed = 3
            mock_result.progress.total_steps = 3
            mock_result.progress.progress_percentage = 100.0
            mock_result.progress.start_time = datetime.now()
            mock_result.progress.estimated_completion = None
            mock_result.progress.elapsed_time = 60.0
            mock_result.progress.scenarios_generated = 1000
            mock_result.progress.total_scenarios_target = 1000
            mock_result.progress.current_operation = "Complete"
            mock_result.progress.worker_count = 2
            mock_result.progress.memory_usage_mb = 128.0
            mock_result.progress.error_message = None
            
            mock_engine_instance.run_simulation = AsyncMock(return_value=mock_result)
            mock_engine.return_value = mock_engine_instance
            
            # Test request
            request_data = {
                "simulation_type": sim_type,
                "num_scenarios": 500,
                "scenario_length": 20,
                "portfolio_value": 50000
            }
            
            response = client.post(
                "/api/time-bins/TEST_ACCOUNT/14/0/monte-carlo",
                headers=auth_headers,
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_run_simulation_invalid_minute_bin(self, client, auth_headers, sample_simulation_request):
        """Test simulation with invalid minute bin."""
        with patch('trading_platform.api.dependencies.require_read_permission') as mock_auth:
            mock_auth.return_value = {"user_id": "test_user"}
            
            response = client.post(
                "/api/time-bins/IPS_TM_10/9/15/monte-carlo",  # Invalid minute bin
                headers=auth_headers,
                json=sample_simulation_request
            )
            
            assert response.status_code == 400
            assert "must be 0 or 30" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_run_simulation_server_capacity_error(self, mock_engine, mock_auth, 
                                                 client, auth_headers, sample_simulation_request):
        """Test simulation when server is at capacity."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.run_simulation = AsyncMock(
            side_effect=RuntimeError("Maximum concurrent simulations reached")
        )
        mock_engine.return_value = mock_engine_instance
        
        response = client.post(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo",
            headers=auth_headers,
            json=sample_simulation_request
        )
        
        assert response.status_code == 503
        assert "at capacity" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_run_simulation_validation_error(self, mock_engine, mock_auth, 
                                           client, auth_headers):
        """Test simulation with validation errors."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.run_simulation = AsyncMock(
            side_effect=ValueError("Insufficient historical data")
        )
        mock_engine.return_value = mock_engine_instance
        
        invalid_request = {
            "simulation_type": "bootstrap",
            "num_scenarios": 50,  # Too few scenarios
            "scenario_length": 10,
            "portfolio_value": 100000
        }
        
        response = client.post(
            "/api/time-bins/EMPTY_ACCOUNT/9/30/monte-carlo",
            headers=auth_headers,
            json=invalid_request
        )
        
        assert response.status_code == 400
        assert "Insufficient historical data" in response.json()["detail"]


class TestSimulationProgress:
    """Test simulation progress tracking endpoints."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_simulation_progress_success(self, mock_engine, mock_auth, 
                                           client, auth_headers, sample_progress):
        """Test successful progress retrieval."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.get_simulation_progress.return_value = sample_progress
        mock_engine.return_value = mock_engine_instance
        
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo/sim_test_123/progress",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "Progress retrieved" in data["message"]
        
        # Verify progress data
        progress_data = data["data"]
        assert progress_data["simulation_id"] == "sim_test_123"
        assert progress_data["status"] == "running"
        assert progress_data["progress_percentage"] == 40.0
        assert progress_data["scenarios_generated"] == 400
        assert progress_data["total_scenarios_target"] == 1000
        assert progress_data["worker_count"] == 2
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_simulation_progress_not_found(self, mock_engine, mock_auth, client, auth_headers):
        """Test progress retrieval for non-existent simulation."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.get_simulation_progress.return_value = None
        mock_engine.return_value = mock_engine_instance
        
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo/nonexistent_sim/progress",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_cancel_simulation_success(self, mock_engine, mock_auth, client, auth_headers):
        """Test successful simulation cancellation."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.cancel_simulation.return_value = True
        mock_engine.return_value = mock_engine_instance
        
        response = client.delete(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo/sim_test_123",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "cancelled successfully" in data["message"]
        assert data["data"]["cancelled"] is True
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_cancel_simulation_not_found(self, mock_engine, mock_auth, client, auth_headers):
        """Test cancellation of non-existent simulation."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.cancel_simulation.return_value = False
        mock_engine.return_value = mock_engine_instance
        
        response = client.delete(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo/nonexistent_sim",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found or already completed" in response.json()["detail"]


class TestRiskMetrics:
    """Test risk metrics endpoint."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_risk_metrics_success(self, mock_engine, mock_auth, 
                                    client, auth_headers, sample_risk_report):
        """Test successful risk metrics calculation."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock engine result
        mock_result = Mock()
        mock_result.risk_report = sample_risk_report
        
        mock_engine_instance = Mock()
        mock_engine_instance.run_simulation = AsyncMock(return_value=mock_result)
        mock_engine.return_value = mock_engine_instance
        
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/risk-metrics?num_scenarios=1000&simulation_type=bootstrap",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "Risk metrics calculated" in data["message"]
        
        # Verify risk metrics structure
        risk_data = data["data"]
        assert "var_results" in risk_data
        assert "expected_shortfall_results" in risk_data
        assert "tail_risk_metrics" in risk_data
        assert "probability_metrics" in risk_data
        assert "scenario_summary" in risk_data
        assert "risk_decomposition" in risk_data
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_risk_metrics_with_parameters(self, mock_engine, mock_auth, 
                                            client, auth_headers, sample_risk_report):
        """Test risk metrics with various parameters."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_result = Mock()
        mock_result.risk_report = sample_risk_report
        
        mock_engine_instance = Mock()
        mock_engine_instance.run_simulation = AsyncMock(return_value=mock_result)
        mock_engine.return_value = mock_engine_instance
        
        # Test with all parameters
        response = client.get(
            "/api/time-bins/IPS_TM_10/14/0/risk-metrics"
            "?num_scenarios=2000"
            "&simulation_type=parametric"
            "&portfolio_value=250000"
            "&confidence_levels=0.95&confidence_levels=0.99&confidence_levels=0.999"
            "&start_date=2024-01-01"
            "&end_date=2024-12-31",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify engine was called with correct configuration
        mock_engine_instance.run_simulation.assert_called_once()
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_risk_metrics_calculation_failure(self, mock_engine, mock_auth, client, auth_headers):
        """Test risk metrics when calculation fails."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_result = Mock()
        mock_result.risk_report = None  # Simulation failed to generate report
        
        mock_engine_instance = Mock()
        mock_engine_instance.run_simulation = AsyncMock(return_value=mock_result)
        mock_engine.return_value = mock_engine_instance
        
        response = client.get(
            "/api/time-bins/EMPTY_ACCOUNT/9/30/risk-metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 500
        assert "failed to generate results" in response.json()["detail"]


class TestEngineManagement:
    """Test engine management endpoints."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_active_simulations(self, mock_engine, mock_auth, 
                                  client, auth_headers, sample_progress):
        """Test getting active simulations."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock multiple active simulations
        active_sims = [
            sample_progress,
            SimulationProgress(
                simulation_id="sim_test_456",
                status=SimulationStatus.PENDING,
                current_step="Initializing",
                steps_completed=0,
                total_steps=5,
                progress_percentage=0.0,
                start_time=datetime.now(),
                estimated_completion=None,
                elapsed_time=5.0,
                scenarios_generated=0,
                total_scenarios_target=2000,
                current_operation="Preparing",
                worker_count=4,
                memory_usage_mb=128.0
            )
        ]
        
        mock_engine_instance = Mock()
        mock_engine_instance.get_active_simulations.return_value = active_sims
        mock_engine.return_value = mock_engine_instance
        
        response = client.get(
            "/api/time-bins/monte-carlo/active-simulations",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "Retrieved 2 active simulations" in data["message"]
        
        # Verify simulation data
        simulations = data["data"]
        assert len(simulations) == 2
        assert simulations[0]["simulation_id"] == "sim_test_123"
        assert simulations[1]["simulation_id"] == "sim_test_456"
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_get_engine_status(self, mock_engine, mock_auth, client, auth_headers):
        """Test engine status retrieval."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        engine_status = {
            "active_simulations": 2,
            "max_concurrent_simulations": 4,
            "current_simulation_count": 2,
            "available_slots": 2,
            "cpu_count": 8,
            "memory_usage_mb": 512.3,
            "active_simulation_ids": ["sim_123", "sim_456"]
        }
        
        mock_engine_instance = Mock()
        mock_engine_instance.get_engine_status.return_value = engine_status
        mock_engine.return_value = mock_engine_instance
        
        response = client.get(
            "/api/time-bins/monte-carlo/engine-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        
        # Verify engine status data
        status_data = data["data"]
        assert status_data["active_simulations"] == 2
        assert status_data["available_slots"] == 2
        assert status_data["cpu_count"] == 8
        assert len(status_data["active_simulation_ids"]) == 2
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_cleanup_completed_simulations(self, mock_engine, mock_auth, client, auth_headers):
        """Test cleanup of completed simulations."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        mock_engine_instance = Mock()
        mock_engine_instance.cleanup_completed_simulations.return_value = None
        mock_engine.return_value = mock_engine_instance
        
        response = client.delete(
            "/api/time-bins/monte-carlo/cleanup-completed?max_age_hours=12",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "12 hours" in data["message"]
        assert data["data"]["cleanup_completed"] is True
        
        # Verify cleanup was called
        mock_engine_instance.cleanup_completed_simulations.assert_called_once_with(12)


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_endpoints_require_authentication(self, client):
        """Test that all endpoints require authentication."""
        endpoints = [
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo",
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo/sim_123/progress",
            "/api/time-bins/IPS_TM_10/9/30/risk-metrics",
            "/api/time-bins/monte-carlo/active-simulations",
            "/api/time-bins/monte-carlo/engine-status"
        ]
        
        for endpoint in endpoints:
            if endpoint.endswith("monte-carlo"):
                response = client.post(endpoint, json={"simulation_type": "bootstrap"})
            elif "progress" in endpoint or "risk-metrics" in endpoint:
                response = client.get(endpoint)
            elif endpoint.endswith("sim_123"):
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
            "/api/time-bins/IPS_TM_10/25/30/monte-carlo",  # Hour 25 is invalid
            headers=auth_headers,
            json={"simulation_type": "bootstrap"}
        )
        assert response.status_code == 422
        
        # Test invalid request body
        response = client.post(
            "/api/time-bins/IPS_TM_10/9/30/monte-carlo",
            headers=auth_headers,
            json={"simulation_type": "invalid_type"}  # Invalid simulation type
        )
        assert response.status_code == 422
        
        # Test invalid num_scenarios in risk metrics
        response = client.get(
            "/api/time-bins/IPS_TM_10/9/30/risk-metrics?num_scenarios=50000",  # Too many
            headers=auth_headers
        )
        assert response.status_code == 422


class TestPerformanceAndConcurrency:
    """Test performance and concurrency scenarios."""
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    @pytest.mark.asyncio
    async def test_concurrent_simulation_requests(self, mock_engine, mock_auth, 
                                                 client, auth_headers):
        """Test handling of concurrent simulation requests."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock engine to simulate different response times
        mock_engine_instance = Mock()
        
        async def mock_run_simulation(request):
            # Simulate varying execution times
            await asyncio.sleep(0.1)  # Small delay to simulate work
            
            mock_result = Mock()
            mock_result.simulation_id = f"sim_{request.account_name}_{int(time.time())}"
            mock_result.request.simulation_type = request.simulation_type
            mock_result.risk_report = Mock()
            mock_result.performance_metrics = {}
            mock_result.generation_timestamp = datetime.now()
            mock_result.progress = Mock()
            mock_result.progress.status = SimulationStatus.COMPLETED
            mock_result.progress.simulation_id = mock_result.simulation_id
            mock_result.progress.current_step = "Complete"
            mock_result.progress.steps_completed = 3
            mock_result.progress.total_steps = 3
            mock_result.progress.progress_percentage = 100.0
            mock_result.progress.start_time = datetime.now()
            mock_result.progress.estimated_completion = None
            mock_result.progress.elapsed_time = 60.0
            mock_result.progress.scenarios_generated = 1000
            mock_result.progress.total_scenarios_target = 1000
            mock_result.progress.current_operation = "Complete"
            mock_result.progress.worker_count = 2
            mock_result.progress.memory_usage_mb = 128.0
            mock_result.progress.error_message = None
            
            return mock_result
        
        mock_engine_instance.run_simulation = AsyncMock(side_effect=mock_run_simulation)
        mock_engine.return_value = mock_engine_instance
        
        # Test multiple concurrent requests
        request_data = {
            "simulation_type": "bootstrap",
            "num_scenarios": 500,
            "scenario_length": 10
        }
        
        # Note: TestClient runs synchronously, but this tests the API's ability
        # to handle the requests properly even if they arrive concurrently
        responses = []
        for i in range(3):
            response = client.post(
                f"/api/time-bins/TEST_ACCOUNT_{i}/9/30/monte-carlo",
                headers=auth_headers,
                json=request_data
            )
            responses.append(response)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    @patch('trading_platform.api.dependencies.require_read_permission')
    @patch('trading_platform.api.routers.monte_carlo_analytics.get_monte_carlo_engine')
    def test_large_scenario_simulation(self, mock_engine, mock_auth, 
                                     client, auth_headers, sample_risk_report):
        """Test simulation with large number of scenarios."""
        mock_auth.return_value = {"user_id": "test_user"}
        
        # Mock engine for large simulation
        mock_result = Mock()
        mock_result.simulation_id = "sim_large_123"
        mock_result.request.simulation_type = SimulationType.COMPREHENSIVE
        mock_result.risk_report = sample_risk_report
        mock_result.performance_metrics = {
            "total_execution_time": 300.0,
            "parallel_efficiency": 0.85,
            "memory_peak_usage_mb": 2048.0
        }
        mock_result.generation_timestamp = datetime.now()
        mock_result.progress = Mock()
        mock_result.progress.status = SimulationStatus.COMPLETED
        mock_result.progress.simulation_id = "sim_large_123"
        mock_result.progress.current_step = "Complete"
        mock_result.progress.steps_completed = 6
        mock_result.progress.total_steps = 6
        mock_result.progress.progress_percentage = 100.0
        mock_result.progress.start_time = datetime.now() - timedelta(minutes=5)
        mock_result.progress.estimated_completion = None
        mock_result.progress.elapsed_time = 300.0
        mock_result.progress.scenarios_generated = 50000
        mock_result.progress.total_scenarios_target = 50000
        mock_result.progress.current_operation = "Complete"
        mock_result.progress.worker_count = 8
        mock_result.progress.memory_usage_mb = 2048.0
        mock_result.progress.error_message = None
        
        mock_engine_instance = Mock()
        mock_engine_instance.run_simulation = AsyncMock(return_value=mock_result)
        mock_engine.return_value = mock_engine_instance
        
        # Large simulation request
        large_request = {
            "simulation_type": "comprehensive",
            "num_scenarios": 50000,
            "scenario_length": 252,
            "portfolio_value": 1000000,
            "parallel_processing": True,
            "max_workers": 8
        }
        
        response = client.post(
            "/api/time-bins/LARGE_TEST/9/30/monte-carlo",
            headers=auth_headers,
            json=large_request
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        sim_data = data["data"]
        assert sim_data["progress"]["scenarios_generated"] == 50000
        assert sim_data["performance_metrics"]["memory_peak_usage_mb"] == 2048.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])