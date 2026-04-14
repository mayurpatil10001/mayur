import React, { useState } from 'react';
import { getApiV1BaseUrl } from '../../../services/api';

interface MethodMetrics {
    method: string;
    total_pnl: number;
    total_trades: number;
    win_rate: number;
    avg_trade: number;
    profit_factor: number;
    sharpe: number;
    sortino: number;
    consistency_ratio: number;
    total_folds: number;
    profitable_folds: number;
    avg_edges_per_fold: number;
    permutation_p_value: number | null;
    equity_curve: { date: string; pnl: number }[];
}

interface MethodComparisonData {
    symbol: string;
    train_months: number;
    test_months: number;
    total_unique_months: number;
    methods: { [key: string]: MethodMetrics };
    recommended_method: string;
    method_labels: { [key: string]: string };
}

interface LiveBinResult {
    time_slot: string;
    day_of_week: number;
    day_name: string;
    account: string;
    expected_avg_trade: number;
    actual_avg_trade: number | null;
    expected_win_rate: number;
    actual_win_rate: number | null;
    actual_profit_factor: number | null;
    expected_profit_factor: number;
    z_score: number | null;
    status: string;
    n_actual_trades: number;
    actual_pnl: number;
    expected_pnl: number;
    tracking_error: number;
}

interface LiveValidationData {
    symbol: string;
    validation_start_date: string;
    method: string;
    verdict: string;
    total_expected_pnl: number;
    total_actual_pnl: number;
    tracking_error_total: number;
    bins_on_track: number;
    bins_total: number;
    bin_results: LiveBinResult[];
    equity_curve_actual: { date: string; pnl: number }[];
}

interface Props {
    symbol: string;
    onSelectMethod?: (method: string) => void;
    formatCurrency: (v: number) => string;
}

const METHOD_COLORS: { [key: string]: string } = {
    persistence: '#60a5fa',
    classic: '#a78bfa',
    statistical: '#34d399',
    ensemble: '#fb923c',
};
const TEXT_PRIMARY = '#0f172a';
const TEXT_MUTED = '#334155';

const METRICS_ROWS = [
    { key: 'total_pnl', label: 'Total OOS PnL', fmt: (v: number, fc: (n: number) => string) => fc(v), higherBetter: true },
    { key: 'avg_trade', label: 'Avg Trade', fmt: (v: number, fc: (n: number) => string) => fc(v), higherBetter: true },
    { key: 'win_rate', label: 'Win Rate', fmt: (v: number) => `${v.toFixed(1)}%`, higherBetter: true },
    { key: 'profit_factor', label: 'Profit Factor', fmt: (v: number) => v.toFixed(2), higherBetter: true },
    { key: 'sharpe', label: 'Sharpe', fmt: (v: number) => v.toFixed(2), higherBetter: true },
    { key: 'sortino', label: 'Sortino', fmt: (v: number) => v.toFixed(2), higherBetter: true },
    { key: 'consistency_ratio', label: 'Consistency %', fmt: (v: number) => `${v.toFixed(1)}%`, higherBetter: true },
    { key: 'avg_edges_per_fold', label: 'Avg Edges/Fold', fmt: (v: number) => v.toFixed(1), higherBetter: false },
    { key: 'permutation_p_value', label: 'Permutation p-val', fmt: (v: number | null) => v != null ? v.toFixed(4) : 'n/a', higherBetter: false, lowerBetter: true },
];

