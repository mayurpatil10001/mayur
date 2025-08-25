"""
Real-time processing performance tests for trading analytics platform.

This module tests real-time monitoring and alerting performance including:
- Real-time trade data ingestion and processing
- Live performance monitoring and anomaly detection
- Alert generation and notification performance
- System responsiveness under real-time load
- WebSocket and streaming data performance

Requirements: 14.1, 14.2, 14.4, 8.1
"""

import pytest
import asyncio
import tempfile
import os
import time
import psutil
import threading
import json
import websockets
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator
from unittest.mock import Mock, patch, AsyncMock
import statistics
import queue
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# Import components for real-time testing
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.models.time_bin_analytics import TimeBinAnalysis, MarketData
from trading_platform.services.time_bin_monitoring_service import (
    TimeBinMonitoringService, MonitoringConfiguration, PerformanceSnapshot, MonitoringAlert
)
from trading_platform.services.alerts_engine import AlertsEngine
from trading_platform.services.real_time_data_processor import RealTimeDataProcessor
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer
from trading_platform.services.performance_metrics_calculator import PerformanceMetricsCalculator
from trading_platform.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@dataclass
class RealTimeMetrics:
    """Metrics for real-time processing performance."""
    messages_processed: int = 0
    alerts_generated: int = 0
    processing_latency_ms: List[float] = field(default_factory=list)
    alert_latency_ms: List[float] = field(default_factory=list)
    memory_usage_mb: List[float] = field(default_factory=list)
    cpu_usage_percent: List[float] = field(default_factory=list)
    throughput_msg_per_sec: float = 0.0
    errors_count: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class MockTradeDataFeed:
    """Mock real-time trade data feed for testing."""
    
    def __init__(self, account_names: List[str], rate_per_second: float = 10.0):
        self.account_names = account_names
        self.rate_per_second = rate_per_second
        self.running = False
        self.subscribers = []
        self.trade_id_counter = 1
        
    def subscribe(self, callback):
        """Subscribe to trade data feed."""
        self.subscribers.append(callback)
    
    async def start_feed(self, duration_seconds: int = 60):
        """Start generating mock trade data."""
        self.running = True
        start_time = time.time()
        
        try:
            while self.running and (time.time() - start_time) < duration_seconds:
                # Generate trade data
                trade_data = self._generate_trade_data()
                
                # Send to all subscribers
                for callback in self.subscribers:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(trade_data)
                        else:
                            callback(trade_data)
                    except Exception as e:
                        print(f"Error in feed callback: {e}")
                
                # Wait for next message
                await asyncio.sleep(1.0 / self.rate_per_second)
                
        except Exception as e:
            print(f"Error in trade feed: {e}")
        finally:
            self.running = False
    
    def stop_feed(self):
        """Stop the trade data feed."""
        self.running = False
    
    def _generate_trade_data(self) -> Dict[str, Any]:
        """Generate realistic trade data."""
        account = np.random.choice(self.account_names)
        symbol = "ES"  # E-mini S&P 500
        
        # Generate realistic trade parameters
        side = np.random.choice(["LONG", "SHORT"])
        quantity = 1
        
        # Generate realistic P&L (-100 to +150, 60% win rate)
        if np.random.random() < 0.60:
            profit_loss = np.random.uniform(5, 150)
        else:
            profit_loss = np.random.uniform(-100, -5)
        
        # Generate realistic prices
        base_price = 4500.0
        entry_price = base_price + np.random.normal(0, 10)
        
        if side == "LONG":
            exit_price = entry_price + (profit_loss / 20)
        else:
            exit_price = entry_price - (profit_loss / 20)
        
        # Generate realistic timing
        now = datetime.now()
        entry_time = now - timedelta(minutes=np.random.randint(5, 120))
        exit_time = now
        
        trade_data = {
            'trade_id': f"RT_{self.trade_id_counter:08d}",
            'account_name': account,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_time': entry_time.isoformat(),
            'exit_time': exit_time.isoformat(),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit_loss': profit_loss,
            'commission': 2.50,
            'duration_minutes': (exit_time - entry_time).total_seconds() / 60,
            'timestamp': time.time()
        }
        
        self.trade_id_counter += 1
        return trade_data


