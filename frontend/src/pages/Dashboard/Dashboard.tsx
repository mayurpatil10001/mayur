import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { setSelectedAccount, fetchPerformanceMetrics, fetchCurrentRecommendation, fetchRecentTrades } from '../../store/slices/dashboardSlice';
import './Dashboard.css';

const Dashboard: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { 
    selectedAccount, 
    performanceMetrics, 
    currentRecommendation, 
    recentTrades,
    isLoadingMetrics,
    isLoadingRecommendation,
    isLoadingTrades 
  } = useSelector((state: RootState) => state.dashboard);

  // Fetch accounts from API
  const [availableAccounts, setAvailableAccounts] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'validation' | 'temporal' | 'monte-carlo'>('overview');
  const [isCleaningTrades, setIsCleaningTrades] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<any>(null);
  const [validationData, setValidationData] = useState<any>(null);
  const [isLoadingValidation, setIsLoadingValidation] = useState(false);

  // Fetch available accounts from API
  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        console.log('[DASHBOARD] Fetching accounts...');
        const response = await fetch('http://localhost:8000/api/v1/accounts/?size=100');
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('[DASHBOARD] API Response:', data);
        
        if (data.status === 'success' && data.data?.items) {
          const items = data.data.items;
          const displayNames = items.map((item: any) => 
            `${item.name} (${item.symbol}) - ${item.total_trades.toLocaleString()} trades`
          );
          
          console.log('[DASHBOARD] Setting', displayNames.length, 'accounts');
          setAvailableAccounts(displayNames);
          
        } else {
          console.error('[DASHBOARD] Invalid response:', data);
          setAvailableAccounts(['ERROR: Invalid API response']);
        }
      } catch (error) {
        console.error('[DASHBOARD] Fetch error:', error);
        setAvailableAccounts(['ERROR: Failed to load accounts']);
      }
    };
    
    fetchAccounts();
  }, []);

  // Set default account if none selected
  useEffect(() => {
    if (!selectedAccount && availableAccounts.length > 0 && !availableAccounts[0].includes('ERROR')) {
      const firstAccountName = availableAccounts[0].split(' (')[0];
      console.log('[DASHBOARD] Auto-selecting first account:', firstAccountName);
      dispatch(setSelectedAccount(firstAccountName));
    }
  }, [availableAccounts, selectedAccount, dispatch]);

  // Fetch validation analytics data
  const fetchValidationData = async (accountName: string) => {
    setIsLoadingValidation(true);
    try {
      // Fetch advanced recommendations with validation data
      const response = await fetch(`http://localhost:8000/api/v1/recommendations/advanced?account_name=${accountName}&min_confidence=0.0`);
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success' && data.data?.length > 0) {
          setValidationData(data.data[0]); // Use first recommendation for validation display
        }
      }
    } catch (error) {
      console.error('Error fetching validation data:', error);
    } finally {
      setIsLoadingValidation(false);
    }
  };

  // Fetch data when account changes
  useEffect(() => {
    if (selectedAccount) {
      dispatch(fetchPerformanceMetrics(selectedAccount));
      dispatch(fetchCurrentRecommendation());
      dispatch(fetchRecentTrades({ accountName: selectedAccount, limit: 5 }));
      fetchValidationData(selectedAccount);
    }
  }, [dispatch, selectedAccount]);

  const handleAccountChange = (displayName: string) => {
    // Extract just the account name from the display format "AccountName (Symbol) - X trades"
    const accountName = displayName.split(' (')[0];
    console.log('[DASHBOARD] Selected account:', accountName, 'from display:', displayName);
    dispatch(setSelectedAccount(accountName));
  };

  const handleRecommendationAction = (recommendation: any) => {
    // In a real app, this would integrate with trading system
    console.log('Execute trade recommendation:', recommendation);
    alert(`Trade recommendation for ${recommendation.account_name} - ${recommendation.symbol} would be executed here.`);
  };

  const handleCleanMultidayTrades = async () => {
    if (!window.confirm('This will permanently remove all trades that were not closed on the same day they were opened. Are you sure?')) {
      return;
    }

    setIsCleaningTrades(true);
    setCleanupResult(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/analytics/clean-multiday-trades', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.status === 'success') {
        setCleanupResult(result.data);
        alert(`Successfully removed ${result.data.trades_removed} multi-day trades!\n\nBefore: ${result.data.total_trades_before} trades\nAfter: ${result.data.total_trades_after} trades`);
        
        // Refresh the page to update all data
        window.location.reload();
      } else {
        throw new Error(result.message || 'Failed to clean trades');
      }
    } catch (error) {
      console.error('Error cleaning multi-day trades:', error);
      alert(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsCleaningTrades(false);
    }
  };

  const handleCleanDuplicateTrades = async () => {
    if (!window.confirm('This will permanently remove duplicate trades from the database. Are you sure?')) {
      return;
    }

    setIsCleaningTrades(true);
    setCleanupResult(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/data-ingestion/cleanup/duplicates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.status === 'success') {
        setCleanupResult(result.data);
        alert(`Successfully cleaned duplicate trades!\n\nProcessed: ${result.data.total_items} items\nRemoved: ${result.data.successful_items} duplicates\nFailed: ${result.data.failed_items} items`);
        
        // Refresh the page to update all data
        window.location.reload();
      } else {
        throw new Error(result.message || 'Failed to clean duplicates');
      }
    } catch (error) {
      console.error('Error cleaning duplicate trades:', error);
      alert(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsCleaningTrades(false);
    }
  };

  const currentMetrics = selectedAccount ? performanceMetrics[selectedAccount] : null;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Trading Optimization Dashboard</h1>
        <div className="account-selector">
          <label htmlFor="account-select">Account: </label>
          <select 
            id="account-select"
            value={availableAccounts.find(acc => acc.startsWith(selectedAccount || '')) || ''} 
            onChange={(e) => handleAccountChange(e.target.value)}
            className="account-select"
          >
            <option value="">Select Account ({availableAccounts.length} available)</option>
            {availableAccounts.map(account => (
              <option key={account} value={account}>{account}</option>
            ))}
          </select>
          <button 
            onClick={() => window.location.reload()} 
            style={{marginLeft: '10px', padding: '5px 10px', fontSize: '12px'}}
          >
            Refresh
          </button>
          <button 
            onClick={handleCleanMultidayTrades}
            style={{marginLeft: '10px', padding: '5px 10px', fontSize: '12px', backgroundColor: '#dc2626', color: 'white'}}
            disabled={isCleaningTrades}
          >
            {isCleaningTrades ? 'Cleaning...' : 'Clean Multi-Day Trades'}
          </button>
          <button 
            onClick={handleCleanDuplicateTrades}
            style={{marginLeft: '10px', padding: '5px 10px', fontSize: '12px', backgroundColor: '#dc2626', color: 'white'}}
            disabled={isCleaningTrades}
          >
            {isCleaningTrades ? 'Cleaning...' : 'Clean Duplicate Trades'}
          </button>
          <div style={{fontSize: '12px', color: '#666', marginTop: '5px'}}>
            Debug: {availableAccounts.length} accounts loaded | API working: {availableAccounts.length > 0 ? 'YES' : 'NO'}
          </div>
        </div>
      </div>

      {selectedAccount && (
        <>
          <div className="dashboard-main">
            <div className="dashboard-left">
              {/* Current Recommendation Card */}
              <div className="recommendation-section">
                <h3>Current Recommendation</h3>
                {isLoadingRecommendation ? (
                  <div className="loading-placeholder">Loading recommendation...</div>
                ) : currentRecommendation ? (
                  <div className="recommendation-card">
                    <div className="recommendation-header">
                      <span className="account-name">{currentRecommendation.account_name}</span>
                      <span className="symbol">{currentRecommendation.symbol}</span>
                      <span className={`action ${currentRecommendation.recommended_action.toLowerCase()}`}>
                        {currentRecommendation.recommended_action}
                      </span>
                    </div>
                    <div className="recommendation-metrics">
                      <div className="metric">
                        <span className="label">Confidence:</span>
                        <span className="value">{(currentRecommendation.confidence_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="metric">
                        <span className="label">Expected Return:</span>
                        <span className="value">${currentRecommendation.expected_return?.toFixed(2) || 'N/A'}</span>
                      </div>
                    </div>
                    <div className="recommendation-reasoning">
                      <p>{currentRecommendation.reasoning}</p>
                    </div>
                    {validationData && (
                      <div className="quick-validation">
                        <div className="validation-summary">
                          <span className={`validation-badge ${validationData.statistical_significance ? 'good' : 'bad'}`}>
                            {validationData.statistical_significance ? '✓ Statistically Valid' : '✗ Not Significant'}
                          </span>
                          <span className={`validation-badge ${validationData.robustness_score > 0.7 ? 'good' : 'warning'}`}>
                            Robustness: {(validationData.robustness_score * 100).toFixed(0)}%
                          </span>
                          <span className={`validation-badge ${validationData.market_neutrality ? 'good' : 'warning'}`}>
                            {validationData.market_neutrality ? '✓ Market Neutral' : '⚠ Market Dependent'}
                          </span>
                        </div>
                        <div className="validation-link">
                          <button 
                            className="validation-details-btn"
                            onClick={() => setActiveTab('validation')}
                          >
                            🔬 View Full Validation Analysis
                          </button>
                        </div>
                      </div>
                    )}
                    <button 
                      className="action-button"
                      onClick={() => handleRecommendationAction(currentRecommendation)}
                    >
                      Execute Recommendation
                    </button>
                  </div>
                ) : (
                  <div className="no-data">No current recommendation available</div>
                )}
              </div>
              
              {/* Performance Metrics */}
              <div className="performance-section">
                <h3>Performance Metrics</h3>
                {isLoadingMetrics ? (
                  <div className="loading-placeholder">Loading metrics...</div>
                ) : currentMetrics ? (
                  <div className="metrics-grid">
                    <div className="metric-card">
                      <span className="metric-label">Total Return</span>
                      <span className="metric-value">${currentMetrics.total_return?.toFixed(2) || '0.00'}</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-label">Win Rate</span>
                      <span className="metric-value">{(currentMetrics.win_rate * 100).toFixed(1)}%</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-label">Total Trades</span>
                      <span className="metric-value">{currentMetrics.total_trades}</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-label">Profit Factor</span>
                      <span className="metric-value">{currentMetrics.profit_factor?.toFixed(2) || 'N/A'}</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-label">Max Drawdown</span>
                      <span className="metric-value">{(currentMetrics.max_drawdown * 100).toFixed(1)}%</span>
                    </div>
                    <div className="metric-card">
                      <span className="metric-label">Sharpe Ratio</span>
                      <span className="metric-value">{currentMetrics.sharpe_ratio?.toFixed(2) || 'N/A'}</span>
                    </div>
                  </div>
                ) : (
                  <div className="no-data">No performance data available</div>
                )}
              </div>
            </div>

            <div className="dashboard-right">
              <div className="tab-navigation">
                <button 
                  className={`tab-button ${activeTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('overview')}
                >
                  Overview
                </button>
                <button 
                  className={`tab-button ${activeTab === 'validation' ? 'active' : ''}`}
                  onClick={() => setActiveTab('validation')}
                >
                  🔬 Validation Analytics
                </button>
                <button 
                  className={`tab-button ${activeTab === 'temporal' ? 'active' : ''}`}
                  onClick={() => setActiveTab('temporal')}
                >
                  Temporal Analysis
                </button>
                <button 
                  className={`tab-button ${activeTab === 'monte-carlo' ? 'active' : ''}`}
                  onClick={() => setActiveTab('monte-carlo')}
                >
                  Monte Carlo
                </button>
              </div>

              <div className="tab-content">
                {activeTab === 'overview' && (
                  <div className="overview-tab">
                    <div className="recent-trades-section">
                      <h3>Recent Trades</h3>
                      {isLoadingTrades ? (
                        <div className="loading-placeholder">Loading trades...</div>
                      ) : recentTrades.length > 0 ? (
                        <div className="trades-list">
                          {recentTrades.map((trade, index) => (
                            <div key={trade.trade_id || index} className="trade-item">
                              <div className="trade-header">
                                <span className="trade-symbol">{trade.symbol}</span>
                                <span className={`trade-pnl ${trade.profit_loss >= 0 ? 'positive' : 'negative'}`}>
                                  ${trade.profit_loss?.toFixed(2) || '0.00'}
                                </span>
                              </div>
                              <div className="trade-details">
                                <span className="trade-side">{trade.side}</span>
                                <span className="trade-quantity">{trade.quantity} contracts</span>
                                <span className="trade-time">
                                  {trade.entry_time ? new Date(trade.entry_time).toLocaleDateString() : 'N/A'}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="no-data">No recent trades found</div>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === 'validation' && (
                  <div className="validation-tab">
                    <h3>🔬 Validation Analytics - Can You Trust This Strategy?</h3>
                    {isLoadingValidation ? (
                      <div className="loading-placeholder">Loading validation analytics...</div>
                    ) : validationData ? (
                      <div className="validation-dashboard">
                        {/* Trust Score Overview */}
                        <div className="trust-score-section">
                          <div className="trust-score-card">
                            <h4>Overall Trust Score</h4>
                            <div className={`trust-score ${validationData.confidence.toLowerCase()}`}>
                              {validationData.confidence}
                            </div>
                            <div className="trust-indicators">
                              <span className={`indicator ${validationData.statistical_significance ? 'good' : 'bad'}`}>
                                {validationData.statistical_significance ? '✓' : '✗'} Statistical Significance
                              </span>
                              <span className={`indicator ${validationData.robustness_score > 0.7 ? 'good' : 'bad'}`}>
                                {validationData.robustness_score > 0.7 ? '✓' : '✗'} Robust Performance
                              </span>
                              <span className={`indicator ${validationData.market_neutrality ? 'good' : 'warning'}`}>
                                {validationData.market_neutrality ? '✓' : '⚠'} Market Independence
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Statistical Validation */}
                        <div className="validation-section">
                          <h4>📊 Statistical Validation</h4>
                          <div className="validation-metrics">
                            <div className="metric-card">
                              <span className="metric-label">P-Value</span>
                              <span className={`metric-value ${validationData.p_value < 0.05 ? 'good' : 'bad'}`}>
                                {validationData.p_value.toFixed(4)}
                              </span>
                              <span className="metric-help">
                                {validationData.p_value < 0.05 ? 'Statistically significant' : 'Not significant'}
                              </span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Sample Size</span>
                              <span className={`metric-value ${validationData.sample_size > 100 ? 'good' : 'warning'}`}>
                                {validationData.sample_size}
                              </span>
                              <span className="metric-help">
                                {validationData.sample_size > 100 ? 'Sufficient data' : 'Limited data'}
                              </span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Confidence Interval</span>
                              <span className="metric-value">
                                [{validationData.confidence_interval[0].toFixed(3)}, {validationData.confidence_interval[1].toFixed(3)}]
                              </span>
                              <span className="metric-help">95% confidence range</span>
                            </div>
                          </div>
                        </div>

                        {/* Monte Carlo Risk Analysis */}
                        <div className="validation-section">
                          <h4>🎲 Monte Carlo Risk Analysis</h4>
                          <div className="validation-metrics">
                            <div className="metric-card">
                              <span className="metric-label">Value at Risk (95%)</span>
                              <span className={`metric-value ${validationData.var_95 > -0.2 ? 'good' : 'bad'}`}>
                                {(validationData.var_95 * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">Maximum expected loss</span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Expected Shortfall</span>
                              <span className={`metric-value ${validationData.expected_shortfall > -0.3 ? 'good' : 'bad'}`}>
                                {(validationData.expected_shortfall * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">Average loss in worst 5%</span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Worst Case Scenario</span>
                              <span className="metric-value bad">
                                {(validationData.worst_case_scenario * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">Extreme downside risk</span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Best Case Scenario</span>
                              <span className="metric-value good">
                                {(validationData.best_case_scenario * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">Maximum upside potential</span>
                            </div>
                          </div>
                        </div>

                        {/* Walk-Forward Validation */}
                        <div className="validation-section">
                          <h4>🚶 Walk-Forward Validation</h4>
                          <div className="validation-metrics">
                            <div className="metric-card">
                              <span className="metric-label">Out-of-Sample Performance</span>
                              <span className={`metric-value ${validationData.out_of_sample_performance > 0 ? 'good' : 'bad'}`}>
                                {(validationData.out_of_sample_performance * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">Performance on unseen data</span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Robustness Score</span>
                              <span className={`metric-value ${validationData.robustness_score > 0.7 ? 'good' : validationData.robustness_score > 0.5 ? 'warning' : 'bad'}`}>
                                {(validationData.robustness_score * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">
                                {validationData.robustness_score > 0.7 ? 'Highly robust' : validationData.robustness_score > 0.5 ? 'Moderately robust' : 'Not robust'}
                              </span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Performance Decay Rate</span>
                              <span className={`metric-value ${validationData.performance_decay_rate < 0.1 ? 'good' : 'warning'}`}>
                                {(validationData.performance_decay_rate * 100).toFixed(1)}%
                              </span>
                              <span className="metric-help">
                                {validationData.performance_decay_rate < 0.1 ? 'Stable over time' : 'Performance degrading'}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Market Correlation Analysis */}
                        <div className="validation-section">
                          <h4>📈 Market Correlation Analysis</h4>
                          <div className="validation-metrics">
                            <div className="metric-card">
                              <span className="metric-label">Market Correlation</span>
                              <span className={`metric-value ${Math.abs(validationData.market_correlation) < 0.3 ? 'good' : 'warning'}`}>
                                {validationData.market_correlation.toFixed(3)}
                              </span>
                              <span className="metric-help">
                                {Math.abs(validationData.market_correlation) < 0.3 ? 'Market neutral' : 'Market dependent'}
                              </span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Beta Coefficient</span>
                              <span className={`metric-value ${Math.abs(validationData.beta_coefficient) < 0.5 ? 'good' : 'warning'}`}>
                                {validationData.beta_coefficient.toFixed(3)}
                              </span>
                              <span className="metric-help">Market sensitivity</span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Alpha Generation</span>
                              <span className={`metric-value ${validationData.alpha_generation > 0 ? 'good' : 'bad'}`}>
                                {(validationData.alpha_generation * 100).toFixed(2)}%
                              </span>
                              <span className="metric-help">
                                {validationData.alpha_generation > 0 ? 'Generating alpha' : 'No alpha generation'}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* VIX Regime Analysis */}
                        <div className="validation-section">
                          <h4>📊 VIX Regime Analysis</h4>
                          <div className="validation-metrics">
                            <div className="metric-card">
                              <span className="metric-label">Current VIX Regime</span>
                              <span className={`metric-value ${validationData.current_vix_regime.toLowerCase()}`}>
                                {validationData.current_vix_regime}
                              </span>
                              <span className="metric-help">Current market volatility</span>
                            </div>
                            <div className="metric-card">
                              <span className="metric-label">Best Regime</span>
                              <span className="metric-value">
                                {validationData.regime_preference}
                              </span>
                              <span className="metric-help">Optimal volatility environment</span>
                            </div>
                            <div className="regime-performance">
                              <span className="metric-label">Performance by Regime:</span>
                              <div className="regime-bars">
                                {Object.entries(validationData.regime_performance).map(([regime, performance]: [string, any]) => (
                                  <div key={regime} className="regime-bar">
                                    <span className="regime-name">{regime}</span>
                                    <div className="performance-bar">
                                      <div 
                                        className={`bar-fill ${performance > 0 ? 'positive' : 'negative'}`}
                                        style={{width: `${Math.abs(performance) * 100}%`}}
                                      ></div>
                                    </div>
                                    <span className={`performance-value ${performance > 0 ? 'positive' : 'negative'}`}>
                                      {(performance * 100).toFixed(1)}%
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Alerts and Recommendations */}
                        <div className="validation-section">
                          <h4>⚠️ Alerts & Recommendations</h4>
                          <div className="alerts-section">
                            {validationData.alerts?.length > 0 && (
                              <div className="alerts">
                                <h5>Alerts:</h5>
                                {validationData.alerts.map((alert: string, index: number) => (
                                  <div key={index} className="alert-item warning">
                                    ⚠️ {alert}
                                  </div>
                                ))}
                              </div>
                            )}
                            {validationData.recommendations?.length > 0 && (
                              <div className="recommendations">
                                <h5>Recommendations:</h5>
                                {validationData.recommendations.map((rec: string, index: number) => (
                                  <div key={index} className="recommendation-item">
                                    💡 {rec}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="reasoning-section">
                            <h5>Analysis Reasoning:</h5>
                            <p className="reasoning-text">{validationData.reasoning}</p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="no-data">
                        <h4>No Validation Data Available</h4>
                        <p>Advanced analytics validation requires:</p>
                        <ul>
                          <li>Sufficient historical trade data (100+ trades recommended)</li>
                          <li>Market data synchronization (SPY/QQQ/VIX)</li>
                          <li>Statistical significance in performance</li>
                        </ul>
                        <button 
                          onClick={() => fetchValidationData(selectedAccount)}
                          style={{marginTop: '10px', padding: '8px 16px'}}
                        >
                          Retry Validation Analysis
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'temporal' && (
                  <div className="temporal-tab">
                    <div className="chart-placeholder">
                      <h4>Temporal Analysis</h4>
                      <p>Temporal analysis charts will be displayed here.</p>
                      <p>Account: {selectedAccount}</p>
                    </div>
                  </div>
                )}

                {activeTab === 'monte-carlo' && (
                  <div className="monte-carlo-tab">
                    <div className="chart-placeholder">
                      <h4>Monte Carlo Simulation</h4>
                      <p>Monte Carlo simulation results will be displayed here.</p>
                      <p>Account: {selectedAccount}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {!selectedAccount && (
        <div className="no-account-selected">
          <div className="placeholder-content">
            <h2>Select an Account</h2>
            <p>Choose an account from the dropdown above to view dashboard data.</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;