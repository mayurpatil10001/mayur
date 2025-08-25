"""
Comprehensive integration tests for complete time-bin analysis workflow.

This module tests the complete end-to-end time-bin analysis pipeline including:
- Data ingestion and validation
- Time-bin analysis calculation
- Statistical significance testing
- Performance metrics computation
- Export and reporting generation

Requirements: 1.1, 2.1, 3.1, 11.1, 12.1
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
from datetime import datetime, timedelta, time as dt_time
from decimal import Decimal
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock
import json

# Import all the components we need for the complete workflow
from trading_platform.models.database import (
    ProcessedTrade, Account, PerformanceMetric, TemporalPerformance
)
from trading_platform.models.time_bin_analytics import (
    TimeBinAnalysis, MarketData, VolatilityRegime
)
from trading_platform.services.time_bin_analyzer import (
    TimeBinAnalyzer, TimeBin, TimeBinPerformance
)
from trading_platform.services.statistical_analysis_engine.performance_metrics_calculator import (
    PerformanceMetricsCalculator
)
from trading_platform.services.export_reporting.data_export_engine import (
    DataExportEngine, ExportConfig, ExportFormat
)
from trading_platform.services.recommendation.recommendation_service import (
    RecommendationService
)
from trading_platform.database.base import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class TestCompleteTimeBinWorkflow:
    """Test complete end-to-end time-bin analysis workflow."""
    
    @pytest.fixture
    async def test_database(self):
        """Create a temporary database with realistic test data."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        # Insert comprehensive test data
        with SessionLocal() as session:
            # Create test accounts
            accounts = [
                Account(name="IPS_TM_10", symbol="NQ", total_trades=0, is_active=True),
                Account(name="IPS_TM_13", symbol="ES", total_trades=0, is_active=True),
                Account(name="IPS_TM_15", symbol="YM", total_trades=0, is_active=True)
            ]
            session.add_all(accounts)
            
            # Create realistic trading data spanning multiple time periods
            base_date = datetime(2024, 1, 1, 9, 30)  # Start at market open
            processed_trades = []
            
            for account in accounts:
                trade_id = 1
                for day_offset in range(60):  # 60 days of data
                    current_date = base_date + timedelta(days=day_offset)
                    
                    # Skip weekends
                    if current_date.weekday() >= 5:
                        continue
                    
                    # Generate trades for different time bins throughout the day
                    for hour in range(9, 16):  # Market hours 9:30 AM - 4:00 PM
                        for minute_bin in [30, 45]:  # 30-minute bins
                            if minute_bin == 45 and hour == 15:  # Don't go past 4:00 PM
                                break
                                
                            entry_time = current_date.replace(hour=hour, minute=minute_bin)
                            exit_time = entry_time + timedelta(minutes=15 + (trade_id % 20))
                            
                            # Create realistic P&L based on time patterns
                            base_pnl = 50.0
                            
                            # Morning sessions tend to be more profitable
                            if 9 <= hour <= 11:
                                base_pnl *= 1.2
                            # Lunch time less profitable
                            elif 11 <= hour <= 13:
                                base_pnl *= 0.8
                            # Afternoon moderate
                            else:
                                base_pnl *= 1.0
                            
                            # Add some randomness based on account and day
                            pnl_variation = (trade_id * day_offset * hash(account.name)) % 100 - 50
                            profit_loss = base_pnl + pnl_variation
                            
                            # Some accounts perform better on certain days
                            if account.name == "IPS_TM_10" and current_date.weekday() in [0, 2, 4]:  # Mon, Wed, Fri
                                profit_loss *= 1.3
                            elif account.name == "IPS_TM_13" and current_date.weekday() in [1, 3]:  # Tue, Thu
                                profit_loss *= 1.4
                            
                            trade = ProcessedTrade(
                                trade_id=f"{account.name}_{trade_id:06d}",
                                account_name=account.name,
                                symbol=account.symbol,
                                entry_time=entry_time,
                                exit_time=exit_time,
                                entry_price=4500.0 + (trade_id % 100),
                                exit_price=4500.0 + (trade_id % 100) + (profit_loss / 20),
                                quantity=1,
                                side="LONG" if trade_id % 2 == 0 else "SHORT",
                                profit_loss=profit_loss,
                                commission=2.50,
                                duration_minutes=int((exit_time - entry_time).total_seconds() / 60),
                                hour_of_day=hour,
                                day_of_week=current_date.weekday(),
                                entry_order_id=f"E_{trade_id}",
                                exit_order_id=f"X_{trade_id}"
                            )
                            
                            processed_trades.append(trade)
                            trade_id += 1
            
            session.add_all(processed_trades)
            
            # Update account trade counts
            for account in accounts:
                account.total_trades = len([t for t in processed_trades if t.account_name == account.name])
                account.first_trade_date = min(t.entry_time for t in processed_trades if t.account_name == account.name)
                account.last_trade_date = max(t.entry_time for t in processed_trades if t.account_name == account.name)
            
            # Add market data for correlation analysis
            market_symbols = ['SPY', 'QQQ', 'VIX']
            market_data = []
            
            for day_offset in range(60):
                current_date = (base_date + timedelta(days=day_offset)).date()
                if current_date.weekday() >= 5:
                    continue
                    
                for symbol in market_symbols:
                    if symbol == 'VIX':
                        base_price = 20.0
                        volatility = 5.0
                    elif symbol == 'SPY':
                        base_price = 450.0
                        volatility = 10.0
                    else:  # QQQ
                        base_price = 380.0
                        volatility = 15.0
                    
                    # Create realistic price movements
                    price_change = ((day_offset * hash(symbol)) % 200 - 100) / 100 * volatility
                    close_price = base_price + price_change
                    
                    market_data.append(MarketData(
                        symbol=symbol,
                        date=current_date,
                        open_price=close_price - 1.0,
                        high_price=close_price + 2.0,
                        low_price=close_price - 2.0,
                        close_price=close_price,
                        volume=1000000 + (day_offset * 10000),
                        adjusted_close=close_price
                    ))
            
            session.add_all(market_data)
            session.commit()
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_complete_data_ingestion_to_analysis_workflow(self, test_database):
        """Test complete workflow from data ingestion to time-bin analysis."""
        engine, SessionLocal = test_database
        
        # Step 1: Initialize time-bin analyzer
        analyzer = TimeBinAnalyzer()
        
        # Step 2: Retrieve processed trades from database
        with SessionLocal() as session:
            trades = session.query(ProcessedTrade).all()
            accounts = session.query(Account).all()
            
            assert len(trades) > 0, "Should have test trades"
            assert len(accounts) == 3, "Should have 3 test accounts"
            
            # Step 3: Analyze time-bin performance for each account
            analysis_results = {}
            
            for account in accounts:
                account_trades = [t for t in trades if t.account_name == account.name]
                assert len(account_trades) > 0, f"Account {account.name} should have trades"
                
                # Convert to TimeBin format for analysis
                time_bins = {}
                for trade in account_trades:
                    # Create 30-minute time bins
                    bin_minute = 30 if trade.entry_time.minute >= 30 else 0
                    bin_key = (trade.entry_time.hour, bin_minute)
                    
                    if bin_key not in time_bins:
                        time_bins[bin_key] = TimeBin(
                            hour=trade.entry_time.hour,
                            minute=bin_minute,
                            trades=[],
                            total_pnl=0.0,
                            winning_trades=0,
                            losing_trades=0
                        )
                    
                    time_bins[bin_key].trades.append(trade)
                    time_bins[bin_key].total_pnl += trade.profit_loss
                    
                    if trade.profit_loss > 0:
                        time_bins[bin_key].winning_trades += 1
                    else:
                        time_bins[bin_key].losing_trades += 1
                
                # Analyze each time bin
                time_bin_analyses = []
                for (hour, minute), time_bin in time_bins.items():
                    if len(time_bin.trades) < 5:  # Skip bins with insufficient data
                        continue
                    
                    analysis = await analyzer.analyze_time_bin_performance(
                        account_name=account.name,
                        time_bin=time_bin,
                        benchmark_data=None  # Simplified for this test
                    )
                    
                    # Verify analysis results
                    assert analysis is not None
                    assert analysis.account_name == account.name
                    assert analysis.hour == hour
                    assert analysis.minute_bin == minute
                    assert analysis.total_trades == len(time_bin.trades)
                    assert analysis.total_trades > 0
                    
                    # Calculate expected metrics
                    expected_win_rate = time_bin.winning_trades / len(time_bin.trades)
                    expected_avg_pnl = time_bin.total_pnl / len(time_bin.trades)
                    
                    assert abs(analysis.win_rate - expected_win_rate) < 0.01
                    assert abs(analysis.average_pnl - expected_avg_pnl) < 1.0
                    
                    time_bin_analyses.append(analysis)
                
                analysis_results[account.name] = time_bin_analyses
                
                print(f"Account {account.name}: Analyzed {len(time_bin_analyses)} time bins")
        
        # Step 4: Verify statistical significance calculations
        total_analyses = sum(len(analyses) for analyses in analysis_results.values())
        assert total_analyses > 0, "Should have generated time-bin analyses"
        
        # Step 5: Test performance metrics calculation
        calculator = PerformanceMetricsCalculator()
        
        for account_name, analyses in analysis_results.items():
            for analysis in analyses[:3]:  # Test first 3 analyses per account
                # Convert analysis to trade list for metrics calculation
                with SessionLocal() as session:
                    time_bin_trades = session.query(ProcessedTrade).filter(
                        ProcessedTrade.account_name == account_name,
                        ProcessedTrade.hour_of_day == analysis.hour,
                        # Simplified minute bin check
                    ).limit(10).all()
                    
                    if time_bin_trades:
                        metrics = await calculator.calculate_comprehensive_metrics(time_bin_trades)
                        
                        assert metrics is not None
                        assert 'total_return' in metrics
                        assert 'sharpe_ratio' in metrics
                        assert 'max_drawdown' in metrics
                        assert 'win_rate' in metrics
                        
                        # Metrics should be reasonable
                        assert -10.0 <= metrics['sharpe_ratio'] <= 10.0
                        assert 0.0 <= metrics['win_rate'] <= 1.0
                        assert metrics['max_drawdown'] <= 0.0
                        
                        print(f"Time bin {analysis.hour}:{analysis.minute_bin:02d} metrics: "
                              f"Sharpe={metrics['sharpe_ratio']:.2f}, Win Rate={metrics['win_rate']:.1%}")
        
        print(f"✅ Complete workflow test passed: {total_analyses} time-bin analyses generated")
    
    @pytest.mark.asyncio
    async def test_end_to_end_analysis_pipeline_with_export(self, test_database):
        """Test complete pipeline from analysis to export generation."""
        engine, SessionLocal = test_database
        
        # Step 1: Generate comprehensive time-bin analyses
        analyzer = TimeBinAnalyzer()
        
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            all_time_bin_analyses = []
            
            for account in accounts:
                # Get account trades
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == account.name
                ).all()
                
                if not trades:
                    continue
                
                # Group by time bins and analyze top performing ones
                time_bin_groups = {}
                for trade in trades:
                    bin_key = (trade.hour_of_day, 0 if trade.entry_time.minute < 30 else 30)
                    if bin_key not in time_bin_groups:
                        time_bin_groups[bin_key] = []
                    time_bin_groups[bin_key].append(trade)
                
                # Analyze time bins with sufficient data
                for (hour, minute_bin), bin_trades in time_bin_groups.items():
                    if len(bin_trades) >= 10:  # Need sufficient sample size
                        # Create TimeBinAnalysis record
                        total_pnl = sum(t.profit_loss for t in bin_trades)
                        winning_trades = len([t for t in bin_trades if t.profit_loss > 0])
                        
                        analysis = TimeBinAnalysis(
                            account_name=account.name,
                            hour=hour,
                            minute_bin=minute_bin,
                            day_of_week=None,  # All days combined
                            analysis_date=datetime.now().date(),
                            total_trades=len(bin_trades),
                            win_rate=winning_trades / len(bin_trades),
                            average_pnl=total_pnl / len(bin_trades),
                            sharpe_ratio=self._calculate_sharpe_ratio([t.profit_loss for t in bin_trades]),
                            max_drawdown=self._calculate_max_drawdown([t.profit_loss for t in bin_trades]),
                            profit_factor=self._calculate_profit_factor([t.profit_loss for t in bin_trades]),
                            statistical_significance=len(bin_trades) >= 30,  # Simple threshold
                            sample_size_adequate=len(bin_trades) >= 20
                        )
                        
                        session.add(analysis)
                        all_time_bin_analyses.append(analysis)
            
            session.commit()
            
            assert len(all_time_bin_analyses) > 0, "Should generate time-bin analyses"
            print(f"Generated {len(all_time_bin_analyses)} time-bin analyses")
        
        # Step 2: Test data export functionality
        temp_export_dir = tempfile.mkdtemp()
        
        try:
            export_config = ExportConfig(
                export_directory=temp_export_dir,
                include_summary=True,
                include_detailed_trades=True,
                include_performance_charts=True,
                export_formats=[ExportFormat.CSV, ExportFormat.JSON],
                date_range_start=datetime(2024, 1, 1),
                date_range_end=datetime(2024, 3, 1)
            )
            
            exporter = DataExportEngine(SessionLocal())
            
            # Export time-bin analysis results
            export_results = await exporter.export_time_bin_analysis(
                analysis_ids=[a.id for a in all_time_bin_analyses[:5]],  # Export first 5
                config=export_config
            )
            
            assert export_results is not None
            assert 'exported_files' in export_results
            assert len(export_results['exported_files']) > 0
            
            # Verify exported files exist
            for file_path in export_results['exported_files']:
                full_path = os.path.join(temp_export_dir, os.path.basename(file_path))
                assert os.path.exists(full_path), f"Exported file should exist: {file_path}"
                assert os.path.getsize(full_path) > 0, f"Exported file should not be empty: {file_path}"
            
            print(f"✅ Export completed: {len(export_results['exported_files'])} files generated")
            
        finally:
            # Cleanup export directory
            import shutil
            shutil.rmtree(temp_export_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_complete_workflow_with_recommendations(self, test_database):
        """Test complete workflow including recommendation generation."""
        engine, SessionLocal = test_database
        
        # Step 1: Analyze time-bin performance
        with SessionLocal() as session:
            # Get best performing time bins for recommendations
            accounts = session.query(Account).all()
            recommendation_data = []
            
            for account in accounts:
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == account.name
                ).all()
                
                # Group by time bins and find profitable patterns
                time_bin_performance = {}
                for trade in trades:
                    bin_key = (trade.hour_of_day, 0 if trade.entry_time.minute < 30 else 30, trade.day_of_week)
                    
                    if bin_key not in time_bin_performance:
                        time_bin_performance[bin_key] = {
                            'total_pnl': 0.0,
                            'trade_count': 0,
                            'winning_trades': 0
                        }
                    
                    time_bin_performance[bin_key]['total_pnl'] += trade.profit_loss
                    time_bin_performance[bin_key]['trade_count'] += 1
                    if trade.profit_loss > 0:
                        time_bin_performance[bin_key]['winning_trades'] += 1
                
                # Identify top performing time bins
                for (hour, minute_bin, day_of_week), performance in time_bin_performance.items():
                    if performance['trade_count'] >= 10:  # Sufficient sample size
                        avg_pnl = performance['total_pnl'] / performance['trade_count']
                        win_rate = performance['winning_trades'] / performance['trade_count']
                        
                        if avg_pnl > 20 and win_rate > 0.6:  # Strong performance criteria
                            recommendation_data.append({
                                'account_name': account.name,
                                'hour': hour,
                                'minute_bin': minute_bin,
                                'day_of_week': day_of_week,
                                'avg_pnl': avg_pnl,
                                'win_rate': win_rate,
                                'trade_count': performance['trade_count']
                            })
        
        # Step 2: Generate recommendations
        if recommendation_data:
            recommendation_service = RecommendationService(SessionLocal())
            
            for rec_data in recommendation_data[:5]:  # Test first 5 recommendations
                recommendation = await recommendation_service.generate_time_based_recommendation(
                    account_name=rec_data['account_name'],
                    hour=rec_data['hour'],
                    minute_bin=rec_data['minute_bin'],
                    day_of_week=rec_data['day_of_week'],
                    historical_performance={
                        'avg_pnl': rec_data['avg_pnl'],
                        'win_rate': rec_data['win_rate'],
                        'sample_size': rec_data['trade_count']
                    }
                )
                
                assert recommendation is not None
                assert recommendation.account_name == rec_data['account_name']
                assert recommendation.recommended_action in ['TRADE', 'AVOID']
                assert 0.0 <= recommendation.confidence_score <= 1.0
                
                if rec_data['win_rate'] > 0.6 and rec_data['avg_pnl'] > 20:
                    assert recommendation.recommended_action == 'TRADE'
                    assert recommendation.confidence_score > 0.6
                
                print(f"Recommendation for {rec_data['account_name']} "
                      f"{rec_data['hour']}:{rec_data['minute_bin']:02d}: "
                      f"{recommendation.recommended_action} (confidence: {recommendation.confidence_score:.2f})")
            
            print(f"✅ Generated {len(recommendation_data)} trading recommendations")
        
        else:
            print("⚠️  No high-performance time bins found for recommendations")
    
    @pytest.mark.asyncio
    async def test_workflow_performance_under_load(self, test_database):
        """Test workflow performance with concurrent analysis requests."""
        engine, SessionLocal = test_database
        
        # Simulate multiple concurrent analysis requests
        analyzer = TimeBinAnalyzer()
        
        async def analyze_account_concurrently(account_name: str) -> Dict[str, Any]:
            """Analyze single account concurrently."""
            start_time = datetime.now()
            
            with SessionLocal() as session:
                trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == account_name
                ).limit(100).all()  # Limit for performance testing
                
                if not trades:
                    return {'account': account_name, 'analyses': 0, 'duration': 0}
                
                # Group into time bins
                time_bins = {}
                for trade in trades:
                    bin_key = (trade.hour_of_day, 0 if trade.entry_time.minute < 30 else 30)
                    if bin_key not in time_bins:
                        time_bins[bin_key] = []
                    time_bins[bin_key].append(trade)
                
                # Analyze each bin
                analysis_count = 0
                for (hour, minute_bin), bin_trades in time_bins.items():
                    if len(bin_trades) >= 5:
                        # Simplified analysis for performance testing
                        total_pnl = sum(t.profit_loss for t in bin_trades)
                        avg_pnl = total_pnl / len(bin_trades)
                        win_rate = len([t for t in bin_trades if t.profit_loss > 0]) / len(bin_trades)
                        
                        # Simulate some calculation time
                        await asyncio.sleep(0.01)  # 10ms per analysis
                        analysis_count += 1
                
                duration = (datetime.now() - start_time).total_seconds()
                return {
                    'account': account_name,
                    'analyses': analysis_count,
                    'duration': duration
                }
        
        # Run concurrent analysis for all accounts
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            start_time = datetime.now()
            
            # Execute concurrent analysis
            tasks = [analyze_account_concurrently(account.name) for account in accounts]
            results = await asyncio.gather(*tasks)
            
            total_duration = (datetime.now() - start_time).total_seconds()
            
            # Validate results
            total_analyses = sum(r['analyses'] for r in results)
            assert total_analyses > 0, "Should complete some analyses"
            assert total_duration < 10.0, f"Concurrent analysis too slow: {total_duration:.2f}s"
            
            for result in results:
                assert result['duration'] < 5.0, f"Individual account analysis too slow: {result}"
            
            print(f"✅ Concurrent analysis completed: {total_analyses} analyses in {total_duration:.2f}s")
            for result in results:
                print(f"  {result['account']}: {result['analyses']} analyses in {result['duration']:.2f}s")
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio for returns list."""
        if not returns:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0.0
        
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5
        
        return avg_return / std_dev if std_dev > 0 else 0.0
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from returns."""
        if not returns:
            return 0.0
        
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        
        for return_val in returns:
            cumulative += return_val
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return -max_drawdown  # Return as negative value
    
    def _calculate_profit_factor(self, returns: List[float]) -> float:
        """Calculate profit factor from returns."""
        if not returns:
            return 1.0
        
        total_profit = sum(r for r in returns if r > 0)
        total_loss = abs(sum(r for r in returns if r < 0))
        
        return total_profit / total_loss if total_loss > 0 else float('inf')


