"""
Tests for data models with validation.
"""

import pytest
from datetime import datetime
from trading_platform.models.sierra_chart import SierraChartTradeRecord
from trading_platform.models.trading import ProcessedTrade, Account, PerformanceMetrics, TradingRecommendation
from trading_platform.utils.validators import ValidationError


class TestSierraChartTradeRecord:
    """Test SierraChart trade record model with validation."""
    
    def test_create_valid_record(self):
        """Test creating a valid SierraChart trade record."""
        record = SierraChartTradeRecord(
            activity_type="Fills",
            date_time=datetime(2024, 3, 5, 16, 5, 58),
            trans_date_time=datetime(2024, 3, 5, 16, 5, 59),
            service_order_id="8951508",
            order_type="Market",
            quantity=3,
            order_status="Filled",
            trade_account="IPS_TM_10",
            buy_sell="Sell",
            price=None,
            price2=None,
            fill_price=17943.5,
            filled_quantity=3,
            note="AutoTrader_",
            order_action_source="Trading Evaluator",
            internal_order_id="758655",
            symbol="NQH24",
            open_close="Open",
            parent_internal_order_id=None,
            position_quantity=-3,
            fill_execution_service_id="8951508.1",
            high_during_position=None,
            low_during_position=None,
            account_balance=0.0,
            exchange_order_id="8951508",
            client_order_id="758655.43161",
            time_in_force="Good till Canceled",
            username="shimishon",
            is_automated="Y"
        )
        
        assert record.trade_account == "IPS_TM_10"
        assert record.is_sell is True
        assert record.is_buy is False
        assert record.is_opening is True
        assert record.base_symbol == "NQ"
        assert record.trade_id == "IPS_TM_10_758655"
        assert record.is_same_day_trade is True
    
    def test_invalid_activity_type(self):
        """Test invalid activity type validation."""
        with pytest.raises(ValidationError, match="ActivityType must be one of"):
            SierraChartTradeRecord(
                activity_type="Invalid",
                date_time=datetime(2024, 3, 5, 16, 5, 58),
                trans_date_time=datetime(2024, 3, 5, 16, 5, 59),
                service_order_id="8951508",
                order_type="Market",
                quantity=3,
                order_status="Filled",
                trade_account="IPS_TM_10",
                buy_sell="Sell",
                price=None,
                price2=None,
                fill_price=17943.5,
                filled_quantity=3,
                note="",
                order_action_source="",
                internal_order_id="758655",
                symbol="NQH24",
                open_close="Open",
                parent_internal_order_id=None,
                position_quantity=-3,
                fill_execution_service_id="",
                high_during_position=None,
                low_during_position=None,
                account_balance=0.0,
                exchange_order_id="",
                client_order_id="",
                time_in_force="",
                username="",
                is_automated="Y"
            )
    
    def test_invalid_trade_account(self):
        """Test invalid trade account validation."""
        with pytest.raises(ValidationError, match="does not match expected pattern"):
            SierraChartTradeRecord(
                activity_type="Fills",
                date_time=datetime(2024, 3, 5, 16, 5, 58),
                trans_date_time=datetime(2024, 3, 5, 16, 5, 59),
                service_order_id="8951508",
                order_type="Market",
                quantity=3,
                order_status="Filled",
                trade_account="INVALID_ACCOUNT",
                buy_sell="Sell",
                price=None,
                price2=None,
                fill_price=17943.5,
                filled_quantity=3,
                note="",
                order_action_source="",
                internal_order_id="758655",
                symbol="NQH24",
                open_close="Open",
                parent_internal_order_id=None,
                position_quantity=-3,
                fill_execution_service_id="",
                high_during_position=None,
                low_during_position=None,
                account_balance=0.0,
                exchange_order_id="",
                client_order_id="",
                time_in_force="",
                username="",
                is_automated="Y"
            )
    
    def test_from_dict_creation(self):
        """Test creating record from dictionary."""
        data = {
            'activity_type': "Fills",
            'date_time': datetime(2024, 3, 5, 16, 5, 58),
            'trans_date_time': datetime(2024, 3, 5, 16, 5, 59),
            'service_order_id': "8951508",
            'order_type': "Market",
            'quantity': 3,
            'order_status': "Filled",
            'trade_account': "IPS_TM_10",
            'buy_sell': "Sell",
            'price': None,
            'price2': None,
            'fill_price': 17943.5,
            'filled_quantity': 3,
            'note': "",
            'order_action_source': "",
            'internal_order_id': "758655",
            'symbol': "NQH24",
            'open_close': "Open",
            'parent_internal_order_id': None,
            'position_quantity': -3,
            'fill_execution_service_id': "",
            'high_during_position': None,
            'low_during_position': None,
            'account_balance': 0.0,
            'exchange_order_id': "",
            'client_order_id': "",
            'time_in_force': "",
            'username': "",
            'is_automated': "Y"
        }
        
        record = SierraChartTradeRecord.from_dict(data, "test_file.txt")
        assert record.file_source == "test_file.txt"
        assert record.trade_account == "IPS_TM_10"


