import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import './MarketCorrelationDashboard.css';

// Data Interfaces
interface CorrelationData {
  time_bin: string;
  account: string;
  hour: number;
  minute_bin: number;
  spy_correlation: number;
  qqq_correlation: number;
  vix_correlation: number;
  beta_spy: number;
  beta_qqq: number;
  alpha_spy: number;
  alpha_qqq: number;
  r_squared_spy: number;
  r_squared_qqq: number;
  correlation_stability: number;
  sample_size: number;
  statistical_significance: boolean;
}

interface RollingCorrelationPoint {
  date: string;
  spy_correlation: number;
  qqq_correlation: number;
  vix_correlation: number;
  vix_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  stability_score: number;
  confidence_interval_lower: number;
  confidence_interval_upper: number;
}

interface BetaAnalysisData {
  account: string;
  time_bin: string;
  returns: number[];
  spy_returns: number[];
  qqq_returns: number[];
  beta_spy: number;
  beta_qqq: number;
  alpha_spy: number;
  alpha_qqq: number;
  r_squared_spy: number;
  r_squared_qqq: number;
  tracking_error_spy: number;
  tracking_error_qqq: number;
  information_ratio_spy: number;
  information_ratio_qqq: number;
}

interface CorrelationStabilityMetrics {
  time_bin: string;
  rolling_correlation_volatility: number;
  correlation_trend_slope: number;
  stability_score: number;
  regime_specific_correlations: {
    low_vix: { spy: number; qqq: number; count: number };
    medium_vix: { spy: number; qqq: number; count: number };
    high_vix: { spy: number; qqq: number; count: number };
  };
  consistency_rating: 'HIGHLY_STABLE' | 'STABLE' | 'MODERATE' | 'UNSTABLE' | 'HIGHLY_UNSTABLE';
}

// Component Props
interface MarketCorrelationDashboardProps {
  accountName: string;
  startDate?: string;
  endDate?: string;
  selectedTimeBins?: string[];
  showHeatmap?: boolean;
  showRollingCorrelations?: boolean;
  showBetaAnalysis?: boolean;
  showStabilityMetrics?: boolean;
  rollingWindowDays?: number;
  height?: number;
  onTimeBinSelect?: (timeBin: string) => void;
  onCorrelationClick?: (correlation: CorrelationData) => void;
}

