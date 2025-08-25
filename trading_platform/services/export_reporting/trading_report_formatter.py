"""
TradingReportFormatter for professional chart generation and visual analytics.

This module provides comprehensive chart generation capabilities for:
- Equity curve charts for cumulative P&L visualization
- Drawdown charts for risk assessment
- Monthly returns tables for performance breakdown
- Performance metrics tables for comprehensive statistics
- Professional chart styling and formatting

Requirements: 13.5, 6.1
"""

import os
import io
import base64
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import logging

from ...database.connection import get_db_session
from ..time_bin_analyzer import TimeBin, SimpleTrade
from ..performance_metrics_calculator import PerformanceMetricsCalculator

logger = logging.getLogger(__name__)


@dataclass
class ChartConfiguration:
    """Configuration for chart generation and styling."""
    
    # Chart dimensions
    figure_width: float = 12.0
    figure_height: float = 8.0
    dpi: int = 300
    
    # Styling options
    style: str = 'seaborn-v0_8-whitegrid'  # matplotlib style
    color_palette: str = 'husl'  # seaborn color palette
    primary_color: str = '#2563eb'
    secondary_color: str = '#10b981'
    danger_color: str = '#ef4444'
    warning_color: str = '#f59e0b'
    background_color: str = '#ffffff'
    grid_color: str = '#e5e7eb'
    
    # Font settings
    font_family: str = 'Arial'
    title_font_size: int = 16
    label_font_size: int = 12
    tick_font_size: int = 10
    legend_font_size: int = 11
    
    # Chart-specific settings
    line_width: float = 2.0
    marker_size: float = 6.0
    alpha: float = 0.8
    
    # Export settings
    format: str = 'png'  # 'png', 'pdf', 'svg'
    bbox_inches: str = 'tight'
    pad_inches: float = 0.1
    
    # Performance settings
    show_benchmarks: bool = True
    show_drawdown_periods: bool = True
    show_statistics: bool = True
    show_grid: bool = True
    
    def __post_init__(self):
        """Set matplotlib style after initialization."""
        try:
            plt.style.use(self.style)
            sns.set_palette(self.color_palette)
        except Exception as e:
            logger.warning(f"Could not set chart style {self.style}: {e}")
            plt.style.use('default')