class TestProcessedTrade:
    """Test processed trade model with validation."""
    
    def test_create_valid_processed_trade(self):
        """Test creating a valid processed trade."""
        entry_time = datetime(2024, 3, 5, 16, 5, 58)
        exit_time = datetime(2024, 3, 5, 16, 7, 42)
        duration = int((exit_time - entry_time).total_seconds() / 60)  # Calculate actual duration
        
        trade = ProcessedTrade(
            trade_id="IPS_TM_10_001",
            account_name="IPS_TM_10",
            symbol="NQ",
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=17943.5,
            exit_price=17934.75,
            quantity=3,
            side="SHORT",
            profit_loss=26.25,  # (17943.5 - 17934.75) * 3
            commission=0.0,
            duration_minutes=duration,  # Use calculated duration
            hour_of_day=16,
            day_of_week=1,  # Tuesday
            entry_order_id="758655",
            exit_order_id="758661"
        )
        
        assert trade.is_profitable is True
        assert trade.return_percentage > 0
        assert trade.account_name == "IPS_TM_10"
        assert trade.is_short is True
        assert trade.is_long is False
    
    def test_invalid_side(self):
        """Test invalid side validation."""
        with pytest.raises(ValidationError, match="Side must be 'LONG' or 'SHORT'"):
            ProcessedTrade(
                trade_id="IPS_TM_10_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=datetime(2024, 3, 5, 16, 5, 58),
                exit_time=datetime(2024, 3, 5, 16, 7, 42),
                entry_price=17943.5,
                exit_price=17934.75,
                quantity=3,
                side="INVALID",
                profit_loss=26.25,
                commission=0.0,
                duration_minutes=104,
                hour_of_day=16,
                day_of_week=1,
                entry_order_id="758655",
                exit_order_id="758661"
            )
    
    def test_invalid_time_order(self):
        """Test invalid time order validation."""
        with pytest.raises(ValidationError, match="Exit time must be after entry time"):
            ProcessedTrade(
                trade_id="IPS_TM_10_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=datetime(2024, 3, 5, 16, 7, 42),
                exit_time=datetime(2024, 3, 5, 16, 5, 58),  # Before entry
                entry_price=17943.5,
                exit_price=17934.75,
                quantity=3,
                side="SHORT",
                profit_loss=26.25,
                commission=0.0,
                duration_minutes=104,
                hour_of_day=16,
                day_of_week=1,
                entry_order_id="758655",
                exit_order_id="758661"
            )


class TestAccount:
    """Test account model with validation."""
    
    def test_create_valid_account(self):
        """Test creating a valid account."""
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=100,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 3, 5),
            is_active=True
        )
        
        assert account.name == "IPS_TM_10"
        assert account.symbol == "NQ"
        assert account.trading_days > 0
        assert account.trades_per_day > 0
    
    def test_invalid_date_order(self):
        """Test invalid date order validation."""
        with pytest.raises(ValidationError, match="Last trade date cannot be before first trade date"):
            Account(
                name="IPS_TM_10",
                symbol="NQ",
                total_trades=100,
                first_trade_date=datetime(2024, 3, 5),
                last_trade_date=datetime(2024, 1, 1),  # Before first trade
                is_active=True
            )


