import React, { useState, useEffect, useRef } from 'react';
import Plot from 'react-plotly.js';
import './DiscoveryExplorer.css';

interface Edge {
    account_name: string;
    time_slot: string;
    day_of_week: number;
    total_pnl: number;
    total_trades: number;
    persistence_score: number;
    avg_profit_per_trade: number;
    win_rate: number;
    profit_factor?: number;
    leader_tags?: string[];
}

interface PerformanceMetrics {
    total_pnl: number;
    total_trades: number;
    trading_days: number;
    win_rate: number;
    profit_factor: number;
    wl_ratio: number;
    avg_trade: number;
    sharpe: number;
    sortino: number;
}

interface ValidationData {
    equity_curve: { date: string; pnl: number }[];
    metrics: PerformanceMetrics;
    monte_carlo?: {
        probability_of_profit: number;
        expected_return: number;
        percentiles: { [key: string]: number };
        sample_paths: number[][];
    };
}

const getApiBase = (): string => {
    if (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) {
        return process.env.REACT_APP_API_URL.replace(/\/$/, '');
    }
    return `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000`;
};

const DiscoveryExplorer: React.FC = () => {
    const [symbol, setSymbol] = useState('NQ');
    const [edges, setEdges] = useState<Edge[]>([]);
    const [loading, setLoading] = useState(false);
    const [hasRecentData, setHasRecentData] = useState<boolean | null>(null);
    const [validationLoading, setValidationLoading] = useState(false);
    const [validationData, setValidationData] = useState<ValidationData | null>(null);
    const [minPersistence, setMinPersistence] = useState(60);
    const [minTradesBin, setMinTradesBin] = useState(200);
    const [minAvgProfitBin, setMinAvgProfitBin] = useState(20);
    const [selectedEdges, setSelectedEdges] = useState<number[]>([]);
    const [portfolioData, setPortfolioData] = useState<any>(null);
    const [portfolioLoading, setPortfolioLoading] = useState(false);
    const [validationMode, setValidationMode] = useState<'sliding' | 'expanding'>('expanding');
    const [trainMonths, setTrainMonths] = useState(4);
    const [testMonths, setTestMonths] = useState(1);
    const [selectionLogic, setSelectionLogic] = useState<'classic' | 'statistical' | 'persistence' | 'ensemble'>('persistence');
    const [viewMode, setViewMode] = useState<'table' | 'matrix'>('table');
    const [predictions, setPredictions] = useState<any>(null);
    const [predictionsLoading, setPredictionsLoading] = useState(false);
    const [monteCarloLoading, setMonteCarloLoading] = useState(false);
    const fetchGenerationRef = useRef(0);

    const fetchEdges = async () => {
        const generation = ++fetchGenerationRef.current;
        setLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const API_BASE = getApiBase();
            const url = `${API_BASE}/api/v1/analytics/recommendations/discovery/${symbol}?min_persistence=${minPersistence}&min_trades_total=${minTradesBin}&min_avg_profit=${minAvgProfitBin}&logic=${selectionLogic}&winners_only=${viewMode === 'matrix'}`;
            const response = await fetch(url, { headers, cache: 'no-store' });
            const data = await response.json();
            if (generation !== fetchGenerationRef.current) return;
            if (data.status === 'success') {
                let list = data.data.edges || [];
                const minT = minTradesBin;
                const minA = minAvgProfitBin;
                const minP = minPersistence;
                // Session: no trades 17:00–18:00 NY (market closed); 18:00+ is evening session
                // Ensemble uses its own scoring (conviction/voting); don't apply bin filters or we filter out all results
                list = list.filter((e: Edge) => {
                    const sessionOk = e.time_slot < '17:00' || e.time_slot >= '18:00';
                    if (selectionLogic === 'ensemble') return sessionOk;
                    return sessionOk && e.avg_profit_per_trade >= minA && e.total_trades >= minT && e.persistence_score >= minP;
                });
                if (generation !== fetchGenerationRef.current) return;
                setEdges(list);
                setHasRecentData(data.data.has_recent_data);
            }
        } catch (error) {
            if (generation !== fetchGenerationRef.current) return;
            console.error('Error fetching edges:', error);
        } finally {
            if (generation === fetchGenerationRef.current) setLoading(false);
        }
    };

    const toggleEdgeSelection = (index: number) => {
        setSelectedEdges(prev =>
            prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]
        );
    };

    // Helper to find edge index from matrix cell

    const runPortfolioBacktest = async () => {
        if (selectedEdges.length === 0) return;
        setPortfolioLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const selections = selectedEdges.map(i => edges[i]);
            const API_BASE = getApiBase();
            const response = await fetch(`${API_BASE}/api/v1/analytics/recommendations/backtest/portfolio`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ symbol, edges: selections })
            });
            const data = await response.json();
            if (data.status === 'success') {
                setPortfolioData(data.data);
            }
        } catch (error) {
            console.error('Error running portfolio backtest:', error);
        } finally {
            setPortfolioLoading(false);
        }
    };

    const runValidation = async () => {
        setValidationData(null);
        setValidationLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const selections = selectedEdges.map(i => edges[i]);
            const API_BASE = getApiBase();
            const response = await fetch(`${API_BASE}/api/v1/analytics/recommendations/validation/walk-forward/${symbol}`, {
                method: 'POST',
                headers: { ...headers, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    min_persistence: minPersistence,
                    logic: selectionLogic,
                    mode: validationMode,
                    train_months: trainMonths,
                    test_months: testMonths,
                    allowed_edges: selections.length > 0 ? selections : null
                })
            });
            const data = await response.json().catch(() => ({ status: 'error', message: 'Invalid response' }));
            if (data.status === 'success') {
                setValidationData(data.data);
            } else {
                const msg = !response.ok && (data.detail ?? data.message)
                    ? (typeof data.detail === 'string' ? data.detail : data.message || `Server error ${response.status}`)
                    : (data.message || `Walk-forward failed (${response.status})`);
                alert(msg);
            }
        } catch (error) {
            console.error('Error running validation:', error);
            const msg = error instanceof Error ? error.message : 'Network or server error. Is the backend running?';
            alert(msg);
        } finally {
            setValidationLoading(false);
        }
    };

    const fetchWeeklyPredictions = async () => {
        setPredictionsLoading(true);
        try {
            const API_BASE = getApiBase();
            const url = `${API_BASE}/api/v1/analytics/recommendations/predict-week/${symbol}?lookback_weeks=13`;
            const response = await fetch(url);
            const data = await response.json();
            if (data.status === 'success') {
                setPredictions(data.data);
            }
        } catch (e) {
            console.error('Error fetching roadmap:', e);
        } finally {
            setPredictionsLoading(false);
        }
    };

    const handleExportCSV = async () => {
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const selections = selectedEdges.map(i => edges[i]);
            const API_BASE = getApiBase();

            const response = await fetch(`${API_BASE}/api/v1/analytics/recommendations/validation/walk-forward/export/${symbol}`, {
                method: 'POST',
                headers: { ...headers, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    min_persistence: minPersistence,
                    logic: selectionLogic,
                    mode: validationMode,
                    train_months: trainMonths,
                    test_months: testMonths,
                    allowed_edges: selections.length > 0 ? selections : null
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: null }));
                const detail = errorData.detail ?? errorData.message;
                const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: any) => e?.msg ?? e).join(', ') : `Server error: ${response.status}`;
                if (response.status === 404) {
                    throw new Error(`API not found (404). Is the backend running? Start it with: python main.py (from project root) then try again.`);
                }
                throw new Error(msg);
            }

            const data = await response.json();
            if (data.status !== 'success') {
                alert(data.message || 'Export failed.');
                return;
            }
            if (data.data == null) {
                alert('Export returned no data.');
                return;
            }
            const trades = Array.isArray(data.data) ? data.data : [];
            const fieldNames = trades.length > 0 ? Object.keys(trades[0]) : ['date', 'time', 'exit_time', 'permutation', 'side', 'quantity', 'entry_price', 'exit_price', 'pnl'];

            const escape = (val: any) => {
                const str = String(val === null || val === undefined ? '' : val);
                return `"${str.replace(/"/g, '""')}"`;
            };

            const csvContent = [
                fieldNames.map(escape).join(','),
                ...trades.map((t: any) => fieldNames.map(f => escape(t[f])).join(','))
            ].join('\n');

            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', `wf_oos_trades_${symbol}_${new Date().toISOString().split('T')[0]}.csv`);
            link.click();
            URL.revokeObjectURL(url);
            if (trades.length === 0) {
                alert('No OOS trades found; downloaded CSV with headers only.');
            }
        } catch (error) {
            console.error('Error exporting CSV:', error);
            let msg = error instanceof Error ? error.message : 'Failed to export trades.';
            if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Load failed')) {
                msg = `Cannot reach the API at ${getApiBase()}. Start the backend with: python main.py (from project root).`;
            }
            alert(msg);
        }
    };

    const runMonteCarloOOS = async () => {
        if (!validationData) {
            alert('Run Walk-Forward Analysis first to get OOS results, then run Monte Carlo.');
            return;
        }
        setMonteCarloLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const selections = selectedEdges.map(i => edges[i]);
            const API_BASE = getApiBase();
            const response = await fetch(`${API_BASE}/api/v1/analytics/recommendations/validation/walk-forward/monte-carlo/${symbol}`, {
                method: 'POST',
                headers: { ...headers, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    min_persistence: minPersistence,
                    logic: selectionLogic,
                    mode: validationMode,
                    train_months: trainMonths,
                    test_months: testMonths,
                    allowed_edges: selections.length > 0 ? selections : null
                })
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: null }));
                const detail = errorData.detail ?? errorData.message;
                const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: any) => e?.msg ?? e).join(', ') : `Server error: ${response.status}`;
                if (response.status === 404) {
                    throw new Error(`API not found (404). Is the backend running? Start it with: python main.py (from project root) then try again.`);
                }
                throw new Error(msg);
            }
            const data = await response.json();
            if (data.status === 'success' && data.data?.monte_carlo) {
                setValidationData(prev => prev ? { ...prev, monte_carlo: data.data.monte_carlo } : null);
            } else {
                alert(data.message || 'Monte Carlo failed. Run Walk-Forward Analysis first.');
            }
        } catch (error) {
            console.error('Error running Monte Carlo:', error);
            let msg = error instanceof Error ? error.message : 'Failed to run Monte Carlo.';
            if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Load failed')) {
                msg = `Cannot reach the API at ${getApiBase()}. Start the backend with: python main.py (from project root).`;
            }
            alert(msg);
        } finally {
            setMonteCarloLoading(false);
        }
    };

    useEffect(() => {
        fetchEdges();
    }, [symbol, minPersistence, minTradesBin, minAvgProfitBin, selectionLogic, viewMode, fetchEdges]);

    // When ranking logic or symbol changes, the grid refreshes with new edges. Clear selection and WF results
    // so indices aren't stale and Export/Monte Carlo run with the current mode (or autonomous discovery if none selected).
    useEffect(() => {
        setSelectedEdges([]);
        setValidationData(null);
    }, [selectionLogic, symbol]);

    // DB stores day_of_week using Python weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 6=Sun
    // This matches the Recommendations page convention exactly.
    const DAY_NAME_MAP: Record<number, string> = { 0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 6: 'Sun' };
    const getDayName = (dow: number) => DAY_NAME_MAP[dow] ?? String(dow);

    // Matrix View Component
    const MatrixView = () => {
        const timeSlots = Array.from(new Set(edges.map(e => e.time_slot))).sort();
        // Column order: Sun (6) then Mon(0)..Fri(4) — matches Recommendations page & DB weekday convention
        const days = [6, 0, 1, 2, 3, 4];

        return (
            <div className="discovery-matrix-container">
                <table className="discovery-matrix">
                    <thead>
                        <tr>
                            <th>Time</th>
                            {days.map(d => <th key={d}>{getDayName(d)}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        {timeSlots.map(time => (
                            <tr key={time}>
                                <td className="time-col">{time}</td>
                                {days.map(dow => {
                                    const binEdges = edges.filter(e => e.time_slot === time && e.day_of_week === dow);

                                    return (
                                        <td
                                            key={dow}
                                            className={`matrix-cell ${binEdges.length > 0 ? 'has-edge' : ''}`}
                                        >
                                            {binEdges.length > 0 ? (
                                                <div className="bin-contenders">
                                                    {binEdges.map(edge => {
                                                        const edgeIndex = edges.indexOf(edge);
                                                        const isSelected = selectedEdges.includes(edgeIndex);

                                                        return (
                                                            <div
                                                                key={edgeIndex}
                                                                className={`edge-contender ${isSelected ? 'selected' : ''}`}
                                                                onClick={() => toggleEdgeSelection(edgeIndex)}
                                                                title={`Account: ${edge.account_name}\nLogic Leader: ${edge.leader_tags?.join(', ')}\nPnL: $${edge.avg_profit_per_trade}\nTrades: ${edge.total_trades}\nWin Rate: ${edge.win_rate}%\nPersistence: ${edge.persistence_score}%`}
                                                            >
                                                                <div className="acct">{edge.account_name}</div>
                                                                <div className="stat-grid">
                                                                    <span className="stat-pnl" title="Avg Profit">${edge.avg_profit_per_trade.toFixed(1)}</span>
                                                                    <span className="stat-count" title="Trades Count">{edge.total_trades}</span>
                                                                    <span className="stat-wl" title="Win Rate">{edge.win_rate.toFixed(0)}%</span>
                                                                    <span className="stat-win" title="Persistence">{edge.persistence_score.toFixed(0)}%</span>
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            ) : '-'}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    return (
        <div className="discovery-explorer">
            <div className="discovery-header">
                <div className="discovery-title-row">
                    <h2>Edge Discovery Explorer</h2>
                    <div className="header-controls">
                        <div className="control-group">
                            <label>Instrument</label>
                            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                                <option value="NQ">NQ (Nasdaq)</option>
                                <option value="ES">ES (S&P 500)</option>
                                <option value="CL">CL (Crude Oil)</option>
                                <option value="FDAX">FDAX (DAX)</option>
                            </select>
                        </div>

                        <div className="control-group">
                            <label>Ranking Logic</label>
                            <div className="mode-tabs">
                                {(['persistence', 'classic', 'statistical', 'ensemble'] as const).map(l => (
                                    <button
                                        key={l}
                                        className={`mode-tab ${selectionLogic === l ? 'active' : ''}`}
                                        onClick={() => setSelectionLogic(l)}
                                    >
                                        {l.charAt(0).toUpperCase() + l.slice(1)}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="control-group">
                            <label>View Mode</label>
                            <div className="mode-tabs">
                                <button className={`mode-tab ${viewMode === 'table' ? 'active' : ''}`} onClick={() => setViewMode('table')}>List</button>
                                <button className={`mode-tab ${viewMode === 'matrix' ? 'active' : ''}`} onClick={() => setViewMode('matrix')}>Matrix</button>
                            </div>
                        </div>

                        <button className="refresh-button" onClick={fetchEdges} disabled={loading}>
                            {loading ? 'Refreshing...' : 'Refresh'}
                        </button>
                    </div>
                </div>
            </div>

            {
                hasRecentData === false && (
                    <div className="warning-box" style={{ margin: '15px 20px', padding: '15px', background: '#ffebee', color: '#c62828', borderRadius: '4px', borderLeft: '4px solid #ef5350' }}>
                        <strong>Alert: No Recent Data!</strong> No accounts with data from the last 30 days were found for this symbol. Please import more data using the binary importer.
                    </div>
                )
            }

            {
                loading && (
                    <div className="discovery-progress-container">
                        <div className="discovery-progress-bar"></div>
                        <span className="discovery-progress-text">Analyzing Persistence Matrices...</span>
                    </div>
                )
            }

            <div className="discovery-layout">
                <div className="discovery-main">
                    <section className="section table-section">
                        <div className="section-header">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div>
                                    <h3>{selectionLogic === 'persistence' ? 'High-Persistence All-Stars' :
                                        selectionLogic === 'statistical' ? 'Statistical EV Rankings' :
                                            selectionLogic === 'ensemble' ? 'Ensemble Consensus' : 'Classic Performance Rankings'}</h3>
                                    <p>{selectionLogic === 'persistence' ? 'The "DNA" of consistency: Account/Day/Time slots that win most months.' :
                                        selectionLogic === 'statistical' ? 'Expected Value leaders: Maximizing (Avg Trade * Win Rate).' :
                                            'Strategies ranked by historical profit and volume.'}</p>
                                </div>
                                <div className="table-actions">
                                    <div className="matrix-legend">
                                        <div className="legend-item"><div className="legend-color" style={{ backgroundColor: '#d63384' }}></div><span>Avg PnL</span></div>
                                        <div className="legend-item"><div className="legend-color" style={{ backgroundColor: '#fd7e14' }}></div><span>Trades</span></div>
                                        <div className="legend-item"><div className="legend-color" style={{ backgroundColor: '#212529' }}></div><span>W/L %</span></div>
                                        <div className="legend-item"><div className="legend-color" style={{ backgroundColor: '#198754' }}></div><span>Persistence</span></div>
                                    </div>
                                    <button className="text-button" onClick={() => setSelectedEdges(edges.map((_, i) => i))}>Select All</button>
                                    <span className="divider">|</span>
                                    <button className="text-button" onClick={() => setSelectedEdges([])}>Clear</button>
                                </div>
                            </div>
                        </div>

                        {viewMode === 'matrix' ? (
                            <MatrixView />
                        ) : (
                            <div className="table-container">
                                <table className="discovery-table">
                                    <thead>
                                        <tr>
                                            <th>Account</th>
                                            <th>Day</th>
                                            <th>Slot</th>
                                            <th>{selectionLogic === 'persistence' ? 'Persistence' : 'Win Rate'}</th>
                                            <th>PnL</th>
                                            <th>Trades</th>
                                            <th>Avg</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {edges.map((edge, i) => (
                                            <tr
                                                key={i}
                                                className={`${edge.persistence_score >= 80 ? 'top-tier' : ''} ${selectedEdges.includes(i) ? 'selected-row' : ''}`}
                                                onClick={() => toggleEdgeSelection(i)}
                                                style={{ cursor: 'pointer' }}
                                            >
                                                <td title={edge.account_name}>{edge.account_name}</td>
                                                <td>{getDayName(edge.day_of_week)}</td>
                                                <td>{edge.time_slot}</td>
                                                <td className="persistence-cell">
                                                    <div className="persistence-bar-bg">
                                                        <div
                                                            className="persistence-bar-fg"
                                                            style={{ width: `${edge.persistence_score}%`, backgroundColor: edge.persistence_score > 70 ? '#4caf50' : '#ff9800' }}
                                                        ></div>
                                                    </div>
                                                    {edge.persistence_score}%
                                                </td>
                                                <td className={edge.total_pnl >= 0 ? 'pos' : 'neg'}>
                                                    ${edge.total_pnl > 1000 ? (edge.total_pnl / 1000).toFixed(1) + 'k' : edge.total_pnl.toFixed(0)}
                                                </td>
                                                <td>{edge.total_trades}</td>
                                                <td>${edge.avg_profit_per_trade.toFixed(0)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </section>
                </div>

                <div className="discovery-sidebar">
                    <section className="section validation-section">
                        <div className="section-header">
                            <h3>Portfolio Validation (Static)</h3>
                            <p>Click rows in the table to test their combined historical performance.</p>
                        </div>

                        <div className="portfolio-controls" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                            <div style={{ padding: '12px 14px', background: '#f8f9fa', borderRadius: '8px', border: '1px solid #eee' }}>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: '#495057', marginBottom: '10px' }}>Bin filters (grid / backtest)</div>
                                {selectionLogic === 'ensemble' && (
                                    <p style={{ fontSize: '11px', color: '#6c757d', marginBottom: '10px', fontStyle: 'italic' }}>
                                        Ensemble mode uses its own scoring (multi-window consensus). Only <strong>Min trades per bin</strong> is used for discovery; persistence and avg profit use fixed internal thresholds. These sliders still apply to Backtest and Walk-Forward if you run them.
                                    </p>
                                )}
                                <div className="control-group" style={{ marginBottom: '10px' }}>
                                    <label>Min persistence: {minPersistence}%</label>
                                    <input
                                        type="range"
                                        min={50}
                                        max={95}
                                        step={5}
                                        value={minPersistence}
                                        onChange={(e) => setMinPersistence(parseInt(e.target.value))}
                                        style={{ width: '100%' }}
                                    />
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                                    <div className="control-group">
                                        <label title="Orange number in grid">Min trades per bin</label>
                                        <input
                                            type="number"
                                            className="text-input"
                                            min={0}
                                            value={minTradesBin}
                                            onChange={(e) => setMinTradesBin(Math.max(0, parseInt(e.target.value) || 0))}
                                            style={{ width: '100%' }}
                                        />
                                    </div>
                                    <div className="control-group">
                                        <label title="Red number in grid">Min avg profit per bin ($)</label>
                                        <input
                                            type="number"
                                            className="text-input"
                                            min={0}
                                            step={1}
                                            value={minAvgProfitBin}
                                            onChange={(e) => setMinAvgProfitBin(Math.max(0, parseFloat(e.target.value) || 0))}
                                            style={{ width: '100%' }}
                                        />
                                    </div>
                                </div>
                            </div>
                            <button
                                className="primary-button"
                                onClick={runPortfolioBacktest}
                                disabled={selectedEdges.length === 0 || portfolioLoading}
                            >
                                {portfolioLoading ? 'Calculating...' : `Backtest Selection (${selectedEdges.length})`}
                            </button>
                        </div>

                        {portfolioData && (
                            <div className="validation-results">
                                <div className="metrics-grid">
                                    <div className="stat-card">
                                        <label>Total PnL</label>
                                        <span className={portfolioData.metrics.total_pnl >= 0 ? 'pos' : 'neg'}>
                                            ${portfolioData.metrics.total_pnl.toLocaleString()}
                                        </span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Win%</label>
                                        <span>{portfolioData.metrics.win_rate}%</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Profit Factor</label>
                                        <span>{portfolioData.metrics.profit_factor}</span>
                                    </div>

                                    <div className="stat-card">
                                        <label>Trades</label>
                                        <span>{portfolioData.metrics.total_trades}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Trading Days</label>
                                        <span>{portfolioData.metrics.trading_days}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Avg Trade</label>
                                        <span>${portfolioData.metrics.avg_trade.toFixed(0)}</span>
                                    </div>

                                    <div className="stat-card">
                                        <label>W/L Ratio</label>
                                        <span>{portfolioData.metrics.wl_ratio}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Sharpe</label>
                                        <span>{portfolioData.metrics.sharpe}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Sortino</label>
                                        <span>{portfolioData.metrics.sortino}</span>
                                    </div>
                                </div>
                                {portfolioData.equity_curve && portfolioData.equity_curve.length > 0 ? (
                                    <div className="validation-chart">
                                        <Plot
                                            data={[{
                                                x: portfolioData.equity_curve.map((d: any) => d.date),
                                                y: portfolioData.equity_curve.map((d: any) => d.pnl),
                                                type: 'scatter', mode: 'lines', name: 'Portfolio',
                                                line: { color: '#4caf50', width: 2 }
                                            }]}
                                            layout={{
                                                autosize: true, height: 300, margin: { l: 50, r: 10, t: 10, b: 30 },
                                                paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                                                xaxis: { showgrid: false, tickfont: { size: 9 } },
                                                yaxis: { gridcolor: '#eee', tickfont: { size: 9 } }
                                            }}
                                            config={{ responsive: true, displayModeBar: false }}
                                        />
                                    </div>
                                ) : (
                                    <div className="empty-chart-msg" style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                                        📉 No trades found matching these selections in historical data.
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="discovery-divider" style={{ margin: '20px 0', borderTop: '1px solid #ddd' }}></div>

                        <h3>Walk-Forward Validation</h3>
                        <p>Simulate real-time edge discovery with a rolling window.</p>

                        <div className="validation-controls">
                            <div className="discovery-wf-setup" style={{ marginTop: '0', padding: '15px', background: '#f8f9fa', borderRadius: '8px' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                                    <div className="control-group">
                                        <label>Train Log (Months)</label>
                                        <input
                                            type="number"
                                            className="text-input"
                                            value={trainMonths}
                                            onChange={(e) => setTrainMonths(parseInt(e.target.value))}
                                        />
                                    </div>
                                    <div className="control-group">
                                        <label>Test Step (Month)</label>
                                        <input
                                            type="number"
                                            className="text-input"
                                            value={testMonths}
                                            onChange={(e) => setTestMonths(parseInt(e.target.value))}
                                        />
                                    </div>
                                </div>

                                <div className="control-group" style={{ marginTop: '15px' }}>
                                    <label>Selection Logic</label>
                                    <select
                                        value={validationMode}
                                        onChange={(e) => setValidationMode(e.target.value as any)}
                                        className="text-input"
                                        style={{ height: '40px' }}
                                    >
                                        <option value="expanding">Expanding (All History)</option>
                                        <option value="sliding">Sliding (Fix Window)</option>
                                    </select>
                                </div>

                                <button
                                    className="primary-button"
                                    onClick={runValidation}
                                    disabled={validationLoading}
                                    style={{ width: '100%', marginTop: '15px', backgroundColor: '#28a745' }}
                                >
                                    {validationLoading ? 'Validating...' : 'Run Walk-Forward Analysis'}
                                </button>
                            </div>
                        </div>

                        {validationData && validationData.metrics.total_trades === 0 && (
                            <div className="warning-box" style={{ marginTop: '15px', padding: '10px', background: '#fff3cd', color: '#856404', borderRadius: '4px', fontSize: '12px' }}>
                                <strong>No Trades Found!</strong> Try reducing the "Train Log" window or the bin filters (min persistence, min trades, min avg profit) above.
                            </div>
                        )}

                        {validationLoading && (
                            <div className="validation-progress-container">
                                <div className="validation-progress-bar"></div>
                            </div>
                        )}

                        {validationData && (
                            <div className="validation-results">
                                <div className="metrics-grid">
                                    <div className="stat-card">
                                        <label>Total PnL</label>
                                        <span className={validationData.metrics.total_pnl >= 0 ? 'pos' : 'neg'}>
                                            ${validationData.metrics.total_pnl.toLocaleString()}
                                        </span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Win%</label>
                                        <span>{validationData.metrics.win_rate}%</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Profit Factor</label>
                                        <span>{validationData.metrics.profit_factor}</span>
                                    </div>

                                    <div className="stat-card">
                                        <label>Trades</label>
                                        <span>{validationData.metrics.total_trades}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Trading Days</label>
                                        <span>{validationData.metrics.trading_days}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Avg Trade</label>
                                        <span>${validationData.metrics.avg_trade.toFixed(0)}</span>
                                    </div>

                                    <div className="stat-card">
                                        <label>W/L Ratio</label>
                                        <span>{validationData.metrics.wl_ratio}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Sharpe</label>
                                        <span>{validationData.metrics.sharpe}</span>
                                    </div>
                                    <div className="stat-card">
                                        <label>Sortino</label>
                                        <span>{validationData.metrics.sortino}</span>
                                    </div>
                                </div>

                                <div className="validation-chart">
                                    <Plot
                                        data={[
                                            {
                                                x: validationData.equity_curve.map(d => d.date),
                                                y: validationData.equity_curve.map(d => d.pnl),
                                                type: 'scatter',
                                                mode: 'lines',
                                                name: 'Equity Curve',
                                                line: { color: '#2196f3', width: 2 }
                                            }
                                        ]}
                                        layout={{
                                            autosize: true,
                                            height: 380,
                                            margin: { l: 60, r: 20, t: 10, b: 40 },
                                            paper_bgcolor: 'transparent',
                                            plot_bgcolor: 'transparent',
                                            xaxis: {
                                                showgrid: false,
                                                tickfont: { size: 10 }
                                            },
                                            yaxis: {
                                                gridcolor: '#eee',
                                                tickfont: { size: 10 }
                                            }
                                        }}
                                        config={{ responsive: true, displayModeBar: false }}
                                    />
                                </div>

                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center', marginBottom: '20px', alignItems: 'center' }}>
                                    <button onClick={handleExportCSV} className="text-button" style={{ fontSize: '12px', opacity: 0.9 }}>📥 Export OOS Trade List (CSV)</button>
                                    <span style={{ color: '#999', fontSize: '12px' }}>|</span>
                                    <button
                                        onClick={runMonteCarloOOS}
                                        disabled={monteCarloLoading}
                                        className="text-button"
                                        style={{ fontSize: '12px', opacity: 0.9 }}
                                        title="Run Monte Carlo simulation on the current OOS trades"
                                    >
                                        {monteCarloLoading ? 'Running MC…' : '🎲 Run Monte Carlo (OOS)'}
                                    </button>
                                </div>

                                {validationData.monte_carlo && (
                                    <div className="mc-oos-section" style={{ marginTop: '20px', padding: '15px', background: 'rgba(33, 150, 243, 0.03)', borderRadius: '12px', border: '1px solid rgba(33, 150, 243, 0.1)' }}>
                                        <h4 style={{ marginBottom: '12px' }}>🎲 Monte Carlo Risk (OOS)</h4>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '15px' }}>
                                            <div className="stat-card" style={{ background: '#fff' }}>
                                                <label>Prob. of Profit</label>
                                                <span style={{ fontSize: '20px', color: '#2196f3' }}>{validationData.monte_carlo.probability_of_profit}%</span>
                                            </div>
                                            <div className="stat-card" style={{ background: '#fff' }}>
                                                <label>Expected Ret.</label>
                                                <span style={{ fontSize: '18px' }}>${validationData.monte_carlo.expected_return.toLocaleString()}</span>
                                            </div>
                                        </div>
                                        <Plot
                                            data={[
                                                ...validationData.monte_carlo.sample_paths.slice(0, 50).map((path, i) => ({
                                                    y: path,
                                                    type: 'scatter' as any, mode: 'lines' as any,
                                                    line: { color: 'rgba(33, 150, 243, 0.08)', width: 1 },
                                                    hoverinfo: 'none' as any, showlegend: false
                                                })),
                                                {
                                                    y: Array(validationData.monte_carlo.sample_paths[0].length).fill(0),
                                                    type: 'scatter' as any, mode: 'lines' as any,
                                                    line: { color: '#000', width: 1, dash: 'dash' as any },
                                                    showlegend: false
                                                }
                                            ]}
                                            layout={{ autosize: true, height: 180, margin: { l: 40, r: 10, t: 10, b: 30 }, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', xaxis: { showgrid: false }, yaxis: { gridcolor: '#f0f0f0' } }}
                                            config={{ responsive: true, displayModeBar: false }}
                                        />
                                        <p style={{ fontSize: '10px', color: '#888', fontStyle: 'italic', marginTop: '10px' }}>Simulated across 5,000 permutations of unseen data.</p>
                                    </div>
                                )}

                                <div className="forecast-roadmap" style={{ marginTop: '30px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                                        <h4 style={{ margin: 0 }}>🔮 Weekly Prediction Roadmap</h4>
                                        <button onClick={fetchWeeklyPredictions} disabled={predictionsLoading} className="text-button" style={{ fontSize: '12px' }}>
                                            {predictionsLoading ? '...' : 'Update'}
                                        </button>
                                    </div>
                                    {predictions ? (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '8px' }}>
                                            {Object.entries(predictions.predictions).flatMap(([slot, days]: [string, any]) =>
                                                Object.entries(days).map(([dow, pred]: [string, any]) => (
                                                    <div key={`${slot}-${dow}`} style={{ padding: '8px 12px', background: '#fff', borderRadius: '8px', border: '1px solid #eee', borderLeft: `4px solid ${pred.confidence === 'High' ? '#10b981' : '#f59e0b'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                        <div>
                                                            <div style={{ fontSize: '10px', color: '#888' }}>{getDayName(parseInt(dow))} {slot}</div>
                                                            <div style={{ fontSize: '13px', fontWeight: 'bold' }}>{pred.predicted_account}</div>
                                                        </div>
                                                        <div style={{ textAlign: 'right' }}>
                                                            <div style={{ fontSize: '11px', color: pred.confidence === 'High' ? '#10b981' : '#f59e0b', fontWeight: 'bold' }}>{pred.confidence}</div>
                                                            <div style={{ fontSize: '10px', color: '#aaa' }}>{(pred.agreement_ratio * 100).toFixed(0)}%</div>
                                                        </div>
                                                    </div>
                                                ))
                                            ).slice(0, 50)}
                                        </div>
                                    ) : (
                                        <p style={{ fontSize: '12px', color: '#999', textAlign: 'center' }}>Click Update to see this week's winners.</p>
                                    )}
                                </div>

                                <div className="logic-hint" style={{ marginTop: '25px', padding: '15px', borderLeft: '4px solid #2196f3', backgroundColor: 'rgba(33, 150, 243, 0.05)' }}>
                                    <p style={{ marginBottom: '10px' }}><strong>Note 1 (Timing):</strong> Uses <strong>Calendar Months</strong>. The engine trains on the past month(s) and tests on the next, sliding forward 1 month at a time to ensure no look-ahead bias.</p>
                                    <p style={{ marginBottom: '10px' }}><strong>Note 2 (Selection Logic):</strong> Manual bin selections (Account/Day/Hour) define your <strong>Allowed Universe</strong>. However, an edge is only "traded" in the next month if it <i>also</i> passes the <strong>{selectionLogic.toUpperCase()}</strong> threshold during its specific training window. This simulates a real trader who only sticks with their picks as long as they remain consistent.</p>
                                    <p><strong>Note 3 (Highest Persistence & PnL):</strong> For every unique Time/Day slot, the engine selects the single best account based on <strong>Full Window Consistency</strong> (must be active and green across the entire training period). If scores are tied, it selects the account with the <b>highest Profit</b>. Minimum 5 trades required per window to filter out noise.</p>
                                </div>
                            </div>
                        )}
                    </section>
                </div>
            </div>

            <section className="section methodology-section" style={{ marginTop: '30px' }}>
                <h3>Methodology & FAQ</h3>
                <div className="methodology-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                    <div className="method-card">
                        <h4>Monte Carlo OOS</h4>
                        <p style={{ fontSize: '13px', color: '#666' }}>Unlike traditional MC, this simulates permutations of <strong>Out-of-Sample</strong> trades. It calculates the probability that the strategy's robustness actually translates into forward returns over a 21-day horizon.</p>
                    </div>
                    <div className="method-card">
                        <h4>Roadmap Prediction</h4>
                        <p style={{ fontSize: '13px', color: '#666' }}>Uses a rolling-weighted consensus across 2, 4, 8, and 13-week windows to identify which account is currently dominant in each time slot, providing guidance for the upcoming week.</p>
                    </div>
                    <div className="method-card">
                        <h4>Static vs. Walk-Forward</h4>
                        <p style={{ fontSize: '13px', color: '#666' }}><strong>Static Backtest:</strong> Hindsight view. Shows what happens if you traded your favorite picks across their entire history. Used to verify the "DNA" of an edge.</p>
                        <p style={{ fontSize: '13px', color: '#666' }}><strong>Walk-Forward:</strong> Real-time simulation. Simulates what you would have picked each month using <i>only</i> data available at that time.</p>
                    </div>
                </div>
            </section>
        </div >
    );
};

export default DiscoveryExplorer;
