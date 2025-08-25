"""
PDFReportGenerator for professional trading reports.

This module provides comprehensive PDF report generation capabilities for:
- Time-bin trading reports with standard sections
- Performance summary pages with key metrics
- Statistical analysis pages with significance testing
- Market correlation pages with benchmark comparisons
- Professional formatting with charts and tables

Requirements: 13.2, 13.5
"""

import os
import io
import base64
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from sqlalchemy.orm import Session
import logging

# PDF generation libraries
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, black, blue, red, green
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
        PageBreak, Image, KeepTogether
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.graphics.shapes import Drawing, Line
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("ReportLab not available. PDF generation will be limited.")

from ...database.connection import get_db_session
from ...models.database import ProcessedTrade as ProcessedTradeORM
from ..time_bin_analyzer import TimeBinAnalyzer, TimeBin, SimpleTrade
from ..performance_metrics_calculator import PerformanceMetricsCalculator
# from ..vix_regime_analyzer import VIXRegimeAnalyzer  # Temporarily disabled - class doesn't exist
from ..benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ReportConfiguration:
    """Configuration for PDF report generation."""
    
    # Page settings
    page_size: str = 'letter'  # 'letter', 'A4'
    margins: Dict[str, float] = None  # {'top': 1, 'bottom': 1, 'left': 1, 'right': 1} in inches
    
    # Report sections
    include_executive_summary: bool = True
    include_performance_summary: bool = True
    include_statistical_analysis: bool = True
    include_market_correlation: bool = True
    include_trade_details: bool = True
    include_charts: bool = True
    include_risk_analysis: bool = True
    
    # Formatting options
    chart_style: str = 'professional'  # 'professional', 'minimal', 'colorful'
    table_style: str = 'grid'  # 'grid', 'plain', 'fancy'
    font_size: int = 10
    chart_dpi: int = 300
    
    # Data options
    decimal_places: int = 4
    percentage_places: int = 2
    currency_symbol: str = '$'
    date_format: str = '%Y-%m-%d'
    
    # Color scheme
    primary_color: str = '#1f2937'
    secondary_color: str = '#3b82f6'
    success_color: str = '#10b981'
    warning_color: str = '#f59e0b'
    danger_color: str = '#ef4444'
    
    def __post_init__(self):
        if self.margins is None:
            self.margins = {'top': 1, 'bottom': 1, 'left': 1, 'right': 1}


@dataclass
class ReportMetadata:
    """Metadata for generated PDF reports."""
    
    report_id: str
    generation_timestamp: datetime
    account_name: str
    time_bin_hour: Optional[int]
    time_bin_minute: Optional[int]
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    total_trades: int
    report_sections: List[str]
    file_path: str
    file_size_bytes: int
    page_count: int
    configuration: ReportConfiguration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        result = asdict(self)
        result['generation_timestamp'] = self.generation_timestamp.isoformat()
        if self.date_range_start:
            result['date_range_start'] = self.date_range_start.isoformat()
        if self.date_range_end:
            result['date_range_end'] = self.date_range_end.isoformat()
        return result


