"""
Comprehensive integration tests for market correlation analysis workflow.

This module tests the complete market correlation pipeline including:
- Market data ingestion (SPY/QQQ/VIX)
- Correlation calculation with trading performance
- Beta and alpha analysis
- Market regime classification
- Market-neutral strategy validation

Requirements: 1.1, 2.1, 3.1, 11.1, 12.1
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, patch, AsyncMock
import json

# Import components for market correlation workflow
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.models.time_bin_analytics import (
    TimeBinAnalysis, MarketData, VolatilityRegime
)
from trading_platform.services.benchmark_comparison_analyzer import (
    BenchmarkComparisonAnalyzer, BenchmarkMetrics
)
from trading_platform.services.vix_regime_analyzer import (
    VIXRegimeAnalyzer, VIXRegime, RegimeType
)
from trading_platform.services.market_data_ingestion import (
    MarketDataIngestionService
)
from trading_platform.services.free_market_data import (
    FreeMarketDataService
)
from trading_platform.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestMarketCorrelationWorkflow:
    """Test complete market correlation analysis workflow."""
    
    @pytest.fixture
    async def test_database_with_market_data(self):
        """Create test database with comprehensive market and trading data."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            # Create test accounts
            accounts = [
                Account(name="SPY_FOLLOWER", symbol="ES", total_trades=0, is_active=True),
                Account(name="QQQ_MOMENTUM", symbol="NQ", total_trades=0, is_active=True),
                Account(name="VIX_CONTRARIAN", symbol="ES", total_trades=0, is_active=True)
            ]
            session.add_all(accounts)
            
            # Generate 90 days of market data
            base_date = datetime(2024, 1, 1)
            market_data = []
            
            # SPY data - trending upward
            spy_base = 450.0
            for day in range(90):
                if (base_date + timedelta(days=day)).weekday() >= 5:  # Skip weekends
                    continue
                    
                current_date = (base_date + timedelta(days=day)).date()
                trend = day * 0.5  # Upward trend
                volatility = np.random.normal(0, 5)  # Daily volatility
                close_price = spy_base + trend + volatility
                
                market_data.append(MarketData(
                    symbol='SPY',
                    date=current_date,
                    open_price=close_price - 1.0,
                    high_price=close_price + 2.0,
                    low_price=close_price - 2.0,
                    close_price=close_price,
                    volume=50000000,
                    adjusted_close=close_price
                ))
            
            # QQQ data - higher volatility, momentum-driven
            qqq_base = 380.0
            for day in range(90):
                if (base_date + timedelta(days=day)).weekday() >= 5:
                    continue
                    
                current_date = (base_date + timedelta(days=day)).date()
                momentum = np.sin(day * 0.1) * 10  # Cyclical momentum
                volatility = np.random.normal(0, 8)  # Higher volatility than SPY
                close_price = qqq_base + momentum + volatility
                
                market_data.append(MarketData(
                    symbol='QQQ',
                    date=current_date,
                    open_price=close_price - 1.5,
                    high_price=close_price + 3.0,
                    low_price=close_price - 3.0,
                    close_price=close_price,
                    volume=30000000,
                    adjusted_close=close_price
                ))
            
            # VIX data - inversely correlated with market
            vix_base = 20.0
            for day in range(90):
                if (base_date + timedelta(days=day)).weekday() >= 5:
                    continue
                    
                current_date = (base_date + timedelta(days=day)).date()
                # VIX spikes when market drops
                market_stress = -trend * 0.3 + abs(volatility) * 0.5
                vix_value = max(10.0, vix_base + market_stress + np.random.normal(0, 2))
                
                market_data.append(MarketData(
                    symbol='VIX',
                    date=current_date,
                    open_price=vix_value - 0.5,
                    high_price=vix_value + 1.0,
                    low_price=vix_value - 1.0,
                    close_price=vix_value,
                    volume=0,  # VIX doesn't have volume
                    adjusted_close=vix_value
                ))
            
            session.add_all(market_data)
            
            # Generate trading data correlated with market conditions
            spy_prices = {md.date: md.close_price for md in market_data if md.symbol == 'SPY'}
            qqq_prices = {md.date: md.close_price for md in market_data if md.symbol == 'QQQ'}
            vix_values = {md.date: md.close_price for md in market_data if md.symbol == 'VIX'}
            
            all_trades = []
            
            for account in accounts:
                trade_id = 1
                
                for day_offset in range(60):  # 60 days of trading
                    trade_date = base_date + timedelta(days=day_offset)
                    
                    if trade_date.weekday() >= 5 or trade_date.date() not in spy_prices:
                        continue
                    
                    spy_price = spy_prices[trade_date.date()]
                    qqq_price = qqq_prices[trade_date.date()]
                    vix_value = vix_values[trade_date.date()]
                    
                    # Different trading strategies based on account
                    if account.name == "SPY_FOLLOWER":
                        # Trades that follow SPY direction
                        spy_return = (spy_price - spy_prices.get(
                            (trade_date - timedelta(days=1)).date(), spy_price
                        )) / spy_price
                        base_pnl = spy_return * 1000  # Amplified SPY returns
                        
                    elif account.name == "QQQ_MOMENTUM":
                        # Momentum strategy following QQQ
                        qqq_return = (qqq_price - qqq_prices.get(
                            (trade_date - timedelta(days=1)).date(), qqq_price
                        )) / qqq_price
                        base_pnl = qqq_return * 1200  # Higher leverage on QQQ
                        
                    else:  # VIX_CONTRARIAN
                        # Contrarian strategy - profit when VIX is high
                        vix_impact = (vix_value - 20) * 10  # More profit when VIX > 20
                        base_pnl = vix_impact + np.random.normal(0, 20)
                    
                    # Generate multiple trades per day
                    for hour in [10, 12, 14]:
                        entry_time = trade_date.replace(hour=hour, minute=30)
                        exit_time = entry_time + timedelta(minutes=30)
                        
                        # Add some noise to the correlation
                        noise = np.random.normal(0, 30)
                        final_pnl = base_pnl + noise
                        
                        trade = ProcessedTrade(
                            trade_id=f"{account.name}_{trade_id:06d}",
                            account_name=account.name,
                            symbol=account.symbol,
                            entry_time=entry_time,
                            exit_time=exit_time,
                            entry_price=4500.0,
                            exit_price=4500.0 + (final_pnl / 20),
                            quantity=1,
                            side="LONG" if final_pnl > 0 else "SHORT",
                            profit_loss=final_pnl,
                            commission=2.50,
                            duration_minutes=30,
                            hour_of_day=hour,
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
            
            session.commit()
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_market_data_ingestion_workflow(self, test_database_with_market_data):
        """Test market data ingestion and validation."""
        engine, SessionLocal = test_database_with_market_data
        
        # Step 1: Initialize market data service
        market_data_service = MarketDataIngestionService(SessionLocal())
        
        # Step 2: Validate ingested market data
        with SessionLocal() as session:
            spy_data = session.query(MarketData).filter(MarketData.symbol == 'SPY').all()
            qqq_data = session.query(MarketData).filter(MarketData.symbol == 'QQQ').all()
            vix_data = session.query(MarketData).filter(MarketData.symbol == 'VIX').all()
            
            assert len(spy_data) > 60, "Should have sufficient SPY data"
            assert len(qqq_data) > 60, "Should have sufficient QQQ data"
            assert len(vix_data) > 60, "Should have sufficient VIX data"
            
            # Validate data quality
            for data_point in spy_data[:10]:
                assert data_point.close_price > 0, "SPY price should be positive"
                assert data_point.volume > 0, "SPY volume should be positive"
                assert data_point.high_price >= data_point.close_price >= data_point.low_price
            
            for data_point in vix_data[:10]:
                assert 5.0 <= data_point.close_price <= 100.0, "VIX should be in reasonable range"
            
            print(f"✅ Market data validation passed: SPY={len(spy_data)}, QQQ={len(qqq_data)}, VIX={len(vix_data)}")
        
        # Step 3: Test data consistency checks
        validation_result = await market_data_service.validate_market_data_consistency(
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 3, 31).date()
        )
        
        assert validation_result['status'] == 'valid'
        assert validation_result['missing_dates'] == 0 or validation_result['missing_dates'] <= 3  # Allow for weekends
        assert validation_result['data_quality_score'] > 0.8
    
    @pytest.mark.asyncio
    async def test_benchmark_correlation_analysis(self, test_database_with_market_data):
        """Test correlation analysis between trading performance and market benchmarks."""
        engine, SessionLocal = test_database_with_market_data
        
        # Initialize benchmark comparison analyzer
        analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
        
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            correlation_results = {}
            
            for account in accounts:
                # Analyze correlation with each benchmark
                spy_correlation = await analyzer.calculate_benchmark_correlation(
                    account_name=account.name,
                    benchmark_symbol='SPY',
                    analysis_period_days=60
                )
                
                qqq_correlation = await analyzer.calculate_benchmark_correlation(
                    account_name=account.name,
                    benchmark_symbol='QQQ',
                    analysis_period_days=60
                )
                
                vix_correlation = await analyzer.calculate_benchmark_correlation(
                    account_name=account.name,
                    benchmark_symbol='VIX',
                    analysis_period_days=60
                )
                
                correlation_results[account.name] = {
                    'SPY': spy_correlation,
                    'QQQ': qqq_correlation,
                    'VIX': vix_correlation
                }
                
                # Validate expected correlations based on account strategy
                if account.name == "SPY_FOLLOWER":
                    assert spy_correlation['correlation'] > 0.3, f"SPY_FOLLOWER should be correlated with SPY: {spy_correlation['correlation']}"
                    assert spy_correlation['beta'] > 0.5, f"SPY_FOLLOWER should have positive beta to SPY: {spy_correlation['beta']}"
                    
                elif account.name == "QQQ_MOMENTUM":
                    assert qqq_correlation['correlation'] > 0.2, f"QQQ_MOMENTUM should be correlated with QQQ: {qqq_correlation['correlation']}"
                    assert qqq_correlation['beta'] > 0.3, f"QQQ_MOMENTUM should have positive beta to QQQ: {qqq_correlation['beta']}"
                    
                elif account.name == "VIX_CONTRARIAN":
                    # VIX contrarian should have negative correlation with VIX (profits when VIX is high but falling)
                    # Or positive correlation if strategy profits from high VIX
                    assert abs(vix_correlation['correlation']) > 0.1, f"VIX_CONTRARIAN should have meaningful VIX correlation: {vix_correlation['correlation']}"
                
                print(f"Account {account.name} correlations:")
                print(f"  SPY: r={spy_correlation['correlation']:.3f}, β={spy_correlation['beta']:.3f}")
                print(f"  QQQ: r={qqq_correlation['correlation']:.3f}, β={qqq_correlation['beta']:.3f}")
                print(f"  VIX: r={vix_correlation['correlation']:.3f}, β={vix_correlation['beta']:.3f}")
        
        # Step 2: Generate comprehensive benchmark metrics
        benchmark_metrics = await analyzer.generate_benchmark_comparison_report(
            account_names=[acc.name for acc in accounts],
            benchmark_symbols=['SPY', 'QQQ', 'VIX'],
            analysis_period_days=60
        )
        
        assert 'account_comparisons' in benchmark_metrics
        assert len(benchmark_metrics['account_comparisons']) == len(accounts)
        
        for account_metrics in benchmark_metrics['account_comparisons']:
            assert 'sharpe_ratio' in account_metrics
            assert 'alpha' in account_metrics
            assert 'information_ratio' in account_metrics
            assert 'tracking_error' in account_metrics
            
            # Validate reasonable ranges
            assert -5.0 <= account_metrics['sharpe_ratio'] <= 5.0
            assert -500.0 <= account_metrics['alpha'] <= 500.0
    
    @pytest.mark.asyncio
    async def test_vix_regime_analysis(self, test_database_with_market_data):
        """Test VIX regime classification and performance analysis."""
        engine, SessionLocal = test_database_with_market_data
        
        # Initialize VIX regime analyzer
        vix_analyzer = VIXRegimeAnalyzer(SessionLocal())
        
        # Step 1: Classify VIX regimes
        regime_analysis = await vix_analyzer.analyze_vix_regimes(
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 3, 31).date()
        )
        
        assert 'regimes' in regime_analysis
        assert len(regime_analysis['regimes']) > 0
        
        # Validate regime classifications
        regimes = regime_analysis['regimes']
        regime_types = {regime['regime_type'] for regime in regimes}
        
        # Should have identified different regime types
        expected_regimes = {RegimeType.LOW_VOLATILITY, RegimeType.NORMAL_VOLATILITY}
        assert len(regime_types.intersection(expected_regimes)) > 0
        
        for regime in regimes:
            assert 'start_date' in regime
            assert 'end_date' in regime
            assert 'avg_vix' in regime
            assert 10.0 <= regime['avg_vix'] <= 80.0  # Reasonable VIX range
        
        print(f"✅ VIX regime analysis: {len(regimes)} regimes identified")
        for regime in regimes:
            print(f"  {regime['regime_type']}: {regime['start_date']} to {regime['end_date']}, avg VIX: {regime['avg_vix']:.1f}")
        
        # Step 2: Analyze trading performance by VIX regime
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            for account in accounts:
                regime_performance = await vix_analyzer.analyze_performance_by_regime(
                    account_name=account.name,
                    regimes=regimes
                )
                
                assert 'regime_breakdown' in regime_performance
                assert 'overall_statistics' in regime_performance
                
                breakdown = regime_performance['regime_breakdown']
                
                for regime_type, performance in breakdown.items():
                    if performance['trade_count'] > 0:
                        assert 'avg_pnl' in performance
                        assert 'win_rate' in performance
                        assert 'sharpe_ratio' in performance
                        assert 0.0 <= performance['win_rate'] <= 1.0
                
                print(f"Account {account.name} regime performance:")
                for regime_type, perf in breakdown.items():
                    if perf['trade_count'] > 0:
                        print(f"  {regime_type}: {perf['trade_count']} trades, "
                              f"avg PnL: {perf['avg_pnl']:.1f}, "
                              f"win rate: {perf['win_rate']:.1%}")
    
    @pytest.mark.asyncio
    async def test_market_neutral_strategy_validation(self, test_database_with_market_data):
        """Test validation of market-neutral trading strategies."""
        engine, SessionLocal = test_database_with_market_data
        
        analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
        
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            market_neutrality_results = {}
            
            for account in accounts:
                # Test market neutrality
                neutrality_test = await analyzer.test_market_neutrality(
                    account_name=account.name,
                    benchmark_symbols=['SPY', 'QQQ'],
                    significance_level=0.05
                )
                
                market_neutrality_results[account.name] = neutrality_test
                
                assert 'is_market_neutral' in neutrality_test
                assert 'p_values' in neutrality_test
                assert 'beta_significance' in neutrality_test
                assert 'correlation_significance' in neutrality_test
                
                # Validate statistical test results
                for benchmark, p_value in neutrality_test['p_values'].items():
                    assert 0.0 <= p_value <= 1.0, f"P-value should be between 0 and 1: {p_value}"
                
                print(f"Account {account.name} market neutrality:")
                print(f"  Market neutral: {neutrality_test['is_market_neutral']}")
                print(f"  P-values: {neutrality_test['p_values']}")
                
                # Expected results based on account strategies
                if account.name == "SPY_FOLLOWER":
                    # Should NOT be market neutral (should be correlated with SPY)
                    assert not neutrality_test['is_market_neutral'], "SPY_FOLLOWER should not be market neutral"
                    
                elif account.name == "VIX_CONTRARIAN":
                    # Might be more market neutral depending on VIX strategy effectiveness
                    # This is OK either way
                    pass
        
        # Step 2: Generate market exposure report
        exposure_report = await analyzer.calculate_market_exposure_report(
            account_names=[acc.name for acc in accounts],
            benchmark_symbols=['SPY', 'QQQ', 'VIX']
        )
        
        assert 'total_accounts_analyzed' in exposure_report
        assert 'market_neutral_accounts' in exposure_report
        assert 'high_correlation_accounts' in exposure_report
        assert 'exposure_summary' in exposure_report
        
        assert exposure_report['total_accounts_analyzed'] == len(accounts)
        
        print(f"✅ Market exposure analysis:")
        print(f"  Total accounts: {exposure_report['total_accounts_analyzed']}")
        print(f"  Market neutral: {len(exposure_report['market_neutral_accounts'])}")
        print(f"  High correlation: {len(exposure_report['high_correlation_accounts'])}")
    
    @pytest.mark.asyncio
    async def test_dynamic_correlation_analysis(self, test_database_with_market_data):
        """Test dynamic correlation analysis over time periods."""
        engine, SessionLocal = test_database_with_market_data
        
        analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
        
        with SessionLocal() as session:
            # Test rolling correlation analysis
            account = session.query(Account).first()
            
            rolling_correlation = await analyzer.calculate_rolling_correlation(
                account_name=account.name,
                benchmark_symbol='SPY',
                window_days=20,
                step_days=5
            )
            
            assert 'correlation_series' in rolling_correlation
            assert 'beta_series' in rolling_correlation
            assert 'time_series' in rolling_correlation
            
            correlation_values = rolling_correlation['correlation_series']
            beta_values = rolling_correlation['beta_series']
            
            assert len(correlation_values) > 0, "Should have correlation time series"
            assert len(beta_values) > 0, "Should have beta time series"
            assert len(correlation_values) == len(beta_values), "Series should have same length"
            
            # Validate correlation values are in valid range
            for corr in correlation_values:
                if corr is not None:
                    assert -1.0 <= corr <= 1.0, f"Correlation should be between -1 and 1: {corr}"
            
            # Validate beta values are reasonable
            for beta in beta_values:
                if beta is not None:
                    assert -5.0 <= beta <= 5.0, f"Beta should be reasonable: {beta}"
            
            print(f"✅ Rolling correlation analysis: {len(correlation_values)} periods")
            print(f"  Correlation range: {min(c for c in correlation_values if c is not None):.3f} to {max(c for c in correlation_values if c is not None):.3f}")
            print(f"  Beta range: {min(b for b in beta_values if b is not None):.3f} to {max(b for b in beta_values if b is not None):.3f}")
    
    @pytest.mark.asyncio
    async def test_correlation_workflow_performance(self, test_database_with_market_data):
        """Test performance of correlation analysis workflow under load."""
        engine, SessionLocal = test_database_with_market_data
        
        analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
        
        # Test concurrent correlation analysis
        async def analyze_account_correlation(account_name: str) -> Dict[str, Any]:
            start_time = datetime.now()
            
            correlations = {}
            for benchmark in ['SPY', 'QQQ', 'VIX']:
                corr_result = await analyzer.calculate_benchmark_correlation(
                    account_name=account_name,
                    benchmark_symbol=benchmark,
                    analysis_period_days=30  # Shorter period for performance test
                )
                correlations[benchmark] = corr_result
            
            duration = (datetime.now() - start_time).total_seconds()
            return {
                'account': account_name,
                'correlations': correlations,
                'duration': duration
            }
        
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            # Execute concurrent correlation analysis
            start_time = datetime.now()
            tasks = [analyze_account_correlation(acc.name) for acc in accounts]
            results = await asyncio.gather(*tasks)
            total_duration = (datetime.now() - start_time).total_seconds()
            
            # Validate performance
            assert total_duration < 15.0, f"Concurrent correlation analysis too slow: {total_duration:.2f}s"
            
            for result in results:
                assert result['duration'] < 10.0, f"Individual correlation analysis too slow: {result}"
                assert len(result['correlations']) == 3, "Should analyze all benchmarks"
                
                # Validate correlation results
                for benchmark, corr_data in result['correlations'].items():
                    assert 'correlation' in corr_data
                    assert 'beta' in corr_data
                    assert 'r_squared' in corr_data
            
            print(f"✅ Concurrent correlation analysis: {len(results)} accounts in {total_duration:.2f}s")
            for result in results:
                print(f"  {result['account']}: {result['duration']:.2f}s")


