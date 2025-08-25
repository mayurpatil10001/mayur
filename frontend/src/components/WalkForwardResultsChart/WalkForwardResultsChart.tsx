import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import './WalkForwardResultsChart.css';

// Walk-Forward Analysis Data Interfaces
interface ValidationPeriodResult {
  period_id: string;
  period_start: string;
  period_end: string;
  in_sample_start: string;
  in_sample_end: string;
  out_of_sample_start: string;
  out_of_sample_end: string;
  in_sample_performance: {
    total_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    profit_factor: number;
    volatility: number;
    total_trades: number;
  };
  out_of_sample_performance: {
    total_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    profit_factor: number;
    volatility: number;
    total_trades: number;
    prediction_accuracy: number;
    correlation_with_in_sample: number;
  };
  degradation_metrics: {
    return_degradation: number;
    sharpe_degradation: number;
    drawdown_increase: number;
    overall_degradation_score: number;
    is_significant_degradation: boolean;
  };
  statistical_tests: {
    t_test_p_value: number;
    ks_test_p_value: number;
    correlation_p_value: number;
    is_statistically_significant: boolean;
  };
}

interface PredictionAccuracyData {
  date: string;
  predicted_return: number;
  actual_return: number;
  prediction_error: number;
  rolling_accuracy: number;
  confidence_interval_lower: number;
  confidence_interval_upper: number;
  directional_accuracy: boolean;
  magnitude_accuracy_score: number;
}

interface DegradationAlert {
  alert_id: string;
  timestamp: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  alert_type: 'PERFORMANCE_DECAY' | 'PREDICTION_ACCURACY' | 'STATISTICAL_SIGNIFICANCE' | 'OVERFITTING';
  message: string;
  affected_periods: string[];
  recommendation: string;
  confidence_level: number;
  auto_retraining_suggested: boolean;
}

interface WalkForwardSummary {
  account: string;
  time_bin: string;
  analysis_start: string;
  analysis_end: string;
  total_periods: number;
  validation_method: 'anchored' | 'rolling' | 'expanding' | 'time_series_cv';
  window_size_days: number;
  step_size_days: number;
  overall_metrics: {
    average_out_of_sample_return: number;
    average_prediction_accuracy: number;
    consistency_score: number;
    degradation_trend: number;
    robustness_rating: 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' | 'VERY_POOR';
    recommended_retraining_frequency: number;
  };
  performance_stability: {
    return_volatility: number;
    sharpe_volatility: number;
    prediction_accuracy_volatility: number;
    stability_score: number;
  };
}

// Component Props
interface WalkForwardResultsChartProps {
  accountName: string;
  hour: number;
  minuteBin: number;
  validationMethod?: 'anchored' | 'rolling' | 'expanding' | 'time_series_cv';
  startDate?: string;
  endDate?: string;
  showPerformanceEvolution?: boolean;
  showPredictionAccuracy?: boolean;
  showValidationComparison?: boolean;
  showDegradationAlerts?: boolean;
  height?: number;
  onPeriodClick?: (period: ValidationPeriodResult) => void;
  onAlertClick?: (alert: DegradationAlert) => void;
}

