"""
DataExportEngine for comprehensive trading data export functionality.

This module provides professional-grade export capabilities for:
- Time-bin trade lists (CSV/Excel)
- Analytics results and performance metrics
- Market correlation analysis data
- Organized export packages with structured file organization

Requirements: 13.1, 13.3, 13.4
"""

import os
import json
import csv
import zipfile
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
import logging

from ...database.connection import get_db_session
from ...models.database import ProcessedTrade as ProcessedTradeORM
from ..time_bin_analyzer import TimeBinAnalyzer, TimeBin, SimpleTrade
from ..performance_metrics_calculator import PerformanceMetricsCalculator
# from ..vix_regime_analyzer import VIXRegimeAnalyzer  # Temporarily disabled - class doesn't exist
from ..benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ExportConfiguration:
    """Configuration for data export operations."""
    
    include_raw_trades: bool = True
    include_performance_metrics: bool = True
    include_statistical_analysis: bool = True
    include_market_correlation: bool = True
    include_vix_regime_data: bool = True
    include_benchmark_comparison: bool = True
    
    # File format options
    export_formats: List[str] = None  # ['csv', 'excel', 'json']
    date_format: str = '%Y-%m-%d %H:%M:%S'
    decimal_places: int = 6
    
    # Output organization
    create_organized_structure: bool = True
    include_metadata: bool = True
    compress_output: bool = False
    
    def __post_init__(self):
        if self.export_formats is None:
            self.export_formats = ['csv', 'excel']


