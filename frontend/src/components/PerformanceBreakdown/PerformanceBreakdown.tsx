import React from 'react';
import './PerformanceBreakdown.css';

interface PerformanceMetric {
  label: string;
  value: string | number;
  category: 'returns' | 'risk' | 'trades';
  status?: 'positive' | 'negative' | 'neutral';
}

interface MonteCarloMetric {
  label: string;
  value: string | number;
  description: string;
  status: 'good' | 'warning' | 'poor';
}

interface PerformanceBreakdownProps {
  performanceMetrics: PerformanceMetric[];
  monteCarloMetrics: MonteCarloMetric[];
  title?: string;
  subtitle?: string;
}

const PerformanceBreakdown: React.FC<PerformanceBreakdownProps> = ({
  performanceMetrics,
  monteCarloMetrics,
  title = "Performance Breakdown",
  subtitle = "Detailed performance analysis across key metrics"
}) => {
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'positive':
      case 'good':
        return '#10b981';
      case 'negative':
      case 'poor':
        return '#ef4444';
      case 'warning':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good':
        return '✅';
      case 'warning':
        return '⚠️';
      case 'poor':
        return '❌';
      default:
        return '📊';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'returns':
        return '💰';
      case 'risk':
        return '⚠️';
      case 'trades':
        return '📊';
      default:
        return '📈';
    }
  };

  const groupedMetrics = performanceMetrics.reduce((acc, metric) => {
    if (!acc[metric.category]) {
      acc[metric.category] = [];
    }
    acc[metric.category].push(metric);
    return acc;
  }, {} as Record<string, PerformanceMetric[]>);

  const categoryLabels = {
    returns: 'Returns',
    risk: 'Risk',
    trades: 'Trade Stats'
  };

  return (
    <div className="performance-breakdown">
      {/* Header */}
      <div className="breakdown-header">
        <h4 className="breakdown-title">
          <span className="breakdown-icon">📊</span>
          {title}
        </h4>
        <p className="breakdown-subtitle">{subtitle}</p>
      </div>

      {/* Performance Metrics */}
      <div className="performance-section">
        <div className="metrics-categories">
          {Object.entries(groupedMetrics).map(([category, metrics]) => (
            <div key={category} className="metrics-category">
              <div className="category-header">
                <span className="category-icon">{getCategoryIcon(category)}</span>
                <span className="category-label">{categoryLabels[category as keyof typeof categoryLabels]}</span>
              </div>
              <div className="category-metrics">
                {metrics.map((metric, index) => (
                  <div key={index} className="performance-metric">
                    <div className="metric-label">{metric.label}</div>
                    <div 
                      className="metric-value"
                      style={{ color: getStatusColor(metric.status) }}
                    >
                      {metric.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Monte Carlo Risk Analysis */}
      <div className="monte-carlo-section">
        <div className="monte-carlo-header">
          <h5 className="monte-carlo-title">
            <span className="monte-carlo-icon">🎲</span>
            Monte Carlo Risk Analysis
          </h5>
          <p className="monte-carlo-subtitle">
            Statistical simulation: 10,000 scenarios using historical distribution and Monte Carlo risk rating: 8/10
          </p>
        </div>

        <div className="monte-carlo-grid">
          {monteCarloMetrics.map((metric, index) => (
            <div key={index} className={`monte-carlo-card ${metric.status}`}>
              <div className="card-header">
                <span className="card-icon">{getStatusIcon(metric.status)}</span>
                <span className="card-label">{metric.label}</span>
              </div>
              <div className="card-value">{metric.value}</div>
              <div className="card-description">{metric.description}</div>
            </div>
          ))}
        </div>

        {/* Additional Monte Carlo Cards */}
        <div className="additional-cards">
          <div className="monte-carlo-card poor">
            <div className="card-header">
              <span className="card-icon">📉</span>
              <span className="card-label">Worst Case Scenario</span>
            </div>
            <div className="card-value">-$7,154.60</div>
            <div className="card-description">Maximum potential loss in simulation</div>
          </div>
          
          <div className="monte-carlo-card good">
            <div className="card-header">
              <span className="card-icon">📈</span>
              <span className="card-label">Best Case Scenario</span>
            </div>
            <div className="card-value">$7,830.80</div>
            <div className="card-description">Maximum potential gain in simulation</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceBreakdown;