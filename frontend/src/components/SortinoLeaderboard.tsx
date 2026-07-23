import React, { useEffect, useState, useCallback } from 'react';

interface SortinoEntry {
  account_name: string;
  symbol: string;
  sortino_ratio: number;
  trades_per_week: number;
  total_trades: number;
  mean_pnl: number;
  total_pnl: number;
  win_rate: number;
  profit_factor: number | null;
  downside_dev: number;
  pnl_std_dev: number;
  span_days: number;
}

interface SortinoData {
  status: string;
  filters: { min_trades_per_week: number; min_total_trades: number; max_pnl_std_dev: number | null };
  total_qualifying: number;
  rankings: SortinoEntry[];
}

const MEDAL = ['🥇', '🥈', '🥉'];

const sortino_color = (v: number) => {
  if (v >= 2.0) return '#00e676';
  if (v >= 1.0) return '#ffee58';
  if (v >= 0.0) return '#ff9800';
  return '#f44336';
};

const freq_badge = (tpw: number) => {
  if (tpw >= 20) return { label: 'Very High', bg: '#1565c0', color: '#fff' };
  if (tpw >= 10) return { label: 'High', bg: '#2e7d32', color: '#fff' };
  if (tpw >= 5)  return { label: 'Medium', bg: '#e65100', color: '#fff' };
  return { label: 'Low', bg: '#424242', color: '#aaa' };
};

const SortinoLeaderboard: React.FC = () => {
  const [data, setData]           = useState<SortinoData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [minTpw, setMinTpw]       = useState(3);
  const [maxVol, setMaxVol]       = useState<string>('');
  const [limit, setLimit]         = useState(20);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  const fetchRankings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        min_trades_per_week: String(minTpw),
        min_total_trades:    '30',
        limit:               String(limit),
      });
      if (maxVol) params.append('max_pnl_std_dev', maxVol);

      const res = await fetch(`http://localhost:8000/api/v1/analytics/sortino-ranking?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: SortinoData = await res.json();
      setData(json);
      setLastFetch(new Date());
    } catch (e: any) {
      setError(e.message ?? 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [minTpw, maxVol, limit]);

  useEffect(() => { fetchRankings(); }, [fetchRankings]);

  const styles: Record<string, React.CSSProperties> = {
    container: {
      background: 'linear-gradient(135deg, #0d1117 0%, #161b22 100%)',
      borderRadius: 16,
      padding: '24px',
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      color: '#e6edf3',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      marginBottom: 24,
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 20,
      flexWrap: 'wrap' as const,
      gap: 12,
    },
    title: { fontSize: 22, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 },
    subtitle: { fontSize: 13, color: '#8b949e', marginTop: 4 },
    controls: { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' as const },
    controlGroup: { display: 'flex', flexDirection: 'column' as const, gap: 4 },
    label: { fontSize: 11, color: '#8b949e', textTransform: 'uppercase' as const, letterSpacing: 1 },
    input: {
      background: '#21262d', border: '1px solid #30363d', borderRadius: 8,
      color: '#e6edf3', padding: '6px 10px', fontSize: 13, width: 80,
    },
    btn: {
      background: 'linear-gradient(135deg, #238636, #2ea043)',
      border: 'none', borderRadius: 8, color: '#fff',
      padding: '8px 16px', fontSize: 13, cursor: 'pointer', fontWeight: 600,
      transition: 'opacity 0.2s',
    },
    statsRow: {
      display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
      gap: 12, marginBottom: 20,
    },
    stat: {
      background: '#21262d', borderRadius: 10, padding: '12px 16px',
      border: '1px solid #30363d', textAlign: 'center' as const,
    },
    statVal: { fontSize: 24, fontWeight: 700, color: '#58a6ff' },
    statLabel: { fontSize: 11, color: '#8b949e', marginTop: 4 },
    table: { width: '100%', borderCollapse: 'collapse' as const },
    th: {
      padding: '10px 12px', textAlign: 'left' as const,
      fontSize: 11, color: '#8b949e', borderBottom: '1px solid #21262d',
      textTransform: 'uppercase' as const, letterSpacing: 0.8,
    },
    td: { padding: '10px 12px', borderBottom: '1px solid #161b22', fontSize: 13, verticalAlign: 'middle' as const },
    row: { transition: 'background 0.15s', cursor: 'default' },
    pill: {
      display: 'inline-block', padding: '2px 8px', borderRadius: 12,
      fontSize: 11, fontWeight: 600,
    },
    footer: { marginTop: 12, fontSize: 11, color: '#8b949e', textAlign: 'right' as const },
  };

  const totalTrades = data?.rankings.reduce((s, r) => s + r.total_trades, 0) ?? 0;
  const avgSortino  = data?.rankings.length
    ? (data.rankings.reduce((s, r) => s + r.sortino_ratio, 0) / data.rankings.length).toFixed(2)
    : '—';

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>
            <span>📊</span> Sortino Leaderboard
          </h2>
          <p style={styles.subtitle}>
            High Sortino · High Trade Frequency · Low Volatility — ranked for real-time model evaluation
          </p>
        </div>
        <div style={styles.controls}>
          <div style={styles.controlGroup}>
            <span style={styles.label}>Min trades/wk</span>
            <input style={styles.input} type="number" min={1} max={100}
              value={minTpw} onChange={e => setMinTpw(Number(e.target.value))} />
          </div>
          <div style={styles.controlGroup}>
            <span style={styles.label}>Max PnL σ</span>
            <input style={styles.input} type="number" min={0} placeholder="none"
              value={maxVol} onChange={e => setMaxVol(e.target.value)} />
          </div>
          <div style={styles.controlGroup}>
            <span style={styles.label}>Show top</span>
            <input style={styles.input} type="number" min={5} max={200}
              value={limit} onChange={e => setLimit(Number(e.target.value))} />
          </div>
          <button style={styles.btn} onClick={fetchRankings}>🔄 Refresh</button>
        </div>
      </div>

      {/* Summary stats */}
      {data && (
        <div style={styles.statsRow}>
          <div style={styles.stat}>
            <div style={styles.statVal}>{data.total_qualifying}</div>
            <div style={styles.statLabel}>Qualifying Accounts</div>
          </div>
          <div style={styles.stat}>
            <div style={{...styles.statVal, color: '#00e676'}}>{avgSortino}</div>
            <div style={styles.statLabel}>Avg Sortino (top {data.rankings.length})</div>
          </div>
          <div style={styles.stat}>
            <div style={{...styles.statVal, color: '#ffee58'}}>{totalTrades.toLocaleString()}</div>
            <div style={styles.statLabel}>Total Trades in View</div>
          </div>
        </div>
      )}

      {/* States */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#58a6ff', fontSize: 15 }}>
          ⏳ Computing Sortino rankings across all accounts…
        </div>
      )}
      {error && (
        <div style={{ background: '#2d1117', border: '1px solid #f85149', borderRadius: 8,
          padding: '12px 16px', color: '#f85149', marginBottom: 16 }}>
          ❌ {error} — backend may still be importing data.
        </div>
      )}

      {/* Table */}
      {!loading && data && data.rankings.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>#</th>
                <th style={styles.th}>Account</th>
                <th style={styles.th}>Symbol</th>
                <th style={styles.th}>Sortino ↓</th>
                <th style={styles.th}>Trades/Wk</th>
                <th style={styles.th}>Win Rate</th>
                <th style={styles.th}>Avg PnL</th>
                <th style={styles.th}>Total PnL</th>
                <th style={styles.th}>PnL σ</th>
                <th style={styles.th}>Downside σ</th>
                <th style={styles.th}>P. Factor</th>
              </tr>
            </thead>
            <tbody>
              {data.rankings.map((row, i) => {
                const fb = freq_badge(row.trades_per_week);
                const sc = sortino_color(row.sortino_ratio);
                const isTop3 = i < 3;
                return (
                  <tr key={`${row.account_name}-${row.symbol}`} style={{
                    ...styles.row,
                    background: isTop3 ? 'rgba(88,166,255,0.05)' : 'transparent',
                  }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                    onMouseLeave={e => (e.currentTarget.style.background = isTop3 ? 'rgba(88,166,255,0.05)' : 'transparent')}
                  >
                    <td style={styles.td}>
                      {i < 3 ? MEDAL[i] : <span style={{ color: '#8b949e' }}>{i + 1}</span>}
                    </td>
                    <td style={{ ...styles.td, fontWeight: isTop3 ? 600 : 400 }}>
                      {row.account_name}
                    </td>
                    <td style={styles.td}>
                      <span style={{ ...styles.pill, background: '#21262d', color: '#58a6ff', border: '1px solid #30363d' }}>
                        {row.symbol}
                      </span>
                    </td>
                    <td style={{ ...styles.td, fontWeight: 700, color: sc, fontSize: 15 }}>
                      {row.sortino_ratio.toFixed(3)}
                    </td>
                    <td style={styles.td}>
                      <span style={{ ...styles.pill, background: fb.bg, color: fb.color }}>
                        {fb.label} ({row.trades_per_week}/wk)
                      </span>
                    </td>
                    <td style={{ ...styles.td, color: row.win_rate >= 0.55 ? '#00e676' : row.win_rate >= 0.45 ? '#ffee58' : '#f44336' }}>
                      {(row.win_rate * 100).toFixed(1)}%
                    </td>
                    <td style={{ ...styles.td, color: row.mean_pnl >= 0 ? '#00e676' : '#f44336' }}>
                      ${row.mean_pnl.toFixed(2)}
                    </td>
                    <td style={{ ...styles.td, color: row.total_pnl >= 0 ? '#00e676' : '#f44336' }}>
                      ${row.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td style={{ ...styles.td, color: row.pnl_std_dev < 200 ? '#00e676' : row.pnl_std_dev < 500 ? '#ffee58' : '#f44336' }}>
                      ${row.pnl_std_dev.toFixed(0)}
                    </td>
                    <td style={{ ...styles.td, color: '#ff9800' }}>
                      ${row.downside_dev.toFixed(0)}
                    </td>
                    <td style={styles.td}>
                      {row.profit_factor != null
                        ? <span style={{ color: row.profit_factor >= 1.5 ? '#00e676' : row.profit_factor >= 1.0 ? '#ffee58' : '#f44336' }}>
                            {row.profit_factor.toFixed(2)}x
                          </span>
                        : <span style={{ color: '#8b949e' }}>∞</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && data && data.rankings.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#8b949e' }}>
          No accounts meet the current filters. Try lowering Min trades/wk.
        </div>
      )}

      {lastFetch && (
        <div style={styles.footer}>
          Last updated: {lastFetch.toLocaleTimeString()} · 
          Filter: ≥{minTpw} trades/wk · ≥30 total trades{maxVol ? ` · PnL σ ≤ $${maxVol}` : ''}
        </div>
      )}
    </div>
  );
};

export default SortinoLeaderboard;