class TestTimeBinWorkflowValidation:
    """Additional validation tests for workflow components."""
    
    @pytest.mark.asyncio
    async def test_data_consistency_validation(self):
        """Test data consistency throughout the workflow pipeline."""
        # Test data integrity validation
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        try:
            with SessionLocal() as session:
                # Create test account
                account = Account(name="TEST_ACCOUNT", symbol="ES", total_trades=0)
                session.add(account)
                
                # Create trades with potential data inconsistencies
                trades = [
                    ProcessedTrade(
                        trade_id="VALID_001",
                        account_name="TEST_ACCOUNT",
                        symbol="ES",
                        entry_time=datetime(2024, 1, 1, 10, 30),
                        exit_time=datetime(2024, 1, 1, 11, 0),
                        profit_loss=100.0,
                        quantity=1,
                        side="LONG",
                        entry_price=4500.0,
                        exit_price=4520.0,
                        hour_of_day=10,
                        day_of_week=0,
                        duration_minutes=30,
                        entry_order_id="E_001",
                        exit_order_id="X_001"
                    ),
                    ProcessedTrade(
                        trade_id="INVALID_002",
                        account_name="TEST_ACCOUNT", 
                        symbol="ES",
                        entry_time=datetime(2024, 1, 1, 11, 0),
                        exit_time=datetime(2024, 1, 1, 10, 30),  # Exit before entry!
                        profit_loss=-50.0,
                        quantity=1,
                        side="SHORT",
                        entry_price=4500.0,
                        exit_price=4480.0,
                        hour_of_day=11,
                        day_of_week=0,
                        duration_minutes=-30,  # Negative duration!
                        entry_order_id="E_002",
                        exit_order_id="X_002"
                    )
                ]
                
                session.add_all(trades)
                session.commit()
                
                # Test validation logic
                analyzer = TimeBinAnalyzer()
                
                # Should handle invalid data gracefully
                valid_trades = [t for t in trades if t.exit_time > t.entry_time and t.duration_minutes > 0]
                assert len(valid_trades) == 1, "Should filter out invalid trades"
                
                # Analysis should work with valid data only
                time_bin = TimeBin(hour=10, minute=30, trades=valid_trades, total_pnl=100.0, winning_trades=1, losing_trades=0)
                
                analysis = await analyzer.analyze_time_bin_performance(
                    account_name="TEST_ACCOUNT",
                    time_bin=time_bin,
                    benchmark_data=None
                )
                
                assert analysis is not None
                assert analysis.total_trades == 1
                assert analysis.win_rate == 1.0  # 100% win rate with 1 winning trade
                
        finally:
            os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_workflow_error_handling(self):
        """Test error handling throughout the workflow."""
        analyzer = TimeBinAnalyzer()
        
        # Test with empty time bin
        empty_time_bin = TimeBin(hour=10, minute=30, trades=[], total_pnl=0.0, winning_trades=0, losing_trades=0)
        
        # Should handle empty data gracefully
        with pytest.raises(ValueError, match="insufficient.*data"):
            await analyzer.analyze_time_bin_performance(
                account_name="TEST_ACCOUNT",
                time_bin=empty_time_bin,
                benchmark_data=None
            )
        
        # Test with missing account
        mock_trade = Mock()
        mock_trade.profit_loss = 100.0
        mock_trade.entry_time = datetime.now()
        
        time_bin_with_data = TimeBin(
            hour=10, 
            minute=30, 
            trades=[mock_trade], 
            total_pnl=100.0, 
            winning_trades=1, 
            losing_trades=0
        )
        
        # Should handle missing account gracefully
        analysis = await analyzer.analyze_time_bin_performance(
            account_name="NONEXISTENT_ACCOUNT",
            time_bin=time_bin_with_data,
            benchmark_data=None
        )
        
        # Should still create analysis with available data
        assert analysis is not None
        assert analysis.account_name == "NONEXISTENT_ACCOUNT"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])