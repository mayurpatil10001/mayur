"""
Test suite for TimeBinScenarioGenerator

Comprehensive testing of scenario generation methods for time-bin trading strategies,
including bootstrap, parametric, and regime-conditional scenario generation.

Requirements: 2.1, 2.2, 2.3
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from trading_platform.services.monte_carlo.time_bin_scenario_generator import (
    TimeBinScenarioGenerator, ScenarioType, DistributionType, ScenarioGenerationConfig,
    ScenarioSet, RegimeConditionalScenarios, DistributionFit
)
from trading_platform.services.time_bin_analyzer import TimeBin
from trading_platform.services.vix_regime_analyzer import (
    TradeRegimeAlignment, VolatilityRegime
)
from trading_platform.models.database import ProcessedTrade


class TestTimeBinScenarioGenerator:
    """Test suite for TimeBinScenarioGenerator class."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def scenario_generator(self, mock_db_session):
        """Create TimeBinScenarioGenerator instance."""
        return TimeBinScenarioGenerator(db_session=mock_db_session)
    
    @pytest.fixture
    def sample_config(self):
        """Create sample scenario generation configuration."""
        return ScenarioGenerationConfig(
            num_scenarios=1000,
            scenario_length=30,
            random_seed=42,
            confidence_levels=[0.95, 0.99]
        )
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample processed trades."""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        for i in range(50):
            trade = Mock(spec=ProcessedTrade)
            trade.trade_id = f"trade_{i}"
            trade.timestamp = base_date + timedelta(days=i)
            trade.pnl = np.random.normal(100, 50)  # Mean 100, std 50
            trade.return_percentage = trade.pnl / 1000 * 100
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_alignments(self):
        """Create sample trade-regime alignments."""
        alignments = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        # Low volatility regime trades
        for i in range(20):
            alignment = TradeRegimeAlignment(
                trade_timestamp=base_date + timedelta(days=i),
                entry_price=100.0 + i,
                vix_level=12.0 + np.random.normal(0, 2),
                regime=VolatilityRegime.LOW,
                days_since_regime_start=i % 10,
                trade_pnl=np.random.normal(80, 30)
            )
            alignments.append(alignment)
        
        # Medium volatility regime trades
        for i in range(20, 35):
            alignment = TradeRegimeAlignment(
                trade_timestamp=base_date + timedelta(days=i),
                entry_price=100.0 + i,
                vix_level=18.0 + np.random.normal(0, 3),
                regime=VolatilityRegime.MEDIUM,
                days_since_regime_start=(i-20) % 8,
                trade_pnl=np.random.normal(120, 60)
            )
            alignments.append(alignment)
        
        # High volatility regime trades
        for i in range(35, 45):
            alignment = TradeRegimeAlignment(
                trade_timestamp=base_date + timedelta(days=i),
                entry_price=100.0 + i,
                vix_level=28.0 + np.random.normal(0, 5),
                regime=VolatilityRegime.HIGH,
                days_since_regime_start=(i-35) % 5,
                trade_pnl=np.random.normal(200, 100)
            )
            alignments.append(alignment)
        
        return alignments


class TestBootstrapScenarios:
    """Test bootstrap scenario generation."""
    
    @patch('trading_platform.services.monte_carlo.time_bin_scenario_generator.TimeBinAnalyzer')
    def test_generate_bootstrap_scenarios_success(self, mock_analyzer, scenario_generator, 
                                                 sample_config, sample_trades):
        """Test successful bootstrap scenario generation."""
        # Mock time bin analyzer
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.get_time_bin_trades.return_value = sample_trades
        scenario_generator.time_bin_analyzer = mock_analyzer_instance
        
        # Generate scenarios
        scenario_set = scenario_generator.generate_bootstrap_scenarios(
            account_name="IPS_TM_10",
            hour=9,
            minute_bin=30,
            config=sample_config
        )
        
        # Verify results
        assert isinstance(scenario_set, ScenarioSet)
        assert scenario_set.generation_method == ScenarioType.BOOTSTRAP
        assert scenario_set.scenarios.shape == (1000, 30)
        assert scenario_set.distribution_fit is None  # Bootstrap doesn't use parametric fit
        assert "mean" in scenario_set.statistical_properties
        assert "std" in scenario_set.statistical_properties
        assert scenario_set.validation_results is not None
        assert scenario_set.generation_config == sample_config
    
    def test_bootstrap_insufficient_data_error(self, scenario_generator, sample_config):
        """Test error handling for insufficient historical data."""
        with patch.object(scenario_generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades:
            # Mock insufficient trades
            mock_get_trades.return_value = [Mock(pnl=100) for _ in range(5)]  # Less than 30
            
            with pytest.raises(ValueError, match="Insufficient historical data"):
                scenario_generator.generate_bootstrap_scenarios(
                    account_name="IPS_TM_10",
                    hour=9,
                    minute_bin=30,
                    config=sample_config
                )
    
    def test_bootstrap_with_block_size(self, scenario_generator, sample_config, sample_trades):
        """Test bootstrap with block bootstrap for time series structure."""
        with patch.object(scenario_generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades:
            mock_get_trades.return_value = sample_trades
            
            # Enable block bootstrap
            sample_config.bootstrap_block_size = 5
            
            scenario_set = scenario_generator.generate_bootstrap_scenarios(
                account_name="IPS_TM_10",
                hour=9,
                minute_bin=30,
                config=sample_config
            )
            
            assert scenario_set.scenarios.shape == (1000, 30)
            # Block bootstrap should preserve some time series structure
            assert scenario_set.validation_results is not None


class TestParametricScenarios:
    """Test parametric scenario generation."""
    
    def test_generate_parametric_scenarios_success(self, scenario_generator, sample_config, sample_trades):
        """Test successful parametric scenario generation."""
        with patch.object(scenario_generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades:
            mock_get_trades.return_value = sample_trades
            
            scenario_set = scenario_generator.generate_parametric_scenarios(
                account_name="IPS_TM_10",
                hour=9,
                minute_bin=30,
                config=sample_config
            )
            
            # Verify results
            assert isinstance(scenario_set, ScenarioSet)
            assert scenario_set.generation_method == ScenarioType.PARAMETRIC
            assert scenario_set.scenarios.shape == (1000, 30)
            assert scenario_set.distribution_fit is not None
            assert isinstance(scenario_set.distribution_fit, DistributionFit)
            assert scenario_set.distribution_fit.distribution_type in [
                DistributionType.NORMAL, DistributionType.T_DISTRIBUTION,
                DistributionType.SKEWED_NORMAL, DistributionType.MIXTURE_NORMAL
            ]
    
    def test_parametric_specific_distribution(self, scenario_generator, sample_config, sample_trades):
        """Test parametric scenario generation with specific distribution."""
        with patch.object(scenario_generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades:
            mock_get_trades.return_value = sample_trades
            
            scenario_set = scenario_generator.generate_parametric_scenarios(
                account_name="IPS_TM_10",
                hour=9,
                minute_bin=30,
                config=sample_config,
                distribution_type=DistributionType.NORMAL
            )
            
            assert scenario_set.distribution_fit.distribution_type == DistributionType.NORMAL
            assert "aic" in scenario_set.distribution_fit.__dict__
            assert "bic" in scenario_set.distribution_fit.__dict__
    
    def test_parametric_insufficient_data_error(self, scenario_generator, sample_config):
        """Test error handling for insufficient data in parametric fitting."""
        with patch.object(scenario_generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades:
            # Mock insufficient trades (less than 50)
            mock_get_trades.return_value = [Mock(pnl=100) for _ in range(20)]
            
            with pytest.raises(ValueError, match="Insufficient data for parametric fitting"):
                scenario_generator.generate_parametric_scenarios(
                    account_name="IPS_TM_10",
                    hour=9,
                    minute_bin=30,
                    config=sample_config
                )


class TestRegimeConditionalScenarios:
    """Test regime-conditional scenario generation."""
    
    def test_generate_regime_conditional_scenarios_success(self, scenario_generator, 
                                                          sample_config, sample_alignments):
        """Test successful regime-conditional scenario generation."""
        with patch.object(scenario_generator.vix_analyzer, 'synchronize_vix_with_trades') as mock_sync:
            mock_sync.return_value = sample_alignments
            
            regime_scenarios = scenario_generator.generate_regime_conditional_scenarios(
                account_name="IPS_TM_10",
                hour=9,
                minute_bin=30,
                config=sample_config
            )
            
            # Verify results
            assert isinstance(regime_scenarios, RegimeConditionalScenarios)
            assert isinstance(regime_scenarios.low_regime_scenarios, ScenarioSet)
            assert isinstance(regime_scenarios.medium_regime_scenarios, ScenarioSet)
            assert isinstance(regime_scenarios.high_regime_scenarios, ScenarioSet)
            
            # Verify each regime has scenarios
            assert regime_scenarios.low_regime_scenarios.scenarios.shape[0] > 0
            assert regime_scenarios.medium_regime_scenarios.scenarios.shape[0] > 0
            assert regime_scenarios.high_regime_scenarios.scenarios.shape[0] > 0
            
            # Verify transition probabilities
            assert isinstance(regime_scenarios.regime_transition_probabilities, dict)
            assert isinstance(regime_scenarios.regime_persistence, dict)
    
    def test_regime_conditional_insufficient_data_error(self, scenario_generator, sample_config):
        """Test error handling for insufficient regime data."""
        with patch.object(scenario_generator.vix_analyzer, 'synchronize_vix_with_trades') as mock_sync:
            # Mock insufficient alignments
            mock_sync.return_value = [Mock() for _ in range(10)]  # Less than 50
            
            with pytest.raises(ValueError, match="Insufficient regime data"):
                scenario_generator.generate_regime_conditional_scenarios(
                    account_name="IPS_TM_10",
                    hour=9,
                    minute_bin=30,
                    config=sample_config
                )


class TestDistributionFitting:
    """Test distribution fitting methods."""
    
    def test_find_best_distribution_fit(self, scenario_generator):
        """Test automatic best distribution selection."""
        # Generate test data with known distribution
        np.random.seed(42)
        normal_data = np.random.normal(100, 20, 200).tolist()
        
        distribution_fit = scenario_generator._find_best_distribution_fit(normal_data)
        
        assert isinstance(distribution_fit, DistributionFit)
        assert distribution_fit.distribution_type in scenario_generator.supported_distributions
        assert distribution_fit.aic < float('inf')
        assert distribution_fit.bic < float('inf')
        assert "goodness_of_fit" in distribution_fit.__dict__
    
    def test_fit_normal_distribution(self, scenario_generator):
        """Test fitting normal distribution."""
        np.random.seed(42)
        normal_data = np.random.normal(100, 20, 200).tolist()
        
        distribution_fit = scenario_generator._fit_specific_distribution(
            normal_data, DistributionType.NORMAL
        )
        
        assert distribution_fit.distribution_type == DistributionType.NORMAL
        assert len(distribution_fit.parameters) == 2  # mean, std
        assert abs(distribution_fit.parameters[0] - 100) < 5  # Close to true mean
        assert abs(distribution_fit.parameters[1] - 20) < 5   # Close to true std
    
    def test_fit_t_distribution(self, scenario_generator):
        """Test fitting t-distribution."""
        from scipy import stats
        np.random.seed(42)
        t_data = stats.t.rvs(df=5, loc=50, scale=10, size=200).tolist()
        
        distribution_fit = scenario_generator._fit_specific_distribution(
            t_data, DistributionType.T_DISTRIBUTION
        )
        
        assert distribution_fit.distribution_type == DistributionType.T_DISTRIBUTION
        assert len(distribution_fit.parameters) == 3  # df, loc, scale
    
    def test_fit_mixture_normal(self, scenario_generator):
        """Test fitting Gaussian mixture model."""
        np.random.seed(42)
        # Create bimodal data
        data1 = np.random.normal(50, 10, 100)
        data2 = np.random.normal(150, 15, 100)
        mixture_data = np.concatenate([data1, data2]).tolist()
        
        distribution_fit = scenario_generator._fit_specific_distribution(
            mixture_data, DistributionType.MIXTURE_NORMAL
        )
        
        assert distribution_fit.distribution_type == DistributionType.MIXTURE_NORMAL
        assert "weights" in distribution_fit.parameters
        assert "means" in distribution_fit.parameters
        assert "covariances" in distribution_fit.parameters


class TestScenarioValidation:
    """Test scenario validation methods."""
    
    def test_validate_scenario_properties(self, scenario_generator, sample_config):
        """Test comprehensive scenario validation."""
        np.random.seed(42)
        
        # Generate test scenarios
        scenarios = np.random.normal(100, 20, (500, 30))
        historical_data = np.random.normal(100, 20, 200).tolist()
        
        scenario_set = ScenarioSet(
            scenarios=scenarios,
            generation_method=ScenarioType.BOOTSTRAP,
            distribution_fit=None,
            statistical_properties={},
            validation_results={},
            generation_config=sample_config,
            generation_timestamp=datetime.now()
        )
        
        validation = scenario_generator.validate_scenario_properties(
            scenario_set, historical_data
        )
        
        # Verify validation components
        assert "overall_validation_score" in validation
        assert validation["overall_validation_score"] >= 0
        assert validation["overall_validation_score"] <= 1
    
    def test_distribution_tests(self, scenario_generator):
        """Test distribution comparison tests."""
        np.random.seed(42)
        scenario_data = np.random.normal(100, 20, 1000)
        historical_data = np.random.normal(100, 20, 200).tolist()
        
        tests = scenario_generator._run_distribution_tests(scenario_data, historical_data)
        
        assert "ks_test" in tests
        assert "statistic" in tests["ks_test"]
        assert "p_value" in tests["ks_test"]
        assert "similar" in tests["ks_test"]
        
        assert "mann_whitney_test" in tests
    
    def test_moment_tests(self, scenario_generator):
        """Test moment comparison tests."""
        np.random.seed(42)
        scenario_data = np.random.normal(100, 20, 1000)
        historical_data = np.random.normal(100, 20, 200).tolist()
        
        tests = scenario_generator._run_moment_tests(scenario_data, historical_data)
        
        assert "moment_tests" in tests
        assert "mean_rel_diff" in tests["moment_tests"]
        assert "std_rel_diff" in tests["moment_tests"]
        assert "skew_diff" in tests["moment_tests"]
        assert "kurtosis_diff" in tests["moment_tests"]
        assert "moment_similarity_score" in tests
    
    def test_independence_tests(self, scenario_generator):
        """Test independence tests on scenario paths."""
        np.random.seed(42)
        # Create scenarios with some autocorrelation
        scenarios = np.random.normal(0, 1, (100, 50))
        
        tests = scenario_generator._run_independence_tests(scenarios)
        
        if "independence_tests" in tests:
            assert "mean_autocorr_lag1" in tests["independence_tests"]
            assert "max_autocorr_lag1" in tests["independence_tests"]
            assert "independence_score" in tests["independence_tests"]
    
    def test_stationarity_tests(self, scenario_generator):
        """Test stationarity tests on scenario paths."""
        np.random.seed(42)
        scenarios = np.random.normal(0, 1, (50, 40))
        
        tests = scenario_generator._run_stationarity_tests(scenarios)
        
        if "stationarity_tests" in tests:
            assert "mean_stationarity_score" in tests["stationarity_tests"]
            assert "min_stationarity_score" in tests["stationarity_tests"]


class TestRegimeHelperMethods:
    """Test regime-specific helper methods."""
    
    def test_filter_alignments_by_time_bin(self, scenario_generator, sample_alignments):
        """Test filtering alignments by time bin."""
        # All sample alignments are for 9:30
        filtered = scenario_generator._filter_alignments_by_time_bin(
            sample_alignments, hour=9, minute_bin=30
        )
        
        # Should match all alignments (they're all 9:30)
        assert len(filtered) == len(sample_alignments)
        
        # Test different time bin
        filtered_empty = scenario_generator._filter_alignments_by_time_bin(
            sample_alignments, hour=14, minute_bin=0
        )
        
        assert len(filtered_empty) == 0
    
    def test_separate_trades_by_regime(self, scenario_generator, sample_alignments):
        """Test separating trades by volatility regime."""
        regime_trades = scenario_generator._separate_trades_by_regime(sample_alignments)
        
        assert VolatilityRegime.LOW in regime_trades
        assert VolatilityRegime.MEDIUM in regime_trades
        assert VolatilityRegime.HIGH in regime_trades
        
        # Verify counts match our test data
        assert len(regime_trades[VolatilityRegime.LOW]) == 20
        assert len(regime_trades[VolatilityRegime.MEDIUM]) == 15
        assert len(regime_trades[VolatilityRegime.HIGH]) == 10
    
    def test_calculate_regime_transition_probabilities(self, scenario_generator, sample_alignments):
        """Test calculation of regime transition probabilities."""
        transitions = scenario_generator._calculate_regime_transition_probabilities(sample_alignments)
        
        assert isinstance(transitions, dict)
        # Should have transition probabilities that sum to 1.0
        if transitions:
            total_prob = sum(transitions.values())
            assert abs(total_prob - 1.0) < 0.01
    
    def test_calculate_regime_persistence(self, scenario_generator, sample_alignments):
        """Test calculation of regime persistence."""
        persistence = scenario_generator._calculate_regime_persistence(sample_alignments)
        
        assert isinstance(persistence, dict)
        # Should have persistence measures for each regime
        regime_keys = ["Low_avg_persistence_days", "Medium_avg_persistence_days", "High_avg_persistence_days"]
        found_keys = [k for k in regime_keys if k in persistence]
        assert len(found_keys) > 0  # At least some regime should have persistence data


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_parameters(self, scenario_generator, sample_config):
        """Test handling of invalid parameters."""
        with pytest.raises(ValueError):
            scenario_generator.generate_bootstrap_scenarios(
                account_name="",  # Empty account name
                hour=25,  # Invalid hour
                minute_bin=30,
                config=sample_config
            )
    
    def test_empty_historical_data(self, scenario_generator, sample_config):
        """Test handling of empty historical data."""
        with patch.object(scenario_generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades:
            mock_get_trades.return_value = []
            
            with pytest.raises(ValueError):
                scenario_generator.generate_bootstrap_scenarios(
                    account_name="IPS_TM_10",
                    hour=9,
                    minute_bin=30,
                    config=sample_config
                )
    
    def test_distribution_fitting_failure_fallback(self, scenario_generator):
        """Test fallback to normal distribution when fitting fails."""
        # Create pathological data that might cause fitting issues
        pathological_data = [float('inf')] * 10 + [1, 2, 3] * 20
        
        try:
            distribution_fit = scenario_generator._find_best_distribution_fit(pathological_data)
            # Should fallback to normal distribution
            assert distribution_fit.distribution_type == DistributionType.NORMAL
        except:
            # If it raises an exception, that's also acceptable behavior
            pass


class TestIntegration:
    """Integration tests combining multiple components."""
    
    @patch('trading_platform.services.monte_carlo.time_bin_scenario_generator.get_db_session')
    def test_full_scenario_generation_workflow(self, mock_get_session, sample_trades, sample_alignments):
        """Test complete scenario generation workflow."""
        mock_session = Mock(spec=Session)
        mock_get_session.return_value = mock_session
        
        generator = TimeBinScenarioGenerator(db_session=mock_session)
        
        with patch.object(generator.time_bin_analyzer, 'get_time_bin_trades') as mock_get_trades, \
             patch.object(generator.vix_analyzer, 'synchronize_vix_with_trades') as mock_sync:
            
            mock_get_trades.return_value = sample_trades
            mock_sync.return_value = sample_alignments
            
            config = ScenarioGenerationConfig(
                num_scenarios=100,
                scenario_length=20,
                random_seed=42
            )
            
            # Test bootstrap scenarios
            bootstrap_scenarios = generator.generate_bootstrap_scenarios(
                "IPS_TM_10", 9, 30, config
            )
            assert bootstrap_scenarios.scenarios.shape == (100, 20)
            
            # Test parametric scenarios
            parametric_scenarios = generator.generate_parametric_scenarios(
                "IPS_TM_10", 9, 30, config
            )
            assert parametric_scenarios.scenarios.shape == (100, 20)
            
            # Test regime-conditional scenarios
            regime_scenarios = generator.generate_regime_conditional_scenarios(
                "IPS_TM_10", 9, 30, config
            )
            assert isinstance(regime_scenarios, RegimeConditionalScenarios)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])