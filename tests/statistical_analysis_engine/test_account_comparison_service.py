"""
Unit tests for account comparison service.

Tests statistical comparison methods between accounts, hypothesis testing
for performance differences, and correlation analysis.

This is part of task 5.3: Implement account comparison and statistical testing
Requirements: 3.3, 3.5
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from trading_platform.services.account_comparison_service import (
    AccountComparisonService,
    AccountComparisonResult,
    CorrelationAnalysisResult,
    MultiAccountAnalysisResult,
    AccountComparisonError
)
from trading_platform.models.trading import ProcessedTrade


class TestAccountComparisonService:
    """Test cases for AccountComparisonService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return AccountComparisonService(significance_level=0.05, confidence_level=0.95)
    
    @pytest.fixture
    def sample_trades_account_1(self):
        """Create sample trades for account 1."""
        base_time = datetime(2024, 1, 1, 9, 0)
        trades = []
        
        # Create 20 trades with varying P&L
        profits = [100, -50, 75, -25, 150, -75, 200, -100, 125, -60,
                  80, -40, 110, -30, 90, -45, 160, -80, 140, -70]
        
        for i, profit in enumerate(profits):
            entry_time = base_time + timedelta(days=i, hours=1)
            exit_time = entry_time + timedelta(minutes=30)
            
            # Calculate prices to match the desired P&L
            entry_price = 15000.0
            quantity = 20
            commission = 2.0
            
            # For LONG: profit_loss = (exit_price - entry_price) * quantity - commission
            # For SHORT: profit_loss = (entry_price - exit_price) * quantity - commission
            if profit > 0:  # LONG trade
                exit_price = entry_price + (profit + commission) / quantity
                side = "LONG"
            else:  # SHORT trade
                exit_price = entry_price - (profit + commission) / quantity
                side = "SHORT"
            
            trade = ProcessedTrade(
                trade_id=f"T1_{i+1:03d}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit,
                commission=commission,
                duration_minutes=30,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"E1_{i+1}",
                exit_order_id=f"X1_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_trades_account_2(self):
        """Create sample trades for account 2."""
        base_time = datetime(2024, 1, 1, 10, 0)
        trades = []
        
        # Create 15 trades with different performance characteristics
        profits = [80, -60, 95, -35, 120, -85, 170, -90, 105, -50,
                  70, -30, 130, -65, 85]
        
        for i, profit in enumerate(profits):
            entry_time = base_time + timedelta(days=i, hours=2)
            exit_time = entry_time + timedelta(minutes=45)
            
            # Calculate prices to match the desired P&L
            entry_price = 17000.0
            quantity = 25
            commission = 3.0
            
            # For LONG: profit_loss = (exit_price - entry_price) * quantity - commission
            # For SHORT: profit_loss = (entry_price - exit_price) * quantity - commission
            if profit > 0:  # LONG trade
                exit_price = entry_price + (profit + commission) / quantity
                side = "LONG"
            else:  # SHORT trade
                exit_price = entry_price - (profit + commission) / quantity
                side = "SHORT"
            
            trade = ProcessedTrade(
                trade_id=f"T2_{i+1:03d}",
                account_name="IPS_TM_13",
                symbol="FDAX",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit,
                commission=commission,
                duration_minutes=45,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"E2_{i+1}",
                exit_order_id=f"X2_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_trades_account_3(self):
        """Create sample trades for account 3."""
        base_time = datetime(2024, 1, 1, 11, 0)
        trades = []
        
        # Create 18 trades with high volatility
        profits = [200, -150, 180, -120, 250, -200, 300, -180, 220, -140,
                  160, -100, 280, -160, 190, -130, 240, -170]
        
        for i, profit in enumerate(profits):
            entry_time = base_time + timedelta(days=i, hours=1, minutes=30)
            exit_time = entry_time + timedelta(minutes=20)
            
            # Calculate prices to match the desired P&L
            entry_price = 15100.0
            quantity = 30
            commission = 2.5
            
            # For LONG: profit_loss = (exit_price - entry_price) * quantity - commission
            # For SHORT: profit_loss = (entry_price - exit_price) * quantity - commission
            if profit > 0:  # LONG trade
                exit_price = entry_price + (profit + commission) / quantity
                side = "LONG"
            else:  # SHORT trade
                exit_price = entry_price - (profit + commission) / quantity
                side = "SHORT"
            
            trade = ProcessedTrade(
                trade_id=f"T3_{i+1:03d}",
                account_name="IPS_TM_15",
                symbol="NQ",
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                side=side,
                profit_loss=profit,
                commission=commission,
                duration_minutes=20,
                hour_of_day=entry_time.hour,
                day_of_week=entry_time.weekday(),
                entry_order_id=f"E3_{i+1}",
                exit_order_id=f"X3_{i+1}"
            )
            trades.append(trade)
        
        return trades
    
    def test_compare_two_accounts_basic(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test basic two-account comparison."""
        result = service.compare_two_accounts(
            sample_trades_account_1,
            sample_trades_account_2,
            "IPS_TM_10",
            "IPS_TM_13"
        )
        
        assert isinstance(result, AccountComparisonResult)
        assert result.account_1 == "IPS_TM_10"
        assert result.account_2 == "IPS_TM_13"
        assert result.symbol_1 == "NQ"
        assert result.symbol_2 == "FDAX"
        assert result.account_1_trades == 20
        assert result.account_2_trades == 15
        
        # Check statistical calculations
        assert isinstance(result.mean_difference, float)
        assert isinstance(result.t_statistic, float)
        assert isinstance(result.p_value, float)
        assert isinstance(result.is_significantly_different, bool)
        assert isinstance(result.cohens_d, float)
        assert result.effect_size_interpretation in ["negligible", "small", "medium", "large"]
    
    def test_compare_two_accounts_with_period(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test account comparison with specific time period."""
        period_start = datetime(2024, 1, 5)
        period_end = datetime(2024, 1, 15)
        
        result = service.compare_two_accounts(
            sample_trades_account_1,
            sample_trades_account_2,
            "IPS_TM_10",
            "IPS_TM_13",
            period_start,
            period_end
        )
        
        assert result.comparison_period_start == period_start
        assert result.comparison_period_end == period_end
        assert result.account_1_trades <= 20  # Should be filtered
        assert result.account_2_trades <= 15  # Should be filtered
    
    def test_compare_two_accounts_empty_trades(self, service):
        """Test comparison with empty trade lists."""
        with pytest.raises(AccountComparisonError, match="Both accounts must have trades"):
            service.compare_two_accounts([], [], "Account1", "Account2")
    
    def test_compare_two_accounts_statistical_properties(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test statistical properties of comparison results."""
        result = service.compare_two_accounts(
            sample_trades_account_1,
            sample_trades_account_2,
            "IPS_TM_10",
            "IPS_TM_13"
        )
        
        # Confidence interval should contain the mean difference
        assert result.confidence_interval_lower <= result.mean_difference <= result.confidence_interval_upper
        
        # Variance ratio should be positive
        assert result.variance_ratio > 0
        
        # P-values should be between 0 and 1
        assert 0 <= result.p_value <= 1
        assert 0 <= result.variance_test_p_value <= 1
        
        # Sharpe ratios should be calculated if possible
        if result.sharpe_ratio_1 is not None and result.sharpe_ratio_2 is not None:
            assert result.sharpe_difference is not None
    
    def test_analyze_correlations_basic(self, service, sample_trades_account_1, sample_trades_account_2, sample_trades_account_3):
        """Test basic correlation analysis."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": sample_trades_account_2,
            "IPS_TM_15": sample_trades_account_3
        }
        
        result = service.analyze_correlations(account_trades, min_overlapping_days=5)
        
        assert isinstance(result, CorrelationAnalysisResult)
        assert len(result.account_pairs) == 3  # C(3,2) = 3 pairs
        assert len(result.return_correlations) <= 3
        assert len(result.correlation_p_values) <= 3
        assert len(result.significant_correlations) <= 3
        
        # Check correlation values are valid
        for correlation in result.return_correlations.values():
            assert -1 <= correlation <= 1
        
        # Check p-values are valid
        for p_value in result.correlation_p_values.values():
            assert 0 <= p_value <= 1
    
    def test_analyze_correlations_insufficient_accounts(self, service, sample_trades_account_1):
        """Test correlation analysis with insufficient accounts."""
        account_trades = {"IPS_TM_10": sample_trades_account_1}
        
        with pytest.raises(AccountComparisonError, match="Need at least 2 accounts"):
            service.analyze_correlations(account_trades)
    
    def test_analyze_correlations_summary_statistics(self, service, sample_trades_account_1, sample_trades_account_2, sample_trades_account_3):
        """Test correlation analysis summary statistics."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": sample_trades_account_2,
            "IPS_TM_15": sample_trades_account_3
        }
        
        result = service.analyze_correlations(account_trades, min_overlapping_days=5)
        
        if result.return_correlations:
            correlations = list(result.return_correlations.values())
            
            # Summary statistics should be consistent
            assert result.min_correlation == min(correlations)
            assert result.max_correlation == max(correlations)
            assert abs(result.average_correlation - np.mean(correlations)) < 1e-10
            
            # Diversification ratio should be between 0 and 1
            assert 0 < result.diversification_ratio <= 1
    
    def test_perform_multi_account_analysis(self, service, sample_trades_account_1, sample_trades_account_2, sample_trades_account_3):
        """Test comprehensive multi-account analysis."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": sample_trades_account_2,
            "IPS_TM_15": sample_trades_account_3
        }
        
        result = service.perform_multi_account_analysis(account_trades)
        
        assert isinstance(result, MultiAccountAnalysisResult)
        assert len(result.accounts) == 3
        assert len(result.pairwise_comparisons) == 3  # C(3,2) = 3 pairs
        
        # ANOVA results
        assert isinstance(result.f_statistic, float)
        assert 0 <= result.anova_p_value <= 1
        assert isinstance(result.significant_differences, bool)
        
        # Best/worst account identification
        assert result.best_performing_account in result.accounts
        assert result.worst_performing_account in result.accounts
        assert result.most_consistent_account in result.accounts
        assert result.most_volatile_account in result.accounts
        
        # Correlation analysis should be included
        assert isinstance(result.correlation_analysis, CorrelationAnalysisResult)
    
    def test_perform_multi_account_analysis_insufficient_accounts(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test multi-account analysis with insufficient accounts."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": sample_trades_account_2
        }
        
        with pytest.raises(AccountComparisonError, match="Need at least 3 accounts"):
            service.perform_multi_account_analysis(account_trades)
    
    def test_test_performance_hypothesis_two_sided(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test two-sided hypothesis testing."""
        result = service.test_performance_hypothesis(
            sample_trades_account_1,
            sample_trades_account_2,
            hypothesis="two_sided",
            expected_difference=0.0
        )
        
        assert "t_statistic" in result
        assert "p_value" in result
        assert "mean_difference" in result
        assert "effect_size" in result
        assert "is_significant" in result
        assert result["hypothesis"] == "two_sided"
        assert result["expected_difference"] == 0.0
        
        # P-value should be valid
        assert 0 <= result["p_value"] <= 1
    
    def test_test_performance_hypothesis_one_sided(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test one-sided hypothesis testing."""
        # Test "greater" hypothesis
        result_greater = service.test_performance_hypothesis(
            sample_trades_account_1,
            sample_trades_account_2,
            hypothesis="greater"
        )
        assert result_greater["hypothesis"] == "greater"
        assert 0 <= result_greater["p_value"] <= 1
        
        # Test "less" hypothesis
        result_less = service.test_performance_hypothesis(
            sample_trades_account_1,
            sample_trades_account_2,
            hypothesis="less"
        )
        assert result_less["hypothesis"] == "less"
        assert 0 <= result_less["p_value"] <= 1
    
    def test_test_performance_hypothesis_invalid_hypothesis(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test hypothesis testing with invalid hypothesis type."""
        with pytest.raises(AccountComparisonError, match="Unknown hypothesis type"):
            service.test_performance_hypothesis(
                sample_trades_account_1,
                sample_trades_account_2,
                hypothesis="invalid"
            )
    
    def test_test_performance_hypothesis_empty_trades(self, service):
        """Test hypothesis testing with empty trades."""
        with pytest.raises(AccountComparisonError, match="Both groups must have trades"):
            service.test_performance_hypothesis([], [], hypothesis="two_sided")
    
    def test_validate_trades_for_comparison_valid(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test validation with valid trades."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": sample_trades_account_2
        }
        
        assert service.validate_trades_for_comparison(account_trades) is True
    
    def test_validate_trades_for_comparison_empty_dict(self, service):
        """Test validation with empty account trades dictionary."""
        with pytest.raises(AccountComparisonError, match="Account trades dictionary cannot be empty"):
            service.validate_trades_for_comparison({})
    
    def test_validate_trades_for_comparison_insufficient_accounts(self, service, sample_trades_account_1):
        """Test validation with insufficient accounts."""
        account_trades = {"IPS_TM_10": sample_trades_account_1}
        
        with pytest.raises(AccountComparisonError, match="Need at least 2 accounts"):
            service.validate_trades_for_comparison(account_trades)
    
    def test_validate_trades_for_comparison_empty_trades(self, service, sample_trades_account_1):
        """Test validation with empty trades for an account."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": []
        }
        
        with pytest.raises(AccountComparisonError, match="Account IPS_TM_13 has no trades"):
            service.validate_trades_for_comparison(account_trades)
    
    def test_filter_trades_by_period(self, service, sample_trades_account_1):
        """Test trade filtering by time period."""
        period_start = datetime(2024, 1, 5)
        period_end = datetime(2024, 1, 10)
        
        filtered_trades = service._filter_trades_by_period(
            sample_trades_account_1,
            period_start,
            period_end
        )
        
        # All filtered trades should be within the period
        for trade in filtered_trades:
            assert period_start <= trade.entry_time <= period_end
        
        # Should have fewer trades than original
        assert len(filtered_trades) <= len(sample_trades_account_1)
    
    def test_filter_trades_by_period_no_filters(self, service, sample_trades_account_1):
        """Test trade filtering with no period filters."""
        filtered_trades = service._filter_trades_by_period(
            sample_trades_account_1,
            None,
            None
        )
        
        # Should return all trades
        assert len(filtered_trades) == len(sample_trades_account_1)
        assert filtered_trades == sample_trades_account_1
    
    def test_calculate_daily_returns(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test daily returns calculation."""
        account_trades = {
            "IPS_TM_10": sample_trades_account_1,
            "IPS_TM_13": sample_trades_account_2
        }
        
        period_start = datetime(2024, 1, 1)
        period_end = datetime(2024, 1, 31)
        
        daily_returns = service._calculate_daily_returns(
            account_trades,
            period_start,
            period_end
        )
        
        assert "IPS_TM_10" in daily_returns
        assert "IPS_TM_13" in daily_returns
        
        # Each account should have daily returns
        for account, returns in daily_returns.items():
            assert isinstance(returns, dict)
            for date, return_value in returns.items():
                assert isinstance(return_value, (int, float))
    
    def test_interpret_effect_size(self, service):
        """Test effect size interpretation."""
        assert service._interpret_effect_size(0.1) == "negligible"
        assert service._interpret_effect_size(0.3) == "small"
        assert service._interpret_effect_size(0.6) == "medium"
        assert service._interpret_effect_size(1.0) == "large"
    
    def test_calculate_effect_size(self, service):
        """Test effect size calculation."""
        returns_1 = [10, 20, 30, 40, 50]
        returns_2 = [5, 15, 25, 35, 45]
        
        effect_size = service._calculate_effect_size(returns_1, returns_2)
        
        # Should be positive since returns_1 has higher mean
        assert effect_size > 0
        assert isinstance(effect_size, float)
    
    def test_calculate_diversification_ratio(self, service):
        """Test diversification ratio calculation."""
        # Perfect positive correlation
        correlations_high = [0.9, 0.8, 0.85]
        ratio_high = service._calculate_diversification_ratio(correlations_high)
        
        # Low correlation
        correlations_low = [0.1, 0.2, 0.15]
        ratio_low = service._calculate_diversification_ratio(correlations_low)
        
        # Low correlation should give higher diversification ratio
        assert ratio_low > ratio_high
        assert 0 < ratio_high <= 1
        assert 0 < ratio_low <= 1
    
    def test_calculate_diversification_ratio_empty(self, service):
        """Test diversification ratio with empty correlations."""
        ratio = service._calculate_diversification_ratio([])
        assert ratio == 1.0
    
    def test_service_initialization(self):
        """Test service initialization with custom parameters."""
        service = AccountComparisonService(significance_level=0.01, confidence_level=0.99)
        
        assert service.significance_level == 0.01
        assert service.confidence_level == 0.99
        assert service.performance_calculator is not None
    
    def test_comparison_result_properties(self, service, sample_trades_account_1, sample_trades_account_2):
        """Test that comparison result has all expected properties."""
        result = service.compare_two_accounts(
            sample_trades_account_1,
            sample_trades_account_2,
            "IPS_TM_10",
            "IPS_TM_13"
        )
        
        # Check all required attributes exist
        required_attrs = [
            'account_1', 'account_2', 'symbol_1', 'symbol_2',
            'comparison_period_start', 'comparison_period_end',
            'account_1_trades', 'account_2_trades',
            'account_1_mean_return', 'account_2_mean_return',
            'account_1_volatility', 'account_2_volatility',
            'mean_difference', 't_statistic', 'p_value',
            'is_significantly_different', 'confidence_interval_lower',
            'confidence_interval_upper', 'cohens_d', 'effect_size_interpretation',
            'sharpe_ratio_1', 'sharpe_ratio_2', 'sharpe_difference',
            'variance_ratio', 'variance_test_p_value', 'equal_variances'
        ]
        
        for attr in required_attrs:
            assert hasattr(result, attr), f"Missing attribute: {attr}"


if __name__ == "__main__":
    pytest.main([__file__])