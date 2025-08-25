import React from 'react';
import './MetricCard.css';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  isLoading?: boolean;
  icon?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  trendValue,
  isLoading = false,
  icon,
  className = '',
  onClick
}) => {
  const getTrendColor = (trend?: 'up' | 'down' | 'neutral') => {
    switch (trend) {
      case 'up': return 'trend-up';
      case 'down': return 'trend-down';
      case 'neutral': return 'trend-neutral';
      default: return '';
    }
  };

  const formatValue = (value: string | number): string => {
    if (typeof value === 'number') {
      // Format numbers with appropriate precision
      if (Math.abs(value) >= 1000000) {
        return `${(value / 1000000).toFixed(1)}M`;
      } else if (Math.abs(value) >= 1000) {
        return `${(value / 1000).toFixed(1)}K`;
      } else if (value % 1 !== 0) {
        return value.toFixed(2);
      }
      return value.toString();
    }
    return value;
  };

  return (
    <div 
      className={`metric-card ${className} ${onClick ? 'clickable' : ''}`}
      onClick={onClick}
    >
      <div className="metric-card-header">
        {icon && <div className="metric-card-icon">{icon}</div>}
        <h3 className="metric-card-title">{title}</h3>
      </div>
      
      <div className="metric-card-content">
        {isLoading ? (
          <div className="metric-card-loading">
            <div className="loading-spinner" data-testid="loading-spinner"></div>
          </div>
        ) : (
          <>
            <div className="metric-card-value">
              {formatValue(value)}
            </div>
            
            {subtitle && (
              <div className="metric-card-subtitle">
                {subtitle}
              </div>
            )}
            
            {trend && trendValue && (
              <div className={`metric-card-trend ${getTrendColor(trend)}`}>
                <span className="trend-icon">
                  {trend === 'up' ? '↗' : trend === 'down' ? '↘' : '→'}
                </span>
                <span className="trend-value">{trendValue}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default MetricCard;