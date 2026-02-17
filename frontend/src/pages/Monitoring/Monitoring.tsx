import React, { useState, useEffect, useCallback } from 'react';
import './Monitoring.css';

// --- Interfaces ---
interface Account {
  name: string;
  base_symbol: string;
  trade_count: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  first_trade_date: string | null;
  last_trade_date: string | null;
  days_since_last_trade: number | null;
  best_day_of_week: number | null;
  best_hour_of_day: number | null;
}

interface SystemStatus {
  component: string;
  status: string;
  responseTime: number;
  lastUpdate: string;
}

interface ScannerState {
  symbol: string;
  path: string;
  detectedAccounts: string[];
  selectedAccounts: string[];
  status: 'idle' | 'scanning' | 'ready' | 'importing' | 'error';
  message: string;
}

interface ImportStatus {
  running: boolean;
  message: string;
  progress: number;
  stats: any;
}

const Monitoring = () => {
  // Data States
  const [dbAccounts, setDbAccounts] = useState<Account[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSymbol, setFilterSymbol] = useState('ALL');
  const [globalImportStatus, setGlobalImportStatus] = useState<ImportStatus | null>(null);

  // Scanners
  const [scanners, setScanners] = useState<ScannerState[]>([
    { symbol: 'CL', path: 'D:\\SierraChart_Simulated_Feed\\SierraChartInstance_4\\TradeActivityLogs', detectedAccounts: [], selectedAccounts: [], status: 'idle', message: '' },
    { symbol: 'ES', path: 'D:\\SierraChart_Simulated_Feed\\SierraChartInstance_5\\TradeActivityLogs', detectedAccounts: [], selectedAccounts: [], status: 'idle', message: '' },
    { symbol: 'NQ', path: 'D:\\SierraChart_Simulated_Feed\\TradeActivityLogs', detectedAccounts: [], selectedAccounts: [], status: 'idle', message: '' },
    { symbol: 'FDAX', path: 'D:\\SierraChart_Delayed_Simulated\\TradeActivityLogs', detectedAccounts: [], selectedAccounts: [], status: 'idle', message: '' },
  ]);

  // Modals
  const [pasteModal, setPasteModal] = useState(false);
  const [viewTradesModal, setViewTradesModal] = useState<{ open: boolean; account?: string; symbol?: string }>({ open: false });
  const [validationModal, setValidationModal] = useState<{ open: boolean; data?: any; account?: string }>({ open: false });
  const [deleteConfirm, setDeleteConfirm] = useState<{ account: string; symbol?: string } | null>(null);

  const [importText, setImportText] = useState('');
  const [importResult, setImportResult] = useState<any>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [recentTrades, setRecentTrades] = useState<any[]>([]);

  // --- Fetching ---
  const fetchData = useCallback(async () => {
    try {
      const accRes = await fetch('http://localhost:8000/api/system/accounts');
      const accData = await accRes.json();
      if (Array.isArray(accData)) setDbAccounts(accData);

      const statusRes = await fetch('http://localhost:8000/api/system/status');
      const statusData = await statusRes.json();
      if (Array.isArray(statusData)) setSystemStatus(statusData);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  const fetchImportStatus = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/system/import-status');
      const data = await res.json();
      setGlobalImportStatus(data);
      if (data.running) {
        fetchData(); // Refresh list while importing
      }
    } catch (e) { console.error(e); }
  }, [fetchData]);

  useEffect(() => {
    fetchData();
    fetchImportStatus();
    const interval = setInterval(() => {
      fetchData();
      fetchImportStatus();
    }, 10000); // Heartbeat
    return () => clearInterval(interval);
  }, [fetchData, fetchImportStatus]);

  // --- Actions ---
  const handleScan = async (symbol: string) => {
    setScanners(p => p.map(s => s.symbol === symbol ? { ...s, status: 'scanning' } : s));
    try {
      const path = scanners.find(s => s.symbol === symbol)?.path;
      const res = await fetch('http://localhost:8000/api/system/check-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path || '', symbol })
      });
      const data = await res.json();
      setScanners(p => p.map(s => s.symbol === symbol ? {
        ...s, status: 'ready',
        detectedAccounts: data.accounts || [],
        selectedAccounts: data.accounts || [],
        message: data.message
      } : s));
    } catch (e) {
      setScanners(p => p.map(s => s.symbol === symbol ? { ...s, status: 'error', message: 'Scan failed: ' + String(e) } : s));
    }
  };

  const handleImport = async (symbol: string) => {
    const scanner = scanners.find(s => s.symbol === symbol);
    if (!scanner) return;
    setScanners(p => p.map(s => s.symbol === symbol ? { ...s, status: 'importing' } : s));
    try {
      const paths = [scanner.path];
      await fetch('http://localhost:8000/api/system/import-start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, symbol, accounts: scanner.selectedAccounts })
      });
      fetchImportStatus();
    } catch (e) { }
    setScanners(p => p.map(s => s.symbol === symbol ? { ...s, status: 'ready' } : s));
  };

  const handleStopImport = async () => {
    try {
      await fetch('http://localhost:8000/api/system/import-stop', { method: 'POST' });
      setTimeout(fetchImportStatus, 500);
    } catch (e) { console.error(e); }
  };

  const handlePurgeAnomalies = async (account: string, symbol: string) => {
    if (!window.confirm(`Permanently remove future trades, PnL outliers and overnight holds for ${account}?`)) return;
    setIsSaving(true);
    try {
      const res = await fetch('http://localhost:8000/api/system/purge-anomalies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account, symbol })
      });
      const data = await res.json();
      alert(`Cleaned: ${data.removed.future} future, ${data.removed.overnight} overnight, ${data.removed.outliers} PnL outliers.`);
      setValidationModal({ open: false });
      fetchData();
    } catch (e) { console.error(e); }
    setIsSaving(false);
  };

  const handleViewRecent = async (account: string, symbol: string) => {
    setViewTradesModal({ open: true, account, symbol });
    setRecentTrades([]);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/trades/?account_name=${account}&symbol=${symbol}&size=10&page=1`);
      const data = await res.json();
      setRecentTrades(data.data?.items || []);
    } catch (e) { console.error(e); }
  };

  const handleValidate = async (account: string, symbol: string) => {
    setValidationModal({ open: true, account });
    try {
      const res = await fetch(`http://localhost:8000/api/v1/accounts/accounts/${account}/validate?symbol=${symbol}`);
      const data = await res.json();
      setValidationModal({ open: true, account, data });
    } catch (e) { console.error(e); }
  };

  // --- Rendering Helpers ---
  const getDayLabel = (d: any) => (d === null || d === undefined) ? '-' : ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d];
  const getHourLabel = (h: any) => {
    if (h === null || h === undefined) return '-';
    const hour = parseInt(h);
    if (isNaN(hour)) return '-';
    return hour === 0 ? '12 AM' : hour > 12 ? `${hour - 12} PM` : hour === 12 ? '12 PM' : `${hour} AM`;
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      const url = `http://localhost:8000/api/system/remove-cluster?account=${encodeURIComponent(deleteConfirm.account)}${deleteConfirm.symbol ? `&symbol=${encodeURIComponent(deleteConfirm.symbol)}` : ''}`;
      const res = await fetch(url, { method: 'POST' });
      const result = await res.json();
      console.log('Delete result:', result);

      setDeleteConfirm(null);
      setTimeout(() => {
        fetchData();
      }, 500);
    } catch (e) {
      console.error('Delete error:', e);
      setDeleteConfirm(null);
    }
  };

  const handleRestartBackend = async () => {
    if (!window.confirm("Restart backend service? This will briefly interrupt the API.")) return;
    try {
      await fetch('http://localhost:8000/api/system/restart', { method: 'POST' });
      alert("Restart triggered. Please wait 5-10 seconds.");
    } catch (e) {
      alert("Failed to trigger restart: " + e);
    }
  };

  const filtered = dbAccounts.filter(a => filterSymbol === 'ALL' || a.base_symbol === filterSymbol);
  const totalVolume = systemStatus.find(s => s.component.includes('Trades Table'))?.component.match(/\((.*) records\)/)?.[1] || '0';

  return (
    <div className="monitoring">
      {/* 🚀 System Health Header */}
      <div className="system-status-bar">
        <div className="status-left">
          <h1>System Control Center</h1>
          <span className="status-val">Backend active at localhost:8000</span>
        </div>
        <div className="status-indicators">
          <div className="status-item">
            <div className={`status-dot ${systemStatus.find(s => s.component === 'API Server')?.status === 'online' ? 'online' : 'offline'}`}></div>
            <span className="status-label">API Server</span>
          </div>
          <div className="status-item">
            <div className={`status-dot ${systemStatus.find(s => s.component === 'Database')?.status === 'online' ? 'online' : 'offline'}`}></div>
            <span className="status-label">SQLite Database</span>
          </div>
          <div className="status-item">
            <span className="status-label">DB Size:</span>
            <span className="status-val" style={{ fontWeight: 800, color: '#2563eb' }}>{totalVolume}</span>
          </div>
          <button className="btn btn-scan" onClick={fetchData}>🔄 Refresh</button>
          <button className="btn btn-scan" style={{ backgroundColor: '#dc2626', marginLeft: '10px' }} onClick={handleRestartBackend}>⚠️ Restart Backend</button>
        </div>
      </div>

      {/* Global Import Progress (Always visible if running) */}
      {globalImportStatus?.running && (
        <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '12px', padding: '15px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 700, color: '#1e40af' }}>⚡ Active Import in Progress...</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <span style={{ fontWeight: 800, color: '#2563eb' }}>{globalImportStatus.progress}%</span>
              <button
                onClick={handleStopImport}
                style={{
                  background: '#ef4444',
                  color: 'white',
                  border: 'none',
                  padding: '4px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                🛑 STOP
              </button>
            </div>
          </div>
          <div style={{ width: '100%', height: '8px', background: '#dbeafe', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
            <div style={{ width: `${globalImportStatus.progress}%`, height: '100%', background: '#2563eb' }} />
          </div>
          <div style={{ fontSize: '13px', color: '#1e40af' }}>{globalImportStatus.message}</div>
          <div style={{ fontSize: '11px', color: '#60a5fa', marginTop: '4px' }}>
            {globalImportStatus.stats && typeof globalImportStatus.stats === 'object'
              ? `Processed: ${globalImportStatus.stats.processed} | Found: ${globalImportStatus.stats.found} | Errors: ${globalImportStatus.stats.errors}`
              : String(globalImportStatus.stats || '')}
          </div>
        </div>
      )}

      <div className="monitoring-grid">
        {/* 📥 INGESTION PANEL */}
        <div className="control-section">
          <div className="section-title">
            <h2>📥 Log Ingestion</h2>
            <button className="btn btn-import" onClick={() => setPasteModal(true)}>Manual Paste</button>
          </div>
          <div className="ingestion-list">
            {scanners.map(s => (
              <div key={s.symbol} className="ingestion-card">
                <div className="card-header">
                  <span className="symbol-name">{s.symbol}</span>
                  <div className="button-group">
                    {s.status === 'scanning' ? (
                      <button className="btn btn-scan" disabled>Scanning...</button>
                    ) : (s.status === 'importing' || (globalImportStatus?.running && globalImportStatus.message.includes(s.symbol))) ? (
                      <button className="btn btn-import" disabled style={{ opacity: 0.7, cursor: 'not-allowed' }}>Importing...</button>
                    ) : s.status === 'ready' ? (
                      <button className="btn btn-import" onClick={() => handleImport(s.symbol)}>Import {s.symbol}</button>
                    ) : (
                      <button className="btn btn-scan" onClick={() => handleScan(s.symbol)}>Scan</button>
                    )}
                  </div>
                </div>
                <div className="path-input-group">
                  <input type="text" value={s.path} readOnly />
                  {s.message && (
                    <div style={{
                      fontSize: '11px',
                      marginTop: '4px',
                      color: s.status === 'error' ? '#ef4444' : '#2563eb',
                      fontWeight: 600
                    }}>
                      {s.message}
                    </div>
                  )}
                </div>
                {s.status === 'ready' && s.detectedAccounts.length > 0 && (
                  <div className="account-selection-grid">
                    <label className="acc-select-item" style={{ borderBottom: '1px solid #e2e8f0', marginBottom: '8px', paddingBottom: '8px', fontWeight: 700, width: '100%' }}>
                      <input type="checkbox"
                        checked={s.selectedAccounts.length === s.detectedAccounts.length}
                        onChange={() => setScanners(prev => prev.map(ps => ps.symbol === s.symbol ? {
                          ...ps, selectedAccounts: ps.selectedAccounts.length === ps.detectedAccounts.length ? [] : [...ps.detectedAccounts]
                        } : ps))}
                      /> Select All (Found {s.detectedAccounts.length})
                    </label>
                    {s.detectedAccounts.map(acc => (
                      <label key={acc} className="acc-select-item">
                        <input type="checkbox" checked={s.selectedAccounts.includes(acc)}
                          onChange={() => setScanners(prev => prev.map(ps => ps.symbol === s.symbol ? {
                            ...ps, selectedAccounts: ps.selectedAccounts.includes(acc) ? ps.selectedAccounts.filter(x => x !== acc) : [...ps.selectedAccounts, acc]
                          } : ps))}
                        /> {acc}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <button className="btn btn-import" style={{ background: '#059669', padding: '12px' }} onClick={() => {
            if (window.confirm("Run global sync for all symbols?")) handleImport('CL'); // Example trigger
          }}>🚀 Fast Global Sync</button>
        </div>

        {/* 📊 ASSET MANAGEMENT PANEL */}
        <div className="table-section">
          <div className="section-title">
            <h2>📊 Database Accounts & Performance</h2>
            <div className="filter-pills">
              {['ALL', 'CL', 'ES', 'NQ', 'FDAX'].map(p => (
                <div key={p} className={`pill ${filterSymbol === p ? 'active' : ''}`} onClick={() => setFilterSymbol(p)}>{p === 'FDAX' ? 'FD' : p}</div>
              ))}
            </div>
          </div>

          <div className="global-stats-row">
            <div className="mini-stat-card">
              <div className="mini-stat-label">Total Clusters</div>
              <div className="mini-stat-val">{dbAccounts.length}</div>
            </div>
            <div className="mini-stat-card">
              <div className="mini-stat-label">Stale (&gt;30d)</div>
              <div className="mini-stat-val" style={{ color: '#ef4444' }}>{dbAccounts.filter(a => (a.days_since_last_trade || 0) > 30).length}</div>
            </div>
            <div className="mini-stat-card">
              <div className="mini-stat-label">P&L (Sum)</div>
              <div className="mini-stat-val" style={{ color: '#059669' }}>${dbAccounts.reduce((s, a) => s + (a.total_pnl || 0), 0).toLocaleString()}</div>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="management-table">
              <thead>
                <tr>
                  <th>Account Group</th>
                  <th>Sym</th>
                  <th>Trades</th>
                  <th>Win Rate</th>
                  <th>Total P&L</th>
                  <th>Best Window</th>
                  <th>Days Ago</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(acc => {
                  const isStale = (acc.days_since_last_trade || 0) > 30;
                  const winRate = acc.win_rate || 0;
                  return (
                    <tr key={`${acc.name}-${acc.base_symbol}`} className={isStale ? 'tr-stale' : ''}>
                      <td className="acc-name">{acc.name}</td>
                      <td><span className="pill">{acc.base_symbol}</span></td>
                      <td style={{ fontWeight: 600 }}>{acc.trade_count}</td>
                      <td>
                        <span className={`win-rate-tag ${winRate > 55 ? 'high' : winRate > 45 ? 'mid' : 'low'}`}>
                          {winRate.toFixed(1)}%
                        </span>
                      </td>
                      <td className={(acc.total_pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                        ${(acc.total_pnl || 0).toLocaleString()}
                      </td>
                      <td>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>
                          {acc.best_day_of_week !== null ? getDayLabel(acc.best_day_of_week) : '-'}{acc.best_hour_of_day !== null ? `, ${getHourLabel(acc.best_hour_of_day)}` : ''}
                        </div>
                      </td>
                      <td>
                        <span style={{ color: isStale ? '#ef4444' : '#64748b', fontWeight: isStale ? 700 : 400 }}>
                          {acc.days_since_last_trade != null ? `${acc.days_since_last_trade}d` : '-'}
                        </span>
                      </td>
                      <td>
                        <div className="action-btns">
                          <button
                            className="icon-btn"
                            onClick={() => handleValidate(acc.name, acc.base_symbol)}
                            style={{ opacity: 1, filter: (acc.total_pnl === 0 || isStale) ? 'grayscale(1)' : 'none' }}
                            title="Validate Stats"
                          >
                            {(acc.days_since_last_trade != null && acc.days_since_last_trade < 0) ? '🔴' : '🟢'}
                          </button>
                          <button className="icon-btn" onClick={() => handleViewRecent(acc.name, acc.base_symbol)}>👁️</button>
                          <button className="icon-btn" onClick={() => setDeleteConfirm({ account: acc.name, symbol: acc.base_symbol })}>🗑️</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* --- MODALS --- */}
      {pasteModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="section-title"><h2>Manual Paste Import</h2><button onClick={() => setPasteModal(false)}>✕</button></div>
            <textarea className="paste-textarea" value={importText} onChange={e => setImportText(e.target.value)} placeholder="Paste TradesList.txt content here..." />
            {importResult && <div style={{ background: '#f0fdf4', padding: '15px', marginTop: '15px', borderRadius: '8px' }}>Success: {importResult.new_trades} added.</div>}
            <div className="modal-footer">
              <button className="btn" onClick={() => setPasteModal(false)}>Close</button>
              <button className="btn btn-import" onClick={async () => {
                setIsSaving(true);
                const res = await fetch('http://localhost:8000/api/v1/trades/import-paste', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: importText }) });
                setImportResult(await res.json());
                setIsSaving(false); fetchData();
              }}>{isSaving ? 'Saving...' : 'Start Import'}</button>
            </div>
          </div>
        </div>
      )}

      {viewTradesModal.open && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ width: '900px' }}>
            <div className="section-title"><h2>Recent Trades: {viewTradesModal.account} ({viewTradesModal.symbol})</h2><button onClick={() => setViewTradesModal({ open: false })}>✕</button></div>
            <table className="management-table">
              <thead><tr><th>Time</th><th>Side</th><th>Price</th><th>Profit</th></tr></thead>
              <tbody>
                {recentTrades.map((t, i) => (
                  <tr key={i}>
                    <td>{new Date(t.entry_time).toLocaleString()}</td>
                    <td><span className={`pill ${t.side?.toLowerCase()}`}>{t.side}</span></td>
                    <td>{t.entry_price}</td>
                    <td className={(t.profit_loss || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'}>${(t.profit_loss || 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="modal-footer"><button className="btn" onClick={() => setViewTradesModal({ open: false })}>Close</button></div>
          </div>
        </div>
      )}

      {validationModal.open && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="section-title"><h2>Validation Report: {validationModal.account}</h2><button onClick={() => setValidationModal({ open: false })}>✕</button></div>
            {!validationModal.data ? 'Validating...' : (
              <div className="validation-result">
                <h3>Status: {validationModal.data.is_valid ? '✅ Clean' : '⚠️ Issues Found'}</h3>
                <ul>
                  {validationModal.data.alerts.map((a: any, i: number) => (
                    <li key={i} style={{ marginBottom: '10px', padding: '10px', background: '#f8fafc', borderRadius: '6px' }}>
                      <strong>{a.alert_type}</strong>: {a.message} ({a.count} occurrences)
                    </li>
                  ))}
                </ul>
                <div style={{ marginTop: '20px', padding: '15px', background: '#fff7ed', border: '1px solid #ffedd5', borderRadius: '8px' }}>
                  <h4 style={{ color: '#9a3412', marginBottom: '8px' }}>🛠️ Data Correction Tools</h4>
                  <p style={{ fontSize: '12px', color: '#7c2d12', marginBottom: '12px' }}>This will remove future-dated trades and overnight holds to fix your P&L and Days Ago stats.</p>
                  <button className="btn" style={{ background: '#ea580c', color: 'white' }} onClick={() => handlePurgeAnomalies(validationModal.account!, filterSymbol)}>
                    ✨ Clean All Anomalies
                  </button>
                </div>
              </div>
            )}
            <div className="modal-footer"><button className="btn" onClick={() => setValidationModal({ open: false })}>Close</button></div>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ width: '400px', textAlign: 'center' }}>
            <h2 style={{ color: '#ef4444' }}>Confirm Deletion</h2>
            <p>Delete all <strong>{deleteConfirm.symbol}</strong> trades for <strong>{deleteConfirm.account}</strong>?</p>
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>This action cannot be undone.</p>
            <div className="modal-footer" style={{ justifyContent: 'center' }}>
              <button className="btn" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn" style={{ background: '#ef4444', color: 'white' }} onClick={handleDelete}>Yes, DELETE</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Monitoring;
