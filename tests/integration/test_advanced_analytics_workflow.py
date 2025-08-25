"""
Comprehensive integration tests for advanced analytics workflows.

This module tests the combined Monte Carlo and Walk-Forward analysis pipeline including:
- Monte Carlo risk simulation
- Walk-Forward validation
- Combined risk-performance analysis
- Advanced statistical validation
- Integrated recommendation generation

Requirements: 1.1, 2.1, 3.1, 11.1, 12.1
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from unittest.mock import Mock, patch, AsyncMock
import json
from decimal import Decimal

# Import advanced analytics components
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.models.time_bin_analytics import (
    TimeBinAnalysis, MonteCarloResult, WalkForwardResult
)
from trading_platform.services.statistical_analysis_engine.monte_carlo_simulator import (
    MonteCarloSimulator, RiskMetrics, SimulationConfig
)
from trading_platform.services.statistical_analysis_engine.walk_forward_analyzer import (
    WalkForwardAnalyzer, ValidationScheme, ValidationResult
)
from trading_platform.services.statistical_analysis_engine.performance_metrics_calculator import (
    PerformanceMetricsCalculator
)
from trading_platform.services.recommendation.recommendation_service import (
    RecommendationService, RecommendationType
)
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer
from trading_platform.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestAdvancedAnalyticsWorkflow:
    """Test comprehensive advanced analytics workflow."""
    
    @pytest.fixture
    async def test_database_with_analytics_data(self):
        """Create test database with comprehensive analytics test data."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            # Create test accounts with different performance characteristics
            accounts = [
                Account(name="CONSISTENT_PERFORMER", symbol="ES", total_trades=0, is_active=True),
                Account(name="VOLATILE_HIGH_RETURN", symbol="NQ", total_trades=0, is_active=True),
                Account(name="LOW_RISK_STEADY", symbol="YM", total_trades=0, is_active=True),
                Account(name="TREND_FOLLOWING", symbol="ES", total_trades=0, is_active=True)
            ]
            session.add_all(accounts)
            
            # Generate 120 days of detailed trading data for advanced analytics
            base_date = datetime(2024, 1, 1, 9, 30)
            all_trades = []
            
            for account in accounts:
                trade_id = 1
                
                # Define account-specific performance characteristics
                if account.name == "CONSISTENT_PERFORMER":
                    base_return = 0.6  # 60% win rate
                    return_volatility = 25.0  # Low volatility
                    trend_factor = 0.05  # Slight upward trend
                    
                elif account.name == "VOLATILE_HIGH_RETURN":
                    base_return = 0.55  # 55% win rate
                    return_volatility = 60.0  # High volatility
                    trend_factor = 0.15  # Strong upward trend
                    
                elif account.name == "LOW_RISK_STEADY":
                    base_return = 0.70  # 70% win rate
                    return_volatility = 15.0  # Very low volatility
                    trend_factor = 0.02  # Minimal trend
                    
                else:  # TREND_FOLLOWING
                    base_return = 0.50  # 50% win rate baseline
                    return_volatility = 40.0  # Medium-high volatility
                    trend_factor = 0.08  # Moderate trend
                
                # Generate trades over 120 days
                for day_offset in range(120):
                    trade_date = base_date + timedelta(days=day_offset)
                    
                    if trade_date.weekday() >= 5:  # Skip weekends
                        continue
                    
                    # Create time-dependent performance variations
                    day_factor = np.sin(day_offset * 0.1) * 0.1  # Cyclical performance
                    weekly_factor = np.sin(day_offset * 0.02) * 0.05  # Weekly patterns
                    
                    # Generate multiple trades per day with realistic patterns
                    daily_trades = np.random.randint(3, 8)  # 3-7 trades per day
                    
                    for trade_idx in range(daily_trades):
                        # Distribute trades throughout the day
                        hour_offset = trade_idx * 1.5  # Spread trades every 1.5 hours
                        entry_hour = int(9 + hour_offset) % 16  # Keep within market hours
                        entry_minute = np.random.randint(0, 60)
                        
                        entry_time = trade_date.replace(
                            hour=max(9, min(15, entry_hour)),
                            minute=entry_minute
                        )
                        exit_time = entry_time + timedelta(minutes=np.random.randint(5, 120))
                        
                        # Generate realistic P&L based on account characteristics
                        win_probability = base_return + day_factor + weekly_factor
                        
                        if np.random.random() < win_probability:
                            # Winning trade
                            base_profit = 30 + (trend_factor * day_offset * 5)
                            profit_loss = abs(np.random.normal(base_profit, return_volatility * 0.6))
                        else:
                            # Losing trade
                            base_loss = -25 - (trend_factor * day_offset * 2)
                            profit_loss = -abs(np.random.normal(-base_loss, return_volatility * 0.8))
                        
                        # Add account-specific adjustments
                        if account.name == "TREND_FOLLOWING":
                            # Trend following has bigger wins, bigger losses
                            profit_loss *= (1.5 if profit_loss > 0 else 1.3)
                        
                        # Simulate market impact on different days
                        if day_offset % 7 == 0:  # Monday effect
                            profit_loss *= 1.1
                        elif day_offset % 7 == 4:  # Friday effect
                            profit_loss *= 0.9
                        
                        trade = ProcessedTrade(
                            trade_id=f"{account.name}_{trade_id:08d}",
                            account_name=account.name,
                            symbol=account.symbol,
                            entry_time=entry_time,
                            exit_time=exit_time,
                            entry_price=4500.0 + np.random.normal(0, 10),
                            exit_price=4500.0 + np.random.normal(0, 10) + (profit_loss / 20),
                            quantity=1,
                            side="LONG" if np.random.random() > 0.5 else "SHORT",
                            profit_loss=profit_loss,
                            commission=2.50,
                            duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                            hour_of_day=entry_hour,
                            day_of_week=trade_date.weekday(),
                            entry_order_id=f"E_{trade_id}",
                            exit_order_id=f"X_{trade_id}"
                        )
                        
                        all_trades.append(trade)
                        trade_id += 1
            
            session.add_all(all_trades)
            
            # Update account statistics
            for account in accounts:
                account_trades = [t for t in all_trades if t.account_name == account.name]
                account.total_trades = len(account_trades)
                if account_trades:
                    account.first_trade_date = min(t.entry_time for t in account_trades)
                    account.last_trade_date = max(t.entry_time for t in account_trades)
            
            # Create time-bin analyses for advanced analytics
            time_bin_analyses = []
            
            for account in accounts:
                account_trades = [t for t in all_trades if t.account_name == account.name]
                
                # Group trades by time bins
                time_bin_groups = {}
                for trade in account_trades:
                    bin_key = (trade.hour_of_day, 0 if trade.entry_time.minute < 30 else 30)
                    if bin_key not in time_bin_groups:
                        time_bin_groups[bin_key] = []
                    time_bin_groups[bin_key].append(trade)
                
                # Create time-bin analyses for bins with sufficient data
                for (hour, minute_bin), bin_trades in time_bin_groups.items():
                    if len(bin_trades) >= 30:  # Need substantial data for advanced analytics
                        total_pnl = sum(t.profit_loss for t in bin_trades)
                        winning_trades = len([t for t in bin_trades if t.profit_loss > 0])
                        
                        # Calculate advanced metrics
                        returns = [t.profit_loss for t in bin_trades]
                        avg_return = total_pnl / len(bin_trades)
                        
                        # Calculate Sharpe ratio
                        if len(returns) > 1:
                            std_return = np.std(returns, ddof=1)
                            sharpe_ratio = avg_return / std_return if std_return > 0 else 0.0
                        else:
                            sharpe_ratio = 0.0
                        
                        # Calculate max drawdown
                        cumulative = np.cumsum(returns)
                        running_max = np.maximum.accumulate(cumulative)
                        drawdown = running_max - cumulative
                        max_drawdown = -np.max(drawdown)
                        
                        # Calculate profit factor
                        gross_profit = sum(r for r in returns if r > 0)
                        gross_loss = abs(sum(r for r in returns if r < 0))
                        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                        
                        analysis = TimeBinAnalysis(
                            account_name=account.name,
                            hour=hour,
                            minute_bin=minute_bin,
                            analysis_date=datetime.now().date(),
                            total_trades=len(bin_trades),
                            win_rate=winning_trades / len(bin_trades),
                            average_pnl=avg_return,
                            sharpe_ratio=sharpe_ratio,
                            max_drawdown=max_drawdown,
                            profit_factor=profit_factor,
                            statistical_significance=len(bin_trades) >= 50,
                            sample_size_adequate=len(bin_trades) >= 30,
                            confidence_interval_lower=avg_return - (1.96 * std_return / np.sqrt(len(bin_trades))) if len(bin_trades) > 1 else None,
                            confidence_interval_upper=avg_return + (1.96 * std_return / np.sqrt(len(bin_trades))) if len(bin_trades) > 1 else None
                        )
                        
                        session.add(analysis)
                        time_bin_analyses.append(analysis)
            
            session.commit()
        
        yield engine, SessionLocal, time_bin_analyses
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_monte_carlo_risk_simulation_workflow(self, test_database_with_analytics_data):
        """Test comprehensive Monte Carlo risk simulation."""
        engine, SessionLocal, time_bin_analyses = test_database_with_analytics_data
        
        # Initialize Monte Carlo simulator
        simulator = MonteCarloSimulator()
        
        with SessionLocal() as session:
            # Test Monte Carlo simulation for each time-bin analysis
            simulation_results = {}
            
            for analysis in time_bin_analyses[:6]:  # Test first 6 analyses
                # Get historical trade data for this time bin
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == analysis.account_name,
                    ProcessedTrade.hour_of_day == analysis.hour
                ).all()
                
                if len(trades) < 30:
                    continue
                
                # Configure simulation based on historical data
                returns = [t.profit_loss for t in trades]
                config = SimulationConfig(
                    n_scenarios=10000,
                    time_horizon_days=30,
                    confidence_levels=[0.95, 0.99, 0.999],
                    initial_capital=100000,
                    position_size=1.0,
                    include_transaction_costs=True,
                    transaction_cost_per_trade=2.50
                )
                
                # Run Monte Carlo simulation
                simulation_result = await simulator.run_monte_carlo_simulation(
                    historical_returns=returns,
                    config=config
                )
                
                assert simulation_result is not None
                assert 'risk_metrics' in simulation_result
                assert 'scenario_statistics' in simulation_result
                assert 'performance_distribution' in simulation_result
                
                risk_metrics = simulation_result['risk_metrics']
                
                # Validate VaR calculations
                assert 'var_95' in risk_metrics
                assert 'var_99' in risk_metrics
                assert 'var_999' in risk_metrics
                assert 'expected_shortfall_95' in risk_metrics
                
                # VaR should be negative (representing potential losses)
                assert risk_metrics['var_95'] <= 0
                assert risk_metrics['var_99'] <= risk_metrics['var_95']  # 99% VaR should be worse than 95%
                assert risk_metrics['var_999'] <= risk_metrics['var_99']
                
                # Expected Shortfall should be worse than VaR
                assert risk_metrics['expected_shortfall_95'] <= risk_metrics['var_95']
                
                # Validate other metrics
                assert 'probability_of_profit' in risk_metrics
                assert 'expected_return' in risk_metrics
                assert 'volatility' in risk_metrics
                
                assert 0.0 <= risk_metrics['probability_of_profit'] <= 1.0
                assert risk_metrics['volatility'] >= 0.0
                
                # Store results in database
                monte_carlo_record = MonteCarloResult(
                    time_bin_analysis_id=analysis.id,
                    simulation_date=datetime.now().date(),
                    n_scenarios=config.n_scenarios,
                    var_95=risk_metrics['var_95'],
                    var_99=risk_metrics['var_99'],
                    var_99_9=risk_metrics['var_999'],
                    expected_shortfall_95=risk_metrics['expected_shortfall_95'],
                    expected_return=risk_metrics['expected_return'],
                    probability_of_profit=risk_metrics['probability_of_profit']
                )
                
                session.add(monte_carlo_record)
                simulation_results[f"{analysis.account_name}_{analysis.hour}:{analysis.minute_bin:02d}"] = simulation_result
                
                print(f"✅ Monte Carlo simulation for {analysis.account_name} {analysis.hour}:{analysis.minute_bin:02d}:")
                print(f"  VaR 95%: ${risk_metrics['var_95']:.2f}")
                print(f"  VaR 99%: ${risk_metrics['var_99']:.2f}")
                print(f"  Expected Return: ${risk_metrics['expected_return']:.2f}")
                print(f"  Probability of Profit: {risk_metrics['probability_of_profit']:.1%}")
            
            session.commit()
            
            assert len(simulation_results) > 0, "Should complete Monte Carlo simulations"
            print(f"✅ Completed {len(simulation_results)} Monte Carlo simulations")
    
    @pytest.mark.asyncio
    async def test_walk_forward_validation_workflow(self, test_database_with_analytics_data):
        """Test comprehensive Walk-Forward validation analysis."""
        engine, SessionLocal, time_bin_analyses = test_database_with_analytics_data
        
        # Initialize Walk-Forward analyzer
        analyzer = WalkForwardAnalyzer()
        
        with SessionLocal() as session:
            validation_results = {}
            
            for analysis in time_bin_analyses[:4]:  # Test first 4 analyses
                # Get historical trades for this time bin
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == analysis.account_name,
                    ProcessedTrade.hour_of_day == analysis.hour
                ).order_by(ProcessedTrade.entry_time).all()
                
                if len(trades) < 60:  # Need sufficient data for walk-forward
                    continue
                
                # Test different validation schemes
                validation_schemes = [
                    ValidationScheme.ANCHORED,
                    ValidationScheme.ROLLING,
                    ValidationScheme.EXPANDING
                ]
                
                account_validation_results = {}
                
                for scheme in validation_schemes:
                    # Configure walk-forward analysis
                    validation_config = {
                        'in_sample_period_days': 30,
                        'out_sample_period_days': 15,
                        'step_size_days': 5,
                        'min_trades_required': 20,
                        'validation_scheme': scheme
                    }
                    
                    # Run walk-forward validation
                    validation_result = await analyzer.perform_walk_forward_validation(
                        trades=trades,
                        config=validation_config
                    )
                    
                    assert validation_result is not None
                    assert 'validation_periods' in validation_result
                    assert 'overall_statistics' in validation_result
                    assert 'stability_metrics' in validation_result
                    
                    validation_periods = validation_result['validation_periods']
                    assert len(validation_periods) > 0, "Should have validation periods"
                    
                    for period in validation_periods:
                        assert 'in_sample_start' in period
                        assert 'in_sample_end' in period
                        assert 'out_sample_start' in period
                        assert 'out_sample_end' in period
                        assert 'in_sample_performance' in period
                        assert 'out_sample_performance' in period
                        assert 'prediction_error' in period
                        
                        # Validate performance metrics
                        in_sample_perf = period['in_sample_performance']
                        out_sample_perf = period['out_sample_performance']
                        
                        assert 'avg_return' in in_sample_perf
                        assert 'win_rate' in in_sample_perf
                        assert 'sharpe_ratio' in in_sample_perf
                        
                        assert 'avg_return' in out_sample_perf
                        assert 'win_rate' in out_sample_perf
                        assert 'actual_trades' in out_sample_perf
                        
                        # Validate prediction error calculation
                        expected_error = abs(in_sample_perf['avg_return'] - out_sample_perf['avg_return'])
                        assert abs(period['prediction_error'] - expected_error) < 0.01
                    
                    # Validate overall statistics
                    overall_stats = validation_result['overall_statistics']
                    assert 'mean_prediction_error' in overall_stats
                    assert 'prediction_error_std' in overall_stats
                    assert 'hit_ratio' in overall_stats
                    assert 'stability_score' in overall_stats
                    
                    assert overall_stats['mean_prediction_error'] >= 0
                    assert overall_stats['prediction_error_std'] >= 0
                    assert 0.0 <= overall_stats['hit_ratio'] <= 1.0
                    assert 0.0 <= overall_stats['stability_score'] <= 1.0
                    
                    # Store validation results
                    for period in validation_periods:
                        walk_forward_record = WalkForwardResult(
                            time_bin_analysis_id=analysis.id,
                            validation_scheme=scheme.value,
                            in_sample_start=period['in_sample_start'].date(),
                            in_sample_end=period['in_sample_end'].date(),
                            out_sample_start=period['out_sample_start'].date(),
                            out_sample_end=period['out_sample_end'].date(),
                            predicted_performance=period['in_sample_performance']['avg_return'],
                            actual_performance=period['out_sample_performance']['avg_return'],
                            prediction_error=period['prediction_error'],
                            trades_in_out_sample=period['out_sample_performance']['actual_trades']
                        )
                        session.add(walk_forward_record)
                    
                    account_validation_results[scheme.value] = validation_result
                    
                    print(f"✅ Walk-Forward {scheme.value} for {analysis.account_name} {analysis.hour}:{analysis.minute_bin:02d}:")
                    print(f"  Periods: {len(validation_periods)}")
                    print(f"  Mean Prediction Error: {overall_stats['mean_prediction_error']:.2f}")
                    print(f"  Hit Ratio: {overall_stats['hit_ratio']:.1%}")
                    print(f"  Stability Score: {overall_stats['stability_score']:.3f}")
                
                validation_results[f"{analysis.account_name}_{analysis.hour}:{analysis.minute_bin:02d}"] = account_validation_results
            
            session.commit()
            
            assert len(validation_results) > 0, "Should complete walk-forward validations"
            print(f"✅ Completed walk-forward validation for {len(validation_results)} time bins")
    
    @pytest.mark.asyncio
    async def test_combined_monte_carlo_walkforward_analysis(self, test_database_with_analytics_data):
        """Test combined Monte Carlo and Walk-Forward analysis for comprehensive risk assessment."""
        engine, SessionLocal, time_bin_analyses = test_database_with_analytics_data
        
        # Initialize both analyzers
        monte_carlo_simulator = MonteCarloSimulator()
        walk_forward_analyzer = WalkForwardAnalyzer()
        
        with SessionLocal() as session:
            combined_results = {}
            
            for analysis in time_bin_analyses[:3]:  # Test first 3 for combined analysis
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == analysis.account_name,
                    ProcessedTrade.hour_of_day == analysis.hour
                ).order_by(ProcessedTrade.entry_time).all()
                
                if len(trades) < 60:
                    continue
                
                # Step 1: Run Walk-Forward to validate strategy consistency
                wf_config = {
                    'in_sample_period_days': 30,
                    'out_sample_period_days': 10,
                    'step_size_days': 5,
                    'min_trades_required': 15,
                    'validation_scheme': ValidationScheme.ROLLING
                }
                
                wf_result = await walk_forward_analyzer.perform_walk_forward_validation(
                    trades=trades,
                    config=wf_config
                )
                
                # Step 2: Use Walk-Forward results to inform Monte Carlo simulation
                # Get the most recent out-of-sample performance as basis for MC
                recent_periods = wf_result['validation_periods'][-3:]  # Last 3 periods
                recent_returns = []
                
                for period in recent_periods:
                    period_trades = [
                        t for t in trades 
                        if period['out_sample_start'] <= t.entry_time <= period['out_sample_end']
                    ]
                    recent_returns.extend([t.profit_loss for t in period_trades])
                
                if len(recent_returns) >= 20:  # Need sufficient recent data
                    # Configure Monte Carlo with walk-forward informed parameters
                    mc_config = SimulationConfig(
                        n_scenarios=5000,
                        time_horizon_days=20,
                        confidence_levels=[0.95, 0.99],
                        initial_capital=50000,
                        position_size=1.0,
                        include_transaction_costs=True,
                        transaction_cost_per_trade=2.50
                    )
                    
                    # Run Monte Carlo on recent validated performance
                    mc_result = await monte_carlo_simulator.run_monte_carlo_simulation(
                        historical_returns=recent_returns,
                        config=mc_config
                    )
                    
                    # Step 3: Combine results for comprehensive risk assessment
                    combined_analysis = {
                        'time_bin_info': {
                            'account': analysis.account_name,
                            'hour': analysis.hour,
                            'minute_bin': analysis.minute_bin,
                            'total_trades': analysis.total_trades
                        },
                        'walk_forward_validation': {
                            'stability_score': wf_result['overall_statistics']['stability_score'],
                            'prediction_consistency': wf_result['overall_statistics']['hit_ratio'],
                            'mean_prediction_error': wf_result['overall_statistics']['mean_prediction_error'],
                            'validation_periods': len(wf_result['validation_periods'])
                        },
                        'monte_carlo_risk': {
                            'var_95': mc_result['risk_metrics']['var_95'],
                            'var_99': mc_result['risk_metrics']['var_99'],
                            'expected_shortfall': mc_result['risk_metrics']['expected_shortfall_95'],
                            'probability_of_profit': mc_result['risk_metrics']['probability_of_profit'],
                            'expected_return': mc_result['risk_metrics']['expected_return']
                        },
                        'combined_risk_score': None,  # Will calculate
                        'recommendation': None  # Will generate
                    }
                    
                    # Step 4: Calculate combined risk score
                    # Normalize components to 0-1 scale and combine
                    stability_component = wf_result['overall_statistics']['stability_score']  # Already 0-1
                    consistency_component = wf_result['overall_statistics']['hit_ratio']  # Already 0-1
                    
                    # Normalize VaR (more negative = higher risk = lower score)
                    var_component = max(0, 1 + (mc_result['risk_metrics']['var_95'] / 500))  # Assume -500 is very bad
                    
                    # Probability of profit component
                    profit_prob_component = mc_result['risk_metrics']['probability_of_profit']
                    
                    # Combined score (weighted average)
                    combined_risk_score = (
                        stability_component * 0.3 +
                        consistency_component * 0.25 +
                        var_component * 0.25 +
                        profit_prob_component * 0.2
                    )
                    
                    combined_analysis['combined_risk_score'] = combined_risk_score
                    
                    # Step 5: Generate risk-based recommendation
                    if combined_risk_score > 0.7 and mc_result['risk_metrics']['probability_of_profit'] > 0.6:
                        recommendation = "STRONG_BUY"
                        risk_level = "LOW"
                    elif combined_risk_score > 0.5 and mc_result['risk_metrics']['probability_of_profit'] > 0.55:
                        recommendation = "BUY"
                        risk_level = "MEDIUM"
                    elif combined_risk_score > 0.3:
                        recommendation = "HOLD"
                        risk_level = "MEDIUM_HIGH"
                    else:
                        recommendation = "AVOID"
                        risk_level = "HIGH"
                    
                    combined_analysis['recommendation'] = {
                        'action': recommendation,
                        'risk_level': risk_level,
                        'confidence': combined_risk_score,
                        'reasoning': f"Based on {len(wf_result['validation_periods'])} validation periods and {mc_config.n_scenarios} Monte Carlo scenarios"
                    }
                    
                    combined_results[f"{analysis.account_name}_{analysis.hour}:{analysis.minute_bin:02d}"] = combined_analysis
                    
                    print(f"✅ Combined Analysis for {analysis.account_name} {analysis.hour}:{analysis.minute_bin:02d}:")
                    print(f"  Combined Risk Score: {combined_risk_score:.3f}")
                    print(f"  Recommendation: {recommendation} ({risk_level} risk)")
                    print(f"  WF Stability: {stability_component:.3f}")
                    print(f"  MC VaR 95%: ${mc_result['risk_metrics']['var_95']:.2f}")
                    print(f"  Profit Probability: {profit_prob_component:.1%}")
            
            assert len(combined_results) > 0, "Should complete combined analyses"
            print(f"✅ Completed {len(combined_results)} combined Monte Carlo + Walk-Forward analyses")
            
            return combined_results
    
    @pytest.mark.asyncio
    async def test_advanced_statistical_validation(self, test_database_with_analytics_data):
        """Test advanced statistical validation combining multiple methodologies."""
        engine, SessionLocal, time_bin_analyses = test_database_with_analytics_data
        
        # Initialize performance metrics calculator
        metrics_calculator = PerformanceMetricsCalculator()
        
        with SessionLocal() as session:
            validation_results = {}
            
            for analysis in time_bin_analyses[:5]:  # Test first 5
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == analysis.account_name,
                    ProcessedTrade.hour_of_day == analysis.hour
                ).order_by(ProcessedTrade.entry_time).all()
                
                if len(trades) < 40:
                    continue
                
                # Step 1: Calculate comprehensive performance metrics
                comprehensive_metrics = await metrics_calculator.calculate_comprehensive_metrics(trades)
                
                # Step 2: Statistical significance testing
                returns = [t.profit_loss for t in trades]
                
                # T-test for mean return significantly different from zero
                from scipy import stats
                t_stat, p_value_ttest = stats.ttest_1samp(returns, 0)
                
                # Jarque-Bera test for normality
                jb_stat, p_value_normality = stats.jarque_bera(returns)
                
                # Kolmogorov-Smirnov test against normal distribution
                ks_stat, p_value_ks = stats.kstest(returns, 'norm', args=(np.mean(returns), np.std(returns)))
                
                # Step 3: Bootstrap confidence intervals
                n_bootstrap = 1000
                bootstrap_means = []
                bootstrap_sharpes = []
                
                for _ in range(n_bootstrap):
                    bootstrap_sample = np.random.choice(returns, size=len(returns), replace=True)
                    bootstrap_means.append(np.mean(bootstrap_sample))
                    if np.std(bootstrap_sample) > 0:
                        bootstrap_sharpes.append(np.mean(bootstrap_sample) / np.std(bootstrap_sample))
                
                # Calculate confidence intervals
                mean_ci_lower = np.percentile(bootstrap_means, 2.5)
                mean_ci_upper = np.percentile(bootstrap_means, 97.5)
                
                if bootstrap_sharpes:
                    sharpe_ci_lower = np.percentile(bootstrap_sharpes, 2.5)
                    sharpe_ci_upper = np.percentile(bootstrap_sharpes, 97.5)
                else:
                    sharpe_ci_lower = sharpe_ci_upper = 0
                
                # Step 4: Stability analysis over time
                # Divide trades into terciles and compare performance
                n_trades = len(trades)
                tercile_size = n_trades // 3
                
                tercile_1_returns = returns[:tercile_size]
                tercile_2_returns = returns[tercile_size:2*tercile_size]
                tercile_3_returns = returns[2*tercile_size:]
                
                tercile_means = [
                    np.mean(tercile_1_returns),
                    np.mean(tercile_2_returns), 
                    np.mean(tercile_3_returns)
                ]
                
                # ANOVA test for stability across terciles
                f_stat, p_value_anova = stats.f_oneway(tercile_1_returns, tercile_2_returns, tercile_3_returns)
                
                # Step 5: Risk-adjusted performance metrics
                sortino_ratio = comprehensive_metrics.get('sortino_ratio', 0)
                calmar_ratio = comprehensive_metrics.get('calmar_ratio', 0)
                omega_ratio = comprehensive_metrics.get('omega_ratio', 0)
                
                # Step 6: Compile advanced validation results
                advanced_validation = {
                    'basic_metrics': {
                        'total_trades': len(trades),
                        'win_rate': analysis.win_rate,
                        'average_pnl': analysis.average_pnl,
                        'sharpe_ratio': analysis.sharpe_ratio,
                        'max_drawdown': analysis.max_drawdown
                    },
                    'statistical_tests': {
                        'mean_significance': {
                            't_statistic': float(t_stat),
                            'p_value': float(p_value_ttest),
                            'is_significant': p_value_ttest < 0.05
                        },
                        'normality_tests': {
                            'jarque_bera_p': float(p_value_normality),
                            'ks_test_p': float(p_value_ks),
                            'is_normal': p_value_normality > 0.05 and p_value_ks > 0.05
                        },
                        'stability_test': {
                            'anova_f_stat': float(f_stat),
                            'anova_p_value': float(p_value_anova),
                            'is_stable': p_value_anova > 0.05
                        }
                    },
                    'confidence_intervals': {
                        'mean_return_95_ci': [float(mean_ci_lower), float(mean_ci_upper)],
                        'sharpe_ratio_95_ci': [float(sharpe_ci_lower), float(sharpe_ci_upper)]
                    },
                    'temporal_analysis': {
                        'tercile_means': [float(x) for x in tercile_means],
                        'performance_trend': 'improving' if tercile_means[2] > tercile_means[0] else 'declining' if tercile_means[2] < tercile_means[0] else 'stable'
                    },
                    'risk_adjusted_metrics': {
                        'sortino_ratio': sortino_ratio,
                        'calmar_ratio': calmar_ratio,
                        'omega_ratio': omega_ratio
                    },
                    'overall_validation_score': None  # Will calculate
                }
                
                # Step 7: Calculate overall validation score
                score_components = []
                
                # Significance component
                score_components.append(1.0 if advanced_validation['statistical_tests']['mean_significance']['is_significant'] else 0.3)
                
                # Stability component
                score_components.append(1.0 if advanced_validation['statistical_tests']['stability_test']['is_stable'] else 0.5)
                
                # Sample size component
                sample_score = min(1.0, len(trades) / 100.0)  # Normalize to 100 trades
                score_components.append(sample_score)
                
                # Risk-adjusted performance component
                sharpe_score = max(0, min(1.0, (analysis.sharpe_ratio + 2) / 4))  # Normalize Sharpe from -2 to 2 into 0-1
                score_components.append(sharpe_score)
                
                # Overall validation score
                overall_score = np.mean(score_components)
                advanced_validation['overall_validation_score'] = overall_score
                
                validation_results[f"{analysis.account_name}_{analysis.hour}:{analysis.minute_bin:02d}"] = advanced_validation
                
                print(f"✅ Advanced Validation for {analysis.account_name} {analysis.hour}:{analysis.minute_bin:02d}:")
                print(f"  Overall Score: {overall_score:.3f}")
                print(f"  Mean Significant: {advanced_validation['statistical_tests']['mean_significance']['is_significant']}")
                print(f"  Temporally Stable: {advanced_validation['statistical_tests']['stability_test']['is_stable']}")
                print(f"  Performance Trend: {advanced_validation['temporal_analysis']['performance_trend']}")
                print(f"  Sharpe CI: [{sharpe_ci_lower:.3f}, {sharpe_ci_upper:.3f}]")
            
            assert len(validation_results) > 0, "Should complete advanced validations"
            print(f"✅ Completed advanced statistical validation for {len(validation_results)} time bins")
            
            return validation_results
    
    @pytest.mark.asyncio
    async def test_integrated_recommendation_generation(self, test_database_with_analytics_data):
        """Test integrated recommendation generation using all analytics components."""
        engine, SessionLocal, time_bin_analyses = test_database_with_analytics_data
        
        # Run combined analysis first
        combined_results = await self.test_combined_monte_carlo_walkforward_analysis(test_database_with_analytics_data)
        advanced_validation = await self.test_advanced_statistical_validation(test_database_with_analytics_data)
        
        # Initialize recommendation service
        recommendation_service = RecommendationService(SessionLocal())
        
        integrated_recommendations = {}
        
        # Generate integrated recommendations combining all analytics
        for time_bin_key in combined_results.keys():
            if time_bin_key in advanced_validation:
                combined_data = combined_results[time_bin_key]
                validation_data = advanced_validation[time_bin_key]
                
                # Create comprehensive input for recommendation
                analytics_input = {
                    'time_bin_info': combined_data['time_bin_info'],
                    'performance_metrics': validation_data['basic_metrics'],
                    'statistical_validation': validation_data['statistical_tests'],
                    'risk_metrics': combined_data['monte_carlo_risk'],
                    'validation_stability': combined_data['walk_forward_validation'],
                    'confidence_intervals': validation_data['confidence_intervals'],
                    'risk_adjusted_metrics': validation_data['risk_adjusted_metrics']
                }
                
                # Generate comprehensive recommendation
                recommendation = await recommendation_service.generate_comprehensive_recommendation(
                    time_bin_key=time_bin_key,
                    analytics_data=analytics_input
                )
                
                assert recommendation is not None
                assert 'recommendation_type' in recommendation
                assert 'confidence_score' in recommendation
                assert 'risk_assessment' in recommendation
                assert 'supporting_evidence' in recommendation
                assert 'risk_warnings' in recommendation
                
                # Validate recommendation structure
                assert recommendation['recommendation_type'] in [
                    'STRONG_BUY', 'BUY', 'HOLD', 'AVOID', 'STRONG_AVOID'
                ]
                assert 0.0 <= recommendation['confidence_score'] <= 1.0
                assert recommendation['risk_assessment'] in [
                    'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'
                ]
                
                # Supporting evidence should be comprehensive
                evidence = recommendation['supporting_evidence']
                assert 'statistical_significance' in evidence
                assert 'risk_metrics' in evidence
                assert 'performance_consistency' in evidence
                assert 'sample_adequacy' in evidence
                
                integrated_recommendations[time_bin_key] = recommendation
                
                print(f"✅ Integrated Recommendation for {time_bin_key}:")
                print(f"  Recommendation: {recommendation['recommendation_type']}")
                print(f"  Confidence: {recommendation['confidence_score']:.3f}")
                print(f"  Risk Level: {recommendation['risk_assessment']}")
                print(f"  Key Evidence: {len(evidence)} factors analyzed")
        
        assert len(integrated_recommendations) > 0, "Should generate integrated recommendations"
        print(f"✅ Generated {len(integrated_recommendations)} integrated recommendations")
        
        return integrated_recommendations
    
    @pytest.mark.asyncio
    async def test_advanced_analytics_performance_under_load(self, test_database_with_analytics_data):
        """Test performance of advanced analytics workflow under concurrent load."""
        engine, SessionLocal, time_bin_analyses = test_database_with_analytics_data
        
        # Test concurrent Monte Carlo simulations
        simulator = MonteCarloSimulator()
        
        async def run_concurrent_monte_carlo(analysis) -> Dict[str, Any]:
            """Run Monte Carlo simulation concurrently."""
            start_time = datetime.now()
            
            with SessionLocal() as session:
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == analysis.account_name,
                    ProcessedTrade.hour_of_day == analysis.hour
                ).all()
                
                if len(trades) < 30:
                    return {'analysis_id': analysis.id, 'status': 'insufficient_data', 'duration': 0}
                
                returns = [t.profit_loss for t in trades]
                config = SimulationConfig(
                    n_scenarios=5000,  # Reduced for performance test
                    time_horizon_days=20,
                    confidence_levels=[0.95, 0.99],
                    initial_capital=100000
                )
                
                try:
                    result = await simulator.run_monte_carlo_simulation(returns, config)
                    duration = (datetime.now() - start_time).total_seconds()
                    
                    return {
                        'analysis_id': analysis.id,
                        'status': 'completed',
                        'duration': duration,
                        'var_95': result['risk_metrics']['var_95'],
                        'scenarios': config.n_scenarios
                    }
                except Exception as e:
                    return {
                        'analysis_id': analysis.id,
                        'status': 'error',
                        'duration': (datetime.now() - start_time).total_seconds(),
                        'error': str(e)
                    }
        
        # Run concurrent simulations
        start_time = datetime.now()
        tasks = [run_concurrent_monte_carlo(analysis) for analysis in time_bin_analyses[:8]]  # Test with 8 concurrent
        results = await asyncio.gather(*tasks)
        total_duration = (datetime.now() - start_time).total_seconds()
        
        # Validate performance
        completed_results = [r for r in results if r['status'] == 'completed']
        assert len(completed_results) > 0, "Should complete some simulations"
        assert total_duration < 30.0, f"Concurrent analytics too slow: {total_duration:.2f}s"
        
        avg_individual_duration = sum(r['duration'] for r in completed_results) / len(completed_results)
        assert avg_individual_duration < 10.0, f"Individual simulations too slow: {avg_individual_duration:.2f}s"
        
        print(f"✅ Concurrent Analytics Performance:")
        print(f"  Total time: {total_duration:.2f}s for {len(tasks)} concurrent simulations")
        print(f"  Completed: {len(completed_results)}/{len(tasks)}")
        print(f"  Average individual time: {avg_individual_duration:.2f}s")
        print(f"  Scenarios per simulation: 5000")
        
        return results


