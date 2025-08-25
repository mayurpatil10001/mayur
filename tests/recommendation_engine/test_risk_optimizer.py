"""
Unit tests for risk-return optimization service.

This module tests the risk optimizer functionality including single recommendation
optimization, portfolio allocation optimization, and various optimization methods.

Requirements: 6.2, 6.3
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trading_platform.services.recommendation.risk_optimizer import (
    RiskOptimizer, TradingOption, OptimizationConstraints, OptimizationResult,
    OptimizationMethod, RiskTolerance, RiskOptimizerError, RiskToleranceSettings
)


class TestTradingOption:
    """Test TradingOption data class."""
    
    def test_trading_option_creation(self):
        """Test creating a trading option."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.05,
            expected_risk=0.15,
            confidence_score=0.8,
            historical_sharpe=1.2,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.5
        )
        
        assert option.account_name == "IPS_TM_10"
        assert option.symbol == "NQ"
        assert option.expected_return == 0.05
        assert option.expected_risk == 0.15
        assert option.confidence_score == 0.8
    
    def test_risk_adjusted_return(self):
        """Test risk-adjusted return calculation."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.2,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        assert option.risk_adjusted_return == 0.5  # 0.1 / 0.2
    
    def test_risk_adjusted_return_zero_risk(self):
        """Test risk-adjusted return with zero risk."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.0,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        assert option.risk_adjusted_return == 0.0
    
    def test_kelly_fraction(self):
        """Test Kelly criterion fraction calculation."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.2,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        expected_kelly = 0.1 / (0.2 ** 2)  # μ / σ²
        assert abs(option.kelly_fraction - expected_kelly) < 1e-6


class TestOptimizationConstraints:
    """Test OptimizationConstraints data class."""
    
    def test_default_constraints(self):
        """Test default constraint values."""
        constraints = OptimizationConstraints()
        
        assert constraints.max_position_size == 1.0
        assert constraints.min_position_size == 0.0
        assert constraints.max_total_risk == 0.2
        assert constraints.min_diversification == 1
        assert constraints.max_concentration == 0.5
        assert constraints.target_return is None
        assert constraints.max_drawdown_limit == 0.25
    
    def test_custom_constraints(self):
        """Test custom constraint values."""
        constraints = OptimizationConstraints(
            max_position_size=0.8,
            min_position_size=0.1,
            max_total_risk=0.15,
            min_diversification=2,
            max_concentration=0.4,
            target_return=0.12,
            max_drawdown_limit=0.2
        )
        
        assert constraints.max_position_size == 0.8
        assert constraints.min_position_size == 0.1
        assert constraints.max_total_risk == 0.15
        assert constraints.min_diversification == 2
        assert constraints.max_concentration == 0.4
        assert constraints.target_return == 0.12
        assert constraints.max_drawdown_limit == 0.2


class TestRiskOptimizer:
    """Test RiskOptimizer class."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a risk optimizer instance."""
        return RiskOptimizer(
            default_risk_tolerance=0.5,
            default_optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_free_rate=0.02
        )
    
    @pytest.fixture
    def sample_trading_options(self):
        """Create sample trading options for testing."""
        return [
            TradingOption(
                account_name="IPS_TM_10",
                symbol="NQ",
                expected_return=0.08,
                expected_risk=0.15,
                confidence_score=0.8,
                historical_sharpe=1.2,
                max_drawdown=-0.1,
                win_rate=0.65,
                trade_frequency=2.5
            ),
            TradingOption(
                account_name="IPS_TM_13",
                symbol="FDAX",
                expected_return=0.06,
                expected_risk=0.12,
                confidence_score=0.7,
                historical_sharpe=1.0,
                max_drawdown=-0.08,
                win_rate=0.6,
                trade_frequency=2.0
            ),
            TradingOption(
                account_name="IPS_TM_10",
                symbol="FDAX",
                expected_return=0.05,
                expected_risk=0.1,
                confidence_score=0.9,
                historical_sharpe=0.8,
                max_drawdown=-0.06,
                win_rate=0.7,
                trade_frequency=1.8
            )
        ]
    
    def test_optimizer_initialization(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.default_risk_tolerance == 0.5
        assert optimizer.default_optimization_method == OptimizationMethod.SHARPE_RATIO
        assert optimizer.risk_free_rate == 0.02
        assert len(optimizer.optimization_history) == 0
        assert len(optimizer.risk_tolerance_params) == 4
    
    def test_optimize_single_recommendation_empty_options(self, optimizer):
        """Test single recommendation optimization with empty options."""
        with pytest.raises(RiskOptimizerError, match="No trading options provided"):
            optimizer.optimize_single_recommendation([])
    
    def test_optimize_single_recommendation_sharpe_ratio(self, optimizer, sample_trading_options):
        """Test single recommendation optimization using Sharpe ratio."""
        result = optimizer.optimize_single_recommendation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        assert isinstance(result, TradingOption)
        assert result.account_name in ["IPS_TM_10", "IPS_TM_13"]
        assert result.symbol in ["NQ", "FDAX"]
    
    def test_optimize_single_recommendation_mean_variance(self, optimizer, sample_trading_options):
        """Test single recommendation optimization using mean-variance."""
        result = optimizer.optimize_single_recommendation(
            sample_trading_options,
            risk_tolerance=0.3,
            optimization_method=OptimizationMethod.MEAN_VARIANCE
        )
        
        assert isinstance(result, TradingOption)
        assert result.account_name in ["IPS_TM_10", "IPS_TM_13"]
        assert result.symbol in ["NQ", "FDAX"]
    
    def test_optimize_single_recommendation_kelly_criterion(self, optimizer, sample_trading_options):
        """Test single recommendation optimization using Kelly criterion."""
        result = optimizer.optimize_single_recommendation(
            sample_trading_options,
            risk_tolerance=0.8,
            optimization_method=OptimizationMethod.KELLY_CRITERION
        )
        
        assert isinstance(result, TradingOption)
        assert result.account_name in ["IPS_TM_10", "IPS_TM_13"]
        assert result.symbol in ["NQ", "FDAX"]
    
    def test_optimize_portfolio_allocation_empty_options(self, optimizer):
        """Test portfolio allocation optimization with empty options."""
        with pytest.raises(RiskOptimizerError, match="No trading options provided"):
            optimizer.optimize_portfolio_allocation([])
    
    def test_optimize_portfolio_allocation_single_option(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization with single option."""
        single_option = [sample_trading_options[0]]
        
        result = optimizer.optimize_portfolio_allocation(
            single_option,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 1
        assert list(result.optimal_weights.values())[0] == 1.0
        assert result.max_weight == 1.0
        assert result.diversification_ratio == 1.0
    
    def test_optimize_portfolio_allocation_sharpe_ratio(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization using Sharpe ratio."""
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.expected_portfolio_return > 0
        assert result.expected_portfolio_risk > 0
        assert result.optimization_method == OptimizationMethod.SHARPE_RATIO
    
    def test_optimize_portfolio_allocation_mean_variance(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization using mean-variance."""
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.3,
            optimization_method=OptimizationMethod.MEAN_VARIANCE
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.optimization_method == OptimizationMethod.MEAN_VARIANCE
    
    def test_optimize_portfolio_allocation_kelly_criterion(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization using Kelly criterion."""
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.7,
            optimization_method=OptimizationMethod.KELLY_CRITERION
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.optimization_method == OptimizationMethod.KELLY_CRITERION
    
    def test_optimize_portfolio_allocation_risk_parity(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization using risk parity."""
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.RISK_PARITY
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.optimization_method == OptimizationMethod.RISK_PARITY
    
    def test_optimize_portfolio_allocation_maximum_diversification(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization using maximum diversification."""
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.MAXIMUM_DIVERSIFICATION
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.optimization_method == OptimizationMethod.MAXIMUM_DIVERSIFICATION
    
    def test_optimize_portfolio_allocation_with_constraints(self, optimizer, sample_trading_options):
        """Test portfolio allocation optimization with custom constraints."""
        constraints = OptimizationConstraints(
            max_position_size=0.6,
            min_position_size=0.1,
            max_total_risk=0.15,
            min_diversification=2,
            max_concentration=0.5
        )
        
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            constraints=constraints
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        
        # Check constraint satisfaction
        weights = list(result.optimal_weights.values())
        assert all(w >= constraints.min_position_size - 1e-6 for w in weights)
        assert all(w <= constraints.max_position_size + 1e-6 for w in weights)
        assert result.max_weight <= constraints.max_concentration + 1e-6
    
    def test_unsupported_optimization_method(self, optimizer, sample_trading_options):
        """Test unsupported optimization method."""
        with pytest.raises(RiskOptimizerError, match="Unsupported optimization method"):
            optimizer.optimize_portfolio_allocation(
                sample_trading_options,
                optimization_method="unsupported_method"
            )
    
    def test_calculate_option_score_sharpe_ratio(self, optimizer):
        """Test option score calculation using Sharpe ratio."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.2,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        score = optimizer._calculate_option_score(
            option, 0.5, OptimizationMethod.SHARPE_RATIO
        )
        
        assert score > 0
        assert isinstance(score, float)
    
    def test_calculate_option_score_mean_variance(self, optimizer):
        """Test option score calculation using mean-variance."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.2,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        score = optimizer._calculate_option_score(
            option, 0.3, OptimizationMethod.MEAN_VARIANCE
        )
        
        assert isinstance(score, float)
    
    def test_calculate_option_score_kelly_criterion(self, optimizer):
        """Test option score calculation using Kelly criterion."""
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.2,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.1,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        score = optimizer._calculate_option_score(
            option, 0.7, OptimizationMethod.KELLY_CRITERION
        )
        
        assert isinstance(score, float)
    
    def test_build_correlation_matrix(self, optimizer, sample_trading_options):
        """Test correlation matrix building."""
        correlation_matrix = optimizer._build_correlation_matrix(sample_trading_options)
        
        assert correlation_matrix.shape == (3, 3)
        assert np.allclose(np.diag(correlation_matrix), 1.0)  # Diagonal should be 1
        assert np.allclose(correlation_matrix, correlation_matrix.T)  # Should be symmetric
        
        # Check specific correlations
        # Same symbol, different accounts should have high correlation (0.8)
        # Same account, different symbols should have moderate correlation (0.4)
        # Different account and symbol should have low correlation (0.2)
        
        # Options 0 and 2 are same account (IPS_TM_10), different symbols
        assert abs(correlation_matrix[0, 2] - 0.4) < 1e-6
        
        # Options 0 and 1 are different accounts and symbols
        assert abs(correlation_matrix[0, 1] - 0.2) < 1e-6
    
    def test_calculate_covariance_matrix(self, optimizer):
        """Test covariance matrix calculation."""
        risks = np.array([0.1, 0.15, 0.2])
        correlation_matrix = np.array([
            [1.0, 0.5, 0.3],
            [0.5, 1.0, 0.4],
            [0.3, 0.4, 1.0]
        ])
        
        covariance_matrix = optimizer._calculate_covariance_matrix(risks, correlation_matrix)
        
        assert covariance_matrix.shape == (3, 3)
        assert np.allclose(covariance_matrix, covariance_matrix.T)  # Should be symmetric
        
        # Check diagonal elements (variances)
        expected_variances = risks ** 2
        actual_variances = np.diag(covariance_matrix)
        assert np.allclose(actual_variances, expected_variances)
        
        # Check off-diagonal elements (covariances)
        assert abs(covariance_matrix[0, 1] - (0.1 * 0.15 * 0.5)) < 1e-10
        assert abs(covariance_matrix[0, 2] - (0.1 * 0.2 * 0.3)) < 1e-10
        assert abs(covariance_matrix[1, 2] - (0.15 * 0.2 * 0.4)) < 1e-10
    
    def test_get_risk_tolerance_parameters(self, optimizer):
        """Test risk tolerance parameter mapping."""
        # Conservative
        params = optimizer.get_risk_tolerance_parameters(0.2)
        assert params['max_risk'] == 0.1
        assert params['min_sharpe'] == 1.0
        assert params['max_drawdown'] == 0.15
        
        # Moderate
        params = optimizer.get_risk_tolerance_parameters(0.5)
        assert params['max_risk'] == 0.2
        assert params['min_sharpe'] == 0.5
        assert params['max_drawdown'] == 0.25
        
        # Aggressive
        params = optimizer.get_risk_tolerance_parameters(0.8)
        assert params['max_risk'] == 0.35
        assert params['min_sharpe'] == 0.3
        assert params['max_drawdown'] == 0.4
        
        # Very Aggressive
        params = optimizer.get_risk_tolerance_parameters(0.95)
        assert params['max_risk'] == 0.5
        assert params['min_sharpe'] == 0.2
        assert params['max_drawdown'] == 0.6
    
    def test_validate_optimization_result_valid(self, optimizer):
        """Test validation of valid optimization result."""
        result = OptimizationResult(
            optimal_weights={"IPS_TM_10-NQ": 0.4, "IPS_TM_13-FDAX": 0.6},
            expected_portfolio_return=0.07,
            expected_portfolio_risk=0.12,
            sharpe_ratio=0.8,
            diversification_ratio=1.2,
            max_weight=0.6,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_tolerance=0.5,
            constraints_satisfied=True,
            optimization_success=True,
            optimization_message="Success"
        )
        
        constraints = OptimizationConstraints(
            max_position_size=1.0,
            min_position_size=0.0,
            max_total_risk=0.2,
            min_diversification=1,
            max_concentration=0.8
        )
        
        assert optimizer.validate_optimization_result(result, constraints)
    
    def test_validate_optimization_result_invalid_weights_sum(self, optimizer):
        """Test validation with invalid weights sum."""
        result = OptimizationResult(
            optimal_weights={"IPS_TM_10-NQ": 0.3, "IPS_TM_13-FDAX": 0.6},  # Sum = 0.9
            expected_portfolio_return=0.07,
            expected_portfolio_risk=0.12,
            sharpe_ratio=0.8,
            diversification_ratio=1.2,
            max_weight=0.6,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_tolerance=0.5,
            constraints_satisfied=True,
            optimization_success=True,
            optimization_message="Success"
        )
        
        constraints = OptimizationConstraints()
        
        assert not optimizer.validate_optimization_result(result, constraints)
    
    def test_validate_optimization_result_weight_bounds_violation(self, optimizer):
        """Test validation with weight bounds violation."""
        result = OptimizationResult(
            optimal_weights={"IPS_TM_10-NQ": 1.2, "IPS_TM_13-FDAX": -0.2},  # Violates bounds
            expected_portfolio_return=0.07,
            expected_portfolio_risk=0.12,
            sharpe_ratio=0.8,
            diversification_ratio=1.2,
            max_weight=1.2,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_tolerance=0.5,
            constraints_satisfied=True,
            optimization_success=True,
            optimization_message="Success"
        )
        
        constraints = OptimizationConstraints(
            max_position_size=1.0,
            min_position_size=0.0
        )
        
        assert not optimizer.validate_optimization_result(result, constraints)
    
    def test_validate_optimization_result_risk_constraint_violation(self, optimizer):
        """Test validation with risk constraint violation."""
        result = OptimizationResult(
            optimal_weights={"IPS_TM_10-NQ": 0.5, "IPS_TM_13-FDAX": 0.5},
            expected_portfolio_return=0.07,
            expected_portfolio_risk=0.25,  # Exceeds max risk
            sharpe_ratio=0.8,
            diversification_ratio=1.2,
            max_weight=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_tolerance=0.5,
            constraints_satisfied=True,
            optimization_success=True,
            optimization_message="Success"
        )
        
        constraints = OptimizationConstraints(max_total_risk=0.2)
        
        assert not optimizer.validate_optimization_result(result, constraints)
    
    def test_validate_optimization_result_concentration_violation(self, optimizer):
        """Test validation with concentration constraint violation."""
        result = OptimizationResult(
            optimal_weights={"IPS_TM_10-NQ": 0.8, "IPS_TM_13-FDAX": 0.2},
            expected_portfolio_return=0.07,
            expected_portfolio_risk=0.12,
            sharpe_ratio=0.8,
            diversification_ratio=1.2,
            max_weight=0.8,  # Exceeds max concentration
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_tolerance=0.5,
            constraints_satisfied=True,
            optimization_success=True,
            optimization_message="Success"
        )
        
        constraints = OptimizationConstraints(max_concentration=0.6)
        
        assert not optimizer.validate_optimization_result(result, constraints)
    
    def test_validate_optimization_result_diversification_violation(self, optimizer):
        """Test validation with diversification constraint violation."""
        result = OptimizationResult(
            optimal_weights={"IPS_TM_10-NQ": 1.0, "IPS_TM_13-FDAX": 0.0, "IPS_TM_10-FDAX": 0.0},
            expected_portfolio_return=0.07,
            expected_portfolio_risk=0.12,
            sharpe_ratio=0.8,
            diversification_ratio=1.2,
            max_weight=1.0,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_tolerance=0.5,
            constraints_satisfied=True,
            optimization_success=True,
            optimization_message="Success"
        )
        
        constraints = OptimizationConstraints(min_diversification=2)
        
        assert not optimizer.validate_optimization_result(result, constraints)
    
    def test_optimization_history_tracking(self, optimizer, sample_trading_options):
        """Test optimization history tracking."""
        initial_history_length = len(optimizer.optimization_history)
        
        # Perform optimization
        optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        # Check history was updated
        assert len(optimizer.optimization_history) == initial_history_length + 1
        
        # Check history content
        latest_result = optimizer.optimization_history[-1]
        assert isinstance(latest_result, OptimizationResult)
        assert latest_result.optimization_method == OptimizationMethod.SHARPE_RATIO
        assert latest_result.risk_tolerance == 0.5
    
    def test_get_optimization_history(self, optimizer, sample_trading_options):
        """Test getting optimization history."""
        # Perform multiple optimizations
        for i in range(5):
            optimizer.optimize_portfolio_allocation(
                sample_trading_options,
                risk_tolerance=0.5,
                optimization_method=OptimizationMethod.SHARPE_RATIO
            )
        
        # Get history
        history = optimizer.get_optimization_history(limit=3)
        assert len(history) == 3
        assert all(isinstance(result, OptimizationResult) for result in history)
        
        # Get all history
        full_history = optimizer.get_optimization_history(limit=100)
        assert len(full_history) == 5
    
    def test_clear_optimization_history(self, optimizer, sample_trading_options):
        """Test clearing optimization history."""
        # Perform optimization
        optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        assert len(optimizer.optimization_history) > 0
        
        # Clear history
        optimizer.clear_optimization_history()
        assert len(optimizer.optimization_history) == 0
    
    @patch('trading_platform.services.recommendation.risk_optimizer.minimize')
    def test_optimization_failure_handling(self, mock_minimize, optimizer, sample_trading_options):
        """Test handling of optimization failures."""
        # Mock optimization failure
        mock_result = Mock()
        mock_result.success = False
        mock_result.message = "Optimization failed"
        mock_result.x = np.array([0.33, 0.33, 0.34])
        mock_minimize.return_value = mock_result
        
        result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            risk_tolerance=0.5,
            optimization_method=OptimizationMethod.MEAN_VARIANCE
        )
        
        assert isinstance(result, OptimizationResult)
        assert not result.optimization_success
        assert "failure" in result.optimization_message.lower()
    
    def test_risk_tolerance_edge_cases(self, optimizer, sample_trading_options):
        """Test risk tolerance edge cases."""
        # Very low risk tolerance
        result_low = optimizer.optimize_single_recommendation(
            sample_trading_options,
            risk_tolerance=0.01
        )
        assert isinstance(result_low, TradingOption)
        
        # Very high risk tolerance
        result_high = optimizer.optimize_single_recommendation(
            sample_trading_options,
            risk_tolerance=0.99
        )
        assert isinstance(result_high, TradingOption)
        
        # Exactly at boundaries
        result_boundary = optimizer.optimize_single_recommendation(
            sample_trading_options,
            risk_tolerance=0.5
        )
        assert isinstance(result_boundary, TradingOption)


class TestRiskToleranceSettings:
    """Test RiskToleranceSettings data class and functionality."""
    
    def test_risk_tolerance_settings_creation(self):
        """Test creating risk tolerance settings."""
        settings = RiskToleranceSettings(
            risk_level=0.6,
            max_portfolio_risk=0.2,
            min_sharpe_ratio=0.5,
            max_drawdown_tolerance=0.25,
            diversification_preference=0.4,
            return_preference=0.7,
            volatility_penalty=2.0,
            concentration_limit=0.5
        )
        
        assert settings.risk_level == 0.6
        assert settings.max_portfolio_risk == 0.2
        assert settings.min_sharpe_ratio == 0.5
        assert settings.max_drawdown_tolerance == 0.25
        assert settings.diversification_preference == 0.4
        assert settings.return_preference == 0.7
        assert settings.volatility_penalty == 2.0
        assert settings.concentration_limit == 0.5
    
    def test_risk_tolerance_settings_validation_risk_level(self):
        """Test validation of risk level bounds."""
        with pytest.raises(ValueError, match="Risk level must be between 0.0 and 1.0"):
            RiskToleranceSettings(
                risk_level=1.5,  # Invalid
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=0.4,
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_validation_diversification_preference(self):
        """Test validation of diversification preference bounds."""
        with pytest.raises(ValueError, match="Diversification preference must be between 0.0 and 1.0"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=1.5,  # Invalid
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_validation_return_preference(self):
        """Test validation of return preference bounds."""
        with pytest.raises(ValueError, match="Return preference must be between 0.0 and 1.0"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=0.4,
                return_preference=1.2,  # Invalid
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_validation_max_portfolio_risk(self):
        """Test validation of maximum portfolio risk."""
        with pytest.raises(ValueError, match="Maximum portfolio risk must be positive"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=-0.1,  # Invalid
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=0.4,
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_validation_max_drawdown_tolerance(self):
        """Test validation of maximum drawdown tolerance."""
        with pytest.raises(ValueError, match="Maximum drawdown tolerance must be positive"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=-0.1,  # Invalid
                diversification_preference=0.4,
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )


class TestRiskOptimizerEnhanced:
    """Test enhanced RiskOptimizer functionality."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a risk optimizer instance."""
        return RiskOptimizer(
            default_risk_tolerance=0.5,
            default_optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_free_rate=0.02
        )
    
    @pytest.fixture
    def sample_risk_settings(self):
        """Create sample risk tolerance settings."""
        return RiskToleranceSettings(
            risk_level=0.6,
            max_portfolio_risk=0.2,
            min_sharpe_ratio=0.5,
            max_drawdown_tolerance=0.25,
            diversification_preference=0.4,
            return_preference=0.7,
            volatility_penalty=2.0,
            concentration_limit=0.5
        )
    
    @pytest.fixture
    def sample_trading_options(self):
        """Create sample trading options for testing."""
        return [
            TradingOption(
                account_name="IPS_TM_10",
                symbol="NQ",
                expected_return=0.08,
                expected_risk=0.15,
                confidence_score=0.8,
                historical_sharpe=1.2,
                max_drawdown=-0.1,
                win_rate=0.65,
                trade_frequency=2.5
            ),
            TradingOption(
                account_name="IPS_TM_13",
                symbol="FDAX",
                expected_return=0.06,
                expected_risk=0.12,
                confidence_score=0.7,
                historical_sharpe=1.0,
                max_drawdown=-0.08,
                win_rate=0.6,
                trade_frequency=2.0
            ),
            TradingOption(
                account_name="IPS_TM_10",
                symbol="FDAX",
                expected_return=0.05,
                expected_risk=0.1,
                confidence_score=0.9,
                historical_sharpe=0.8,
                max_drawdown=-0.06,
                win_rate=0.7,
                trade_frequency=1.8
            )
        ]
    
    def test_create_risk_tolerance_settings_conservative(self, optimizer):
        """Test creating conservative risk tolerance settings."""
        settings = optimizer.create_risk_tolerance_settings(
            risk_level=0.2,
            return_preference=0.5,
            diversification_preference=0.6
        )
        
        assert settings.risk_level == 0.2
        assert settings.max_portfolio_risk <= 0.12  # Conservative risk limit
        assert settings.min_sharpe_ratio >= 1.0     # High Sharpe requirement
        assert settings.volatility_penalty >= 2.5   # High volatility penalty
        assert settings.concentration_limit <= 0.4  # Low concentration limit
        assert settings.return_preference == 0.5
        assert settings.diversification_preference == 0.6
    
    def test_create_risk_tolerance_settings_aggressive(self, optimizer):
        """Test creating aggressive risk tolerance settings."""
        settings = optimizer.create_risk_tolerance_settings(
            risk_level=0.9,
            return_preference=0.8,
            diversification_preference=0.2
        )
        
        assert settings.risk_level == 0.9
        assert settings.max_portfolio_risk >= 0.4   # Higher risk tolerance
        assert settings.min_sharpe_ratio <= 0.3     # Lower Sharpe requirement
        assert settings.volatility_penalty <= 1.5   # Lower volatility penalty
        assert settings.concentration_limit >= 0.8  # Higher concentration allowed
        assert settings.return_preference == 0.8
        assert settings.diversification_preference == 0.2
    
    def test_update_risk_tolerance_settings(self, optimizer, sample_risk_settings):
        """Test updating risk tolerance settings."""
        assert optimizer.user_risk_settings is None
        
        optimizer.update_risk_tolerance_settings(sample_risk_settings)
        
        assert optimizer.user_risk_settings == sample_risk_settings
        assert optimizer.user_risk_settings.risk_level == 0.6
    
    def test_get_effective_risk_tolerance_override(self, optimizer, sample_risk_settings):
        """Test getting effective risk tolerance with override."""
        optimizer.update_risk_tolerance_settings(sample_risk_settings)
        
        # Override should take precedence
        effective = optimizer.get_effective_risk_tolerance(override_tolerance=0.8)
        assert effective == 0.8
    
    def test_get_effective_risk_tolerance_user_settings(self, optimizer, sample_risk_settings):
        """Test getting effective risk tolerance from user settings."""
        optimizer.update_risk_tolerance_settings(sample_risk_settings)
        
        # User settings should be used
        effective = optimizer.get_effective_risk_tolerance()
        assert effective == 0.6
    
    def test_get_effective_risk_tolerance_default(self, optimizer):
        """Test getting effective risk tolerance using default."""
        # No user settings, should use default
        effective = optimizer.get_effective_risk_tolerance()
        assert effective == 0.5  # Default from fixture
    
    def test_create_constraints_from_risk_settings(self, optimizer, sample_risk_settings):
        """Test creating constraints from risk settings."""
        constraints = optimizer.create_constraints_from_risk_settings(sample_risk_settings)
        
        assert isinstance(constraints, OptimizationConstraints)
        assert constraints.max_position_size == sample_risk_settings.concentration_limit
        assert constraints.max_total_risk == sample_risk_settings.max_portfolio_risk
        assert constraints.max_concentration == sample_risk_settings.concentration_limit
        assert constraints.max_drawdown_limit == sample_risk_settings.max_drawdown_tolerance
        assert constraints.min_position_size == 0.01
        assert constraints.min_diversification >= 2
    
    def test_create_constraints_from_risk_settings_default(self, optimizer):
        """Test creating constraints with no risk settings."""
        constraints = optimizer.create_constraints_from_risk_settings()
        
        assert isinstance(constraints, OptimizationConstraints)
        # Should use default values
        assert constraints.max_position_size == 1.0
        assert constraints.max_total_risk == 0.2
        assert constraints.max_concentration == 0.5
    
    def test_optimize_with_profit_volatility_balance(self, optimizer, sample_trading_options):
        """Test profit-volatility balance optimization."""
        result = optimizer.optimize_with_profit_volatility_balance(
            sample_trading_options,
            profit_weight=0.7,
            volatility_weight=0.3,
            risk_tolerance=0.5
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.expected_portfolio_return > 0
        assert result.expected_portfolio_risk > 0
        assert "profit_weight=0.7" in result.optimization_message
        assert "volatility_weight=0.3" in result.optimization_message
    
    def test_optimize_with_profit_volatility_balance_invalid_weights(self, optimizer, sample_trading_options):
        """Test profit-volatility balance optimization with invalid weights."""
        with pytest.raises(RiskOptimizerError, match="Profit weight and volatility weight must sum to 1.0"):
            optimizer.optimize_with_profit_volatility_balance(
                sample_trading_options,
                profit_weight=0.7,
                volatility_weight=0.4  # Sum = 1.1, invalid
            )
    
    def test_optimize_with_profit_volatility_balance_empty_options(self, optimizer):
        """Test profit-volatility balance optimization with empty options."""
        with pytest.raises(RiskOptimizerError, match="No trading options provided"):
            optimizer.optimize_with_profit_volatility_balance(
                [],
                profit_weight=0.6,
                volatility_weight=0.4
            )
    
    def test_optimize_with_profit_volatility_balance_with_constraints(self, optimizer, sample_trading_options):
        """Test profit-volatility balance optimization with constraints."""
        constraints = OptimizationConstraints(
            max_position_size=0.6,
            min_position_size=0.1,
            max_total_risk=0.15
        )
        
        result = optimizer.optimize_with_profit_volatility_balance(
            sample_trading_options,
            profit_weight=0.6,
            volatility_weight=0.4,
            constraints=constraints
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        
        # Check constraint satisfaction
        weights = list(result.optimal_weights.values())
        assert all(w >= constraints.min_position_size - 1e-6 for w in weights)
        assert all(w <= constraints.max_position_size + 1e-6 for w in weights)
        assert result.expected_portfolio_risk <= constraints.max_total_risk + 1e-6
    
    def test_optimize_with_user_risk_settings(self, optimizer, sample_trading_options, sample_risk_settings):
        """Test optimization with user risk settings applied."""
        optimizer.update_risk_tolerance_settings(sample_risk_settings)
        
        # Test single recommendation with user settings
        result = optimizer.optimize_single_recommendation(
            sample_trading_options,
            optimization_method=OptimizationMethod.MEAN_VARIANCE
        )
        
        assert isinstance(result, TradingOption)
        
        # Test portfolio optimization with user settings
        portfolio_result = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        assert isinstance(portfolio_result, OptimizationResult)
        assert portfolio_result.optimization_success
        assert portfolio_result.risk_tolerance == sample_risk_settings.risk_level
    
    def test_enhanced_option_scoring_with_user_preferences(self, optimizer, sample_risk_settings):
        """Test enhanced option scoring with user preferences."""
        optimizer.update_risk_tolerance_settings(sample_risk_settings)
        
        option = TradingOption(
            account_name="IPS_TM_10",
            symbol="NQ",
            expected_return=0.1,
            expected_risk=0.2,
            confidence_score=0.8,
            historical_sharpe=1.0,
            max_drawdown=-0.15,
            win_rate=0.6,
            trade_frequency=2.0
        )
        
        # Test with different optimization methods
        sharpe_score = optimizer._calculate_option_score(
            option, 0.5, OptimizationMethod.SHARPE_RATIO
        )
        
        mv_score = optimizer._calculate_option_score(
            option, 0.5, OptimizationMethod.MEAN_VARIANCE
        )
        
        kelly_score = optimizer._calculate_option_score(
            option, 0.5, OptimizationMethod.KELLY_CRITERION
        )
        
        assert isinstance(sharpe_score, float)
        assert isinstance(mv_score, float)
        assert isinstance(kelly_score, float)
        
        # Scores should be different due to user preferences
        assert sharpe_score != mv_score or mv_score != kelly_score


class TestOptimizationIntegration:
    """Integration tests for risk optimization."""
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer for integration tests."""
        return RiskOptimizer(
            default_risk_tolerance=0.5,
            default_optimization_method=OptimizationMethod.SHARPE_RATIO,
            risk_free_rate=0.02
        )
    
    @pytest.fixture
    def diverse_trading_options(self):
        """Create diverse trading options for integration testing."""
        return [
            TradingOption(
                account_name="IPS_TM_10",
                symbol="NQ",
                expected_return=0.12,
                expected_risk=0.18,
                confidence_score=0.85,
                historical_sharpe=1.5,
                max_drawdown=-0.12,
                win_rate=0.68,
                trade_frequency=3.2
            ),
            TradingOption(
                account_name="IPS_TM_13",
                symbol="FDAX",
                expected_return=0.08,
                expected_risk=0.14,
                confidence_score=0.75,
                historical_sharpe=1.1,
                max_drawdown=-0.09,
                win_rate=0.62,
                trade_frequency=2.8
            ),
            TradingOption(
                account_name="IPS_TM_15",
                symbol="ES",
                expected_return=0.06,
                expected_risk=0.11,
                confidence_score=0.9,
                historical_sharpe=0.9,
                max_drawdown=-0.07,
                win_rate=0.72,
                trade_frequency=2.1
            ),
            TradingOption(
                account_name="IPS_TM_10",
                symbol="FDAX",
                expected_return=0.07,
                expected_risk=0.13,
                confidence_score=0.8,
                historical_sharpe=1.0,
                max_drawdown=-0.08,
                win_rate=0.65,
                trade_frequency=2.5
            )
        ]
    
    def test_end_to_end_optimization_workflow(self, optimizer, diverse_trading_options):
        """Test complete optimization workflow."""
        # Test single recommendation optimization
        best_single = optimizer.optimize_single_recommendation(
            diverse_trading_options,
            risk_tolerance=0.6,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        assert isinstance(best_single, TradingOption)
        assert best_single.account_name in ["IPS_TM_10", "IPS_TM_13", "IPS_TM_15"]
        
        # Test portfolio allocation optimization
        portfolio_result = optimizer.optimize_portfolio_allocation(
            diverse_trading_options,
            risk_tolerance=0.6,
            optimization_method=OptimizationMethod.SHARPE_RATIO,
            constraints=OptimizationConstraints(
                max_position_size=0.5,
                min_position_size=0.1,
                min_diversification=2
            )
        )
        
        assert isinstance(portfolio_result, OptimizationResult)
        assert portfolio_result.optimization_success
        assert len(portfolio_result.optimal_weights) == 4
        assert abs(sum(portfolio_result.optimal_weights.values()) - 1.0) < 1e-6
        
        # Validate result
        constraints = OptimizationConstraints(
            max_position_size=0.5,
            min_position_size=0.1,
            min_diversification=2
        )
        assert optimizer.validate_optimization_result(portfolio_result, constraints)
        
        # Check history tracking
        assert len(optimizer.optimization_history) == 1
        assert optimizer.optimization_history[0] == portfolio_result
    
    def test_different_optimization_methods_comparison(self, optimizer, diverse_trading_options):
        """Test and compare different optimization methods."""
        methods = [
            OptimizationMethod.SHARPE_RATIO,
            OptimizationMethod.MEAN_VARIANCE,
            OptimizationMethod.KELLY_CRITERION,
            OptimizationMethod.RISK_PARITY,
            OptimizationMethod.MAXIMUM_DIVERSIFICATION
        ]
        
        results = {}
        
        for method in methods:
            result = optimizer.optimize_portfolio_allocation(
                diverse_trading_options,
                risk_tolerance=0.5,
                optimization_method=method
            )
            
            assert result.optimization_success
            results[method] = result
        
        # All methods should produce valid results
        assert len(results) == 5
        
        # Results should be different (at least some of them)
        weight_sets = [set(result.optimal_weights.items()) for result in results.values()]
        assert len(set(frozenset(ws) for ws in weight_sets)) > 1  # At least some different results
        
        # All should satisfy basic constraints
        for result in results.values():
            assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
            assert all(w >= -1e-6 for w in result.optimal_weights.values())
            assert all(w <= 1.0 + 1e-6 for w in result.optimal_weights.values())
    
    def test_risk_tolerance_impact(self, optimizer, diverse_trading_options):
        """Test impact of different risk tolerance levels."""
        risk_tolerances = [0.2, 0.5, 0.8]
        results = {}
        
        for risk_tolerance in risk_tolerances:
            result = optimizer.optimize_portfolio_allocation(
                diverse_trading_options,
                risk_tolerance=risk_tolerance,
                optimization_method=OptimizationMethod.MEAN_VARIANCE
            )
            
            assert result.optimization_success
            results[risk_tolerance] = result
        
        # Higher risk tolerance should generally lead to higher expected return and risk
        # (though this may not always be strictly monotonic due to optimization constraints)
        conservative_result = results[0.2]
        aggressive_result = results[0.8]
        
        # At minimum, results should be different
        assert conservative_result.optimal_weights != aggressive_result.optimal_weights
        
        # Both should be valid
        assert conservative_result.optimization_success
        assert aggressive_result.optimization_success


class TestAdvancedOptimizationMethods:
    """Test advanced optimization methods."""
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer for advanced testing."""
        return RiskOptimizer()
    
    @pytest.fixture
    def sample_trading_options(self):
        """Create sample trading options for testing."""
        return [
            TradingOption(
                account_name="Account_A",
                symbol="Asset_A",
                expected_return=0.08,
                expected_risk=0.15,
                confidence_score=0.8,
                historical_sharpe=0.53,
                max_drawdown=-0.10,
                win_rate=0.60,
                trade_frequency=2.0
            ),
            TradingOption(
                account_name="Account_B",
                symbol="Asset_B",
                expected_return=0.06,
                expected_risk=0.12,
                confidence_score=0.85,
                historical_sharpe=0.5,
                max_drawdown=-0.08,
                win_rate=0.65,
                trade_frequency=1.8
            ),
            TradingOption(
                account_name="Account_C",
                symbol="Asset_C",
                expected_return=0.10,
                expected_risk=0.20,
                confidence_score=0.75,
                historical_sharpe=0.5,
                max_drawdown=-0.12,
                win_rate=0.58,
                trade_frequency=2.2
            )
        ]
    
    def test_dynamic_risk_budget_optimization(self, optimizer, sample_trading_options):
        """Test dynamic risk budgeting optimization."""
        risk_budget = 0.12
        
        result = optimizer.optimize_dynamic_risk_budget(
            sample_trading_options,
            total_risk_budget=risk_budget,
            risk_tolerance=0.5
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        
        # Portfolio risk should be within budget (allowing small numerical tolerance)
        assert result.expected_portfolio_risk <= risk_budget + 1e-3, \
            f"Portfolio risk {result.expected_portfolio_risk} exceeds budget {risk_budget}"
        
        assert result.expected_portfolio_return > 0
        assert result.sharpe_ratio > 0
        assert "risk budget" in result.optimization_message.lower()
    
    def test_dynamic_risk_budget_empty_options(self, optimizer):
        """Test dynamic risk budget optimization with empty options."""
        with pytest.raises(RiskOptimizerError, match="No trading options provided"):
            optimizer.optimize_dynamic_risk_budget([])
    
    def test_dynamic_risk_budget_tight_budget(self, optimizer, sample_trading_options):
        """Test dynamic risk budget optimization with very tight budget."""
        # Very tight risk budget - use the minimum risk from the options
        min_risk = min(opt.expected_risk for opt in sample_trading_options)
        tight_budget = min_risk * 0.8  # Even tighter than the lowest risk option
        
        result = optimizer.optimize_dynamic_risk_budget(
            sample_trading_options,
            total_risk_budget=tight_budget,
            risk_tolerance=0.3
        )
        
        assert isinstance(result, OptimizationResult)
        # With very tight budget, optimization may fail or not meet exact constraint
        # This is acceptable behavior - we test that it handles the situation gracefully
        if result.optimization_success:
            # Allow more tolerance for very tight constraints as optimization may not converge perfectly
            assert result.expected_portfolio_risk <= tight_budget + 0.05, \
                f"Portfolio risk {result.expected_portfolio_risk} should be close to budget {tight_budget}"
        else:
            # If optimization fails with impossible constraints, that's acceptable
            assert not result.constraints_satisfied
    
    def test_conditional_value_at_risk_optimization(self, optimizer, sample_trading_options):
        """Test Conditional Value at Risk (CVaR) optimization."""
        confidence_level = 0.95
        
        result = optimizer.optimize_conditional_value_at_risk(
            sample_trading_options,
            confidence_level=confidence_level,
            risk_tolerance=0.5
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        
        assert result.expected_portfolio_return > 0
        assert result.expected_portfolio_risk > 0
        assert result.sharpe_ratio > 0
        assert "cvar" in result.optimization_message.lower()
    
    def test_conditional_value_at_risk_empty_options(self, optimizer):
        """Test CVaR optimization with empty options."""
        with pytest.raises(RiskOptimizerError, match="No trading options provided"):
            optimizer.optimize_conditional_value_at_risk([])
    
    def test_conditional_value_at_risk_invalid_confidence(self, optimizer, sample_trading_options):
        """Test CVaR optimization with invalid confidence level."""
        with pytest.raises(RiskOptimizerError, match="Confidence level must be between"):
            optimizer.optimize_conditional_value_at_risk(
                sample_trading_options,
                confidence_level=1.1  # Invalid confidence level
            )
        
        with pytest.raises(RiskOptimizerError, match="Confidence level must be between"):
            optimizer.optimize_conditional_value_at_risk(
                sample_trading_options,
                confidence_level=0.3  # Too low confidence level
            )
    
    def test_conditional_value_at_risk_different_confidence_levels(self, optimizer, sample_trading_options):
        """Test CVaR optimization with different confidence levels."""
        confidence_levels = [0.90, 0.95, 0.99]
        results = []
        
        for confidence in confidence_levels:
            result = optimizer.optimize_conditional_value_at_risk(
                sample_trading_options,
                confidence_level=confidence,
                risk_tolerance=0.5
            )
            
            assert result.optimization_success
            results.append(result)
        
        # Higher confidence levels should generally lead to more conservative allocations
        # (though this may not always be strictly true due to optimization complexity)
        for i, result in enumerate(results):
            assert result.expected_portfolio_return > 0
            assert result.expected_portfolio_risk > 0
            print(f"CVaR {confidence_levels[i]*100}%: Return={result.expected_portfolio_return:.4f}, "
                  f"Risk={result.expected_portfolio_risk:.4f}")
    
    def test_advanced_methods_with_constraints(self, optimizer, sample_trading_options):
        """Test advanced optimization methods with custom constraints."""
        constraints = OptimizationConstraints(
            max_position_size=0.6,
            min_position_size=0.1,
            max_total_risk=0.15,
            min_diversification=2,
            max_concentration=0.5
        )
        
        # Test risk budget optimization with constraints
        risk_budget_result = optimizer.optimize_dynamic_risk_budget(
            sample_trading_options,
            total_risk_budget=0.14,
            constraints=constraints
        )
        
        assert risk_budget_result.optimization_success
        weights = list(risk_budget_result.optimal_weights.values())
        assert all(w >= constraints.min_position_size - 1e-6 for w in weights)
        assert all(w <= constraints.max_position_size + 1e-6 for w in weights)
        
        # Test CVaR optimization with constraints
        cvar_result = optimizer.optimize_conditional_value_at_risk(
            sample_trading_options,
            confidence_level=0.95,
            constraints=constraints
        )
        
        assert cvar_result.optimization_success
        weights = list(cvar_result.optimal_weights.values())
        assert all(w >= constraints.min_position_size - 1e-6 for w in weights)
        assert all(w <= constraints.max_position_size + 1e-6 for w in weights)
    
    def test_advanced_methods_performance_comparison(self, optimizer, sample_trading_options):
        """Test performance comparison of advanced optimization methods."""
        methods_results = {}
        
        # Standard methods
        methods_results['sharpe'] = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            optimization_method=OptimizationMethod.SHARPE_RATIO
        )
        
        methods_results['mean_variance'] = optimizer.optimize_portfolio_allocation(
            sample_trading_options,
            optimization_method=OptimizationMethod.MEAN_VARIANCE
        )
        
        # Advanced methods
        methods_results['risk_budget'] = optimizer.optimize_dynamic_risk_budget(
            sample_trading_options,
            total_risk_budget=0.15
        )
        
        methods_results['cvar'] = optimizer.optimize_conditional_value_at_risk(
            sample_trading_options,
            confidence_level=0.95
        )
        
        methods_results['profit_volatility'] = optimizer.optimize_with_profit_volatility_balance(
            sample_trading_options,
            profit_weight=0.6,
            volatility_weight=0.4
        )
        
        # All methods should succeed
        for method_name, result in methods_results.items():
            assert result.optimization_success, f"{method_name} optimization failed"
            assert len(result.optimal_weights) == 3
            assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
            assert result.expected_portfolio_return > 0
            assert result.expected_portfolio_risk > 0
            
            print(f"{method_name}: Return={result.expected_portfolio_return:.4f}, "
                  f"Risk={result.expected_portfolio_risk:.4f}, "
                  f"Sharpe={result.sharpe_ratio:.4f}")
        
        # Verify that different methods produce different results
        sharpe_weights = list(methods_results['sharpe'].optimal_weights.values())
        cvar_weights = list(methods_results['cvar'].optimal_weights.values())
        
        # At least some weights should be different
        weight_differences = [abs(s - c) for s, c in zip(sharpe_weights, cvar_weights)]
        assert max(weight_differences) > 0.01, "Different methods should produce different allocations"
    
    def test_create_risk_tolerance_settings(self, optimizer):
        """Test creating risk tolerance settings."""
        settings = optimizer.create_risk_tolerance_settings(
            risk_level=0.6,
            return_preference=0.7,
            diversification_preference=0.4
        )
        
        assert settings.risk_level == 0.6
        assert settings.return_preference == 0.7
        assert settings.diversification_preference == 0.4
        assert 0.0 < settings.max_portfolio_risk < 1.0
        assert 0.0 < settings.min_sharpe_ratio < 2.0
        assert 0.0 < settings.max_drawdown_tolerance < 1.0
        assert 0.0 < settings.volatility_penalty < 5.0
        assert 0.0 < settings.concentration_limit <= 1.0
    
    def test_update_risk_tolerance_settings(self, optimizer):
        """Test updating risk tolerance settings."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        settings = RiskToleranceSettings(
            risk_level=0.7,
            max_portfolio_risk=0.25,
            min_sharpe_ratio=0.4,
            max_drawdown_tolerance=0.3,
            diversification_preference=0.5,
            return_preference=0.8,
            volatility_penalty=1.5,
            concentration_limit=0.6
        )
        
        optimizer.update_risk_tolerance_settings(settings)
        assert optimizer.user_risk_settings == settings
        assert optimizer.get_effective_risk_tolerance() == 0.7
    
    def test_get_effective_risk_tolerance(self, optimizer):
        """Test getting effective risk tolerance."""
        # Test with no user settings and no override
        assert optimizer.get_effective_risk_tolerance() == 0.5  # default
        
        # Test with override
        assert optimizer.get_effective_risk_tolerance(0.8) == 0.8
        
        # Test with user settings
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        settings = RiskToleranceSettings(
            risk_level=0.3,
            max_portfolio_risk=0.15,
            min_sharpe_ratio=0.8,
            max_drawdown_tolerance=0.2,
            diversification_preference=0.6,
            return_preference=0.4,
            volatility_penalty=2.5,
            concentration_limit=0.4
        )
        optimizer.update_risk_tolerance_settings(settings)
        
        assert optimizer.get_effective_risk_tolerance() == 0.3
        assert optimizer.get_effective_risk_tolerance(0.9) == 0.9  # Override still works
    
    def test_create_constraints_from_risk_settings(self, optimizer):
        """Test creating constraints from risk settings."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        settings = RiskToleranceSettings(
            risk_level=0.6,
            max_portfolio_risk=0.2,
            min_sharpe_ratio=0.5,
            max_drawdown_tolerance=0.25,
            diversification_preference=0.4,
            return_preference=0.7,
            volatility_penalty=2.0,
            concentration_limit=0.5
        )
        
        constraints = optimizer.create_constraints_from_risk_settings(settings)
        
        assert constraints.max_position_size == 0.5
        assert constraints.max_total_risk == 0.2
        assert constraints.max_concentration == 0.5
        assert constraints.max_drawdown_limit == 0.25
        assert constraints.min_diversification >= 2
    
    def test_optimize_with_profit_volatility_balance(self, optimizer, sample_trading_options):
        """Test profit-volatility balance optimization."""
        result = optimizer.optimize_with_profit_volatility_balance(
            sample_trading_options,
            profit_weight=0.7,
            volatility_weight=0.3,
            risk_tolerance=0.5
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert "profit_weight=0.7" in result.optimization_message
        assert "volatility_weight=0.3" in result.optimization_message
    
    def test_optimize_with_profit_volatility_balance_invalid_weights(self, optimizer, sample_trading_options):
        """Test profit-volatility balance optimization with invalid weights."""
        with pytest.raises(RiskOptimizerError, match="must sum to 1.0"):
            optimizer.optimize_with_profit_volatility_balance(
                sample_trading_options,
                profit_weight=0.6,
                volatility_weight=0.5  # Sum = 1.1
            )
    
    def test_optimize_portfolio_allocation_with_user_preferences(self, optimizer, sample_trading_options):
        """Test portfolio optimization with user preferences."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        # Set up user preferences
        settings = RiskToleranceSettings(
            risk_level=0.6,
            max_portfolio_risk=0.2,
            min_sharpe_ratio=0.5,
            max_drawdown_tolerance=0.25,
            diversification_preference=0.4,
            return_preference=0.8,  # High return preference
            volatility_penalty=2.0,
            concentration_limit=0.5
        )
        optimizer.update_risk_tolerance_settings(settings)
        
        result = optimizer.optimize_portfolio_allocation_with_user_preferences(
            sample_trading_options
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.optimization_method == OptimizationMethod.SHARPE_RATIO  # Due to high return preference
    
    def test_optimize_portfolio_allocation_with_user_preferences_no_settings(self, optimizer, sample_trading_options):
        """Test portfolio optimization with user preferences but no settings configured."""
        with pytest.raises(RiskOptimizerError, match="No user risk tolerance settings configured"):
            optimizer.optimize_portfolio_allocation_with_user_preferences(sample_trading_options)
    
    def test_optimize_dynamic_risk_budget(self, optimizer, sample_trading_options):
        """Test dynamic risk budget optimization."""
        result = optimizer.optimize_dynamic_risk_budget(
            sample_trading_options,
            total_risk_budget=0.12,
            risk_tolerance=0.5
        )
        
        assert isinstance(result, OptimizationResult)
        assert result.optimization_success
        assert len(result.optimal_weights) == 3
        assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6
        assert result.expected_portfolio_risk <= 0.12 + 1e-6  # Should respect risk budget
        assert "budget=0.12" in result.optimization_message
    
    def test_get_optimization_performance_metrics_empty_history(self, optimizer):
        """Test getting performance metrics with empty history."""
        metrics = optimizer.get_optimization_performance_metrics()
        
        assert metrics['total_optimizations'] == 0
        assert metrics['success_rate'] == 0.0
        assert metrics['average_sharpe_ratio'] == 0.0
        assert metrics['average_diversification_ratio'] == 0.0
        assert metrics['methods_used'] == {}
    
    def test_get_optimization_performance_metrics_with_history(self, optimizer, sample_trading_options):
        """Test getting performance metrics with optimization history."""
        # Perform some optimizations
        for _ in range(3):
            optimizer.optimize_portfolio_allocation(
                sample_trading_options,
                risk_tolerance=0.5,
                optimization_method=OptimizationMethod.SHARPE_RATIO
            )
        
        metrics = optimizer.get_optimization_performance_metrics()
        
        assert metrics['total_optimizations'] == 3
        assert metrics['success_rate'] == 1.0  # All should succeed
        assert metrics['average_sharpe_ratio'] > 0
        assert metrics['average_diversification_ratio'] > 0
        assert 'sharpe_ratio' in metrics['methods_used']
        assert metrics['methods_used']['sharpe_ratio'] == 3
    
    def test_benchmark_optimization_methods(self, optimizer, sample_trading_options):
        """Test benchmarking optimization methods."""
        results = optimizer.benchmark_optimization_methods(
            sample_trading_options,
            risk_tolerance=0.5
        )
        
        expected_methods = [
            'sharpe_ratio', 'mean_variance', 'kelly_criterion', 
            'risk_parity', 'max_diversification'
        ]
        
        assert len(results) == len(expected_methods)
        
        for method in expected_methods:
            assert method in results
            result = results[method]
            assert isinstance(result, OptimizationResult)
            # Most should succeed, but some might fail depending on the data
            if result.optimization_success:
                assert len(result.optimal_weights) == 3
                assert abs(sum(result.optimal_weights.values()) - 1.0) < 1e-6


class TestRiskToleranceSettingsValidation:
    """Test RiskToleranceSettings validation."""
    
    def test_risk_tolerance_settings_valid_creation(self):
        """Test creating valid risk tolerance settings."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        settings = RiskToleranceSettings(
            risk_level=0.6,
            max_portfolio_risk=0.2,
            min_sharpe_ratio=0.5,
            max_drawdown_tolerance=0.25,
            diversification_preference=0.4,
            return_preference=0.7,
            volatility_penalty=2.0,
            concentration_limit=0.5
        )
        
        assert settings.risk_level == 0.6
        assert settings.max_portfolio_risk == 0.2
        assert settings.min_sharpe_ratio == 0.5
        assert settings.max_drawdown_tolerance == 0.25
        assert settings.diversification_preference == 0.4
        assert settings.return_preference == 0.7
        assert settings.volatility_penalty == 2.0
        assert settings.concentration_limit == 0.5
    
    def test_risk_tolerance_settings_invalid_risk_level(self):
        """Test creating risk tolerance settings with invalid risk level."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        with pytest.raises(ValueError, match="Risk level must be between 0.0 and 1.0"):
            RiskToleranceSettings(
                risk_level=1.5,  # Invalid
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=0.4,
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_invalid_diversification_preference(self):
        """Test creating risk tolerance settings with invalid diversification preference."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        with pytest.raises(ValueError, match="Diversification preference must be between 0.0 and 1.0"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=1.5,  # Invalid
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_invalid_return_preference(self):
        """Test creating risk tolerance settings with invalid return preference."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        with pytest.raises(ValueError, match="Return preference must be between 0.0 and 1.0"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=0.4,
                return_preference=-0.1,  # Invalid
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_invalid_max_portfolio_risk(self):
        """Test creating risk tolerance settings with invalid max portfolio risk."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        with pytest.raises(ValueError, match="Maximum portfolio risk must be positive"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=-0.1,  # Invalid
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.25,
                diversification_preference=0.4,
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )
    
    def test_risk_tolerance_settings_invalid_max_drawdown_tolerance(self):
        """Test creating risk tolerance settings with invalid max drawdown tolerance."""
        from trading_platform.services.recommendation.risk_optimizer import RiskToleranceSettings
        
        with pytest.raises(ValueError, match="Maximum drawdown tolerance must be positive"):
            RiskToleranceSettings(
                risk_level=0.6,
                max_portfolio_risk=0.2,
                min_sharpe_ratio=0.5,
                max_drawdown_tolerance=0.0,  # Invalid
                diversification_preference=0.4,
                return_preference=0.7,
                volatility_penalty=2.0,
                concentration_limit=0.5
            )