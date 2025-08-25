import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchPerformanceMetrics } from '../../store/slices/dashboardSlice';
import MetricCard from '../MetricCard/MetricCard';
import './PerformanceMetrics.css';

interface PerformanceMetricsProps {
  accountName: string;
  showTitle?: boolean;
  compact?: boolean;
}

const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({
  accountName,
  showTitle = true,
  compact = false
}) => {
  const dispatch = useDispatch<AppDispatch>();
  const { performanceMetrics, isLoadingMetrics, metricsError } = useSelector(
    (state: RootState) => state.dashboard
  );

  const metrics = performanceMetrics[accountName];

  useEffect(() => {
    if (accountName && !metrics) {
      dispatch(fetchPerformanceMetrics(accountName));
    }
  }, [dispatch, accountName, metrics]);

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercentage = (value: number): string => {
    return `${value.toFixed(1)}%`;
  };

  const getTrendDirection = (value: number): 'up' | 'down' | 'neutral' => {
    if (value > 0) return 'up';
    if (value < 0) return 'down';
    return 'neutral';
  };

  if (metricsError) {
    return (
      <div className="performance-metrics-error">
        <div className="error-message">
          <h3>Error Loading Metrics</h3>
          <p>{metricsError}</p>
          <button 
            onClick={() => dispatch(fetchPerformanceMetrics(accountName))}
            className="retry-button"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const metricCards = [
    {
      title: 'Total Return',
      value: metrics ? formatCurrency(metrics.total_return) : 0,
      trend: metrics ? getTrendDirection(metrics.total_return) : 'neutral',
      trendValue: metrics ? formatCurrency(Math.abs(metrics.total_return)) : '',
      className: metrics && metrics.total_return > 0 ? 'positive' : metrics && metrics.total_return < 0 ? 'negative' : 'neutral',
      icon: '💰'
    },
    {
      title: 'Win Rate',
      value: metrics ? formatPercentage(metrics.win_rate) : '0%',
      subtitle: metrics ? `${metrics.winning_trades}/${metrics.total_trades} trades` : '',
      className: metrics && metrics.win_rate > 50 ? 'positive' : 'warning',
      icon: '🎯'
    },
    {
      title: 'Profit Factor',
      value: metrics ? metrics.profit_factor.toFixed(2) : '0.00',
      subtitle: 'Gross Profit / Gross Loss',
      className: metrics && metrics.profit_factor > 1 ? 'positive' : 'negative',
      icon: '📊'
    },
    {
      title: 'Sharpe Ratio',
      value: metrics?.sharpe_ratio ? metrics.sharpe_ratio.toFixed(2) : 'N/A',
      subtitle: 'Risk-adjusted return',
      className: metrics && metrics.sharpe_ratio && metrics.sharpe_ratio > 1 ? 'positive' : 'neutral',
      icon: '📈'
    },
    {
      title: 'Max Drawdown',
      value: metrics ? formatCurrency(Math.abs(metrics.max_drawdown)) : '$0',
      subtitle: 'Largest peak-to-trough decline',
      className: 'negative',
      icon: '📉'
    },
    {
      title: 'Average Win',
      value: metrics ? formatCurrency(metrics.average_win) : '$0',
      subtitle: `vs ${metrics ? formatCurrency(Math.abs(metrics.average_loss)) : '$0'} avg loss`,
      className: 'positive',
      icon: '🏆'
    }
  ];

  return (
    <div className={`performance-metrics ${compact ? 'compact' : ''}`}>
      {showTitle && (
        <div className="performance-metrics-header">
          <h2>Performance Metrics</h2>
          <div className="account-info">
            <span className="account-name">{accountName}</span>
            {metrics && (
              <span className="symbol-badge">{metrics.symbol}</span>
            )}
          </div>
        </div>
      )}

      <div className="metrics-grid">
        {metricCards.map((card, index) => (
          <MetricCard
            key={index}
            title={card.title}
            value={card.value}
            subtitle={card.subtitle}
            trend={card.trend}
            trendValue={card.trendValue}
            className={card.className}
            icon={card.icon}
            isLoading={isLoadingMetrics}
          />
        ))}
      </div>

      {metrics && (
        <div className="metrics-summary">
          <div className="summary-row">
            <span className="label">Analysis Period:</span>
            <span className="value">
              {new Date(metrics.period_start).toLocaleDateString()} - {new Date(metrics.period_end).toLocaleDateString()}
            </span>
          </div>
          <div className="summary-row">
            <span className="label">Total Trades:</span>
            <span className="value">{metrics.total_trades}</span>
          </div>
          <div className="summary-row">
            <span className="label">Largest Win:</span>
            <span className="value positive">{formatCurrency(metrics.largest_win)}</span>
          </div>
          <div className="summary-row">
            <span className="label">Largest Loss:</span>
            <span className="value negative">{formatCurrency(metrics.largest_loss)}</span>
          </div>
          {metrics.average_trade_duration && (
            <div className="summary-row">
              <span className="label">Avg Trade Duration:</span>
              <span className="value">{Math.round(metrics.average_trade_duration)} minutes</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PerformanceMetrics;