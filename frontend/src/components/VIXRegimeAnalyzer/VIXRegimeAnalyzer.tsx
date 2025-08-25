import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import './VIXRegimeAnalyzer.css';

// VIX Regime Data Interfaces
interface VIXRegimeData {
  date: string;
  vix_level: number;
  regime: 'LOW' | 'MEDIUM' | 'HIGH';
  regime_duration_days: number;
  previous_regime?: 'LOW' | 'MEDIUM' | 'HIGH';
  transition_date?: string;
}

interface RegimePerformanceData {
  account: string;
  time_bin: string;
  hour: number;
  minute_bin: number;
  regime: 'LOW' | 'MEDIUM' | 'HIGH';
  performance_metrics: {
    total_pnl: number;
    average_pnl: number;
    win_rate: number;
    profit_factor: number;
    sharpe_ratio: number;
    max_drawdown: number;
    volatility: number;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
  };
  statistical_significance: {
    p_value: number;
    confidence_level: number;
    is_significant: boolean;
    sample_size_adequate: boolean;
  };
}

interface VIXDistributionData {
  time_bin: string;
  vix_levels: number[];
  regime_counts: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
  };
  regime_percentages: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
  };
  average_vix_by_regime: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
  };
  vix_statistics: {
    min: number;
    max: number;
    mean: number;
    median: number;
    std: number;
    skewness: number;
    kurtosis: number;
  };
}

interface RegimeTransition {
  date: string;
  from_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  to_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  trigger_vix_level: number;
  days_in_previous_regime: number;
  performance_impact: {
    pre_transition_pnl: number;
    post_transition_pnl: number;
    performance_change: number;
    transition_volatility: number;
  };
  market_context: {
    spy_return: number;
    qqq_return: number;
    volume_spike: boolean;
  };
}

interface CurrentRegimeIndicator {
  current_vix_level: number;
  current_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  days_in_current_regime: number;
  regime_percentile: number;
  historical_context: {
    regime_frequency_last_year: {
      LOW: number;
      MEDIUM: number;
      HIGH: number;
    };
    average_regime_duration: {
      LOW: number;
      MEDIUM: number;
      HIGH: number;
    };
    typical_vix_range: {
      LOW: { min: number; max: number; avg: number };
      MEDIUM: { min: number; max: number; avg: number };
      HIGH: { min: number; max: number; avg: number };
    };
  };
  regime_forecast: {
    probability_low: number;
    probability_medium: number;
    probability_high: number;
    expected_duration_days: number;
    confidence_level: number;
  };
}

// Component Props
interface VIXRegimeAnalyzerProps {
  accountName: string;
  startDate?: string;
  endDate?: string;
  selectedTimeBins?: string[];
  showPerformanceComparison?: boolean;
  showDistributionHistograms?: boolean;
  showTransitionTimeline?: boolean;
  showCurrentIndicator?: boolean;
  height?: number;
  onRegimeClick?: (regime: 'LOW' | 'MEDIUM' | 'HIGH') => void;
  onTransitionClick?: (transition: RegimeTransition) => void;
}

