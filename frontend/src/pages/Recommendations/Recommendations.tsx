/**
 * frontend/src/pages/Recommendations/Recommendations.tsx
 * ========================================================
 * Top promoted time slots with recommendation labels, confidence tiers,
 * sortable table, and Sharpe/expectancy metrics.
 */

import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { get } from '../../api/client';
import type { RootState } from '../../store/store';
import './Recommendations.css';

interface Recommendation {
  rank: number;
  account_name: string;
  symbol: string;
  time_slot_ny: string;
  trade_count: number;
  win_rate: number | null;
  total_pnl: number;
  expectancy: number | null;
  profit_factor: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  bh_fdr_pvalue: number | null;
  is_promoted: boolean;
  recommendation: string;
  confidence: string;
}

const SORT_OPTIONS = [
  { value: 'sharpe_ratio', label: 'Sharpe Ratio' },
  { value: 'expectancy', label: 'Expectancy' },
  { value: 'sortino_ratio', label: 'Sortino Ratio' },
  { value: 'total_pnl', label: 'Total PnL' },
];

const confClass = (c: string) =>
  c === 'HIGH' ? 'conf-high' : c === 'MEDIUM' ? 'conf-med' : 'conf-low';

const recClass = (r: string) =>
  r === 'STRONG BUY' ? 'rec-strong' :
  r === 'BUY' ? 'rec-buy' :
  r === 'WATCH' ? 'rec-watch' : 'rec-avoid';

const Recommendations: React.FC = () => {
  const filters = useSelector((s: RootState) => s.analytics.filters);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState('sharpe_ratio');
  const [topN, setTopN] = useState(20);

  useEffect(() => {
    const fetchRecs = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string> = {
          sort_by: sortBy,
          top_n: String(topN),
        };
        if (filters.account) params['account'] = filters.account;
        if (filters.symbol) params['symbol'] = filters.symbol;
        if (filters.dateFrom) params['date_from'] = filters.dateFrom;
        if (filters.dateTo) params['date_to'] = filters.dateTo;

        const data = await get<Recommendation[]>('/recommendations', params);
        setRecs(data);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchRecs();
  }, [filters, sortBy, topN]);

  const strongBuy = recs.filter((r) => r.recommendation === 'STRONG BUY').length;
  const buy = recs.filter((r) => r.recommendation === 'BUY').length;

  return (
    <div className="recs-page">
      <header className="page-header">
        <h1>Strategy Recommendations</h1>
        <p>BH-FDR promoted time slots ranked by performance quality</p>
      </header>

      {/* ── Summary badges ─────────────────────────────────────────────────── */}
      <div className="rec-summary">
        <span className="rec-badge rec-strong">{strongBuy} STRONG BUY</span>
        <span className="rec-badge rec-buy">{buy} BUY</span>
        <span className="rec-badge rec-watch">{recs.filter(r => r.recommendation === 'WATCH').length} WATCH</span>
      </div>

      {/* ── Controls ───────────────────────────────────────────────────────── */}
      <div className="recs-controls">
        <label>
          Sort by:
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="select">
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label>
          Show top:
          <select value={topN} onChange={(e) => setTopN(Number(e.target.value))} className="select">
            {[10, 20, 50].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {loading ? (
        <div className="loading"><div className="spinner" /><p>Analyzing time slots…</p></div>
      ) : (
        <div className="panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Signal</th>
                <th>Confidence</th>
                <th>Account</th>
                <th>Symbol</th>
                <th>Time Slot</th>
                <th>Trades</th>
                <th>Win Rate</th>
                <th>Expectancy</th>
                <th>Sharpe</th>
                <th>Sortino</th>
                <th>Profit Factor</th>
                <th>Total PnL</th>
                <th>BH-FDR p</th>
              </tr>
            </thead>
            <tbody>
              {recs.map((r) => (
                <tr key={`${r.account_name}|${r.symbol}|${r.time_slot_ny}`}>
                  <td className="rank">{r.rank}</td>
                  <td><span className={`signal-badge ${recClass(r.recommendation)}`}>{r.recommendation}</span></td>
                  <td><span className={`conf-badge ${confClass(r.confidence)}`}>{r.confidence}</span></td>
                  <td className="account-name">{r.account_name}</td>
                  <td>{r.symbol}</td>
                  <td className="slot-label">{r.time_slot_ny}</td>
                  <td>{r.trade_count}</td>
                  <td>{r.win_rate != null ? `${(r.win_rate * 100).toFixed(1)}%` : '—'}</td>
                  <td className={r.expectancy != null && r.expectancy >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                    {r.expectancy != null ? `$${r.expectancy.toFixed(0)}` : '—'}
                  </td>
                  <td>{r.sharpe_ratio?.toFixed(2) ?? '—'}</td>
                  <td>{r.sortino_ratio?.toFixed(2) ?? '—'}</td>
                  <td>{r.profit_factor?.toFixed(2) ?? '—'}</td>
                  <td className={r.total_pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                    ${r.total_pnl.toLocaleString('en-US', { minimumFractionDigits: 0 })}
                  </td>
                  <td className="p-value">{r.bh_fdr_pvalue?.toExponential(2) ?? '—'}</td>
                </tr>
              ))}
              {recs.length === 0 && (
                <tr><td colSpan={14} className="empty-row">No promoted slots found — import more data or lower min_trades threshold</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Recommendations;