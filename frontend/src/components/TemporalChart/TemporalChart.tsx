import React, { useEffect, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchTemporalAnalysis } from '../../store/slices/analyticsSlice';
import { TemporalAnalysis, TemporalPerformance } from '../../types/api';
import './TemporalChart.css';

interface TemporalChartProps {
  accountName: string;
  chartType: 'hourly' | 'daily';
  metric: 'total_pnl' | 'win_rate' | 'average_pnl' | 'total_trades';
  height?: number;
  showTitle?: boolean;
}

const TemporalChart: React.FC<TemporalChartProps> = ({
  accountName,
  chartType,
  metric,
  height = 400,
  showTitle = true
}) => {
  const dispatch = useDispatch<AppDispatch>();
  const { temporalAnalysis, isLoadingTemporal, temporalError } = useSelector(
    (state: RootState) => state.analytics
  );

  const analysis = temporalAnalysis[accountName];

  useEffect(() => {
    if (accountName && !analysis) {
      dispatch(fetchTemporalAnalysis({ accountName }));
    }
  }, [dispatch, accountName, analysis]);

  const chartData = useMemo(() => {
    if (!analysis) return null;

    const data = chartType === 'hourly' ? analysis.hourly_performance : analysis.daily_performance;
    const keys = Object.keys(data).sort((a, b) => parseInt(a) - parseInt(b));
    
    const values = keys.map(key => {
      const perfData = data[key];
      switch (metric) {
        case 'total_pnl':
          return perfData.total_pnl;
        case 'win_rate':
          return perfData.win_rate * 100; // Convert to percentage
        case 'average_pnl':
          return perfData.average_pnl;
        case 'total_trades':
          return perfData.total_trades;
        default:
          return 0;
      }
    });

    const labels = chartType === 'hourly' 
      ? keys.map(hour => `${hour}:00`)
      : keys.map(day => {
          const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
          return dayNames[parseInt(day)] || `Day ${day}`;
        });

    return { keys, values, labels };
  }, [analysis, chartType, metric]);

  const getMetricDisplayName = (metric: string): string => {
    switch (metric) {
      case 'total_pnl': return 'Total P&L';
      case 'win_rate': return 'Win Rate (%)';
      case 'average_pnl': return 'Average P&L';
      case 'total_trades': return 'Total Trades';
      default: return metric;
    }
  };

  const getChartTitle = (): string => {
    const metricName = getMetricDisplayName(metric);
    const timeFrame = chartType === 'hourly' ? 'Hour of Day' : 'Day of Week';
    return `${metricName} by ${timeFrame}`;
  };

  const getColorScale = (values: number[]): string => {
    if (metric === 'total_pnl' || metric === 'average_pnl') {
      // Use red-to-green scale for P&L metrics
      return 'RdYlGn';
    } else if (metric === 'win_rate') {
      // Use blue scale for win rate
      return 'Blues';
    } else {
      // Use viridis for trade count
      return 'Viridis';
    }
  };

  const formatValue = (value: number): string => {
    if (metric === 'total_pnl' || metric === 'average_pnl') {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(value);
    } else if (metric === 'win_rate') {
      return `${value.toFixed(1)}%`;
    } else {
      return value.toString();
    }
  };

  if (temporalError) {
    return (
      <div className="temporal-chart-error">
        <div className="error-message">
          <h3>Error Loading Chart Data</h3>
          <p>{temporalError}</p>
          <button 
            onClick={() => dispatch(fetchTemporalAnalysis({ accountName }))}
            className="retry-button"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (isLoadingTemporal || !chartData) {
    return (
      <div className="temporal-chart-loading">
        <div className="loading-spinner"></div>
        <p>Loading chart data...</p>
      </div>
    );
  }

  const plotData = [
    {
      x: chartData.labels,
      y: chartData.values,
      type: 'bar' as const,
      marker: {
        color: chartData.values,
        colorscale: getColorScale(chartData.values),
        showscale: true,
        colorbar: {
          title: getMetricDisplayName(metric),
          titleside: 'right' as const,
        },
      },
      text: chartData.values.map(formatValue),
      textposition: 'outside' as const,
      hovertemplate: `<b>%{x}</b><br>${getMetricDisplayName(metric)}: %{text}<br><extra></extra>`,
    },
  ];

  const layout = {
    title: showTitle ? {
      text: getChartTitle(),
      font: { size: 16, color: '#2c3e50' },
    } : undefined,
    xaxis: {
      title: chartType === 'hourly' ? 'Hour of Day' : 'Day of Week',
      tickangle: chartType === 'daily' ? -45 : 0,
    },
    yaxis: {
      title: getMetricDisplayName(metric),
      tickformat: metric === 'win_rate' ? '.1f' : 
                  (metric === 'total_pnl' || metric === 'average_pnl') ? '$,.0f' : '.0f',
    },
    height: height,
    margin: { t: showTitle ? 60 : 20, r: 50, b: 80, l: 80 },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Arial, sans-serif', size: 12, color: '#2c3e50' },
    showlegend: false,
  };

  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'] as any,
    responsive: true,
  };

  return (
    <div className="temporal-chart">
      <Plot
        data={plotData}
        layout={layout}
        config={config}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
      />
      
      {analysis?.statistical_significance && (
        <div className="statistical-significance">
          <h4>Statistical Significance</h4>
          {chartType === 'hourly' && analysis.statistical_significance.hourly_anova && (
            <div className="significance-item">
              <span className="label">Hourly Pattern:</span>
              <span className={`value ${analysis.statistical_significance.hourly_anova.significant ? 'significant' : 'not-significant'}`}>
                {analysis.statistical_significance.hourly_anova.significant ? 'Significant' : 'Not Significant'}
              </span>
              <span className="p-value">
                (p = {analysis.statistical_significance.hourly_anova.p_value.toFixed(3)})
              </span>
            </div>
          )}
          {chartType === 'daily' && analysis.statistical_significance.daily_anova && (
            <div className="significance-item">
              <span className="label">Daily Pattern:</span>
              <span className={`value ${analysis.statistical_significance.daily_anova.significant ? 'significant' : 'not-significant'}`}>
                {analysis.statistical_significance.daily_anova.significant ? 'Significant' : 'Not Significant'}
              </span>
              <span className="p-value">
                (p = {analysis.statistical_significance.daily_anova.p_value.toFixed(3)})
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TemporalChart;