const VIXRegimeAnalyzer: React.FC<VIXRegimeAnalyzerProps> = ({
  accountName,
  startDate,
  endDate,
  selectedTimeBins = [],
  showPerformanceComparison = true,
  showDistributionHistograms = true,
  showTransitionTimeline = true,
  showCurrentIndicator = true,
  height = 800,
  onRegimeClick,
  onTransitionClick
}) => {
  // State management
  const [vixData, setVixData] = useState<VIXRegimeData[]>([]);
  const [performanceData, setPerformanceData] = useState<RegimePerformanceData[]>([]);
  const [distributionData, setDistributionData] = useState<VIXDistributionData[]>([]);
  const [transitionData, setTransitionData] = useState<RegimeTransition[]>([]);
  const [currentRegime, setCurrentRegime] = useState<CurrentRegimeIndicator | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRegime, setSelectedRegime] = useState<'ALL' | 'LOW' | 'MEDIUM' | 'HIGH'>('ALL');
  const [comparisonMetric, setComparisonMetric] = useState<'total_pnl' | 'win_rate' | 'sharpe_ratio' | 'profit_factor'>('total_pnl');

  // Regime color scheme
  const regimeColors = {
    LOW: '#10b981',    // Green
    MEDIUM: '#f59e0b',  // Yellow/Amber
    HIGH: '#ef4444'     // Red
  };

  // Data fetching functions
  const fetchVIXData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/vix-regime/data?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (!response.ok) throw new Error('Failed to fetch VIX data');
      
      const data = await response.json();
      setVixData(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load VIX data');
    }
  }, [startDate, endDate]);

  const fetchPerformanceData = useCallback(async () => {
    if (!showPerformanceComparison) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (selectedTimeBins.length) params.append('time_bins', selectedTimeBins.join(','));
      
      const response = await fetch(
        `/api/vix-regime/performance/${accountName}?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setPerformanceData(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch regime performance data:', err);
    }
  }, [accountName, startDate, endDate, selectedTimeBins, showPerformanceComparison]);

  const fetchDistributionData = useCallback(async () => {
    if (!showDistributionHistograms) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (selectedTimeBins.length) params.append('time_bins', selectedTimeBins.join(','));
      
      const response = await fetch(
        `/api/vix-regime/distribution?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setDistributionData(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch VIX distribution data:', err);
    }
  }, [startDate, endDate, selectedTimeBins, showDistributionHistograms]);

  const fetchTransitionData = useCallback(async () => {
    if (!showTransitionTimeline) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/vix-regime/transitions/${accountName}?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setTransitionData(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch transition data:', err);
    }
  }, [accountName, startDate, endDate, showTransitionTimeline]);

  const fetchCurrentRegime = useCallback(async () => {
    if (!showCurrentIndicator) return;
    
    try {
      const response = await fetch(
        `/api/vix-regime/current`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setCurrentRegime(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch current regime data:', err);
    }
  }, [showCurrentIndicator]);

  // Load data on mount and prop changes
  useEffect(() => {
    fetchVIXData();
  }, [fetchVIXData]);

  useEffect(() => {
    fetchPerformanceData();
  }, [fetchPerformanceData]);

  useEffect(() => {
    fetchDistributionData();
  }, [fetchDistributionData]);

  useEffect(() => {
    fetchTransitionData();
  }, [fetchTransitionData]);

  useEffect(() => {
    fetchCurrentRegime();
  }, [fetchCurrentRegime]);

  useEffect(() => {
    if (!isLoading) {
      setIsLoading(false);
    }
  }, [vixData, performanceData, distributionData, transitionData, currentRegime]);

  // Performance comparison chart data
  const performanceComparisonData = useMemo(() => {
    if (!performanceData.length || !showPerformanceComparison) return [];
    
    const filteredData = selectedRegime === 'ALL' ? performanceData : 
                        performanceData.filter(d => d.regime === selectedRegime);
    
    // Group by time-bin for comparison
    const timeBinGroups = filteredData.reduce((groups, item) => {
      if (!groups[item.time_bin]) {
        groups[item.time_bin] = { LOW: null, MEDIUM: null, HIGH: null };
      }
      groups[item.time_bin][item.regime] = item;
      return groups;
    }, {} as Record<string, Record<string, RegimePerformanceData | null>>);
    
    const traces: any[] = [];
    const regimes: Array<'LOW' | 'MEDIUM' | 'HIGH'> = ['LOW', 'MEDIUM', 'HIGH'];
    
    regimes.forEach(regime => {
      const timeBins = Object.keys(timeBinGroups);
      const values = timeBins.map(timeBin => {
        const data = timeBinGroups[timeBin][regime];
        if (!data) return 0;
        
        switch (comparisonMetric) {
          case 'total_pnl': return data.performance_metrics.total_pnl;
          case 'win_rate': return data.performance_metrics.win_rate * 100;
          case 'sharpe_ratio': return data.performance_metrics.sharpe_ratio;
          case 'profit_factor': return data.performance_metrics.profit_factor;
          default: return 0;
        }
      });
      
      const hoverTexts = timeBins.map(timeBin => {
        const data = timeBinGroups[timeBin][regime];
        if (!data) return '';
        
        return `Time-Bin: ${timeBin}<br>` +
               `Regime: ${regime} VIX<br>` +
               `Total P&L: $${data.performance_metrics.total_pnl.toFixed(2)}<br>` +
               `Win Rate: ${(data.performance_metrics.win_rate * 100).toFixed(1)}%<br>` +
               `Sharpe Ratio: ${data.performance_metrics.sharpe_ratio.toFixed(3)}<br>` +
               `Profit Factor: ${data.performance_metrics.profit_factor.toFixed(2)}<br>` +
               `Total Trades: ${data.performance_metrics.total_trades}<br>` +
               `Significant: ${data.statistical_significance.is_significant ? 'Yes' : 'No'}`;
      });
      
      traces.push({
        x: timeBins,
        y: values,
        type: 'bar',
        name: `${regime} VIX`,
        marker: { color: regimeColors[regime] },
        hovertemplate: '%{text}<extra></extra>',
        text: hoverTexts
      });
    });
    
    return traces;
  }, [performanceData, selectedRegime, comparisonMetric, showPerformanceComparison]);

  // VIX distribution histogram data
  const distributionHistogramData = useMemo(() => {
    if (!distributionData.length || !showDistributionHistograms) return [];
    
    const traces: any[] = [];
    
    distributionData.forEach((dist, index) => {
      // Create histogram for each time-bin
      traces.push({
        x: dist.vix_levels,
        type: 'histogram',
        name: dist.time_bin,
        opacity: 0.7,
        nbinsx: 20,
        marker: {
          color: `hsl(${index * 40}, 70%, 50%)`,
          line: { color: 'white', width: 1 }
        },
        hovertemplate: '<b>%{fullData.name}</b><br>' +
                      'VIX Level: %{x:.1f}<br>' +
                      'Count: %{y}<br>' +
                      '<extra></extra>'
      });
    });
    
    // Add regime threshold lines
    const maxCount = Math.max(...distributionData.flatMap(d => d.vix_levels)) || 50;
    
    traces.push(
      {
        x: [15, 15],
        y: [0, maxCount * 0.1],
        type: 'scatter',
        mode: 'lines',
        name: 'Low/Medium Threshold',
        line: { color: '#f59e0b', width: 2, dash: 'dash' },
        hoverinfo: 'skip'
      },
      {
        x: [25, 25],
        y: [0, maxCount * 0.1],
        type: 'scatter',
        mode: 'lines',
        name: 'Medium/High Threshold',
        line: { color: '#ef4444', width: 2, dash: 'dash' },
        hoverinfo: 'skip'
      }
    );
    
    return traces;
  }, [distributionData, showDistributionHistograms]);

  // Transition timeline data
  const transitionTimelineData = useMemo(() => {
    if (!transitionData.length || !showTransitionTimeline) return [];
    
    const traces: any[] = [];
    const dates = transitionData.map(t => t.date);
    const vixLevels = transitionData.map(t => t.trigger_vix_level);
    
    // Main VIX level line
    traces.push({
      x: dates,
      y: vixLevels,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'VIX Level',
      line: { color: '#6b7280', width: 2 },
      marker: { size: 6, color: '#6b7280' },
      hovertemplate: '<b>VIX Transition</b><br>' +
                    'Date: %{x}<br>' +
                    'VIX Level: %{y:.1f}<br>' +
                    '<extra></extra>'
    });
    
    // Transition markers by type
    const transitionTypes = ['LOW_TO_MEDIUM', 'MEDIUM_TO_HIGH', 'HIGH_TO_MEDIUM', 'MEDIUM_TO_LOW', 'LOW_TO_HIGH', 'HIGH_TO_LOW'];
    const transitionGroups = transitionData.reduce((groups, transition) => {
      const key = `${transition.from_regime}_TO_${transition.to_regime}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(transition);
      return groups;
    }, {} as Record<string, RegimeTransition[]>);
    
    Object.entries(transitionGroups).forEach(([transitionType, transitions], index) => {
      const colors = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#6366f1'];
      
      traces.push({
        x: transitions.map(t => t.date),
        y: transitions.map(t => t.trigger_vix_level),
        type: 'scatter',
        mode: 'markers',
        name: transitionType.replace('_TO_', ' → '),
        marker: {
          size: transitions.map(t => Math.min(20, Math.max(8, Math.abs(t.performance_impact.performance_change) / 100))),
          color: colors[index % colors.length],
          symbol: index % 2 === 0 ? 'triangle-up' : 'triangle-down',
          line: { color: 'white', width: 2 }
        },
        hovertemplate: '<b>%{fullData.name}</b><br>' +
                      'Date: %{x}<br>' +
                      'VIX Level: %{y:.1f}<br>' +
                      'Performance Impact: %{text}<br>' +
                      '<extra></extra>',
        text: transitions.map(t => `${t.performance_impact.performance_change > 0 ? '+' : ''}${t.performance_impact.performance_change.toFixed(2)}%`)
      });
    });
    
    // Add regime threshold backgrounds
    const minDate = dates[0];
    const maxDate = dates[dates.length - 1];
    
    return traces;
  }, [transitionData, showTransitionTimeline]);

  // Format helper functions
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercentage = (value: number): string => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const getRegimeLabel = (regime: 'LOW' | 'MEDIUM' | 'HIGH'): string => {
    switch (regime) {
      case 'LOW': return 'Low Volatility (VIX < 15)';
      case 'MEDIUM': return 'Medium Volatility (VIX 15-25)';
      case 'HIGH': return 'High Volatility (VIX > 25)';
    }
  };

  if (isLoading) {
    return (
      <div className="vix-regime-loading">
        <div className="loading-spinner"></div>
        <p>Loading VIX regime analysis...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="vix-regime-error">
        <div className="error-message">
          <h3>Error Loading VIX Analysis</h3>
          <p>{error}</p>
          <button onClick={fetchVIXData} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="vix-regime-analyzer">
      {/* Header and Controls */}
      <div className="analyzer-header">
        <div className="header-content">
          <h2>VIX Regime Analysis - {accountName}</h2>
          <div className="analyzer-controls">
            <div className="control-group">
              <label>Regime Filter:</label>
              <select 
                value={selectedRegime} 
                onChange={(e) => setSelectedRegime(e.target.value as any)}
              >
                <option value="ALL">All Regimes</option>
                <option value="LOW">Low VIX</option>
                <option value="MEDIUM">Medium VIX</option>
                <option value="HIGH">High VIX</option>
              </select>
            </div>
            
            {showPerformanceComparison && (
              <div className="control-group">
                <label>Comparison Metric:</label>
                <select 
                  value={comparisonMetric} 
                  onChange={(e) => setComparisonMetric(e.target.value as any)}
                >
                  <option value="total_pnl">Total P&L</option>
                  <option value="win_rate">Win Rate</option>
                  <option value="sharpe_ratio">Sharpe Ratio</option>
                  <option value="profit_factor">Profit Factor</option>
                </select>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Current Regime Indicator */}
      {showCurrentIndicator && currentRegime && (
        <div className="current-regime-panel">
          <div className="regime-indicator-card">
            <div className="regime-header">
              <h3>Current VIX Regime</h3>
              <div 
                className={`regime-badge ${currentRegime.current_regime.toLowerCase()}`}
                style={{ backgroundColor: regimeColors[currentRegime.current_regime] }}
              >
                {currentRegime.current_regime}
              </div>
            </div>
            
            <div className="regime-details">
              <div className="detail-row">
                <span className="label">VIX Level:</span>
                <span className="value">{currentRegime.current_vix_level.toFixed(1)}</span>
              </div>
              <div className="detail-row">
                <span className="label">Days in Regime:</span>
                <span className="value">{currentRegime.days_in_current_regime}</span>
              </div>
              <div className="detail-row">
                <span className="label">Regime Percentile:</span>
                <span className="value">{currentRegime.regime_percentile.toFixed(0)}th</span>
              </div>
            </div>
            
            <div className="forecast-section">
              <h4>Regime Forecast</h4>
              <div className="forecast-probabilities">
                <div className="prob-item">
                  <span className="prob-label">Low:</span>
                  <span className="prob-value">{formatPercentage(currentRegime.regime_forecast.probability_low)}</span>
                </div>
                <div className="prob-item">
                  <span className="prob-label">Medium:</span>
                  <span className="prob-value">{formatPercentage(currentRegime.regime_forecast.probability_medium)}</span>
                </div>
                <div className="prob-item">
                  <span className="prob-label">High:</span>
                  <span className="prob-value">{formatPercentage(currentRegime.regime_forecast.probability_high)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Visualization Grid */}
      <div className="visualization-grid">
        
        {/* Performance Comparison Chart */}
        {showPerformanceComparison && performanceComparisonData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>Regime Performance Comparison</h3>
              <div className="panel-stats">
                <span>Metric: {comparisonMetric.replace('_', ' ').toUpperCase()}</span>
                <span>Time-Bins: {performanceData.length ? Math.floor(performanceData.length / 3) : 0}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={performanceComparisonData}
                layout={{
                  title: `Performance by VIX Regime (${comparisonMetric.replace('_', ' ')})`,
                  xaxis: { title: 'Time-Bin' },
                  yaxis: { 
                    title: comparisonMetric === 'total_pnl' ? 'Total P&L ($)' :
                           comparisonMetric === 'win_rate' ? 'Win Rate (%)' :
                           comparisonMetric === 'sharpe_ratio' ? 'Sharpe Ratio' :
                           'Profit Factor'
                  },
                  height: 400,
                  margin: { t: 60, r: 50, b: 80, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  barmode: 'group'
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
                onClick={(data) => {
                  if (data.points?.[0] && onRegimeClick) {
                    const point = data.points[0] as any;
                    const regime = point.data?.name?.split(' ')[0] as 'LOW' | 'MEDIUM' | 'HIGH';
                    onRegimeClick(regime);
                  }
                }}
              />
            </div>
          </div>
        )}

        {/* VIX Distribution Histograms */}
        {showDistributionHistograms && distributionHistogramData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>VIX Level Distribution by Time-Bin</h3>
              <div className="panel-stats">
                <span>Time-Bins: {distributionData.length}</span>
                <span>Avg VIX: {distributionData.length ? (distributionData.reduce((a, b) => a + b.vix_statistics.mean, 0) / distributionData.length).toFixed(1) : '0'}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={distributionHistogramData}
                layout={{
                  title: 'VIX Level Distribution',
                  xaxis: { 
                    title: 'VIX Level',
                    range: [5, 50]
                  },
                  yaxis: { title: 'Frequency' },
                  height: 400,
                  margin: { t: 60, r: 50, b: 80, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  barmode: 'overlay'
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* Transition Timeline */}
        {showTransitionTimeline && transitionTimelineData.length > 0 && (
          <div className="visualization-panel full-width">
            <div className="panel-header">
              <h3>Regime Transition Timeline</h3>
              <div className="panel-stats">
                <span>Transitions: {transitionData.length}</span>
                <span>Avg Impact: {transitionData.length ? (transitionData.reduce((a, b) => a + Math.abs(b.performance_impact.performance_change), 0) / transitionData.length).toFixed(1) : '0'}%</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={transitionTimelineData}
                layout={{
                  title: 'VIX Regime Transitions and Performance Impact',
                  xaxis: { 
                    title: 'Date',
                    type: 'date'
                  },
                  yaxis: { 
                    title: 'VIX Level',
                    range: [5, 50]
                  },
                  height: 500,
                  margin: { t: 60, r: 50, b: 80, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  hovermode: 'closest',
                  shapes: [
                    {
                      type: 'rect',
                      xref: 'paper',
                      yref: 'y',
                      x0: 0,
                      y0: 0,
                      x1: 1,
                      y1: 15,
                      fillcolor: 'rgba(16, 185, 129, 0.1)',
                      layer: 'below',
                      line: { width: 0 }
                    },
                    {
                      type: 'rect',
                      xref: 'paper',
                      yref: 'y',
                      x0: 0,
                      y0: 15,
                      x1: 1,
                      y1: 25,
                      fillcolor: 'rgba(245, 158, 11, 0.1)',
                      layer: 'below',
                      line: { width: 0 }
                    },
                    {
                      type: 'rect',
                      xref: 'paper',
                      yref: 'y',
                      x0: 0,
                      y0: 25,
                      x1: 1,
                      y1: 50,
                      fillcolor: 'rgba(239, 68, 68, 0.1)',
                      layer: 'below',
                      line: { width: 0 }
                    }
                  ]
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
                onClick={(data) => {
                  if (data.points?.[0] && onTransitionClick) {
                    const pointIndex = data.points[0].pointIndex;
                    const transition = transitionData[pointIndex];
                    if (transition) {
                      onTransitionClick(transition);
                    }
                  }
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Summary Statistics */}
      {distributionData.length > 0 && (
        <div className="summary-panel">
          <div className="panel-header">
            <h3>Regime Summary Statistics</h3>
          </div>
          
          <div className="summary-grid">
            {distributionData.map((dist, index) => (
              <div key={index} className="summary-card">
                <div className="summary-header">
                  <h4>{dist.time_bin}</h4>
                </div>
                
                <div className="regime-breakdown">
                  <div className="regime-stat low">
                    <div className="regime-info">
                      <span className="regime-name">Low VIX</span>
                      <span className="regime-percentage">{dist.regime_percentages.LOW.toFixed(1)}%</span>
                    </div>
                    <div className="regime-details">
                      <span>Avg: {dist.average_vix_by_regime.LOW.toFixed(1)}</span>
                      <span>Count: {dist.regime_counts.LOW}</span>
                    </div>
                  </div>
                  
                  <div className="regime-stat medium">
                    <div className="regime-info">
                      <span className="regime-name">Medium VIX</span>
                      <span className="regime-percentage">{dist.regime_percentages.MEDIUM.toFixed(1)}%</span>
                    </div>
                    <div className="regime-details">
                      <span>Avg: {dist.average_vix_by_regime.MEDIUM.toFixed(1)}</span>
                      <span>Count: {dist.regime_counts.MEDIUM}</span>
                    </div>
                  </div>
                  
                  <div className="regime-stat high">
                    <div className="regime-info">
                      <span className="regime-name">High VIX</span>
                      <span className="regime-percentage">{dist.regime_percentages.HIGH.toFixed(1)}%</span>
                    </div>
                    <div className="regime-details">
                      <span>Avg: {dist.average_vix_by_regime.HIGH.toFixed(1)}</span>
                      <span>Count: {dist.regime_counts.HIGH}</span>
                    </div>
                  </div>
                </div>
                
                <div className="vix-statistics">
                  <div className="stat-item">
                    <span className="stat-label">Range:</span>
                    <span className="stat-value">{dist.vix_statistics.min.toFixed(1)} - {dist.vix_statistics.max.toFixed(1)}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Mean:</span>
                    <span className="stat-value">{dist.vix_statistics.mean.toFixed(1)}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Volatility:</span>
                    <span className="stat-value">{dist.vix_statistics.std.toFixed(1)}</span>
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

export default VIXRegimeAnalyzer;