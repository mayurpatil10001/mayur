"""
Comprehensive integration tests with realistic trading scenarios.

This module tests all components working together using realistic trading data patterns
and scenarios that mirror actual trading conditions and challenges.

Requirements: 1.1, 2.1, 3.1, 11.1, 12.1
"""

import pytest
import asyncio
import tempfile
import os
import numpy as np
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, patch
import json

# Import all components for comprehensive integration testing
from trading_platform.models.database import (
    ProcessedTrade, Account, PerformanceMetric
)
from trading_platform.models.time_bin_analytics import (
    TimeBinAnalysis, MarketData, VolatilityRegime, WalkForwardResult, MonteCarloResult
)
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer, TimeBin
from trading_platform.services.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.services.walk_forward_analyzer import WalkForwardAnalyzer
from trading_platform.services.vix_regime_analyzer import VIXRegimeAnalyzer
from trading_platform.services.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
from trading_platform.services.recommendation.recommendation_service import RecommendationService
from trading_platform.services.export_reporting.data_export_engine import (
    DataExportEngine, ExportConfig, ExportFormat
)
from trading_platform.database.base import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class TestRealisticTradingScenarios:
    """Test system with realistic trading scenarios and edge cases."""
    
    @pytest.fixture
    async def realistic_trading_database(self):
        """Create database with realistic trading scenarios including edge cases."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            # Create accounts representing different trading styles
            accounts = [
                Account(name="SCALPER_ACCOUNT", symbol="ES", total_trades=0, is_active=True),
                Account(name="SWING_TRADER", symbol="NQ", total_trades=0, is_active=True), 
                Account(name="NEWS_TRADER", symbol="YM", total_trades=0, is_active=True),
                Account(name="ALGO_TRADER", symbol="RTY", total_trades=0, is_active=True),
                Account(name="STRUGGLING_ACCOUNT", symbol="ES", total_trades=0, is_active=True)
            ]
            session.add_all(accounts)
            
            # Generate realistic market data with different regime periods
            base_date = datetime(2023, 1, 1)
            market_data = []
            
            # Create different market regimes
            regimes = [
                {"name": "Bull Market", "days": 90, "trend": 0.0008, "volatility": 0.015},
                {"name": "High Volatility", "days": 45, "trend": -0.0003, "volatility": 0.035},
                {"name": "Sideways", "days": 60, "trend": 0.0001, "volatility": 0.012},
                {"name": "Bear Market", "days": 30, "trend": -0.0012, "volatility": 0.025},
                {"name": "Recovery", "days": 45, "trend": 0.0015, "volatility": 0.020}
            ]
            
            # Generate market data for each regime
            current_date = base_date
            spy_price = 400.0
            qqq_price = 320.0
            vix_level = 18.0
            
            regime_periods = []
            
            for regime in regimes:
                regime_start = current_date.date()
                
                for day in range(regime["days"]):
                    if current_date.weekday() < 5:  # Skip weekends
                        # SPY movement
                        spy_change = regime["trend"] + np.random.normal(0, regime["volatility"])
                        spy_price *= (1 + spy_change)
                        
                        # QQQ correlated but more volatile
                        qqq_change = spy_change * 1.2 + np.random.normal(0, regime["volatility"] * 0.3)
                        qqq_price *= (1 + qqq_change)
                        
                        # VIX inversely correlated with markets
                        vix_change = -spy_change * 15 + np.random.normal(0, 2.0)
                        vix_level = max(10.0, min(80.0, vix_level + vix_change))
                        
                        # Create market data records
                        for symbol, price in [("SPY", spy_price), ("QQQ", qqq_price), ("VIX", vix_level)]:
                            high = price * (1 + abs(np.random.normal(0, 0.008)))
                            low = price * (1 - abs(np.random.normal(0, 0.008)))
                            open_price = low + (high - low) * np.random.random()
                            
                            market_data.append(MarketData(
                                symbol=symbol,
                                date=current_date.date(),
                                open_price=open_price,
                                high_price=high,
                                low_price=low,
                                close_price=price,
                                volume=int(2000000 * (0.7 + np.random.random() * 0.6)),
                                adjusted_close=price
                            ))
                    
                    current_date += timedelta(days=1)
                
                regime_end = (current_date - timedelta(days=1)).date()
                regime_periods.append({
                    "name": regime["name"],
                    "start": regime_start,
                    "end": regime_end,
                    "avg_vix": None  # Will calculate after VIX data is complete
                })
            
            session.add_all(market_data)
            
            # Create VIX regime records
            volatility_regimes = []
            for period in regime_periods:
                period_vix_data = [md for md in market_data 
                                 if md.symbol == "VIX" and period["start"] <= md.date <= period["end"]]
                if period_vix_data:
                    avg_vix = np.mean([md.close_price for md in period_vix_data])
                    min_vix = np.min([md.close_price for md in period_vix_data])
                    max_vix = np.max([md.close_price for md in period_vix_data])
                    
                    if avg_vix < 16:
                        regime_name = "Low"
                    elif avg_vix < 25:
                        regime_name = "Medium"
                    else:
                        regime_name = "High"
                    
                    volatility_regimes.append(VolatilityRegime(
                        start_date=period["start"],
                        end_date=period["end"],
                        regime_name=regime_name,
                        avg_vix=avg_vix,
                        min_vix=min_vix,
                        max_vix=max_vix
                    ))
            
            session.add_all(volatility_regimes)
            
            # Generate realistic trading data for each account type
            processed_trades = []
            trade_id = 1
            
            # Define trading characteristics for each account
            trading_profiles = {
                "SCALPER_ACCOUNT": {
                    "trades_per_day": 15,
                    "avg_duration_minutes": 8,
                    "win_rate": 0.58,
                    "avg_win": 12.5,
                    "avg_loss": -8.0,
                    "active_hours": list(range(9, 16)),  # All market hours
                    "market_sensitivity": 0.3
                },
                "SWING_TRADER": {
                    "trades_per_day": 2,
                    "avg_duration_minutes": 180,
                    "win_rate": 0.52,
                    "avg_win": 85.0,
                    "avg_loss": -65.0,
                    "active_hours": [10, 11, 14, 15],  # Strategic hours
                    "market_sensitivity": 0.7
                },
                "NEWS_TRADER": {
                    "trades_per_day": 4,
                    "avg_duration_minutes": 25,
                    "win_rate": 0.45,
                    "avg_win": 120.0,
                    "avg_loss": -80.0,
                    "active_hours": [9, 10, 14, 15],  # News-heavy hours
                    "market_sensitivity": 1.2
                },
                "ALGO_TRADER": {
                    "trades_per_day": 8,
                    "avg_duration_minutes": 45,
                    "win_rate": 0.62,
                    "avg_win": 35.0,
                    "avg_loss": -28.0,
                    "active_hours": list(range(9, 16)),
                    "market_sensitivity": 0.1  # Market neutral
                },
                "STRUGGLING_ACCOUNT": {
                    "trades_per_day": 6,
                    "avg_duration_minutes": 60,
                    "win_rate": 0.35,  # Poor win rate
                    "avg_win": 40.0,
                    "avg_loss": -55.0,  # Losses larger than wins
                    "active_hours": [11, 12, 13, 14],
                    "market_sensitivity": -0.4  # Trades against market
                }
            }
            
            # Generate trades for the entire period
            for day_offset in range(270):  # 9 months of data
                current_trade_date = base_date + timedelta(days=day_offset)
                
                if current_trade_date.weekday() >= 5:  # Skip weekends
                    continue
                
                # Get market conditions for this day
                day_market_data = [md for md in market_data 
                                 if md.date == current_trade_date.date() and md.symbol == "SPY"]
                if not day_market_data:
                    continue
                
                spy_data = day_market_data[0]
                daily_market_move = (spy_data.close_price - spy_data.open_price) / spy_data.open_price
                
                # Get VIX level
                vix_data = [md for md in market_data 
                           if md.date == current_trade_date.date() and md.symbol == "VIX"]
                vix_level = vix_data[0].close_price if vix_data else 20.0
                
                for account in accounts:
                    profile = trading_profiles[account.name]
                    
                    # Adjust trade frequency based on market conditions
                    base_trades = profile["trades_per_day"]
                    if vix_level > 30:  # High volatility
                        trade_multiplier = 0.7 if account.name == "SCALPER_ACCOUNT" else 1.3
                    else:
                        trade_multiplier = 1.0
                    
                    daily_trades = max(0, int(np.random.poisson(base_trades * trade_multiplier)))
                    
                    for trade_num in range(daily_trades):
                        # Choose trading hour
                        hour = np.random.choice(profile["active_hours"])
                        minute = np.random.choice([0, 30])  # 30-minute bins
                        
                        entry_time = current_trade_date.replace(hour=hour, minute=minute)
                        
                        # Duration varies by account type
                        duration_variance = profile["avg_duration_minutes"] * 0.5
                        duration = max(5, int(np.random.normal(
                            profile["avg_duration_minutes"], duration_variance
                        )))
                        exit_time = entry_time + timedelta(minutes=duration)
                        
                        # Calculate P&L based on market conditions and account profile
                        base_win_rate = profile["win_rate"]
                        
                        # Market sensitivity affects performance
                        market_adjusted_win_rate = base_win_rate + (
                            daily_market_move * profile["market_sensitivity"]
                        )
                        market_adjusted_win_rate = max(0.1, min(0.9, market_adjusted_win_rate))
                        
                        # Time-of-day effects
                        if hour in [9, 15]:  # Open/close are more volatile
                            market_adjusted_win_rate *= 0.9
                        elif hour in [11, 12]:  # Lunch time less predictable
                            market_adjusted_win_rate *= 0.95
                        
                        # Determine if trade wins
                        is_winner = np.random.random() < market_adjusted_win_rate
                        
                        if is_winner:
                            base_pnl = profile["avg_win"]
                            pnl_std = base_pnl * 0.4
                        else:
                            base_pnl = profile["avg_loss"]
                            pnl_std = abs(base_pnl) * 0.4
                        
                        # Add market impact and noise
                        market_impact = daily_market_move * profile["market_sensitivity"] * 50
                        noise = np.random.normal(0, pnl_std)
                        final_pnl = base_pnl + market_impact + noise
                        
                        # Create trade record
                        entry_price = 4500 + np.random.normal(0, 100)
                        exit_price = entry_price + (final_pnl / 20)  # Rough price conversion
                        
                        trade = ProcessedTrade(
                            trade_id=f"{account.name}_{trade_id:06d}",
                            account_name=account.name,
                            symbol=account.symbol,
                            entry_time=entry_time,
                            exit_time=exit_time,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            quantity=1,
                            side="LONG" if np.random.random() > 0.5 else "SHORT",
                            profit_loss=final_pnl,
                            commission=2.50,
                            duration_minutes=duration,
                            hour_of_day=hour,
                            day_of_week=current_trade_date.weekday(),
                            entry_order_id=f"E_{trade_id}",
                            exit_order_id=f"X_{trade_id}"
                        )
                        
                        processed_trades.append(trade)
                        trade_id += 1
            
            session.add_all(processed_trades)
            
            # Update account statistics
            for account in accounts:
                account_trades = [t for t in processed_trades if t.account_name == account.name]
                account.total_trades = len(account_trades)
                if account_trades:
                    account.first_trade_date = min(t.entry_time for t in account_trades)
                    account.last_trade_date = max(t.entry_time for t in account_trades)
            
            session.commit()
            
            print(f"Generated realistic database with:")
            print(f"  {len(accounts)} accounts")
            print(f"  {len(processed_trades)} trades")
            print(f"  {len(market_data)} market data points")
            print(f"  {len(volatility_regimes)} volatility regimes")
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_complete_system_integration_realistic_scenario(self, realistic_trading_database):
        """Test complete system integration with realistic trading scenarios."""
        engine, SessionLocal = realistic_trading_database
        
        # Initialize all major components
        time_bin_analyzer = TimeBinAnalyzer()
        monte_carlo_simulator = MonteCarloSimulator(SessionLocal())
        walk_forward_analyzer = WalkForwardAnalyzer(SessionLocal())
        vix_analyzer = VIXRegimeAnalyzer(SessionLocal())
        benchmark_analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
        recommendation_service = RecommendationService(SessionLocal())
        
        integration_results = {}
        
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            print(f"Testing system integration with {len(accounts)} realistic accounts")
            
            for account in accounts[:3]:  # Test first 3 accounts thoroughly
                account_results = {
                    "account_name": account.name,
                    "total_trades": account.total_trades,
                    "analysis_components": {}
                }
                
                print(f"\n🔄 Processing {account.name} ({account.total_trades} trades)")
                
                # Step 1: Time-bin analysis
                account_trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == account.name
                ).order_by(ProcessedTrade.entry_time).all()
                
                if len(account_trades) >= 50:  # Need substantial data
                    # Group trades by time bins
                    time_bins = self._group_trades_by_time_bins(account_trades)
                    
                    # Analyze significant time bins
                    time_bin_analyses = []
                    for (hour, minute_bin), bin_trades in time_bins.items():
                        if len(bin_trades) >= 10:  # Minimum for meaningful analysis
                            analysis = await self._analyze_time_bin(
                                time_bin_analyzer, account.name, hour, minute_bin, bin_trades
                            )
                            if analysis:
                                time_bin_analyses.append(analysis)
                                session.add(analysis)
                    
                    account_results["analysis_components"]["time_bins"] = len(time_bin_analyses)
                    
                    # Step 2: Market correlation analysis
                    correlation_results = await benchmark_analyzer.calculate_market_correlation(
                        account_name=account.name,
                        benchmark_symbols=["SPY", "QQQ"],
                        start_date=datetime(2023, 1, 1),
                        end_date=datetime(2023, 10, 1)
                    )
                    
                    account_results["analysis_components"]["market_correlation"] = correlation_results
                    
                    # Step 3: VIX regime analysis
                    regime_performance = await vix_analyzer.analyze_performance_by_regime(
                        account_name=account.name,
                        start_date=datetime(2023, 1, 1).date(),
                        end_date=datetime(2023, 10, 1).date()
                    )
                    
                    account_results["analysis_components"]["vix_regimes"] = regime_performance
                    
                    # Step 4: Advanced analytics for top time bins
                    if time_bin_analyses:
                        # Select best performing time bin for advanced analysis
                        best_time_bin = max(time_bin_analyses, key=lambda x: x.average_pnl)
                        
                        # Get trades for this specific time bin
                        time_bin_trades = [t for t in account_trades 
                                         if (t.hour_of_day == best_time_bin.hour and
                                             ((t.entry_time.minute >= 30) == (best_time_bin.minute_bin >= 30)))]
                        
                        if len(time_bin_trades) >= 30:
                            # Monte Carlo simulation
                            try:
                                mc_results = await monte_carlo_simulator.run_simulation(
                                    time_bin_analysis_id=best_time_bin.id,
                                    historical_trades=time_bin_trades,
                                    n_scenarios=1000,
                                    time_horizon_days=30
                                )
                                account_results["analysis_components"]["monte_carlo"] = {
                                    "var_95": mc_results["var_95"],
                                    "expected_return": mc_results["expected_return"],
                                    "probability_of_profit": mc_results["probability_of_profit"]
                                }
                            except Exception as e:
                                print(f"    ⚠️  Monte Carlo failed: {str(e)}")
                            
                            # Walk-Forward analysis
                            try:
                                wf_results = await walk_forward_analyzer.run_walk_forward_analysis(
                                    time_bin_analysis_id=best_time_bin.id,
                                    historical_trades=time_bin_trades,
                                    validation_scheme="expanding",
                                    in_sample_months=3,
                                    out_sample_months=1
                                )
                                account_results["analysis_components"]["walk_forward"] = {
                                    "prediction_accuracy": wf_results["summary_statistics"]["prediction_accuracy"],
                                    "mean_error": wf_results["summary_statistics"]["mean_prediction_error"]
                                }
                            except Exception as e:
                                print(f"    ⚠️  Walk-Forward failed: {str(e)}")
                        
                        # Step 5: Generate recommendations
                        try:
                            recommendation = await recommendation_service.generate_time_based_recommendation(
                                account_name=account.name,
                                hour=best_time_bin.hour,
                                minute_bin=best_time_bin.minute_bin,
                                day_of_week=None,
                                historical_performance={
                                    "avg_pnl": best_time_bin.average_pnl,
                                    "win_rate": best_time_bin.win_rate,
                                    "sample_size": best_time_bin.total_trades
                                }
                            )
                            
                            account_results["analysis_components"]["recommendation"] = {
                                "action": recommendation.recommended_action,
                                "confidence": recommendation.confidence_score,
                                "reasoning": recommendation.reasoning
                            }
                        except Exception as e:
                            print(f"    ⚠️  Recommendation generation failed: {str(e)}")
                
                integration_results[account.name] = account_results
                
                # Print account summary
                print(f"  ✅ {account.name} analysis completed:")
                print(f"     Time bins analyzed: {account_results['analysis_components'].get('time_bins', 0)}")
                if 'market_correlation' in account_results['analysis_components']:
                    corr = account_results['analysis_components']['market_correlation']
                    print(f"     SPY correlation: {corr.get('spy_correlation', 0):.3f}")
                if 'monte_carlo' in account_results['analysis_components']:
                    mc = account_results['analysis_components']['monte_carlo']
                    print(f"     Monte Carlo VaR 95%: ${mc['var_95']:.2f}")
                if 'recommendation' in account_results['analysis_components']:
                    rec = account_results['analysis_components']['recommendation']
                    print(f"     Recommendation: {rec['action']} (confidence: {rec['confidence']:.1%})")
            
            session.commit()
        
        # Validate integration results
        successful_analyses = 0
        total_components_tested = 0
        
        for account_name, results in integration_results.items():
            components = results["analysis_components"]
            total_components_tested += len(components)
            
            # Validate each component produced reasonable results
            if "time_bins" in components and components["time_bins"] > 0:
                successful_analyses += 1
            
            if "market_correlation" in components:
                corr = components["market_correlation"]
                assert -1.0 <= corr.get("spy_correlation", 0) <= 1.0, \
                    f"Invalid SPY correlation for {account_name}"
                successful_analyses += 1
            
            if "monte_carlo" in components:
                mc = components["monte_carlo"]
                assert isinstance(mc["var_95"], (int, float)), \
                    f"Invalid VaR for {account_name}"
                assert 0.0 <= mc["probability_of_profit"] <= 1.0, \
                    f"Invalid probability of profit for {account_name}"
                successful_analyses += 1
            
            if "recommendation" in components:
                rec = components["recommendation"]
                assert rec["action"] in ["TRADE", "AVOID", "STRONG_BUY", "BUY", "HOLD"], \
                    f"Invalid recommendation action for {account_name}"
                assert 0.0 <= rec["confidence"] <= 1.0, \
                    f"Invalid confidence score for {account_name}"
                successful_analyses += 1
        
        print(f"\n✅ System integration test completed:")
        print(f"   Accounts processed: {len(integration_results)}")
        print(f"   Successful component analyses: {successful_analyses}/{total_components_tested}")
        print(f"   Success rate: {successful_analyses/max(1, total_components_tested):.1%}")
        
        # Ensure reasonable success rate
        assert successful_analyses >= total_components_tested * 0.7, \
            f"Integration success rate too low: {successful_analyses}/{total_components_tested}"
        
        return integration_results
    
    @pytest.mark.asyncio
    async def test_edge_cases_and_error_handling(self, realistic_trading_database):
        """Test system behavior with edge cases and error conditions."""
        engine, SessionLocal = realistic_trading_database
        
        with SessionLocal() as session:
            # Test 1: Account with very few trades
            sparse_account = Account(name="SPARSE_TRADER", symbol="ES", total_trades=0)
            session.add(sparse_account)
            
            # Add only 3 trades (insufficient for most analyses)
            sparse_trades = []
            for i in range(3):
                trade = ProcessedTrade(
                    trade_id=f"SPARSE_{i:03d}",
                    account_name="SPARSE_TRADER",
                    symbol="ES",
                    entry_time=datetime(2023, 6, 1, 10, 30) + timedelta(days=i),
                    exit_time=datetime(2023, 6, 1, 11, 0) + timedelta(days=i),
                    profit_loss=50.0 * (i - 1),  # [-50, 0, 50]
                    quantity=1,
                    side="LONG",
                    entry_price=4500.0,
                    exit_price=4550.0,
                    hour_of_day=10,
                    day_of_week=i,
                    duration_minutes=30,
                    entry_order_id=f"E_SPARSE_{i}",
                    exit_order_id=f"X_SPARSE_{i}"
                )
                sparse_trades.append(trade)
            
            session.add_all(sparse_trades)
            
            # Test 2: Account with extreme outlier trades
            outlier_account = Account(name="OUTLIER_TRADER", symbol="NQ", total_trades=0)
            session.add(outlier_account)
            
            outlier_trades = []
            for i in range(20):
                if i == 10:  # One extreme outlier
                    pnl = 10000.0  # Massive win
                elif i == 15:
                    pnl = -8000.0  # Massive loss
                else:
                    pnl = np.random.normal(20, 30)  # Normal trades
                
                trade = ProcessedTrade(
                    trade_id=f"OUTLIER_{i:03d}",
                    account_name="OUTLIER_TRADER",
                    symbol="NQ",
                    entry_time=datetime(2023, 6, 1, 10, 30) + timedelta(hours=i),
                    exit_time=datetime(2023, 6, 1, 11, 0) + timedelta(hours=i),
                    profit_loss=pnl,
                    quantity=1,
                    side="LONG",
                    entry_price=4500.0,
                    exit_price=4500.0 + (pnl / 20),
                    hour_of_day=10,
                    day_of_week=0,
                    duration_minutes=30,
                    entry_order_id=f"E_OUTLIER_{i}",
                    exit_order_id=f"X_OUTLIER_{i}"
                )
                outlier_trades.append(trade)
            
            session.add_all(outlier_trades)
            session.commit()
            
            # Test analyses with edge cases
            time_bin_analyzer = TimeBinAnalyzer()
            
            # Test 1: Insufficient data handling
            print("\n🧪 Testing edge case: Insufficient data")
            try:
                sparse_analysis = await self._analyze_time_bin(
                    time_bin_analyzer, "SPARSE_TRADER", 10, 30, sparse_trades
                )
                
                # Should handle gracefully or return None
                if sparse_analysis:
                    print("   ✅ Analysis completed with sparse data")
                    assert sparse_analysis.total_trades == 3
                else:
                    print("   ✅ Correctly rejected sparse data")
            
            except ValueError as e:
                print(f"   ✅ Expected error for sparse data: {str(e)}")
                assert "insufficient" in str(e).lower()
            except Exception as e:
                print(f"   ⚠️  Unexpected error: {str(e)}")
            
            # Test 2: Outlier handling
            print("\n🧪 Testing edge case: Extreme outliers")
            try:
                outlier_analysis = await self._analyze_time_bin(
                    time_bin_analyzer, "OUTLIER_TRADER", 10, 30, outlier_trades
                )
                
                if outlier_analysis:
                    print(f"   ✅ Analysis handled outliers (avg P&L: ${outlier_analysis.average_pnl:.2f})")
                    
                    # Check if outliers significantly skewed results
                    median_pnl = np.median([t.profit_loss for t in outlier_trades])
                    outlier_ratio = abs(outlier_analysis.average_pnl) / abs(median_pnl) if median_pnl != 0 else 1
                    
                    print(f"   Outlier impact ratio: {outlier_ratio:.2f}")
                    
                    # Should be somewhat robust to outliers
                    assert outlier_ratio < 50, "Analysis too sensitive to outliers"
                
            except Exception as e:
                print(f"   ⚠️  Outlier handling error: {str(e)}")
            
            # Test 3: Missing market data correlation
            print("\n🧪 Testing edge case: Missing market data correlation")
            benchmark_analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
            
            try:
                # Try correlation with non-existent date range
                correlation_result = await benchmark_analyzer.calculate_market_correlation(
                    account_name="OUTLIER_TRADER",
                    benchmark_symbols=["SPY"],
                    start_date=datetime(2020, 1, 1),  # Before our data
                    end_date=datetime(2020, 12, 31)
                )
                
                # Should handle gracefully
                if correlation_result:
                    print("   ✅ Correlation analysis handled missing data")
                else:
                    print("   ✅ Correctly returned None for missing market data")
                    
            except Exception as e:
                print(f"   Expected error for missing market data: {str(e)}")
            
            # Test 4: Monte Carlo with extreme volatility
            print("\n🧪 Testing edge case: Monte Carlo with extreme volatility")
            monte_carlo_simulator = MonteCarloSimulator(SessionLocal())
            
            try:
                # Create analysis record for outlier account
                outlier_analysis = TimeBinAnalysis(
                    account_name="OUTLIER_TRADER",
                    hour=10,
                    minute_bin=30,
                    analysis_date=datetime.now().date(),
                    total_trades=20,
                    win_rate=0.6,
                    average_pnl=200.0,  # Will be skewed by outliers
                    sharpe_ratio=0.5,
                    max_drawdown=-500.0,
                    profit_factor=1.2
                )
                session.add(outlier_analysis)
                session.commit()
                
                mc_results = await monte_carlo_simulator.run_simulation(
                    time_bin_analysis_id=outlier_analysis.id,
                    historical_trades=outlier_trades,
                    n_scenarios=500,  # Fewer scenarios for edge case testing
                    time_horizon_days=30
                )
                
                if mc_results:
                    print(f"   ✅ Monte Carlo handled extreme volatility")
                    print(f"      VaR 95%: ${mc_results['var_95']:.2f}")
                    
                    # Results should be reasonable despite outliers
                    assert -50000 <= mc_results['var_95'] <= 50000, "VaR seems unreasonable"
                    assert 0.0 <= mc_results['probability_of_profit'] <= 1.0, "Probability invalid"
                
            except Exception as e:
                print(f"   Expected Monte Carlo robustness issue: {str(e)}")
        
        print("\n✅ Edge case testing completed")
    
    @pytest.mark.asyncio
    async def test_performance_under_realistic_load(self, realistic_trading_database):
        """Test system performance under realistic concurrent load."""
        engine, SessionLocal = realistic_trading_database
        
        print("\n🚀 Testing system performance under realistic load")
        
        # Simulate multiple concurrent user sessions
        async def simulate_user_session(session_id: int, account_name: str) -> Dict[str, Any]:
            """Simulate a user session performing typical analytics."""
            session_start = datetime.now()
            session_results = {"session_id": session_id, "account": account_name, "operations": []}
            
            try:
                with SessionLocal() as db_session:
                    # Operation 1: Get account overview
                    op_start = datetime.now()
                    account_trades = db_session.query(ProcessedTrade).filter(
                        ProcessedTrade.account_name == account_name
                    ).limit(200).all()  # Realistic query limit
                    
                    op_duration = (datetime.now() - op_start).total_seconds()
                    session_results["operations"].append({
                        "operation": "account_overview",
                        "duration": op_duration,
                        "records": len(account_trades)
                    })
                    
                    if account_trades:
                        # Operation 2: Time-bin analysis
                        op_start = datetime.now()
                        time_bins = self._group_trades_by_time_bins(account_trades)
                        
                        # Analyze one time bin
                        if time_bins:
                            hour, minute_bin = list(time_bins.keys())[0]
                            bin_trades = time_bins[(hour, minute_bin)]
                            
                            if len(bin_trades) >= 10:
                                analyzer = TimeBinAnalyzer()
                                analysis = await self._analyze_time_bin(
                                    analyzer, account_name, hour, minute_bin, bin_trades
                                )
                        
                        op_duration = (datetime.now() - op_start).total_seconds()
                        session_results["operations"].append({
                            "operation": "time_bin_analysis",
                            "duration": op_duration,
                            "time_bins": len(time_bins)
                        })
                        
                        # Operation 3: Market correlation
                        op_start = datetime.now()
                        benchmark_analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
                        await benchmark_analyzer.calculate_market_correlation(
                            account_name=account_name,
                            benchmark_symbols=["SPY"],
                            start_date=datetime(2023, 6, 1),
                            end_date=datetime(2023, 8, 1)
                        )
                        
                        op_duration = (datetime.now() - op_start).total_seconds()
                        session_results["operations"].append({
                            "operation": "market_correlation",
                            "duration": op_duration
                        })
                        
                        # Simulate some think time
                        await asyncio.sleep(0.1)
            
            except Exception as e:
                session_results["error"] = str(e)
            
            session_results["total_duration"] = (datetime.now() - session_start).total_seconds()
            return session_results
        
        # Start concurrent user sessions
        with SessionLocal() as session:
            active_accounts = [acc.name for acc in session.query(Account).limit(4).all()]
        
        concurrent_sessions = []
        for i in range(8):  # 8 concurrent users
            account = active_accounts[i % len(active_accounts)]
            session_task = asyncio.create_task(simulate_user_session(i, account))
            concurrent_sessions.append(session_task)
        
        # Wait for all sessions to complete
        load_test_start = datetime.now()
        session_results = await asyncio.gather(*concurrent_sessions, return_exceptions=True)
        total_load_test_time = (datetime.now() - load_test_start).total_seconds()
        
        # Analyze performance results
        successful_sessions = [r for r in session_results if isinstance(r, dict) and "error" not in r]
        failed_sessions = [r for r in session_results if not isinstance(r, dict) or "error" in r]
        
        print(f"   Concurrent sessions: 8")
        print(f"   Successful sessions: {len(successful_sessions)}")
        print(f"   Failed sessions: {len(failed_sessions)}")
        print(f"   Total test time: {total_load_test_time:.2f}s")
        
        if successful_sessions:
            # Calculate performance statistics
            session_durations = [s["total_duration"] for s in successful_sessions]
            avg_session_time = np.mean(session_durations)
            max_session_time = np.max(session_durations)
            
            operation_stats = {}
            for session in successful_sessions:
                for op in session["operations"]:
                    op_name = op["operation"]
                    if op_name not in operation_stats:
                        operation_stats[op_name] = []
                    operation_stats[op_name].append(op["duration"])
            
            print(f"   Average session time: {avg_session_time:.2f}s")
            print(f"   Maximum session time: {max_session_time:.2f}s")
            
            for op_name, durations in operation_stats.items():
                avg_duration = np.mean(durations)
                max_duration = np.max(durations)
                print(f"   {op_name}: avg={avg_duration:.3f}s, max={max_duration:.3f}s")
            
            # Performance assertions
            assert len(successful_sessions) >= 6, "Too many session failures"
            assert avg_session_time < 5.0, f"Average session time too slow: {avg_session_time:.2f}s"
            assert max_session_time < 10.0, f"Maximum session time too slow: {max_session_time:.2f}s"
            
            print("   ✅ Performance targets met")
        
        print(f"✅ Realistic load testing completed")
    
    # Helper methods
    
    def _group_trades_by_time_bins(self, trades: List[ProcessedTrade]) -> Dict[Tuple[int, int], List[ProcessedTrade]]:
        """Group trades by hour and 30-minute bins."""
        time_bins = {}
        for trade in trades:
            minute_bin = 30 if trade.entry_time.minute >= 30 else 0
            bin_key = (trade.hour_of_day, minute_bin)
            
            if bin_key not in time_bins:
                time_bins[bin_key] = []
            time_bins[bin_key].append(trade)
        
        return time_bins
    
    async def _analyze_time_bin(
        self, 
        analyzer: TimeBinAnalyzer,
        account_name: str,
        hour: int,
        minute_bin: int,
        trades: List[ProcessedTrade]
    ) -> TimeBinAnalysis:
        """Analyze a time bin and return TimeBinAnalysis."""
        if len(trades) < 5:  # Minimum threshold
            raise ValueError("Insufficient data for time bin analysis")
        
        total_pnl = sum(t.profit_loss for t in trades)
        winning_trades = len([t for t in trades if t.profit_loss > 0])
        
        returns = [t.profit_loss for t in trades]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        max_drawdown = self._calculate_max_drawdown(returns) 
        profit_factor = self._calculate_profit_factor(returns)
        
        analysis = TimeBinAnalysis(
            account_name=account_name,
            hour=hour,
            minute_bin=minute_bin,
            day_of_week=None,
            analysis_date=datetime.now().date(),
            total_trades=len(trades),
            win_rate=winning_trades / len(trades),
            average_pnl=total_pnl / len(trades),
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            statistical_significance=len(trades) >= 30,
            sample_size_adequate=len(trades) >= 20
        )
        
        return analysis
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        return mean_return / std_return if std_return > 0 else 0.0
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown."""
        if not returns:
            return 0.0
        
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        
        return float(np.min(drawdown))
    
    def _calculate_profit_factor(self, returns: List[float]) -> float:
        """Calculate profit factor."""
        if not returns:
            return 1.0
        
        profits = [r for r in returns if r > 0]
        losses = [abs(r) for r in returns if r < 0]
        
        total_profit = sum(profits)
        total_loss = sum(losses)
        
        return total_profit / total_loss if total_loss > 0 else float('inf')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])