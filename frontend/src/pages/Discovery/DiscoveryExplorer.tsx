import React, { useState, useEffect } from 'react';
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
}

const DiscoveryExplorer: React.FC = () => {
    const [symbol, setSymbol] = useState('NQ');
    const [edges, setEdges] = useState<Edge[]>([]);
    const [loading, setLoading] = useState(false);
    const [hasRecentData, setHasRecentData] = useState<boolean | null>(null);
    const [validationLoading, setValidationLoading] = useState(false);
    const [validationData, setValidationData] = useState<ValidationData | null>(null);
    const [minPersistence, setMinPersistence] = useState(70);
    const [selectedEdges, setSelectedEdges] = useState<number[]>([]);
    const [portfolioData, setPortfolioData] = useState<any>(null);
    const [portfolioLoading, setPortfolioLoading] = useState(false);
    const [validationMode, setValidationMode] = useState<'sliding' | 'expanding'>('expanding');
    const [trainMonths, setTrainMonths] = useState(4);
    const [testMonths, setTestMonths] = useState(1);
    const [selectionLogic, setSelectionLogic] = useState<'classic' | 'statistical' | 'persistence' | 'ensemble'>('persistence');
    const [viewMode, setViewMode] = useState<'table' | 'matrix'>('table');

    const fetchEdges = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const API_BASE = `http://${window.location.hostname}:8000`;
            const url = `${API_BASE}/api/v1/analytics/recommendations/discovery/${symbol}?min_persistence=${minPersistence}&logic=${selectionLogic}&winners_only=${viewMode === 'matrix'}`;
            const response = await fetch(url, { headers });
            const data = await response.json();
            if (data.status === 'success') {
                setEdges(data.data.edges);
                setHasRecentData(data.data.has_recent_data);
            }
        } catch (error) {
            console.error('Error fetching edges:', error);
        } finally {
            setLoading(false);
        }
    };

    const toggleEdgeSelection = (index: number) => {
        setSelectedEdges(prev =>
            prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]
        );
    };

    // Helper to find edge index from matrix cell
    const selectFromMatrix = (time: string, dow: number) => {
        const index = edges.findIndex(e => e.time_slot === time && e.day_of_week === dow);
        if (index !== -1) {
            toggleEdgeSelection(index);
        }
    };

    const runPortfolioBacktest = async () => {
        if (selectedEdges.length === 0) return;
        setPortfolioLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const selections = selectedEdges.map(i => edges[i]);
            const API_BASE = `http://${window.location.hostname}:8000`;
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
        setValidationLoading(true);
        try {
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const selections = selectedEdges.map(i => edges[i]);
            const API_BASE = `http://${window.location.hostname}:8000`;
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
            const data = await response.json();
            if (data.status === 'success') {
                setValidationData(data.data);
            }
        } catch (error) {
            console.error('Error running validation:', error);
        } finally {
            setValidationLoading(false);
        }
    };

    useEffect(() => {
        fetchEdges();
    }, [symbol, minPersistence, selectionLogic, viewMode]);

    const getDayName = (dow: number) => {
        const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        return days[dow] || dow;
    };

    // Matrix View Component
    const MatrixView = () => {
        const timeSlots = Array.from(new Set(edges.map(e => e.time_slot))).sort();
        const days = [0, 1, 2, 3, 4, 5]; // Sun-Fri

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

                        <div className="portfolio-controls">
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
                            {selectionLogic === 'persistence' && (
                                <div className="control-group">
                                    <label>Min Persistence Threshold: {minPersistence}%</label>
                                    <input
                                        type="range"
                                        min="50" max="95" step="5"
                                        value={minPersistence}
                                        onChange={(e) => setMinPersistence(parseInt(e.target.value))}
                                    />
                                </div>
                            )}

                            <div className="discovery-wf-setup" style={{ marginTop: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '8px' }}>
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
                                <strong>No Trades Found!</strong> Try reducing the "Train Log" window or the "Min Persistence" threshold.
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
                                            height: 450,
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
                                <div className="logic-hint" style={{ marginTop: '15px', padding: '15px', borderLeft: '4px solid #2196f3', backgroundColor: 'rgba(33, 150, 243, 0.05)' }}>
                                    <p style={{ marginBottom: '10px' }}><strong>Note 1 (Timing):</strong> Uses <strong>Calendar Months</strong>. The engine trains on the past month(s) and tests on the next, sliding forward 1 month at a time to ensure no look-ahead bias.</p>
                                    <p style={{ marginBottom: '10px' }}><strong>Note 2 (Selection Logic):</strong> Manual bin selections (Account/Day/Hour) define your <strong>Allowed Universe</strong>. However, an edge is only "traded" in the next month if it <i>also</i> passes the <strong>{selectionLogic.toUpperCase()}</strong> threshold during its specific training window. This simulates a real trader who only sticks with their picks as long as they remain consistent.</p>
                                    <p><strong>Note 3 (Highest Persistence & PnL):</strong> For every unique Time/Day slot, the engine selects the single best account based on <strong>Full Window Consistency</strong> (must be active and green across the entire training period). If scores are tied, it selects the account with the <b>highest Profit</b>. Minimum 5 trades required per window to filter out noise.</p>
                                </div>
                            </div>
                        )}
                    </section>
                </div>
            </div>

            <section className="section methodology-section" style={{ marginTop: '20px' }}>
                <h3>Methodology & FAQ</h3>
                <div className="methodology-grid">
                    <div className="method-card">
                        <h4>Where is the data from?</h4>
                        <p>All metrics (Win%, Avg PnL, Trades) are calculated from your <strong>All-Time Trade History</strong>. These are the "All Stars" that have proven their consistency over the entire life of the account.</p>
                    </div>
                    <div className="method-card">
                        <h4>Static vs. Walk-Forward</h4>
                        <p><strong>Static Backtest:</strong> This is "Hindsight". It shows what happens if you traded your favorite picks across their entire history. Used to verify the DNA of an edge.</p>
                        <p><strong>Walk-Forward:</strong> This is "Real-Time Simulation". It simulates what you would have picked each month using <i>only</i> data that was available at that time.</p>
                    </div>
                    <div className="method-card">
                        <h4>Expanding Window Mode</h4>
                        <p>This answers the question: "If I pick the best all-time performers every month, how do they perform in the next month?" It avoids the trap of 'chasing ghosts' by looking for deep, structural consistency.</p>
                    </div>
                </div>
            </section>
        </div >
    );
};

export default DiscoveryExplorer;
