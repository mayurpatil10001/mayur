"""
System load testing for trading analytics platform.

This module tests system performance under concurrent user load including:
- Multiple simultaneous analytics requests
- Concurrent time-bin analysis operations
- Database connection pool stress testing
- Memory and CPU usage validation under load
- Response time degradation analysis

Requirements: 14.1, 14.2, 14.4, 8.1
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import time
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, patch
import statistics
import json

# Import components for system load testing
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.models.time_bin_analytics import TimeBinAnalysis, MarketData
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer
from trading_platform.services.performance_metrics_calculator import PerformanceMetricsCalculator
from trading_platform.services.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.services.walk_forward_validator import WalkForwardValidator
from trading_platform.services.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
from trading_platform.services.data_export_engine import DataExportEngine
from trading_platform.services.pdf_report_generator import PDFReportGenerator
from trading_platform.services.database.connection_pool_manager import ConnectionPoolManager
from trading_platform.services.database.query_optimizer import QueryOptimizer
from trading_platform.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class SystemLoadTester:
    """System load testing coordinator."""
    
    def __init__(self, engine, session_factory):
        self.engine = engine
        self.session_factory = session_factory
        self.results = []
        self.start_time = None
        self.system_metrics = []
        
    def start_monitoring(self):
        """Start system resource monitoring."""
        self.start_time = time.time()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_system_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop system resource monitoring."""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_system_resources(self):
        """Monitor system resources continuously."""
        while self.monitoring:
            try:
                metrics = {
                    'timestamp': time.time(),
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'memory_used_gb': psutil.virtual_memory().used / (1024**3),
                    'disk_io_read': psutil.disk_io_counters().read_bytes if psutil.disk_io_counters() else 0,
                    'disk_io_write': psutil.disk_io_counters().write_bytes if psutil.disk_io_counters() else 0,
                    'network_sent': psutil.net_io_counters().bytes_sent if psutil.net_io_counters() else 0,
                    'network_recv': psutil.net_io_counters().bytes_recv if psutil.net_io_counters() else 0,
                    'active_connections': len(psutil.net_connections())
                }
                self.system_metrics.append(metrics)
                time.sleep(0.5)  # Monitor every 500ms
            except Exception as e:
                print(f"Monitoring error: {e}")
                break
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Generate performance summary from test results."""
        if not self.results:
            return {}
            
        response_times = [r['duration'] for r in self.results if 'duration' in r]
        success_count = sum(1 for r in self.results if r.get('success', False))
        error_count = len(self.results) - success_count
        
        cpu_usage = [m['cpu_percent'] for m in self.system_metrics]
        memory_usage = [m['memory_percent'] for m in self.system_metrics]
        
        return {
            'total_requests': len(self.results),
            'successful_requests': success_count,
            'failed_requests': error_count,
            'success_rate': success_count / len(self.results) if self.results else 0,
            'response_times': {
                'min': min(response_times) if response_times else 0,
                'max': max(response_times) if response_times else 0,
                'mean': statistics.mean(response_times) if response_times else 0,
                'median': statistics.median(response_times) if response_times else 0,
                'p95': statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else max(response_times) if response_times else 0,
                'p99': statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else max(response_times) if response_times else 0
            },
            'system_resources': {
                'max_cpu_percent': max(cpu_usage) if cpu_usage else 0,
                'avg_cpu_percent': statistics.mean(cpu_usage) if cpu_usage else 0,
                'max_memory_percent': max(memory_usage) if memory_usage else 0,
                'avg_memory_percent': statistics.mean(memory_usage) if memory_usage else 0,
                'peak_memory_gb': max(m['memory_used_gb'] for m in self.system_metrics) if self.system_metrics else 0
            },
            'throughput': {
                'requests_per_second': len(self.results) / (time.time() - self.start_time) if self.start_time else 0,
                'successful_requests_per_second': success_count / (time.time() - self.start_time) if self.start_time else 0
            }
        }


class TestSystemLoad:
    """Test system performance under concurrent load."""
    
    @pytest.fixture
    async def load_test_database(self):
        """Create database with substantial data for load testing."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            # Create multiple test accounts
            accounts = []
            for i in range(10):
                account = Account(
                    name=f"LOAD_TEST_ACCOUNT_{i+1:02d}",
                    symbol="ES" if i % 2 == 0 else "NQ",
                    total_trades=0,
                    is_active=True
                )
                accounts.append(account)
            session.add_all(accounts)
            
            # Generate substantial market data (180 days)
            base_date = datetime(2024, 1, 1)
            market_data = []
            
            for day in range(180):
                current_date = (base_date + timedelta(days=day))
                if current_date.weekday() >= 5:  # Skip weekends
                    continue
                    
                date_obj = current_date.date()
                
                # SPY data
                spy_price = 450 + day * 0.5 + (day % 30 - 15) * 2  # Trend with cycles
                market_data.append(MarketData(
                    symbol='SPY',
                    date=date_obj,
                    open_price=spy_price - 1,
                    high_price=spy_price + 3,
                    low_price=spy_price - 3,
                    close_price=spy_price,
                    volume=50000000,
                    adjusted_close=spy_price
                ))
                
                # QQQ data
                qqq_price = 380 + day * 0.7 + (day % 20 - 10) * 3
                market_data.append(MarketData(
                    symbol='QQQ',
                    date=date_obj,
                    open_price=qqq_price - 1.5,
                    high_price=qqq_price + 4,
                    low_price=qqq_price - 4,
                    close_price=qqq_price,
                    volume=30000000,
                    adjusted_close=qqq_price
                ))
                
                # VIX data
                vix_value = max(10, 25 - day * 0.05 + abs((day % 40) - 20))
                market_data.append(MarketData(
                    symbol='VIX',
                    date=date_obj,
                    open_price=vix_value - 0.5,
                    high_price=vix_value + 1,
                    low_price=vix_value - 1,
                    close_price=vix_value,
                    volume=0,
                    adjusted_close=vix_value
                ))
            
            session.add_all(market_data)
            
            # Generate substantial trading data for each account
            all_trades = []
            trade_id_counter = 1
            
            for account in accounts:
                # Generate 6 months of trading data per account
                for day_offset in range(120):
                    trade_date = base_date + timedelta(days=day_offset)
                    
                    if trade_date.weekday() >= 5:  # Skip weekends
                        continue
                    
                    # Generate 5-15 trades per day per account
                    daily_trades = 5 + (day_offset % 11)  # Varies between 5-15
                    
                    for trade_num in range(daily_trades):
                        hour = 9 + (trade_num % 7)  # Trading hours 9-15
                        minute = (trade_num * 7) % 60
                        
                        entry_time = trade_date.replace(hour=hour, minute=minute)
                        exit_time = entry_time + timedelta(minutes=15 + (trade_num % 45))
                        
                        # Generate realistic P&L with some patterns
                        base_pnl = (day_offset % 10 - 4) * 10  # Some trend
                        noise = (trade_id_counter % 21 - 10) * 5  # Random component
                        win_bias = 15 if trade_id_counter % 3 == 0 else -5  # 67% win rate
                        final_pnl = base_pnl + noise + win_bias
                        
                        trade = ProcessedTrade(
                            trade_id=f"LOAD_{trade_id_counter:08d}",
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
                            duration_minutes=(exit_time - entry_time).total_seconds() // 60,
                            hour_of_day=hour,
                            day_of_week=trade_date.weekday(),
                            entry_order_id=f"E_{trade_id_counter}",
                            exit_order_id=f"X_{trade_id_counter}"
                        )
                        
                        all_trades.append(trade)
                        trade_id_counter += 1
            
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
    async def test_concurrent_time_bin_analysis(self, load_test_database):
        """Test concurrent time-bin analysis operations."""
        engine, SessionLocal = load_test_database
        load_tester = SystemLoadTester(engine, SessionLocal)
        
        async def analyze_time_bin(account_name: str, hour: int, minute_bin: int) -> Dict[str, Any]:
            """Perform time-bin analysis for load testing."""
            start_time = time.time()
            success = True
            error_msg = None
            
            try:
                analyzer = TimeBinAnalyzer(SessionLocal())
                
                result = await analyzer.analyze_time_bin_performance(
                    account_name=account_name,
                    hour=hour,
                    minute_bin=minute_bin,
                    start_date=datetime(2024, 1, 1).date(),
                    end_date=datetime(2024, 4, 1).date()
                )
                
                # Validate result structure
                assert 'total_trades' in result
                assert 'win_rate' in result
                assert 'average_pnl' in result
                
            except Exception as e:
                success = False
                error_msg = str(e)
                result = None
            
            duration = time.time() - start_time
            
            return {
                'account_name': account_name,
                'hour': hour,
                'minute_bin': minute_bin,
                'duration': duration,
                'success': success,
                'error': error_msg,
                'result': result
            }
        
        # Start system monitoring
        load_tester.start_monitoring()
        
        try:
            # Generate concurrent requests
            with SessionLocal() as session:
                accounts = session.query(Account).limit(5).all()  # Use 5 accounts for testing
            
            tasks = []
            
            # Create 50 concurrent analysis tasks
            for i in range(50):
                account = accounts[i % len(accounts)]
                hour = 10 + (i % 6)  # Hours 10-15
                minute_bin = (i % 4) * 15  # 0, 15, 30, 45 minute bins
                
                tasks.append(analyze_time_bin(account.name, hour, minute_bin))
            
            # Execute concurrent analysis
            print(f"Starting {len(tasks)} concurrent time-bin analyses...")
            start_time = time.time()
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            execution_time = time.time() - start_time
            print(f"Completed {len(results)} analyses in {execution_time:.2f} seconds")
            
            # Process results
            successful_results = []
            failed_results = []
            
            for result in results:
                if isinstance(result, Exception):
                    failed_results.append({'error': str(result), 'success': False})
                else:
                    if result['success']:
                        successful_results.append(result)
                    else:
                        failed_results.append(result)
            
            load_tester.results = successful_results + failed_results
            
            # Validate performance requirements
            success_rate = len(successful_results) / len(results)
            avg_response_time = sum(r['duration'] for r in successful_results) / len(successful_results) if successful_results else 0
            throughput = len(successful_results) / execution_time
            
            print(f"Performance Results:")
            print(f"  Success Rate: {success_rate:.1%}")
            print(f"  Average Response Time: {avg_response_time:.3f}s")
            print(f"  Throughput: {throughput:.1f} analyses/second")
            print(f"  Failed Analyses: {len(failed_results)}")
            
            # Performance assertions
            assert success_rate >= 0.95, f"Success rate too low: {success_rate:.1%}"
            assert avg_response_time <= 5.0, f"Average response time too high: {avg_response_time:.3f}s"
            assert throughput >= 5.0, f"Throughput too low: {throughput:.1f} analyses/second"
            
        finally:
            load_tester.stop_monitoring()
            
        # Generate performance summary
        perf_summary = load_tester.get_performance_summary()
        print(f"System Resource Usage:")
        print(f"  Peak CPU: {perf_summary['system_resources']['max_cpu_percent']:.1f}%")
        print(f"  Peak Memory: {perf_summary['system_resources']['max_memory_percent']:.1f}%")
        print(f"  Peak Memory GB: {perf_summary['system_resources']['peak_memory_gb']:.2f}GB")
        
        # Resource usage assertions
        assert perf_summary['system_resources']['max_cpu_percent'] <= 90, "CPU usage too high"
        assert perf_summary['system_resources']['max_memory_percent'] <= 80, "Memory usage too high"
    
    @pytest.mark.asyncio
    async def test_concurrent_monte_carlo_simulations(self, load_test_database):
        """Test concurrent Monte Carlo simulation performance."""
        engine, SessionLocal = load_test_database
        load_tester = SystemLoadTester(engine, SessionLocal)
        
        async def run_monte_carlo_simulation(account_name: str, simulation_id: int) -> Dict[str, Any]:
            """Run Monte Carlo simulation for load testing."""
            start_time = time.time()
            success = True
            error_msg = None
            
            try:
                simulator = MonteCarloSimulator(SessionLocal())
                
                result = await simulator.run_monte_carlo_analysis(
                    account_name=account_name,
                    num_simulations=100,  # Reduced for load testing
                    confidence_levels=[0.95, 0.99],
                    risk_free_rate=0.02
                )
                
                # Validate result structure
                assert 'simulations_run' in result
                assert 'var_estimates' in result
                assert 'performance_metrics' in result
                
            except Exception as e:
                success = False
                error_msg = str(e)
                result = None
            
            duration = time.time() - start_time
            
            return {
                'account_name': account_name,
                'simulation_id': simulation_id,
                'duration': duration,
                'success': success,
                'error': error_msg,
                'result': result
            }
        
        # Start system monitoring
        load_tester.start_monitoring()
        
        try:
            with SessionLocal() as session:
                accounts = session.query(Account).limit(3).all()  # Use 3 accounts
            
            # Create 15 concurrent Monte Carlo simulations
            tasks = []
            for i in range(15):
                account = accounts[i % len(accounts)]
                tasks.append(run_monte_carlo_simulation(account.name, i))
            
            print(f"Starting {len(tasks)} concurrent Monte Carlo simulations...")
            start_time = time.time()
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            execution_time = time.time() - start_time
            print(f"Completed {len(results)} simulations in {execution_time:.2f} seconds")
            
            # Process results
            successful_results = [r for r in results if not isinstance(r, Exception) and r['success']]
            failed_results = [r for r in results if isinstance(r, Exception) or not r.get('success', True)]
            
            load_tester.results = successful_results + failed_results
            
            # Validate performance
            success_rate = len(successful_results) / len(results)
            avg_response_time = sum(r['duration'] for r in successful_results) / len(successful_results) if successful_results else 0
            throughput = len(successful_results) / execution_time
            
            print(f"Monte Carlo Performance:")
            print(f"  Success Rate: {success_rate:.1%}")
            print(f"  Average Response Time: {avg_response_time:.2f}s")
            print(f"  Throughput: {throughput:.2f} simulations/second")
            
            # Performance assertions
            assert success_rate >= 0.90, f"Monte Carlo success rate too low: {success_rate:.1%}"
            assert avg_response_time <= 30.0, f"Monte Carlo response time too high: {avg_response_time:.2f}s"
            
        finally:
            load_tester.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, load_test_database):
        """Test system performance with mixed concurrent operations."""
        engine, SessionLocal = load_test_database
        load_tester = SystemLoadTester(engine, SessionLocal)
        
        async def mixed_operation(operation_type: str, account_name: str, operation_id: int) -> Dict[str, Any]:
            """Perform mixed analytics operations."""
            start_time = time.time()
            success = True
            error_msg = None
            result = None
            
            try:
                if operation_type == "time_bin":
                    analyzer = TimeBinAnalyzer(SessionLocal())
                    result = await analyzer.analyze_time_bin_performance(
                        account_name=account_name,
                        hour=10 + (operation_id % 6),
                        minute_bin=(operation_id % 4) * 15,
                        start_date=datetime(2024, 1, 1).date(),
                        end_date=datetime(2024, 3, 1).date()
                    )
                    
                elif operation_type == "performance_metrics":
                    calculator = PerformanceMetricsCalculator(SessionLocal())
                    result = await calculator.calculate_comprehensive_metrics(
                        account_name=account_name,
                        start_date=datetime(2024, 1, 1).date(),
                        end_date=datetime(2024, 3, 1).date()
                    )
                    
                elif operation_type == "benchmark_correlation":
                    analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
                    result = await analyzer.calculate_benchmark_correlation(
                        account_name=account_name,
                        benchmark_symbol='SPY',
                        analysis_period_days=60
                    )
                    
                elif operation_type == "data_export":
                    exporter = DataExportEngine(SessionLocal())
                    result = await exporter.export_time_bin_trades(
                        account_name=account_name,
                        hour=10,
                        minute_bin=0,
                        export_format='csv'
                    )
                
            except Exception as e:
                success = False
                error_msg = str(e)
            
            duration = time.time() - start_time
            
            return {
                'operation_type': operation_type,
                'account_name': account_name,
                'operation_id': operation_id,
                'duration': duration,
                'success': success,
                'error': error_msg
            }
        
        # Start system monitoring
        load_tester.start_monitoring()
        
        try:
            with SessionLocal() as session:
                accounts = session.query(Account).limit(4).all()
            
            # Create mixed workload (40 total operations)
            tasks = []
            operation_types = ["time_bin", "performance_metrics", "benchmark_correlation", "data_export"]
            
            for i in range(40):
                operation_type = operation_types[i % len(operation_types)]
                account = accounts[i % len(accounts)]
                tasks.append(mixed_operation(operation_type, account.name, i))
            
            print(f"Starting mixed workload with {len(tasks)} concurrent operations...")
            start_time = time.time()
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            execution_time = time.time() - start_time
            print(f"Completed mixed workload in {execution_time:.2f} seconds")
            
            # Analyze results by operation type
            operation_stats = {}
            for result in results:
                if isinstance(result, Exception):
                    continue
                    
                op_type = result['operation_type']
                if op_type not in operation_stats:
                    operation_stats[op_type] = {
                        'count': 0,
                        'successful': 0,
                        'total_duration': 0,
                        'max_duration': 0
                    }
                
                stats = operation_stats[op_type]
                stats['count'] += 1
                if result['success']:
                    stats['successful'] += 1
                stats['total_duration'] += result['duration']
                stats['max_duration'] = max(stats['max_duration'], result['duration'])
            
            print("Mixed Workload Results by Operation Type:")
            for op_type, stats in operation_stats.items():
                success_rate = stats['successful'] / stats['count'] if stats['count'] > 0 else 0
                avg_duration = stats['total_duration'] / stats['count'] if stats['count'] > 0 else 0
                print(f"  {op_type}:")
                print(f"    Success Rate: {success_rate:.1%}")
                print(f"    Average Duration: {avg_duration:.3f}s")
                print(f"    Max Duration: {stats['max_duration']:.3f}s")
                
                # Assertions for each operation type
                assert success_rate >= 0.90, f"{op_type} success rate too low: {success_rate:.1%}"
                
                # Different duration thresholds for different operation types
                duration_limits = {
                    'time_bin': 5.0,
                    'performance_metrics': 8.0,
                    'benchmark_correlation': 10.0,
                    'data_export': 15.0
                }
                limit = duration_limits.get(op_type, 10.0)
                assert avg_duration <= limit, f"{op_type} average duration too high: {avg_duration:.3f}s"
            
            load_tester.results = [r for r in results if not isinstance(r, Exception)]
            
        finally:
            load_tester.stop_monitoring()
            
        # Final performance summary
        perf_summary = load_tester.get_performance_summary()
        print(f"\nOverall System Performance:")
        print(f"  Total Operations: {perf_summary['total_requests']}")
        print(f"  Overall Success Rate: {perf_summary['success_rate']:.1%}")
        print(f"  Overall Throughput: {perf_summary['throughput']['requests_per_second']:.1f} ops/second")
        print(f"  Peak System Resources:")
        print(f"    CPU: {perf_summary['system_resources']['max_cpu_percent']:.1f}%")
        print(f"    Memory: {perf_summary['system_resources']['max_memory_percent']:.1f}%")
        
        # Overall system performance assertions
        assert perf_summary['success_rate'] >= 0.90, "Overall success rate too low"
        assert perf_summary['throughput']['requests_per_second'] >= 2.0, "Overall throughput too low"
        assert perf_summary['system_resources']['max_cpu_percent'] <= 95, "System CPU usage too high"
        assert perf_summary['system_resources']['max_memory_percent'] <= 85, "System memory usage too high"
    
    @pytest.mark.asyncio
    async def test_database_connection_pool_stress(self, load_test_database):
        """Test database connection pool under stress conditions."""
        engine, SessionLocal = load_test_database
        
        # Test connection pool with high concurrent access
        connection_manager = ConnectionPoolManager(engine)
        
        async def database_operation(operation_id: int) -> Dict[str, Any]:
            """Perform database operation for connection pool testing."""
            start_time = time.time()
            success = True
            error_msg = None
            
            try:
                # Get connection from pool
                with SessionLocal() as session:
                    # Perform multiple database operations
                    accounts = session.query(Account).limit(5).all()
                    for account in accounts:
                        trades = session.query(ProcessedTrade).filter(
                            ProcessedTrade.account_name == account.name
                        ).limit(100).all()
                        
                        if trades:
                            total_pnl = sum(t.profit_loss for t in trades)
                            win_rate = sum(1 for t in trades if t.profit_loss > 0) / len(trades)
                        
                    # Also query market data
                    market_data = session.query(MarketData).filter(
                        MarketData.symbol == 'SPY'
                    ).limit(50).all()
                    
            except Exception as e:
                success = False
                error_msg = str(e)
            
            duration = time.time() - start_time
            return {
                'operation_id': operation_id,
                'duration': duration,
                'success': success,
                'error': error_msg
            }
        
        # Test with 100 concurrent database operations
        tasks = [database_operation(i) for i in range(100)]
        
        print("Testing database connection pool with 100 concurrent operations...")
        start_time = time.time()
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        execution_time = time.time() - start_time
        
        # Analyze connection pool performance
        successful_ops = [r for r in results if not isinstance(r, Exception) and r['success']]
        failed_ops = [r for r in results if isinstance(r, Exception) or not r.get('success', True)]
        
        success_rate = len(successful_ops) / len(results)
        avg_duration = sum(r['duration'] for r in successful_ops) / len(successful_ops) if successful_ops else 0
        throughput = len(successful_ops) / execution_time
        
        print(f"Database Connection Pool Results:")
        print(f"  Success Rate: {success_rate:.1%}")
        print(f"  Average Operation Duration: {avg_duration:.3f}s")
        print(f"  Throughput: {throughput:.1f} operations/second")
        print(f"  Failed Operations: {len(failed_ops)}")
        
        # Connection pool assertions
        assert success_rate >= 0.95, f"Database connection pool success rate too low: {success_rate:.1%}"
        assert avg_duration <= 2.0, f"Database operation duration too high: {avg_duration:.3f}s"
        assert len(failed_ops) <= 5, f"Too many failed database operations: {len(failed_ops)}"
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, load_test_database):
        """Test memory usage patterns under sustained load."""
        engine, SessionLocal = load_test_database
        
        # Monitor memory usage during sustained operations
        memory_usage = []
        
        def record_memory():
            """Record current memory usage."""
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_usage.append({
                'timestamp': time.time(),
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent()
            })
        
        async def sustained_operation(batch_id: int) -> Dict[str, Any]:
            """Perform sustained analytics operations."""
            record_memory()
            
            try:
                analyzer = TimeBinAnalyzer(SessionLocal())
                
                with SessionLocal() as session:
                    accounts = session.query(Account).limit(3).all()
                
                results = []
                for account in accounts:
                    for hour in [10, 11, 12]:
                        for minute_bin in [0, 15, 30, 45]:
                            result = await analyzer.analyze_time_bin_performance(
                                account_name=account.name,
                                hour=hour,
                                minute_bin=minute_bin,
                                start_date=datetime(2024, 1, 1).date(),
                                end_date=datetime(2024, 2, 1).date()
                            )
                            results.append(result)
                            
                            # Record memory periodically
                            if len(results) % 10 == 0:
                                record_memory()
                
                return {
                    'batch_id': batch_id,
                    'operations_completed': len(results),
                    'success': True
                }
                
            except Exception as e:
                return {
                    'batch_id': batch_id,
                    'error': str(e),
                    'success': False
                }
        
        # Record initial memory
        record_memory()
        
        # Run sustained operations in batches
        print("Testing memory usage under sustained load...")
        
        for batch in range(5):  # 5 batches of operations
            print(f"  Running batch {batch + 1}/5...")
            
            # Run batch operations
            batch_tasks = [sustained_operation(i) for i in range(3)]
            batch_results = await asyncio.gather(*batch_tasks)
            
            # Record memory after batch
            record_memory()
            
            # Allow some time for garbage collection
            await asyncio.sleep(1.0)
            record_memory()
        
        # Analyze memory usage patterns
        initial_memory = memory_usage[0]['rss_mb']
        peak_memory = max(m['rss_mb'] for m in memory_usage)
        final_memory = memory_usage[-1]['rss_mb']
        
        memory_growth = final_memory - initial_memory
        memory_peak_ratio = peak_memory / initial_memory
        
        print(f"Memory Usage Analysis:")
        print(f"  Initial Memory: {initial_memory:.1f} MB")
        print(f"  Peak Memory: {peak_memory:.1f} MB")
        print(f"  Final Memory: {final_memory:.1f} MB")
        print(f"  Memory Growth: {memory_growth:.1f} MB ({memory_growth/initial_memory:.1%})")
        print(f"  Peak/Initial Ratio: {memory_peak_ratio:.2f}x")
        
        # Memory usage assertions
        assert memory_growth < 200, f"Excessive memory growth: {memory_growth:.1f} MB"
        assert memory_peak_ratio < 3.0, f"Peak memory usage too high: {memory_peak_ratio:.2f}x initial"
        assert final_memory < initial_memory * 2.0, f"Final memory usage too high: {final_memory:.1f} MB vs initial {initial_memory:.1f} MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])