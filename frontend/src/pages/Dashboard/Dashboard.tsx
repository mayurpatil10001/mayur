/**
 * frontend/src/pages/Dashboard/Dashboard.tsx
 * ============================================
 * Main dashboard: KPI grid, PnL equity curve, symbol breakdown table,
 * promoted slots count badge, and Sortino leaderboard preview.
 */

import React, { useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Plot from 'react-plotly.js';
import type { AppDispatch, RootState } from '../../store/store';
import {
  fetchSummary,
  fetchPnLCurve,
  fetchLeaderboard,
} from '../../store/slices/analyticsSlice';
import './Dashboard.css';

// ── KPI Card ──────────────────────────────────────────────────────────────────

interface KPICardProps {
  label: string;
  value: string | number | null;
  sub?: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: string;
}

const KPICard: React.FC<KPICardProps> = ({ label, value, sub, trend, color }) => {
  const trendIcon = trend === 'up' ? '▲' : trend === 'down' ? '▼' : '─';
  const trendClass = trend === 'up' ? 'kpi-trend-up' : trend === 'down' ? 'kpi-trend-down' : '';

  return (
    <div className="kpi-card" style={{ borderTopColor: color ?? '#6366f1' }}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value ?? '—'}</span>
      {sub && (
        <span className={`kpi-sub ${trendClass}`}>
          {trendIcon} {sub}
        </span>
      )}
    </div>
  );
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (v: number | null | undefined, decimals = 0, prefix = '') =>
  v != null ? `${prefix}${v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}` : '—';

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${(v * 100).toFixed(1)}%` : '—';

// ── Dashboard ─────────────────────────────────────────────────────────────────

const Dashboard: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { summary, pnlCurve, leaderboard, filters, status, error } = useSelector(
    (s: RootState) => s.analytics,
  );

  useEffect(() => {
    dispatch(fetchSummary(filters));
    dispatch(fetchPnLCurve(filters));
    dispatch(fetchLeaderboard(filters));
  }, [dispatch, filters]);

  // ── PnL Chart data ────────────────────────────────────────────────────────
  const pnlChartData = useMemo(() => {
    if (!pnlCurve.length) return [];
    const dates = pnlCurve.map((p) => p.date);
    const cumPnl = pnlCurve.map((p) => p.cumulative_pnl);
    const dailyPnl = pnlCurve.map((p) => p.daily_pnl);

    const lineColor = (cumPnl.at(-1) ?? 0) >= 0 ? '#10b981' : '#ef4444';

    return [
      {
        x: dates,
        y: cumPnl,
        type: 'scatter',
        mode: 'lines',
        name: 'Cumulative PnL',
        line: { color: lineColor, width: 2 },
        fill: 'tozeroy',
        fillcolor: lineColor + '18',
      },
      {
        x: dates,
        y: dailyPnl,
        type: 'bar',
        name: 'Daily PnL',
        marker: {
          color: dailyPnl.map((v) => (v >= 0 ? '#10b98140' : '#ef444440')),
          line: { color: dailyPnl.map((v) => (v >= 0 ? '#10b981' : '#ef4444')), width: 1 },
        },
        yaxis: 'y2',
      },
    ];
  }, [pnlCurve]);

  const pnlChartLayout = useMemo(
    () => ({
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 12 },
      margin: { l: 60, r: 20, t: 20, b: 40 },
      xaxis: { gridcolor: '#1e293b', tickfont: { size: 11 } },
      yaxis: { gridcolor: '#1e293b', title: 'Cumulative PnL ($)', tickfont: { size: 11 } },
      yaxis2: {
        overlaying: 'y', side: 'right', title: 'Daily PnL ($)',
        showgrid: false, tickfont: { size: 10 },
      },
      legend: { orientation: 'h', y: -0.15 },
    }),
    [],
  );

  if (status === 'loading') {
    return (
      <div className="dashboard-loading">
        <div className="spinner" />
        <p>Loading dashboard…</p>
      </div>
    );
  }

  const s = summary;

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Performance Dashboard</h1>
        <p className="dashboard-subtitle">
          {filters.account ?? 'All Accounts'}
          {filters.symbol ? ` · ${filters.symbol}` : ''}
          {filters.dateFrom ? ` · From ${filters.dateFrom}` : ''}
        </p>
      </header>

      {error && <div className="dashboard-error">⚠ {error}</div>}

      {/* ── KPI Grid ──────────────────────────────────────────────────────── */}
      <section className="kpi-grid">
        <KPICard
          label="Net PnL"
          value={fmt(s?.net_pnl, 0, '$')}
          trend={(s?.net_pnl ?? 0) >= 0 ? 'up' : 'down'}
          color="#10b981"
        />
        <KPICard
          label="Win Rate"
          value={fmtPct(s?.win_rate)}
          sub={s ? `${s.win_count}W / ${s.loss_count}L` : undefined}
          trend={(s?.win_rate ?? 0) >= 0.5 ? 'up' : 'down'}
          color="#6366f1"
        />
        <KPICard
          label="Sharpe Ratio"
          value={fmt(s?.sharpe_ratio, 2)}
          trend={(s?.sharpe_ratio ?? 0) >= 1.0 ? 'up' : 'neutral'}
          color="#8b5cf6"
        />
        <KPICard
          label="Sortino Ratio"
          value={fmt(s?.sortino_ratio, 2)}
          trend={(s?.sortino_ratio ?? 0) >= 1.0 ? 'up' : 'neutral'}
          color="#a78bfa"
        />
        <KPICard
          label="Max Drawdown"
          value={fmt(s?.max_drawdown, 0, '-$')}
          trend={(s?.max_drawdown ?? 0) < 5000 ? 'up' : 'down'}
          color="#f59e0b"
        />
        <KPICard
          label="Total Trades"
          value={s?.trade_count ?? '—'}
          sub={s ? `Profit Factor: ${fmt(s.profit_factor, 2)}` : undefined}
          color="#06b6d4"
        />
        <KPICard
          label="Expectancy / Trade"
          value={fmt(s?.expectancy, 0, '$')}
          trend={(s?.expectancy ?? 0) >= 0 ? 'up' : 'down'}
          color="#84cc16"
        />
        <KPICard
          label="Promoted Slots"
          value={pnlCurve.length > 0 ? leaderboard.reduce((a, b) => a + b.promoted_slots, 0) : '—'}
          sub="Passed BH-FDR gate"
          color="#f97316"
        />
      </section>

      {/* ── Equity Curve ──────────────────────────────────────────────────── */}
      <section className="dashboard-section">
        <h2>Equity Curve</h2>
        <div className="chart-container">
          {pnlCurve.length > 0 ? (
            <Plot
              data={pnlChartData as any}
              layout={pnlChartLayout as any}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: '320px' }}
            />
          ) : (
            <div className="chart-empty">No trade data available</div>
          )}
        </div>
      </section>

      {/* ── Leaderboard ───────────────────────────────────────────────────── */}
      <section className="dashboard-section">
        <h2>Account Leaderboard <span className="badge">Sortino Ranked</span></h2>
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Account</th>
                <th>Symbol</th>
                <th>Trades</th>
                <th>Net PnL</th>
                <th>Win Rate</th>
                <th>Sharpe</th>
                <th>Sortino</th>
                <th>Max DD</th>
                <th>Promoted</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((row) => (
                <tr key={`${row.account_name}-${row.symbol}`}>
                  <td className="rank">{row.rank}</td>
                  <td className="account-name">{row.account_name}</td>
                  <td>{row.symbol}</td>
                  <td>{row.trade_count}</td>
                  <td className={row.net_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                    {fmt(row.net_pnl, 0, '$')}
                  </td>
                  <td>{fmtPct(row.win_rate)}</td>
                  <td>{fmt(row.sharpe_ratio, 2)}</td>
                  <td className={row.sortino_ratio != null && row.sortino_ratio >= 1 ? 'good' : ''}>
                    {fmt(row.sortino_ratio, 2)}
                  </td>
                  <td className="pnl-negative">{fmt(row.max_drawdown, 0, '$')}</td>
                  <td>
                    <span className={`badge ${row.promoted_slots > 0 ? 'badge-green' : 'badge-gray'}`}>
                      {row.promoted_slots}
                    </span>
                  </td>
                </tr>
              ))}
              {leaderboard.length === 0 && (
                <tr>
                  <td colSpan={10} className="empty-row">No data — run an import first</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;