const WalkForwardResultsChart: React.FC<WalkForwardResultsChartProps> = ({
  accountName,
  hour,
  minuteBin,
  validationMethod = 'rolling',
  startDate,
  endDate,
  showPerformanceEvolution = true,
  showPredictionAccuracy = true,
  showValidationComparison = true,
  showDegradationAlerts = true,
  height = 800,
  onPeriodClick,
  onAlertClick
}) => {
  // State management
  const [validationResults, setValidationResults] = useState<ValidationPeriodResult[]>([]);
  const [predictionData, setPredictionData] = useState<PredictionAccuracyData[]>([]);
  const [degradationAlerts, setDegradationAlerts] = useState<DegradationAlert[]>([]);
  const [walkForwardSummary, setWalkForwardSummary] = useState<WalkForwardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<'total_return' | 'sharpe_ratio' | 'win_rate' | 'max_drawdown'>('total_return');
  const [showConfidenceIntervals, setShowConfidenceIntervals] = useState<boolean>(true);
  const [alertSeverityFilter, setAlertSeverityFilter] = useState<'ALL' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'>('ALL');

  // Data fetching functions
  const fetchWalkForwardResults = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      params.append('validation_method', validationMethod);
      
      const response = await fetch(
        `/api/time-bins/${accountName}/${hour}/${minuteBin}/walk-forward?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (!response.ok) throw new Error('Failed to fetch walk-forward results');
      
      const data = await response.json();
      setValidationResults(data.validation_periods || []);
      setWalkForwardSummary(data.summary || null);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load walk-forward results');
    }
  }, [accountName, hour, minuteBin, validationMethod, startDate, endDate]);

  const fetchPredictionAccuracy = useCallback(async () => {
    if (!showPredictionAccuracy) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/time-bins/${accountName}/${hour}/${minuteBin}/prediction-accuracy?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setPredictionData(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch prediction accuracy data:', err);
    }
  }, [accountName, hour, minuteBin, showPredictionAccuracy, startDate, endDate]);

  const fetchDegradationAlerts = useCallback(async () => {
    if (!showDegradationAlerts) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/time-bins/${accountName}/${hour}/${minuteBin}/degradation-alerts?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setDegradationAlerts(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch degradation alerts:', err);
    }
  }, [accountName, hour, minuteBin, showDegradationAlerts, startDate, endDate]);

  // Load data on mount and prop changes
  useEffect(() => {
    fetchWalkForwardResults();
  }, [fetchWalkForwardResults]);

  useEffect(() => {
    fetchPredictionAccuracy();
  }, [fetchPredictionAccuracy]);

  useEffect(() => {
    fetchDegradationAlerts();
  }, [fetchDegradationAlerts]);

  useEffect(() => {
    if (!isLoading) {
      setIsLoading(false);
    }
  }, [validationResults, predictionData, degradationAlerts, walkForwardSummary]);

  // Performance evolution chart data
  const performanceEvolutionData = useMemo(() => {
    if (!validationResults.length || !showPerformanceEvolution) return [];
    
    const traces: any[] = [];
    const periods = validationResults.map(r => r.period_id);
    
    // In-sample performance trace
    const inSampleValues = validationResults.map(r => {
      switch (selectedMetric) {
        case 'total_return': return r.in_sample_performance.total_return * 100;
        case 'sharpe_ratio': return r.in_sample_performance.sharpe_ratio;
        case 'win_rate': return r.in_sample_performance.win_rate * 100;
        case 'max_drawdown': return r.in_sample_performance.max_drawdown * 100;
        default: return 0;
      }
    });
    
    // Out-of-sample performance trace
    const outOfSampleValues = validationResults.map(r => {
      switch (selectedMetric) {
        case 'total_return': return r.out_of_sample_performance.total_return * 100;
        case 'sharpe_ratio': return r.out_of_sample_performance.sharpe_ratio;
        case 'win_rate': return r.out_of_sample_performance.win_rate * 100;
        case 'max_drawdown': return r.out_of_sample_performance.max_drawdown * 100;
        default: return 0;
      }
    });
    
    traces.push(
      {
        x: periods,
        y: inSampleValues,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'In-Sample',
        line: { color: '#3b82f6', width: 2 },
        marker: { size: 6, color: '#3b82f6' },
        hovertemplate: '<b>In-Sample</b><br>' +
                      'Period: %{x}<br>' +
                      `${selectedMetric.replace('_', ' ')}: %{y:.2f}${selectedMetric.includes('rate') || selectedMetric.includes('return') || selectedMetric.includes('drawdown') ? '%' : ''}<br>` +
                      '<extra></extra>'
      },
      {
        x: periods,
        y: outOfSampleValues,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Out-of-Sample',
        line: { color: '#ef4444', width: 2 },
        marker: { size: 6, color: '#ef4444' },
        hovertemplate: '<b>Out-of-Sample</b><br>' +
                      'Period: %{x}<br>' +
                      `${selectedMetric.replace('_', ' ')}: %{y:.2f}${selectedMetric.includes('rate') || selectedMetric.includes('return') || selectedMetric.includes('drawdown') ? '%' : ''}<br>` +
                      '<extra></extra>'
      }
    );
    
    // Add degradation markers
    const degradationPeriods = validationResults.filter(r => r.degradation_metrics.is_significant_degradation);
    if (degradationPeriods.length > 0) {
      const degradationValues = degradationPeriods.map(r => {
        switch (selectedMetric) {
          case 'total_return': return r.out_of_sample_performance.total_return * 100;
          case 'sharpe_ratio': return r.out_of_sample_performance.sharpe_ratio;
          case 'win_rate': return r.out_of_sample_performance.win_rate * 100;
          case 'max_drawdown': return r.out_of_sample_performance.max_drawdown * 100;
          default: return 0;
        }
      });
      
      traces.push({
        x: degradationPeriods.map(r => r.period_id),
        y: degradationValues,
        type: 'scatter',
        mode: 'markers',
        name: 'Significant Degradation',
        marker: {
          size: 12,
          color: '#f59e0b',
          symbol: 'triangle-down',
          line: { color: 'white', width: 2 }
        },
        hovertemplate: '<b>Degradation Alert</b><br>' +
                      'Period: %{x}<br>' +
                      'Degradation Score: %{text}<br>' +
                      '<extra></extra>',
        text: degradationPeriods.map(r => r.degradation_metrics.overall_degradation_score.toFixed(3))
      });
    }
    
    return traces;
  }, [validationResults, selectedMetric, showPerformanceEvolution]);

  // Prediction accuracy chart data
  const predictionAccuracyData = useMemo(() => {
    if (!predictionData.length || !showPredictionAccuracy) return [];
    
    const traces: any[] = [];
    const dates = predictionData.map(p => p.date);
    
    // Rolling accuracy trace
    traces.push({
      x: dates,
      y: predictionData.map(p => p.rolling_accuracy * 100),
      type: 'scatter',
      mode: 'lines',
      name: 'Rolling Accuracy',
      line: { color: '#10b981', width: 3 },
      hovertemplate: '<b>Rolling Accuracy</b><br>' +
                    'Date: %{x}<br>' +
                    'Accuracy: %{y:.1f}%<br>' +
                    '<extra></extra>'
    });
    
    // Confidence intervals
    if (showConfidenceIntervals) {
      const upperBound = predictionData.map(p => p.confidence_interval_upper * 100);
      const lowerBound = predictionData.map(p => p.confidence_interval_lower * 100);
      
      traces.push({
        x: [...dates, ...dates.reverse()],
        y: [...upperBound, ...lowerBound.reverse()],
        type: 'scatter',
        mode: 'lines',
        fill: 'tonexty',
        name: '95% Confidence Interval',
        line: { color: 'rgba(16, 185, 129, 0.3)' },
        fillcolor: 'rgba(16, 185, 129, 0.1)',
        hoverinfo: 'skip'
      });
    }
    
    // Directional accuracy markers
    const correctPredictions = predictionData.filter(p => p.directional_accuracy);
    const incorrectPredictions = predictionData.filter(p => !p.directional_accuracy);
    
    if (correctPredictions.length > 0) {
      traces.push({
        x: correctPredictions.map(p => p.date),
        y: correctPredictions.map(p => p.rolling_accuracy * 100),
        type: 'scatter',
        mode: 'markers',
        name: 'Correct Direction',
        marker: {
          size: 4,
          color: '#10b981',
          symbol: 'circle',
          opacity: 0.7
        },
        hovertemplate: '<b>Correct Prediction</b><br>' +
                      'Date: %{x}<br>' +
                      'Predicted: %{text}<br>' +
                      '<extra></extra>',
        text: correctPredictions.map(p => `${p.predicted_return > 0 ? '+' : ''}${(p.predicted_return * 100).toFixed(2)}%`)
      });
    }
    
    if (incorrectPredictions.length > 0) {
      traces.push({
        x: incorrectPredictions.map(p => p.date),
        y: incorrectPredictions.map(p => p.rolling_accuracy * 100),
        type: 'scatter',
        mode: 'markers',
        name: 'Incorrect Direction',
        marker: {
          size: 4,
          color: '#ef4444',
          symbol: 'x',
          opacity: 0.7
        },
        hovertemplate: '<b>Incorrect Prediction</b><br>' +
                      'Date: %{x}<br>' +
                      'Predicted: %{text}<br>' +
                      '<extra></extra>',
        text: incorrectPredictions.map(p => `${p.predicted_return > 0 ? '+' : ''}${(p.predicted_return * 100).toFixed(2)}%`)
      });
    }
    
    return traces;
  }, [predictionData, showPredictionAccuracy, showConfidenceIntervals]);

  // Validation comparison chart data
  const validationComparisonData = useMemo(() => {
    if (!validationResults.length || !showValidationComparison) return [];
    
    const traces: any[] = [];
    const periods = validationResults.map(r => r.period_id);
    
    // Correlation between in-sample and out-of-sample
    traces.push({
      x: periods,
      y: validationResults.map(r => r.out_of_sample_performance.correlation_with_in_sample),
      type: 'bar',
      name: 'In/Out-of-Sample Correlation',
      marker: {
        color: validationResults.map(r => r.out_of_sample_performance.correlation_with_in_sample > 0.5 ? '#10b981' : '#ef4444'),
        opacity: 0.8
      },
      hovertemplate: '<b>Correlation Analysis</b><br>' +
                    'Period: %{x}<br>' +
                    'Correlation: %{y:.3f}<br>' +
                    '<extra></extra>'
    });
    
    // Add reference lines
    traces.push(
      {
        x: [periods[0], periods[periods.length - 1]],
        y: [0.5, 0.5],
        type: 'scatter',
        mode: 'lines',
        name: 'Good Correlation Threshold',
        line: { color: '#f59e0b', dash: 'dash', width: 2 },
        hoverinfo: 'skip'
      },
      {
        x: [periods[0], periods[periods.length - 1]],
        y: [0, 0],
        type: 'scatter',
        mode: 'lines',
        name: 'Zero Correlation',
        line: { color: '#6b7280', dash: 'dot', width: 1 },
        hoverinfo: 'skip'
      }
    );
    
    return traces;
  }, [validationResults, showValidationComparison]);

  // Format helper functions
  const formatPercentage = (value: number): string => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatMetric = (value: number, metric: string): string => {
    if (metric.includes('rate') || metric.includes('return') || metric.includes('drawdown')) {
      return formatPercentage(value / 100);
    }
    return value.toFixed(3);
  };

  const getSeverityColor = (severity: DegradationAlert['severity']): string => {
    switch (severity) {
      case 'LOW': return '#10b981';
      case 'MEDIUM': return '#f59e0b';
      case 'HIGH': return '#ef4444';
      case 'CRITICAL': return '#dc2626';
      default: return '#6b7280';
    }
  };

  const getRobustnessColor = (rating: WalkForwardSummary['overall_metrics']['robustness_rating']): string => {
    switch (rating) {
      case 'EXCELLENT': return '#10b981';
      case 'GOOD': return '#84cc16';
      case 'FAIR': return '#f59e0b';
      case 'POOR': return '#ef4444';
      case 'VERY_POOR': return '#dc2626';
      default: return '#6b7280';
    }
  };

  if (isLoading) {
    return (
      <div className="walk-forward-loading">
        <div className="loading-spinner"></div>
        <p>Loading walk-forward analysis results...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="walk-forward-error">
        <div className="error-message">
          <h3>Error Loading Walk-Forward Results</h3>
          <p>{error}</p>
          <button onClick={fetchWalkForwardResults} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="walk-forward-results-chart">
      {/* Header and Controls */}
      <div className="results-header">
        <div className="header-content">
          <h2>Walk-Forward Analysis Results - {accountName} {hour}:{minuteBin.toString().padStart(2, '0')}</h2>
          <div className="results-controls">
            <div className="control-group">
              <label>Performance Metric:</label>
              <select 
                value={selectedMetric} 
                onChange={(e) => setSelectedMetric(e.target.value as any)}
              >
                <option value="total_return">Total Return</option>
                <option value="sharpe_ratio">Sharpe Ratio</option>
                <option value="win_rate">Win Rate</option>
                <option value="max_drawdown">Max Drawdown</option>
              </select>
            </div>
            
            <div className="control-group">
              <label>Validation Method:</label>
              <span className="method-badge">{validationMethod.toUpperCase()}</span>
            </div>
            
            <div className="toggle-group">
              <label className="toggle">
                <input 
                  type="checkbox" 
                  checked={showConfidenceIntervals} 
                  onChange={(e) => setShowConfidenceIntervals(e.target.checked)}
                />
                <span>Confidence Intervals</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Panel */}
      {walkForwardSummary && (
        <div className="summary-panel">
          <div className="summary-header">
            <h3>Analysis Summary</h3>
            <div 
              className={`robustness-badge ${walkForwardSummary.overall_metrics.robustness_rating.toLowerCase().replace('_', '-')}`}
              style={{ backgroundColor: getRobustnessColor(walkForwardSummary.overall_metrics.robustness_rating) }}
            >
              {walkForwardSummary.overall_metrics.robustness_rating.replace('_', ' ')}
            </div>
          </div>
          
          <div className="summary-metrics">
            <div className="metric-card">
              <span className="metric-label">Avg Out-of-Sample Return</span>
              <span className="metric-value">
                {formatPercentage(walkForwardSummary.overall_metrics.average_out_of_sample_return)}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Avg Prediction Accuracy</span>
              <span className="metric-value">
                {formatPercentage(walkForwardSummary.overall_metrics.average_prediction_accuracy)}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Consistency Score</span>
              <span className="metric-value">
                {walkForwardSummary.overall_metrics.consistency_score.toFixed(3)}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Retraining Frequency</span>
              <span className="metric-value">
                {walkForwardSummary.overall_metrics.recommended_retraining_frequency} days
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Visualization Grid */}
      <div className="visualization-grid">
        
        {/* Performance Evolution Chart */}
        {showPerformanceEvolution && performanceEvolutionData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>Out-of-Sample Performance Evolution</h3>
              <div className="panel-stats">
                <span>Periods: {validationResults.length}</span>
                <span>Method: {validationMethod}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={performanceEvolutionData}
                layout={{
                  title: `${selectedMetric.replace('_', ' ')} Evolution Over Time`,
                  xaxis: { 
                    title: 'Validation Period',
                    tickangle: -45
                  },
                  yaxis: { 
                    title: selectedMetric.includes('rate') || selectedMetric.includes('return') || selectedMetric.includes('drawdown') ? 
                           `${selectedMetric.replace('_', ' ')} (%)` : 
                           selectedMetric.replace('_', ' ')
                  },
                  height: 400,
                  margin: { t: 60, r: 50, b: 100, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  hovermode: 'x unified'
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
                onClick={(data) => {
                  if (data.points?.[0] && onPeriodClick) {
                    const periodId = data.points[0].x as string;
                    const period = validationResults.find(r => r.period_id === periodId);
                    if (period) {
                      onPeriodClick(period);
                    }
                  }
                }}
              />
            </div>
          </div>
        )}

        {/* Prediction Accuracy Chart */}
        {showPredictionAccuracy && predictionAccuracyData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>Prediction Accuracy Tracking</h3>
              <div className="panel-stats">
                <span>Data Points: {predictionData.length}</span>
                <span>Avg Accuracy: {predictionData.length ? formatPercentage(predictionData.reduce((a, b) => a + b.rolling_accuracy, 0) / predictionData.length) : '0%'}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={predictionAccuracyData}
                layout={{
                  title: 'Rolling Prediction Accuracy',
                  xaxis: { 
                    title: 'Date',
                    type: 'date'
                  },
                  yaxis: { 
                    title: 'Accuracy (%)',
                    range: [0, 100]
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
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* Validation Comparison Chart */}
        {showValidationComparison && validationComparisonData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>In-Sample vs Out-of-Sample Correlation</h3>
              <div className="panel-stats">
                <span>Periods: {validationResults.length}</span>
                <span>Avg Correlation: {validationResults.length ? (validationResults.reduce((a, b) => a + b.out_of_sample_performance.correlation_with_in_sample, 0) / validationResults.length).toFixed(3) : '0'}</span>
              </div>
            </div>
            
            <div className="chart-container">
              <Plot
                data={validationComparisonData}
                layout={{
                  title: 'Performance Correlation Analysis',
                  xaxis: { 
                    title: 'Validation Period',
                    tickangle: -45
                  },
                  yaxis: { 
                    title: 'Correlation Coefficient',
                    range: [-1, 1]
                  },
                  height: 400,
                  margin: { t: 60, r: 50, b: 100, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 }
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
      </div>

      {/* Degradation Alerts Panel */}
      {showDegradationAlerts && degradationAlerts.length > 0 && (
        <div className="alerts-panel">
          <div className="panel-header">
            <h3>Degradation Alerts</h3>
            <div className="alert-controls">
              <label>Severity Filter:</label>
              <select 
                value={alertSeverityFilter} 
                onChange={(e) => setAlertSeverityFilter(e.target.value as any)}
              >
                <option value="ALL">All Severities</option>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>
          </div>
          
          <div className="alerts-list">
            {degradationAlerts
              .filter(alert => alertSeverityFilter === 'ALL' || alert.severity === alertSeverityFilter)
              .map((alert, index) => (
                <div 
                  key={index} 
                  className={`alert-card ${alert.severity.toLowerCase()}`}
                  onClick={() => onAlertClick && onAlertClick(alert)}
                >
                  <div className="alert-header">
                    <div className="alert-info">
                      <span 
                        className="severity-badge"
                        style={{ backgroundColor: getSeverityColor(alert.severity) }}
                      >
                        {alert.severity}
                      </span>
                      <span className="alert-type">{alert.alert_type.replace('_', ' ')}</span>
                      <span className="alert-time">{new Date(alert.timestamp).toLocaleDateString()}</span>
                    </div>
                    <div className="confidence-score">
                      {formatPercentage(alert.confidence_level)} confidence
                    </div>
                  </div>
                  
                  <div className="alert-content">
                    <p className="alert-message">{alert.message}</p>
                    <p className="alert-recommendation">
                      <strong>Recommendation:</strong> {alert.recommendation}
                    </p>
                    
                    {alert.auto_retraining_suggested && (
                      <div className="retraining-suggestion">
                        <span className="suggestion-icon">🤖</span>
                        <span>Automatic retraining recommended</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="affected-periods">
                    <span className="periods-label">Affected periods:</span>
                    <span className="periods-list">{alert.affected_periods.join(', ')}</span>
                  </div>
                </div>
              ))
            }
          </div>
        </div>
      )}

      {/* Detailed Results Table */}
      <div className="results-table-panel">
        <div className="panel-header">
          <h3>Detailed Validation Results</h3>
        </div>
        
        <div className="results-table-container">
          <table className="results-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>In-Sample Return</th>
                <th>Out-of-Sample Return</th>
                <th>Prediction Accuracy</th>
                <th>Correlation</th>
                <th>Degradation Score</th>
                <th>Statistical Significance</th>
              </tr>
            </thead>
            <tbody>
              {validationResults.map((result, index) => (
                <tr 
                  key={index}
                  className={result.degradation_metrics.is_significant_degradation ? 'degraded' : ''}
                  onClick={() => onPeriodClick && onPeriodClick(result)}
                >
                  <td>{result.period_id}</td>
                  <td className={result.in_sample_performance.total_return >= 0 ? 'positive' : 'negative'}>
                    {formatPercentage(result.in_sample_performance.total_return)}
                  </td>
                  <td className={result.out_of_sample_performance.total_return >= 0 ? 'positive' : 'negative'}>
                    {formatPercentage(result.out_of_sample_performance.total_return)}
                  </td>
                  <td>{formatPercentage(result.out_of_sample_performance.prediction_accuracy)}</td>
                  <td>{result.out_of_sample_performance.correlation_with_in_sample.toFixed(3)}</td>
                  <td className={result.degradation_metrics.is_significant_degradation ? 'high-degradation' : 'low-degradation'}>
                    {result.degradation_metrics.overall_degradation_score.toFixed(3)}
                  </td>
                  <td className={result.statistical_tests.is_statistically_significant ? 'significant' : 'not-significant'}>
                    {result.statistical_tests.is_statistically_significant ? 'Yes' : 'No'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default WalkForwardResultsChart;