class TestMarketCorrelationIntegration:
    """Integration tests for market correlation with other components."""
    
    @pytest.mark.asyncio
    async def test_correlation_with_time_bin_analysis(self):
        """Test integration of market correlation with time-bin analysis."""
        # This would test how market correlation affects time-bin performance
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        try:
            # Create test data with time-bin and market correlation
            with SessionLocal() as session:
                # Add market data
                market_data = []
                base_date = datetime(2024, 1, 1)
                
                for day in range(30):
                    if (base_date + timedelta(days=day)).weekday() >= 5:
                        continue
                    
                    current_date = (base_date + timedelta(days=day)).date()
                    spy_price = 450 + day * 2 + np.random.normal(0, 5)  # Upward trend
                    
                    market_data.append(MarketData(
                        symbol='SPY',
                        date=current_date,
                        close_price=spy_price,
                        open_price=spy_price - 1,
                        high_price=spy_price + 2,
                        low_price=spy_price - 2,
                        volume=50000000,
                        adjusted_close=spy_price
                    ))
                
                session.add_all(market_data)
                
                # Add account and time-bin analysis data
                account = Account(name="TEST_ACCOUNT", symbol="ES", total_trades=100)
                session.add(account)
                
                # Create time-bin analysis with market correlation data
                time_bin_analysis = TimeBinAnalysis(
                    account_name="TEST_ACCOUNT",
                    hour=10,
                    minute_bin=30,
                    analysis_date=datetime(2024, 1, 15).date(),
                    total_trades=50,
                    win_rate=0.65,
                    average_pnl=45.0,
                    sharpe_ratio=1.8,
                    max_drawdown=-120.0,
                    profit_factor=1.4,
                    spy_correlation=0.72,  # High correlation with SPY
                    beta_spy=1.15,  # Leveraged to SPY
                    alpha_vs_spy=25.0,  # Positive alpha
                    market_neutrality_p_value=0.02,  # Not market neutral
                    statistical_significance=True,
                    sample_size_adequate=True
                )
                
                session.add(time_bin_analysis)
                session.commit()
                
                # Test correlation integration
                analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
                
                # Get time-bin with correlation data
                time_bin_with_correlation = await analyzer.enrich_time_bin_with_correlation(
                    time_bin_analysis_id=time_bin_analysis.id,
                    benchmark_symbols=['SPY']
                )
                
                assert time_bin_with_correlation is not None
                assert 'correlation_metrics' in time_bin_with_correlation
                assert 'market_exposure' in time_bin_with_correlation
                
                correlation_metrics = time_bin_with_correlation['correlation_metrics']['SPY']
                assert abs(correlation_metrics['correlation'] - 0.72) < 0.1  # Should match stored correlation
                assert abs(correlation_metrics['beta'] - 1.15) < 0.1  # Should match stored beta
                
                print(f"✅ Time-bin correlation integration validated")
                print(f"  Correlation: {correlation_metrics['correlation']:.3f}")
                print(f"  Beta: {correlation_metrics['beta']:.3f}")
                print(f"  Alpha: {correlation_metrics.get('alpha', 0):.1f}")
                
        finally:
            os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_real_time_correlation_monitoring(self):
        """Test real-time correlation monitoring capabilities."""
        # Mock real-time market data feed
        class MockMarketDataFeed:
            def __init__(self):
                self.spy_price = 450.0
                self.callbacks = []
            
            def subscribe(self, callback):
                self.callbacks.append(callback)
            
            async def simulate_price_update(self):
                self.spy_price += np.random.normal(0, 2)
                for callback in self.callbacks:
                    await callback('SPY', self.spy_price, datetime.now())
        
        # Test real-time correlation tracking
        feed = MockMarketDataFeed()
        correlation_tracker = {}
        
        async def track_correlation(symbol: str, price: float, timestamp: datetime):
            if symbol not in correlation_tracker:
                correlation_tracker[symbol] = []
            correlation_tracker[symbol].append((price, timestamp))
            
            # Keep only recent prices (last 20 updates)
            if len(correlation_tracker[symbol]) > 20:
                correlation_tracker[symbol] = correlation_tracker[symbol][-20:]
        
        feed.subscribe(track_correlation)
        
        # Simulate real-time updates
        for _ in range(25):
            await feed.simulate_price_update()
            await asyncio.sleep(0.01)  # Small delay
        
        # Validate tracking
        assert 'SPY' in correlation_tracker
        assert len(correlation_tracker['SPY']) == 20  # Should keep only last 20
        
        prices = [price for price, _ in correlation_tracker['SPY']]
        assert len(set(prices)) > 1, "Prices should vary"
        assert all(400 <= price <= 500 for price in prices), "Prices should be reasonable"
        
        print(f"✅ Real-time correlation tracking: {len(correlation_tracker['SPY'])} updates")
        print(f"  Price range: {min(prices):.2f} - {max(prices):.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])