const MethodComparison: React.FC<Props> = ({ symbol, onSelectMethod, formatCurrency }) => {
    const [trainMonths, setTrainMonths] = useState(4);
    const [testMonths, setTestMonths] = useState(1);
    const [minPersistence, setMinPersistence] = useState(70);
    const [isLoading, setIsLoading] = useState(false);
    const [data, setData] = useState<MethodComparisonData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [selectedMethod, setSelectedMethod] = useState<string | null>(null);

    // Live validation state
    const [liveDate, setLiveDate] = useState('');
    const [liveMethod, setLiveMethod] = useState('persistence');
    const [isLoadingLive, setIsLoadingLive] = useState(false);
    const [liveData, setLiveData] = useState<LiveValidationData | null>(null);
    const [liveError, setLiveError] = useState<string | null>(null);
    const [showLive, setShowLive] = useState(false);

    const runComparison = async () => {
        setIsLoading(true);
        setError(null);
        setData(null);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const resp = await fetch(`${getApiV1BaseUrl()}/analytics/recommendations/method-comparison/${encodeURIComponent(symbol)}`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ train_months: trainMonths, test_months: testMonths, min_persistence: minPersistence }),
            });
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                const msg = json.message || json.detail || `HTTP ${resp.status}`;
                setError(
                    resp.status === 404
                        ? `${msg} — Restart the Python API from the project root so it loads the latest routes (POST .../method-comparison/{symbol}). Confirm at http://localhost:8000/docs`
                        : String(msg)
                );
                return;
            }
            if (json.status === 'success') {
                setData(json.data);
                setSelectedMethod(json.data.recommended_method);
            } else {
                setError(json.message || 'Comparison failed');
            }
        } catch (err: any) {
            setError(String(err));
        } finally {
            setIsLoading(false);
        }
    };

    const runLiveValidation = async () => {
        if (!liveDate) return;
        setIsLoadingLive(true);
        setLiveError(null);
        setLiveData(null);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const resp = await fetch(`${getApiV1BaseUrl()}/analytics/recommendations/live-validation/${encodeURIComponent(symbol)}`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ validation_start_date: liveDate, method: liveMethod }),
            });
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                setLiveError(String(json.message || json.detail || `HTTP ${resp.status}`));
                return;
            }
            if (json.status === 'success') {
                setLiveData(json.data);
            } else {
                setLiveError(json.message || 'Live validation failed');
            }
        } catch (err: any) {
            setLiveError(String(err));
        } finally {
            setIsLoadingLive(false);
        }
    };

    const getBestValueForMetric = (metricKey: string, higherBetter: boolean, lowerBetter?: boolean): string => {
        if (!data) return '';
        const values = Object.entries(data.methods).map(([m, d]) => ({
            method: m,
            val: (d as any)[metricKey] as number | null
        })).filter(x => x.val != null);
        if (!values.length) return '';
        if (lowerBetter) return values.reduce((a, b) => (a.val! < b.val! ? a : b)).method;
        if (higherBetter) return values.reduce((a, b) => (a.val! > b.val! ? a : b)).method;
        return '';
    };

    const verdictColor = (v: string) => {
        if (v === 'ON_TRACK') return '#4ade80';
        if (v === 'DRIFTING') return '#facc15';
        return '#f87171';
    };

    const statusColor = (s: string) => {
        if (s === 'ON_TRACK') return '#4ade80';
        if (s === 'DRIFTING') return '#facc15';
        if (s === 'CRITICAL') return '#f87171';
        return '#94a3b8';
    };

    const methods = data ? Object.keys(data.methods) : [];
    const selectedForChart = selectedMethod || data?.recommended_method || '';
    const maxCurveLen = data ? Math.max(...Object.values(data.methods).map(m => m.equity_curve?.length || 0), 2) : 2;
    const allPnls = data ? Object.values(data.methods).flatMap(m => (m.equity_curve || []).map(p => p.pnl)) : [0];
    const maxPnl = Math.max(...allPnls, 0);
    const minPnl = Math.min(...allPnls, 0);
    const pnlRange = Math.max(1, maxPnl - minPnl);

    return (
        <div style={{ padding: '16px 0' }}>
            <div style={{
                background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 10,
                padding: '12px 16px', marginBottom: 18, fontSize: 13, color: TEXT_MUTED, lineHeight: 1.55,
            }}>
                <strong style={{ color: TEXT_PRIMARY }}>How to use Method Bake-Off</strong>
                <ul style={{ margin: '8px 0 0 18px', padding: 0 }}>
                    <li>Click <strong>Run Method Bake-Off</strong> to run the same walk-forward process four times (Persistence, Classic, Statistical, Ensemble) and compare <strong>out-of-sample</strong> metrics.</li>
                    <li>Prefer the method with high <strong>Consistency %</strong> and a low <strong>permutation p-value</strong> (&lt; 0.05 means not random).</li>
                    <li>Use <strong>Use This Method in Matrix</strong> to switch the matrix ranking to match the winner.</li>
                    <li><strong>Live Trading Tracker</strong> (below): set your real go-live date after you start trading live; it compares expected vs actual PnL per bin.</li>
                </ul>
            </div>
            {/* Controls */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: 20 }}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: TEXT_MUTED }}>
                    Train Months
                    <input type="number" min={2} max={24} value={trainMonths}
                        onChange={e => setTrainMonths(Number(e.target.value))}
                        style={{ width: 70, padding: '4px 8px', borderRadius: 6, border: '1px solid #94a3b8', background: '#fff', color: TEXT_PRIMARY }} />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: TEXT_MUTED }}>
                    Test Months
                    <input type="number" min={1} max={6} value={testMonths}
                        onChange={e => setTestMonths(Number(e.target.value))}
                        style={{ width: 70, padding: '4px 8px', borderRadius: 6, border: '1px solid #94a3b8', background: '#fff', color: TEXT_PRIMARY }} />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: TEXT_MUTED }}>
                    Min Persistence %
                    <input type="number" min={50} max={100} value={minPersistence}
                        onChange={e => setMinPersistence(Number(e.target.value))}
                        style={{ width: 90, padding: '4px 8px', borderRadius: 6, border: '1px solid #94a3b8', background: '#fff', color: TEXT_PRIMARY }} />
                </label>
                <button
                    onClick={runComparison}
                    disabled={isLoading}
                    style={{
                        padding: '8px 20px', background: isLoading ? '#3a4460' : '#3b82f6',
                        color: '#fff', border: 'none', borderRadius: 8, cursor: isLoading ? 'not-allowed' : 'pointer',
                        fontWeight: 600, fontSize: 13,
                    }}
                >
                    {isLoading ? 'Running...' : 'Run Method Bake-Off'}
                </button>
            </div>

            {error && (
                <div style={{ background: '#3b1f1f', border: '1px solid #dc2626', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', marginBottom: 16 }}>
                    {error}
                </div>
            )}

            {data && (
                <>
                    {/* Recommended method banner */}
                    <div style={{
                        background: '#1a2535', border: `2px solid ${METHOD_COLORS[data.recommended_method] || '#3b82f6'}`,
                        borderRadius: 10, padding: '12px 18px', marginBottom: 20,
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10,
                    }}>
                        <div>
                            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2 }}>RECOMMENDED METHOD</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: METHOD_COLORS[data.recommended_method] || '#e2e8f0' }}>
                                {data.method_labels[data.recommended_method] || data.recommended_method}
                            </div>
                            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                                {data.total_unique_months} months of data · {data.train_months}M train / {data.test_months}M test folds
                            </div>
                        </div>
                        {onSelectMethod && (
                            <button
                                onClick={() => { onSelectMethod(data.recommended_method); setSelectedMethod(data.recommended_method); }}
                                style={{
                                    padding: '8px 18px', background: METHOD_COLORS[data.recommended_method] || '#3b82f6',
                                    color: '#000', border: 'none', borderRadius: 8, cursor: 'pointer',
                                    fontWeight: 700, fontSize: 13,
                                }}
                            >
                                Use This Method in Matrix
                            </button>
                        )}
                    </div>

                    {/* Comparison table */}
                    <div style={{ overflowX: 'auto', marginBottom: 24 }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, color: TEXT_PRIMARY }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #cbd5e1' }}>
                                    <th style={{ textAlign: 'left', padding: '8px 12px', color: TEXT_PRIMARY, fontWeight: 700 }}>Metric</th>
                                    {methods.map(m => (
                                        <th key={m} style={{
                                            textAlign: 'center', padding: '8px 12px',
                                            color: METHOD_COLORS[m] || TEXT_PRIMARY, fontWeight: 700,
                                            background: m === data.recommended_method ? 'rgba(59,130,246,0.12)' : 'transparent',
                                            cursor: 'pointer',
                                        }} onClick={() => setSelectedMethod(m)}>
                                            {data.method_labels[m] || m}
                                            {m === data.recommended_method && (
                                                <span style={{ display: 'block', fontSize: 9, color: '#fbbf24', fontWeight: 700 }}>★ BEST</span>
                                            )}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {METRICS_ROWS.map(row => {
                                    const bestMethod = getBestValueForMetric(row.key, row.higherBetter, row.lowerBetter);
                                    return (
                                        <tr key={row.key} style={{ borderBottom: '1px solid #e2e8f0' }}>
                                            <td style={{ padding: '7px 12px', color: TEXT_PRIMARY, fontWeight: 600 }}>{row.label}</td>
                                            {methods.map(m => {
                                                const val = (data.methods[m] as any)[row.key];
                                                const isBest = m === bestMethod;
                                                return (
                                                    <td key={m} style={{
                                                        textAlign: 'center', padding: '7px 12px',
                                                        color: isBest ? '#16a34a' : TEXT_PRIMARY,
                                                        fontWeight: isBest ? 700 : 400,
                                                        background: m === data.recommended_method ? 'rgba(59,130,246,0.08)' : 'transparent',
                                                    }}>
                                                        {val != null ? (row.fmt as any)(val, formatCurrency) : 'n/a'}
                                                        {isBest && <span style={{ marginLeft: 4, fontSize: 10, color: '#16a34a' }}>✓</span>}
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* Method hint */}
                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 8, padding: '10px 16px', marginBottom: 24, fontSize: 12, color: TEXT_MUTED, lineHeight: 1.6 }}>
                        <strong style={{ color: TEXT_PRIMARY }}>How to read this:</strong> Consistency % = % of test folds that were profitable OOS.
                        A permutation p-value &lt; 0.05 means the results are unlikely to be random.
                        Sharpe &gt; 0.5 is the minimum bar for live trading. Higher consistency + low p-value beats pure PnL.
                    </div>

                    {/* Equity curves */}
                    <div style={{ marginBottom: 24 }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: TEXT_PRIMARY, marginBottom: 10 }}>
                            OOS Equity Curves — All Methods
                        </div>
                        <div style={{ height: 260, position: 'relative', background: 'linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%)', borderRadius: 10, border: '1px solid #cbd5e1', padding: 16, overflow: 'hidden' }}>
                            <svg style={{ position: 'absolute', inset: 16, width: 'calc(100% - 32px)', height: 'calc(100% - 32px)' }} viewBox="0 0 100 200" preserveAspectRatio="none">
                                {[0, 25, 50, 75, 100].map((v) => (
                                    <line key={v} x1="0" x2="100" y1={(v * 2).toString()} y2={(v * 2).toString()} stroke="#dbeafe" strokeWidth="0.6" />
                                ))}
                            </svg>
                            {methods.map(m => {
                                const curve = data.methods[m].equity_curve;
                                if (!curve || curve.length < 2) return null;
                                const h = 200;
                                const w = 100;
                                const pts = curve.map((pt, i) => {
                                    const x = (i / (maxCurveLen - 1)) * w;
                                    const y = h - ((pt.pnl - minPnl) / pnlRange) * h;
                                    return `${x},${y}`;
                                }).join(' ');
                                return (
                                    <svg key={m} style={{ position: 'absolute', top: 16, left: 16, right: 16, bottom: 16, width: 'calc(100% - 32px)', height: 'calc(100% - 32px)' }} preserveAspectRatio="none" viewBox={`0 0 100 ${h}`}>
                                        <defs>
                                            <filter id={`glow-${m}`}>
                                                <feGaussianBlur stdDeviation="1.2" result="blur" />
                                                <feMerge>
                                                    <feMergeNode in="blur" />
                                                    <feMergeNode in="SourceGraphic" />
                                                </feMerge>
                                            </filter>
                                        </defs>
                                        <polyline points={pts} fill="none" stroke={METHOD_COLORS[m] || '#fff'}
                                            strokeWidth={m === selectedForChart ? 3.2 : 1.8}
                                            strokeOpacity={m === selectedForChart ? 0.98 : 0.55}
                                            filter={m === selectedForChart ? `url(#glow-${m})` : undefined}
                                            strokeLinecap="round"
                                            strokeLinejoin="round" />
                                    </svg>
                                );
                            })}
                            {/* Legend */}
                            <div style={{ position: 'absolute', bottom: 8, right: 12, display: 'flex', gap: 12 }}>
                                {methods.map(m => (
                                    <div key={m} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
                                        <div style={{ width: 16, height: 2, background: METHOD_COLORS[m] || '#fff' }} />
                                        <span style={{ color: METHOD_COLORS[m] || TEXT_PRIMARY, fontWeight: 700 }}>{data.method_labels[m] || m}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </>
            )}

            {/* Live Validation Section */}
            <div style={{ borderTop: '1px solid #1e2a3a', paddingTop: 20, marginTop: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                    <div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0' }}>Live Trading Tracker</div>
                        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                            Set your go-live date to compare expected vs actual results per bin
                        </div>
                    </div>
                    <button
                        onClick={() => setShowLive(!showLive)}
                        style={{ padding: '6px 14px', background: '#1e2a3a', color: '#94a3b8', border: '1px solid #3a4460', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}
                    >
                        {showLive ? 'Hide' : 'Show'}
                    </button>
                </div>

                {showLive && (
                    <>
                        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: 16 }}>
                            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#94a3b8' }}>
                                Go-Live Date
                                <input type="date" value={liveDate} onChange={e => setLiveDate(e.target.value)}
                                    style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #3a4460', background: '#151c2e', color: '#e2e8f0' }} />
                            </label>
                            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#94a3b8' }}>
                                Selection Method
                                <select value={liveMethod} onChange={e => setLiveMethod(e.target.value)}
                                    style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #3a4460', background: '#151c2e', color: '#e2e8f0' }}>
                                    <option value="persistence">Persistence</option>
                                    <option value="classic">Classic</option>
                                    <option value="statistical">Statistical EV</option>
                                    <option value="ensemble">Ensemble</option>
                                </select>
                            </label>
                            <button
                                onClick={runLiveValidation}
                                disabled={isLoadingLive || !liveDate}
                                style={{
                                    padding: '8px 18px', background: isLoadingLive || !liveDate ? '#3a4460' : '#10b981',
                                    color: '#fff', border: 'none', borderRadius: 8, cursor: isLoadingLive || !liveDate ? 'not-allowed' : 'pointer',
                                    fontWeight: 600, fontSize: 13,
                                }}
                            >
                                {isLoadingLive ? 'Analyzing...' : 'Check Live vs Expected'}
                            </button>
                        </div>

                        {liveError && (
                            <div style={{ background: '#3b1f1f', border: '1px solid #dc2626', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', marginBottom: 14 }}>
                                {liveError}
                            </div>
                        )}

                        {liveData && (
                            <>
                                {/* Verdict banner */}
                                <div style={{
                                    background: '#1a2535', border: `2px solid ${verdictColor(liveData.verdict)}`,
                                    borderRadius: 10, padding: '12px 18px', marginBottom: 16,
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10,
                                }}>
                                    <div>
                                        <div style={{ fontSize: 11, color: '#94a3b8' }}>OVERALL VERDICT</div>
                                        <div style={{ fontSize: 20, fontWeight: 800, color: verdictColor(liveData.verdict) }}>
                                            {liveData.verdict.replace(/_/g, ' ')}
                                        </div>
                                        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                                            {liveData.bins_on_track}/{liveData.bins_total} bins on track since {liveData.validation_start_date}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: 20 }}>
                                        <div style={{ textAlign: 'center' }}>
                                            <div style={{ fontSize: 11, color: '#94a3b8' }}>Expected PnL</div>
                                            <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{formatCurrency(liveData.total_expected_pnl)}</div>
                                        </div>
                                        <div style={{ textAlign: 'center' }}>
                                            <div style={{ fontSize: 11, color: '#94a3b8' }}>Actual PnL</div>
                                            <div style={{ fontSize: 16, fontWeight: 700, color: liveData.total_actual_pnl >= 0 ? '#4ade80' : '#f87171' }}>
                                                {formatCurrency(liveData.total_actual_pnl)}
                                            </div>
                                        </div>
                                        <div style={{ textAlign: 'center' }}>
                                            <div style={{ fontSize: 11, color: '#94a3b8' }}>Tracking Error</div>
                                            <div style={{ fontSize: 16, fontWeight: 700, color: liveData.tracking_error_total >= 0 ? '#4ade80' : '#f87171' }}>
                                                {formatCurrency(liveData.tracking_error_total)}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Per-bin table */}
                                <div style={{ overflowX: 'auto', marginBottom: 16 }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                        <thead>
                                            <tr style={{ borderBottom: '2px solid #3a4460' }}>
                                                {['Status', 'Bin', 'Account', 'Exp Avg', 'Act Avg', 'Exp WR', 'Act WR', 'Act PF', 'Z-Score', 'Trades', 'Act PnL', 'Error'].map(h => (
                                                    <th key={h} style={{ textAlign: h === 'Status' ? 'center' : 'right', padding: '6px 10px', color: '#94a3b8', fontWeight: 600 }}>{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {liveData.bin_results.map((b, i) => (
                                                <tr key={i} style={{ borderBottom: '1px solid #1a2535' }}>
                                                    <td style={{ textAlign: 'center', padding: '5px 10px' }}>
                                                        <span style={{
                                                            padding: '2px 7px', borderRadius: 4, fontSize: 10, fontWeight: 700,
                                                            background: b.status === 'ON_TRACK' ? '#052e16' : b.status === 'DRIFTING' ? '#451a03' : b.status === 'CRITICAL' ? '#3b1f1f' : '#1e2a3a',
                                                            color: statusColor(b.status),
                                                        }}>
                                                            {b.status.replace(/_/g, ' ')}
                                                        </span>
                                                    </td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#e2e8f0' }}>{b.time_slot} {b.day_name}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#94a3b8', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.account}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#94a3b8' }}>{formatCurrency(b.expected_avg_trade)}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: b.actual_avg_trade != null ? (b.actual_avg_trade >= b.expected_avg_trade * 0.7 ? '#4ade80' : '#f87171') : '#94a3b8' }}>
                                                        {b.actual_avg_trade != null ? formatCurrency(b.actual_avg_trade) : '—'}
                                                    </td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#94a3b8' }}>{b.expected_win_rate.toFixed(1)}%</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#e2e8f0' }}>{b.actual_win_rate != null ? `${b.actual_win_rate.toFixed(1)}%` : '—'}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#e2e8f0' }}>{b.actual_profit_factor != null ? b.actual_profit_factor.toFixed(2) : '—'}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: b.z_score != null ? (b.z_score >= -1.5 ? '#4ade80' : b.z_score >= -2.5 ? '#facc15' : '#f87171') : '#94a3b8' }}>
                                                        {b.z_score != null ? b.z_score.toFixed(2) : '—'}
                                                    </td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: '#e2e8f0' }}>{b.n_actual_trades}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: b.actual_pnl >= 0 ? '#4ade80' : '#f87171' }}>{formatCurrency(b.actual_pnl)}</td>
                                                    <td style={{ textAlign: 'right', padding: '5px 10px', color: b.tracking_error >= 0 ? '#4ade80' : '#f87171' }}>{formatCurrency(b.tracking_error)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>

                                <div style={{ fontSize: 11, color: '#64748b', padding: '0 4px' }}>
                                    Z-Score: how many standard errors the actual avg trade deviates from expected.
                                    Z &gt; −1.5 = ON TRACK · Z −1.5 to −2.5 = DRIFTING · Z &lt; −2.5 = CRITICAL (pause this bin).
                                </div>
                            </>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default MethodComparison;