class TestPerformanceMetrics:
    """Test performance metrics model with validation."""
    
    def test_create_valid_metrics(self):
        """Test creating valid performance metrics."""
        metrics = PerformanceMetrics(
            account_name="IPS_TM_10",
            symbol="NQ",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 5),
            total_return=1000.0,
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=0.6,
            average_win=25.0,
            average_loss=-15.0,
            profit_factor=1.67,
            max_drawdown=-200.0,
            sharpe_ratio=1.5,
            volatility=0.15,
            largest_win=100.0,
            largest_loss=-50.0
        )
        
        assert metrics.account_name == "IPS_TM_10"
        assert metrics.win_rate == 0.6
        assert metrics.average_trade == 10.0
        assert metrics.expectancy > 0
        assert metrics.recovery_factor > 0
    
    def test_invalid_trade_count_consistency(self):
        """Test invalid trade count consistency."""
        with pytest.raises(ValidationError, match="Winning trades \\+ losing trades must equal total trades"):
            PerformanceMetrics(
                account_name="IPS_TM_10",
                symbol="NQ",
                period_start=datetime(2024, 1, 1),
                period_end=datetime(2024, 3, 5),
                total_return=1000.0,
                total_trades=100,
                winning_trades=60,
                losing_trades=50,  # 60 + 50 != 100
                win_rate=0.6,
                average_win=25.0,
                average_loss=-15.0,
                profit_factor=1.67,
                max_drawdown=-200.0,
                sharpe_ratio=1.5,
                volatility=0.15,
                largest_win=100.0,
                largest_loss=-50.0
            )


class TestTradingRecommendation:
    """Test trading recommendation model with validation."""
    
    def test_create_valid_recommendation(self):
        """Test creating a valid trading recommendation."""
        recommendation = TradingRecommendation(
            timestamp=datetime(2024, 3, 5, 16, 0, 0),
            account_name="IPS_TM_10",
            symbol="NQ",
            recommended_action="TRADE",
            confidence_score=0.85,
            expected_return=25.0,
            expected_risk=15.0,
            reasoning="Strong historical performance at this time",
            hour_of_day=16,
            day_of_week=1,
            historical_win_rate=0.65,
            avg_profit_this_time=22.5
        )
        
        assert recommendation.should_trade is True
        assert recommendation.is_high_confidence is True
        assert recommendation.risk_reward_ratio > 1.0
    
    def test_invalid_confidence_score(self):
        """Test invalid confidence score validation."""
        with pytest.raises(ValidationError, match="Confidence score must be between 0.0 and 1.0"):
            TradingRecommendation(
                timestamp=datetime(2024, 3, 5, 16, 0, 0),
                account_name="IPS_TM_10",
                symbol="NQ",
                recommended_action="TRADE",
                confidence_score=1.5,  # Invalid
                expected_return=25.0,
                expected_risk=15.0,
                reasoning="Test",
                hour_of_day=16,
                day_of_week=1,
                historical_win_rate=0.65,
                avg_profit_this_time=22.5
            )
    
    def test_invalid_action(self):
        """Test invalid recommended action validation."""
        with pytest.raises(ValidationError, match="Recommended action must be 'TRADE' or 'AVOID'"):
            TradingRecommendation(
                timestamp=datetime(2024, 3, 5, 16, 0, 0),
                account_name="IPS_TM_10",
                symbol="NQ",
                recommended_action="INVALID",
                confidence_score=0.85,
                expected_return=25.0,
                expected_risk=15.0,
                reasoning="Test",
                hour_of_day=16,
                day_of_week=1,
                historical_win_rate=0.65,
                avg_profit_this_time=22.5
            )


if __name__ == "__main__":
    pytest.main([__file__])