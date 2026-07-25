/**
 * frontend/src/pages/MonteCarlo/MonteCarlo.tsx
 * Monte Carlo Simulation UI component with percentile equity curves and ruin probability.
 */

import React, { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Plot from 'react-plotly.js';
import type { AppDispatch, RootState } from '../../store/store';
import { triggerMonteCarlo } from '../../store/slices/walkForwardSlice';
import './MonteCarlo.css';

const MonteCarlo: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { monteCarloResult, status, error } = useSelector(
    (s: RootState) => s.walkforward
  );

  const [account, setAccount] = useState('');
  const [symbol, setSymbol] = useState('');
  const [nSimulations, setNSimulations] = useState(10000);
  const [horizonDays, setHorizonDays] = useState(252);
  const [ruinThreshold, setRuinThreshold] = useState(0.50);

  const runSimulation = () => {
    if (!account || !symbol) return;
    dispatch(
      triggerMonteCarlo({
        account,
        symbol,
        n_simulations: nSimulations,
        horizon_days: horizonDays,
        ruin_threshold: ruinThreshold,
      })
    );
  };

  const mc = monteCarloResult;

  const curveData = mc
    ? [
        {
          x: Array.from({ length: mc.p95_curve.length }, (_, i) => i),
          y: mc.p95_curve,
          type: 'scatter',
          mode: 'lines',
          name: '95th Percentile',
          line: { color: '#10b981', width: 2 },
        },
        {
          x: Array.from({ length: mc.p50_curve.length }, (_, i) => i),
          y: mc.p50_curve,
          type: 'scatter',
          mode: 'lines',
          name: '50th Percentile (Median)',
          line: { color: '#6366f1', width: 2 },
        },
        {
          x: Array.from({ length: mc.p05_curve.length }, (_, i) => i),
          y: mc.p05_curve,
          type: 'scatter',
          mode: 'lines',
          name: '5th Percentile',
          line: { color: '#ef4444', width: 2 },
        },
      ]
    : [];

  const curveLayout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 11 },
    margin: { l: 60, r: 20, t: 20, b: 50 },
    xaxis: { title: 'Trading Days Horizon', gridcolor: '#1e293b' },
    yaxis: { title: 'Simulated PnL ($)', gridcolor: '#1e293b' },
    legend: { orientation: 'h', y: -0.2 },
  };

  const histData = mc?.max_drawdown_histogram
    ? [
        {
          x: mc.max_drawdown_histogram.map(
            (b) => `$${b.bin_start.toFixed(0)} - $${b.bin_end.toFixed(0)}`
          ),
          y: mc.max_drawdown_histogram.map((b) => b.count),
          type: 'bar',
          marker: { color: '#f59e0b' },
        },
      ]
    : [];

  const histLayout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 10 },
    margin: { l: 50, r: 20, t: 20, b: 80 },
    xaxis: { tickangle: -45, gridcolor: '#1e293b' },
    yaxis: { title: 'Frequency', gridcolor: '#1e293b' },
  };

  return (
    <div className="mc-page">
      <header className="page-header">
        <h1>Monte Carlo Simulation</h1>
        <p>Equity curve distribution and risk of ruin modeling</p>
      </header>

      <div className="mc-form-card">
        <h2>Simulation Settings</h2>
        <div className="form-grid">
          <label>
            Account
            <input
              className="input"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              placeholder="e.g. TM_7"
            />
          </label>
          <label>
            Symbol
            <input
              className="input"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="e.g. FDAXM26"
            />
          </label>
          <label>
            Simulations
            <input
              className="input"
              type="number"
              value={nSimulations}
              onChange={(e) => setNSimulations(Number(e.target.value))}
            />
          </label>
          <label>
            Horizon (Days)
            <input
              className="input"
              type="number"
              value={horizonDays}
              onChange={(e) => setHorizonDays(Number(e.target.value))}
            />
          </label>
        </div>
        <button className="btn-primary" onClick={runSimulation}>
          Run Monte Carlo
        </button>
        {error && <div className="error-banner">⚠ {error}</div>}
      </div>

      {mc && (
        <>
          <div className="result-banner">
            <div className="result-item">
              <span>{((mc.ruin_probability ?? 0) * 100).toFixed(1)}%</span>
              <label>Ruin Probability</label>
            </div>
            <div className="result-item">
              <span>${mc.median_final_pnl?.toFixed(0) ?? '—'}</span>
              <label>Median Final PnL</label>
            </div>
            <div className="result-item">
              <span>${mc.p05_final_pnl?.toFixed(0) ?? '—'}</span>
              <label>5th Pct PnL (Worst Case)</label>
            </div>
            <div className="result-item">
              <span>${mc.median_max_drawdown?.toFixed(0) ?? '—'}</span>
              <label>Median Max DD</label>
            </div>
          </div>

          <div className="panel">
            <h2>Percentile Equity Paths</h2>
            <Plot
              data={curveData as any}
              layout={curveLayout as any}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: '340px' }}
            />
          </div>

          <div className="panel">
            <h2>Max Drawdown Distribution</h2>
            <Plot
              data={histData as any}
              layout={histLayout as any}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: '280px' }}
            />
          </div>
        </>
      )}
    </div>
  );
};

export default MonteCarlo;