@dataclass
class ExportMetadata:
    """Metadata for export operations."""
    
    export_timestamp: datetime
    account_name: str
    time_bin_hour: Optional[int]
    time_bin_minute: Optional[int]
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    total_trades: int
    export_formats: List[str]
    file_paths: Dict[str, str]
    configuration: ExportConfiguration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for JSON export."""
        result = asdict(self)
        # Convert datetime objects to strings
        result['export_timestamp'] = self.export_timestamp.isoformat()
        if self.date_range_start:
            result['date_range_start'] = self.date_range_start.isoformat()
        if self.date_range_end:
            result['date_range_end'] = self.date_range_end.isoformat()
        return result


class DataExportEngine:
    """
    Comprehensive data export engine for trading analytics platform.
    
    Provides professional-grade export capabilities with multiple format support,
    organized file structure, and comprehensive metadata tracking.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the DataExportEngine."""
        self.db_session = db_session or get_db_session()
        self.time_bin_analyzer = TimeBinAnalyzer(self.db_session)
        self.performance_calculator = PerformanceMetricsCalculator(self.db_session)
        # self.vix_analyzer = VIXRegimeAnalyzer(self.db_session)  # Temporarily disabled
        self.benchmark_analyzer = BenchmarkComparisonAnalyzer(self.db_session)
        
        # Export tracking
        self.export_history: List[ExportMetadata] = []
        
    def export_time_bin_trades(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        output_path: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        config: Optional[ExportConfiguration] = None
    ) -> ExportMetadata:
        """
        Export time-bin trades to CSV/Excel with comprehensive trade details.
        
        Args:
            account_name: Trading account name
            hour: Hour of day (0-23)
            minute_bin: Minute bin (0 or 30)
            output_path: Base output directory path
            start_date: Optional start date filter
            end_date: Optional end date filter
            config: Export configuration options
            
        Returns:
            ExportMetadata: Metadata about the export operation
        """
        if config is None:
            config = ExportConfiguration()
            
        logger.info(f"Starting time-bin trades export for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            # Create time bin
            time_bin = TimeBin(account_name=account_name, hour=hour, minute_bin=minute_bin)
            
            # Retrieve trades
            trades = self.time_bin_analyzer.get_time_bin_trades(
                time_bin=time_bin,
                start_date=start_date,
                end_date=end_date
            )
            
            if not trades:
                logger.warning(f"No trades found for {account_name} {hour}:{minute_bin:02d}")
                
            # Prepare export directory
            export_dir = self._prepare_export_directory(output_path, account_name, hour, minute_bin)
            file_paths = {}
            
            # Export to different formats
            if 'csv' in config.export_formats:
                csv_path = self._export_trades_to_csv(trades, export_dir, config)
                file_paths['csv'] = csv_path
                
            if 'excel' in config.export_formats:
                excel_path = self._export_trades_to_excel(trades, export_dir, config)
                file_paths['excel'] = excel_path
                
            if 'json' in config.export_formats:
                json_path = self._export_trades_to_json(trades, export_dir, config)
                file_paths['json'] = json_path
            
            # Create metadata
            metadata = ExportMetadata(
                export_timestamp=datetime.now(),
                account_name=account_name,
                time_bin_hour=hour,
                time_bin_minute=minute_bin,
                date_range_start=start_date,
                date_range_end=end_date,
                total_trades=len(trades),
                export_formats=config.export_formats,
                file_paths=file_paths,
                configuration=config
            )
            
            # Export metadata if requested
            if config.include_metadata:
                metadata_path = os.path.join(export_dir, 'export_metadata.json')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata.to_dict(), f, indent=2)
                file_paths['metadata'] = metadata_path
            
            # Track export
            self.export_history.append(metadata)
            
            logger.info(f"Time-bin trades export completed: {len(trades)} trades exported")
            return metadata
            
        except Exception as e:
            logger.error(f"Error exporting time-bin trades: {str(e)}")
            raise
    
    def export_analysis_results(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        output_path: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        config: Optional[ExportConfiguration] = None
    ) -> ExportMetadata:
        """
        Export comprehensive analysis results including performance metrics and statistics.
        
        Args:
            account_name: Trading account name
            hour: Hour of day (0-23)
            minute_bin: Minute bin (0 or 30)
            output_path: Base output directory path
            start_date: Optional start date filter
            end_date: Optional end date filter
            config: Export configuration options
            
        Returns:
            ExportMetadata: Metadata about the export operation
        """
        if config is None:
            config = ExportConfiguration()
            
        logger.info(f"Starting analysis results export for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            # Create time bin
            time_bin = TimeBin(account_name=account_name, hour=hour, minute_bin=minute_bin)
            
            # Collect analysis data
            analysis_data = {}
            
            if config.include_performance_metrics:
                # Get performance metrics
                trades = self.time_bin_analyzer.get_time_bin_trades(
                    time_bin=time_bin,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if trades:
                    performance_metrics = self.performance_calculator.calculate_comprehensive_metrics(trades)
                    analysis_data['performance_metrics'] = performance_metrics
                
            if config.include_statistical_analysis:
                # Get statistical analysis
                stats_results = self.time_bin_analyzer.analyze_time_bin_performance(
                    time_bin, start_date, end_date
                )
                analysis_data['statistical_analysis'] = stats_results
            
            if config.include_vix_regime_data:
                # Get VIX regime analysis - temporarily disabled
                try:
                    # vix_analysis = self.vix_analyzer.analyze_regime_performance(
                    #     account_name=account_name,
                    #     hour=hour,
                    #     minute_bin=minute_bin,
                    #     start_date=start_date,
                    #     end_date=end_date
                    # )
                    # analysis_data['vix_regime_analysis'] = vix_analysis
                    pass  # Placeholder
                except Exception as e:
                    logger.warning(f"VIX regime analysis failed: {e}")
            
            if config.include_benchmark_comparison:
                # Get benchmark comparison
                try:
                    benchmark_data = self.benchmark_analyzer.analyze_benchmark_comparison(
                        account_name=account_name,
                        hour=hour,
                        minute_bin=minute_bin,
                        start_date=start_date,
                        end_date=end_date
                    )
                    analysis_data['benchmark_comparison'] = benchmark_data
                except Exception as e:
                    logger.warning(f"Benchmark comparison failed: {e}")
            
            # Prepare export directory
            export_dir = self._prepare_export_directory(output_path, account_name, hour, minute_bin)
            file_paths = {}
            
            # Export analysis data
            if 'json' in config.export_formats:
                json_path = self._export_analysis_to_json(analysis_data, export_dir, config)
                file_paths['analysis_json'] = json_path
                
            if 'excel' in config.export_formats:
                excel_path = self._export_analysis_to_excel(analysis_data, export_dir, config)
                file_paths['analysis_excel'] = excel_path
                
            if 'csv' in config.export_formats:
                csv_paths = self._export_analysis_to_csv(analysis_data, export_dir, config)
                file_paths.update(csv_paths)
            
            # Create metadata
            metadata = ExportMetadata(
                export_timestamp=datetime.now(),
                account_name=account_name,
                time_bin_hour=hour,
                time_bin_minute=minute_bin,
                date_range_start=start_date,
                date_range_end=end_date,
                total_trades=len(analysis_data.get('performance_metrics', {}).get('trades', [])),
                export_formats=config.export_formats,
                file_paths=file_paths,
                configuration=config
            )
            
            # Export metadata
            if config.include_metadata:
                metadata_path = os.path.join(export_dir, 'analysis_metadata.json')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata.to_dict(), f, indent=2)
                file_paths['metadata'] = metadata_path
            
            # Track export
            self.export_history.append(metadata)
            
            logger.info("Analysis results export completed")
            return metadata
            
        except Exception as e:
            logger.error(f"Error exporting analysis results: {str(e)}")
            raise
    
    def export_market_correlation_data(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        output_path: str,
        benchmarks: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        config: Optional[ExportConfiguration] = None
    ) -> ExportMetadata:
        """
        Export market correlation analysis data with benchmark comparisons.
        
        Args:
            account_name: Trading account name
            hour: Hour of day (0-23)
            minute_bin: Minute bin (0 or 30)
            output_path: Base output directory path
            benchmarks: List of benchmark symbols (default: ['SPY', 'QQQ', 'VIX'])
            start_date: Optional start date filter
            end_date: Optional end date filter
            config: Export configuration options
            
        Returns:
            ExportMetadata: Metadata about the export operation
        """
        if config is None:
            config = ExportConfiguration()
            
        if benchmarks is None:
            benchmarks = ['SPY', 'QQQ', 'VIX']
            
        logger.info(f"Starting market correlation export for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            # Collect correlation data
            correlation_data = {}
            
            # Get time-bin performance for correlation analysis
            time_bin = TimeBin(account_name=account_name, hour=hour, minute_bin=minute_bin)
            trades = self.time_bin_analyzer.get_time_bin_trades(
                time_bin=time_bin,
                start_date=start_date,
                end_date=end_date
            )
            
            if not trades:
                logger.warning(f"No trades found for correlation analysis")
                correlation_data['trades'] = []
            else:
                correlation_data['trades'] = [asdict(trade) for trade in trades]
            
            # Analyze correlation with benchmarks
            if config.include_benchmark_comparison:
                benchmark_correlations = {}
                
                for benchmark in benchmarks:
                    try:
                        correlation_result = self.benchmark_analyzer.calculate_correlation_with_benchmark(
                            account_name=account_name,
                            hour=hour,
                            minute_bin=minute_bin,
                            benchmark_symbol=benchmark,
                            start_date=start_date,
                            end_date=end_date
                        )
                        benchmark_correlations[benchmark] = correlation_result
                    except Exception as e:
                        logger.warning(f"Correlation analysis with {benchmark} failed: {e}")
                        benchmark_correlations[benchmark] = None
                
                correlation_data['benchmark_correlations'] = benchmark_correlations
            
            # Get VIX regime correlation if requested
            if config.include_vix_regime_data:
                try:
                    # vix_correlation = self.vix_analyzer.calculate_vix_correlation(
                    #     account_name=account_name,
                    #     hour=hour,
                    #     minute_bin=minute_bin,
                    #     start_date=start_date,
                    #     end_date=end_date
                    # )
                    # correlation_data['vix_correlation'] = vix_correlation
                    pass  # Placeholder
                except Exception as e:
                    logger.warning(f"VIX correlation analysis failed: {e}")
            
            # Calculate rolling correlations
            rolling_correlations = self._calculate_rolling_correlations(
                trades, benchmarks, start_date, end_date
            )
            correlation_data['rolling_correlations'] = rolling_correlations
            
            # Prepare export directory
            export_dir = self._prepare_export_directory(output_path, account_name, hour, minute_bin)
            file_paths = {}
            
            # Export correlation data
            if 'json' in config.export_formats:
                json_path = self._export_correlation_to_json(correlation_data, export_dir, config)
                file_paths['correlation_json'] = json_path
                
            if 'excel' in config.export_formats:
                excel_path = self._export_correlation_to_excel(correlation_data, export_dir, config)
                file_paths['correlation_excel'] = excel_path
                
            if 'csv' in config.export_formats:
                csv_paths = self._export_correlation_to_csv(correlation_data, export_dir, config)
                file_paths.update(csv_paths)
            
            # Create metadata
            metadata = ExportMetadata(
                export_timestamp=datetime.now(),
                account_name=account_name,
                time_bin_hour=hour,
                time_bin_minute=minute_bin,
                date_range_start=start_date,
                date_range_end=end_date,
                total_trades=len(trades) if trades else 0,
                export_formats=config.export_formats,
                file_paths=file_paths,
                configuration=config
            )
            
            # Export metadata
            if config.include_metadata:
                metadata_path = os.path.join(export_dir, 'correlation_metadata.json')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata.to_dict(), f, indent=2)
                file_paths['metadata'] = metadata_path
            
            # Track export
            self.export_history.append(metadata)
            
            logger.info("Market correlation export completed")
            return metadata
            
        except Exception as e:
            logger.error(f"Error exporting market correlation data: {str(e)}")
            raise
    
    def create_export_package(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        output_path: str,
        package_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        config: Optional[ExportConfiguration] = None
    ) -> ExportMetadata:
        """
        Create a comprehensive export package with organized file structure.
        
        Args:
            account_name: Trading account name
            hour: Hour of day (0-23)
            minute_bin: Minute bin (0 or 30)
            output_path: Base output directory path
            package_name: Optional custom package name
            start_date: Optional start date filter
            end_date: Optional end date filter
            config: Export configuration options
            
        Returns:
            ExportMetadata: Metadata about the export package
        """
        if config is None:
            config = ExportConfiguration()
            config.create_organized_structure = True
            config.include_metadata = True
        
        if package_name is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            package_name = f"{account_name}_{hour:02d}{minute_bin:02d}_{timestamp}"
        
        logger.info(f"Creating comprehensive export package: {package_name}")
        
        try:
            # Create package directory
            package_dir = os.path.join(output_path, package_name)
            os.makedirs(package_dir, exist_ok=True)
            
            # Create organized subdirectories
            subdirs = {
                'trades': os.path.join(package_dir, '01_trades'),
                'analytics': os.path.join(package_dir, '02_analytics'),
                'correlations': os.path.join(package_dir, '03_correlations'),
                'metadata': os.path.join(package_dir, '04_metadata'),
                'summary': os.path.join(package_dir, '00_summary')
            }
            
            for subdir in subdirs.values():
                os.makedirs(subdir, exist_ok=True)
            
            all_file_paths = {}
            
            # 1. Export trades
            logger.info("Exporting trades data...")
            trades_metadata = self.export_time_bin_trades(
                account_name, hour, minute_bin, subdirs['trades'],
                start_date, end_date, config
            )
            all_file_paths.update({f"trades_{k}": v for k, v in trades_metadata.file_paths.items()})
            
            # 2. Export analysis results
            logger.info("Exporting analysis results...")
            analysis_metadata = self.export_analysis_results(
                account_name, hour, minute_bin, subdirs['analytics'],
                start_date, end_date, config
            )
            all_file_paths.update({f"analysis_{k}": v for k, v in analysis_metadata.file_paths.items()})
            
            # 3. Export correlation data
            logger.info("Exporting correlation data...")
            correlation_metadata = self.export_market_correlation_data(
                account_name, hour, minute_bin, subdirs['correlations'],
                start_date=start_date, end_date=end_date, config=config
            )
            all_file_paths.update({f"correlation_{k}": v for k, v in correlation_metadata.file_paths.items()})
            
            # 4. Create summary report
            logger.info("Creating summary report...")
            summary_path = self._create_summary_report(
                package_dir, account_name, hour, minute_bin,
                trades_metadata, analysis_metadata, correlation_metadata,
                config
            )
            all_file_paths['summary_report'] = summary_path
            
            # 5. Create package metadata
            package_metadata = ExportMetadata(
                export_timestamp=datetime.now(),
                account_name=account_name,
                time_bin_hour=hour,
                time_bin_minute=minute_bin,
                date_range_start=start_date,
                date_range_end=end_date,
                total_trades=trades_metadata.total_trades,
                export_formats=config.export_formats,
                file_paths=all_file_paths,
                configuration=config
            )
            
            # Export package metadata
            package_metadata_path = os.path.join(subdirs['metadata'], 'package_metadata.json')
            with open(package_metadata_path, 'w') as f:
                json.dump(package_metadata.to_dict(), f, indent=2)
            all_file_paths['package_metadata'] = package_metadata_path
            
            # 6. Create README
            readme_path = self._create_package_readme(package_dir, package_metadata)
            all_file_paths['readme'] = readme_path
            
            # 7. Compress if requested
            if config.compress_output:
                logger.info("Compressing export package...")
                zip_path = self._compress_export_package(package_dir, output_path)
                all_file_paths['compressed_package'] = zip_path
            
            # Track export
            self.export_history.append(package_metadata)
            
            logger.info(f"Export package created successfully: {package_name}")
            return package_metadata
            
        except Exception as e:
            logger.error(f"Error creating export package: {str(e)}")
            raise
    
    # Private helper methods
    
    def _prepare_export_directory(
        self, 
        base_path: str, 
        account_name: str, 
        hour: int, 
        minute_bin: int
    ) -> str:
        """Prepare and create export directory structure."""
        export_dir = os.path.join(base_path, f"{account_name}_{hour:02d}{minute_bin:02d}")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir
    
    def _export_trades_to_csv(
        self, 
        trades: List[SimpleTrade], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export trades to CSV format."""
        csv_path = os.path.join(export_dir, 'trades.csv')
        
        if not trades:
            # Create empty CSV with headers
            with open(csv_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'trade_id', 'account_name', 'symbol', 'entry_time', 'exit_time',
                    'entry_price', 'exit_price', 'quantity', 'side', 'profit_loss',
                    'commission', 'duration_minutes', 'hour_of_day', 'day_of_week'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
        else:
            with open(csv_path, 'w', newline='') as csvfile:
                fieldnames = list(asdict(trades[0]).keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in trades:
                    trade_dict = asdict(trade)
                    # Format datetime objects
                    if isinstance(trade_dict['entry_time'], datetime):
                        trade_dict['entry_time'] = trade_dict['entry_time'].strftime(config.date_format)
                    if isinstance(trade_dict['exit_time'], datetime):
                        trade_dict['exit_time'] = trade_dict['exit_time'].strftime(config.date_format)
                    
                    # Round numeric fields
                    for field in ['entry_price', 'exit_price', 'profit_loss', 'commission']:
                        if field in trade_dict and isinstance(trade_dict[field], (int, float)):
                            trade_dict[field] = round(trade_dict[field], config.decimal_places)
                    
                    writer.writerow(trade_dict)
        
        return csv_path
    
    def _export_trades_to_excel(
        self, 
        trades: List[SimpleTrade], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export trades to Excel format."""
        excel_path = os.path.join(export_dir, 'trades.xlsx')
        
        if not trades:
            # Create empty DataFrame with columns
            df = pd.DataFrame(columns=[
                'trade_id', 'account_name', 'symbol', 'entry_time', 'exit_time',
                'entry_price', 'exit_price', 'quantity', 'side', 'profit_loss',
                'commission', 'duration_minutes', 'hour_of_day', 'day_of_week'
            ])
        else:
            # Convert trades to DataFrame
            trades_data = [asdict(trade) for trade in trades]
            df = pd.DataFrame(trades_data)
            
            # Round numeric columns
            numeric_cols = ['entry_price', 'exit_price', 'profit_loss', 'commission']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = df[col].round(config.decimal_places)
        
        # Export to Excel
        df.to_excel(excel_path, index=False)
        return excel_path
    
    def _export_trades_to_json(
        self, 
        trades: List[SimpleTrade], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export trades to JSON format."""
        json_path = os.path.join(export_dir, 'trades.json')
        
        if not trades:
            trades_data = []
        else:
            trades_data = []
            for trade in trades:
                trade_dict = asdict(trade)
                # Convert datetime objects to strings
                if isinstance(trade_dict['entry_time'], datetime):
                    trade_dict['entry_time'] = trade_dict['entry_time'].isoformat()
                if isinstance(trade_dict['exit_time'], datetime):
                    trade_dict['exit_time'] = trade_dict['exit_time'].isoformat()
                trades_data.append(trade_dict)
        
        with open(json_path, 'w') as f:
            json.dump(trades_data, f, indent=2, default=str)
        
        return json_path
    
    def _export_analysis_to_json(
        self, 
        analysis_data: Dict[str, Any], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export analysis results to JSON format."""
        json_path = os.path.join(export_dir, 'analysis_results.json')
        
        with open(json_path, 'w') as f:
            json.dump(analysis_data, f, indent=2, default=str)
        
        return json_path
    
    def _export_analysis_to_excel(
        self, 
        analysis_data: Dict[str, Any], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export analysis results to Excel format with multiple sheets."""
        excel_path = os.path.join(export_dir, 'analysis_results.xlsx')
        
        with pd.ExcelWriter(excel_path) as writer:
            # Performance metrics sheet
            if 'performance_metrics' in analysis_data:
                perf_data = analysis_data['performance_metrics']
                if isinstance(perf_data, dict):
                    # Convert to DataFrame format
                    df_data = []
                    for key, value in perf_data.items():
                        if not isinstance(value, (list, dict)):
                            df_data.append({'Metric': key, 'Value': value})
                    
                    if df_data:
                        df = pd.DataFrame(df_data)
                        df.to_excel(writer, sheet_name='Performance_Metrics', index=False)
            
            # Statistical analysis sheet
            if 'statistical_analysis' in analysis_data:
                stats_data = analysis_data['statistical_analysis']
                if isinstance(stats_data, dict):
                    df_data = []
                    for key, value in stats_data.items():
                        if not isinstance(value, (list, dict)):
                            df_data.append({'Test': key, 'Result': value})
                    
                    if df_data:
                        df = pd.DataFrame(df_data)
                        df.to_excel(writer, sheet_name='Statistical_Analysis', index=False)
        
        return excel_path
    
    def _export_analysis_to_csv(
        self, 
        analysis_data: Dict[str, Any], 
        export_dir: str,
        config: ExportConfiguration
    ) -> Dict[str, str]:
        """Export analysis results to multiple CSV files."""
        csv_paths = {}
        
        # Performance metrics CSV
        if 'performance_metrics' in analysis_data:
            csv_path = os.path.join(export_dir, 'performance_metrics.csv')
            perf_data = analysis_data['performance_metrics']
            
            if isinstance(perf_data, dict):
                with open(csv_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Metric', 'Value'])
                    
                    for key, value in perf_data.items():
                        if not isinstance(value, (list, dict)):
                            writer.writerow([key, value])
                
                csv_paths['performance_metrics_csv'] = csv_path
        
        return csv_paths
    
    def _export_correlation_to_json(
        self, 
        correlation_data: Dict[str, Any], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export correlation data to JSON format."""
        json_path = os.path.join(export_dir, 'correlation_analysis.json')
        
        with open(json_path, 'w') as f:
            json.dump(correlation_data, f, indent=2, default=str)
        
        return json_path
    
    def _export_correlation_to_excel(
        self, 
        correlation_data: Dict[str, Any], 
        export_dir: str,
        config: ExportConfiguration
    ) -> str:
        """Export correlation data to Excel format."""
        excel_path = os.path.join(export_dir, 'correlation_analysis.xlsx')
        
        with pd.ExcelWriter(excel_path) as writer:
            # Benchmark correlations sheet
            if 'benchmark_correlations' in correlation_data:
                bench_data = correlation_data['benchmark_correlations']
                if isinstance(bench_data, dict):
                    df_data = []
                    for benchmark, correlation in bench_data.items():
                        if correlation is not None:
                            df_data.append({
                                'Benchmark': benchmark,
                                'Correlation': correlation if isinstance(correlation, (int, float)) else str(correlation)
                            })
                    
                    if df_data:
                        df = pd.DataFrame(df_data)
                        df.to_excel(writer, sheet_name='Benchmark_Correlations', index=False)
        
        return excel_path
    
    def _export_correlation_to_csv(
        self, 
        correlation_data: Dict[str, Any], 
        export_dir: str,
        config: ExportConfiguration
    ) -> Dict[str, str]:
        """Export correlation data to CSV files."""
        csv_paths = {}
        
        # Benchmark correlations CSV
        if 'benchmark_correlations' in correlation_data:
            csv_path = os.path.join(export_dir, 'benchmark_correlations.csv')
            bench_data = correlation_data['benchmark_correlations']
            
            if isinstance(bench_data, dict):
                with open(csv_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Benchmark', 'Correlation'])
                    
                    for benchmark, correlation in bench_data.items():
                        if correlation is not None:
                            writer.writerow([benchmark, correlation])
                
                csv_paths['benchmark_correlations_csv'] = csv_path
        
        return csv_paths
    
    def _calculate_rolling_correlations(
        self,
        trades: List[SimpleTrade],
        benchmarks: List[str],
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict[str, Any]:
        """Calculate rolling correlations with benchmarks."""
        # This is a placeholder for rolling correlation calculation
        # In a real implementation, this would fetch market data and calculate rolling correlations
        return {
            'window_size': 30,
            'correlations': {},
            'note': 'Rolling correlations require market data integration'
        }
    
    def _create_summary_report(
        self,
        package_dir: str,
        account_name: str,
        hour: int,
        minute_bin: int,
        trades_metadata: ExportMetadata,
        analysis_metadata: ExportMetadata,
        correlation_metadata: ExportMetadata,
        config: ExportConfiguration
    ) -> str:
        """Create a comprehensive summary report."""
        summary_path = os.path.join(package_dir, '00_summary', 'export_summary.txt')
        
        with open(summary_path, 'w') as f:
            f.write(f"Trading Analytics Export Summary\n")
            f.write(f"=" * 50 + "\n\n")
            
            f.write(f"Account: {account_name}\n")
            f.write(f"Time Bin: {hour:02d}:{minute_bin:02d}\n")
            f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"Export Statistics:\n")
            f.write(f"- Total Trades: {trades_metadata.total_trades}\n")
            f.write(f"- Export Formats: {', '.join(config.export_formats)}\n")
            f.write(f"- Date Range: {trades_metadata.date_range_start or 'All'} to {trades_metadata.date_range_end or 'All'}\n\n")
            
            f.write(f"Exported Files:\n")
            f.write(f"- Trade Data Files: {len(trades_metadata.file_paths)}\n")
            f.write(f"- Analysis Files: {len(analysis_metadata.file_paths)}\n")
            f.write(f"- Correlation Files: {len(correlation_metadata.file_paths)}\n\n")
            
            f.write(f"Package Structure:\n")
            f.write(f"- 01_trades/: Raw trade data exports\n")
            f.write(f"- 02_analytics/: Performance metrics and statistical analysis\n")
            f.write(f"- 03_correlations/: Market correlation analysis\n")
            f.write(f"- 04_metadata/: Export metadata and configuration\n")
            f.write(f"- 00_summary/: This summary report\n\n")
            
            f.write(f"Configuration:\n")
            f.write(f"- Include Raw Trades: {config.include_raw_trades}\n")
            f.write(f"- Include Performance Metrics: {config.include_performance_metrics}\n")
            f.write(f"- Include Statistical Analysis: {config.include_statistical_analysis}\n")
            f.write(f"- Include Market Correlation: {config.include_market_correlation}\n")
            f.write(f"- Include VIX Regime Data: {config.include_vix_regime_data}\n")
            f.write(f"- Include Benchmark Comparison: {config.include_benchmark_comparison}\n")
        
        return summary_path
    
    def _create_package_readme(
        self,
        package_dir: str,
        package_metadata: ExportMetadata
    ) -> str:
        """Create a README file for the export package."""
        readme_path = os.path.join(package_dir, 'README.md')
        
        with open(readme_path, 'w') as f:
            f.write(f"# Trading Analytics Export Package\n\n")
            
            f.write(f"**Account:** {package_metadata.account_name}  \n")
            f.write(f"**Time Bin:** {package_metadata.time_bin_hour:02d}:{package_metadata.time_bin_minute:02d}  \n")
            f.write(f"**Export Date:** {package_metadata.export_timestamp.strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Total Trades:** {package_metadata.total_trades}  \n\n")
            
            f.write(f"## Package Contents\n\n")
            f.write(f"### 00_summary/\n")
            f.write(f"- `export_summary.txt`: Comprehensive summary of the export operation\n")
            f.write(f"- `README.md`: This file\n\n")
            
            f.write(f"### 01_trades/\n")
            f.write(f"Raw trading data in multiple formats:\n")
            for format_type in package_metadata.export_formats:
                f.write(f"- `trades.{format_type}`: Trade data in {format_type.upper()} format\n")
            f.write(f"\n")
            
            f.write(f"### 02_analytics/\n")
            f.write(f"Performance metrics and statistical analysis:\n")
            f.write(f"- Performance metrics calculations\n")
            f.write(f"- Statistical significance testing\n")
            f.write(f"- Risk-adjusted returns analysis\n\n")
            
            f.write(f"### 03_correlations/\n")
            f.write(f"Market correlation analysis:\n")
            f.write(f"- Benchmark correlation analysis (SPY, QQQ, VIX)\n")
            f.write(f"- VIX regime correlation analysis\n")
            f.write(f"- Rolling correlation calculations\n\n")
            
            f.write(f"### 04_metadata/\n")
            f.write(f"Export metadata and configuration:\n")
            f.write(f"- `package_metadata.json`: Complete export metadata\n")
            f.write(f"- Configuration settings and parameters\n\n")
            
            f.write(f"## Data Formats\n\n")
            f.write(f"- **CSV**: Comma-separated values for easy spreadsheet import\n")
            f.write(f"- **Excel**: Microsoft Excel format with multiple sheets\n")
            f.write(f"- **JSON**: JavaScript Object Notation for programmatic access\n\n")
            
            f.write(f"## Usage Notes\n\n")
            f.write(f"- All timestamps are in format: {package_metadata.configuration.date_format}\n")
            f.write(f"- Numeric values rounded to {package_metadata.configuration.decimal_places} decimal places\n")
            f.write(f"- Missing or null values are handled gracefully in all formats\n\n")
            
            f.write(f"---\n")
            f.write(f"*Generated by Trading Platform DataExportEngine*\n")
        
        return readme_path
    
    def _compress_export_package(
        self,
        package_dir: str,
        output_path: str
    ) -> str:
        """Compress the export package into a ZIP file."""
        package_name = os.path.basename(package_dir)
        zip_path = os.path.join(output_path, f"{package_name}.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, package_dir)
                    zipf.write(file_path, arcname)
        
        return zip_path
    
    def get_export_history(self) -> List[ExportMetadata]:
        """Get the history of export operations."""
        return self.export_history.copy()
    
    def clear_export_history(self) -> None:
        """Clear the export history."""
        self.export_history.clear()