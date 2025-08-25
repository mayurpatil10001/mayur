import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchTemporalAnalysis, fetchAccountCorrelation, clearAnalyticsData } from '../../store/slices/analyticsSlice';
import './Analytics.css';

const Analytics: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { 
    temporalAnalysis, 
    correlationData,
    isLoadingTemporal,
    isLoadingCorrelation,
    temporalError,
    correlationError
  } = useSelector((state: RootState) => state.analytics);

  // Add state for performance metrics and account selection
  const [selectedAccount, setSelectedAccount] = React.useState<string>('');
  const [availableAccounts, setAvailableAccounts] = React.useState<string[]>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = React.useState(false);
  const [performanceMetrics, setPerformanceMetrics] = React.useState<any>(null);
  const [isLoadingPerformance, setIsLoadingPerformance] = React.useState(false);
  const [performanceError, setPerformanceError] = React.useState<string | null>(null);

  // Function to fetch all available accounts
  const fetchAvailableAccounts = async () => {
    setIsLoadingAccounts(true);
    try {
      const response = await fetch('http://localhost:8000/api/v1/accounts');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      if (result.status === 'success' && result.data && result.data.items) {
        const accountNames = result.data.items.map((account: any) => account.name);
        setAvailableAccounts(accountNames);
        
        // Set the first account as default if no account is selected
        if (accountNames.length > 0 && !selectedAccount) {
          setSelectedAccount(accountNames[0]);
        }
        
        console.log('[ANALYTICS] Available accounts loaded:', accountNames);
        console.log('[ANALYTICS] Full API response:', result);
      } else {
        console.error('[ANALYTICS] Invalid API response structure:', result);
        throw new Error(result.message || 'Failed to fetch accounts');
      }
    } catch (error) {
      console.error('[ANALYTICS] Error fetching accounts:', error);
      // Fallback to hardcoded accounts if API fails
      const fallbackAccounts = ['CL_3', 'CL_TM_2', 'IPS_TM_10', 'IPS_TM_13'];
      setAvailableAccounts(fallbackAccounts);
      if (!selectedAccount) {
        setSelectedAccount(fallbackAccounts[0]);
      }
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  // Function to fetch performance metrics
  const fetchPerformanceMetrics = async (accountName: string) => {
    setIsLoadingPerformance(true);
    setPerformanceError(null);
    
    try {
      const response = await fetch(`http://localhost:8000/api/v1/analytics/performance/${accountName}`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      if (result.status === 'success' && result.data) {
        setPerformanceMetrics(result.data);
        console.log('[ANALYTICS] Performance metrics loaded:', result.data);
      } else {
        throw new Error(result.message || 'Failed to fetch performance metrics');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setPerformanceError(errorMessage);
      console.error('[ANALYTICS] Performance metrics error:', error);
    } finally {
      setIsLoadingPerformance(false);
    }
  };

  // Function to load data for selected account
  const loadAccountData = React.useCallback((accountName: string) => {
    console.log('[ANALYTICS] Loading data for account:', accountName);
    
    // Clear previous data first
    dispatch(clearAnalyticsData());
    setPerformanceMetrics(null);
    setPerformanceError(null);
    
    dispatch(fetchTemporalAnalysis({ 
      accountName: accountName
    })).then((result) => {
      console.log('[ANALYTICS] Temporal analysis result:', result);
    }).catch((error) => {
      console.error('[ANALYTICS] Temporal analysis error:', error);
    });
    
    dispatch(fetchAccountCorrelation([accountName, 'CL_TM_2'])).then((result) => {
      console.log('[ANALYTICS] Correlation result:', result);
    }).catch((error) => {
      console.error('[ANALYTICS] Correlation error:', error);
    });

    fetchPerformanceMetrics(accountName);
  }, [dispatch]);

  useEffect(() => {
    console.log('[ANALYTICS] Component mounted, fetching accounts...');
    fetchAvailableAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      console.log('[ANALYTICS] Loading data for selected account:', selectedAccount);
      loadAccountData(selectedAccount);
    }
  }, [loadAccountData, selectedAccount]);

  // Handle account selection change
  const handleAccountChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newAccount = event.target.value;
    setSelectedAccount(newAccount);
  };

  if (isLoadingAccounts) {
    return (
      <div className="analytics">
        <div className="loading">Loading accounts...</div>
      </div>
    );
  }

  if (isLoadingTemporal || isLoadingCorrelation || isLoadingPerformance) {
    return (
      <div className="analytics">
        <div className="loading">Loading analytics data...</div>
      </div>
    );
  }

  if (temporalError || correlationError || performanceError) {
    return (
      <div className="analytics">
        <div className="error">Error loading analytics: {temporalError || correlationError || performanceError}</div>
      </div>
    );
  }

  console.log('[ANALYTICS] Current state:', {
    temporalAnalysis,
    correlationData,
    isLoadingTemporal,
    isLoadingCorrelation,
    temporalError,
    correlationError
  });

  return (
    <div className="analytics">
      <div className="analytics-header">
        <h1>Trading Analytics</h1>
        <div className="account-selector">
          <label htmlFor="account-select">Select Account: </label>
          <select 
            id="account-select" 
            value={selectedAccount} 
            onChange={handleAccountChange}
            className="account-dropdown"
            disabled={isLoadingAccounts || availableAccounts.length === 0}
          >
            {isLoadingAccounts ? (
              <option value="">Loading accounts...</option>
            ) : availableAccounts.length === 0 ? (
              <option value="">No accounts available</option>
            ) : (
              availableAccounts.map(account => (
                <option key={account} value={account}>
                  {account}
                </option>
              ))
            )}
          </select>
        </div>
      </div>
      
      <div className="analytics-grid">
        <div className="analytics-card">
          <h3>Temporal Patterns</h3>
          <div className="temporal-section">
            <h4>Trading Patterns by Hour</h4>
            <div className="pattern-list">
              {temporalAnalysis && selectedAccount && temporalAnalysis[selectedAccount] ? (
                (() => {
                  const analysis = temporalAnalysis[selectedAccount];
                  return (
                    <div className="pattern-item">
                      <div className="account-header">
                        <strong>Account: {selectedAccount} ({analysis.symbol})</strong>
                      </div>
                      <div className="analysis-details">
                        <p>Period: {new Date(analysis.analysis_period_start).toLocaleDateString()} - {new Date(analysis.analysis_period_end).toLocaleDateString()}</p>
                        {analysis.best_trading_hours && (
                          <p>Best Hours: {analysis.best_trading_hours.join(', ')}</p>
                        )}
                        {analysis.best_trading_days && (
                          <p>Best Days: {analysis.best_trading_days.map((d: number) => ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d]).join(', ')}</p>
                        )}
                        {analysis.hourly_performance && (
                          <div className="hourly-stats">
                            <h5>Top Performing Hours:</h5>
                            {Object.entries(analysis.hourly_performance).slice(0, 3).map(([hour, stats]: [string, any]) => (
                              <div key={hour} className="hour-stat">
                                <span>{hour}:00 - Win Rate: {(stats.win_rate * 100).toFixed(1)}%, Avg P&L: ${stats.avg_profit.toFixed(2)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="no-data">No temporal data available</div>
              )}
            </div>
          </div>
        </div>

        <div className="analytics-card">
          <h3>Account Correlations</h3>
          <div className="comparison-table">
            {correlationData ? (
              <div className="correlation-item">
                <div className="correlation-header">
                  <span>Correlation Analysis</span>
                  <span>Period: {correlationData.period_start ? new Date(correlationData.period_start).toLocaleDateString() : 'N/A'} - {correlationData.period_end ? new Date(correlationData.period_end).toLocaleDateString() : 'N/A'}</span>
                </div>
                <div className="correlation-metrics">
                  <div className="correlation-matrix">
                    <h5>Correlation Matrix:</h5>
                    {correlationData.correlation_matrix && Object.entries(correlationData.correlation_matrix).map(([account1, correlations]: [string, any]) => (
                      <div key={account1} className="correlation-row">
                        <strong>{account1}:</strong>
                        {Object.entries(correlations).map(([account2, correlation]: [string, any]) => (
                          <span key={account2} className="correlation-value">
                            {account2}: {(correlation * 100).toFixed(1)}%
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                  {correlationData.strongest_correlation && (
                    <div className="correlation-highlight">
                      <p><strong>Strongest Correlation:</strong> {correlationData.strongest_correlation.accounts.join(' & ')} ({(correlationData.strongest_correlation.correlation * 100).toFixed(1)}%)</p>
                    </div>
                  )}
                  {correlationData.diversification_score && (
                    <div className="diversification-info">
                      <p><strong>Diversification Score:</strong> {(correlationData.diversification_score * 100).toFixed(1)}%</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="no-data">No correlation data available</div>
            )}
          </div>
        </div>

        <div className="analytics-card full-width">
          <h3>Performance Overview</h3>
          <div className="refresh-section">
            <button 
              onClick={() => {
                console.log('[ANALYTICS] Refresh button clicked');
                dispatch(fetchTemporalAnalysis({ accountName: 'CL_3' })).then((result) => {
                  console.log('[ANALYTICS] Refresh temporal result:', result);
                });
                dispatch(fetchAccountCorrelation(['CL_3', 'CL_TM_2'])).then((result) => {
                  console.log('[ANALYTICS] Refresh correlation result:', result);
                });
                fetchPerformanceMetrics('CL_3');
              }}
              disabled={isLoadingTemporal || isLoadingCorrelation || isLoadingPerformance}
            >
              Refresh Analytics
            </button>
          </div>
          
          {performanceMetrics ? (
            <div className="performance-metrics">
              <div className="metrics-grid">
                <div className="metric-card">
                  <h4>Account Performance</h4>
                  <div className="metric-item">
                    <span className="metric-label">Account:</span>
                    <span className="metric-value">{performanceMetrics.account_name} ({performanceMetrics.symbol})</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Period:</span>
                    <span className="metric-value">
                      {performanceMetrics.period_start ? new Date(performanceMetrics.period_start).toLocaleDateString() : 'N/A'} - {performanceMetrics.period_end ? new Date(performanceMetrics.period_end).toLocaleDateString() : 'N/A'}
                    </span>
                  </div>
                </div>

                <div className="metric-card">
                  <h4>Trading Statistics</h4>
                  <div className="metric-item">
                    <span className="metric-label">Total Trades:</span>
                    <span className="metric-value">{performanceMetrics.total_trades}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Winning Trades:</span>
                    <span className="metric-value positive">{performanceMetrics.winning_trades}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Losing Trades:</span>
                    <span className="metric-value negative">{performanceMetrics.losing_trades}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Win Rate:</span>
                    <span className={`metric-value ${performanceMetrics.win_rate >= 50 ? 'positive' : 'negative'}`}>
                      {performanceMetrics.win_rate.toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="metric-card">
                  <h4>Financial Performance</h4>
                  <div className="metric-item">
                    <span className="metric-label">Total Return:</span>
                    <span className={`metric-value ${performanceMetrics.total_return >= 0 ? 'positive' : 'negative'}`}>
                      ${performanceMetrics.total_return.toLocaleString()}
                    </span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Net Profit:</span>
                    <span className={`metric-value ${performanceMetrics.net_profit >= 0 ? 'positive' : 'negative'}`}>
                      ${performanceMetrics.net_profit.toLocaleString()}
                    </span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Average Win:</span>
                    <span className="metric-value positive">${performanceMetrics.average_win.toFixed(2)}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Average Loss:</span>
                    <span className="metric-value negative">${performanceMetrics.average_loss.toFixed(2)}</span>
                  </div>
                </div>

                <div className="metric-card">
                  <h4>Risk Metrics</h4>
                  <div className="metric-item">
                    <span className="metric-label">Profit Factor:</span>
                    <span className={`metric-value ${performanceMetrics.profit_factor >= 1 ? 'positive' : 'negative'}`}>
                      {performanceMetrics.profit_factor.toFixed(2)}
                    </span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Max Drawdown:</span>
                    <span className="metric-value negative">${performanceMetrics.max_drawdown.toLocaleString()}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Sharpe Ratio:</span>
                    <span className={`metric-value ${performanceMetrics.sharpe_ratio >= 1 ? 'positive' : 'negative'}`}>
                      {performanceMetrics.sharpe_ratio.toFixed(2)}
                    </span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Volatility:</span>
                    <span className="metric-value">{(performanceMetrics.volatility * 100).toFixed(1)}%</span>
                  </div>
                </div>

                <div className="metric-card">
                  <h4>Extremes</h4>
                  <div className="metric-item">
                    <span className="metric-label">Largest Win:</span>
                    <span className="metric-value positive">${performanceMetrics.largest_win.toFixed(2)}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Largest Loss:</span>
                    <span className="metric-value negative">${performanceMetrics.largest_loss.toFixed(2)}</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Avg Trade Duration:</span>
                    <span className="metric-value">{performanceMetrics.average_trade_duration.toFixed(1)} min</span>
                  </div>
                  <div className="metric-item">
                    <span className="metric-label">Total Commission:</span>
                    <span className="metric-value">${performanceMetrics.total_commission.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="no-data">
              <p>Click "Refresh Analytics" to load performance metrics</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Analytics;