class TestAdvancedAnalyticsIntegration:
    """Integration tests for advanced analytics with other system components."""
    
    @pytest.mark.asyncio
    async def test_analytics_integration_with_real_time_monitoring(self):
        """Test integration of advanced analytics with real-time monitoring systems."""
        # Mock real-time trade stream
        class MockTradeStream:
            def __init__(self):
                self.subscribers = []
                self.active = False
            
            def subscribe(self, callback):
                self.subscribers.append(callback)
            
            async def start_streaming(self):
                self.active = True
                trade_id = 1
                
                while self.active and trade_id <= 20:  # Stream 20 trades
                    # Generate realistic trade
                    trade = {
                        'trade_id': f"RT_{trade_id:06d}",
                        'account_name': 'REALTIME_TEST',
                        'profit_loss': np.random.normal(25, 40),
                        'timestamp': datetime.now(),
                        'symbol': 'ES'
                    }
                    
                    # Notify subscribers
                    for callback in self.subscribers:
                        await callback(trade)
                    
                    trade_id += 1
                    await asyncio.sleep(0.1)  # 10 trades per second
            
            def stop_streaming(self):
                self.active = False
        
        # Mock analytics processor
        class RealTimeAnalyticsProcessor:
            def __init__(self):
                self.trade_buffer = []
                self.analytics_cache = {}
            
            async def process_trade(self, trade):
                self.trade_buffer.append(trade)
                
                # Trigger analytics every 10 trades
                if len(self.trade_buffer) >= 10:
                    await self._run_incremental_analytics()
            
            async def _run_incremental_analytics(self):
                returns = [t['profit_loss'] for t in self.trade_buffer]
                
                # Quick risk calculation
                if len(returns) >= 10:
                    var_95 = np.percentile(returns, 5)  # Simple VaR calculation
                    current_sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                    
                    self.analytics_cache['last_update'] = datetime.now()
                    self.analytics_cache['rolling_var_95'] = var_95
                    self.analytics_cache['rolling_sharpe'] = current_sharpe
                    self.analytics_cache['sample_size'] = len(returns)
                
                # Keep only last 50 trades for rolling calculation
                if len(self.trade_buffer) > 50:
                    self.trade_buffer = self.trade_buffer[-50:]
        
        # Test real-time integration
        stream = MockTradeStream()
        processor = RealTimeAnalyticsProcessor()
        
        # Subscribe processor to stream
        stream.subscribe(processor.process_trade)
        
        # Start streaming and processing
        start_time = datetime.now()
        await stream.start_streaming()
        stream.stop_streaming()
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Validate real-time processing
        assert len(processor.trade_buffer) > 0, "Should process trades"
        assert 'last_update' in processor.analytics_cache, "Should run analytics"
        assert processing_time < 5.0, f"Real-time processing too slow: {processing_time:.2f}s"
        
        # Validate analytics results
        assert 'rolling_var_95' in processor.analytics_cache
        assert 'rolling_sharpe' in processor.analytics_cache
        assert processor.analytics_cache['sample_size'] >= 10
        
        print(f"✅ Real-time Analytics Integration:")
        print(f"  Processing time: {processing_time:.2f}s")
        print(f"  Trades processed: {len(processor.trade_buffer)}")
        print(f"  Rolling VaR 95%: ${processor.analytics_cache['rolling_var_95']:.2f}")
        print(f"  Rolling Sharpe: {processor.analytics_cache['rolling_sharpe']:.3f}")
    
    @pytest.mark.asyncio
    async def test_analytics_with_alert_system(self):
        """Test integration of analytics with automated alert system."""
        # Mock alert system
        class AlertSystem:
            def __init__(self):
                self.alerts = []
            
            async def trigger_alert(self, alert_type: str, message: str, severity: str, data: Dict[str, Any]):
                alert = {
                    'timestamp': datetime.now(),
                    'type': alert_type,
                    'message': message,
                    'severity': severity,
                    'data': data
                }
                self.alerts.append(alert)
                print(f"🚨 ALERT [{severity}]: {message}")
        
        # Mock analytics monitor
        class AnalyticsMonitor:
            def __init__(self, alert_system: AlertSystem):
                self.alert_system = alert_system
                self.risk_thresholds = {
                    'var_95_threshold': -200,  # Alert if VaR worse than -$200
                    'sharpe_threshold': -0.5,  # Alert if Sharpe below -0.5
                    'drawdown_threshold': -500  # Alert if drawdown exceeds $500
                }
            
            async def evaluate_risk_metrics(self, metrics: Dict[str, float]):
                # Check VaR threshold
                if metrics.get('var_95', 0) < self.risk_thresholds['var_95_threshold']:
                    await self.alert_system.trigger_alert(
                        'RISK_EXCEEDED',
                        f"VaR 95% exceeded threshold: ${metrics['var_95']:.2f}",
                        'HIGH',
                        {'metric': 'var_95', 'value': metrics['var_95'], 'threshold': self.risk_thresholds['var_95_threshold']}
                    )
                
                # Check Sharpe ratio
                if metrics.get('sharpe_ratio', 0) < self.risk_thresholds['sharpe_threshold']:
                    await self.alert_system.trigger_alert(
                        'PERFORMANCE_DEGRADATION',
                        f"Sharpe ratio below threshold: {metrics['sharpe_ratio']:.3f}",
                        'MEDIUM',
                        {'metric': 'sharpe_ratio', 'value': metrics['sharpe_ratio'], 'threshold': self.risk_thresholds['sharpe_threshold']}
                    )
                
                # Check drawdown
                if metrics.get('max_drawdown', 0) < self.risk_thresholds['drawdown_threshold']:
                    await self.alert_system.trigger_alert(
                        'DRAWDOWN_EXCEEDED',
                        f"Maximum drawdown exceeded: ${metrics['max_drawdown']:.2f}",
                        'HIGH',
                        {'metric': 'max_drawdown', 'value': metrics['max_drawdown'], 'threshold': self.risk_thresholds['drawdown_threshold']}
                    )
        
        # Test alert integration
        alert_system = AlertSystem()
        monitor = AnalyticsMonitor(alert_system)
        
        # Test scenarios that should trigger alerts
        test_scenarios = [
            {
                'name': 'High Risk VaR',
                'metrics': {'var_95': -350, 'sharpe_ratio': 0.8, 'max_drawdown': -100},
                'expected_alerts': 1
            },
            {
                'name': 'Poor Performance',
                'metrics': {'var_95': -100, 'sharpe_ratio': -0.8, 'max_drawdown': -200},
                'expected_alerts': 1
            },
            {
                'name': 'Multiple Issues',
                'metrics': {'var_95': -400, 'sharpe_ratio': -1.2, 'max_drawdown': -600},
                'expected_alerts': 3
            },
            {
                'name': 'Good Performance',
                'metrics': {'var_95': -50, 'sharpe_ratio': 1.5, 'max_drawdown': -80},
                'expected_alerts': 0
            }
        ]
        
        total_alerts_generated = 0
        
        for scenario in test_scenarios:
            initial_alert_count = len(alert_system.alerts)
            
            await monitor.evaluate_risk_metrics(scenario['metrics'])
            
            alerts_generated = len(alert_system.alerts) - initial_alert_count
            total_alerts_generated += alerts_generated
            
            assert alerts_generated == scenario['expected_alerts'], \
                f"Scenario '{scenario['name']}' expected {scenario['expected_alerts']} alerts, got {alerts_generated}"
            
            print(f"✅ Scenario '{scenario['name']}': {alerts_generated} alerts generated as expected")
        
        # Validate alert quality
        for alert in alert_system.alerts:
            assert 'timestamp' in alert
            assert 'type' in alert
            assert 'severity' in alert in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            assert 'data' in alert
            assert len(alert['message']) > 10  # Should have descriptive messages
        
        print(f"✅ Alert System Integration: {total_alerts_generated} total alerts generated across all scenarios")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])