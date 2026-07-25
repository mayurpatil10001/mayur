/**
 * frontend/src/pages/Analytics/Analytics.tsx
 * =============================================
 * Analytics page: BH-FDR time-slot heatmap, drawdown chart, 
 * promoted slots table with Wilcoxon p-values, symbol breakdown.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Plot from 'react-plotly.js';
import type { AppDispatch, RootState } from '../../store/store';
import {
  fetchTimeBinGrid,
  fetchDrawdown,
  fetchPnLCurve,
  setFilters,
} from '../../store/slices/analyticsSlice';
import './Analytics.css';

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${(v * 100).toFixed(1)}%` : '—';
const fmt = (v: number | null | undefined, d = 2) =>
  v != null ? v.toFixed(d) : '—';
const fmtUsd = (v: number | null | undefined) =>
  v != null ? `$${v.toLocaleString('en-US', { minimumFractionDigits: 0 })}` : '—';

const Analytics: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { timeBinGrid, drawdown, pnlCurve, filters, status } = useSelector(
    (s: RootState) => s.analytics,
  );

  const [activeTab, setActiveTab] = useState<'heatmap' | 'drawdown' | 'slots'>('heatmap');

  useEffect(() => {
    dispatch(fetchTimeBinGrid(filters));
    dispatch(fetchDrawdown(filters));
    dispatch(fetchPnLCurve(filters));
  }, [dispatch, filters]);

  // ── Heatmap data ──────────────────────────────────────────────────────────
  const heatmapData = useMemo(() => {
    const h = timeBinGrid?.heatmap;
    if (!h) return null;

    const z = h.matrix as (number | null)[][];
    return [
      {
        type: 'heatmap',
        x: h.slots as string[],
        y: h.accounts as string[],
        z,
        colorscale: [
          [0, '#7f1d1d'],
          [0.35, '#1e293b'],
          [0.5, '#1e293b'],
          [0.65, '#1e293b'],
          [1, '#064e3b'],
        ],
        zmid: 0,
        colorbar: {
          title: 'Total PnL ($)',
          titleside: 'right',
          tickfont: { color: '#94a3b8' },
          titlefont: { color: '#94a3b8' },
        },
        hoverongaps: false,
        hovertemplate: 'Account: %{y}<br>Slot: %{x}<br>PnL: $%{z:,.0f}<extra></extra>',
      },
    ];
  }, [timeBinGrid]);

  const heatmapLayout = useMemo(
    () => ({
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 11 },
      margin: { l: 120, r: 80, t: 20, b: 80 },
      xaxis: { title: 'Time Slot (NY)', tickfont: { size: 10 }, tickangle: -45 },
      yaxis: { title: 'Account', tickfont: { size: 10 } },
    }),
    [],
  );

  // ── Drawdown chart ────────────────────────────────────────────────────────
  const drawdownData = useMemo(() => {
    if (!drawdown.length) return [];
    return [
      {
        x: drawdown.map((d) => d.date),
        y: drawdown.map((d) => -d.drawdown),
        type: 'scatter',
        mode: 'lines',
        fill: 'tozeroy',
        fillcolor: '#ef444420',
        line: { color: '#ef4444', width: 1.5 },
        name: 'Drawdown ($)',
      },
    ];
  }, [drawdown]);

  const drawdownLayout = useMemo(
    () => ({
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 11 },
      margin: { l: 70, r: 20, t: 20, b: 50 },
      xaxis: { gridcolor: '#1e293b' },
      yaxis: { gridcolor: '#1e293b', title: 'Drawdown ($)', tickformat: ',.0f' },
      showlegend: false,
    }),
    [],
  );

  const promotedSlots = timeBinGrid?.slots.filter((s) => s.is_promoted) ?? [];

  return (
    <div className="analytics-page">
      <header className="page-header">
        <h1>Analytics</h1>
        <p>BH-FDR time-slot analysis · α = {timeBinGrid?.alpha ?? 0.05}</p>
      </header>

      {/* ── Stat Banner ───────────────────────────────────────────────────── */}
      <div className="stat-banner">
        <div className="stat-item">
          <span className="stat-val">{timeBinGrid?.total_slots ?? '—'}</span>
          <span className="stat-lbl">Total Slots</span>
        </div>
        <div className="stat-item stat-item--promoted">
          <span className="stat-val">{timeBinGrid?.promoted_slots ?? '—'}</span>
          <span className="stat-lbl">Promoted (BH-FDR)</span>
        </div>
        <div className="stat-item">
          <span className="stat-val">
            {drawdown.length > 0
              ? fmtUsd(Math.max(...drawdown.map((d) => d.drawdown)))
              : '—'}
          </span>
          <span className="stat-lbl">Max Drawdown</span>
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div className="tabs">
        {(['heatmap', 'drawdown', 'slots'] as const).map((tab) => (
          <button
            key={tab}
            className={`tab-btn ${activeTab === tab ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'heatmap' ? '🔥 Heatmap' : tab === 'drawdown' ? '📉 Drawdown' : '✅ Promoted Slots'}
          </button>
        ))}
      </div>

      {/* ── Tab Panels ───────────────────────────────────────────────────── */}
      {activeTab === 'heatmap' && (
        <div className="analytics-panel">
          <h2>Account × Time Slot PnL Heatmap</h2>
          {heatmapData ? (
            <Plot
              data={heatmapData as any}
              layout={heatmapLayout as any}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: '400px' }}
            />
          ) : (
            <div className="empty">Run an import to generate heatmap data</div>
          )}
        </div>
      )}

      {activeTab === 'drawdown' && (
        <div className="analytics-panel">
          <h2>Equity Drawdown from Peak</h2>
          {drawdown.length > 0 ? (
            <Plot
              data={drawdownData as any}
              layout={drawdownLayout as any}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: '340px' }}
            />
          ) : (
            <div className="empty">No drawdown data</div>
          )}
        </div>
      )}

      {activeTab === 'slots' && (
        <div className="analytics-panel">
          <h2>
            Promoted Time Slots{' '}
            <span className="badge badge-green">{promotedSlots.length} slots</span>
          </h2>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Symbol</th>
                  <th>Slot (NY)</th>
                  <th>Trades</th>
                  <th>Win Rate</th>
                  <th>Total PnL</th>
                  <th>Expectancy</th>
                  <th>Sharpe</th>
                  <th>Profit Factor</th>
                  <th>Wilcoxon p</th>
                  <th>BH-FDR p</th>
                </tr>
              </thead>
              <tbody>
                {promotedSlots.map((s) => (
                  <tr key={`${s.account_name}|${s.symbol}|${s.time_slot_ny}`}>
                    <td className="account-name">{s.account_name}</td>
                    <td>{s.symbol}</td>
                    <td className="slot-label">{s.time_slot_ny}</td>
                    <td>{s.trade_count}</td>
                    <td>{fmtPct(s.win_rate)}</td>
                    <td className={s.total_pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                      {fmtUsd(s.total_pnl)}
                    </td>
                    <td className={s.expectancy != null && s.expectancy >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                      {fmtUsd(s.expectancy)}
                    </td>
                    <td>{fmt(s.sharpe_ratio)}</td>
                    <td>{fmt(s.profit_factor)}</td>
                    <td className="p-value">{s.wilcoxon_pvalue?.toExponential(2) ?? '—'}</td>
                    <td className="p-value promoted-p">{s.bh_fdr_pvalue?.toExponential(2) ?? '—'}</td>
                  </tr>
                ))}
                {promotedSlots.length === 0 && (
                  <tr>
                    <td colSpan={11} className="empty-row">
                      No promoted slots — need ≥30 trades per slot and BH-FDR p &lt; 0.05
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Analytics;