const MarketCorrelationDashboard: React.FC<MarketCorrelationDashboardProps> = ({
  accountName,
  startDate,
  endDate,
  selectedTimeBins = [],
  showHeatmap = true,
  showRollingCorrelations = true,
  showBetaAnalysis = true,
  showStabilityMetrics = true,
  rollingWindowDays = 30,
  height = 800,
  onTimeBinSelect,
  onCorrelationClick
}) => {
  // State management
  const [correlationData, setCorrelationData] = useState<CorrelationData[]>([]);
  const [rollingCorrelations, setRollingCorrelations] = useState<RollingCorrelationPoint[]>([]);
  const [betaAnalysis, setBetaAnalysis] = useState<BetaAnalysisData[]>([]);
  const [stabilityMetrics, setStabilityMetrics] = useState<CorrelationStabilityMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMarketIndex, setSelectedMarketIndex] = useState<'SPY' | 'QQQ'>('SPY');
  const [correlationThreshold, setCorrelationThreshold] = useState<number>(0.1);
  const [showOnlySignificant, setShowOnlySignificant] = useState<boolean>(false);

  // Data fetching functions
  const fetchCorrelationData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (selectedTimeBins.length) params.append('time_bins', selectedTimeBins.join(','));
      
      const response = await fetch(
        `/api/market-correlation/heatmap/${accountName}?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (!response.ok) throw new Error('Failed to fetch correlation data');
      
      const data = await response.json();
      setCorrelationData(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load correlation data');
    }
  }, [accountName, startDate, endDate, selectedTimeBins]);

  const fetchRollingCorrelations = useCallback(async () => {
    if (!showRollingCorrelations) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('window_days', rollingWindowDays.toString());
      
      const response = await fetch(
        `/api/market-correlation/rolling/${accountName}?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setRollingCorrelations(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch rolling correlations:', err);
    }
  }, [accountName, startDate, endDate, showRollingCorrelations, rollingWindowDays]);

  const fetchBetaAnalysis = useCallback(async () => {
    if (!showBetaAnalysis) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/market-correlation/beta-analysis/${accountName}?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setBetaAnalysis(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch beta analysis:', err);
    }
  }, [accountName, startDate, endDate, showBetaAnalysis]);

  const fetchStabilityMetrics = useCallback(async () => {
    if (!showStabilityMetrics) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/market-correlation/stability/${accountName}?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setStabilityMetrics(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch stability metrics:', err);
    }
  }, [accountName, startDate, endDate, showStabilityMetrics]);

  // Load data on mount and prop changes
  useEffect(() => {
    fetchCorrelationData();
  }, [fetchCorrelationData]);

  useEffect(() => {
    fetchRollingCorrelations();
  }, [fetchRollingCorrelations]);

  useEffect(() => {
    fetchBetaAnalysis();
  }, [fetchBetaAnalysis]);

  useEffect(() => {
    fetchStabilityMetrics();
  }, [fetchStabilityMetrics]);

  // Correlation heatmap data preparation
  const heatmapData = useMemo(() => {
    if (!correlationData.length || !showHeatmap) return null;
    
    const filteredData = correlationData.filter(d => 
      (!showOnlySignificant || d.statistical_significance) &&
      Math.abs(selectedMarketIndex === 'SPY' ? d.spy_correlation : d.qqq_correlation) >= correlationThreshold
    );
    
    if (!filteredData.length) return null;
    
    // Create time-bin labels
    const timeBins = Array.from(new Set(filteredData.map(d => `${d.hour}:${d.minute_bin.toString().padStart(2, '0')}`)));
    
    // Prepare correlation matrix
    const correlationValues = timeBins.map(timeBin => {
      const data = filteredData.find(d => `${d.hour}:${d.minute_bin.toString().padStart(2, '0')}` === timeBin);
      return data ? (selectedMarketIndex === 'SPY' ? data.spy_correlation : data.qqq_correlation) : 0;
    });
    
    // Prepare beta values for secondary heatmap
    const betaValues = timeBins.map(timeBin => {
      const data = filteredData.find(d => `${d.hour}:${d.minute_bin.toString().padStart(2, '0')}` === timeBin);
      return data ? (selectedMarketIndex === 'SPY' ? data.beta_spy : data.beta_qqq) : 0;
    });
    
    // Prepare hover text
    const hoverText = timeBins.map(timeBin => {
      const data = filteredData.find(d => `${d.hour}:${d.minute_bin.toString().padStart(2, '0')}` === timeBin);
      if (!data) return '';
      
      const correlation = selectedMarketIndex === 'SPY' ? data.spy_correlation : data.qqq_correlation;
      const beta = selectedMarketIndex === 'SPY' ? data.beta_spy : data.beta_qqq;
      const alpha = selectedMarketIndex === 'SPY' ? data.alpha_spy : data.alpha_qqq;
      const rSquared = selectedMarketIndex === 'SPY' ? data.r_squared_spy : data.r_squared_qqq;
      
      return `Time-Bin: ${timeBin}<br>` +
             `${selectedMarketIndex} Correlation: ${correlation.toFixed(3)}<br>` +
             `Beta: ${beta.toFixed(3)}<br>` +
             `Alpha: ${alpha.toFixed(3)}<br>` +
             `R²: ${rSquared.toFixed(3)}<br>` +
             `Stability: ${data.correlation_stability.toFixed(3)}<br>` +
             `Sample Size: ${data.sample_size}<br>` +
             `Significant: ${data.statistical_significance ? 'Yes' : 'No'}`;
    });
    
    return {
      timeBins,
      correlationValues,
      betaValues,
      hoverText,
      filteredData
    };
  }, [correlationData, selectedMarketIndex, correlationThreshold, showOnlySignificant, showHeatmap]);

  // Rolling correlation chart data
  const rollingCorrelationChartData = useMemo(() => {
    if (!rollingCorrelations.length || !showRollingCorrelations) return [];
    
    const traces: any[] = [];
    const dates = rollingCorrelations.map(r => r.date);
    
    // Main correlation trace
    const correlationValues = rollingCorrelations.map(r => 
      selectedMarketIndex === 'SPY' ? r.spy_correlation : r.qqq_correlation
    );
    
    traces.push({
      x: dates,
      y: correlationValues,
      type: 'scatter',
      mode: 'lines',
      name: `${selectedMarketIndex} Correlation`,
      line: { color: '#3b82f6', width: 2 },
      hovertemplate: '<b>%{fullData.name}</b><br>' +
                    'Date: %{x}<br>' +
                    'Correlation: %{y:.3f}<br>' +
                    '<extra></extra>'
    });
    
    // Confidence intervals
    const upperBound = rollingCorrelations.map(r => r.confidence_interval_upper);
    const lowerBound = rollingCorrelations.map(r => r.confidence_interval_lower);
    
    traces.push({
      x: [...dates, ...dates.reverse()],
      y: [...upperBound, ...lowerBound.reverse()],
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      name: '95% Confidence Interval',
      line: { color: 'rgba(59, 130, 246, 0.3)' },
      fillcolor: 'rgba(59, 130, 246, 0.1)',
      hoverinfo: 'skip'
    });
    
    // VIX regime markers
    const vixRegimeColors = {
      'LOW': '#10b981',
      'MEDIUM': '#f59e0b',
      'HIGH': '#ef4444'
    };
    
    const regimeGroups = rollingCorrelations.reduce((groups, point) => {
      if (!groups[point.vix_regime]) groups[point.vix_regime] = [];
      groups[point.vix_regime].push(point);
      return groups;
    }, {} as Record<string, RollingCorrelationPoint[]>);
    
    Object.entries(regimeGroups).forEach(([regime, points]) => {
      traces.push({
        x: points.map(p => p.date),
        y: points.map(p => selectedMarketIndex === 'SPY' ? p.spy_correlation : p.qqq_correlation),
        type: 'scatter',
        mode: 'markers',
        name: `VIX ${regime}`,
        marker: {
          color: vixRegimeColors[regime as keyof typeof vixRegimeColors],
          size: 6,
          symbol: 'circle',
          line: { color: 'white', width: 1 }
        },
        hovertemplate: '<b>VIX %{fullData.name}</b><br>' +
                      'Date: %{x}<br>' +
                      'Correlation: %{y:.3f}<br>' +
                      'Stability: %{text}<br>' +
                      '<extra></extra>',
        text: points.map(p => p.stability_score.toFixed(3))
      });
    });
    
    return traces;
  }, [rollingCorrelations, selectedMarketIndex, showRollingCorrelations]);

  // Beta scatter plot data
  const betaScatterData = useMemo(() => {
    if (!betaAnalysis.length || !showBetaAnalysis) return [];
    
    const traces: any[] = [];
    
    betaAnalysis.forEach((analysis, index) => {
      const marketReturns = selectedMarketIndex === 'SPY' ? analysis.spy_returns : analysis.qqq_returns;
      const beta = selectedMarketIndex === 'SPY' ? analysis.beta_spy : analysis.beta_qqq;
      const alpha = selectedMarketIndex === 'SPY' ? analysis.alpha_spy : analysis.alpha_qqq;
      const rSquared = selectedMarketIndex === 'SPY' ? analysis.r_squared_spy : analysis.r_squared_qqq;
      
      // Main scatter plot
      traces.push({
        x: marketReturns,
        y: analysis.returns,
        type: 'scatter',
        mode: 'markers',
        name: analysis.time_bin,
        marker: {
          size: 6,
          opacity: 0.7,
          color: index < 10 ? `hsl(${index * 36}, 70%, 50%)` : '#6b7280'
        },
        hovertemplate: '<b>%{fullData.name}</b><br>' +
                      `${selectedMarketIndex} Return: %{x:.3f}<br>` +
                      'Strategy Return: %{y:.3f}<br>' +
                      `Beta: ${beta.toFixed(3)}<br>` +
                      `Alpha: ${alpha.toFixed(3)}<br>` +
                      `R²: ${rSquared.toFixed(3)}<br>` +
                      '<extra></extra>'
      });
      
      // Regression line
      const minReturn = Math.min(...marketReturns);
      const maxReturn = Math.max(...marketReturns);
      const regressionX = [minReturn, maxReturn];
      const regressionY = regressionX.map(x => alpha + beta * x);
      
      traces.push({
        x: regressionX,
        y: regressionY,
        type: 'scatter',
        mode: 'lines',
        name: `${analysis.time_bin} Regression`,
        line: { 
          color: index < 10 ? `hsl(${index * 36}, 70%, 50%)` : '#6b7280',
          dash: 'dash',
          width: 1
        },
        showlegend: false,
        hoverinfo: 'skip'
      });
    });
    
    return traces;
  }, [betaAnalysis, selectedMarketIndex, showBetaAnalysis]);

  // Format helper functions
  const formatCorrelation = (value: number): string => {
    return value.toFixed(3);
  };

  const formatBeta = (value: number): string => {
    return value.toFixed(3);
  };

  const getStabilityColor = (score: number): string => {
    if (score >= 0.8) return '#10b981'; // Green
    if (score >= 0.6) return '#f59e0b'; // Yellow
    if (score >= 0.4) return '#f97316'; // Orange
    return '#ef4444'; // Red
  };

  if (isLoading) {
    return (
      <div className="correlation-dashboard-loading">
        <div className="loading-spinner"></div>
        <p>Loading market correlation analysis...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="correlation-dashboard-error">
        <div className="error-message">
          <h3>Error Loading Correlation Dashboard</h3>
          <p>{error}</p>
          <button onClick={fetchCorrelationData} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="market-correlation-dashboard">
      {/* Dashboard Header and Controls */}
      <div className="dashboard-header">
        <div className="header-content">
          <h2>Market Correlation Analysis - {accountName}</h2>
          <div className="dashboard-controls">
            <div className="control-group">
              <label>Market Index:</label>
              <select 
                value={selectedMarketIndex} 
                onChange={(e) => setSelectedMarketIndex(e.target.value as 'SPY' | 'QQQ')}
              >
                <option value="SPY">SPY</option>
                <option value="QQQ">QQQ</option>
              </select>
            </div>
            
            <div className="control-group">
              <label>Correlation Threshold:</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={correlationThreshold}
                onChange={(e) => setCorrelationThreshold(parseFloat(e.target.value))}
              />
              <span className="threshold-value">{correlationThreshold.toFixed(2)}</span>
            </div>
            
            <div className="toggle-group">
              <label className="toggle">
                <input 
                  type="checkbox" 
                  checked={showOnlySignificant} 
                  onChange={(e) => setShowOnlySignificant(e.target.checked)}
                />
                <span>Significant Only</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Visualization Grid */}
      <div className="visualization-grid">
        
        {/* Correlation Heatmap */}
        {showHeatmap && heatmapData && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>{selectedMarketIndex} Correlation Heatmap</h3>
              <div className="panel-stats">
                <span>Time-Bins: {heatmapData.timeBins.length}</span>
                <span>Avg Correlation: {(heatmapData.correlationValues.reduce((a, b) => a + b, 0) / heatmapData.correlationValues.length).toFixed(3)}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={[
                  {
                    z: [heatmapData.correlationValues],
                    x: heatmapData.timeBins,
                    y: ['Correlation'],
                    type: 'heatmap' as const,
                    colorscale: [
                      [0, '#dc2626'],      // Strong negative (red)
                      [0.25, '#f97316'],   // Moderate negative (orange)
                      [0.5, '#fbbf24'],    // Neutral (yellow)
                      [0.75, '#84cc16'],   // Moderate positive (lime)
                      [1, '#10b981']       // Strong positive (green)
                    ] as any,
                    zmin: -1,
                    zmax: 1,
                    hovertemplate: '%{text}<extra></extra>',
                    text: heatmapData.hoverText,
                    colorbar: {
                      title: 'Correlation'
                    }
                  } as any
                ]}
                layout={{
                  title: `${selectedMarketIndex} Correlation by Time-Bin`,
                  xaxis: { title: 'Time-Bin' },
                  yaxis: { title: '' },
                  height: 300,
                  margin: { t: 60, r: 100, b: 60, l: 60 },
                  font: { size: 12 }
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
                onClick={(data) => {
                  if (data.points?.[0] && onCorrelationClick && heatmapData.filteredData) {
                    const pointIndex = data.points[0].pointIndex;
                    const correlationPoint = heatmapData.filteredData[pointIndex];
                    if (correlationPoint) {
                      onCorrelationClick(correlationPoint);
                    }
                  }
                }}
              />
            </div>
          </div>
        )}

        {/* Rolling Correlation Chart */}
        {showRollingCorrelations && rollingCorrelationChartData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>Rolling {selectedMarketIndex} Correlation ({rollingWindowDays}-Day Window)</h3>
              <div className="panel-stats">
                <span>Data Points: {rollingCorrelations.length}</span>
                <span>Avg Stability: {(rollingCorrelations.reduce((a, b) => a + b.stability_score, 0) / rollingCorrelations.length).toFixed(3)}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={rollingCorrelationChartData}
                layout={{
                  title: `Rolling ${selectedMarketIndex} Correlation Over Time`,
                  xaxis: { 
                    title: 'Date',
                    type: 'date'
                  },
                  yaxis: { 
                    title: 'Correlation',
                    range: [-1, 1],
                    zeroline: true,
                    zerolinecolor: '#6b7280',
                    zerolinewidth: 2
                  },
                  height: 400,
                  margin: { t: 60, r: 50, b: 80, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  hovermode: 'x unified'
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* Beta Scatter Plot */}
        {showBetaAnalysis && betaScatterData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>{selectedMarketIndex} Beta Analysis</h3>
              <div className="panel-stats">
                <span>Time-Bins: {betaAnalysis.length}</span>
                <span>Avg Beta: {(betaAnalysis.reduce((a, b) => a + (selectedMarketIndex === 'SPY' ? b.beta_spy : b.beta_qqq), 0) / betaAnalysis.length).toFixed(3)}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={betaScatterData}
                layout={{
                  title: `Strategy vs ${selectedMarketIndex} Returns`,
                  xaxis: { 
                    title: `${selectedMarketIndex} Returns`,
                    zeroline: true,
                    zerolinecolor: '#6b7280',
                    zerolinewidth: 1
                  },
                  yaxis: { 
                    title: 'Strategy Returns',
                    zeroline: true,
                    zerolinecolor: '#6b7280',
                    zerolinewidth: 1
                  },
                  height: 400,
                  margin: { t: 60, r: 50, b: 80, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  hovermode: 'closest'
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Stability Metrics Summary */}
      {showStabilityMetrics && stabilityMetrics.length > 0 && (
        <div className="stability-metrics-panel">
          <div className="panel-header">
            <h3>Correlation Stability Metrics</h3>
          </div>
          
          <div className="stability-grid">
            {stabilityMetrics.map((metric, index) => (
              <div key={index} className="stability-card">
                <div className="stability-header">
                  <h4>{metric.time_bin}</h4>
                  <div 
                    className="stability-score"
                    style={{ color: getStabilityColor(metric.stability_score) }}
                  >
                    {formatCorrelation(metric.stability_score)}
                  </div>
                </div>
                
                <div className="stability-details">
                  <div className="detail-item">
                    <span className="label">Rating:</span>
                    <span className={`rating ${metric.consistency_rating.toLowerCase()}`}>
                      {metric.consistency_rating.replace('_', ' ')}
                    </span>
                  </div>
                  
                  <div className="detail-item">
                    <span className="label">Volatility:</span>
                    <span>{formatCorrelation(metric.rolling_correlation_volatility)}</span>
                  </div>
                  
                  <div className="detail-item">
                    <span className="label">Trend Slope:</span>
                    <span className={metric.correlation_trend_slope >= 0 ? 'positive' : 'negative'}>
                      {formatCorrelation(metric.correlation_trend_slope)}
                    </span>
                  </div>
                </div>
                
                <div className="regime-correlations">
                  <h5>Regime-Specific Correlations:</h5>
                  <div className="regime-grid">
                    <div className="regime-item low">
                      <span className="regime-label">Low VIX:</span>
                      <span>{selectedMarketIndex}: {formatCorrelation(metric.regime_specific_correlations.low_vix[selectedMarketIndex.toLowerCase() as 'spy' | 'qqq'])}</span>
                      <span className="count">({metric.regime_specific_correlations.low_vix.count})</span>
                    </div>
                    <div className="regime-item medium">
                      <span className="regime-label">Med VIX:</span>
                      <span>{selectedMarketIndex}: {formatCorrelation(metric.regime_specific_correlations.medium_vix[selectedMarketIndex.toLowerCase() as 'spy' | 'qqq'])}</span>
                      <span className="count">({metric.regime_specific_correlations.medium_vix.count})</span>
                    </div>
                    <div className="regime-item high">
                      <span className="regime-label">High VIX:</span>
                      <span>{selectedMarketIndex}: {formatCorrelation(metric.regime_specific_correlations.high_vix[selectedMarketIndex.toLowerCase() as 'spy' | 'qqq'])}</span>
                      <span className="count">({metric.regime_specific_correlations.high_vix.count})</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketCorrelationDashboard;