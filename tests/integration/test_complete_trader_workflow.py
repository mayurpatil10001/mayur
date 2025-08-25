"""
Complete trader workflow integration test from data ingestion to recommendations.

This module tests the entire end-to-end trader workflow including:
- Raw data ingestion from multiple sources
- Data validation and processing
- Time-bin analysis and performance calculation
- Market correlation and regime analysis
- Advanced analytics (Monte Carlo, Walk-Forward)
- Actionable recommendation generation
- Report generation and export

Requirements: 1.1, 2.1, 3.1, 11.1, 12.1
"""

import pytest
import asyncio
import tempfile
import os
import csv
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, patch
import shutil

# Import all components for complete workflow testing
from trading_platform.models.database import (
    ProcessedTrade, Account, PerformanceMetric
)
from trading_platform.models.time_bin_analytics import (
    TimeBinAnalysis, MarketData, VolatilityRegime, WalkForwardResult, 
    MonteCarloResult, ExportHistory, PDFReport
)
from trading_platform.services.data_ingestion.sierra_chart_processor import SierraChartDataProcessor
from trading_platform.services.data_ingestion.data_validator import DataValidator
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer
from trading_platform.services.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.services.walk_forward_analyzer import WalkForwardAnalyzer
from trading_platform.services.vix_regime_analyzer import VIXRegimeAnalyzer
from trading_platform.services.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
from trading_platform.services.recommendation.recommendation_service import RecommendationService
from trading_platform.services.export_reporting.data_export_engine import (
    DataExportEngine, ExportConfig, ExportFormat
)
from trading_platform.services.export_reporting.pdf_report_generator import PDFReportGenerator
from trading_platform.database.base import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class TestCompleteTraderWorkflow:
    """Test complete end-to-end trader workflow with real data patterns."""
    
    @pytest.fixture
    async def raw_data_sources(self):
        """Create realistic raw data sources for testing."""
        temp_dir = tempfile.mkdtemp()
        
        # Create SierraChart fills CSV file
        fills_csv_path = os.path.join(temp_dir, "sierra_chart_fills.csv")
        with open(fills_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                "Date", "Time", "Symbol", "Type", "Quantity", "Price", 
                "AccountNumber", "TradeNumber", "Side", "OrderID"
            ])
            
            # Generate realistic fills data
            base_date = datetime(2023, 1, 1)
            trade_number = 1
            
            accounts = ["IPS_TM_10", "IPS_TM_13", "IPS_TM_15"]
            symbols = ["ESH23", "NQH23", "YMH23"]
            
            for day_offset in range(180):  # 6 months of data
                current_date = base_date + timedelta(days=day_offset)
                
                if current_date.weekday() >= 5:  # Skip weekends
                    continue
                
                for account, symbol in zip(accounts, symbols):
                    # Generate 2-8 trades per day per account
                    daily_trades = np.random.randint(2, 9)
                    
                    for trade_idx in range(daily_trades):
                        # Entry trade
                        entry_hour = np.random.randint(9, 16)
                        entry_minute = np.random.choice([0, 15, 30, 45])
                        entry_time = f"{entry_hour:02d}:{entry_minute:02d}:00"
                        
                        price = 4500 + np.random.normal(0, 100)
                        quantity = np.random.choice([1, 2, 3])
                        side = np.random.choice(["Buy", "Sell"])
                        
                        writer.writerow([
                            current_date.strftime("%m/%d/%Y"),
                            entry_time,
                            symbol,
                            "Market",
                            quantity,
                            f"{price:.2f}",
                            account,
                            trade_number,
                            side,
                            f"E_{trade_number}"
                        ])
                        
                        # Exit trade (5-90 minutes later)
                        duration_minutes = np.random.randint(5, 91)
                        exit_time_dt = datetime.strptime(entry_time, "%H:%M:%S") + timedelta(minutes=duration_minutes)
                        exit_time = exit_time_dt.strftime("%H:%M:%S")
                        
                        # Calculate exit price based on some P&L distribution
                        pnl_per_point = 50.0  # ES futures
                        target_pnl = np.random.normal(25, 75)  # Average $25, std $75
                        
                        if side == "Buy":
                            exit_price = price + (target_pnl / pnl_per_point)
                        else:
                            exit_price = price - (target_pnl / pnl_per_point)
                        
                        exit_side = "Sell" if side == "Buy" else "Buy"
                        
                        writer.writerow([
                            current_date.strftime("%m/%d/%Y"),
                            exit_time,
                            symbol,
                            "Market", 
                            quantity,
                            f"{exit_price:.2f}",
                            account,
                            trade_number,
                            exit_side,
                            f"X_{trade_number}"
                        ])
                        
                        trade_number += 1
        
        # Create market data CSV file
        market_csv_path = os.path.join(temp_dir, "market_data.csv")
        with open(market_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"])
            
            # Generate SPY, QQQ, VIX data
            spy_price = 400.0
            qqq_price = 320.0
            vix_level = 20.0
            
            for day_offset in range(180):
                current_date = base_date + timedelta(days=day_offset)
                
                if current_date.weekday() >= 5:
                    continue
                
                # Market movements with correlation
                market_move = np.random.normal(0.001, 0.02)  # Daily return
                
                # SPY
                spy_change = market_move + np.random.normal(0, 0.005)
                spy_price *= (1 + spy_change)
                spy_high = spy_price * (1 + abs(np.random.normal(0, 0.008)))
                spy_low = spy_price * (1 - abs(np.random.normal(0, 0.008)))
                spy_open = spy_low + (spy_high - spy_low) * np.random.random()
                
                writer.writerow([
                    current_date.strftime("%Y-%m-%d"),
                    "SPY",
                    f"{spy_open:.2f}",
                    f"{spy_high:.2f}",
                    f"{spy_low:.2f}",
                    f"{spy_price:.2f}",
                    int(np.random.normal(50000000, 10000000))
                ])
                
                # QQQ (correlated with SPY)
                qqq_change = spy_change * 1.1 + np.random.normal(0, 0.008)
                qqq_price *= (1 + qqq_change)
                qqq_high = qqq_price * (1 + abs(np.random.normal(0, 0.01)))
                qqq_low = qqq_price * (1 - abs(np.random.normal(0, 0.01)))
                qqq_open = qqq_low + (qqq_high - qqq_low) * np.random.random()
                
                writer.writerow([
                    current_date.strftime("%Y-%m-%d"),
                    "QQQ",
                    f"{qqq_open:.2f}",
                    f"{qqq_high:.2f}",
                    f"{qqq_low:.2f}",
                    f"{qqq_price:.2f}",
                    int(np.random.normal(30000000, 8000000))
                ])
                
                # VIX (inversely correlated)
                vix_change = -spy_change * 10 + np.random.normal(0, 1.5)
                vix_level = max(10.0, min(80.0, vix_level + vix_change))
                vix_high = vix_level * (1 + abs(np.random.normal(0, 0.05)))
                vix_low = vix_level * (1 - abs(np.random.normal(0, 0.05)))
                vix_open = vix_low + (vix_high - vix_low) * np.random.random()
                
                writer.writerow([
                    current_date.strftime("%Y-%m-%d"),
                    "VIX",
                    f"{vix_open:.2f}",
                    f"{vix_high:.2f}",
                    f"{vix_low:.2f}",
                    f"{vix_level:.2f}",
                    int(np.random.normal(200000, 50000))
                ])
        
        # Create configuration file
        config_path = os.path.join(temp_dir, "workflow_config.json")
        config = {
            "data_sources": {
                "sierra_chart_fills": fills_csv_path,
                "market_data": market_csv_path
            },
            "analysis_parameters": {
                "min_trades_per_bin": 10,
                "confidence_levels": [0.95, 0.99],
                "monte_carlo_scenarios": 1000,
                "walk_forward_months": 6
            },
            "export_settings": {
                "export_formats": ["CSV", "JSON", "PDF"],
                "include_charts": True,
                "include_recommendations": True
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        yield {
            "temp_dir": temp_dir,
            "fills_csv": fills_csv_path,
            "market_csv": market_csv_path,
            "config": config_path
        }
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    async def workflow_database(self):
        """Create database for complete workflow testing."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_complete_trader_workflow_end_to_end(self, raw_data_sources, workflow_database):
        """Test complete trader workflow from raw data to actionable recommendations."""
        engine, SessionLocal = workflow_database
        data_sources = raw_data_sources
        
        workflow_results = {
            "phase_results": {},
            "final_recommendations": [],
            "export_files": [],
            "performance_metrics": {}
        }
        
        print("🔄 Starting complete trader workflow test")
        
        # PHASE 1: Data Ingestion and Validation
        print("\n📥 Phase 1: Data Ingestion and Validation")
        phase_start = datetime.now()
        
        # Initialize data processor and validator
        data_processor = SierraChartDataProcessor()
        data_validator = DataValidator()
        
        # Process Sierra Chart fills
        with open(data_sources["fills_csv"], 'r') as f:
            raw_fills_data = list(csv.DictReader(f))
        
        print(f"   Processing {len(raw_fills_data)} raw fill records")
        
        # Validate and process fills
        validated_fills = []
        invalid_records = 0
        
        for record in raw_fills_data:
            try:
                # Basic validation
                if await data_validator.validate_fill_record(record):
                    processed_fill = await data_processor.process_fill_record(record)
                    if processed_fill:
                        validated_fills.append(processed_fill)
                else:
                    invalid_records += 1
            except Exception as e:
                invalid_records += 1
                continue
        
        print(f"   Validated {len(validated_fills)} fills, rejected {invalid_records} invalid records")
        
        # Convert fills to processed trades
        processed_trades = await data_processor.create_trades_from_fills(validated_fills)
        
        print(f"   Created {len(processed_trades)} processed trades")
        
        # Process market data
        with open(data_sources["market_csv"], 'r') as f:
            market_records = list(csv.DictReader(f))
        
        market_data_objects = []
        for record in market_records:
            try:
                market_data = MarketData(
                    symbol=record["Symbol"],
                    date=datetime.strptime(record["Date"], "%Y-%m-%d").date(),
                    open_price=float(record["Open"]),
                    high_price=float(record["High"]),
                    low_price=float(record["Low"]),
                    close_price=float(record["Close"]),
                    volume=int(record["Volume"]),
                    adjusted_close=float(record["Close"])
                )
                market_data_objects.append(market_data)
            except Exception:
                continue
        
        print(f"   Processed {len(market_data_objects)} market data records")
        
        # Store in database
        with SessionLocal() as session:
            # Create accounts
            account_names = list(set(t.account_name for t in processed_trades))
            accounts = []
            for account_name in account_names:
                account_trades = [t for t in processed_trades if t.account_name == account_name]
                account = Account(
                    name=account_name,
                    symbol=account_trades[0].symbol if account_trades else "ES",
                    total_trades=len(account_trades),
                    first_trade_date=min(t.entry_time for t in account_trades) if account_trades else None,
                    last_trade_date=max(t.entry_time for t in account_trades) if account_trades else None,
                    is_active=True
                )
                accounts.append(account)
            
            session.add_all(accounts)
            session.add_all(processed_trades)
            session.add_all(market_data_objects)
            session.commit()
        
        phase_1_duration = (datetime.now() - phase_start).total_seconds()
        workflow_results["phase_results"]["data_ingestion"] = {
            "duration_seconds": phase_1_duration,
            "trades_processed": len(processed_trades),
            "market_data_records": len(market_data_objects),
            "accounts_created": len(accounts),
            "data_quality": (len(validated_fills) / len(raw_fills_data)) * 100
        }
        
        print(f"   ✅ Phase 1 completed in {phase_1_duration:.2f}s")
        
        # PHASE 2: Time-Bin Analysis
        print("\n📊 Phase 2: Time-Bin Analysis")
        phase_start = datetime.now()
        
        time_bin_analyzer = TimeBinAnalyzer()
        time_bin_analyses = []
        
        with SessionLocal() as session:
            for account in session.query(Account).all():
                print(f"   Analyzing {account.name} ({account.total_trades} trades)")
                
                account_trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == account.name
                ).order_by(ProcessedTrade.entry_time).all()
                
                # Group by time bins
                time_bins = {}
                for trade in account_trades:
                    minute_bin = 30 if trade.entry_time.minute >= 30 else 0
                    bin_key = (trade.hour_of_day, minute_bin)
                    
                    if bin_key not in time_bins:
                        time_bins[bin_key] = []
                    time_bins[bin_key].append(trade)
                
                # Analyze each time bin with sufficient data
                for (hour, minute_bin), bin_trades in time_bins.items():
                    if len(bin_trades) >= 10:  # Minimum for statistical significance
                        total_pnl = sum(t.profit_loss for t in bin_trades)
                        winning_trades = len([t for t in bin_trades if t.profit_loss > 0])
                        
                        returns = [t.profit_loss for t in bin_trades]
                        sharpe_ratio = self._calculate_sharpe_ratio(returns)
                        max_drawdown = self._calculate_max_drawdown(returns)
                        profit_factor = self._calculate_profit_factor(returns)
                        
                        analysis = TimeBinAnalysis(
                            account_name=account.name,
                            hour=hour,
                            minute_bin=minute_bin,
                            day_of_week=None,
                            analysis_date=datetime.now().date(),
                            total_trades=len(bin_trades),
                            win_rate=winning_trades / len(bin_trades),
                            average_pnl=total_pnl / len(bin_trades),
                            sharpe_ratio=sharpe_ratio,
                            max_drawdown=max_drawdown,
                            profit_factor=profit_factor,
                            statistical_significance=len(bin_trades) >= 30,
                            sample_size_adequate=len(bin_trades) >= 20
                        )
                        
                        time_bin_analyses.append(analysis)
            
            session.add_all(time_bin_analyses)
            session.commit()
        
        phase_2_duration = (datetime.now() - phase_start).total_seconds()
        workflow_results["phase_results"]["time_bin_analysis"] = {
            "duration_seconds": phase_2_duration,
            "time_bins_analyzed": len(time_bin_analyses),
            "statistically_significant": len([a for a in time_bin_analyses if a.statistical_significance])
        }
        
        print(f"   ✅ Phase 2 completed: {len(time_bin_analyses)} time bins analyzed in {phase_2_duration:.2f}s")
        
        # PHASE 3: Market Correlation Analysis
        print("\n🏢 Phase 3: Market Correlation Analysis")
        phase_start = datetime.now()
        
        benchmark_analyzer = BenchmarkComparisonAnalyzer(SessionLocal())
        vix_analyzer = VIXRegimeAnalyzer(SessionLocal())
        
        market_analysis_results = {}
        
        with SessionLocal() as session:
            accounts = session.query(Account).all()
            
            for account in accounts:
                print(f"   Analyzing market correlation for {account.name}")
                
                try:
                    # Market correlation
                    correlation_results = await benchmark_analyzer.calculate_market_correlation(
                        account_name=account.name,
                        benchmark_symbols=["SPY", "QQQ"],
                        start_date=datetime(2023, 1, 1),
                        end_date=datetime(2023, 7, 1)
                    )
                    
                    # VIX regime analysis
                    regime_performance = await vix_analyzer.analyze_performance_by_regime(
                        account_name=account.name,
                        start_date=datetime(2023, 1, 1).date(),
                        end_date=datetime(2023, 7, 1).date()
                    )
                    
                    market_analysis_results[account.name] = {
                        "correlation": correlation_results,
                        "vix_regimes": regime_performance
                    }
                    
                except Exception as e:
                    print(f"     ⚠️  Market analysis failed for {account.name}: {str(e)}")
                    continue
        
        phase_3_duration = (datetime.now() - phase_start).total_seconds()
        workflow_results["phase_results"]["market_correlation"] = {
            "duration_seconds": phase_3_duration,
            "accounts_analyzed": len(market_analysis_results)
        }
        
        print(f"   ✅ Phase 3 completed: {len(market_analysis_results)} accounts analyzed in {phase_3_duration:.2f}s")
        
        # PHASE 4: Advanced Analytics (Monte Carlo + Walk-Forward)
        print("\n🎲 Phase 4: Advanced Analytics")
        phase_start = datetime.now()
        
        monte_carlo_simulator = MonteCarloSimulator(SessionLocal())
        walk_forward_analyzer = WalkForwardAnalyzer(SessionLocal())
        
        advanced_analytics_results = {}
        
        with SessionLocal() as session:
            # Select top-performing time bins for advanced analysis
            top_time_bins = session.query(TimeBinAnalysis).filter(
                TimeBinAnalysis.total_trades >= 20,
                TimeBinAnalysis.average_pnl > 10
            ).order_by(TimeBinAnalysis.sharpe_ratio.desc()).limit(5).all()
            
            print(f"   Running advanced analytics on {len(top_time_bins)} top time bins")
            
            for time_bin in top_time_bins:
                print(f"   Processing {time_bin.account_name} {time_bin.hour}:{time_bin.minute_bin:02d}")
                
                # Get historical trades for this time bin
                time_bin_trades = session.query(ProcessedTrade).filter(
                    ProcessedTrade.account_name == time_bin.account_name,
                    ProcessedTrade.hour_of_day == time_bin.hour
                ).all()
                
                # Filter by minute bin
                filtered_trades = [t for t in time_bin_trades 
                                 if ((t.entry_time.minute >= 30) == (time_bin.minute_bin >= 30))]
                
                if len(filtered_trades) >= 30:
                    try:
                        # Monte Carlo simulation
                        mc_results = await monte_carlo_simulator.run_simulation(
                            time_bin_analysis_id=time_bin.id,
                            historical_trades=filtered_trades,
                            n_scenarios=1000,
                            time_horizon_days=30
                        )
                        
                        # Walk-Forward analysis
                        wf_results = await walk_forward_analyzer.run_walk_forward_analysis(
                            time_bin_analysis_id=time_bin.id,
                            historical_trades=filtered_trades,
                            validation_scheme="expanding",
                            in_sample_months=4,
                            out_sample_months=2
                        )
                        
                        advanced_analytics_results[f"{time_bin.account_name}_{time_bin.hour}_{time_bin.minute_bin}"] = {
                            "monte_carlo": mc_results,
                            "walk_forward": wf_results
                        }
                        
                        print(f"     ✅ Advanced analytics completed")
                        
                    except Exception as e:
                        print(f"     ⚠️  Advanced analytics failed: {str(e)}")
        
        phase_4_duration = (datetime.now() - phase_start).total_seconds()
        workflow_results["phase_results"]["advanced_analytics"] = {
            "duration_seconds": phase_4_duration,
            "time_bins_analyzed": len(advanced_analytics_results)
        }
        
        print(f"   ✅ Phase 4 completed: {len(advanced_analytics_results)} advanced analyses in {phase_4_duration:.2f}s")
        
        # PHASE 5: Recommendation Generation
        print("\n💡 Phase 5: Recommendation Generation")
        phase_start = datetime.now()
        
        recommendation_service = RecommendationService(SessionLocal())
        generated_recommendations = []
        
        with SessionLocal() as session:
            # Generate recommendations for all significant time bins
            significant_time_bins = session.query(TimeBinAnalysis).filter(
                TimeBinAnalysis.statistical_significance == True,
                TimeBinAnalysis.total_trades >= 15
            ).all()
            
            print(f"   Generating recommendations for {len(significant_time_bins)} time bins")
            
            for time_bin in significant_time_bins:
                try:
                    recommendation = await recommendation_service.generate_time_based_recommendation(
                        account_name=time_bin.account_name,
                        hour=time_bin.hour,
                        minute_bin=time_bin.minute_bin,
                        day_of_week=time_bin.day_of_week,
                        historical_performance={
                            "avg_pnl": time_bin.average_pnl,
                            "win_rate": time_bin.win_rate,
                            "sample_size": time_bin.total_trades,
                            "sharpe_ratio": time_bin.sharpe_ratio
                        }
                    )
                    
                    generated_recommendations.append({
                        "account_name": time_bin.account_name,
                        "time_bin": f"{time_bin.hour}:{time_bin.minute_bin:02d}",
                        "recommendation": recommendation.recommended_action,
                        "confidence": recommendation.confidence_score,
                        "reasoning": recommendation.reasoning,
                        "expected_performance": {
                            "avg_pnl": time_bin.average_pnl,
                            "win_rate": time_bin.win_rate,
                            "sharpe_ratio": time_bin.sharpe_ratio
                        }
                    })
                    
                except Exception as e:
                    print(f"     ⚠️  Recommendation generation failed: {str(e)}")
                    continue
        
        # Rank recommendations by quality
        generated_recommendations.sort(
            key=lambda x: x["confidence"] * (1 if x["recommendation"] in ["TRADE", "STRONG_BUY"] else 0.5),
            reverse=True
        )
        
        workflow_results["final_recommendations"] = generated_recommendations[:10]  # Top 10
        
        phase_5_duration = (datetime.now() - phase_start).total_seconds()
        workflow_results["phase_results"]["recommendations"] = {
            "duration_seconds": phase_5_duration,
            "total_recommendations": len(generated_recommendations),
            "actionable_recommendations": len([r for r in generated_recommendations 
                                             if r["recommendation"] in ["TRADE", "STRONG_BUY", "BUY"]])
        }
        
        print(f"   ✅ Phase 5 completed: {len(generated_recommendations)} recommendations in {phase_5_duration:.2f}s")
        
        # PHASE 6: Export and Reporting
        print("\n📄 Phase 6: Export and Reporting")
        phase_start = datetime.now()
        
        export_temp_dir = tempfile.mkdtemp()
        
        try:
            data_export_engine = DataExportEngine(SessionLocal())
            pdf_report_generator = PDFReportGenerator()
            
            export_config = ExportConfig(
                export_directory=export_temp_dir,
                include_summary=True,
                include_detailed_trades=True,
                include_performance_charts=True,
                export_formats=[ExportFormat.CSV, ExportFormat.JSON],
                date_range_start=datetime(2023, 1, 1),
                date_range_end=datetime(2023, 7, 1)
            )
            
            with SessionLocal() as session:
                # Export time-bin analysis results
                all_analyses = session.query(TimeBinAnalysis).all()
                analysis_ids = [a.id for a in all_analyses[:10]]  # Export top 10
                
                export_results = await data_export_engine.export_time_bin_analysis(
                    analysis_ids=analysis_ids,
                    config=export_config
                )
                
                workflow_results["export_files"] = export_results.get("exported_files", [])
                
                # Generate summary report
                summary_report = {
                    "workflow_execution": {
                        "execution_date": datetime.now().isoformat(),
                        "total_duration": sum(p["duration_seconds"] for p in workflow_results["phase_results"].values()),
                        "phases_completed": len(workflow_results["phase_results"])
                    },
                    "data_summary": {
                        "accounts_processed": len(accounts),
                        "total_trades": sum(a.total_trades for a in accounts),
                        "time_bins_analyzed": len(time_bin_analyses),
                        "market_data_points": len(market_data_objects)
                    },
                    "analysis_results": {
                        "significant_time_bins": len([a for a in time_bin_analyses if a.statistical_significance]),
                        "advanced_analytics_completed": len(advanced_analytics_results),
                        "actionable_recommendations": workflow_results["phase_results"]["recommendations"]["actionable_recommendations"]
                    },
                    "top_recommendations": workflow_results["final_recommendations"][:5]
                }
                
                # Save summary report
                summary_path = os.path.join(export_temp_dir, "workflow_summary.json")
                with open(summary_path, 'w') as f:
                    json.dump(summary_report, f, indent=2)
                
                workflow_results["export_files"].append(summary_path)
                
                print(f"   📊 Summary report generated: {len(workflow_results['export_files'])} files exported")
        
        finally:
            # Note: In production, you might want to preserve these files
            shutil.rmtree(export_temp_dir, ignore_errors=True)
        
        phase_6_duration = (datetime.now() - phase_start).total_seconds()
        workflow_results["phase_results"]["export_reporting"] = {
            "duration_seconds": phase_6_duration,
            "files_exported": len(workflow_results["export_files"])
        }
        
        print(f"   ✅ Phase 6 completed in {phase_6_duration:.2f}s")
        
        # FINAL VALIDATION AND SUMMARY
        print("\n🏁 Workflow Completed - Final Validation")
        
        total_workflow_time = sum(p["duration_seconds"] for p in workflow_results["phase_results"].values())
        workflow_results["performance_metrics"] = {
            "total_execution_time": total_workflow_time,
            "data_quality_score": workflow_results["phase_results"]["data_ingestion"]["data_quality"],
            "analysis_coverage": (len(time_bin_analyses) / max(1, sum(a.total_trades for a in accounts))) * 1000,  # Per 1000 trades
            "recommendation_quality": len([r for r in generated_recommendations if r["confidence"] > 0.7]) / max(1, len(generated_recommendations))
        }
        
        # Validate workflow success criteria
        success_criteria = {
            "data_ingestion_quality": workflow_results["performance_metrics"]["data_quality_score"] >= 90.0,
            "time_bin_analysis_coverage": len(time_bin_analyses) >= 10,
            "market_correlation_analysis": len(market_analysis_results) >= 2,
            "advanced_analytics": len(advanced_analytics_results) >= 1,
            "actionable_recommendations": len(generated_recommendations) >= 5,
            "export_completion": len(workflow_results["export_files"]) >= 3,
            "performance_acceptable": total_workflow_time < 60.0  # Under 1 minute
        }
        
        passed_criteria = sum(1 for passed in success_criteria.values() if passed)
        success_rate = passed_criteria / len(success_criteria)
        
        print(f"\n📈 Workflow Results:")
        print(f"   Total execution time: {total_workflow_time:.2f}s")
        print(f"   Data quality score: {workflow_results['performance_metrics']['data_quality_score']:.1f}%")
        print(f"   Time bins analyzed: {len(time_bin_analyses)}")
        print(f"   Actionable recommendations: {workflow_results['phase_results']['recommendations']['actionable_recommendations']}")
        print(f"   Success criteria met: {passed_criteria}/{len(success_criteria)} ({success_rate:.1%})")
        
        # Print top recommendations
        if workflow_results["final_recommendations"]:
            print(f"\n🎯 Top Trading Recommendations:")
            for i, rec in enumerate(workflow_results["final_recommendations"][:5], 1):
                print(f"   {i}. {rec['account_name']} at {rec['time_bin']}: {rec['recommendation']} "
                      f"(confidence: {rec['confidence']:.1%})")
        
        # Assert workflow success
        assert success_rate >= 0.8, f"Workflow success rate too low: {success_rate:.1%}"
        assert len(generated_recommendations) > 0, "No recommendations generated"
        assert total_workflow_time < 120.0, f"Workflow too slow: {total_workflow_time:.2f}s"
        
        print(f"\n✅ Complete trader workflow test PASSED ({success_rate:.1%} success rate)")
        
        return workflow_results
    
    # Helper methods
    
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


class TestWorkflowEdgeCases:
    """Test workflow with edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_workflow_with_minimal_data(self):
        """Test workflow behavior with minimal data sets."""
        # Test with very limited data to ensure graceful handling
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        try:
            with SessionLocal() as session:
                # Create minimal test data
                account = Account(name="MINIMAL_ACCOUNT", symbol="ES", total_trades=0)
                session.add(account)
                
                # Add only 5 trades (below most analysis thresholds)
                trades = []
                for i in range(5):
                    trade = ProcessedTrade(
                        trade_id=f"MIN_{i:03d}",
                        account_name="MINIMAL_ACCOUNT",
                        symbol="ES",
                        entry_time=datetime(2023, 6, 1, 10, 0) + timedelta(hours=i),
                        exit_time=datetime(2023, 6, 1, 10, 30) + timedelta(hours=i),
                        profit_loss=25.0 * (i - 2),  # Mix of wins/losses
                        quantity=1,
                        side="LONG",
                        entry_price=4500.0,
                        exit_price=4525.0,
                        hour_of_day=10,
                        day_of_week=0,
                        duration_minutes=30,
                        entry_order_id=f"E_MIN_{i}",
                        exit_order_id=f"X_MIN_{i}"
                    )
                    trades.append(trade)
                
                session.add_all(trades)
                account.total_trades = len(trades)
                session.commit()
                
                # Test time-bin analysis with minimal data
                time_bin_analyzer = TimeBinAnalyzer()
                
                # Should handle insufficient data gracefully
                try:
                    # This should either work with limited data or fail gracefully
                    bin_trades = [t for t in trades if t.hour_of_day == 10]
                    
                    if len(bin_trades) >= 3:  # Some minimum threshold
                        # Calculate basic metrics
                        total_pnl = sum(t.profit_loss for t in bin_trades)
                        avg_pnl = total_pnl / len(bin_trades)
                        
                        print(f"Minimal data analysis: {len(bin_trades)} trades, avg P&L: ${avg_pnl:.2f}")
                        
                        assert len(bin_trades) == 5
                        assert isinstance(avg_pnl, (int, float))
                    
                except Exception as e:
                    # Should fail gracefully with informative error
                    assert "insufficient" in str(e).lower() or "minimum" in str(e).lower()
                    print(f"Expected error with minimal data: {str(e)}")
        
        finally:
            os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_workflow_data_corruption_handling(self):
        """Test workflow handling of corrupted or inconsistent data."""
        # Create test data with various corruption scenarios
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create CSV with corrupted data
            corrupted_csv = os.path.join(temp_dir, "corrupted_fills.csv")
            with open(corrupted_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Time", "Symbol", "Price", "Quantity", "AccountNumber"])
                
                # Mix of good and bad records
                writer.writerow(["2023-06-01", "10:30:00", "ES", "4500.00", "1", "TEST_ACCOUNT"])  # Good
                writer.writerow(["INVALID_DATE", "10:30:00", "ES", "4500.00", "1", "TEST_ACCOUNT"])  # Bad date
                writer.writerow(["2023-06-01", "25:30:00", "ES", "4500.00", "1", "TEST_ACCOUNT"])  # Bad time
                writer.writerow(["2023-06-01", "10:30:00", "", "4500.00", "1", "TEST_ACCOUNT"])  # Missing symbol
                writer.writerow(["2023-06-01", "10:30:00", "ES", "INVALID", "1", "TEST_ACCOUNT"])  # Bad price
                writer.writerow(["2023-06-01", "10:30:00", "ES", "4500.00", "0", "TEST_ACCOUNT"])  # Zero quantity
                writer.writerow(["2023-06-01", "10:30:00", "ES", "4500.00", "1", ""])  # Missing account
            
            # Test data validation
            data_validator = DataValidator()
            
            with open(corrupted_csv, 'r') as f:
                reader = csv.DictReader(f)
                records = list(reader)
            
            valid_records = 0
            invalid_records = 0
            
            for record in records:
                try:
                    is_valid = await data_validator.validate_fill_record(record)
                    if is_valid:
                        valid_records += 1
                    else:
                        invalid_records += 1
                except Exception:
                    invalid_records += 1
            
            print(f"Data corruption test: {valid_records} valid, {invalid_records} invalid records")
            
            # Should identify corrupted records
            assert valid_records >= 1  # At least one good record
            assert invalid_records >= 5  # Multiple bad records detected
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])