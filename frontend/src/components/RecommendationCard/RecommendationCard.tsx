import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchCurrentRecommendation } from '../../store/slices/dashboardSlice';
import { TradingRecommendation, RecommendationAction, StrategyType } from '../../types/api';
import './RecommendationCard.css';

interface RecommendationCardProps {
  recommendation?: TradingRecommendation;
  showRefresh?: boolean;
  compact?: boolean;
  onActionClick?: (recommendation: TradingRecommendation) => void;
}

const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendation: propRecommendation,
  showRefresh = true,
  compact = false,
  onActionClick
}) => {
  const dispatch = useDispatch<AppDispatch>();
  const { currentRecommendation, isLoadingRecommendation, recommendationError } = useSelector(
    (state: RootState) => state.dashboard
  );

  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  const recommendation = propRecommendation || currentRecommendation;

  useEffect(() => {
    if (!propRecommendation && !currentRecommendation) {
      dispatch(fetchCurrentRecommendation());
    }
  }, [dispatch, propRecommendation, currentRecommendation]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        dispatch(fetchCurrentRecommendation());
      }, 30000); // Refresh every 30 seconds
      setRefreshInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }

    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, [autoRefresh, dispatch, refreshInterval]);

  const getActionIcon = (action: RecommendationAction): string => {
    switch (action) {
      case RecommendationAction.TRADE: return '✅';
      case RecommendationAction.AVOID: return '❌';
      case RecommendationAction.WAIT: return '⏳';
      default: return '❓';
    }
  };

  const getActionColor = (action: RecommendationAction): string => {
    switch (action) {
      case RecommendationAction.TRADE: return 'trade';
      case RecommendationAction.AVOID: return 'avoid';
      case RecommendationAction.WAIT: return 'wait';
      default: return 'neutral';
    }
  };

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 80) return 'high';
    if (confidence >= 60) return 'medium';
    return 'low';
  };

  const getStrategyDisplayName = (strategy: StrategyType): string => {
    switch (strategy) {
      case StrategyType.STATISTICAL: return 'Statistical';
      case StrategyType.MACHINE_LEARNING: return 'ML Enhanced';
      case StrategyType.MONTE_CARLO: return 'Monte Carlo';
      case StrategyType.COMBINED: return 'Combined';
      default: return strategy;
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatTime = (timestamp: string): string => {
    const now = new Date();
    const recTime = new Date(timestamp);
    const diffMs = now.getTime() - recTime.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return recTime.toLocaleDateString();
  };

  const getDayName = (dayOfWeek: number): string => {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    return days[dayOfWeek] || `Day ${dayOfWeek}`;
  };

  const handleRefresh = () => {
    dispatch(fetchCurrentRecommendation());
  };

  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh);
  };

  if (recommendationError) {
    return (
      <div className="recommendation-card error">
        <div className="error-content">
          <div className="error-icon">⚠️</div>
          <div className="error-text">
            <h3>Error Loading Recommendation</h3>
            <p>{recommendationError}</p>
          </div>
          <button onClick={handleRefresh} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (isLoadingRecommendation) {
    return (
      <div className={`recommendation-card loading ${compact ? 'compact' : ''}`}>
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <p>Loading recommendation...</p>
        </div>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className={`recommendation-card no-data ${compact ? 'compact' : ''}`}>
        <div className="no-data-content">
          <div className="no-data-icon">📊</div>
          <h3>No Recommendation Available</h3>
          <p>No trading recommendation is currently available.</p>
          {showRefresh && (
            <button onClick={handleRefresh} className="refresh-button">
              Get Recommendation
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`recommendation-card ${getActionColor(recommendation.recommended_action)} ${compact ? 'compact' : ''}`}>
      <div className="recommendation-header">
        <div className="action-section">
          <div className="action-icon">
            {getActionIcon(recommendation.recommended_action)}
          </div>
          <div className="action-details">
            <h2 className="action-title">{recommendation.recommended_action}</h2>
            <div className="account-symbol">
              <span className="account">{recommendation.account_name}</span>
              <span className="symbol-badge">{recommendation.symbol}</span>
            </div>
          </div>
        </div>

        <div className="confidence-section">
          <div className={`confidence-score ${getConfidenceColor(recommendation.confidence_score)}`}>
            {recommendation.confidence_score.toFixed(0)}%
          </div>
          <div className="confidence-label">Confidence</div>
        </div>

        {showRefresh && (
          <div className="controls-section">
            <button 
              onClick={handleRefresh} 
              className="control-button refresh"
              disabled={isLoadingRecommendation}
            >
              🔄
            </button>
            <button 
              onClick={toggleAutoRefresh}
              className={`control-button auto-refresh ${autoRefresh ? 'active' : ''}`}
            >
              ⚡
            </button>
          </div>
        )}
      </div>

      {!compact && (
        <>
          <div className="recommendation-metrics">
            <div className="metric-item">
              <span className="metric-label">Expected Return</span>
              <span className={`metric-value ${recommendation.expected_return >= 0 ? 'positive' : 'negative'}`}>
                {formatCurrency(recommendation.expected_return)}
              </span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Expected Risk</span>
              <span className="metric-value neutral">
                {formatCurrency(recommendation.expected_risk)}
              </span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Historical Win Rate</span>
              <span className="metric-value">
                {(recommendation.historical_win_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Avg Profit (This Time)</span>
              <span className={`metric-value ${recommendation.avg_profit_this_time >= 0 ? 'positive' : 'negative'}`}>
                {formatCurrency(recommendation.avg_profit_this_time)}
              </span>
            </div>
          </div>

          <div className="recommendation-reasoning">
            <h4>Reasoning</h4>
            <p>{recommendation.reasoning}</p>
          </div>

          <div className="recommendation-details">
            <div className="detail-row">
              <span className="detail-label">Strategy:</span>
              <span className="detail-value strategy-badge">
                {getStrategyDisplayName(recommendation.strategy_used)}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Timing:</span>
              <span className="detail-value">
                {getDayName(recommendation.day_of_week)} at {recommendation.hour_of_day}:00
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Generated:</span>
              <span className="detail-value">
                {formatTime(recommendation.timestamp)}
              </span>
            </div>
          </div>

          {recommendation.risk_metrics && Object.keys(recommendation.risk_metrics).length > 0 && (
            <div className="risk-metrics">
              <h4>Risk Metrics</h4>
              <div className="risk-grid">
                {Object.entries(recommendation.risk_metrics).map(([key, value]) => (
                  <div key={key} className="risk-item">
                    <span className="risk-label">
                      {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    <span className="risk-value">
                      {typeof value === 'number' ? formatCurrency(value) : value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {onActionClick && recommendation.recommended_action === RecommendationAction.TRADE && (
            <div className="recommendation-actions">
              <button 
                onClick={() => onActionClick(recommendation)}
                className="action-button primary"
              >
                Execute Trade
              </button>
            </div>
          )}
        </>
      )}

      <div className="recommendation-footer">
        <div className="timestamp">
          Last updated: {formatTime(recommendation.timestamp)}
        </div>
        {autoRefresh && (
          <div className="auto-refresh-indicator">
            <span className="pulse-dot"></span>
            Auto-refresh enabled
          </div>
        )}
      </div>
    </div>
  );
};

export default RecommendationCard;