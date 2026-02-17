import React, { useState, useEffect } from 'react';
import './AccountManagement.css';
import './AccountManagementTrades.css';

interface AccountSummary {
    account_name: string;
    symbol: string;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    total_pnl: number;
    avg_pnl: number;
    first_trade_date: string | null;
    last_trade_date: string | null;
    days_since_last_trade: number | null;
    best_day_of_week: number | null;
    best_hour_of_day: number | null;
    is_active: boolean;
}

interface ManagementResponse {
    accounts: AccountSummary[];
    total_accounts: number;
    stale_accounts: number;
}

const AccountManagement: React.FC = () => {
    const [data, setData] = useState<ManagementResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [staleThreshold, setStaleThreshold] = useState(30); // Default to 30 days (1 month)
    const [importingAccount, setImportingAccount] = useState<string | null>(null);
    const [importText, setImportText] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [importResult, setImportResult] = useState<any>(null);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [filterSymbol, setFilterSymbol] = useState<string>('ALL');
    const [validationResult, setValidationResult] = useState<any>(null);
    const [validatingAccount, setValidatingAccount] = useState<string | null>(null);
    const [validatingSymbol, setValidatingSymbol] = useState<string | null>(null);
    const [pendingPrune, setPendingPrune] = useState<{ account: string, criteria: string } | null>(null);
    const [cleanAccounts, setCleanAccounts] = useState<Record<string, boolean>>(() => {
        const saved = localStorage.getItem('cleanAccounts');
        try {
            return saved ? JSON.parse(saved) : {};
        } catch (e) {
            console.error('Failed to parse saved shield status:', e);
            return {};
        }
    });

    useEffect(() => {
        localStorage.setItem('cleanAccounts', JSON.stringify(cleanAccounts));
    }, [cleanAccounts]);

    const [pendingDeleteAccount, setPendingDeleteAccount] = useState<string | null>(null);
    const [viewingTradesAccount, setViewingTradesAccount] = useState<string | null>(null);
    const [recentTrades, setRecentTrades] = useState<any[]>([]);
    const [tradesLoading, setTradesLoading] = useState(false);

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/accounts/management?stale_threshold_days=${staleThreshold}`);
            if (!response.ok) throw new Error('Failed to fetch account management data');
            const result = await response.json();
            setData(result);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [staleThreshold]);

    const handleImportPreview = async () => {
        if (!importText.trim()) return;
        setPreviewLoading(true);
        setError(null);
        setImportResult(null);
        try {
            const response = await fetch('http://localhost:8000/api/v1/trades/import-preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: importText }),
            });
            if (!response.ok) throw new Error('Preview failed');
            const data = await response.json();
            setImportResult(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setPreviewLoading(false);
        }
    };

    const handleImportSubmit = async () => {
        if (!importText.trim()) return;
        setIsSaving(true);
        setSaveStatus('idle');
        try {
            const response = await fetch('http://localhost:8000/api/v1/trades/import-paste', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: importText }),
            });
            if (!response.ok) throw new Error('Import failed');
            const data = await response.json();
            setImportResult(data);
            setSaveStatus('success');
            if (data.new_trades > 0) {
                // Clear validation status for updated accounts
                if (data.trades && data.trades.length > 0) {
                    const affectedAccounts = new Set<string>(data.trades.map((t: any) => `${t.account_name}-${t.symbol}`));
                    setCleanAccounts(prev => {
                        const next = { ...prev };
                        affectedAccounts.forEach(key => {
                            delete next[key];
                        });
                        return next;
                    });
                } else if (importingAccount && importingAccount !== 'NEW') {
                    // Fallback for single account import if trades list not populated
                    setCleanAccounts(prev => {
                        const next = { ...prev };
                        // We need the symbol too, but we might not have it readily here 
                        // so we'll look for all keys starting with this account name
                        Object.keys(next).forEach(key => {
                            if (key.startsWith(`${importingAccount}-`)) {
                                delete next[key];
                            }
                        });
                        return next;
                    });
                }

                setTimeout(() => {
                    fetchData();
                }, 1000);
            }
        } catch (err: any) {
            setSaveStatus('error');
            setError(err.message);
        } finally {
            setIsSaving(false);
        }
    };

    const closeImport = () => {
        setImportingAccount(null);
        setImportText('');
        setImportResult(null);
        setSaveStatus('idle');
    };

    const handleDelete = async (accountName: string) => {
        if (pendingDeleteAccount !== accountName) {
            setPendingDeleteAccount(accountName);
            return;
        }

        try {
            console.log(`[DELETE] Starting deletion of account: ${accountName}`);
            const response = await fetch(`http://localhost:8000/api/v1/accounts/accounts/${accountName}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Delete failed' }));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            console.log(`[DELETE] Success for account: ${accountName}`);
            setPendingDeleteAccount(null);
            fetchData();
        } catch (err: any) {
            console.error('[DELETE] Error:', err);
            alert(`Error deleting account: ${err.message}`);
            setPendingDeleteAccount(null);
        }
    };

    const handleValidate = async (accountName: string, symbol: string) => {
        setValidatingAccount(accountName);
        setValidatingSymbol(symbol);
        setValidationResult(null);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/accounts/accounts/${accountName}/validate?symbol=${symbol}`);
            if (!response.ok) throw new Error('Validation failed');
            const result = await response.json();
            setValidationResult(result);

            // Track clean status
            const key = `${accountName}-${symbol}`;
            setCleanAccounts(prev => ({ ...prev, [key]: result.is_valid }));
        } catch (err: any) {
            alert(`Validation error: ${err.message}`);
            setValidatingAccount(null);
            setValidatingSymbol(null);
        }
    };

    const handlePrune = async (accountName: string, criteria: string) => {
        const symbol = validatingSymbol;
        console.log(`[PRUNE] Execution started: account=${accountName}, criteria=${criteria}, symbol=${symbol}`);

        try {
            let url = `http://localhost:8000/api/v1/accounts/accounts/${accountName}/prune?criteria=${criteria}`;
            if (symbol) {
                url += `&symbol=${encodeURIComponent(symbol)}`;
            }

            console.log(`[PRUNE] POST: ${url}`);
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Server error' }));
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

            const result = await response.json();
            console.log("[PRUNE] Success:", result);
            alert(`✅ ${result.message}`);

            setPendingPrune(null); // Clear pending state

            // Re-validate to refresh the current view
            if (symbol) {
                // After pruning, we don't know if it's clean until re-validated
                // but handleValidate below will update it.
                handleValidate(accountName, symbol);
            } else {
                fetchData();
            }
        } catch (err: any) {
            console.error('[PRUNE] Error:', err);
            alert(`❌ Pruning failed: ${err.message}`);
        }
    };

    const handleViewTrades = async (accountName: string, symbol: string) => {
        setViewingTradesAccount(accountName);
        setRecentTrades([]);
        setTradesLoading(true);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/trades/?account_name=${accountName}&symbol=${symbol}&size=10&page=1`);
            if (!response.ok) throw new Error('Failed to fetch trades');
            const data = await response.json();
            setRecentTrades(data.data.items || []);
        } catch (err: any) {
            console.error('Error fetching trades:', err);
            alert(`Failed to load trades: ${err.message}`);
        } finally {
            setTradesLoading(false);
        }
    };

    const closeTradesModal = () => {
        setViewingTradesAccount(null);
        setRecentTrades([]);
    };

    const getDayName = (day: number | null) => {
        if (day === null) return 'N/A';
        return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][day];
    };

    const getFilteredAccounts = () => {
        if (!data) return [];
        return data.accounts.filter(acc => filterSymbol === 'ALL' || acc.symbol === filterSymbol);
    };

    const availableSymbols = data ? Array.from(new Set(data.accounts.map(a => a.symbol))).sort() : [];

    const getHourName = (hour: number | null) => {
        if (hour === null) return 'N/A';
        return hour === 0 ? '12 AM' : hour > 12 ? `${hour - 12} PM` : `${hour} ${hour === 12 ? 'PM' : 'AM'}`;
    };

    const filteredAccounts = getFilteredAccounts();
    const filteredTotal = filteredAccounts.length;
    const filteredStale = filteredAccounts.filter(a => !a.is_active).length;
    const filteredActive = filteredTotal - filteredStale;

    if (isLoading && !data) return <div className="loading">Loading management data...</div>;

    return (
        <div className="account-management-container">
            <div className="header-with-actions">
                <h1>Account Management</h1>
            </div>

            <div className="management-header">
                <div className="stats-row">
                    <div className="stat-card">
                        <span className="label">{filterSymbol === 'ALL' ? 'Total' : `${filterSymbol}`} Accounts</span>
                        <span className="value">{filteredTotal}</span>
                    </div>
                    <div className="stat-card stale">
                        <span className="label">Stale ({'>'} {staleThreshold}d)</span>
                        <span className="value">{filteredStale}</span>
                    </div>
                    <div className="stat-card active">
                        <span className="label">Active</span>
                        <span className="value">{filteredActive}</span>
                    </div>
                </div>

                <div className="filter-controls">
                    <div className="selection-group">
                        <span className="selector-label">Filter by Symbol:</span>
                        <div className="pill-selector">
                            <button
                                className={`filter-btn ${filterSymbol === 'ALL' ? 'active' : ''}`}
                                onClick={() => setFilterSymbol('ALL')}
                            >ALL</button>
                            {availableSymbols.map(sym => (
                                <button
                                    key={sym}
                                    className={`filter-btn ${filterSymbol === sym ? 'active' : ''}`}
                                    onClick={() => setFilterSymbol(sym)}
                                >{sym === 'FD' ? 'FDAX' : sym}</button>
                            ))}
                        </div>
                    </div>
                    <div className="naming-info" title="Account names are extracted from the Note column in Sierra Chart.">
                        ℹ️ <span>Note-based naming</span>
                    </div>
                </div>

                <div className="controls">
                    <label>Stale Threshold (days): </label>
                    <input
                        type="number"
                        value={staleThreshold}
                        onChange={(e) => setStaleThreshold(parseInt(e.target.value) || 1)}
                        min="1"
                    />
                    <button onClick={fetchData} className="refresh-btn">🔄 Refresh</button>
                    <button
                        className="new-import-btn"
                        onClick={() => {
                            setImportingAccount('NEW');
                            setImportText('');
                            setImportResult(null);
                        }}
                    >
                        ➕ Import New Account
                    </button>
                </div>
            </div>

            {importingAccount === 'NEW' && (
                <div className="global-import-container">
                    <div className="import-modal">
                        <h3>Import Trades for New/Existing Account</h3>
                        <p className="hint-text">Paste your Sierra Chart data here. The account name will be detected automatically.</p>
                        <textarea
                            placeholder="Paste Sierra Chart TradesList.txt content here..."
                            value={importText}
                            onChange={(e) => setImportText(e.target.value)}
                            disabled={isSaving || previewLoading || saveStatus === 'success'}
                        />
                        {/* Import Result Display (Same as inline) */}
                        {importResult && (
                            <div className={`import-result-summary ${saveStatus === 'success' ? 'final' : 'preview'}`}>
                                <h5>{saveStatus === 'success' ? 'Import Complete' : 'Import Preview'}</h5>
                                <div className="result-stats">
                                    <div className="res-stat">
                                        <span className="res-label">Parsed</span>
                                        <span className="res-val">{importResult.total_parsed}</span>
                                    </div>
                                    <div className="res-stat highlight">
                                        <span className="res-label">New Trades</span>
                                        <span className="res-val">{importResult.new_trades}</span>
                                    </div>
                                    <div className="res-stat warning">
                                        <span className="res-label">Duplicates</span>
                                        <span className="res-val">{importResult.duplicates}</span>
                                    </div>
                                    {importResult.errors?.length > 0 && (
                                        <div className="res-stat error">
                                            <span className="res-label">Errors</span>
                                            <span className="res-val">{importResult.errors.length}</span>
                                        </div>
                                    )}
                                </div>
                                {importResult.errors?.length > 0 && (
                                    <div className="error-list">
                                        {importResult.errors.slice(0, 5).map((err: string, i: number) => (
                                            <div key={i} className="error-item">❌ {err}</div>
                                        ))}
                                        {importResult.errors.length > 5 && <div>...and {importResult.errors.length - 5} more errors</div>}
                                    </div>
                                )}
                            </div>
                        )}
                        <div className="import-actions">
                            <button
                                className="preview-btn"
                                onClick={handleImportPreview}
                                disabled={previewLoading || isSaving || !importText.trim()}
                            >
                                {previewLoading ? '⏳ Parsing...' : '🔍 Preview'}
                            </button>
                            <button
                                className="save-btn"
                                onClick={handleImportSubmit}
                                disabled={isSaving || previewLoading || !importText.trim()}
                            >
                                {isSaving ? '⏳ Saving...' : '💾 Save to DB'}
                            </button>
                            <button className="cancel-btn" onClick={closeImport}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {viewingTradesAccount && (
                <div className="global-import-container">
                    <div className="import-modal trades-modal">
                        <div className="modal-header-row">
                            <h3>Last 10 Trades: {viewingTradesAccount}</h3>
                            <button className="close-x-btn" onClick={closeTradesModal}>✕</button>
                        </div>

                        {tradesLoading ? (
                            <div className="loading-trades">Loading trades...</div>
                        ) : recentTrades.length === 0 ? (
                            <div className="no-trades">No trades found for this account.</div>
                        ) : (
                            <div className="trades-list-container">
                                <table className="management-table trades-table">
                                    <thead>
                                        <tr>
                                            <th>Time (Entry)</th>
                                            <th>Type</th>
                                            <th>Price</th>
                                            <th>Exit</th>
                                            <th>Qty</th>
                                            <th>P&L</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {recentTrades.map((trade: any, idx: number) => (
                                            <tr key={idx}>
                                                <td>{new Date(trade.entry_time).toLocaleString()}</td>
                                                <td>
                                                    <span className={`side-badge ${trade.side?.toLowerCase()}`}>
                                                        {trade.side}
                                                    </span>
                                                </td>
                                                <td>{trade.entry_price}</td>
                                                <td>{trade.exit_price}</td>
                                                <td>{trade.quantity}</td>
                                                <td className={trade.profit_loss >= 0 ? 'pos' : 'neg'}>
                                                    ${trade.profit_loss?.toFixed(2)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                        <div className="modal-footer">
                            <button className="cancel-btn" onClick={closeTradesModal}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {error && <div className="error-message">{error}</div>}

            <div className="management-table-container">
                <table className="management-table">
                    <thead>
                        <tr>
                            <th>Account/Permutation</th>
                            <th>Symbol</th>
                            <th>Trades</th>
                            <th>Win Rate</th>
                            <th>Total P&L</th>
                            <th>Best Time</th>
                            <th>Last Trade</th>
                            <th>Status / Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredAccounts.map((acc, idx) => (
                            <React.Fragment key={idx}>
                                <tr className={!acc.is_active ? 'stale-row' : ''}>
                                    <td className="account-cell" title={acc.account_name}>
                                        {acc.account_name}
                                    </td>
                                    <td><span className="symbol-badge">{acc.symbol}</span></td>
                                    <td>{acc.total_trades}</td>
                                    <td>{acc.win_rate.toFixed(1)}%</td>
                                    <td className={acc.total_pnl >= 0 ? 'pos' : 'neg'}>
                                        ${acc.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                    </td>
                                    <td>
                                        <div className="timing-info">
                                            <span>{getDayName(acc.best_day_of_week)}</span>
                                            <span className="hour-info">{getHourName(acc.best_hour_of_day)}</span>
                                        </div>
                                    </td>
                                    <td>
                                        <div className="last-trade-info">
                                            {acc.last_trade_date ? new Date(acc.last_trade_date).toLocaleDateString() : 'N/A'}
                                            {acc.days_since_last_trade !== null && (
                                                <span className={`gap-tag ${acc.days_since_last_trade > staleThreshold ? 'warning' : 'ok'}`}>
                                                    {acc.days_since_last_trade}d ago
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                    <td>
                                        <div className="action-cell">
                                            <span className={`status-badge ${acc.is_active ? 'active' : 'inactive'}`}>
                                                {acc.is_active ? 'ACTIVE' : 'STALE'}
                                            </span>
                                            {pendingDeleteAccount === acc.account_name ? (
                                                <div className="delete-confirmation">
                                                    <button
                                                        className="confirm-delete-btn"
                                                        onClick={() => handleDelete(acc.account_name)}
                                                        title="Delete ALL trades forever"
                                                    >
                                                        DELETE ALL?
                                                    </button>
                                                    <button
                                                        className="cancel-delete-btn"
                                                        onClick={() => setPendingDeleteAccount(null)}
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            ) : (
                                                <>
                                                    <button
                                                        className={`action-icon-btn validate-btn ${cleanAccounts[`${acc.account_name}-${acc.symbol}`] ? 'is-valid' : ''}`}
                                                        title="Validate Data Integrity"
                                                        onClick={() => handleValidate(acc.account_name, acc.symbol)}
                                                    >
                                                        🛡️
                                                    </button>
                                                    <button
                                                        className="action-icon-btn delete-btn"
                                                        title="Delete Account"
                                                        onClick={() => handleDelete(acc.account_name)}
                                                    >
                                                        🗑️
                                                    </button>
                                                    <button
                                                        className="action-icon-btn view-trades-btn"
                                                        title="View Last 10 Trades"
                                                        onClick={() => handleViewTrades(acc.account_name, acc.symbol)}
                                                    >
                                                        👁️
                                                    </button>
                                                </>
                                            )}
                                            <button
                                                className="import-line-btn"
                                                onClick={() => {
                                                    if (importingAccount === acc.account_name) {
                                                        closeImport();
                                                    } else {
                                                        setImportingAccount(acc.account_name);
                                                        setImportText('');
                                                        setImportResult(null);
                                                    }
                                                }}
                                            >
                                                📥 Import
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                                {validatingAccount === acc.account_name && validationResult && (
                                    <tr className="validation-row">
                                        <td colSpan={8}>
                                            <div className="validation-result">
                                                <h4>Validation for {acc.account_name}</h4>
                                                <div className="validation-summary">
                                                    Status: <span className={validationResult.is_valid ? 'ok-tag' : 'error-tag'}>
                                                        {validationResult.is_valid ? '✅ Valid' : '⚠️ Issues Found'}
                                                    </span>
                                                    {' '}(Checked {validationResult.total_trades_checked} trades)
                                                </div>
                                                {validationResult.alerts.length > 0 ? (
                                                    <ul className="alert-list">
                                                        {validationResult.alerts.map((alert: any, i: number) => (
                                                            <li key={i} className={`alert-item ${alert.severity}`}>
                                                                <div className="alert-content">
                                                                    <strong>{alert.alert_type}</strong>: {alert.message} ({alert.count} occurrences)
                                                                </div>
                                                                {['overnight_hold', 'negative_duration'].includes(alert.alert_type) && (
                                                                    <div className="fix-actions">
                                                                        {pendingPrune?.account === acc.account_name && pendingPrune?.criteria === alert.alert_type ? (
                                                                            <>
                                                                                <button
                                                                                    className="fix-btn confirm-mode"
                                                                                    onClick={() => handlePrune(acc.account_name, alert.alert_type)}
                                                                                    title="Click again to delete forever"
                                                                                >
                                                                                    ⚠️ CONFIRM ({alert.count})
                                                                                </button>
                                                                                <button className="cancel-prune-btn" onClick={() => setPendingPrune(null)}>
                                                                                    Cancel
                                                                                </button>
                                                                            </>
                                                                        ) : (
                                                                            <button
                                                                                className="fix-btn"
                                                                                onClick={() => setPendingPrune({ account: acc.account_name, criteria: alert.alert_type })}
                                                                            >
                                                                                🛠️ Fix (Delete {alert.count})
                                                                            </button>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                ) : (
                                                    <div className="clean-report">No data integrity issues found.</div>
                                                )}
                                                <button className="close-validation" onClick={() => setValidatingAccount(null)}>Close Report</button>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                                {importingAccount === acc.account_name && (
                                    <tr className="import-row">
                                        <td colSpan={8}>
                                            <div className="inline-import-container">
                                                <h4>Import trades for {acc.account_name}</h4>
                                                <textarea
                                                    placeholder="Paste Sierra Chart TradesList.txt content here..."
                                                    value={importText}
                                                    onChange={(e) => setImportText(e.target.value)}
                                                    disabled={isSaving || previewLoading || saveStatus === 'success'}
                                                />

                                                {importResult && (
                                                    <div className={`import-result-summary ${saveStatus === 'success' ? 'final' : 'preview'}`}>
                                                        <h5>{saveStatus === 'success' ? 'Import Complete' : 'Import Preview'}</h5>
                                                        <div className="result-stats">
                                                            <div className="res-stat">
                                                                <span className="res-label">Parsed</span>
                                                                <span className="res-val">{importResult.total_parsed}</span>
                                                            </div>
                                                            <div className="res-stat highlight">
                                                                <span className="res-label">New Trades</span>
                                                                <span className="res-val">{importResult.new_trades}</span>
                                                            </div>
                                                            <div className="res-stat warning">
                                                                <span className="res-label">Duplicates</span>
                                                                <span className="res-val">{importResult.duplicates}</span>
                                                            </div>
                                                            {importResult.errors?.length > 0 && (
                                                                <div className="res-stat error">
                                                                    <span className="res-label">Errors</span>
                                                                    <span className="res-val">{importResult.errors.length}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                        {importResult.errors?.length > 0 && (
                                                            <div className="error-list">
                                                                {importResult.errors.slice(0, 5).map((err: string, i: number) => (
                                                                    <div key={i} className="error-item">❌ {err}</div>
                                                                ))}
                                                                {importResult.errors.length > 5 && <div>...and {importResult.errors.length - 5} more errors</div>}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                <div className="import-actions">
                                                    {saveStatus !== 'success' && (
                                                        <>
                                                            <button
                                                                className="preview-btn"
                                                                onClick={handleImportPreview}
                                                                disabled={previewLoading || isSaving || !importText.trim()}
                                                            >
                                                                {previewLoading ? '⏳ Parsing...' : '🔍 Preview'}
                                                            </button>
                                                            <button
                                                                className="save-btn"
                                                                onClick={handleImportSubmit}
                                                                disabled={isSaving || previewLoading || !importText.trim()}
                                                            >
                                                                {isSaving ? '⏳ Saving...' : '💾 Save to DB'}
                                                            </button>
                                                        </>
                                                    )}
                                                    {saveStatus === 'success' && (
                                                        <span className="save-success">✅ Great! {importResult.new_trades} trades added to database.</span>
                                                    )}
                                                    {saveStatus === 'error' && <span className="save-error">❌ Error: {error}</span>}
                                                    <button className="cancel-btn" onClick={closeImport}>
                                                        {saveStatus === 'success' ? 'Close' : 'Cancel'}
                                                    </button>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div >
        </div >
    );
};

export default AccountManagement;