class MockMarketDataFeed:
    """Mock real-time market data feed."""
    
    def __init__(self, symbols: List[str], rate_per_second: float = 5.0):
        self.symbols = symbols
        self.rate_per_second = rate_per_second
        self.running = False
        self.subscribers = []
        self.current_prices = {symbol: self._get_base_price(symbol) for symbol in symbols}
        
    def subscribe(self, callback):
        """Subscribe to market data feed."""
        self.subscribers.append(callback)
    
    async def start_feed(self, duration_seconds: int = 60):
        """Start generating mock market data."""
        self.running = True
        start_time = time.time()
        
        try:
            while self.running and (time.time() - start_time) < duration_seconds:
                # Update prices for all symbols
                for symbol in self.symbols:
                    market_data = self._update_symbol_price(symbol)
                    
                    # Send to all subscribers
                    for callback in self.subscribers:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(market_data)
                            else:
                                callback(market_data)
                        except Exception as e:
                            print(f"Error in market data callback: {e}")
                
                await asyncio.sleep(1.0 / self.rate_per_second)
                
        except Exception as e:
            print(f"Error in market data feed: {e}")
        finally:
            self.running = False
    
    def stop_feed(self):
        """Stop market data feed."""
        self.running = False
    
    def _get_base_price(self, symbol: str) -> float:
        """Get base price for symbol."""
        base_prices = {
            'SPY': 450.0,
            'QQQ': 380.0,
            'VIX': 20.0,
            'ES': 4500.0,
            'NQ': 13000.0
        }
        return base_prices.get(symbol, 100.0)
    
    def _update_symbol_price(self, symbol: str) -> Dict[str, Any]:
        """Update and return symbol price data."""
        # Generate price movement
        current_price = self.current_prices[symbol]
        volatility = 0.002 if symbol != 'VIX' else 0.05
        
        change = np.random.normal(0, current_price * volatility)
        new_price = max(1.0, current_price + change)
        
        # Special handling for VIX
        if symbol == 'VIX':
            new_price = max(10.0, min(80.0, new_price))
        
        self.current_prices[symbol] = new_price
        
        return {
            'symbol': symbol,
            'price': new_price,
            'change': change,
            'timestamp': time.time(),
            'volume': np.random.randint(1000000, 10000000) if symbol != 'VIX' else 0
        }


