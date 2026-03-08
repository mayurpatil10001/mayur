import React, { useEffect, useState } from 'react';

interface Account {
  name: string;
  symbol: string;
  total_trades: number;
  first_trade_date: string;
  last_trade_date: string;
  total_pnl: number;
  best_day_of_week: number | null;
  best_hour_of_day: number | null;
  is_active: boolean;
}

const SimpleDashboard: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAccount, setSelectedAccount] = useState<string>('');
  const [validationData, setValidationData] = useState<any>(null);
  const [isLoadingValidation, setIsLoadingValidation] = useState(false);
  const [showValidation, setShowValidation] = useState(false);

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        console.log('🚀 Fetching accounts...');
        setLoading(true);
        setError(null);

        const response = await fetch('http://localhost:8000/api/v1/accounts/?size=1000');
        console.log('📡 Response status:', response.status);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('📊 Response data:', data);

        if (data.status === 'success' && data.data?.items) {
          setAccounts(data.data.items);
          console.log('✅ Loaded', data.data.items.length, 'accounts');
        } else {
          throw new Error('Invalid response format');
        }
      } catch (err) {
        console.error('❌ Error:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchAccounts();
  }, []);

  const handleAccountChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedAccount(event.target.value);
    console.log('🎯 Selected account:', event.target.value);

    // Fetch validation data when account is selected
    if (event.target.value) {
      fetchValidationData(event.target.value);
    }
  };

  const fetchValidationData = async (accountName: string) => {
    setIsLoadingValidation(true);
    try {
      console.log('🔬 Fetching validation data for:', accountName);
      const response = await fetch(`http://localhost:8000/api/v1/recommendations/advanced?account_name=${accountName}&min_confidence=0.0`);
      if (response.ok) {
        const data = await response.json();
        console.log('📊 Validation data:', data);
        if (data.status === 'success' && data.data?.length > 0) {
          setValidationData(data.data[0]);
          console.log('✅ Validation data loaded');
        } else {
          console.log('⚠️ No validation data available');
          setValidationData(null);
        }
      } else {
        console.log('❌ Failed to fetch validation data:', response.status);
        setValidationData(null);
      }
    } catch (error) {
      console.error('❌ Error fetching validation data:', error);
      setValidationData(null);
    } finally {
      setIsLoadingValidation(false);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>🚀 Simple Trading Dashboard</h1>

      <div style={{ marginBottom: '20px' }}>
        <h3>Status</h3>
        {loading && <p style={{ color: 'blue' }}>⏳ Loading accounts...</p>}
        {error && <p style={{ color: 'red' }}>❌ Error: {error}</p>}
        {!loading && !error && (
          <p style={{ color: 'green' }}>✅ Loaded {accounts.length} accounts</p>
        )}
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="account-select" style={{ display: 'block', marginBottom: '10px' }}>
          <strong>Select Account:</strong>
        </label>
        <select
          id="account-select"
          value={selectedAccount}
          onChange={handleAccountChange}
          style={{ padding: '8px', minWidth: '400px', fontSize: '14px' }}
        >
          <option value="">Choose an account ({accounts.length} available)</option>
          {accounts.map((account, index) => (
            <option key={`${account.name}-${account.symbol}`} value={account.name}>
              {account.name} ({account.symbol}) - {account.total_trades.toLocaleString()} trades
            </option>
          ))}
        </select>
      </div>

      {selectedAccount && (
        <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f5f5f5', borderRadius: '5px' }}>
          <h3>Selected Account Details</h3>
          {(() => {
            const account = accounts.find(a => a.name === selectedAccount);
            if (!account) return <p>Account not found</p>;

            return (
              <div>
                <p><strong>Name:</strong> {account.name}</p>
                <p><strong>Symbol:</strong> {account.symbol}</p>
                <p><strong>Total Trades:</strong> {account.total_trades.toLocaleString()}</p>
                <p><strong>First Trade:</strong> {new Date(account.first_trade_date).toLocaleDateString()}</p>
                <p><strong>Last Trade:</strong> {new Date(account.last_trade_date).toLocaleDateString()}</p>
                <p><strong>Status:</strong> {account.is_active ? '✅ Active' : '❌ Inactive'}</p>
              </div>
            );
          })()}
        </div>
      )}

      {selectedAccount && (
        <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#e8f4fd', borderRadius: '5px', border: '2px solid #3498db' }}>
          <div style={{ marginBottom: '15px', color: '#444', fontSize: '14px', lineHeight: '1.4' }}>
            <p><strong>What is this?</strong> This is an advanced AI-driven validation engine. It analyzes your historical performance for this specific account to determine if your trading strategy is <em>statistically significant</em> and <em>robust</em> enough to be trusted right now.</p>
            <p>It performs Monte Carlo simulations, calculates P-values, and checks market correlation to ensure your wins aren't just luck.</p>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
            <h3 style={{ margin: 0, color: '#2c3e50' }}>🔬 Validation Analytics - Can You Trust This Strategy?</h3>
            <button
              onClick={() => setShowValidation(!showValidation)}
              style={{
                padding: '8px 16px',
                backgroundColor: showValidation ? '#e74c3c' : '#3498db',
                color: 'white',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              {showValidation ? 'Hide' : 'Show'} Validation Details
            </button>
          </div>

          {isLoadingValidation && (
            <p style={{ color: '#3498db', fontStyle: 'italic' }}>⏳ Loading validation analytics...</p>
          )}

          {!isLoadingValidation && !validationData && (
            <div style={{ padding: '20px', backgroundColor: '#fff3cd', borderRadius: '5px', border: '1px solid #ffeaa7' }}>
              <h4 style={{ color: '#856404', margin: '0 0 10px 0' }}>⚠️ No Validation Found for Current Context</h4>
              <p style={{ margin: '0 0 10px 0', color: '#856404' }}>
                The AI engine only validates strategies that meet strict safety criteria. Validation may be missing if:
              </p>
              <ul style={{ color: '#856404', margin: '0 0 15px 20px' }}>
                <li><strong>Current Time Window:</strong> There might not be enough historical trades for this specific hour/minute bin.</li>
                <li><strong>Statistical Significance:</strong> The performance in this window doesn't pass the P-value test (i.e., it might be random luck).</li>
                <li><strong>System Load:</strong> Market data (SPY/VIX) might still be indexing for this account.</li>
                <li><strong>Off-Hours:</strong> If you are viewing this outside of active trading hours, the "Current Time" validation might return no results.</li>
              </ul>
              <button
                onClick={() => fetchValidationData(selectedAccount)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#f39c12',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer'
                }}
              >
                🔄 Retry Validation Analysis
              </button>
            </div>
          )}

          {!isLoadingValidation && validationData && (
            <div>
              {/* Quick Trust Indicators */}
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '15px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  backgroundColor: validationData.statistical_significance ? '#d4edda' : '#f8d7da',
                  color: validationData.statistical_significance ? '#155724' : '#721c24'
                }}>
                  {validationData.statistical_significance ? '✅ Statistically Valid' : '❌ Not Significant'}
                </span>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '15px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  backgroundColor: validationData.robustness_score > 0.7 ? '#d4edda' : validationData.robustness_score > 0.5 ? '#fff3cd' : '#f8d7da',
                  color: validationData.robustness_score > 0.7 ? '#155724' : validationData.robustness_score > 0.5 ? '#856404' : '#721c24'
                }}>
                  🏗️ Robustness: {(validationData.robustness_score * 100).toFixed(0)}%
                </span>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '15px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  backgroundColor: validationData.market_neutrality ? '#d4edda' : '#fff3cd',
                  color: validationData.market_neutrality ? '#155724' : '#856404'
                }}>
                  {validationData.market_neutrality ? '✅ Market Neutral' : '⚠️ Market Dependent'}
                </span>
                <span style={{
                  padding: '6px 12px',
                  borderRadius: '15px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  backgroundColor: validationData.confidence === 'VERY_HIGH' ? '#27ae60' :
                    validationData.confidence === 'HIGH' ? '#2ecc71' :
                      validationData.confidence === 'MEDIUM' ? '#f39c12' :
                        validationData.confidence === 'LOW' ? '#e67e22' : '#e74c3c',
                  color: 'white'
                }}>
                  🎯 Confidence: {validationData.confidence}
                </span>
              </div>

              {/* Key Risk Metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', marginBottom: '15px' }}>
                <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '5px', border: '1px solid #ddd' }}>
                  <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold' }}>📉 MAX RISK (VaR 95%)</div>
                  <div style={{ fontSize: '18px', fontWeight: 'bold', color: validationData.var_95 > -0.2 ? '#27ae60' : '#e74c3c' }}>
                    {(validationData.var_95 * 100).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: '10px', color: '#666' }}>Maximum expected loss</div>
                </div>
                <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '5px', border: '1px solid #ddd' }}>
                  <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold' }}>📊 P-VALUE</div>
                  <div style={{ fontSize: '18px', fontWeight: 'bold', color: validationData.p_value < 0.05 ? '#27ae60' : '#e74c3c' }}>
                    {validationData.p_value.toFixed(4)}
                  </div>
                  <div style={{ fontSize: '10px', color: '#666' }}>
                    {validationData.p_value < 0.05 ? 'Statistically significant' : 'Not significant'}
                  </div>
                </div>
                <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '5px', border: '1px solid #ddd' }}>
                  <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold' }}>🎲 SAMPLE SIZE</div>
                  <div style={{ fontSize: '18px', fontWeight: 'bold', color: validationData.sample_size > 100 ? '#27ae60' : '#f39c12' }}>
                    {validationData.sample_size}
                  </div>
                  <div style={{ fontSize: '10px', color: '#666' }}>
                    {validationData.sample_size > 100 ? 'Sufficient data' : 'Limited data'}
                  </div>
                </div>
                <div style={{ padding: '10px', backgroundColor: 'white', borderRadius: '5px', border: '1px solid #ddd' }}>
                  <div style={{ fontSize: '12px', color: '#666', fontWeight: 'bold' }}>📈 OUT-OF-SAMPLE</div>
                  <div style={{ fontSize: '18px', fontWeight: 'bold', color: validationData.out_of_sample_performance > 0 ? '#27ae60' : '#e74c3c' }}>
                    {(validationData.out_of_sample_performance * 100).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: '10px', color: '#666' }}>Performance on unseen data</div>
                </div>
              </div>

              {showValidation && (
                <div style={{ marginTop: '20px', padding: '15px', backgroundColor: 'white', borderRadius: '5px', border: '1px solid #ddd' }}>
                  <h4 style={{ margin: '0 0 15px 0', color: '#2c3e50' }}>📋 Detailed Validation Results</h4>

                  <div style={{ marginBottom: '15px' }}>
                    <h5 style={{ margin: '0 0 8px 0', color: '#34495e' }}>🎲 Monte Carlo Risk Analysis</h5>
                    <div style={{ fontSize: '14px', lineHeight: '1.5' }}>
                      <p><strong>Expected Shortfall:</strong> <span style={{ color: validationData.expected_shortfall > -0.3 ? '#27ae60' : '#e74c3c' }}>{(validationData.expected_shortfall * 100).toFixed(1)}%</span> (avg loss in worst 5%)</p>
                      <p><strong>Worst Case:</strong> <span style={{ color: '#e74c3c' }}>{(validationData.worst_case_scenario * 100).toFixed(1)}%</span> | <strong>Best Case:</strong> <span style={{ color: '#27ae60' }}>{(validationData.best_case_scenario * 100).toFixed(1)}%</span></p>
                    </div>
                  </div>

                  <div style={{ marginBottom: '15px' }}>
                    <h5 style={{ margin: '0 0 8px 0', color: '#34495e' }}>📈 Market Correlation</h5>
                    <div style={{ fontSize: '14px', lineHeight: '1.5' }}>
                      <p><strong>Market Correlation:</strong> <span style={{ color: Math.abs(validationData.market_correlation) < 0.3 ? '#27ae60' : '#f39c12' }}>{validationData.market_correlation.toFixed(3)}</span> ({Math.abs(validationData.market_correlation) < 0.3 ? 'Market neutral' : 'Market dependent'})</p>
                      <p><strong>Beta Coefficient:</strong> {validationData.beta_coefficient.toFixed(3)} | <strong>Alpha Generation:</strong> <span style={{ color: validationData.alpha_generation > 0 ? '#27ae60' : '#e74c3c' }}>{(validationData.alpha_generation * 100).toFixed(2)}%</span></p>
                    </div>
                  </div>

                  <div style={{ marginBottom: '15px' }}>
                    <h5 style={{ margin: '0 0 8px 0', color: '#34495e' }}>📊 VIX Regime Analysis</h5>
                    <div style={{ fontSize: '14px', lineHeight: '1.5' }}>
                      <p><strong>Current VIX Regime:</strong> <span style={{
                        color: validationData.current_vix_regime === 'Low' ? '#27ae60' :
                          validationData.current_vix_regime === 'Medium' ? '#f39c12' : '#e74c3c'
                      }}>{validationData.current_vix_regime}</span></p>
                      <p><strong>Best Regime:</strong> {validationData.regime_preference}</p>
                      <div style={{ marginTop: '8px' }}>
                        <strong>Performance by Regime:</strong>
                        {Object.entries(validationData.regime_performance).map(([regime, performance]: [string, any]) => (
                          <div key={regime} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                            <span style={{ minWidth: '60px', fontSize: '12px' }}>{regime}:</span>
                            <div style={{
                              flex: 1,
                              height: '16px',
                              backgroundColor: '#e9ecef',
                              borderRadius: '8px',
                              overflow: 'hidden',
                              position: 'relative'
                            }}>
                              <div style={{
                                height: '100%',
                                width: `${Math.abs(performance) * 100}%`,
                                backgroundColor: performance > 0 ? '#27ae60' : '#e74c3c',
                                borderRadius: '8px'
                              }}></div>
                            </div>
                            <span style={{
                              minWidth: '50px',
                              fontSize: '12px',
                              fontWeight: 'bold',
                              color: performance > 0 ? '#27ae60' : '#e74c3c'
                            }}>
                              {(performance * 100).toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {validationData.alerts?.length > 0 && (
                    <div style={{ marginBottom: '15px' }}>
                      <h5 style={{ margin: '0 0 8px 0', color: '#34495e' }}>⚠️ Alerts</h5>
                      {validationData.alerts.map((alert: string, index: number) => (
                        <div key={index} style={{
                          padding: '8px 12px',
                          backgroundColor: '#fff3cd',
                          border: '1px solid #ffeaa7',
                          borderRadius: '4px',
                          marginBottom: '5px',
                          fontSize: '14px',
                          color: '#856404'
                        }}>
                          ⚠️ {alert}
                        </div>
                      ))}
                    </div>
                  )}

                  {validationData.recommendations?.length > 0 && (
                    <div style={{ marginBottom: '15px' }}>
                      <h5 style={{ margin: '0 0 8px 0', color: '#34495e' }}>💡 Recommendations</h5>
                      {validationData.recommendations.map((rec: string, index: number) => (
                        <div key={index} style={{
                          padding: '8px 12px',
                          backgroundColor: '#d1ecf1',
                          border: '1px solid #bee5eb',
                          borderRadius: '4px',
                          marginBottom: '5px',
                          fontSize: '14px',
                          color: '#0c5460'
                        }}>
                          💡 {rec}
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ marginTop: '15px', padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '4px', borderLeft: '4px solid #6c757d' }}>
                    <h5 style={{ margin: '0 0 8px 0', color: '#34495e' }}>🧠 Analysis Reasoning</h5>
                    <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.5', color: '#495057' }}>
                      {validationData.reasoning}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: '30px', fontSize: '12px', color: '#666' }}>
        <h4>Debug Info</h4>
        <p>Accounts loaded: {accounts.length}</p>
        <p>Loading: {loading ? 'Yes' : 'No'}</p>
        <p>Error: {error || 'None'}</p>
        <p>Selected: {selectedAccount || 'None'}</p>
      </div>
    </div>
  );
};

export default SimpleDashboard;