class PDFReportGenerator:
    """
    Professional PDF report generator for trading analytics.
    
    Provides comprehensive PDF report generation with standard trading
    report sections, performance metrics, statistical analysis, and
    professional formatting.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the PDFReportGenerator."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is required for PDF generation. "
                "Install with: pip install reportlab"
            )
        
        self.db_session = db_session or get_db_session()
        self.time_bin_analyzer = TimeBinAnalyzer(self.db_session)
        self.performance_calculator = PerformanceMetricsCalculator(self.db_session)
        self.vix_analyzer = VIXRegimeAnalyzer(self.db_session)
        self.benchmark_analyzer = BenchmarkComparisonAnalyzer(self.db_session)
        
        # Report tracking
        self.report_history: List[ReportMetadata] = []
        
        # Setup matplotlib for professional charts
        plt.style.use('seaborn-v0_8-whitegrid')
        sns.set_palette("husl")
    
    def generate_time_bin_report(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        output_path: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        config: Optional[ReportConfiguration] = None
    ) -> ReportMetadata:
        """
        Generate comprehensive time-bin trading report.
        
        Args:
            account_name: Trading account name
            hour: Hour of day (0-23)
            minute_bin: Minute bin (0 or 30)
            output_path: Output file path for the PDF
            start_date: Optional start date filter
            end_date: Optional end date filter
            config: Report configuration options
            
        Returns:
            ReportMetadata: Metadata about the generated report
        """
        if config is None:
            config = ReportConfiguration()
            
        logger.info(f"Generating time-bin report for {account_name} {hour}:{minute_bin:02d}")
        
        try:
            # Generate unique report ID
            report_id = f"TB_{account_name}_{hour:02d}{minute_bin:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Collect data
            time_bin = TimeBin(account_name=account_name, hour=hour, minute_bin=minute_bin)
            
            # Get trades
            trades = self.time_bin_analyzer.get_time_bin_trades(
                time_bin=time_bin,
                start_date=start_date,
                end_date=end_date
            )
            
            # Calculate performance metrics
            performance_data = {}
            if config.include_performance_summary and trades:
                performance_data = self.performance_calculator.calculate_comprehensive_metrics(trades)
            
            # Get statistical analysis
            statistical_data = {}
            if config.include_statistical_analysis:
                statistical_data = self.time_bin_analyzer.analyze_time_bin_performance(
                    time_bin, start_date, end_date
                )
            
            # Get market correlation data
            correlation_data = {}
            if config.include_market_correlation:
                try:
                    correlation_data = self._collect_correlation_data(
                        account_name, hour, minute_bin, start_date, end_date
                    )
                except Exception as e:
                    logger.warning(f"Correlation data collection failed: {e}")
            
            # Create PDF document
            sections_generated = self._create_pdf_document(
                output_path, report_id, account_name, hour, minute_bin,
                trades, performance_data, statistical_data, correlation_data,
                start_date, end_date, config
            )
            
            # Get file information
            file_size = os.path.getsize(output_path)
            page_count = self._count_pdf_pages(output_path)
            
            # Create metadata
            metadata = ReportMetadata(
                report_id=report_id,
                generation_timestamp=datetime.now(),
                account_name=account_name,
                time_bin_hour=hour,
                time_bin_minute=minute_bin,
                date_range_start=start_date,
                date_range_end=end_date,
                total_trades=len(trades) if trades else 0,
                report_sections=sections_generated,
                file_path=output_path,
                file_size_bytes=file_size,
                page_count=page_count,
                configuration=config
            )
            
            # Track report
            self.report_history.append(metadata)
            
            logger.info(f"Time-bin report generated successfully: {output_path}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error generating time-bin report: {str(e)}")
            raise
    
    def create_performance_summary_page(
        self,
        trades: List[SimpleTrade],
        performance_data: Dict[str, Any],
        config: ReportConfiguration
    ) -> List[Any]:
        """
        Create performance summary page elements.
        
        Args:
            trades: List of trades
            performance_data: Performance metrics data
            config: Report configuration
            
        Returns:
            List of ReportLab flowables for the performance summary
        """
        elements = []
        styles = getSampleStyleSheet()
        
        # Performance Summary Header
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=HexColor(config.primary_color),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Performance Summary", title_style))
        elements.append(Spacer(1, 12))
        
        if not performance_data:
            elements.append(Paragraph("No performance data available", styles['Normal']))
            return elements
        
        # Key Metrics Table
        metrics_data = [
            ['Metric', 'Value', 'Description'],
            [
                'Total Return', 
                f"{config.currency_symbol}{performance_data.get('total_pnl', 0):.{config.decimal_places}f}",
                'Total profit/loss for the period'
            ],
            [
                'Return %', 
                f"{performance_data.get('total_return_pct', 0)*100:.{config.percentage_places}f}%",
                'Total return as percentage'
            ],
            [
                'Sharpe Ratio', 
                f"{performance_data.get('sharpe_ratio', 0):.{config.decimal_places}f}",
                'Risk-adjusted return measure'
            ],
            [
                'Max Drawdown', 
                f"{performance_data.get('max_drawdown', 0)*100:.{config.percentage_places}f}%",
                'Maximum peak-to-trough decline'
            ],
            [
                'Win Rate', 
                f"{performance_data.get('win_rate', 0)*100:.{config.percentage_places}f}%",
                'Percentage of profitable trades'
            ],
            [
                'Profit Factor', 
                f"{performance_data.get('profit_factor', 0):.{config.decimal_places}f}",
                'Ratio of gross profit to gross loss'
            ],
            [
                'Total Trades', 
                f"{len(trades)}",
                'Total number of completed trades'
            ],
            [
                'Average Trade', 
                f"{config.currency_symbol}{performance_data.get('avg_trade_pnl', 0):.2f}",
                'Average profit/loss per trade'
            ]
        ]
        
        # Create performance table
        performance_table = Table(
            metrics_data,
            colWidths=[2*inch, 1.5*inch, 3*inch],
            hAlign='LEFT'
        )
        
        # Style the table
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.primary_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Color code performance metrics
        for i, row in enumerate(metrics_data[1:], 1):
            if 'Return' in row[0] or 'Sharpe' in row[0]:
                value = row[1].replace(config.currency_symbol, '').replace('%', '')
                try:
                    numeric_value = float(value)
                    if numeric_value > 0:
                        table_style.append(('TEXTCOLOR', (1, i), (1, i), HexColor(config.success_color)))
                    else:
                        table_style.append(('TEXTCOLOR', (1, i), (1, i), HexColor(config.danger_color)))
                except (ValueError, AttributeError):
                    pass
        
        performance_table.setStyle(TableStyle(table_style))
        elements.append(performance_table)
        elements.append(Spacer(1, 20))
        
        # Trade Distribution Summary
        if trades:
            elements.append(Paragraph("Trade Distribution", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            # Calculate trade statistics
            winning_trades = [t for t in trades if t.profit_loss > 0]
            losing_trades = [t for t in trades if t.profit_loss < 0]
            
            distribution_data = [
                ['Category', 'Count', 'Total P&L', 'Average P&L'],
                [
                    'Winning Trades',
                    f"{len(winning_trades)}",
                    f"{config.currency_symbol}{sum(t.profit_loss for t in winning_trades):.2f}",
                    f"{config.currency_symbol}{np.mean([t.profit_loss for t in winning_trades]) if winning_trades else 0:.2f}"
                ],
                [
                    'Losing Trades',
                    f"{len(losing_trades)}",
                    f"{config.currency_symbol}{sum(t.profit_loss for t in losing_trades):.2f}",
                    f"{config.currency_symbol}{np.mean([t.profit_loss for t in losing_trades]) if losing_trades else 0:.2f}"
                ],
                [
                    'Break-even Trades',
                    f"{len([t for t in trades if t.profit_loss == 0])}",
                    f"{config.currency_symbol}0.00",
                    f"{config.currency_symbol}0.00"
                ]
            ]
            
            distribution_table = Table(
                distribution_data,
                colWidths=[2*inch, 1*inch, 1.5*inch, 1.5*inch],
                hAlign='LEFT'
            )
            
            distribution_style = [
                ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.secondary_color)),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            # Color code the P&L columns
            distribution_style.extend([
                ('TEXTCOLOR', (2, 1), (3, 1), HexColor(config.success_color)),  # Winning trades
                ('TEXTCOLOR', (2, 2), (3, 2), HexColor(config.danger_color)),   # Losing trades
            ])
            
            distribution_table.setStyle(TableStyle(distribution_style))
            elements.append(distribution_table)
        
        return elements
    
    def create_statistical_analysis_page(
        self,
        statistical_data: Dict[str, Any],
        trades: List[SimpleTrade],
        config: ReportConfiguration
    ) -> List[Any]:
        """
        Create statistical analysis page elements.
        
        Args:
            statistical_data: Statistical analysis results
            trades: List of trades for additional analysis
            config: Report configuration
            
        Returns:
            List of ReportLab flowables for statistical analysis
        """
        elements = []
        styles = getSampleStyleSheet()
        
        # Statistical Analysis Header
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=HexColor(config.primary_color),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Statistical Analysis", title_style))
        elements.append(Spacer(1, 12))
        
        if not statistical_data and not trades:
            elements.append(Paragraph("No statistical data available", styles['Normal']))
            return elements
        
        # Statistical Tests Results
        if statistical_data:
            elements.append(Paragraph("Significance Testing", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            # Create significance tests table
            tests_data = [['Test', 'Statistic', 'P-Value', 'Interpretation']]
            
            # Add available statistical tests
            if 't_test_p_value' in statistical_data:
                p_val = statistical_data['t_test_p_value']
                interpretation = "Statistically significant" if p_val < 0.05 else "Not significant"
                tests_data.append([
                    'T-Test (Mean ≠ 0)',
                    f"{statistical_data.get('t_statistic', 0):.4f}",
                    f"{p_val:.4f}",
                    interpretation
                ])
            
            if 'normality_test_p_value' in statistical_data:
                p_val = statistical_data['normality_test_p_value']
                interpretation = "Non-normal distribution" if p_val < 0.05 else "Normal distribution"
                tests_data.append([
                    'Normality Test',
                    f"{statistical_data.get('normality_statistic', 0):.4f}",
                    f"{p_val:.4f}",
                    interpretation
                ])
            
            if 'autocorrelation_test_p_value' in statistical_data:
                p_val = statistical_data['autocorrelation_test_p_value']
                interpretation = "Autocorrelation present" if p_val < 0.05 else "No autocorrelation"
                tests_data.append([
                    'Autocorrelation Test',
                    f"{statistical_data.get('ljung_box_statistic', 0):.4f}",
                    f"{p_val:.4f}",
                    interpretation
                ])
            
            if len(tests_data) > 1:  # Has data beyond header
                tests_table = Table(
                    tests_data,
                    colWidths=[2*inch, 1.2*inch, 1*inch, 2.3*inch],
                    hAlign='LEFT'
                )
                
                tests_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.primary_color)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
                
                # Color code p-values
                for i in range(1, len(tests_data)):
                    try:
                        p_val = float(tests_data[i][2])
                        if p_val < 0.05:
                            tests_style.append(('TEXTCOLOR', (2, i), (2, i), HexColor(config.success_color)))
                        else:
                            tests_style.append(('TEXTCOLOR', (2, i), (2, i), HexColor(config.warning_color)))
                    except (ValueError, IndexError):
                        pass
                
                tests_table.setStyle(TableStyle(tests_style))
                elements.append(tests_table)
                elements.append(Spacer(1, 20))
        
        # Trade Statistics if available
        if trades:
            elements.append(Paragraph("Descriptive Statistics", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            # Calculate descriptive statistics
            pnl_values = [t.profit_loss for t in trades]
            
            if pnl_values:
                stats_data = [
                    ['Statistic', 'Value', 'Description'],
                    ['Count', f"{len(pnl_values)}", 'Number of trades'],
                    ['Mean', f"{config.currency_symbol}{np.mean(pnl_values):.{config.decimal_places}f}", 'Average P&L per trade'],
                    ['Std Dev', f"{config.currency_symbol}{np.std(pnl_values):.{config.decimal_places}f}", 'Standard deviation of P&L'],
                    ['Min', f"{config.currency_symbol}{np.min(pnl_values):.{config.decimal_places}f}", 'Worst single trade'],
                    ['25th %ile', f"{config.currency_symbol}{np.percentile(pnl_values, 25):.{config.decimal_places}f}", '25th percentile'],
                    ['Median', f"{config.currency_symbol}{np.median(pnl_values):.{config.decimal_places}f}", 'Middle value (50th percentile)'],
                    ['75th %ile', f"{config.currency_symbol}{np.percentile(pnl_values, 75):.{config.decimal_places}f}", '75th percentile'],
                    ['Max', f"{config.currency_symbol}{np.max(pnl_values):.{config.decimal_places}f}", 'Best single trade'],
                    ['Skewness', f"{self._calculate_skewness(pnl_values):.{config.decimal_places}f}", 'Distribution asymmetry'],
                    ['Kurtosis', f"{self._calculate_kurtosis(pnl_values):.{config.decimal_places}f}", 'Distribution tail heaviness']
                ]
                
                stats_table = Table(
                    stats_data,
                    colWidths=[1.5*inch, 1.5*inch, 3.5*inch],
                    hAlign='LEFT'
                )
                
                stats_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.secondary_color)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
                
                stats_table.setStyle(TableStyle(stats_style))
                elements.append(stats_table)
                elements.append(Spacer(1, 20))
            
            # Confidence Intervals
            if statistical_data and 'confidence_interval_lower' in statistical_data:
                elements.append(Paragraph("Confidence Intervals", styles['Heading3']))
                elements.append(Spacer(1, 10))
                
                ci_data = [
                    ['Confidence Level', 'Lower Bound', 'Upper Bound', 'Width'],
                    [
                        '95%',
                        f"{config.currency_symbol}{statistical_data.get('confidence_interval_lower', 0):.{config.decimal_places}f}",
                        f"{config.currency_symbol}{statistical_data.get('confidence_interval_upper', 0):.{config.decimal_places}f}",
                        f"{config.currency_symbol}{statistical_data.get('confidence_interval_upper', 0) - statistical_data.get('confidence_interval_lower', 0):.{config.decimal_places}f}"
                    ]
                ]
                
                ci_table = Table(
                    ci_data,
                    colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch],
                    hAlign='LEFT'
                )
                
                ci_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.warning_color)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
                
                ci_table.setStyle(TableStyle(ci_style))
                elements.append(ci_table)
        
        return elements
    
    def create_market_correlation_page(
        self,
        correlation_data: Dict[str, Any],
        trades: List[SimpleTrade],
        config: ReportConfiguration
    ) -> List[Any]:
        """
        Create market correlation analysis page elements.
        
        Args:
            correlation_data: Market correlation data
            trades: List of trades
            config: Report configuration
            
        Returns:
            List of ReportLab flowables for market correlation analysis
        """
        elements = []
        styles = getSampleStyleSheet()
        
        # Market Correlation Header
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=HexColor(config.primary_color),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Market Correlation Analysis", title_style))
        elements.append(Spacer(1, 12))
        
        if not correlation_data:
            elements.append(Paragraph("No correlation data available", styles['Normal']))
            return elements
        
        # Benchmark Correlations
        if 'benchmark_correlations' in correlation_data:
            elements.append(Paragraph("Benchmark Correlations", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            benchmarks = correlation_data['benchmark_correlations']
            
            # Create benchmark correlation table
            corr_data = [['Benchmark', 'Correlation', 'Strength', 'P-Value', 'Interpretation']]
            
            for benchmark, corr_info in benchmarks.items():
                if corr_info is not None:
                    if isinstance(corr_info, dict):
                        correlation = corr_info.get('correlation', 0)
                        p_value = corr_info.get('p_value', 1.0)
                    else:
                        correlation = float(corr_info)
                        p_value = 0.05  # Default assumption
                    
                    # Interpret correlation strength
                    abs_corr = abs(correlation)
                    if abs_corr >= 0.7:
                        strength = "Strong"
                    elif abs_corr >= 0.3:
                        strength = "Moderate"
                    else:
                        strength = "Weak"
                    
                    # Interpret significance
                    interpretation = "Significant" if p_value < 0.05 else "Not significant"
                    
                    corr_data.append([
                        benchmark,
                        f"{correlation:.{config.decimal_places}f}",
                        strength,
                        f"{p_value:.4f}",
                        interpretation
                    ])
            
            if len(corr_data) > 1:  # Has data beyond header
                corr_table = Table(
                    corr_data,
                    colWidths=[1.2*inch, 1.2*inch, 1*inch, 1*inch, 1.6*inch],
                    hAlign='LEFT'
                )
                
                corr_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.primary_color)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
                
                # Color code correlations by strength
                for i in range(1, len(corr_data)):
                    try:
                        corr_val = float(corr_data[i][1])
                        abs_corr = abs(corr_val)
                        
                        if abs_corr >= 0.7:
                            color = HexColor(config.success_color)
                        elif abs_corr >= 0.3:
                            color = HexColor(config.warning_color)
                        else:
                            color = HexColor(config.danger_color)
                        
                        corr_style.append(('TEXTCOLOR', (1, i), (1, i), color))
                        corr_style.append(('TEXTCOLOR', (2, i), (2, i), color))
                    except (ValueError, IndexError):
                        pass
                
                corr_table.setStyle(TableStyle(corr_style))
                elements.append(corr_table)
                elements.append(Spacer(1, 20))
        
        # VIX Regime Analysis
        if 'vix_correlation' in correlation_data:
            elements.append(Paragraph("VIX Volatility Regime Analysis", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            vix_data = correlation_data['vix_correlation']
            
            if isinstance(vix_data, dict) and 'regime_specific_correlations' in vix_data:
                regime_data = [['VIX Regime', 'Correlation', 'Trade Count', 'Avg P&L', 'Performance']]
                
                regime_corrs = vix_data['regime_specific_correlations']
                for regime, corr in regime_corrs.items():
                    # This would be populated with actual regime-specific trade data
                    regime_data.append([
                        regime.replace('_', ' ').title(),
                        f"{corr:.{config.decimal_places}f}",
                        "N/A",  # Would be calculated from actual data
                        "N/A",  # Would be calculated from actual data
                        "Analysis pending"
                    ])
                
                if len(regime_data) > 1:
                    regime_table = Table(
                        regime_data,
                        colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.9*inch],
                        hAlign='LEFT'
                    )
                    
                    regime_style = [
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.secondary_color)),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]
                    
                    regime_table.setStyle(TableStyle(regime_style))
                    elements.append(regime_table)
                    elements.append(Spacer(1, 20))
            
            # Overall VIX correlation summary
            if 'overall_correlation' in vix_data:
                elements.append(Paragraph("VIX Correlation Summary", styles['Heading3']))
                elements.append(Spacer(1, 10))
                
                overall_corr = vix_data['overall_correlation']
                
                # Interpretation text
                if overall_corr > 0.3:
                    interpretation = "Strong positive correlation with VIX indicates higher performance during volatile periods."
                elif overall_corr < -0.3:
                    interpretation = "Strong negative correlation with VIX indicates better performance during calm periods."
                else:
                    interpretation = "Weak correlation with VIX suggests performance is largely independent of market volatility."
                
                summary_text = f"""
                <b>Overall VIX Correlation:</b> {overall_corr:.{config.decimal_places}f}<br/>
                <br/>
                <b>Interpretation:</b> {interpretation}<br/>
                <br/>
                This analysis helps understand how trading performance varies with market volatility conditions,
                which is crucial for risk management and position sizing decisions.
                """
                
                elements.append(Paragraph(summary_text, styles['Normal']))
                elements.append(Spacer(1, 10))
        
        # Market Regime Performance Summary
        elements.append(Paragraph("Market Regime Performance", styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        regime_summary = """
        <b>Key Insights:</b><br/>
        • Monitor correlation strength changes over time to detect regime shifts<br/>
        • Strong correlations (>0.7) may indicate increased systematic risk<br/>
        • VIX correlation patterns help optimize position sizing during volatility spikes<br/>
        • Benchmark correlations inform portfolio diversification strategies<br/>
        <br/>
        <b>Risk Management Implications:</b><br/>
        • High correlations with market indices may require position size adjustments<br/>
        • Negative VIX correlations suggest strategy may struggle during market stress<br/>
        • Monitor correlation stability to detect strategy degradation over time
        """
        
        elements.append(Paragraph(regime_summary, styles['Normal']))
        
        return elements
    
    # Private helper methods
    
    def _create_pdf_document(
        self,
        output_path: str,
        report_id: str,
        account_name: str,
        hour: int,
        minute_bin: int,
        trades: List[SimpleTrade],
        performance_data: Dict[str, Any],
        statistical_data: Dict[str, Any],
        correlation_data: Dict[str, Any],
        start_date: Optional[date],
        end_date: Optional[date],
        config: ReportConfiguration
    ) -> List[str]:
        """Create the complete PDF document."""
        
        # Setup document
        page_size = A4 if config.page_size.lower() == 'a4' else letter
        doc = SimpleDocTemplate(
            output_path,
            pagesize=page_size,
            rightMargin=config.margins['right']*inch,
            leftMargin=config.margins['left']*inch,
            topMargin=config.margins['top']*inch,
            bottomMargin=config.margins['bottom']*inch
        )
        
        story = []
        sections_generated = []
        
        # Title page
        story.extend(self._create_title_page(
            report_id, account_name, hour, minute_bin, 
            start_date, end_date, config
        ))
        sections_generated.append("Title Page")
        
        # Executive Summary
        if config.include_executive_summary:
            story.append(PageBreak())
            story.extend(self._create_executive_summary(
                trades, performance_data, statistical_data, config
            ))
            sections_generated.append("Executive Summary")
        
        # Performance Summary
        if config.include_performance_summary:
            story.append(PageBreak())
            story.extend(self.create_performance_summary_page(
                trades, performance_data, config
            ))
            sections_generated.append("Performance Summary")
        
        # Statistical Analysis
        if config.include_statistical_analysis:
            story.append(PageBreak())
            story.extend(self.create_statistical_analysis_page(
                statistical_data, trades, config
            ))
            sections_generated.append("Statistical Analysis")
        
        # Market Correlation
        if config.include_market_correlation:
            story.append(PageBreak())
            story.extend(self.create_market_correlation_page(
                correlation_data, trades, config
            ))
            sections_generated.append("Market Correlation")
        
        # Trade Details
        if config.include_trade_details and trades:
            story.append(PageBreak())
            story.extend(self._create_trade_details_page(trades, config))
            sections_generated.append("Trade Details")
        
        # Build PDF
        doc.build(story)
        
        return sections_generated
    
    def _create_title_page(
        self,
        report_id: str,
        account_name: str,
        hour: int,
        minute_bin: int,
        start_date: Optional[date],
        end_date: Optional[date],
        config: ReportConfiguration
    ) -> List[Any]:
        """Create title page elements."""
        elements = []
        styles = getSampleStyleSheet()
        
        # Main title
        main_title_style = ParagraphStyle(
            'MainTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=HexColor(config.primary_color),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("Trading Analytics Report", main_title_style))
        
        # Subtitle
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=HexColor(config.secondary_color),
            alignment=TA_CENTER,
            spaceAfter=40
        )
        
        time_bin_str = f"{hour:02d}:{minute_bin:02d}"
        elements.append(Paragraph(f"Account: {account_name} | Time Bin: {time_bin_str}", subtitle_style))
        
        # Report details
        details_style = ParagraphStyle(
            'Details',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        date_range = "All Available Data"
        if start_date and end_date:
            date_range = f"{start_date.strftime(config.date_format)} to {end_date.strftime(config.date_format)}"
        elif start_date:
            date_range = f"From {start_date.strftime(config.date_format)}"
        elif end_date:
            date_range = f"Through {end_date.strftime(config.date_format)}"
        
        details_text = f"""
        <b>Report ID:</b> {report_id}<br/>
        <b>Analysis Period:</b> {date_range}<br/>
        <b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
        """
        
        elements.append(Paragraph(details_text, details_style))
        
        # Disclaimer
        elements.append(Spacer(1, 2*inch))
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_JUSTIFY,
            textColor=colors.grey
        )
        
        disclaimer_text = """
        <b>IMPORTANT DISCLAIMER:</b> This report is for informational purposes only and does not constitute 
        investment advice. Past performance is not indicative of future results. Trading involves substantial 
        risk of loss and may not be suitable for all investors. All statistical analysis and performance 
        metrics are based on historical data and should be interpreted with appropriate caution.
        """
        
        elements.append(Paragraph(disclaimer_text, disclaimer_style))
        
        return elements
    
    def _create_executive_summary(
        self,
        trades: List[SimpleTrade],
        performance_data: Dict[str, Any],
        statistical_data: Dict[str, Any],
        config: ReportConfiguration
    ) -> List[Any]:
        """Create executive summary page."""
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=HexColor(config.primary_color),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Executive Summary", title_style))
        elements.append(Spacer(1, 12))
        
        # Key highlights
        if performance_data:
            total_return = performance_data.get('total_pnl', 0)
            win_rate = performance_data.get('win_rate', 0) * 100
            sharpe_ratio = performance_data.get('sharpe_ratio', 0)
            max_drawdown = performance_data.get('max_drawdown', 0) * 100
            
            # Determine overall performance assessment
            if total_return > 0 and sharpe_ratio > 1.0:
                performance_assessment = "STRONG PERFORMANCE"
                assessment_color = config.success_color
            elif total_return > 0:
                performance_assessment = "POSITIVE PERFORMANCE"
                assessment_color = config.warning_color
            else:
                performance_assessment = "NEGATIVE PERFORMANCE" 
                assessment_color = config.danger_color
            
            summary_text = f"""
            <para align="center" fontSize="14" textColor="{assessment_color}">
            <b>{performance_assessment}</b>
            </para>
            <br/>
            
            <b>Period Overview:</b><br/>
            This analysis covers {len(trades)} completed trades, generating a total return of 
            {config.currency_symbol}{total_return:.2f}. The strategy demonstrated a win rate of 
            {win_rate:.1f}% with a Sharpe ratio of {sharpe_ratio:.2f}, indicating 
            {'strong' if sharpe_ratio > 1.0 else 'moderate' if sharpe_ratio > 0.5 else 'weak'} 
            risk-adjusted returns.
            <br/><br/>
            
            <b>Risk Assessment:</b><br/>
            Maximum drawdown reached {max_drawdown:.1f}%, representing the worst peak-to-trough 
            decline during the analysis period. 
            {'This is within acceptable risk parameters.' if max_drawdown < 10 else 'This indicates elevated risk levels that may require attention.' if max_drawdown < 20 else 'This represents significant risk exposure requiring immediate review.'}
            <br/><br/>
            
            <b>Statistical Significance:</b><br/>
            """
            
            if statistical_data and 't_test_p_value' in statistical_data:
                p_val = statistical_data['t_test_p_value']
                if p_val < 0.05:
                    summary_text += f"Statistical testing confirms results are significant (p = {p_val:.4f}), " \
                                  f"suggesting consistent alpha generation."
                else:
                    summary_text += f"Statistical testing indicates results are not significant (p = {p_val:.4f}), " \
                                  f"suggesting performance may be due to random variation."
            else:
                summary_text += "Statistical significance testing was not available for this analysis period."
            
            summary_text += """
            <br/><br/>
            
            <b>Key Recommendations:</b><br/>
            • Monitor correlation with market benchmarks to assess systematic risk<br/>
            • Review position sizing if maximum drawdown exceeds risk tolerance<br/>
            • Continue statistical monitoring to detect performance degradation<br/>
            • Consider regime-based adjustments based on market volatility conditions
            """
            
            elements.append(Paragraph(summary_text, styles['Normal']))
        else:
            elements.append(Paragraph("No performance data available for analysis.", styles['Normal']))
        
        return elements
    
    def _create_trade_details_page(
        self,
        trades: List[SimpleTrade],
        config: ReportConfiguration
    ) -> List[Any]:
        """Create trade details page."""
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=HexColor(config.primary_color),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Trade Details", title_style))
        elements.append(Spacer(1, 12))
        
        if not trades:
            elements.append(Paragraph("No trades available for detailed analysis.", styles['Normal']))
            return elements
        
        # Limit to recent trades for space
        display_trades = trades[-20:] if len(trades) > 20 else trades
        
        # Create trade details table
        trade_data = [['Date', 'Symbol', 'Side', 'Qty', 'Entry', 'Exit', 'P&L', 'Duration']]
        
        for trade in display_trades:
            trade_data.append([
                trade.entry_time.strftime('%m/%d'),
                trade.symbol,
                trade.side,
                f"{trade.quantity}",
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}",
                f"{config.currency_symbol}{trade.profit_loss:.2f}",
                f"{trade.duration_minutes}m"
            ])
        
        trade_table = Table(
            trade_data,
            colWidths=[0.8*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch],
            hAlign='LEFT'
        )
        
        trade_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor(config.primary_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Color code P&L column
        for i in range(1, len(trade_data)):
            pnl_str = trade_data[i][6]
            try:
                pnl_val = float(pnl_str.replace(config.currency_symbol, ''))
                color = HexColor(config.success_color) if pnl_val >= 0 else HexColor(config.danger_color)
                trade_style.append(('TEXTCOLOR', (6, i), (6, i), color))
            except (ValueError, AttributeError):
                pass
        
        trade_table.setStyle(TableStyle(trade_style))
        elements.append(trade_table)
        
        if len(trades) > 20:
            elements.append(Spacer(1, 10))
            note_text = f"Note: Showing most recent 20 trades of {len(trades)} total trades."
            elements.append(Paragraph(note_text, styles['Normal']))
        
        return elements
    
    def _collect_correlation_data(
        self,
        account_name: str,
        hour: int,
        minute_bin: int,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict[str, Any]:
        """Collect market correlation data."""
        correlation_data = {}
        
        # Get benchmark correlations
        benchmarks = ['SPY', 'QQQ', 'VIX']
        benchmark_correlations = {}
        
        for benchmark in benchmarks:
            try:
                correlation = self.benchmark_analyzer.calculate_correlation_with_benchmark(
                    account_name=account_name,
                    hour=hour,
                    minute_bin=minute_bin,
                    benchmark_symbol=benchmark,
                    start_date=start_date,
                    end_date=end_date
                )
                benchmark_correlations[benchmark] = correlation
            except Exception as e:
                logger.warning(f"Failed to calculate {benchmark} correlation: {e}")
                benchmark_correlations[benchmark] = None
        
        correlation_data['benchmark_correlations'] = benchmark_correlations
        
        # Get VIX correlation data
        try:
            vix_correlation = self.vix_analyzer.calculate_vix_correlation(
                account_name=account_name,
                hour=hour,
                minute_bin=minute_bin,
                start_date=start_date,
                end_date=end_date
            )
            correlation_data['vix_correlation'] = vix_correlation
        except Exception as e:
            logger.warning(f"Failed to calculate VIX correlation: {e}")
        
        return correlation_data
    
    def _calculate_skewness(self, values: List[float]) -> float:
        """Calculate skewness of a distribution."""
        try:
            import scipy.stats
            return scipy.stats.skew(values)
        except ImportError:
            # Fallback calculation
            if len(values) < 3:
                return 0.0
            
            mean_val = np.mean(values)
            std_val = np.std(values, ddof=1)
            
            if std_val == 0:
                return 0.0
                
            n = len(values)
            skew = (n / ((n-1)*(n-2))) * sum(((x - mean_val)/std_val)**3 for x in values)
            return skew
    
    def _calculate_kurtosis(self, values: List[float]) -> float:
        """Calculate kurtosis of a distribution."""
        try:
            import scipy.stats
            return scipy.stats.kurtosis(values, fisher=True)  # Excess kurtosis
        except ImportError:
            # Fallback calculation
            if len(values) < 4:
                return 0.0
            
            mean_val = np.mean(values)
            std_val = np.std(values, ddof=1)
            
            if std_val == 0:
                return 0.0
                
            n = len(values)
            kurt = (n*(n+1)/((n-1)*(n-2)*(n-3))) * sum(((x - mean_val)/std_val)**4 for x in values) - 3*(n-1)**2/((n-2)*(n-3))
            return kurt
    
    def _count_pdf_pages(self, file_path: str) -> int:
        """Count pages in generated PDF."""
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages)
        except ImportError:
            # Estimate based on file size (rough approximation)
            file_size = os.path.getsize(file_path)
            estimated_pages = max(1, file_size // 50000)  # Rough estimate: 50KB per page
            return estimated_pages
        except Exception as e:
            logger.warning(f"Could not count PDF pages: {e}")
            return 1
    
    def get_report_history(self) -> List[ReportMetadata]:
        """Get the history of generated reports."""
        return self.report_history.copy()
    
    def clear_report_history(self) -> None:
        """Clear the report history."""
        self.report_history.clear()