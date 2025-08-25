"""
Large dataset processing performance tests for trading analytics platform.

This module tests system performance with years of historical data including:
- Multi-year trade dataset processing
- Large-scale time-bin analysis with millions of trades
- Memory efficiency with massive datasets
- Query optimization for historical data analysis
- Batch processing performance validation

Requirements: 14.1, 14.2, 14.4, 8.1
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import time
import psutil
import gc
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Generator
from unittest.mock import Mock, patch
import statistics
import json
import numpy as np
from dataclasses import dataclass
import sys

# Import components for large dataset testing
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.models.time_bin_analytics import TimeBinAnalysis, MarketData
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer
from trading_platform.services.performance_metrics_calculator import PerformanceMetricsCalculator
from trading_platform.services.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.services.walk_forward_validator import WalkForwardValidator
from trading_platform.services.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
from trading_platform.services.data_export_engine import DataExportEngine
from trading_platform.services.database.query_optimizer import QueryOptimizer
from trading_platform.services.database.connection_pool_manager import ConnectionPoolManager
from trading_platform.database.base import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@dataclass
class DatasetMetrics:
    """Metrics for dataset size and processing performance."""
    total_trades: int
    total_accounts: int
    date_range_days: int
    processing_time: float
    memory_usage_mb: float
    query_count: int
    avg_query_time: float


class LargeDatasetGenerator:
    """Generate large-scale trading datasets for performance testing."""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        
    def generate_multi_year_dataset(self, 
                                   num_accounts: int = 20,
                                   years: int = 3,
                                   trades_per_account_per_day: Tuple[int, int] = (10, 50)) -> DatasetMetrics:
        """Generate multi-year trading dataset."""
        start_time = time.time()
        start_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        print(f"Generating {years}-year dataset for {num_accounts} accounts...")
        
        with self.session_factory() as session:
            # Create accounts with realistic trading patterns
            accounts = []
            for i in range(num_accounts):
                account_type = ["SCALPER", "SWING", "MOMENTUM", "MEAN_REVERSION", "BREAKOUT"][i % 5]
                symbol = ["ES", "NQ", "YM", "RTY", "GC"][i % 5]
                
                account = Account(
                    name=f"{account_type}_{i+1:03d}",
                    symbol=symbol,
                    total_trades=0,
                    is_active=True
                )
                accounts.append(account)
            
            session.add_all(accounts)
            session.flush()  # Get account IDs
            
            # Generate market data for the entire period
            base_date = datetime(2021, 1, 1)
            total_days = years * 365
            market_data = []
            
            print(f"Generating {total_days} days of market data...")
            
            symbols_data = {
                'SPY': {'base_price': 350, 'volatility': 0.02, 'trend': 0.0003},
                'QQQ': {'base_price': 280, 'volatility': 0.025, 'trend': 0.0004},
                'VIX': {'base_price': 20, 'volatility': 0.05, 'trend': -0.00005},
                'GLD': {'base_price': 170, 'volatility': 0.015, 'trend': 0.0001},
                'TLT': {'base_price': 140, 'volatility': 0.02, 'trend': -0.0002}
            }
            
            # Generate market data in batches to manage memory
            batch_size = 1000
            for day_batch_start in range(0, total_days, batch_size):
                batch_end = min(day_batch_start + batch_size, total_days)
                batch_market_data = []
                
                for day_offset in range(day_batch_start, batch_end):
                    current_date = (base_date + timedelta(days=day_offset))
                    
                    # Skip weekends
                    if current_date.weekday() >= 5:
                        continue
                        
                    date_obj = current_date.date()
                    
                    for symbol, config in symbols_data.items():
                        # Generate realistic price movement
                        trend_component = day_offset * config['trend']
                        cycle_component = np.sin(day_offset * 2 * np.pi / 252) * config['base_price'] * 0.05  # Annual cycle
                        noise_component = np.random.normal(0, config['base_price'] * config['volatility'])
                        
                        close_price = config['base_price'] + trend_component + cycle_component + noise_component
                        
                        # Ensure VIX stays in reasonable range
                        if symbol == 'VIX':
                            close_price = max(10, min(80, close_price))
                        
                        # Calculate OHLC
                        daily_range = abs(noise_component) + config['base_price'] * config['volatility']
                        open_price = close_price + np.random.normal(0, daily_range * 0.3)
                        high_price = max(open_price, close_price) + abs(np.random.normal(0, daily_range * 0.5))
                        low_price = min(open_price, close_price) - abs(np.random.normal(0, daily_range * 0.5))
                        
                        volume = 50000000 if symbol in ['SPY', 'QQQ'] else 10000000
                        if symbol == 'VIX':
                            volume = 0  # VIX doesn't have volume
                        
                        batch_market_data.append(MarketData(
                            symbol=symbol,
                            date=date_obj,
                            open_price=open_price,
                            high_price=high_price,
                            low_price=low_price,
                            close_price=close_price,
                            volume=volume,
                            adjusted_close=close_price
                        ))
                
                # Add batch to database
                session.add_all(batch_market_data)
                if day_batch_start % (batch_size * 10) == 0:  # Commit every 10 batches
                    session.commit()
                    print(f"  Market data progress: {day_batch_start}/{total_days} days")
            
            session.commit()
            print("Market data generation completed")
            
            # Generate trading data for each account
            total_trades_generated = 0
            trade_id_counter = 1
            
            print("Generating trading data...")
            
            for account_idx, account in enumerate(accounts):
                account_trades = []
                account_type = account.name.split('_')[0]
                
                # Different trading patterns by account type
                trading_params = {
                    'SCALPER': {'trades_per_day': (20, 80), 'win_rate': 0.55, 'avg_trade_time': 15},
                    'SWING': {'trades_per_day': (1, 5), 'win_rate': 0.65, 'avg_trade_time': 2880},
                    'MOMENTUM': {'trades_per_day': (5, 20), 'win_rate': 0.60, 'avg_trade_time': 240},
                    'MEAN_REVERSION': {'trades_per_day': (8, 25), 'win_rate': 0.58, 'avg_trade_time': 120},
                    'BREAKOUT': {'trades_per_day': (3, 12), 'win_rate': 0.62, 'avg_trade_time': 480}
                }
                
                params = trading_params[account_type]
                
                # Generate trades for account across entire time period
                for day_offset in range(total_days):
                    trade_date = base_date + timedelta(days=day_offset)
                    
                    # Skip weekends and some random days (vacation, etc.)
                    if trade_date.weekday() >= 5 or np.random.random() < 0.05:
                        continue
                    
                    # Determine number of trades for this day
                    daily_trades = np.random.randint(params['trades_per_day'][0], params['trades_per_day'][1] + 1)
                    
                    for trade_num in range(daily_trades):
                        # Generate realistic trade times
                        hour = np.random.randint(9, 16)  # Market hours
                        minute = np.random.randint(0, 60)
                        second = np.random.randint(0, 60)
                        
                        entry_time = trade_date.replace(hour=hour, minute=minute, second=second)
                        
                        # Generate trade duration based on account type
                        base_duration = params['avg_trade_time']
                        duration_variance = base_duration * 0.5
                        duration_minutes = max(1, int(np.random.normal(base_duration, duration_variance)))
                        exit_time = entry_time + timedelta(minutes=duration_minutes)
                        
                        # Ensure exit time is within market hours
                        if exit_time.hour >= 16:
                            exit_time = trade_date.replace(hour=15, minute=59)
                        
                        # Generate P&L based on account performance and market conditions
                        base_pnl = self._calculate_realistic_pnl(
                            account_type, day_offset, trade_date, params['win_rate']
                        )
                        
                        # Add some correlation with market volatility
                        market_vol_factor = np.random.normal(1.0, 0.2)
                        final_pnl = base_pnl * market_vol_factor
                        
                        # Generate realistic entry/exit prices
                        base_price = 4500.0  # ES contract
                        if account.symbol == 'NQ':
                            base_price = 13000.0
                        elif account.symbol == 'YM':
                            base_price = 33000.0
                        elif account.symbol == 'RTY':
                            base_price = 2000.0
                        elif account.symbol == 'GC':
                            base_price = 1800.0
                        
                        entry_price = base_price + np.random.normal(0, base_price * 0.001)
                        
                        if final_pnl > 0:
                            exit_price = entry_price + (abs(final_pnl) / 20)
                            side = "LONG"
                        else:
                            exit_price = entry_price - (abs(final_pnl) / 20)
                            side = "SHORT"
                        
                        trade = ProcessedTrade(
                            trade_id=f"LARGE_{trade_id_counter:010d}",
                            account_name=account.name,
                            symbol=account.symbol,
                            entry_time=entry_time,
                            exit_time=exit_time,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            quantity=1,
                            side=side,
                            profit_loss=final_pnl,
                            commission=2.50,
                            duration_minutes=duration_minutes,
                            hour_of_day=hour,
                            day_of_week=trade_date.weekday(),
                            entry_order_id=f"E_{trade_id_counter}",
                            exit_order_id=f"X_{trade_id_counter}"
                        )
                        
                        account_trades.append(trade)
                        trade_id_counter += 1
                
                # Add trades in batches
                batch_size = 10000
                for i in range(0, len(account_trades), batch_size):
                    batch = account_trades[i:i + batch_size]
                    session.add_all(batch)
                    
                    if i % (batch_size * 5) == 0:  # Commit every 50k trades
                        session.commit()
                        print(f"  Account {account.name}: {i + len(batch)}/{len(account_trades)} trades")
                
                # Update account statistics
                account.total_trades = len(account_trades)
                if account_trades:
                    account.first_trade_date = min(t.entry_time for t in account_trades)
                    account.last_trade_date = max(t.entry_time for t in account_trades)
                
                total_trades_generated += len(account_trades)
                session.commit()
                
                print(f"Account {account.name} completed: {len(account_trades)} trades")
                
                # Force garbage collection between accounts
                gc.collect()
        
        end_time = time.time()
        end_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        metrics = DatasetMetrics(
            total_trades=total_trades_generated,
            total_accounts=num_accounts,
            date_range_days=total_days,
            processing_time=end_time - start_time,
            memory_usage_mb=end_memory - start_memory,
            query_count=0,  # Will be updated during testing
            avg_query_time=0.0
        )
        
        print(f"Dataset generation completed:")
        print(f"  Total trades: {total_trades_generated:,}")
        print(f"  Total accounts: {num_accounts}")
        print(f"  Date range: {total_days} days ({years} years)")
        print(f"  Generation time: {metrics.processing_time:.1f} seconds")
        print(f"  Memory used: {metrics.memory_usage_mb:.1f} MB")
        
        return metrics
    
    def _calculate_realistic_pnl(self, account_type: str, day_offset: int, 
                                trade_date: datetime, win_rate: float) -> float:
        """Calculate realistic P&L based on account type and market conditions."""
        
        # Base P&L ranges by account type
        pnl_ranges = {
            'SCALPER': (-15, 25),      # Small moves, frequent
            'SWING': (-150, 300),      # Larger moves, less frequent
            'MOMENTUM': (-80, 120),    # Medium moves
            'MEAN_REVERSION': (-60, 90),  # Medium moves
            'BREAKOUT': (-100, 200)    # Variable moves
        }
        
        min_pnl, max_pnl = pnl_ranges[account_type]
        
        # Market condition influence (simulate market cycles)
        market_cycle = np.sin(day_offset * 2 * np.pi / 252)  # Annual cycle
        trend_factor = 1.0 + market_cycle * 0.2
        
        # Determine if trade is winner or loser
        is_winner = np.random.random() < win_rate
        
        if is_winner:
            # Winner: typically smaller gains to maintain realistic profit factor
            pnl = np.random.uniform(5, max_pnl * 0.7) * trend_factor
        else:
            # Loser: can have larger losses
            pnl = np.random.uniform(min_pnl, -5) * trend_factor
        
        # Add some random noise
        pnl += np.random.normal(0, abs(pnl) * 0.1)
        
        return pnl


class TestLargeDatasetProcessing:
    """Test performance with large-scale historical datasets."""
    
    @pytest.fixture
    async def large_dataset_database(self):
        """Create database with multi-year trading data."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        # Use SQLite with performance optimizations
        engine = create_engine(
            f"sqlite:///{temp_db.name}",
            echo=False,
            connect_args={
                'timeout': 60,
                'check_same_thread': False
            },
            pool_pre_ping=True
        )
        
        # Apply SQLite performance optimizations
        with engine.connect() as conn:
            conn.execute(text("PRAGMA synchronous = OFF"))
            conn.execute(text("PRAGMA journal_mode = MEMORY"))
            conn.execute(text("PRAGMA temp_store = MEMORY"))
            conn.execute(text("PRAGMA cache_size = -64000"))  # 64MB cache
            conn.execute(text("PRAGMA mmap_size = 268435456"))  # 256MB mmap
            conn.commit()
        
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        # Generate large dataset
        generator = LargeDatasetGenerator(SessionLocal)
        dataset_metrics = generator.generate_multi_year_dataset(
            num_accounts=15,  # 15 accounts
            years=2,          # 2 years of data
            trades_per_account_per_day=(8, 40)  # 8-40 trades per day
        )
        
        yield engine, SessionLocal, dataset_metrics
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_large_scale_time_bin_analysis(self, large_dataset_database):
        """Test time-bin analysis performance with large datasets."""
        engine, SessionLocal, dataset_metrics = large_dataset_database
        
        print(f"\nTesting time-bin analysis with {dataset_metrics.total_trades:,} trades...")
        
        start_time = time.time()
        start_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        analyzer = TimeBinAnalyzer(SessionLocal())
        query_optimizer = QueryOptimizer(SessionLocal())
        
        # Test comprehensive time-bin analysis across multiple accounts
        with SessionLocal() as session:
            accounts = session.query(Account).limit(5).all()  # Test with 5 accounts
        
        analysis_results = []
        query_count = 0
        total_query_time = 0
        
        for account in accounts:
            account_start = time.time()
            
            # Analyze multiple time bins for each account
            time_bins = [
                (9, 0), (9, 15), (9, 30), (9, 45),
                (10, 0), (10, 15), (10, 30), (10, 45),
                (11, 0), (11, 15), (11, 30), (11, 45),
                (12, 0), (12, 15), (12, 30), (12, 45),
                (13, 0), (13, 15), (13, 30), (13, 45),
                (14, 0), (14, 15), (14, 30), (14, 45),
                (15, 0), (15, 15), (15, 30), (15, 45)
            ]
            
            account_results = []
            for hour, minute_bin in time_bins:
                query_start = time.time()
                
                result = await analyzer.analyze_time_bin_performance(
                    account_name=account.name,
                    hour=hour,
                    minute_bin=minute_bin,
                    start_date=datetime(2021, 1, 1).date(),
                    end_date=datetime(2023, 1, 1).date()
                )
                
                query_time = time.time() - query_start
                total_query_time += query_time
                query_count += 1
                
                if result['total_trades'] > 0:  # Only include active time bins
                    account_results.append({
                        'account_name': account.name,
                        'hour': hour,
                        'minute_bin': minute_bin,
                        'total_trades': result['total_trades'],
                        'win_rate': result['win_rate'],
                        'avg_pnl': result['average_pnl'],
                        'sharpe_ratio': result.get('sharpe_ratio', 0),
                        'query_time': query_time
                    })
            
            analysis_results.extend(account_results)
            account_time = time.time() - account_start
            
            print(f"  {account.name}: {len(account_results)} active time bins, {account_time:.2f}s")
        
        end_time = time.time()
        end_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        # Performance analysis
        total_time = end_time - start_time
        memory_used = end_memory - start_memory
        avg_query_time = total_query_time / query_count if query_count > 0 else 0
        throughput = query_count / total_time
        
        print(f"\nLarge-scale Time-bin Analysis Results:")
        print(f"  Total trades processed: {dataset_metrics.total_trades:,}")
        print(f"  Active time bins found: {len(analysis_results)}")
        print(f"  Total queries executed: {query_count}")
        print(f"  Total processing time: {total_time:.2f} seconds")
        print(f"  Average query time: {avg_query_time:.3f} seconds")
        print(f"  Query throughput: {throughput:.1f} queries/second")
        print(f"  Memory used: {memory_used:.1f} MB")
        
        # Validate significant time bins
        significant_bins = [r for r in analysis_results if r['total_trades'] >= 50]
        print(f"  Significant time bins (50+ trades): {len(significant_bins)}")
        
        # Performance assertions for large datasets
        assert len(analysis_results) > 0, "Should find active time bins"
        assert avg_query_time <= 15.0, f"Average query time too high for large dataset: {avg_query_time:.3f}s"
        assert throughput >= 1.0, f"Query throughput too low: {throughput:.1f} queries/second"
        assert memory_used <= 500, f"Memory usage too high: {memory_used:.1f} MB"
        
        # Validate data quality
        if significant_bins:
            avg_win_rate = sum(r['win_rate'] for r in significant_bins) / len(significant_bins)
            print(f"  Average win rate across significant bins: {avg_win_rate:.1%}")
            assert 0.3 <= avg_win_rate <= 0.8, f"Unrealistic average win rate: {avg_win_rate:.1%}"
    
    @pytest.mark.asyncio
    async def test_historical_performance_metrics(self, large_dataset_database):
        """Test performance metrics calculation with multi-year data."""
        engine, SessionLocal, dataset_metrics = large_dataset_database
        
        print(f"\nTesting performance metrics with {dataset_metrics.total_trades:,} trades...")
        
        calculator = PerformanceMetricsCalculator(SessionLocal())
        
        start_time = time.time()
        start_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        with SessionLocal() as session:
            accounts = session.query(Account).limit(3).all()  # Test with 3 accounts
        
        metrics_results = []
        
        for account in accounts:
            account_start = time.time()
            
            # Calculate comprehensive metrics for entire historical period
            metrics = await calculator.calculate_comprehensive_metrics(
                account_name=account.name,
                start_date=datetime(2021, 1, 1).date(),
                end_date=datetime(2023, 1, 1).date()
            )
            
            account_time = time.time() - account_start
            
            metrics_results.append({
                'account_name': account.name,
                'metrics': metrics,
                'calculation_time': account_time
            })
            
            print(f"  {account.name}: {metrics['total_trades']} trades, {account_time:.2f}s")
            print(f"    Total P&L: ${metrics['total_pnl']:,.2f}")
            print(f"    Win Rate: {metrics['win_rate']:.1%}")
            print(f"    Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            print(f"    Max Drawdown: ${metrics['max_drawdown']:,.2f}")
        
        end_time = time.time()
        end_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        total_time = end_time - start_time
        memory_used = end_memory - start_memory
        avg_calc_time = sum(r['calculation_time'] for r in metrics_results) / len(metrics_results)
        
        print(f"\nHistorical Performance Metrics Results:")
        print(f"  Accounts processed: {len(metrics_results)}")
        print(f"  Total processing time: {total_time:.2f} seconds")
        print(f"  Average calculation time per account: {avg_calc_time:.2f} seconds")
        print(f"  Memory used: {memory_used:.1f} MB")
        
        # Performance assertions
        assert avg_calc_time <= 30.0, f"Performance metrics calculation too slow: {avg_calc_time:.2f}s"
        assert memory_used <= 300, f"Memory usage too high: {memory_used:.1f} MB"
        
        # Validate metrics quality
        for result in metrics_results:
            metrics = result['metrics']
            assert metrics['total_trades'] > 1000, "Should have substantial trade data"
            assert 0.0 <= metrics['win_rate'] <= 1.0, "Win rate should be valid percentage"
            assert abs(metrics['sharpe_ratio']) <= 10.0, "Sharpe ratio should be reasonable"
    
    @pytest.mark.asyncio
    async def test_large_dataset_monte_carlo(self, large_dataset_database):
        """Test Monte Carlo simulation with large historical datasets."""
        engine, SessionLocal, dataset_metrics = large_dataset_database
        
        print(f"\nTesting Monte Carlo with {dataset_metrics.total_trades:,} trades...")
        
        simulator = MonteCarloSimulator(SessionLocal())
        
        start_time = time.time()
        start_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        with SessionLocal() as session:
            # Select account with most trades for Monte Carlo
            account = session.query(Account).order_by(Account.total_trades.desc()).first()
        
        print(f"Running Monte Carlo on {account.name} with {account.total_trades} trades...")
        
        # Run Monte Carlo with larger simulation count for large dataset
        result = await simulator.run_monte_carlo_analysis(
            account_name=account.name,
            num_simulations=1000,  # More simulations for large dataset
            confidence_levels=[0.90, 0.95, 0.99],
            risk_free_rate=0.02
        )
        
        end_time = time.time()
        end_memory = psutil.virtual_memory().used / (1024 * 1024)
        
        processing_time = end_time - start_time
        memory_used = end_memory - start_memory
        
        print(f"Monte Carlo Results:")
        print(f"  Simulations run: {result['simulations_run']}")
        print(f"  Processing time: {processing_time:.2f} seconds")
        print(f"  Memory used: {memory_used:.1f} MB")
        print(f"  Simulations per second: {result['simulations_run'] / processing_time:.1f}")
        
        # Display VaR results
        for confidence, var_value in result['var_estimates'].items():
            print(f"  VaR {confidence}: ${var_value:,.2f}")
        
        # Performance assertions for large dataset Monte Carlo
        assert processing_time <= 60.0, f"Monte Carlo too slow for large dataset: {processing_time:.2f}s"
        assert memory_used <= 400, f"Memory usage too high: {memory_used:.1f} MB"
        assert result['simulations_run'] == 1000, "Should complete all simulations"
        
        # Validate simulation quality
        performance_metrics = result['performance_metrics']
        assert performance_metrics['mean_return'] != 0, "Should have meaningful return statistics"
        assert performance_metrics['volatility'] > 0, "Should have positive volatility"
    
    @pytest.mark.asyncio
    async def test_batch_processing_efficiency(self, large_dataset_database):
        """Test batch processing efficiency with large datasets."""
        engine, SessionLocal, dataset_metrics = large_dataset_database
        
        print(f"\nTesting batch processing efficiency...")
        
        # Test different batch sizes for optimal performance
        batch_sizes = [100, 500, 1000, 2500, 5000]
        batch_results = []
        
        with SessionLocal() as session:
            # Get account with most trades
            account = session.query(Account).order_by(Account.total_trades.desc()).first()
        
        for batch_size in batch_sizes:
            print(f"Testing batch size: {batch_size}")
            
            start_time = time.time()
            start_memory = psutil.virtual_memory().used / (1024 * 1024)
            
            # Simulate batch processing of trades
            with SessionLocal() as session:
                total_processed = 0
                batch_count = 0
                
                # Process trades in batches
                offset = 0
                while True:
                    trades_batch = session.query(ProcessedTrade).filter(
                        ProcessedTrade.account_name == account.name
                    ).offset(offset).limit(batch_size).all()
                    
                    if not trades_batch:
                        break
                    
                    # Simulate processing (calculate some metrics)
                    batch_pnl = sum(t.profit_loss for t in trades_batch)
                    batch_winners = sum(1 for t in trades_batch if t.profit_loss > 0)
                    batch_win_rate = batch_winners / len(trades_batch) if trades_batch else 0
                    
                    total_processed += len(trades_batch)
                    batch_count += 1
                    offset += batch_size
                    
                    # Limit test to prevent excessive runtime
                    if total_processed >= 10000:  # Process max 10k trades per batch size test
                        break
            
            end_time = time.time()
            end_memory = psutil.virtual_memory().used / (1024 * 1024)
            
            processing_time = end_time - start_time
            memory_used = end_memory - start_memory
            throughput = total_processed / processing_time if processing_time > 0 else 0
            
            batch_results.append({
                'batch_size': batch_size,
                'trades_processed': total_processed,
                'batch_count': batch_count,
                'processing_time': processing_time,
                'memory_used': memory_used,
                'throughput': throughput
            })
            
            print(f"  Processed: {total_processed} trades in {batch_count} batches")
            print(f"  Time: {processing_time:.2f}s, Throughput: {throughput:.0f} trades/second")
            print(f"  Memory: {memory_used:.1f} MB")
        
        # Analyze optimal batch size
        print(f"\nBatch Processing Analysis:")
        best_throughput = max(batch_results, key=lambda x: x['throughput'])
        
        print(f"Optimal batch size for throughput: {best_throughput['batch_size']} ({best_throughput['throughput']:.0f} trades/second)")
        
        for result in batch_results:
            efficiency = result['throughput'] / best_throughput['throughput']
            print(f"  Batch {result['batch_size']:4d}: {result['throughput']:6.0f} trades/s ({efficiency:.1%} efficiency)")
        
        # Performance assertions
        assert best_throughput['throughput'] >= 1000, f"Best throughput too low: {best_throughput['throughput']:.0f} trades/second"
        assert any(r['memory_used'] <= 100 for r in batch_results), "Should have memory-efficient batch size options"
    
    @pytest.mark.asyncio
    async def test_query_optimization_large_dataset(self, large_dataset_database):
        """Test query optimization effectiveness with large datasets."""
        engine, SessionLocal, dataset_metrics = large_dataset_database
        
        print(f"\nTesting query optimization with large dataset...")
        
        optimizer = QueryOptimizer(SessionLocal())
        
        # Test different query patterns common in analytics
        test_queries = [
            {
                'name': 'Date range trades',
                'query': """
                    SELECT * FROM processed_trades 
                    WHERE entry_time >= '2021-06-01' AND entry_time <= '2021-12-31'
                    ORDER BY entry_time
                """,
                'expected_optimization': 'date_indexing'
            },
            {
                'name': 'Account performance',
                'query': """
                    SELECT account_name, COUNT(*) as trades, AVG(profit_loss) as avg_pnl
                    FROM processed_trades 
                    WHERE account_name LIKE 'SCALPER%'
                    GROUP BY account_name
                """,
                'expected_optimization': 'account_indexing'
            },
            {
                'name': 'Time-bin aggregation',
                'query': """
                    SELECT hour_of_day, AVG(profit_loss) as avg_pnl, COUNT(*) as trade_count
                    FROM processed_trades
                    WHERE entry_time >= '2021-01-01' AND profit_loss > 0
                    GROUP BY hour_of_day
                    ORDER BY hour_of_day
                """,
                'expected_optimization': 'time_bin_indexing'
            },
            {
                'name': 'Symbol analysis',
                'query': """
                    SELECT symbol, 
                           SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winners,
                           COUNT(*) as total_trades
                    FROM processed_trades
                    WHERE entry_time >= '2021-01-01'
                    GROUP BY symbol
                """,
                'expected_optimization': 'symbol_indexing'
            }
        ]
        
        optimization_results = []
        
        for test_query in test_queries:
            print(f"Testing: {test_query['name']}")
            
            # Test without optimization
            start_time = time.time()
            with SessionLocal() as session:
                result = session.execute(text(test_query['query'])).fetchall()
            unoptimized_time = time.time() - start_time
            
            # Test with optimization
            start_time = time.time()
            optimized_query = await optimizer._apply_query_optimizations(test_query['query'])
            with SessionLocal() as session:
                result_optimized = session.execute(text(optimized_query)).fetchall()
            optimized_time = time.time() - start_time
            
            improvement = (unoptimized_time - optimized_time) / unoptimized_time if unoptimized_time > 0 else 0
            
            optimization_results.append({
                'query_name': test_query['name'],
                'unoptimized_time': unoptimized_time,
                'optimized_time': optimized_time,
                'improvement': improvement,
                'results_count': len(result)
            })
            
            print(f"  Unoptimized: {unoptimized_time:.3f}s")
            print(f"  Optimized: {optimized_time:.3f}s")
            print(f"  Improvement: {improvement:.1%}")
            print(f"  Results: {len(result)} rows")
        
        print(f"\nQuery Optimization Summary:")
        total_improvement = sum(r['improvement'] for r in optimization_results) / len(optimization_results)
        print(f"Average improvement: {total_improvement:.1%}")
        
        # Performance assertions
        assert total_improvement >= 0.0, "Query optimization should not degrade performance"
        assert all(r['optimized_time'] <= 30.0 for r in optimization_results), "Optimized queries should be reasonably fast"
        
        # Report best and worst performing queries
        best_query = max(optimization_results, key=lambda x: x['improvement'])
        worst_query = min(optimization_results, key=lambda x: x['improvement'])
        
        print(f"Best optimization: {best_query['query_name']} ({best_query['improvement']:.1%} improvement)")
        print(f"Least improvement: {worst_query['query_name']} ({worst_query['improvement']:.1%} improvement)")
    
    @pytest.mark.asyncio
    async def test_memory_management_large_dataset(self, large_dataset_database):
        """Test memory management with large dataset operations."""
        engine, SessionLocal, dataset_metrics = large_dataset_database
        
        print(f"\nTesting memory management with large operations...")
        
        # Monitor memory usage during various operations
        memory_snapshots = []
        
        def snapshot_memory(operation_name: str):
            """Take memory snapshot."""
            process = psutil.Process()
            memory_info = process.memory_info()
            snapshot = {
                'operation': operation_name,
                'timestamp': time.time(),
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent()
            }
            memory_snapshots.append(snapshot)
            print(f"  Memory after {operation_name}: {snapshot['rss_mb']:.1f} MB ({snapshot['percent']:.1f}%)")
            return snapshot
        
        # Initial memory snapshot
        initial_memory = snapshot_memory("initial")
        
        # Test 1: Large query result processing
        with SessionLocal() as session:
            snapshot_memory("session_start")
            
            # Large query
            trades = session.query(ProcessedTrade).limit(5000).all()
            snapshot_memory("large_query")
            
            # Process results
            total_pnl = sum(t.profit_loss for t in trades)
            winners = [t for t in trades if t.profit_loss > 0]
            snapshot_memory("result_processing")
            
            # Clear variables
            del trades, winners
            gc.collect()
            snapshot_memory("after_cleanup")
        
        # Test 2: Multiple concurrent operations
        async def memory_intensive_operation(op_id: int):
            """Memory-intensive operation for testing."""
            with SessionLocal() as session:
                trades = session.query(ProcessedTrade).offset(op_id * 1000).limit(1000).all()
                
                # Simulate analytics processing
                daily_pnl = {}
                for trade in trades:
                    date = trade.entry_time.date()
                    if date not in daily_pnl:
                        daily_pnl[date] = []
                    daily_pnl[date].append(trade.profit_loss)
                
                # Calculate daily statistics
                daily_stats = {}
                for date, pnls in daily_pnl.items():
                    daily_stats[date] = {
                        'total_pnl': sum(pnls),
                        'avg_pnl': sum(pnls) / len(pnls),
                        'trade_count': len(pnls)
                    }
                
                return daily_stats
        
        # Run concurrent memory-intensive operations
        print("Running concurrent memory-intensive operations...")
        concurrent_tasks = [memory_intensive_operation(i) for i in range(5)]
        concurrent_results = await asyncio.gather(*concurrent_tasks)
        snapshot_memory("concurrent_operations")
        
        # Force garbage collection
        gc.collect()
        snapshot_memory("final_cleanup")
        
        # Analyze memory usage patterns
        peak_memory = max(s['rss_mb'] for s in memory_snapshots)
        final_memory = memory_snapshots[-1]['rss_mb']
        memory_growth = final_memory - initial_memory['rss_mb']
        
        print(f"\nMemory Management Analysis:")
        print(f"  Initial memory: {initial_memory['rss_mb']:.1f} MB")
        print(f"  Peak memory: {peak_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Net growth: {memory_growth:.1f} MB")
        print(f"  Peak/Initial ratio: {peak_memory / initial_memory['rss_mb']:.2f}x")
        
        # Memory management assertions
        assert memory_growth <= 200, f"Excessive memory growth: {memory_growth:.1f} MB"
        assert peak_memory / initial_memory['rss_mb'] <= 4.0, f"Peak memory usage too high: {peak_memory / initial_memory['rss_mb']:.2f}x"
        assert final_memory <= initial_memory['rss_mb'] * 2.0, f"Memory not properly cleaned up: {final_memory:.1f} MB vs initial {initial_memory['rss_mb']:.1f} MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])