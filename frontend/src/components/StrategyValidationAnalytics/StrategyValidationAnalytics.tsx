import React from 'react';
import './StrategyValidationAnalytics.css';

interface ValidationMetric {
  label: string;
  value: string | number;
  icon: string;
  color: 'green' | 'blue' | 'orange' | 'red';
}

interface TrustIndicator {
  title: string;
  description: string;
  status: 'good' | 'warning' | 'poor';
  details: string;
}

interface StrategyValidationAnalyticsProps {
  title?: string;
  subtitle?: string;
  metrics: ValidationMetric[];
  trustIndicators: TrustIndicator[];
  overallScore?: number;
}

const StrategyValidationAnalytics: React.FC<StrategyValidationAnalyticsProps> = ({
  title = "Strategy Validation Analytics",
  subtitle = "NQ Multi-Account Time-Bin Strategy",
  metrics,
  trustIndicators,
  overallScore
}) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good':
        return '✅';
      case 'warning':
        return '⚠️';
      case 'poor':
        return '❌';
      default:
        return '⚪';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good':
        return '#10b981';
      case 'warning':
        return '#f59e0b';
      case 'poor':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const getMetricColorClass = (color: string) => {
    switch (color) {
      case 'green':
        return 'metric-green';
      case 'blue':
        return 'metric-blue';
      case 'orange':
        return 'metric-orange';
      case 'red':
        return 'metric-red';
      default:
        return 'metric-blue';
    }
  };

  return (
    <div className="strategy-validation-analytics">
      {/* Header */}
      <div className="validation-header">
        <div className="header-content">
          <span className="header-icon">🔬</span>
          <div className="header-text">
            <h3 className="validation-title">{title}</h3>
            <p className="validation-subtitle">{subtitle}</p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="metrics-grid">
        {metrics.map((metric, index) => (
          <div key={index} className={`metric-card ${getMetricColorClass(metric.color)}`}>
            <div className="metric-icon">{metric.icon}</div>
            <div className="metric-content">
              <div className="metric-value">{metric.value}</div>
              <div className="metric-label">{metric.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Trust Indicators */}
      <div className="trust-section">
        <h4 className="trust-title">
          <span className="trust-icon">🛡️</span>
          Can You Trust This Strategy?
        </h4>
        <div className="trust-indicators">
          {trustIndicators.map((indicator, index) => (
            <div key={index} className={`trust-indicator ${indicator.status}`}>
              <div className="trust-status">
                {getStatusIcon(indicator.status)}
              </div>
              <div className="trust-content">
                <div className="trust-indicator-title">{indicator.title}</div>
                <div className="trust-description">{indicator.description}</div>
                <div className="trust-details">{indicator.details}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Overall Score */}
      {overallScore !== undefined && (
        <div className="overall-score">
          <div className="score-label">Trading Readiness Score</div>
          <div className="score-value">
            <span className="score-number">{overallScore}%</span>
            <div className="score-bar">
              <div 
                className="score-fill"
                style={{ 
                  width: `${overallScore}%`,
                  backgroundColor: overallScore >= 80 ? '#10b981' : overallScore >= 60 ? '#f59e0b' : '#ef4444'
                }}
              />
            </div>
          </div>
          <div className="score-status">
            {overallScore >= 80 ? (
              <span className="status-ready">✅ READY FOR LIVE TRADING</span>
            ) : overallScore >= 60 ? (
              <span className="status-caution">⚠️ PROCEED WITH CAUTION</span>
            ) : (
              <span className="status-not-ready">❌ NOT READY FOR LIVE TRADING</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default StrategyValidationAnalytics;