class RealTimePerformanceMonitor:
    """Monitor real-time processing performance."""
    
    def __init__(self):
        self.metrics = RealTimeMetrics()
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start performance monitoring."""
        self.metrics.start_time = time.time()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_system)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.monitoring = False
        self.metrics.end_time = time.time()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_system(self):
        """Monitor system resources."""
        while self.monitoring:
            try:
                # Monitor memory usage
                memory_mb = psutil.virtual_memory().used / (1024 * 1024)
                self.metrics.memory_usage_mb.append(memory_mb)
                
                # Monitor CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.metrics.cpu_usage_percent.append(cpu_percent)
                
                time.sleep(0.5)
            except Exception as e:
                print(f"Error monitoring system: {e}")
                break
    
    def record_processing_latency(self, latency_ms: float):
        """Record message processing latency."""
        self.metrics.processing_latency_ms.append(latency_ms)
    
    def record_alert_latency(self, latency_ms: float):
        """Record alert generation latency."""
        self.metrics.alert_latency_ms.append(latency_ms)
    
    def increment_messages_processed(self):
        """Increment processed message count."""
        self.metrics.messages_processed += 1
    
    def increment_alerts_generated(self):
        """Increment alert count."""
        self.metrics.alerts_generated += 1
    
    def increment_errors(self):
        """Increment error count."""
        self.metrics.errors_count += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if self.metrics.start_time and self.metrics.end_time:
            duration = self.metrics.end_time - self.metrics.start_time
            self.metrics.throughput_msg_per_sec = self.metrics.messages_processed / duration
        
        return {
            'messages_processed': self.metrics.messages_processed,
            'alerts_generated': self.metrics.alerts_generated,
            'throughput_msg_per_sec': self.metrics.throughput_msg_per_sec,
            'errors_count': self.metrics.errors_count,
            'processing_latency': {
                'avg_ms': statistics.mean(self.metrics.processing_latency_ms) if self.metrics.processing_latency_ms else 0,
                'max_ms': max(self.metrics.processing_latency_ms) if self.metrics.processing_latency_ms else 0,
                'p95_ms': statistics.quantiles(self.metrics.processing_latency_ms, n=20)[18] if len(self.metrics.processing_latency_ms) > 20 else 0,
                'p99_ms': statistics.quantiles(self.metrics.processing_latency_ms, n=100)[98] if len(self.metrics.processing_latency_ms) > 100 else 0
            },
            'alert_latency': {
                'avg_ms': statistics.mean(self.metrics.alert_latency_ms) if self.metrics.alert_latency_ms else 0,
                'max_ms': max(self.metrics.alert_latency_ms) if self.metrics.alert_latency_ms else 0
            },
            'system_resources': {
                'peak_memory_mb': max(self.metrics.memory_usage_mb) if self.metrics.memory_usage_mb else 0,
                'avg_memory_mb': statistics.mean(self.metrics.memory_usage_mb) if self.metrics.memory_usage_mb else 0,
                'peak_cpu_percent': max(self.metrics.cpu_usage_percent) if self.metrics.cpu_usage_percent else 0,
                'avg_cpu_percent': statistics.mean(self.metrics.cpu_usage_percent) if self.metrics.cpu_usage_percent else 0
            }
        }


class TestRealTimeProcessing:
    """Test real-time processing performance."""
    
    @pytest.fixture
    async def real_time_test_database(self):
        """Create database for real-time testing."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        # Create test accounts for real-time testing
        with SessionLocal() as session:
            accounts = []
            for i in range(5):
                account = Account(
                    name=f"REALTIME_ACCOUNT_{i+1:02d}",
                    symbol="ES",
                    total_trades=0,
                    is_active=True
                )
                accounts.append(account)
            session.add_all(accounts)
            
            # Add some initial historical data for baseline
            base_date = datetime.now() - timedelta(days=30)
            trades = []
            trade_id = 1
            
            for account in accounts:
                for day in range(30):
                    trade_date = base_date + timedelta(days=day)
                    if trade_date.weekday() >= 5:  # Skip weekends
                        continue
                    
                    # Add some baseline trades
                    for hour in [10, 11, 12, 13, 14]:
                        for minute_bin in [0, 15, 30, 45]:
                            if np.random.random() < 0.3:  # 30% chance of trade
                                entry_time = trade_date.replace(hour=hour, minute=minute_bin)
                                exit_time = entry_time + timedelta(minutes=15)
                                pnl = np.random.normal(10, 30)
                                
                                trade = ProcessedTrade(
                                    trade_id=f"HIST_{trade_id:06d}",
                                    account_name=account.name,
                                    symbol="ES",
                                    entry_time=entry_time,
                                    exit_time=exit_time,
                                    entry_price=4500.0,
                                    exit_price=4500.0 + (pnl/20),
                                    quantity=1,
                                    side="LONG" if pnl > 0 else "SHORT",
                                    profit_loss=pnl,
                                    commission=2.50,
                                    duration_minutes=15,
                                    hour_of_day=hour,
                                    day_of_week=trade_date.weekday(),
                                    entry_order_id=f"E_{trade_id}",
                                    exit_order_id=f"X_{trade_id}"
                                )
                                trades.append(trade)
                                trade_id += 1
            
            session.add_all(trades)
            session.commit()
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_real_time_trade_processing(self, real_time_test_database):
        """Test real-time trade data processing performance."""
        engine, SessionLocal = real_time_test_database
        
        print("\nTesting real-time trade processing...")
        
        # Setup performance monitoring
        perf_monitor = RealTimePerformanceMonitor()
        perf_monitor.start_monitoring()
        
        # Setup real-time processor
        processor = RealTimeDataProcessor(SessionLocal())
        
        # Get account names for testing
        with SessionLocal() as session:
            account_names = [acc.name for acc in session.query(Account).all()]
        
        # Setup trade data feed
        trade_feed = MockTradeDataFeed(account_names, rate_per_second=20.0)  # 20 trades/second
        
        processed_trades = []
        processing_errors = []
        
        async def process_trade_data(trade_data: Dict[str, Any]):
            """Process incoming trade data."""
            process_start = time.time()
            
            try:
                # Convert to ProcessedTrade model
                trade = ProcessedTrade(
                    trade_id=trade_data['trade_id'],
                    account_name=trade_data['account_name'],
                    symbol=trade_data['symbol'],
                    entry_time=datetime.fromisoformat(trade_data['entry_time']),
                    exit_time=datetime.fromisoformat(trade_data['exit_time']),
                    entry_price=trade_data['entry_price'],
                    exit_price=trade_data['exit_price'],
                    quantity=trade_data['quantity'],
                    side=trade_data['side'],
                    profit_loss=trade_data['profit_loss'],
                    commission=trade_data['commission'],
                    duration_minutes=trade_data['duration_minutes'],
                    hour_of_day=datetime.fromisoformat(trade_data['exit_time']).hour,
                    day_of_week=datetime.fromisoformat(trade_data['exit_time']).weekday(),
                    entry_order_id=f"E_{trade_data['trade_id']}",
                    exit_order_id=f"X_{trade_data['trade_id']}"
                )
                
                # Process trade (save to database and update metrics)
                await processor.process_trade(trade)
                
                processed_trades.append(trade_data)
                perf_monitor.increment_messages_processed()
                
                # Record processing latency
                latency_ms = (time.time() - process_start) * 1000
                perf_monitor.record_processing_latency(latency_ms)
                
            except Exception as e:
                processing_errors.append({
                    'trade_id': trade_data.get('trade_id', 'unknown'),
                    'error': str(e),
                    'timestamp': time.time()
                })
                perf_monitor.increment_errors()
        
        # Subscribe to trade feed
        trade_feed.subscribe(process_trade_data)
        
        # Run feed for 30 seconds
        feed_duration = 30
        print(f"Running trade feed for {feed_duration} seconds at 20 trades/second...")
        
        # Start feed in background
        feed_task = asyncio.create_task(trade_feed.start_feed(feed_duration))
        
        # Wait for completion
        try:
            await feed_task
        except Exception as e:
            print(f"Feed error: {e}")
        finally:
            trade_feed.stop_feed()
            perf_monitor.stop_monitoring()
        
        # Analyze results
        performance = perf_monitor.get_performance_summary()
        
        print(f"Real-time Trade Processing Results:")
        print(f"  Messages processed: {performance['messages_processed']}")
        print(f"  Processing errors: {performance['errors_count']}")
        print(f"  Throughput: {performance['throughput_msg_per_sec']:.1f} trades/second")
        print(f"  Average latency: {performance['processing_latency']['avg_ms']:.1f}ms")
        print(f"  P95 latency: {performance['processing_latency']['p95_ms']:.1f}ms")
        print(f"  Max latency: {performance['processing_latency']['max_ms']:.1f}ms")
        print(f"  Peak memory: {performance['system_resources']['peak_memory_mb']:.1f}MB")
        print(f"  Peak CPU: {performance['system_resources']['peak_cpu_percent']:.1f}%")
        
        # Performance assertions for real-time processing
        assert performance['messages_processed'] >= 500, f"Too few messages processed: {performance['messages_processed']}"
        assert performance['throughput_msg_per_sec'] >= 15.0, f"Throughput too low: {performance['throughput_msg_per_sec']:.1f} trades/sec"
        assert performance['processing_latency']['avg_ms'] <= 50.0, f"Average latency too high: {performance['processing_latency']['avg_ms']:.1f}ms"
        assert performance['processing_latency']['p95_ms'] <= 100.0, f"P95 latency too high: {performance['processing_latency']['p95_ms']:.1f}ms"
        assert performance['errors_count'] / performance['messages_processed'] <= 0.01, "Error rate too high"
        
        # Validate data integrity
        assert len(processed_trades) == performance['messages_processed'], "Mismatch in processed trade count"
        
        # Check database persistence
        with SessionLocal() as session:
            db_trade_count = session.query(ProcessedTrade).filter(
                ProcessedTrade.trade_id.like('RT_%')
            ).count()
            assert db_trade_count > 0, "No trades persisted to database"
            print(f"  Trades persisted to database: {db_trade_count}")
    
    @pytest.mark.asyncio
    async def test_real_time_monitoring_alerts(self, real_time_test_database):
        """Test real-time monitoring and alert generation performance."""
        engine, SessionLocal = real_time_test_database
        
        print("\nTesting real-time monitoring and alerts...")
        
        # Setup performance monitoring
        perf_monitor = RealTimePerformanceMonitor()
        perf_monitor.start_monitoring()
        
        # Setup monitoring service with sensitive thresholds for testing
        monitoring_config = MonitoringConfiguration(
            performance_threshold_pnl=-50.0,    # Alert on $50 loss
            win_rate_threshold=0.3,             # Alert if win rate drops below 30%
            max_drawdown_threshold=200.0,       # Alert on $200 drawdown
            statistical_significance_threshold=0.1,  # Alert if p-value > 0.1
            alert_cooldown_minutes=1,           # Short cooldown for testing
            monitoring_interval_seconds=5       # Check every 5 seconds
        )
        
        monitoring_service = TimeBinMonitoringService(SessionLocal(), monitoring_config)
        alerts_engine = AlertsEngine(SessionLocal())
        
        # Get account names
        with SessionLocal() as session:
            account_names = [acc.name for acc in session.query(Account).all()]
        
        # Setup feeds
        trade_feed = MockTradeDataFeed(account_names, rate_per_second=10.0)
        market_feed = MockMarketDataFeed(['SPY', 'QQQ', 'VIX'], rate_per_second=2.0)
        
        # Collect alerts and monitoring results
        generated_alerts = []
        monitoring_snapshots = []
        
        async def process_monitoring_trade(trade_data: Dict[str, Any]):
            """Process trade for monitoring."""
            try:
                # Create trade object
                trade = ProcessedTrade(
                    trade_id=trade_data['trade_id'],
                    account_name=trade_data['account_name'],
                    symbol=trade_data['symbol'],
                    entry_time=datetime.fromisoformat(trade_data['entry_time']),
                    exit_time=datetime.fromisoformat(trade_data['exit_time']),
                    entry_price=trade_data['entry_price'],
                    exit_price=trade_data['exit_price'],
                    quantity=trade_data['quantity'],
                    side=trade_data['side'],
                    profit_loss=trade_data['profit_loss'],
                    commission=trade_data['commission'],
                    duration_minutes=trade_data['duration_minutes'],
                    hour_of_day=datetime.fromisoformat(trade_data['exit_time']).hour,
                    day_of_week=datetime.fromisoformat(trade_data['exit_time']).weekday(),
                    entry_order_id=f"E_{trade_data['trade_id']}",
                    exit_order_id=f"X_{trade_data['trade_id']}"
                )
                
                # Save trade to database
                with SessionLocal() as session:
                    session.add(trade)
                    session.commit()
                
                # Update monitoring
                alert_start_time = time.time()
                
                # Trigger monitoring check
                snapshot = await monitoring_service.update_performance_snapshot(
                    trade_data['account_name'],
                    datetime.fromisoformat(trade_data['exit_time']).hour,
                    (datetime.fromisoformat(trade_data['exit_time']).minute // 15) * 15
                )
                
                if snapshot:
                    monitoring_snapshots.append(snapshot)
                
                # Check for alerts
                alerts = await monitoring_service.check_for_anomalies(
                    trade_data['account_name'],
                    datetime.fromisoformat(trade_data['exit_time']).hour,
                    (datetime.fromisoformat(trade_data['exit_time']).minute // 15) * 15
                )
                
                if alerts:
                    generated_alerts.extend(alerts)
                    perf_monitor.increment_alerts_generated()
                    
                    # Record alert latency
                    alert_latency_ms = (time.time() - alert_start_time) * 1000
                    perf_monitor.record_alert_latency(alert_latency_ms)
                
                perf_monitor.increment_messages_processed()
                
            except Exception as e:
                print(f"Error in monitoring trade processing: {e}")
                perf_monitor.increment_errors()
        
        async def process_market_data(market_data: Dict[str, Any]):
            """Process market data updates."""
            try:
                # Update market data in database
                with SessionLocal() as session:
                    # Check if market data exists for today
                    today = datetime.now().date()
                    existing = session.query(MarketData).filter(
                        MarketData.symbol == market_data['symbol'],
                        MarketData.date == today
                    ).first()
                    
                    if existing:
                        existing.close_price = market_data['price']
                        existing.high_price = max(existing.high_price, market_data['price'])
                        existing.low_price = min(existing.low_price, market_data['price'])
                    else:
                        new_data = MarketData(
                            symbol=market_data['symbol'],
                            date=today,
                            open_price=market_data['price'],
                            high_price=market_data['price'],
                            low_price=market_data['price'],
                            close_price=market_data['price'],
                            volume=market_data['volume'],
                            adjusted_close=market_data['price']
                        )
                        session.add(new_data)
                    
                    session.commit()
                    
            except Exception as e:
                print(f"Error processing market data: {e}")
        
        # Subscribe to feeds
        trade_feed.subscribe(process_monitoring_trade)
        market_feed.subscribe(process_market_data)
        
        # Run monitoring test for 45 seconds
        test_duration = 45
        print(f"Running monitoring test for {test_duration} seconds...")
        
        # Start feeds
        trade_task = asyncio.create_task(trade_feed.start_feed(test_duration))
        market_task = asyncio.create_task(market_feed.start_feed(test_duration))
        
        # Wait for completion
        try:
            await asyncio.gather(trade_task, market_task)
        except Exception as e:
            print(f"Monitoring test error: {e}")
        finally:
            trade_feed.stop_feed()
            market_feed.stop_feed()
            perf_monitor.stop_monitoring()
        
        # Analyze monitoring results
        performance = perf_monitor.get_performance_summary()
        
        print(f"Real-time Monitoring Results:")
        print(f"  Trades monitored: {performance['messages_processed']}")
        print(f"  Alerts generated: {performance['alerts_generated']}")
        print(f"  Monitoring snapshots: {len(monitoring_snapshots)}")
        print(f"  Alert generation rate: {performance['alerts_generated'] / performance['messages_processed'] * 100:.1f}%" if performance['messages_processed'] > 0 else "N/A")
        print(f"  Average alert latency: {performance['alert_latency']['avg_ms']:.1f}ms")
        print(f"  Max alert latency: {performance['alert_latency']['max_ms']:.1f}ms")
        print(f"  System resources:")
        print(f"    Peak memory: {performance['system_resources']['peak_memory_mb']:.1f}MB")
        print(f"    Peak CPU: {performance['system_resources']['peak_cpu_percent']:.1f}%")
        
        # Analyze alert types
        if generated_alerts:
            alert_types = {}
            for alert in generated_alerts:
                alert_type = alert.get('alert_type', 'unknown')
                alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
            
            print(f"  Alert types:")
            for alert_type, count in alert_types.items():
                print(f"    {alert_type}: {count}")
        
        # Performance assertions for monitoring
        assert performance['messages_processed'] >= 300, f"Too few trades monitored: {performance['messages_processed']}"
        assert len(monitoring_snapshots) > 0, "No monitoring snapshots created"
        
        if performance['alerts_generated'] > 0:
            assert performance['alert_latency']['avg_ms'] <= 100.0, f"Alert latency too high: {performance['alert_latency']['avg_ms']:.1f}ms"
            assert performance['alert_latency']['max_ms'] <= 500.0, f"Max alert latency too high: {performance['alert_latency']['max_ms']:.1f}ms"
        
        # System resource assertions
        assert performance['system_resources']['peak_cpu_percent'] <= 80.0, "CPU usage too high during monitoring"
        assert performance['system_resources']['peak_memory_mb'] <= 200.0, "Memory usage too high during monitoring"
    
    @pytest.mark.asyncio
    async def test_streaming_data_performance(self, real_time_test_database):
        """Test streaming data performance with high-frequency updates."""
        engine, SessionLocal = real_time_test_database
        
        print("\nTesting high-frequency streaming data performance...")
        
        perf_monitor = RealTimePerformanceMonitor()
        perf_monitor.start_monitoring()
        
        # Setup high-frequency data streams
        with SessionLocal() as session:
            account_names = [acc.name for acc in session.query(Account).all()]
        
        # High-frequency trade feed (100 trades/second)
        hf_trade_feed = MockTradeDataFeed(account_names, rate_per_second=100.0)
        
        # High-frequency market data (50 updates/second)
        hf_market_feed = MockMarketDataFeed(['ES', 'NQ', 'SPY', 'QQQ'], rate_per_second=50.0)
        
        # Data buffers for batch processing
        trade_buffer = []
        market_buffer = []
        buffer_lock = asyncio.Lock()
        
        # Processing statistics
        batch_processing_times = []
        buffer_sizes = []
        
        async def buffer_trade_data(trade_data: Dict[str, Any]):
            """Buffer trade data for batch processing."""
            async with buffer_lock:
                trade_buffer.append(trade_data)
                perf_monitor.increment_messages_processed()
        
        async def buffer_market_data(market_data: Dict[str, Any]):
            """Buffer market data for batch processing."""
            async with buffer_lock:
                market_buffer.append(market_data)
        
        async def process_buffers():
            """Process buffered data in batches."""
            while perf_monitor.monitoring:
                try:
                    batch_start = time.time()
                    
                    async with buffer_lock:
                        # Process trade buffer
                        if trade_buffer:
                            buffer_sizes.append(len(trade_buffer))
                            # Simulate batch processing
                            await asyncio.sleep(0.01)  # Simulate processing time
                            trade_buffer.clear()
                        
                        # Process market buffer
                        if market_buffer:
                            # Simulate market data processing
                            await asyncio.sleep(0.005)
                            market_buffer.clear()
                    
                    batch_time = time.time() - batch_start
                    batch_processing_times.append(batch_time * 1000)  # Convert to ms
                    
                    # Process batches every 100ms
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error in batch processing: {e}")
                    perf_monitor.increment_errors()
        
        # Subscribe to feeds
        hf_trade_feed.subscribe(buffer_trade_data)
        hf_market_feed.subscribe(buffer_market_data)
        
        # Run high-frequency test for 20 seconds
        test_duration = 20
        print(f"Running high-frequency test for {test_duration} seconds...")
        print("Expected: ~2000 trades and ~1000 market updates")
        
        # Start processing task
        processing_task = asyncio.create_task(process_buffers())
        
        # Start feeds
        trade_task = asyncio.create_task(hf_trade_feed.start_feed(test_duration))
        market_task = asyncio.create_task(hf_market_feed.start_feed(test_duration))
        
        try:
            await asyncio.gather(trade_task, market_task)
        except Exception as e:
            print(f"High-frequency test error: {e}")
        finally:
            hf_trade_feed.stop_feed()
            hf_market_feed.stop_feed()
            perf_monitor.stop_monitoring()
            processing_task.cancel()
            
            try:
                await processing_task
            except asyncio.CancelledError:
                pass
        
        # Analyze streaming performance
        performance = perf_monitor.get_performance_summary()
        
        avg_batch_time = statistics.mean(batch_processing_times) if batch_processing_times else 0
        max_batch_time = max(batch_processing_times) if batch_processing_times else 0
        avg_buffer_size = statistics.mean(buffer_sizes) if buffer_sizes else 0
        max_buffer_size = max(buffer_sizes) if buffer_sizes else 0
        
        print(f"High-frequency Streaming Results:")
        print(f"  Messages processed: {performance['messages_processed']}")
        print(f"  Throughput: {performance['throughput_msg_per_sec']:.1f} messages/second")
        print(f"  Batch processing:")
        print(f"    Batches processed: {len(batch_processing_times)}")
        print(f"    Average batch time: {avg_batch_time:.1f}ms")
        print(f"    Max batch time: {max_batch_time:.1f}ms")
        print(f"    Average buffer size: {avg_buffer_size:.1f} messages")
        print(f"    Max buffer size: {max_buffer_size} messages")
        print(f"  System resources:")
        print(f"    Peak memory: {performance['system_resources']['peak_memory_mb']:.1f}MB")
        print(f"    Peak CPU: {performance['system_resources']['peak_cpu_percent']:.1f}%")
        
        # High-frequency performance assertions
        assert performance['messages_processed'] >= 1500, f"Too few messages processed: {performance['messages_processed']}"
        assert performance['throughput_msg_per_sec'] >= 75.0, f"Throughput too low: {performance['throughput_msg_per_sec']:.1f} msg/sec"
        assert avg_batch_time <= 50.0, f"Average batch processing too slow: {avg_batch_time:.1f}ms"
        assert max_batch_time <= 200.0, f"Max batch processing too slow: {max_batch_time:.1f}ms"
        assert max_buffer_size <= 100, f"Buffer size too large: {max_buffer_size}"
        
        # System resource assertions for high-frequency processing
        assert performance['system_resources']['peak_cpu_percent'] <= 95.0, "CPU usage too high for streaming"
        assert performance['system_resources']['peak_memory_mb'] <= 300.0, "Memory usage too high for streaming"
    
    @pytest.mark.asyncio
    async def test_websocket_performance(self):
        """Test WebSocket connection performance for real-time updates."""
        print("\nTesting WebSocket performance...")
        
        # Mock WebSocket server for testing
        connected_clients = []
        message_counts = []
        latency_measurements = []
        
        async def websocket_handler(websocket, path):
            """Handle WebSocket connections."""
            connected_clients.append(websocket)
            print(f"Client connected. Total clients: {len(connected_clients)}")
            
            try:
                async for message in websocket:
                    # Echo message back with timestamp
                    response = {
                        'original_message': json.loads(message),
                        'server_timestamp': time.time(),
                        'client_count': len(connected_clients)
                    }
                    await websocket.send(json.dumps(response))
                    
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                if websocket in connected_clients:
                    connected_clients.remove(websocket)
                print(f"Client disconnected. Total clients: {len(connected_clients)}")
        
        # Start WebSocket server
        server = await websockets.serve(websocket_handler, "localhost", 8765)
        print("WebSocket server started on localhost:8765")
        
        try:
            # Test multiple concurrent WebSocket connections
            async def websocket_client_test(client_id: int, messages_to_send: int = 50):
                """Test WebSocket client performance."""
                client_latencies = []
                messages_sent = 0
                
                try:
                    async with websockets.connect("ws://localhost:8765") as websocket:
                        for i in range(messages_to_send):
                            send_time = time.time()
                            
                            message = {
                                'client_id': client_id,
                                'message_id': i,
                                'timestamp': send_time,
                                'data': f"Test message {i} from client {client_id}"
                            }
                            
                            await websocket.send(json.dumps(message))
                            response = await websocket.recv()
                            
                            receive_time = time.time()
                            latency = (receive_time - send_time) * 1000  # Convert to ms
                            client_latencies.append(latency)
                            
                            messages_sent += 1
                            
                            # Small delay between messages
                            await asyncio.sleep(0.02)  # 50 messages/second per client
                
                except Exception as e:
                    print(f"Client {client_id} error: {e}")
                
                return {
                    'client_id': client_id,
                    'messages_sent': messages_sent,
                    'latencies': client_latencies,
                    'avg_latency': statistics.mean(client_latencies) if client_latencies else 0,
                    'max_latency': max(client_latencies) if client_latencies else 0
                }
            
            # Run multiple concurrent clients
            num_clients = 10
            messages_per_client = 30
            
            print(f"Testing {num_clients} concurrent WebSocket clients...")
            print(f"Each client sending {messages_per_client} messages")
            
            start_time = time.time()
            
            client_tasks = [
                websocket_client_test(i, messages_per_client) 
                for i in range(num_clients)
            ]
            
            client_results = await asyncio.gather(*client_tasks)
            
            test_duration = time.time() - start_time
            
            # Analyze WebSocket performance
            total_messages = sum(r['messages_sent'] for r in client_results)
            all_latencies = []
            for result in client_results:
                all_latencies.extend(result['latencies'])
            
            avg_latency = statistics.mean(all_latencies) if all_latencies else 0
            max_latency = max(all_latencies) if all_latencies else 0
            p95_latency = statistics.quantiles(all_latencies, n=20)[18] if len(all_latencies) > 20 else max_latency
            throughput = total_messages / test_duration
            
            print(f"WebSocket Performance Results:")
            print(f"  Concurrent clients: {num_clients}")
            print(f"  Total messages: {total_messages}")
            print(f"  Test duration: {test_duration:.2f} seconds")
            print(f"  Throughput: {throughput:.1f} messages/second")
            print(f"  Average latency: {avg_latency:.1f}ms")
            print(f"  P95 latency: {p95_latency:.1f}ms")
            print(f"  Max latency: {max_latency:.1f}ms")
            
            # WebSocket performance assertions
            assert total_messages >= num_clients * messages_per_client * 0.95, "Too many lost messages"
            assert throughput >= 100.0, f"WebSocket throughput too low: {throughput:.1f} msg/sec"
            assert avg_latency <= 50.0, f"Average WebSocket latency too high: {avg_latency:.1f}ms"
            assert p95_latency <= 100.0, f"P95 WebSocket latency too high: {p95_latency:.1f}ms"
            assert max_latency <= 500.0, f"Max WebSocket latency too high: {max_latency:.1f}ms"
            
            print("✅ WebSocket performance test passed")
            
        finally:
            server.close()
            await server.wait_closed()
            print("WebSocket server stopped")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])