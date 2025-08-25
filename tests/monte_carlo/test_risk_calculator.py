"""
Test suite for RiskMetricsCalculator

Comprehensive testing of risk metrics calculation including Value at Risk (VaR),
Expected Shortfall (ES), tail risk metrics, and probability assessments with
validation against known portfolio distributions and analytical solutions.

Requirements: 2.2, 2.4, 2.5
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch
from scipy import stats

from trading_platform.services.monte_carlo.risk_metrics_calculator import (
    RiskMetricsCalculator, VaRResult, ExpectedShortfallResult, TailRiskMetrics,
    ProbabilityMetrics, ComprehensiveRiskReport, RiskMeasureType, TailRiskModel
)
from trading_platform.services.monte_carlo.time_bin_scenario_generator import (
    ScenarioSet, RegimeConditionalScenarios, ScenarioType, ScenarioGenerationConfig
)


class TestRiskMetricsCalculator:
    """Test suite for RiskMetricsCalculator class."""
    
    @pytest.fixture
    def risk_calculator(self):
        """Create RiskMetricsCalculator instance."""
        return RiskMetricsCalculator()
    
    @pytest.fixture
    def normal_scenarios(self):
        """Create normally distributed scenarios for testing."""
        np.random.seed(42)
        return np.random.normal(100, 500, 10000)  # Mean=100, Std=500
    
    @pytest.fixture
    def skewed_scenarios(self):
        """Create skewed distribution scenarios."""
        np.random.seed(42)
        return stats.skewnorm.rvs(a=-2, loc=50, scale=300, size=5000)  # Negatively skewed
    
    @pytest.fixture 
    def sample_scenario_set(self, normal_scenarios):
        """Create sample ScenarioSet for testing."""
        scenarios_2d = normal_scenarios.reshape(1000, 10)
        return ScenarioSet(
            scenarios=scenarios_2d,
            generation_method=ScenarioType.PARAMETRIC,
            distribution_fit=None,
            statistical_properties={},
            validation_results={},
            generation_config=Mock(),
            generation_timestamp=datetime.now()
        )


class TestValueAtRisk:
    """Test Value at Risk calculations."""
    
    def test_calculate_var_monte_carlo_method(self, risk_calculator, normal_scenarios):
        """Test VaR calculation using Monte Carlo method."""
        var_results = risk_calculator.calculate_var(
            normal_scenarios,
            confidence_levels=[0.95, 0.99],
            method=RiskMeasureType.MONTE_CARLO
        )
        
        # Verify results structure
        assert "95.0%" in var_results
        assert "99.0%" in var_results
        
        var_95 = var_results["95.0%"]
        var_99 = var_results["99.0%"]
        
        # Verify VaRResult properties
        assert isinstance(var_95, VaRResult)
        assert var_95.confidence_level == 0.95
        assert var_95.calculation_method == RiskMeasureType.MONTE_CARLO
        assert var_95.sample_size == len(normal_scenarios)
        
        # VaR should be negative (loss) and 99% VaR should be more extreme than 95%
        assert var_95.var_absolute < var_99.var_absolute  # More negative = more extreme
        
        # Test against known normal distribution properties
        # For normal distribution: VaR = μ - z*σ
        expected_var_95 = 100 - stats.norm.ppf(0.95) * 500
        expected_var_99 = 100 - stats.norm.ppf(0.99) * 500
        
        # Allow for some sampling error
        assert abs(var_95.var_absolute - expected_var_95) < 50
        assert abs(var_99.var_absolute - expected_var_99) < 100
    
    def test_calculate_var_parametric_method(self, risk_calculator, normal_scenarios):
        """Test parametric VaR calculation."""
        var_results = risk_calculator.calculate_var(
            normal_scenarios,
            confidence_levels=[0.95],
            method=RiskMeasureType.PARAMETRIC
        )
        
        var_95 = var_results["95.0%"]
        assert var_95.calculation_method == RiskMeasureType.PARAMETRIC
        
        # Parametric should be very close to theoretical for normal distribution
        expected_var = 100 - stats.norm.ppf(0.95) * 500
        assert abs(var_95.var_absolute - expected_var) < 10
    
    def test_calculate_var_historical_method(self, risk_calculator, normal_scenarios):
        """Test historical VaR calculation."""
        var_results = risk_calculator.calculate_var(
            normal_scenarios,
            method=RiskMeasureType.HISTORICAL
        )
        
        var_95 = var_results["95.0%"]
        assert var_95.calculation_method == RiskMeasureType.HISTORICAL
        assert var_95.worst_case_scenario is not None
        assert var_95.worst_case_scenario <= var_95.var_absolute  # Worst case should be more extreme
    
    def test_var_with_portfolio_value(self, risk_calculator, normal_scenarios):
        """Test VaR calculation with portfolio value for percentages."""
        portfolio_value = 1000000  # $1M portfolio
        var_results = risk_calculator.calculate_var(
            normal_scenarios,
            confidence_levels=[0.95],
            portfolio_value=portfolio_value
        )
        
        var_95 = var_results["95.0%"]
        expected_percentage = var_95.var_absolute / portfolio_value * 100
        assert abs(var_95.var_percentage - expected_percentage) < 0.001
    
    def test_var_insufficient_scenarios_error(self, risk_calculator):
        """Test error handling for insufficient scenarios."""
        small_scenarios = np.random.normal(0, 1, 50)  # Too few scenarios
        
        with pytest.raises(ValueError, match="Insufficient scenarios"):
            risk_calculator.calculate_var(
                small_scenarios,
                method=RiskMeasureType.PARAMETRIC  # Requires more scenarios
            )
    
    def test_var_with_non_finite_values(self, risk_calculator):
        """Test VaR calculation with non-finite values."""
        scenarios_with_nan = np.array([100, 200, np.nan, 150, np.inf, -100] * 200)
        
        # Should filter out non-finite values and continue
        var_results = risk_calculator.calculate_var(scenarios_with_nan)
        assert len(var_results) > 0
        assert all(np.isfinite(result.var_absolute) for result in var_results.values())


class TestExpectedShortfall:
    """Test Expected Shortfall calculations."""
    
    def test_calculate_expected_shortfall(self, risk_calculator, normal_scenarios):
        """Test Expected Shortfall calculation."""
        es_results = risk_calculator.calculate_expected_shortfall(
            normal_scenarios,
            confidence_levels=[0.95, 0.99]
        )
        
        # Verify results structure
        assert "95.0%" in es_results
        assert "99.0%" in es_results
        
        es_95 = es_results["95.0%"]
        es_99 = es_results["99.0%"]
        
        # Verify ExpectedShortfallResult properties
        assert isinstance(es_95, ExpectedShortfallResult)
        assert es_95.confidence_level == 0.95
        assert es_95.tail_scenarios_count > 0
        
        # ES should be more extreme than VaR
        assert es_95.expected_shortfall <= es_95.var_threshold
        assert es_99.expected_shortfall <= es_99.var_threshold
        
        # 99% ES should be more extreme than 95% ES
        assert es_99.expected_shortfall <= es_95.expected_shortfall
    
    def test_expected_shortfall_tail_scenarios(self, risk_calculator, normal_scenarios):
        """Test that tail scenarios are correctly identified."""
        es_results = risk_calculator.calculate_expected_shortfall(
            normal_scenarios,
            confidence_levels=[0.95]
        )
        
        es_95 = es_results["95.0%"]
        
        # Verify tail scenarios count matches expectation
        expected_tail_count = int(len(normal_scenarios) * 0.05)  # 5% tail
        assert abs(es_95.tail_scenarios_count - expected_tail_count) <= 1
        
        # If tail scenarios are included, verify they're all <= VaR threshold
        if es_95.tail_scenarios:
            assert all(scenario <= es_95.var_threshold for scenario in es_95.tail_scenarios)
    
    def test_expected_shortfall_coherence(self, risk_calculator, normal_scenarios):
        """Test that Expected Shortfall satisfies coherence properties."""
        es_results = risk_calculator.calculate_expected_shortfall(normal_scenarios)
        
        # Sub-additivity test (simplified): ES should be worse than mean of worst scenarios
        scenarios_flat = normal_scenarios.flatten()
        worst_5_pct = np.sort(scenarios_flat)[:len(scenarios_flat)//20]
        
        es_95 = es_results["95.0%"]
        assert es_95.expected_shortfall <= np.mean(worst_5_pct) + 50  # Allow for sampling variation


class TestTailRiskMetrics:
    """Test tail risk metrics calculations."""
    
    def test_calculate_tail_risk_gev_model(self, risk_calculator, normal_scenarios):
        """Test tail risk calculation using GEV model."""
        tail_metrics = risk_calculator.calculate_tail_risk_metrics(
            normal_scenarios,
            tail_model=TailRiskModel.GENERALIZED_EXTREME_VALUE
        )
        
        assert isinstance(tail_metrics, TailRiskMetrics)
        assert tail_metrics.extreme_value_model in [TailRiskModel.GENERALIZED_EXTREME_VALUE, 
                                                   TailRiskModel.EMPIRICAL]  # May fallback
        
        # Return levels should be increasingly extreme
        assert tail_metrics.return_level_99_9 <= tail_metrics.return_level_99_95
        assert tail_metrics.return_level_99_95 <= tail_metrics.return_level_99_99
        
        assert tail_metrics.worst_historical_loss is not None
        assert 0 <= tail_metrics.tail_concentration <= 1
    
    def test_calculate_tail_risk_pareto_model(self, risk_calculator):
        """Test tail risk calculation using Pareto model."""
        # Create scenarios with heavy tail
        np.random.seed(42)
        heavy_tail_scenarios = np.concatenate([
            np.random.normal(0, 100, 4000),  # Bulk of distribution
            np.random.pareto(1.5, 1000) * -1000  # Heavy negative tail
        ])
        
        tail_metrics = risk_calculator.calculate_tail_risk_metrics(
            heavy_tail_scenarios,
            tail_model=TailRiskModel.PARETO
        )
        
        assert tail_metrics.extreme_value_model in [TailRiskModel.PARETO, TailRiskModel.EMPIRICAL]
        assert tail_metrics.return_level_99_9 is not None
    
    def test_calculate_tail_risk_empirical_model(self, risk_calculator, normal_scenarios):
        """Test empirical tail risk calculation."""
        tail_metrics = risk_calculator.calculate_tail_risk_metrics(
            normal_scenarios,
            tail_model=TailRiskModel.EMPIRICAL
        )
        
        assert tail_metrics.extreme_value_model == TailRiskModel.EMPIRICAL
        
        # Return levels should match percentiles
        scenarios_flat = normal_scenarios.flatten()
        expected_99_9 = np.percentile(-scenarios_flat, 99.9)  # Convert to losses
        assert abs(tail_metrics.return_level_99_9 - expected_99_9) < 10
    
    def test_tail_risk_insufficient_data_fallback(self, risk_calculator):
        """Test fallback to empirical when insufficient data for model fitting."""
        small_scenarios = np.random.normal(0, 100, 50)  # Very small sample
        
        tail_metrics = risk_calculator.calculate_tail_risk_metrics(small_scenarios)
        
        # Should fallback to empirical approach
        assert tail_metrics.extreme_value_model == TailRiskModel.EMPIRICAL
        assert tail_metrics.return_level_99_9 is not None


class TestProbabilityMetrics:
    """Test probability-based risk metrics."""
    
    def test_calculate_probability_of_profit(self, risk_calculator):
        """Test probability metrics calculation."""
        # Create scenarios with known profit probability
        np.random.seed(42)
        # 70% positive, 30% negative
        positive_scenarios = np.random.uniform(50, 500, 700)
        negative_scenarios = np.random.uniform(-300, -50, 300)
        mixed_scenarios = np.concatenate([positive_scenarios, negative_scenarios])
        np.random.shuffle(mixed_scenarios)
        
        prob_metrics = risk_calculator.calculate_probability_of_profit(mixed_scenarios)
        
        assert isinstance(prob_metrics, ProbabilityMetrics)
        
        # Verify basic probabilities
        assert 0.65 <= prob_metrics.probability_of_profit <= 0.75  # Should be around 70%
        assert 0.25 <= prob_metrics.probability_of_loss <= 0.35    # Should be around 30%
        assert abs(prob_metrics.probability_of_profit + prob_metrics.probability_of_loss - 1.0) < 0.01
        
        # Expected returns should have correct signs
        assert prob_metrics.expected_positive_return > 0
        assert prob_metrics.expected_negative_return < 0
        
        # Gain/loss ratio should be reasonable
        assert prob_metrics.gain_loss_ratio > 0
    
    def test_probability_large_loss_thresholds(self, risk_calculator, normal_scenarios):
        """Test probability calculations for large loss thresholds."""
        prob_metrics = risk_calculator.calculate_probability_of_profit(normal_scenarios)
        
        # Verify threshold probabilities are decreasing (larger losses less likely)
        loss_probs = list(prob_metrics.probability_large_loss.values())
        for i in range(1, len(loss_probs)):
            assert loss_probs[i] <= loss_probs[i-1]  # Decreasing probability
        
        # Similar for gains
        gain_probs = list(prob_metrics.probability_large_gain.values())
        for i in range(1, len(gain_probs)):
            assert gain_probs[i] <= gain_probs[i-1]
    
    def test_kelly_criterion_calculation(self, risk_calculator):
        """Test Kelly Criterion calculation."""
        # Create favorable scenarios for Kelly calculation
        # 60% win rate, average win = 100, average loss = 50
        wins = np.random.uniform(50, 150, 600)
        losses = np.random.uniform(-75, -25, 400)
        kelly_scenarios = np.concatenate([wins, losses])
        
        prob_metrics = risk_calculator.calculate_probability_of_profit(kelly_scenarios)
        
        assert prob_metrics.kelly_criterion is not None
        assert -0.25 <= prob_metrics.kelly_criterion <= 0.25  # Reasonable bounds
    
    def test_probability_edge_cases(self, risk_calculator):
        """Test probability calculations with edge cases."""
        # All positive scenarios
        all_positive = np.random.uniform(10, 100, 1000)
        prob_metrics = risk_calculator.calculate_probability_of_profit(all_positive)
        
        assert prob_metrics.probability_of_profit == 1.0
        assert prob_metrics.probability_of_loss == 0.0
        assert prob_metrics.expected_negative_return == 0.0
        assert prob_metrics.gain_loss_ratio == float('inf')
        
        # All negative scenarios
        all_negative = np.random.uniform(-100, -10, 1000)
        prob_metrics = risk_calculator.calculate_probability_of_profit(all_negative)
        
        assert prob_metrics.probability_of_profit == 0.0
        assert prob_metrics.probability_of_loss == 1.0
        assert prob_metrics.expected_positive_return == 0.0


class TestComprehensiveRiskReport:
    """Test comprehensive risk report generation."""
    
    def test_generate_comprehensive_risk_report(self, risk_calculator, sample_scenario_set):
        """Test comprehensive risk report generation."""
        report = risk_calculator.generate_comprehensive_risk_report(
            sample_scenario_set,
            portfolio_value=500000
        )
        
        assert isinstance(report, ComprehensiveRiskReport)
        
        # Verify all components are present
        assert len(report.var_results) == 3  # Default confidence levels
        assert len(report.expected_shortfall_results) == 3
        assert isinstance(report.tail_risk_metrics, TailRiskMetrics)
        assert isinstance(report.probability_metrics, ProbabilityMetrics)
        assert isinstance(report.scenario_summary, dict)
        assert isinstance(report.risk_decomposition, dict)
        
        # Verify scenario summary
        summary = report.scenario_summary
        assert summary['total_scenarios'] > 0
        assert 'mean_return' in summary
        assert 'std_return' in summary
        assert 'skewness' in summary
        assert 'kurtosis' in summary
        
        # Verify risk decomposition
        decomp = report.risk_decomposition
        assert 'worst_1_percent' in decomp
        assert 'worst_5_percent' in decomp
        assert 'best_10_percent' in decomp
        assert decomp['worst_1_percent'] <= decomp['worst_5_percent']
    
    def test_comprehensive_report_with_regime_scenarios(self, risk_calculator, sample_scenario_set):
        """Test report generation with regime scenarios."""
        # Create mock regime scenarios
        regime_scenarios = Mock(spec=RegimeConditionalScenarios)
        regime_scenarios.low_regime_scenarios = sample_scenario_set
        regime_scenarios.medium_regime_scenarios = sample_scenario_set  
        regime_scenarios.high_regime_scenarios = sample_scenario_set
        regime_scenarios.regime_transition_probabilities = {'low_to_medium': 0.3}
        regime_scenarios.regime_persistence = {'low_avg_persistence_days': 15}
        
        report = risk_calculator.generate_comprehensive_risk_report(
            sample_scenario_set,
            regime_scenarios=regime_scenarios
        )
        
        assert report.regime_risk_analysis is not None
        assert 'low_volatility' in report.regime_risk_analysis
        assert 'cross_regime_analysis' in report.regime_risk_analysis
    
    def test_report_calculation_config(self, risk_calculator, sample_scenario_set):
        """Test that calculation configuration is properly recorded."""
        portfolio_value = 750000
        
        report = risk_calculator.generate_comprehensive_risk_report(
            sample_scenario_set,
            portfolio_value=portfolio_value
        )
        
        config = report.calculation_config
        assert config['portfolio_value'] == portfolio_value
        assert config['confidence_levels'] == risk_calculator.default_confidence_levels
        assert config['risk_free_rate'] == risk_calculator.risk_free_rate
        assert config['generation_method'] == sample_scenario_set.generation_method.value


class TestValidationAndErrorHandling:
    """Test validation and error handling."""
    
    def test_empty_scenarios_error(self, risk_calculator):
        """Test error handling for empty scenarios."""
        empty_scenarios = np.array([])
        
        with pytest.raises(ValueError, match="No scenarios provided"):
            risk_calculator.calculate_var(empty_scenarios)
        
        with pytest.raises(ValueError, match="No scenarios provided"):
            risk_calculator.calculate_expected_shortfall(empty_scenarios)
    
    def test_all_nan_scenarios_error(self, risk_calculator):
        """Test handling of all NaN scenarios."""
        nan_scenarios = np.full(1000, np.nan)
        
        with pytest.raises(ValueError):
            risk_calculator.calculate_var(nan_scenarios)
    
    def test_insufficient_scenarios_warning(self, risk_calculator):
        """Test warnings for insufficient scenarios."""
        small_scenarios = np.random.normal(0, 100, 50)
        
        # Should work with historical method (lower requirement)
        var_results = risk_calculator.calculate_var(
            small_scenarios, 
            method=RiskMeasureType.HISTORICAL
        )
        assert len(var_results) > 0
        
        # Should fail with parametric method (higher requirement)
        with pytest.raises(ValueError):
            risk_calculator.calculate_var(
                small_scenarios,
                method=RiskMeasureType.PARAMETRIC
            )
    
    def test_extreme_scenarios_handling(self, risk_calculator):
        """Test handling of extreme scenario values."""
        # Mix of normal values and extreme outliers
        extreme_scenarios = np.concatenate([
            np.random.normal(0, 100, 900),
            np.array([-1e6, 1e6])  # Extreme outliers
        ])
        
        # Should handle extreme values gracefully
        var_results = risk_calculator.calculate_var(extreme_scenarios)
        es_results = risk_calculator.calculate_expected_shortfall(extreme_scenarios)
        
        assert len(var_results) > 0
        assert len(es_results) > 0
        assert all(np.isfinite(result.var_absolute) for result in var_results.values())


class TestModelFittingAndStatistics:
    """Test statistical model fitting and validation."""
    
    def test_gev_model_fitting_quality(self, risk_calculator):
        """Test GEV model fitting with known distribution."""
        # Generate data from known GEV distribution
        np.random.seed(42)
        true_shape, true_loc, true_scale = -0.1, 100, 50
        gev_data = stats.genextreme.rvs(true_shape, loc=true_loc, scale=true_scale, size=5000)
        
        tail_metrics = risk_calculator.calculate_tail_risk_metrics(
            -gev_data,  # Convert to losses
            tail_model=TailRiskModel.GENERALIZED_EXTREME_VALUE
        )
        
        # If GEV fitting succeeded, parameters should be reasonably close
        if tail_metrics.extreme_value_model == TailRiskModel.GENERALIZED_EXTREME_VALUE:
            params = tail_metrics.model_parameters
            assert abs(params['shape'] - true_shape) < 0.2
            assert abs(params['location'] - true_loc) < 20
    
    def test_risk_decomposition_properties(self, risk_calculator, normal_scenarios):
        """Test properties of risk decomposition."""
        decomp = risk_calculator._calculate_risk_decomposition(normal_scenarios)
        
        # Worst percentages should be worse than best
        assert decomp['worst_1_percent'] <= decomp['worst_5_percent']
        assert decomp['worst_5_percent'] <= decomp['worst_10_percent']
        assert decomp['worst_10_percent'] <= decomp['middle_80_percent']
        assert decomp['middle_80_percent'] <= decomp['best_10_percent']
        
        # Interquartile range should be positive
        assert decomp['interquartile_range'] > 0
        assert decomp['range_ratio'] > 0


class TestIntegration:
    """Integration tests with real-world scenarios."""
    
    @pytest.fixture
    def realistic_trading_scenarios(self):
        """Create realistic trading scenarios."""
        np.random.seed(42)
        # Mix of winning and losing trades with realistic P&L distribution
        daily_returns = []
        
        # 55% win rate, skewed towards small wins and occasional large losses
        for _ in range(1000):
            if np.random.random() < 0.55:  # Win
                daily_returns.append(np.random.gamma(2, 50))  # Small to medium wins
            else:  # Loss
                if np.random.random() < 0.1:  # Occasional large loss
                    daily_returns.append(-np.random.gamma(3, 200))
                else:  # Regular small loss
                    daily_returns.append(-np.random.gamma(1.5, 30))
        
        return np.array(daily_returns)
    
    def test_realistic_trading_risk_analysis(self, risk_calculator, realistic_trading_scenarios):
        """Test comprehensive risk analysis with realistic trading data."""
        # Create scenario set
        scenarios_2d = realistic_trading_scenarios.reshape(100, 10)
        scenario_set = ScenarioSet(
            scenarios=scenarios_2d,
            generation_method=ScenarioType.BOOTSTRAP,
            distribution_fit=None,
            statistical_properties={},
            validation_results={},
            generation_config=Mock(),
            generation_timestamp=datetime.now()
        )
        
        # Generate comprehensive report
        report = risk_calculator.generate_comprehensive_risk_report(scenario_set)
        
        # Verify report makes sense for trading data
        assert report.probability_metrics.probability_of_profit > 0.5  # Should be > 50%
        assert report.probability_metrics.gain_loss_ratio > 0
        
        # VaR should be negative (representing losses)
        var_95 = report.var_results["95.0%"]
        assert var_95.var_absolute < 0
        
        # ES should be more extreme than VaR
        es_95 = report.expected_shortfall_results["95.0%"]
        assert es_95.expected_shortfall <= var_95.var_absolute
        
        # Tail concentration should be reasonable
        assert 0 < report.tail_risk_metrics.tail_concentration < 1
    
    def test_performance_with_large_scenarios(self, risk_calculator):
        """Test performance with large scenario sets."""
        # Generate large scenario set
        large_scenarios = np.random.normal(50, 200, 100000)
        
        # Should complete in reasonable time and use memory efficiently
        import time
        start_time = time.time()
        
        var_results = risk_calculator.calculate_var(large_scenarios)
        es_results = risk_calculator.calculate_expected_shortfall(large_scenarios)
        prob_metrics = risk_calculator.calculate_probability_of_profit(large_scenarios)
        
        end_time = time.time()
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert end_time - start_time < 10  # 10 seconds max
        assert len(var_results) == 3
        assert len(es_results) == 3
        assert isinstance(prob_metrics, ProbabilityMetrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])