@dataclass
class ChartData:
    """Container for chart data and metadata."""
    
    chart_type: str
    title: str
    data: Dict[str, Any]
    figure_path: Optional[str] = None
    figure_base64: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TradingReportFormatter:
    """
    Professional chart generator for trading analytics reports.
    
    Provides comprehensive chart generation capabilities including equity curves,
    drawdown analysis, performance tables, and professional visualization
    formatting for trading reports.
    """
    
    def __init__(self, db_session=None):
        """Initialize the TradingReportFormatter."""
        self.db_session = db_session or get_db_session()
        self.performance_calculator = PerformanceMetricsCalculator(self.db_session)
        
        # Chart generation history
        self.chart_history: List[ChartData] = []
        
        # Setup matplotlib for high-quality output
        plt.rcParams['figure.dpi'] = 300
        plt.rcParams['savefig.dpi'] = 300
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3
    
    def create_equity_curve_chart(
        self,
        trades: List[SimpleTrade],
        title: str = "Equity Curve",
        output_path: Optional[str] = None,
        config: Optional[ChartConfiguration] = None,
        show_drawdowns: bool = True,
        show_benchmarks: bool = False,
        benchmark_data: Optional[Dict[str, List[float]]] = None
    ) -> ChartData:
        """
        Create equity curve chart for cumulative P&L visualization.
        
        Args:
            trades: List of trading data
            title: Chart title
            output_path: Optional file path to save chart
            config: Chart configuration options
            show_drawdowns: Whether to highlight drawdown periods
            show_benchmarks: Whether to show benchmark comparison
            benchmark_data: Optional benchmark data for comparison
            
        Returns:
            ChartData: Chart data and metadata
        """
        if config is None:
            config = ChartConfiguration()
        
        logger.info(f"Creating equity curve chart with {len(trades)} trades")
        
        try:
            # Calculate cumulative P&L
            equity_curve_data = self._calculate_equity_curve(trades)
            
            if not equity_curve_data:
                raise ValueError("No equity curve data available")
            
            # Create figure
            fig, ax = plt.subplots(figsize=(config.figure_width, config.figure_height))
            
            dates = equity_curve_data['dates']
            cumulative_pnl = equity_curve_data['cumulative_pnl']
            
            # Main equity curve
            ax.plot(
                dates, 
                cumulative_pnl, 
                color=config.primary_color,
                linewidth=config.line_width,
                alpha=config.alpha,
                label='Portfolio Value'
            )
            
            # Fill area under curve
            ax.fill_between(
                dates, 
                cumulative_pnl, 
                0,
                alpha=0.1, 
                color=config.primary_color
            )
            
            # Add drawdown periods if requested
            if show_drawdowns and 'drawdown_periods' in equity_curve_data:
                drawdown_periods = equity_curve_data['drawdown_periods']
                for period in drawdown_periods:
                    ax.axvspan(
                        period['start'], 
                        period['end'],
                        alpha=0.2, 
                        color=config.danger_color,
                        label='Drawdown Period' if period == drawdown_periods[0] else ""
                    )
            
            # Add benchmark comparison if provided
            if show_benchmarks and benchmark_data:
                for benchmark_name, benchmark_values in benchmark_data.items():
                    if len(benchmark_values) == len(dates):
                        ax.plot(
                            dates,
                            benchmark_values,
                            '--',
                            linewidth=1.5,
                            alpha=0.7,
                            label=f'{benchmark_name} Benchmark'
                        )
            
            # Add key statistics as text
            if config.show_statistics:
                stats_text = self._generate_equity_curve_stats(equity_curve_data, trades)
                ax.text(
                    0.02, 0.98, 
                    stats_text,
                    transform=ax.transAxes,
                    verticalalignment='top',
                    bbox=dict(
                        boxstyle='round',
                        facecolor='white',
                        alpha=0.8,
                        edgecolor=config.grid_color
                    ),
                    fontsize=config.tick_font_size
                )
            
            # Formatting
            ax.set_title(title, fontsize=config.title_font_size, fontweight='bold', pad=20)
            ax.set_xlabel('Date', fontsize=config.label_font_size)
            ax.set_ylabel('Cumulative P&L ($)', fontsize=config.label_font_size)
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add horizontal line at zero
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
            
            # Grid and legend
            if config.show_grid:
                ax.grid(True, alpha=0.3, color=config.grid_color)
            
            ax.legend(fontsize=config.legend_font_size, loc='upper left')
            
            # Tight layout
            plt.tight_layout()
            
            # Save or convert to base64
            chart_data = self._finalize_chart(
                fig, title, 'equity_curve', output_path, config,
                {'trades_count': len(trades), 'final_pnl': cumulative_pnl[-1] if cumulative_pnl else 0}
            )
            
            plt.close(fig)
            
            logger.info("Equity curve chart created successfully")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating equity curve chart: {str(e)}")
            raise
    
    def create_drawdown_chart(
        self,
        trades: List[SimpleTrade],
        title: str = "Drawdown Analysis",
        output_path: Optional[str] = None,
        config: Optional[ChartConfiguration] = None,
        show_underwater_curve: bool = True,
        show_recovery_periods: bool = True
    ) -> ChartData:
        """
        Create drawdown chart for risk assessment.
        
        Args:
            trades: List of trading data
            title: Chart title
            output_path: Optional file path to save chart
            config: Chart configuration options
            show_underwater_curve: Whether to show underwater equity curve
            show_recovery_periods: Whether to highlight recovery periods
            
        Returns:
            ChartData: Chart data and metadata
        """
        if config is None:
            config = ChartConfiguration()
        
        logger.info(f"Creating drawdown chart with {len(trades)} trades")
        
        try:
            # Calculate drawdown data
            drawdown_data = self._calculate_drawdown_analysis(trades)
            
            if not drawdown_data:
                raise ValueError("No drawdown data available")
            
            # Create figure with subplots
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(config.figure_width, config.figure_height * 1.2))
            
            dates = drawdown_data['dates']
            cumulative_pnl = drawdown_data['cumulative_pnl']
            drawdown_pct = drawdown_data['drawdown_pct']
            
            # Top subplot: Equity curve with drawdown shading
            ax1.plot(
                dates, 
                cumulative_pnl,
                color=config.primary_color,
                linewidth=config.line_width,
                label='Equity Curve'
            )
            
            # Shade drawdown periods
            if 'drawdown_periods' in drawdown_data:
                for period in drawdown_data['drawdown_periods']:
                    ax1.axvspan(
                        period['start'], 
                        period['end'],
                        alpha=0.2, 
                        color=config.danger_color
                    )
            
            ax1.set_title(f'{title} - Equity Curve', fontsize=config.title_font_size, fontweight='bold')
            ax1.set_ylabel('Cumulative P&L ($)', fontsize=config.label_font_size)
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Bottom subplot: Drawdown percentage
            ax2.fill_between(
                dates, 
                drawdown_pct, 
                0,
                color=config.danger_color,
                alpha=0.6,
                label='Drawdown %'
            )
            
            ax2.plot(
                dates, 
                drawdown_pct,
                color=config.danger_color,
                linewidth=1.5
            )
            
            # Add recovery period indicators
            if show_recovery_periods and 'recovery_periods' in drawdown_data:
                for period in drawdown_data['recovery_periods']:
                    ax2.axvspan(
                        period['start'], 
                        period['end'],
                        alpha=0.3, 
                        color=config.secondary_color,
                        label='Recovery Period' if period == drawdown_data['recovery_periods'][0] else ""
                    )
            
            ax2.set_title('Drawdown Percentage', fontsize=config.label_font_size, fontweight='bold')
            ax2.set_xlabel('Date', fontsize=config.label_font_size)
            ax2.set_ylabel('Drawdown (%)', fontsize=config.label_font_size)
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # Format x-axes
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax.xaxis.set_major_locator(mdates.MonthLocator())
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add statistics text box
            if config.show_statistics:
                stats_text = self._generate_drawdown_stats(drawdown_data, trades)
                ax1.text(
                    0.02, 0.02, 
                    stats_text,
                    transform=ax1.transAxes,
                    verticalalignment='bottom',
                    bbox=dict(
                        boxstyle='round',
                        facecolor='white',
                        alpha=0.9,
                        edgecolor=config.grid_color
                    ),
                    fontsize=config.tick_font_size
                )
            
            plt.tight_layout()
            
            # Save or convert to base64
            max_drawdown = min(drawdown_pct) if drawdown_pct else 0
            chart_data = self._finalize_chart(
                fig, title, 'drawdown', output_path, config,
                {'max_drawdown_pct': max_drawdown, 'drawdown_periods': len(drawdown_data.get('drawdown_periods', []))}
            )
            
            plt.close(fig)
            
            logger.info("Drawdown chart created successfully")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating drawdown chart: {str(e)}")
            raise
    
    def create_monthly_returns_table(
        self,
        trades: List[SimpleTrade],
        title: str = "Monthly Returns Breakdown",
        output_path: Optional[str] = None,
        config: Optional[ChartConfiguration] = None,
        show_heatmap: bool = True
    ) -> ChartData:
        """
        Create monthly returns table for performance breakdown.
        
        Args:
            trades: List of trading data
            title: Table title
            output_path: Optional file path to save chart
            config: Chart configuration options
            show_heatmap: Whether to show color-coded heatmap
            
        Returns:
            ChartData: Chart data and metadata
        """
        if config is None:
            config = ChartConfiguration()
        
        logger.info(f"Creating monthly returns table with {len(trades)} trades")
        
        try:
            # Calculate monthly returns
            monthly_data = self._calculate_monthly_returns(trades)
            
            if monthly_data.empty:
                raise ValueError("No monthly returns data available")
            
            # Create figure
            fig, ax = plt.subplots(figsize=(config.figure_width, config.figure_height * 0.8))
            
            if show_heatmap:
                # Create heatmap
                sns.heatmap(
                    monthly_data,
                    annot=True,
                    fmt='.1f',
                    cmap='RdYlGn',
                    center=0,
                    ax=ax,
                    cbar_kws={'label': 'Monthly Return (%)'},
                    linewidths=0.5,
                    linecolor='white'
                )
            else:
                # Create table without heatmap
                table_data = monthly_data.round(1)
                table = ax.table(
                    cellText=table_data.values,
                    rowLabels=table_data.index,
                    colLabels=table_data.columns,
                    cellLoc='center',
                    loc='center'
                )
                table.auto_set_font_size(False)
                table.set_fontsize(config.tick_font_size)
                table.scale(1.2, 1.5)
                ax.axis('off')
            
            ax.set_title(title, fontsize=config.title_font_size, fontweight='bold', pad=20)
            
            plt.tight_layout()
            
            # Calculate summary statistics
            total_months = monthly_data.count().sum()
            positive_months = (monthly_data > 0).sum().sum()
            avg_monthly_return = monthly_data.stack().mean()
            
            chart_data = self._finalize_chart(
                fig, title, 'monthly_returns', output_path, config,
                {
                    'total_months': total_months,
                    'positive_months': positive_months,
                    'win_rate_monthly': positive_months / total_months if total_months > 0 else 0,
                    'avg_monthly_return': avg_monthly_return
                }
            )
            
            plt.close(fig)
            
            logger.info("Monthly returns table created successfully")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating monthly returns table: {str(e)}")
            raise
    
    def create_performance_metrics_table(
        self,
        trades: List[SimpleTrade],
        title: str = "Performance Metrics",
        output_path: Optional[str] = None,
        config: Optional[ChartConfiguration] = None,
        include_risk_metrics: bool = True,
        include_trade_metrics: bool = True
    ) -> ChartData:
        """
        Create comprehensive performance metrics table.
        
        Args:
            trades: List of trading data
            title: Table title
            output_path: Optional file path to save chart
            config: Chart configuration options
            include_risk_metrics: Whether to include risk-adjusted metrics
            include_trade_metrics: Whether to include trade-level statistics
            
        Returns:
            ChartData: Chart data and metadata
        """
        if config is None:
            config = ChartConfiguration()
        
        logger.info(f"Creating performance metrics table with {len(trades)} trades")
        
        try:
            # Calculate comprehensive metrics
            metrics = self._calculate_comprehensive_performance_metrics(
                trades, include_risk_metrics, include_trade_metrics
            )
            
            # Create figure
            fig, ax = plt.subplots(figsize=(config.figure_width * 0.8, config.figure_height))
            
            # Prepare table data
            table_data = []
            colors = []
            
            for category, category_metrics in metrics.items():
                # Add category header
                table_data.append([category.upper(), ""])
                colors.append(['lightgray', 'lightgray'])
                
                # Add metrics
                for metric_name, metric_value in category_metrics.items():
                    formatted_value = self._format_metric_value(metric_name, metric_value)
                    table_data.append([metric_name, formatted_value])
                    
                    # Color code based on metric value
                    if isinstance(metric_value, (int, float)):
                        if 'return' in metric_name.lower() or 'profit' in metric_name.lower():
                            color = 'lightgreen' if metric_value > 0 else 'lightcoral'
                        elif 'sharpe' in metric_name.lower():
                            color = 'lightgreen' if metric_value > 1 else 'lightyellow' if metric_value > 0.5 else 'lightcoral'
                        elif 'drawdown' in metric_name.lower():
                            color = 'lightgreen' if abs(metric_value) < 0.1 else 'lightyellow' if abs(metric_value) < 0.2 else 'lightcoral'
                        else:
                            color = 'white'
                    else:
                        color = 'white'
                    
                    colors.append(['white', color])
                
                # Add separator
                table_data.append(["", ""])
                colors.append(['white', 'white'])
            
            # Create table
            table = ax.table(
                cellText=table_data,
                colLabels=['Metric', 'Value'],
                cellLoc='left',
                loc='center',
                cellColours=colors
            )
            
            # Format table
            table.auto_set_font_size(False)
            table.set_fontsize(config.tick_font_size)
            table.scale(1, 2)
            
            # Style header row
            for i in range(2):
                table[(0, i)].set_facecolor(config.primary_color)
                table[(0, i)].set_text_props(weight='bold', color='white')
            
            ax.set_title(title, fontsize=config.title_font_size, fontweight='bold', pad=20)
            ax.axis('off')
            
            plt.tight_layout()
            
            # Extract key summary metrics
            summary_metrics = {}
            if 'Returns' in metrics:
                summary_metrics.update(metrics['Returns'])
            if 'Risk' in metrics:
                summary_metrics.update(metrics['Risk'])
            
            chart_data = self._finalize_chart(
                fig, title, 'performance_metrics', output_path, config,
                {'summary_metrics': summary_metrics}
            )
            
            plt.close(fig)
            
            logger.info("Performance metrics table created successfully")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating performance metrics table: {str(e)}")
            raise
    
    # Private helper methods
    
    def _calculate_equity_curve(self, trades: List[SimpleTrade]) -> Dict[str, Any]:
        """Calculate equity curve data from trades."""
        if not trades:
            return {}
        
        # Sort trades by exit time
        sorted_trades = sorted(trades, key=lambda t: t.exit_time)
        
        dates = []
        cumulative_pnl = []
        running_pnl = 0
        
        # Add starting point
        start_date = sorted_trades[0].entry_time.date()
        dates.append(start_date)
        cumulative_pnl.append(0)
        
        # Calculate cumulative P&L
        for trade in sorted_trades:
            running_pnl += trade.profit_loss
            dates.append(trade.exit_time.date())
            cumulative_pnl.append(running_pnl)
        
        # Calculate drawdown periods
        drawdown_periods = []
        peak = 0
        in_drawdown = False
        drawdown_start = None
        
        for i, pnl in enumerate(cumulative_pnl):
            if pnl > peak:
                # New peak
                if in_drawdown:
                    # End of drawdown period
                    drawdown_periods.append({
                        'start': drawdown_start,
                        'end': dates[i-1],
                        'depth': (peak - min(cumulative_pnl[cumulative_pnl.index(peak):i])) / peak if peak > 0 else 0
                    })
                    in_drawdown = False
                peak = pnl
            elif pnl < peak and not in_drawdown:
                # Start of drawdown
                in_drawdown = True
                drawdown_start = dates[i]
        
        # Handle ongoing drawdown
        if in_drawdown:
            drawdown_periods.append({
                'start': drawdown_start,
                'end': dates[-1],
                'depth': (peak - cumulative_pnl[-1]) / peak if peak > 0 else 0
            })
        
        return {
            'dates': dates,
            'cumulative_pnl': cumulative_pnl,
            'drawdown_periods': drawdown_periods,
            'peak_value': peak,
            'final_value': cumulative_pnl[-1] if cumulative_pnl else 0
        }
    
    def _calculate_drawdown_analysis(self, trades: List[SimpleTrade]) -> Dict[str, Any]:
        """Calculate detailed drawdown analysis."""
        equity_data = self._calculate_equity_curve(trades)
        
        if not equity_data:
            return {}
        
        dates = equity_data['dates']
        cumulative_pnl = equity_data['cumulative_pnl']
        
        # Calculate drawdown percentages
        peak = 0
        drawdown_pct = []
        
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            
            if peak > 0:
                dd_pct = ((pnl - peak) / peak) * 100
            else:
                dd_pct = 0
            
            drawdown_pct.append(dd_pct)
        
        # Calculate recovery periods (periods where drawdown is decreasing)
        recovery_periods = []
        in_recovery = False
        recovery_start = None
        prev_dd = 0
        
        for i, dd in enumerate(drawdown_pct[1:], 1):
            if dd > prev_dd and dd < 0:  # Recovering (less negative)
                if not in_recovery:
                    in_recovery = True
                    recovery_start = dates[i-1] if i > 0 else dates[0]
            elif dd <= prev_dd and in_recovery:  # Recovery ended
                recovery_periods.append({
                    'start': recovery_start,
                    'end': dates[i-1] if i > 0 else dates[0]
                })
                in_recovery = False
            prev_dd = dd
        
        # Handle ongoing recovery
        if in_recovery:
            recovery_periods.append({
                'start': recovery_start,
                'end': dates[-1]
            })
        
        return {
            'dates': dates,
            'cumulative_pnl': cumulative_pnl,
            'drawdown_pct': drawdown_pct,
            'drawdown_periods': equity_data.get('drawdown_periods', []),
            'recovery_periods': recovery_periods,
            'max_drawdown': min(drawdown_pct) if drawdown_pct else 0
        }
    
    def _calculate_monthly_returns(self, trades: List[SimpleTrade]) -> pd.DataFrame:
        """Calculate monthly returns breakdown."""
        if not trades:
            return pd.DataFrame()
        
        # Create DataFrame from trades
        trade_data = []
        for trade in trades:
            trade_data.append({
                'date': trade.exit_time.date(),
                'pnl': trade.profit_loss
            })
        
        df = pd.DataFrame(trade_data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Group by month and calculate returns
        monthly_pnl = df['pnl'].resample('M').sum()
        
        # Create pivot table with years as rows and months as columns
        monthly_pnl_df = monthly_pnl.to_frame()
        monthly_pnl_df['year'] = monthly_pnl_df.index.year
        monthly_pnl_df['month'] = monthly_pnl_df.index.month
        
        # Convert to percentage returns (assuming starting capital for calculation)
        # For this implementation, we'll show absolute returns
        pivot_table = monthly_pnl_df.pivot_table(
            values='pnl',
            index='year',
            columns='month',
            aggfunc='sum',
            fill_value=0
        )
        
        # Rename columns to month names
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Only include months that exist in data
        existing_months = pivot_table.columns
        month_mapping = {i+1: month_names[i] for i in range(12) if i+1 in existing_months}
        pivot_table.rename(columns=month_mapping, inplace=True)
        
        return pivot_table
    
    def _calculate_comprehensive_performance_metrics(
        self,
        trades: List[SimpleTrade],
        include_risk_metrics: bool = True,
        include_trade_metrics: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate comprehensive performance metrics."""
        if not trades:
            return {}
        
        # Use the performance calculator
        performance_data = self.performance_calculator.calculate_comprehensive_metrics(trades)
        
        metrics = {}
        
        # Returns metrics
        metrics['Returns'] = {
            'Total P&L': performance_data.get('total_pnl', 0),
            'Total Return %': performance_data.get('total_return_pct', 0) * 100,
            'Annualized Return': performance_data.get('annualized_return', 0) * 100,
            'CAGR': performance_data.get('cagr', 0) * 100
        }
        
        # Risk metrics
        if include_risk_metrics:
            metrics['Risk'] = {
                'Maximum Drawdown': performance_data.get('max_drawdown', 0) * 100,
                'Volatility': performance_data.get('volatility', 0) * 100,
                'Sharpe Ratio': performance_data.get('sharpe_ratio', 0),
                'Sortino Ratio': performance_data.get('sortino_ratio', 0),
                'VaR (95%)': performance_data.get('var_95', 0),
                'CVaR (95%)': performance_data.get('cvar_95', 0)
            }
        
        # Trade metrics
        if include_trade_metrics:
            winning_trades = [t for t in trades if t.profit_loss > 0]
            losing_trades = [t for t in trades if t.profit_loss < 0]
            
            metrics['Trade Statistics'] = {
                'Total Trades': len(trades),
                'Winning Trades': len(winning_trades),
                'Losing Trades': len(losing_trades),
                'Win Rate': len(winning_trades) / len(trades) * 100 if trades else 0,
                'Profit Factor': performance_data.get('profit_factor', 0),
                'Average Trade': performance_data.get('avg_trade_pnl', 0),
                'Average Winner': np.mean([t.profit_loss for t in winning_trades]) if winning_trades else 0,
                'Average Loser': np.mean([t.profit_loss for t in losing_trades]) if losing_trades else 0,
                'Best Trade': max([t.profit_loss for t in trades]) if trades else 0,
                'Worst Trade': min([t.profit_loss for t in trades]) if trades else 0
            }
        
        return metrics
    
    def _generate_equity_curve_stats(self, equity_data: Dict[str, Any], trades: List[SimpleTrade]) -> str:
        """Generate statistics text for equity curve."""
        final_pnl = equity_data.get('final_value', 0)
        peak_pnl = equity_data.get('peak_value', 0)
        drawdown_periods = len(equity_data.get('drawdown_periods', []))
        
        return f"Final P&L: ${final_pnl:,.0f}\nPeak Value: ${peak_pnl:,.0f}\nDrawdown Periods: {drawdown_periods}\nTotal Trades: {len(trades)}"
    
    def _generate_drawdown_stats(self, drawdown_data: Dict[str, Any], trades: List[SimpleTrade]) -> str:
        """Generate statistics text for drawdown chart."""
        max_dd = drawdown_data.get('max_drawdown', 0)
        dd_periods = len(drawdown_data.get('drawdown_periods', []))
        recovery_periods = len(drawdown_data.get('recovery_periods', []))
        
        return f"Max Drawdown: {max_dd:.1f}%\nDrawdown Periods: {dd_periods}\nRecovery Periods: {recovery_periods}"
    
    def _format_metric_value(self, metric_name: str, value: Any) -> str:
        """Format metric value for display."""
        if isinstance(value, (int, float)):
            if 'return' in metric_name.lower() or '%' in metric_name.lower() or 'rate' in metric_name.lower():
                if abs(value) < 1 and abs(value) > 0:  # Already in decimal form
                    return f"{value * 100:.2f}%"
                else:  # Already in percentage form
                    return f"{value:.2f}%"
            elif 'ratio' in metric_name.lower():
                return f"{value:.3f}"
            elif 'p&l' in metric_name.lower() or '$' in str(value):
                return f"${value:,.2f}"
            else:
                return f"{value:,.2f}"
        else:
            return str(value)
    
    def _finalize_chart(
        self,
        fig: Figure,
        title: str,
        chart_type: str,
        output_path: Optional[str],
        config: ChartConfiguration,
        metadata: Dict[str, Any]
    ) -> ChartData:
        """Finalize chart by saving or converting to base64."""
        
        figure_path = None
        figure_base64 = None
        
        if output_path:
            # Save to file
            fig.savefig(
                output_path,
                format=config.format,
                dpi=config.dpi,
                bbox_inches=config.bbox_inches,
                pad_inches=config.pad_inches,
                facecolor=config.background_color
            )
            figure_path = output_path
        else:
            # Convert to base64
            buffer = io.BytesIO()
            fig.savefig(
                buffer,
                format=config.format,
                dpi=config.dpi,
                bbox_inches=config.bbox_inches,
                pad_inches=config.pad_inches,
                facecolor=config.background_color
            )
            buffer.seek(0)
            figure_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            buffer.close()
        
        # Create chart data
        chart_data = ChartData(
            chart_type=chart_type,
            title=title,
            data=metadata,
            figure_path=figure_path,
            figure_base64=figure_base64,
            metadata={
                'config': asdict(config),
                'generation_time': datetime.now().isoformat(),
                'format': config.format
            }
        )
        
        # Track in history
        self.chart_history.append(chart_data)
        
        return chart_data
    
    def get_chart_history(self) -> List[ChartData]:
        """Get the history of generated charts."""
        return self.chart_history.copy()
    
    def clear_chart_history(self) -> None:
        """Clear the chart generation history."""
        self.chart_history.clear()