/**
 * frontend/src/pages/WalkForward/WalkForward.tsx
 * Trigger WF tests, poll job status, display fold results + OOS vs IS chart.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Plot from 'react-plotly.js';
import type { AppDispatch, RootState } from '../../store/store';
import {
  triggerWalkForward,
  pollJobStatus,
  fetchWalkForwardResult,
} from '../../store/slices/walkForwardSlice';
import './WalkForward.css';

const WalkForward: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { result, jobStatus, currentJobId, status, error } = useSelector(
    (s: RootState) => s.walkforward,
  );

  const [account, setAccount] = useState('');
  const [symbol, setSymbol] = useState('');
  const [inSample, setInSample] = useState(252);
  const [outOfSample, setOutOfSample] = useState(63);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRun = async () => {
    if (!account || !symbol) return;
    await dispatch(triggerWalkForward({
      account, symbol,
      in_sample_days: inSample,
      out_of_sample_days: outOfSample,
    }));
  };

  // Poll job status every 3 seconds while running
  useEffect(() => {
    if (status === 'running' && currentJobId) {
      pollRef.current = setInterval(() => {
        dispatch(pollJobStatus(currentJobId));
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [status, currentJobId, dispatch]);

  // Fetch result when job completes
  useEffect(() => {
    if (jobStatus?.status === 'COMPLETE' && currentJobId) {
      if (pollRef.current) clearInterval(pollRef.current);
      dispatch(fetchWalkForwardResult(currentJobId));
    }
  }, [jobStatus, currentJobId, dispatch]);

  // Chart: OOS PnL per fold
  const foldChartData = result?.folds
    ? [
        {
          x: result.folds.map((f) => `Fold ${f.fold_index + 1}`),
          y: result.folds.map((f) => f.oos_total_pnl),
          type: 'bar',
          name: 'OOS PnL',
          marker: {
            color: result.folds.map((f) =>
              f.oos_total_pnl >= 0 ? '#10b981' : '#ef4444',
            ),
          },
        },
        {
          x: result.folds.map((f) => `Fold ${f.fold_index + 1}`),
          y: result.folds.map((f) => f.oos_sharpe ?? 0),
          type: 'scatter',
          mode: 'lines+markers',
          name: 'OOS Sharpe',
          yaxis: 'y2',
          line: { color: '#6366f1', width: 2 },
          marker: { size: 6, color: '#6366f1' },
        },
      ]
    : [];

  const foldLayout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 11 },
    margin: { l: 60, r: 60, t: 20, b: 60 },
    xaxis: { gridcolor: '#1e293b' },
    yaxis: { gridcolor: '#1e293b', title: 'OOS PnL ($)' },
    yaxis2: { overlaying: 'y', side: 'right', title: 'Sharpe Ratio', showgrid: false },
    legend: { orientation: 'h', y: -0.2 },
    barmode: 'group',
  };

  return (
    <div className="wf-page">
      <header className="page-header">
        <h1>Walk-Forward Validation</h1>
        <p>Rolling IS/OOS windows with BH-FDR slot promotion per fold</p>
      </header>

      {/* ── Run Form ─────────────────────────────────────────────────────── */}
      <div className="wf-form-card">
        <h2>Configure & Run</h2>
        <div className="form-grid">
          <label>Account <input className="input" value={account} onChange={e => setAccount(e.target.value)} placeholder="e.g. TM_7" /></label>
          <label>Symbol <input className="input" value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="e.g. FDAXM26" /></label>
          <label>In-Sample Days <input className="input" type="number" value={inSample} onChange={e => setInSample(Number(e.target.value))} /></label>
          <label>OOS Days <input className="input" type="number" value={outOfSample} onChange={e => setOutOfSample(Number(e.target.value))} /></label>
        </div>
        <button
          className={`btn-primary ${(status === 'loading' || status === 'running') ? 'btn-disabled' : ''}`}
          onClick={startRun}
          disabled={status === 'loading' || status === 'running'}
        >
          {status === 'running' ? '⏳ Running…' : status === 'loading' ? 'Starting…' : '▶ Run Walk-Forward'}
        </button>
        {status === 'running' && (
          <div className="job-status">
            <div className="spinner-sm" />
            Job: {currentJobId?.slice(0, 8)} · Status: {jobStatus?.status}
          </div>
        )}
        {error && <div className="error-banner">⚠ {error}</div>}
      </div>

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {result && (
        <>
          <div className="result-banner">
            <div className="result-item"><span>{result.n_folds}</span><label>Folds</label></div>
            <div className="result-item"><span>${result.total_oos_pnl?.toFixed(0)}</span><label>Total OOS PnL</label></div>
            <div className="result-item"><span>{result.avg_oos_sharpe?.toFixed(2) ?? '—'}</span><label>Avg OOS Sharpe</label></div>
            <div className="result-item"><span>{result.avg_oos_win_rate != null ? `${(result.avg_oos_win_rate * 100).toFixed(1)}%` : '—'}</span><label>Avg Win Rate</label></div>
            <div className={`result-item ${result.is_decay_detected ? 'decay-warning' : 'decay-ok'}`}>
              <span>{result.is_decay_detected ? '⚠ YES' : '✓ NO'}</span>
              <label>Decay Detected</label>
            </div>
          </div>

          <div className="panel">
            <h2>OOS PnL + Sharpe per Fold</h2>
            <Plot
              data={foldChartData as any}
              layout={foldLayout as any}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: '320px' }}
            />
          </div>

          <div className="panel">
            <h2>Fold Details</h2>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Fold</th><th>IS Period</th><th>OOS Period</th>
                    <th>IS Trades</th><th>Promoted Slots</th><th>OOS Trades</th>
                    <th>OOS PnL</th><th>Win Rate</th><th>Sharpe</th><th>Max DD</th>
                  </tr>
                </thead>
                <tbody>
                  {result.folds.map((f) => (
                    <tr key={f.fold_index}>
                      <td className="rank">{f.fold_index + 1}</td>
                      <td>{f.is_start} → {f.is_end}</td>
                      <td>{f.oos_start} → {f.oos_end}</td>
                      <td>{f.is_trade_count}</td>
                      <td>{f.is_promoted_slots.length}</td>
                      <td>{f.oos_trade_count}</td>
                      <td className={f.oos_total_pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                        ${f.oos_total_pnl?.toFixed(0)}
                      </td>
                      <td>{f.oos_win_rate != null ? `${(f.oos_win_rate * 100).toFixed(1)}%` : '—'}</td>
                      <td>{f.oos_sharpe?.toFixed(2) ?? '—'}</td>
                      <td className="pnl-neg">{f.oos_max_drawdown != null ? `$${f.oos_max_drawdown.toFixed(0)}` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default WalkForward;
