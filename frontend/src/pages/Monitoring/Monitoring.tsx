import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { fetchAccounts } from '../../store/slices/accountsSlice';
import { AppDispatch } from '../../store/store';
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
  const dispatch = useDispatch<AppDispatch>();
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
  const [showRules, setShowRules] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{ account: string; symbol?: string } | null>(null);

  const importTextRef = useRef<HTMLTextAreaElement>(null);
  const [importResult, setImportResult] = useState<any>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [recentTrades, setRecentTrades] = useState<any[]>([]);

  const [importDays, setImportDays] = useState('30');
  const [vixData, setVixData] = useState<any[]>([]);
  const [showVixModal, setShowVixModal] = useState(false);
  const [ingestionEnabled, setIngestionEnabled] = useState(false);

  // --- Fetching ---
  const fetchData = useCallback(async () => {
    try {
      const accRes = await fetch('http://localhost:8000/api/system/accounts');
      const accData = await accRes.json();
      if (Array.isArray(accData)) {
        setDbAccounts(accData);
        dispatch(fetchAccounts());
      }

      const statusRes = await fetch('http://localhost:8000/api/system/status');
      const statusData = await statusRes.json();
      if (Array.isArray(statusData)) setSystemStatus(statusData);

      // Fetch saved settings
      const settingsRes = await fetch('http://localhost:8000/api/system/settings');
      const settingsData = await settingsRes.json();
      if (settingsData.scanners) {
        setScanners(prev => prev.map(s => {
          const saved = settingsData.scanners.find((ss: any) => ss.symbol === s.symbol);
          return saved ? { ...s, path: saved.path } : s;
        }));
      }
      if (settingsData.import_days) {
        setImportDays(settingsData.import_days);
      }
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
  }, []); // Remove fetchData and fetchImportStatus from deps to avoid infinite loops if setScanners triggers re-fetch

  // --- Actions ---
  const handleSaveSettings = async (updatedScanners: any[], days?: string) => {
    try {
      await fetch('http://localhost:8000/api/system/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scanners: updatedScanners.map(s => ({ symbol: s.symbol, path: s.path })),
          import_days: days || importDays
        })
      });
    } catch (e) { console.error('Failed to save settings', e); }
  };

  const updatePath = (symbol: string, newPath: string) => {
    setScanners(prev => {
      const next = prev.map(s => s.symbol === symbol ? { ...s, path: newPath } : s);
      handleSaveSettings(next);
      return next;
    });
  };

  const updateImportDays = (val: string) => {
    setImportDays(val);
    handleSaveSettings(scanners, val);
  };

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
        body: JSON.stringify({ paths, symbol, accounts: scanner.selectedAccounts, days: parseInt(importDays) })
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

  const fetchVixData = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/system/vix-data?limit=5000');
      const data = await res.json();
      if (data.status === 'success') {
        setVixData(data.data);
        setShowVixModal(true);
      }
    } catch (e) {
      alert("Failed to fetch VIX data: " + e);
    }
  };

  const handleImportVix = async () => {
    setIsSaving(true);
    try {
      const res = await fetch('http://localhost:8000/api/system/import-vix', { method: 'POST' });
      const data = await res.json();
      alert(data.message || "VIX Data Imported");
      // Refresh after import
      await fetchVixData();
    } catch (e) {
      alert("Failed to import VIX: " + e);
    }
    setIsSaving(false);
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

          <div style={{ display: 'flex', gap: '5px', marginLeft: '10px' }}>
            <button className="btn btn-scan" style={{ backgroundColor: '#0ea5e9', color: 'white' }} onClick={handleImportVix} disabled={isSaving}>
              📥 {isSaving ? '...' : 'FETCH VIX'}
            </button>
            <button className="btn btn-scan" style={{ backgroundColor: '#6366f1', color: 'white' }} onClick={fetchVixData}>
              👁️ VIEW VIX
            </button>
          </div>

          <button className="btn btn-scan" style={{ backgroundColor: '#dc2626', marginLeft: '10px', color: 'white' }} onClick={handleRestartBackend}>⚠️ Restart Backend</button>
        </div>
      </div>

      {/* Global Import Progress (Active or Last Result) */}
      {(globalImportStatus?.running || globalImportStatus?.message?.includes('Complete')) && (
        <div style={{
          background: globalImportStatus.running ? '#eff6ff' : '#f0fdf4',
          border: '1px solid',
          borderColor: globalImportStatus.running ? '#bfdbfe' : '#bbf7d0',
          borderRadius: '12px',
          padding: '15px',
          marginBottom: '24px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 700, color: globalImportStatus.running ? '#1e40af' : '#166534', display: 'flex', alignItems: 'center', gap: '8px' }}>
              {globalImportStatus.running ? (
                <>⚡ Sync in Progress...</>
              ) : (
                <>
                  ✅ Import Finished
                  <button
                    onClick={() => setShowRules(true)}
                    style={{
                      marginLeft: '10px',
                      background: '#eff6ff',
                      color: '#2563eb',
                      border: '1px solid #bfdbfe',
                      borderRadius: '4px',
                      padding: '2px 8px',
                      fontSize: '10px',
                      cursor: 'pointer',
                      fontWeight: 700
                    }}
                  >
                    🛡️ Shield Rules
                  </button>
                </>
              )}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              {globalImportStatus.running ? (
                <>
                  <span style={{ fontWeight: 800, color: '#2563eb' }}>{globalImportStatus.progress}%</span>
                  <button onClick={handleStopImport} className="btn-scan" style={{ background: '#ef4444', color: 'white', border: 'none', padding: '4px 10px', fontSize: '10px' }}>🛑 STOP</button>
                </>
              ) : (
                <button onClick={fetchImportStatus} className="icon-btn">✕</button>
              )}
            </div>
          </div>

          {globalImportStatus.running && (
            <div style={{ width: '100%', height: '6px', background: '#dbeafe', borderRadius: '4px', overflow: 'hidden', marginBottom: '8px' }}>
              <div style={{ width: `${globalImportStatus.progress}%`, height: '100%', background: '#2563eb', transition: 'width 0.3s ease' }} />
            </div>
          )}

          <div style={{ fontSize: '13px', fontWeight: 600, color: '#1e293b' }}>{globalImportStatus.message}</div>

          {globalImportStatus.stats && typeof globalImportStatus.stats === 'object' && (
            <div style={{ marginTop: '12px', borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: '12px' }}>
              <div style={{ display: 'flex', gap: '20px', marginBottom: '12px', padding: '8px 12px', background: 'rgba(255,255,255,0.5)', borderRadius: '8px', fontSize: '11px' }}>
                <div style={{ color: '#0369a1' }}><strong>📋 Processed:</strong> {globalImportStatus.stats.processed} files</div>
                <div style={{ color: '#15803d' }}><strong>➕ Added:</strong> {globalImportStatus.stats.found} trades</div>
                <div style={{ color: '#b91c1c' }}>
                  <strong>🛡️ Dropped:</strong> {globalImportStatus.stats.dropped_long_duration + globalImportStatus.stats.dropped_outliers + globalImportStatus.stats.dropped_eod_1700} ({globalImportStatus.stats.dropped_pct}%)
                </div>
                <div style={{ color: '#6366f1' }}><strong>⚖️ Open:</strong> {globalImportStatus.stats.unpaired_fills} fills</div>
              </div>

              {globalImportStatus.stats.breakdown && Object.keys(globalImportStatus.stats.breakdown).length > 0 && (
                <div style={{ background: 'white', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                  <table style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                        <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 900 }}>ACCOUNT</th>
                        <th style={{ padding: '6px 10px', textAlign: 'center', color: '#ef4444' }}>&gt;24hrs</th>
                        <th style={{ padding: '6px 10px', textAlign: 'center', color: '#f59e0b' }}>EOD (17:00)</th>
                        <th style={{ padding: '6px 10px', textAlign: 'center', color: '#6366f1' }}>OUTLIERS</th>
                        <th style={{ padding: '6px 10px', textAlign: 'center', color: '#ec4899' }}>BAD PRICE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(globalImportStatus.stats.breakdown as Record<string, any>).map(([acc, rules]) => (
                        <tr key={acc} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '6px 10px', fontWeight: 700, color: '#475569' }}>{acc}</td>
                          <td style={{ padding: '6px 10px', textAlign: 'center' }}>
                            <div>{typeof rules.long_duration === 'object' ? rules.long_duration.count : (rules.long_duration || 0)}</div>
                            {typeof rules.long_duration === 'object' && rules.long_duration.pnl !== 0 && (
                              <div style={{ fontSize: '9px', fontWeight: 600, color: rules.long_duration.pnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                ${rules.long_duration.pnl.toFixed(0)}
                              </div>
                            )}
                          </td>
                          <td style={{ padding: '6px 10px', textAlign: 'center' }}>
                            <div>{typeof rules.eod_1700 === 'object' ? rules.eod_1700.count : (rules.eod_1700 || 0)}</div>
                            {typeof rules.eod_1700 === 'object' && rules.eod_1700.pnl !== 0 && (
                              <div style={{ fontSize: '9px', fontWeight: 600, color: rules.eod_1700.pnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                ${rules.eod_1700.pnl.toFixed(0)}
                              </div>
                            )}
                          </td>
                          <td style={{ padding: '6px 10px', textAlign: 'center' }}>
                            <div>{typeof rules.outliers === 'object' ? rules.outliers.count : (rules.outliers || 0)}</div>
                            {typeof rules.outliers === 'object' && rules.outliers.pnl !== 0 && (
                              <div style={{ fontSize: '9px', fontWeight: 600, color: rules.outliers.pnl >= 0 ? '#16a34a' : '#dc2626' }}>
                                ${rules.outliers.pnl.toFixed(0)}
                              </div>
                            )}
                          </td>
                          <td style={{ padding: '6px 10px', textAlign: 'center' }}>
                            {/* Bad Price: No PnL needed/calculated */}
                            {typeof rules.price_mismatch === 'object' ? rules.price_mismatch.count : (rules.price_mismatch || 0)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="monitoring-grid">
        <div className="control-section" style={{ position: 'relative', overflow: 'hidden' }}>
          <div className="section-title">
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>📥</span> Ingestion
            </h2>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <label style={{ fontSize: '10px', fontWeight: 800, color: ingestionEnabled ? '#10b981' : '#ef4444', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <input type="checkbox" checked={ingestionEnabled} onChange={(e) => setIngestionEnabled(e.target.checked)} />
                {ingestionEnabled ? 'ENABLED' : 'LOCKED'}
              </label>
              <button className="btn btn-import" onClick={() => setPasteModal(true)}>
                <span>📋</span> PASTE
              </button>
            </div>
          </div>

          {!ingestionEnabled && (
            <div style={{
              position: 'absolute',
              top: '60px', left: 0, right: 0, bottom: 0,
              background: 'rgba(254, 242, 242, 0.4)',
              backdropFilter: 'blur(1px)',
              zIndex: 10,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
              border: '2px dashed #fee2e2',
              borderRadius: '0 0 12px 12px'
            }}>
              <span style={{ color: '#ef4444', fontWeight: 900, fontSize: '14px', transform: 'rotate(-5deg)', padding: '10px 20px', border: '3px solid #ef4444', borderRadius: '8px' }}>READ ONLY MODE</span>
            </div>
          )}

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            padding: '10px 14px',
            background: '#f8fafc',
            borderRadius: '10px',
            border: '1px solid #e2e8f0',
            marginBottom: '4px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '11px',
                fontWeight: 900,
                cursor: 'pointer',
                color: importDays === '0' ? '#2563eb' : '#64748b',
                letterSpacing: '0.05em'
              }}>
                <input
                  type="checkbox"
                  checked={importDays === '0'}
                  onChange={(e) => updateImportDays(e.target.checked ? '0' : '30')}
                />
                {importDays === '0' ? 'FULL HISTORY' : 'SELECTIVE'}
              </label>

              {importDays !== '0' && (
                <div style={{ display: 'flex', alignItems: 'center', background: 'white', padding: '2px 8px', borderRadius: '6px', fontSize: '10px', border: '1px solid #e2e8f0' }}>
                  <span style={{ marginRight: '4px', color: '#94a3b8', fontWeight: 600 }}>LOOKBACK:</span>
                  <input
                    type="number"
                    value={importDays}
                    onChange={(e) => updateImportDays(e.target.value)}
                    style={{ width: '25px', border: 'none', outline: 'none', fontWeight: 900, color: '#1e293b', textAlign: 'center', fontSize: '11px' }}
                  />
                  <span style={{ marginLeft: '1px', color: '#94a3b8' }}>D</span>
                </div>
              )}
            </div>
          </div>

          <div className="ingestion-list">
            {scanners.map(s => (
              <div key={s.symbol} className="ingestion-card">
                <div className="card-header">
                  <span className="symbol-name">{s.symbol}</span>
                  <div className="button-group">
                    {s.status === 'scanning' ? (
                      <button className="btn btn-scan" disabled>⌛ ...</button>
                    ) : (s.status === 'importing' || (globalImportStatus?.running && globalImportStatus.message.includes(s.symbol))) ? (
                      <button className="btn btn-import" disabled style={{ opacity: 0.7, cursor: 'not-allowed' }}>🚀 ...</button>
                    ) : s.status === 'ready' ? (
                      <button className="btn btn-import" onClick={() => handleImport(s.symbol)} disabled={!ingestionEnabled}>SYNC</button>
                    ) : (
                      <button className="btn btn-scan" onClick={() => handleScan(s.symbol)} disabled={!ingestionEnabled}>SCAN</button>
                    )}
                  </div>
                </div>
                <div className="path-input-group">
                  <input
                    type="text"
                    value={s.path}
                    onChange={(e) => updatePath(s.symbol, e.target.value)}
                    placeholder={`Path for ${s.symbol}...`}
                    title={s.path}
                  />
                  {s.message && (
                    <div style={{
                      fontSize: '10px',
                      marginTop: '4px',
                      color: s.status === 'error' ? '#ef4444' : '#3b82f6',
                      fontWeight: 800,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      {s.status === 'error' ? '🔴' : '🔵'} {s.message}
                    </div>
                  )}
                </div>
                {s.status === 'ready' && s.detectedAccounts.length > 0 && (
                  <div className="account-selection-grid">
                    <label className="acc-select-item" style={{ borderBottom: '1px solid #f1f5f9', marginBottom: '6px', paddingBottom: '6px', fontWeight: 900, width: '100%', color: '#2563eb', fontSize: '10px' }}>
                      <input type="checkbox"
                        checked={s.selectedAccounts.length === s.detectedAccounts.length}
                        onChange={() => setScanners(prev => prev.map(ps => ps.symbol === s.symbol ? {
                          ...ps, selectedAccounts: ps.selectedAccounts.length === ps.detectedAccounts.length ? [] : [...ps.detectedAccounts]
                        } : ps))}
                      /> SELECT ALL ({s.detectedAccounts.length})
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
        </div>

        {/* 📊 ASSET MANAGEMENT PANEL (Now correctly inside grid) */}
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
            <div className="section-title">
              <h2>Manual Paste Import</h2>
              <button onClick={() => setPasteModal(false)}>✕</button>
            </div>
            <textarea
              className="paste-textarea"
              ref={importTextRef}
              placeholder="Paste TradesList.txt content here..."
              defaultValue={""}
            />
            {importResult && (
              <div style={{ background: '#f0fdf4', padding: '15px', marginTop: '15px', borderRadius: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                <div style={{ fontWeight: 700, color: '#166534', marginBottom: '8px' }}>
                  Result: {importResult.new_trades} added, {importResult.duplicates} duplicates, {importResult.total_parsed} parsed.
                </div>

                {importResult.stats?.unpaired && (
                  <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '6px', color: '#92400e', marginBottom: '8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>⚠️ <strong>{importResult.stats.unpaired.count}</strong> Unpaired Executions (approx. ${importResult.stats.unpaired.commission_impact} commission)</span>
                    <span style={{ color: '#b45309' }}>These do not form complete trades and are dropped.</span>
                  </div>
                )}

                {importResult.stats && Object.keys(importResult.stats).length > 0 && (
                  <div style={{ background: 'white', borderRadius: '6px', overflow: 'hidden', border: '1px solid #e2e8f0', marginTop: '8px' }}>
                    <table style={{ width: '100%', fontSize: '10px', borderCollapse: 'collapse' }}>
                      <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                        <tr>
                          <th style={{ padding: '6px' }}>ACCOUNT</th>
                          <th style={{ padding: '6px', textAlign: 'center' }}>FUTURE</th>
                          <th style={{ padding: '6px', textAlign: 'center' }}>&gt;24h</th>
                          <th style={{ padding: '6px', textAlign: 'center' }}>EOD (17:00)</th>
                          <th style={{ padding: '6px', textAlign: 'center' }}>OUTLIERS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(importResult.stats).map(([acc, rules]: any) => (
                          <tr key={acc} style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '6px', fontWeight: 700 }}>{acc}</td>
                            <td style={{ padding: '6px', textAlign: 'center', color: rules.future?.count ? '#ef4444' : '#166534' }}>
                              {rules.future?.count || 0}
                              {rules.future?.pnl !== 0 && <div style={{ fontSize: '9px' }}>${rules.future?.pnl?.toFixed(0)}</div>}
                            </td>
                            <td style={{ padding: '6px', textAlign: 'center', color: rules.long_duration?.count ? '#ef4444' : '#166534' }}>
                              {rules.long_duration?.count || 0}
                              {rules.long_duration?.pnl !== 0 && <div style={{ fontSize: '9px' }}>${rules.long_duration?.pnl?.toFixed(0)}</div>}
                            </td>
                            <td style={{ padding: '6px', textAlign: 'center', color: rules.eod_1700?.count ? '#ef4444' : '#166534' }}>
                              {rules.eod_1700?.count || 0}
                              {rules.eod_1700?.pnl !== 0 && <div style={{ fontSize: '9px' }}>${rules.eod_1700?.pnl?.toFixed(0)}</div>}
                            </td>
                            <td style={{ padding: '6px', textAlign: 'center', color: rules.outliers?.count ? '#ef4444' : '#166534' }}>
                              {rules.outliers?.count || 0}
                              {rules.outliers?.pnl !== 0 && <div style={{ fontSize: '9px' }}>${rules.outliers?.pnl?.toFixed(0)}</div>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {importResult.errors && importResult.errors.length > 0 && (
                  <div style={{ marginTop: '10px', padding: '10px', background: '#fef2f2', borderRadius: '6px', fontSize: '11px', color: '#b91c1c' }}>
                    <strong>Errors ({importResult.errors.length}):</strong>
                    <ul style={{ margin: '5px 0 0 15px', padding: 0 }}>
                      {importResult.errors.slice(0, 5).map((e: string, i: number) => <li key={i}>{e}</li>)}
                      {importResult.errors.length > 5 && <li>...and {importResult.errors.length - 5} more</li>}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <div className="modal-footer">
              <button className="btn" onClick={() => setPasteModal(false)}>Close</button>
              <button
                className="btn btn-import"
                onClick={async () => {
                  if (!importTextRef.current?.value) return;
                  setIsSaving(true);
                  setImportResult(null);
                  try {
                    const res = await fetch('http://localhost:8000/api/v1/trades/import-paste', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ text: importTextRef.current.value })
                    });
                    if (!res.ok) throw new Error(res.statusText);
                    const result = await res.json();
                    setImportResult(result);
                    setIsSaving(false);
                    fetchData();

                    // Auto-close after 3 seconds to show summary, then cleanup
                    setTimeout(() => {
                      setPasteModal(false);
                      setImportResult(null);
                      if (importTextRef.current) importTextRef.current.value = "";
                    }, 3000);
                  } catch (e) {
                    setIsSaving(false);
                    alert("Import failed: " + e);
                  }
                }}
              >
                {isSaving ? 'Saving...' : 'Start Import'}
              </button>
            </div>
          </div>
        </div>
      )
      }

      {
        viewTradesModal.open && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ width: '900px' }}>
              <div className="section-title">
                <h2>Recent Trades: {viewTradesModal.account} ({viewTradesModal.symbol})</h2>
                <button onClick={() => setViewTradesModal({ open: false })}>✕</button>
              </div>
              <table className="management-table">
                <thead><tr><th>Time</th><th>Side</th><th>Price</th><th>Profit</th></tr></thead>
                <tbody>
                  {recentTrades.map((t, i) => (
                    <tr key={i}>
                      <td>{new Date(t.entry_time).toLocaleString()}</td>
                      <td><span className={`pill ${t.side?.toLowerCase()}`}>{t.side}</span></td>
                      <td>{t.entry_price}</td>
                      <td className={(t.profit_loss || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'}>
                        ${(t.profit_loss || 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="modal-footer">
                <button className="btn" onClick={() => setViewTradesModal({ open: false })}>Close</button>
              </div>
            </div>
          </div>
        )
      }

      {
        validationModal.open && (
          <div className="modal-overlay">
            <div className="modal-content">
              <div className="section-title">
                <h2>Validation Report: {validationModal.account}</h2>
                <button onClick={() => setValidationModal({ open: false })}>✕</button>
              </div>
              {!validationModal.data ? 'Validating...' : (
                <div className="validation-result" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
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
                    <p style={{ fontSize: '12px', color: '#7c2d12', marginBottom: '12px' }}>
                      This will remove future-dated trades and overnight holds to fix your P&L and Days Ago stats.
                    </p>
                    <button className="btn" style={{ background: '#ea580c', color: 'white' }} onClick={() => handlePurgeAnomalies(validationModal.account!, filterSymbol)}>
                      ✨ Clean All Anomalies
                    </button>
                  </div>
                </div>
              )}
              <div className="modal-footer">
                <button className="btn" onClick={() => setValidationModal({ open: false })}>Close</button>
              </div>
            </div>
          </div>
        )
      }

      {
        deleteConfirm && (
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
        )
      }
      {
        showRules && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ width: '500px' }}>
              <div className="section-title">
                <h2>🛡️ Import Shield Rules</h2>
                <button className="icon-btn" onClick={() => setShowRules(false)}>✕</button>
              </div>
              <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '15px' }}>
                These rules are applied automatically during every import to ensure your performance stats are clean and accurate.
              </p>
              <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse', borderRadius: '8px', overflow: 'hidden' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                    <th style={{ padding: '10px', textAlign: 'left' }}>RULE</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>CONDITION</th>
                    <th style={{ padding: '10px', textAlign: 'center' }}>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>Future</strong></td>
                    <td style={{ padding: '10px' }}>Entry &gt; 2 days in future</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>&gt;24hrs</strong></td>
                    <td style={{ padding: '10px' }}>Duration exceeds 24 hours</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>EOD (17:00)</strong></td>
                    <td style={{ padding: '10px' }}>Open &lt; 17:00 &amp; Close &gt; 18:00</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>Outliers</strong></td>
                    <td style={{ padding: '10px' }}>PnL &gt; $50,000 per trade</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>Bad Price</strong></td>
                    <td style={{ padding: '10px' }}>Price outside symbol limits</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                </tbody>
              </table>
              <div className="modal-footer" style={{ marginTop: '20px' }}>
                <button className="btn" onClick={() => setShowRules(false)}>Got it</button>
              </div>
            </div>
          </div>
        )
      }

      {/* --- VIX DATA MODAL --- */}
      {showVixModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ width: '1000px' }}>
            <div className="section-title">
              <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>📊</span> VIX Hourly Historical Data (Last 500 bars)
              </h2>
              <button onClick={() => setShowVixModal(false)} className="icon-btn">✕</button>
            </div>

            <div style={{ maxHeight: '60vh', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '12px' }}>
              <table className="management-table">
                <thead>
                  <tr style={{ position: 'sticky', top: 0, background: 'white', zIndex: 1, borderBottom: '2px solid #cbd5e1' }}>
                    <th style={{ background: '#f8fafc' }}>Timestamp (NY)</th>
                    <th style={{ background: '#f8fafc' }}>Open</th>
                    <th style={{ background: '#f8fafc' }}>High</th>
                    <th style={{ background: '#f8fafc' }}>Low</th>
                    <th style={{ background: '#f8fafc' }}>Close</th>
                    <th style={{ background: '#f8fafc' }}>Change</th>
                  </tr>
                </thead>
                <tbody>
                  {vixData.map((v, i) => {
                    const diff = i < vixData.length - 1 ? (v.close - vixData[i + 1].close) : 0;
                    return (
                      <tr key={i}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 700 }}>{v.timestamp.replace('T', ' ').split(':')[0] + ':' + v.timestamp.split(':')[1]}</td>
                        <td>{v.open.toFixed(2)}</td>
                        <td style={{ color: '#059669', fontWeight: 600 }}>{v.high.toFixed(2)}</td>
                        <td style={{ color: '#dc2626', fontWeight: 600 }}>{v.low.toFixed(2)}</td>
                        <td style={{ fontWeight: 800 }}>{v.close.toFixed(2)}</td>
                        <td>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            fontWeight: 900,
                            background: diff > 0 ? '#dcfce7' : diff < 0 ? '#fee2e2' : '#f1f5f9',
                            color: diff > 0 ? '#166534' : diff < 0 ? '#991b1b' : '#64748b'
                          }}>
                            {diff > 0 ? '+' : ''}{diff.toFixed(2)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="modal-footer">
              <button className="btn btn-scan" onClick={() => setShowVixModal(false)}>Close</button>
              <button className="btn btn-import" onClick={handleImportVix} disabled={isSaving}>
                {isSaving ? 'UPDATING...' : 'REFRESH FROM SOURCE'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Monitoring;
