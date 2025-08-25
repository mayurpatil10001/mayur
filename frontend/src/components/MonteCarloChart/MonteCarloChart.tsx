import React, { useEffect, useMemo } from 'react';
import Plot from 'react-plotly.js';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { runMonteCarloSimulation } from '../../store/slices/analyticsSlice';
import { MonteCarloRequest } from '../../types/api';
import './MonteCarloChart.css';

interface MonteCarloChartProps {
  accountName: string;
  simulationParams?: Partial<MonteCarloRequest>;
  height?: number;
  showControls?: boolean;
}

const MonteCarloChart: React.FC<MonteCarloChartProps> = ({
  accountName,
  simulationParams = {},
  height = 500,
  showControls = true
}) => {
  const dispatch = useDispatch<AppDispatch>();
  const { monteCarloResults, isLoadingMonteCarlo, monteCarloError } = useSelector(
    (state: RootState) => state.analytics
  );

  const results = monteCarloResults[accountName];
  
  const defaultParams: MonteCarloRequest = {
    account_name: accountName,
    num_simulations: 10000,
    time_horizon_days: 30,
    confidence_levels: [0.95, 0.99],
    ...simulationParams
  };

  useEffect(() => {
    if (accountName && !results) {
      dispatch(runMonteCarloSimulation(defaultParams));
    }
  }, [dispatch, accountName, results]);

  const distributionData = useMemo(() => {
    if (!results) return null;

    // Create histogram data from percentiles
    const percentileKeys = Object.keys(results.percentiles)
      .map(k => parseFloat(k))
      .sort((a, b) => a - b);
    
    const percentileValues = percentileKeys.map(k => results.percentiles[k.toString()]);
    
    // Generate approximate distribution for visualization
    const bins = 50;
    const min = Math.min(...percentileValues);
    const max = Math.max(...percentileValues);
    const binWidth = (max - min) / bins;
    
    const x = [];
    const y = [];
    
    for (let i = 0; i < bins; i++) {
      const binCenter = min + (i + 0.5) * binWidth;
      x.push(binCenter);
      
      // Approximate probability density based on percentiles
      let density = 0;
      for (let j = 0; j < percentileKeys.length - 1; j++) {
        if (binCenter >= percentileValues[j] && binCenter < percentileValues[j + 1]) {
          const percentileRange = percentileKeys[j + 1] - percentileKeys[j];
          density = percentileRange / 100 / binWidth; // Convert to density
          break;
        }
      }
      y.push(density);
    }
    
    return { x, y, percentileValues, percentileKeys };
  }, [results]);

  const runSimulation = () => {
    dispatch(runMonteCarloSimulation(defaultParams));
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  if (monteCarloError) {
    return (
      <div className="monte-carlo-error">
        <div className="error-message">
          <h3>Error Running Simulation</h3>
          <p>{monteCarloError}</p>
          <button onClick={runSimulation} className="retry-button">
            Retry Simulation
          </button>
        </div>
      </div>
    );
  }

  if (isLoadingMonteCarlo) {
    return (
      <div className="monte-carlo-loading">
        <div className="loading-spinner"></div>
        <p>Running Monte Carlo simulation...</p>
        <div className="progress-bar">
          <div className="progress-fill"></div>
        </div>
      </div>
    );
  }

  if (!results || !distributionData) {
    return (
      <div className="monte-carlo-placeholder">
        <h3>Monte Carlo Simulation</h3>
        <p>Run a Monte Carlo simulation to see potential return distributions</p>
        {showControls && (
          <button onClick={runSimulation} className="run-simulation-button">
            Run Simulation
          </button>
        )}
      </div>
    );
  }

  const traces = [
    // Distribution histogram
    {
      x: distributionData.x,
      y: distributionData.y,
      type: 'scatter' as const,
      mode: 'lines' as const,
      fill: 'tonexty' as const,
      name: 'Return Distribution',
      line: { color: '#3498db', width: 2 },
      fillcolor: 'rgba(52, 152, 219, 0.2)',
    },
    // VaR lines
    ...Object.entries(results.var_estimates).map(([confidence, value], index) => ({
      x: [value, value],
      y: [0, Math.max(...distributionData.y)],
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: `VaR ${confidence}`,
      line: { 
        color: index === 0 ? '#e74c3c' : '#c0392b', 
        width: 2, 
        dash: 'dash' as const 
      },
    })),
    // Expected return line
    {
      x: [results.expected_return, results.expected_return],
      y: [0, Math.max(...distributionData.y)],
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: 'Expected Return',
      line: { color: '#27ae60', width: 3 },
    },
  ];

  const layout = {
    title: {
      text: `Monte Carlo Simulation Results (${results.num_simulations.toLocaleString()} simulations)`,
      font: { size: 16, color: '#2c3e50' },
    },
    xaxis: {
      title: 'Return ($)',
      tickformat: '$,.0f',
    },
    yaxis: {
      title: 'Probability Density',
    },
    height: height,
    margin: { t: 60, r: 50, b: 60, l: 80 },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Arial, sans-serif', size: 12, color: '#2c3e50' },
    showlegend: true,
    legend: { 
      x: 0.02, 
      y: 0.98,
      bgcolor: 'rgba(255,255,255,0.8)',
      bordercolor: '#e1e5e9',
      borderwidth: 1,
    },
    hovermode: 'x unified' as const,
  };

  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'] as any,
    responsive: true,
  };

  return (
    <div className="monte-carlo-chart">
      <div className="chart-container">
        <Plot
          data={traces}
          layout={layout}
          config={config}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>

      <div className="simulation-results">
        <div className="results-grid">
          <div className="result-card">
            <h4>Expected Return</h4>
            <div className="value positive">{formatCurrency(results.expected_return)}</div>
            <div className="subtitle">Over {results.time_horizon_days} days</div>
          </div>

          <div className="result-card">
            <h4>Expected Volatility</h4>
            <div className="value neutral">{formatCurrency(results.expected_volatility)}</div>
            <div className="subtitle">Standard deviation</div>
          </div>

          <div className="result-card">
            <h4>Probability of Loss</h4>
            <div className="value negative">{results.probability_of_loss.toFixed(1)}%</div>
            <div className="subtitle">Chance of negative return</div>
          </div>

          <div className="result-card">
            <h4>Value at Risk (95%)</h4>
            <div className="value negative">{formatCurrency(results.var_estimates['95%'] || 0)}</div>
            <div className="subtitle">95% confidence level</div>
          </div>
        </div>

        <div className="percentile-table">
          <h4>Return Percentiles</h4>
          <div className="percentile-grid">
            {Object.entries(results.percentiles).map(([percentile, value]) => (
              <div key={percentile} className="percentile-item">
                <span className="percentile-label">{percentile}th</span>
                <span className={`percentile-value ${value >= 0 ? 'positive' : 'negative'}`}>
                  {formatCurrency(value)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {showControls && (
          <div className="simulation-controls">
            <button onClick={runSimulation} className="rerun-button">
              Re-run Simulation
            </button>
            <div className="simulation-info">
              <span>Simulations: {results.num_simulations.toLocaleString()}</span>
              <span>Time Horizon: {results.time_horizon_days} days</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MonteCarloChart;