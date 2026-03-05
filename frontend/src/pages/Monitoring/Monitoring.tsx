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
  finish_time?: string;
}

const API_BASE = `http://${window.location.hostname}:8000`;

const Monitoring = () => {
  const dispatch = useDispatch<AppDispatch>();
  // Data States
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [tradesSize, setTradesSize] = useState(50);
  const [filterDate, setFilterDate] = useState('');
  const [filterTime, setFilterTime] = useState('00:00');
  const [dbAccounts, setDbAccounts] = useState<Account[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSymbol, setFilterSymbol] = useState('ALL');
  const [globalImportStatus, setGlobalImportStatus] = useState<ImportStatus | null>(null);
  const [dismissedStatus, setDismissedStatus] = useState(false);

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
  const [auditModal, setAuditModal] = useState<{ open: boolean; account?: string; date: string; result?: any }>({ open: false, date: new Date().toISOString().split('T')[0] });
  const [deleteConfirm, setDeleteConfirm] = useState<{ account: string; symbol?: string } | null>(null);

  const importTextRef = useRef<HTMLTextAreaElement>(null);
  const [importResult, setImportResult] = useState<any>(null);
  const [lastImportReport, setLastImportReport] = useState<any>(() => {
    const saved = localStorage.getItem('lastTradeImportReport');
    return saved ? JSON.parse(saved) : null;
  });
  const [showReportModal, setShowReportModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  const [recentTrades, setRecentTrades] = useState<any[]>([]);
  const [displayLimit, setDisplayLimit] = useState(200);

  const [saveStep, setSaveStep] = useState(0);
  const saveMsgs = [
    "Ripping Sierra Fills...",
    "Reconstructing Trade Pairs...",
    "Deduplicating Database...",
    "Checking High-PnL Outliers...",
    "Running Shield Filters...",
    "Finalizing Performance Stats..."
  ];

  useEffect(() => {
    let interval: any;
    if (isSaving) {
      setSaveStep(0);
      interval = setInterval(() => {
        setSaveStep(prev => (prev + 1) % saveMsgs.length);
      }, 2500);
    }
    return () => clearInterval(interval);
  }, [isSaving]);

  const [importDays, setImportDays] = useState('2000');
  const [vixData, setVixData] = useState<any[]>([]);
  const [showVixModal, setShowVixModal] = useState(false);
  const [ingestionEnabled, setIngestionEnabled] = useState(true);

  // --- Fetching ---
  const fetchData = useCallback(async () => {
    try {
      const accRes = await fetch(`${API_BASE}/api/system/accounts`);
      const accData = await accRes.json();
      if (Array.isArray(accData)) {
        setDbAccounts(accData);
        dispatch(fetchAccounts());
      }

      const statusRes = await fetch(`${API_BASE}/api/system/status`);
      const statusData = await statusRes.json();
      if (Array.isArray(statusData)) setSystemStatus(statusData);

      // Fetch saved settings
      const settingsRes = await fetch(`${API_BASE}/api/system/settings`);
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
      const res = await fetch(`${API_BASE}/api/system/import-status`);
      const data = await res.json();
      setGlobalImportStatus(data);
      if (data.running) {
        setDismissedStatus(false);
        fetchData(); // Refresh list while importing
      } else {
        // If import finished, reset any scanners that were in 'importing' state
        setScanners(prev => prev.map(s => s.status === 'importing' ? { ...s, status: 'ready' } : s));
      }
    } catch (e) { console.error(e); }
  }, [fetchData]);

  useEffect(() => {
    fetchData();
    fetchImportStatus();
    const interval = setInterval(() => {
      fetchData();
      fetchImportStatus();
    }, 3000); // Heartbeat (3s for better responsiveness during imports)
    return () => clearInterval(interval);
  }, []); // Remove fetchData and fetchImportStatus from deps to avoid infinite loops if setScanners triggers re-fetch

  // --- Actions ---
  const handleSaveSettings = async (updatedScanners: any[], days?: string) => {
    try {
      await fetch(`${API_BASE}/api/system/settings`, {
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
      const res = await fetch(`${API_BASE}/api/system/check-path`, {
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
    setDismissedStatus(false);
    setScanners(p => p.map(s => s.symbol === symbol ? { ...s, status: 'importing' } : s));
    try {
      const paths = [scanner.path];
      await fetch(`${API_BASE}/api/system/import-start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, symbol, accounts: scanner.selectedAccounts, days: parseInt(importDays) })
      });
      // Small delay to ensure backend has started and status is updated
      setTimeout(fetchImportStatus, 500);
    } catch (e) {
      console.error("Import start failed:", e);
    }
    // Note: We don't reset to 'ready' here immediately if globalImportStatus shows it's running for this symbol
  };

  const handleStopImport = async () => {
    try {
      await fetch(`${API_BASE}/api/system/import-stop`, { method: 'POST' });
      setTimeout(fetchImportStatus, 500);
    } catch (e) { console.error(e); }
  };

  const handlePurgeAnomalies = async (account: string, symbol: string) => {
    if (!window.confirm(`Permanently remove future trades, PnL outliers and overnight holds for ${account}?`)) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/system/purge-anomalies`, {
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

  const handleViewRecent = async (account: string, symbol: string, size = 50, dateStr = filterDate, timeStr = filterTime) => {
    setViewTradesModal({ open: true, account, symbol });
    setRecentTrades([]);
    setTradesSize(size);
    setDisplayLimit(200); // Reset for new view
    try {
      let url = `${API_BASE}/api/v1/trades/?account_name=${account}&symbol=${symbol}&size=${size}&page=1&sort=ASC`;
      if (dateStr) {
        url += `&start_date=${dateStr}T${timeStr}:00`;
      }
      const res = await fetch(url);
      const data = await res.json();
      setRecentTrades(data.data?.items || []);
    } catch (e) { console.error(e); }
  };

  const handleValidate = async (account: string, symbol: string) => {
    setValidationModal({ open: true, account });
    try {
      const res = await fetch(`${API_BASE}/api/v1/accounts/accounts/${account}/validate?symbol=${symbol}`);
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

  const handleWipeAllData = async () => {
    if (!window.confirm("⚠️ DANGER: This will permanently delete ALL trade data across ALL accounts. Are you absolutely sure?")) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/system/wipe-db`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || "Database wiped successfully.");
      fetchData();
    } catch (e) {
      console.error(e);
      alert("Failed to wipe database: " + e);
    }
    setIsSaving(false);
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      const url = `${API_BASE}/api/system/remove-cluster?account=${encodeURIComponent(deleteConfirm.account)}${deleteConfirm.symbol ? `&symbol=${encodeURIComponent(deleteConfirm.symbol)}` : ''}`;
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
    setShowRestartConfirm(false);
    console.log("[SYSTEM] Restarting...");
    setIsRestarting(true);

    try {
      // Trigger restart
      fetch(`${API_BASE}/api/system/restart`, { method: 'POST' }).catch(err => {
        console.log("[SYSTEM] Connection dropped - this is expected.");
      });

      // Show countdown or clear message
      setTimeout(() => {
        setIsRestarting(false);
        window.location.reload();
      }, 10000);
    } catch (e) {
      console.error("[SYSTEM] Restart failed:", e);
      setIsRestarting(false);
      alert("Error triggering restart: " + e);
    }
  };

  const fetchVixData = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/vix-data?limit=5000`);
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
      const res = await fetch(`${API_BASE}/api/system/import-vix`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || "VIX Data Imported");
      // Refresh after import
      await fetchVixData();
    } catch (e) {
      alert("Failed to import VIX: " + e);
    }
    setIsSaving(false);
  };

  const handleAudit = async () => {
    if (!auditModal.account || !importTextRef.current?.value) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/system/audit-trades`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account: auditModal.account,
          date: auditModal.date,
          raw_text: importTextRef.current.value
        })
      });
      const data = await res.json();
      setAuditModal(prev => ({ ...prev, result: data }));
    } catch (e) {
      alert("Audit failed: " + e);
    }
    setIsSaving(false);
  };

  const renderImportSummary = (result: any) => {
    if (!result) return null;
    return (
      <div style={{ background: '#f0fdf4', padding: '15px', marginTop: '15px', borderRadius: '8px', maxHeight: '400px', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, color: '#166534', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Result: {result.new_trades} added, {result.duplicates} duplicates, {result.total_parsed} parsed.</span>
          {result.import_time && <span style={{ fontSize: '10px', color: '#64748b', opacity: 0.8 }}>🕒 {new Date(result.import_time).toLocaleString()}</span>}
        </div>

        {result.dropped_ghost_fills && result.dropped_ghost_fills.length > 0 && (
          <div className="ghost-fills-warning">
            <h3>⚠️ Simulation Ghost Fills Blocked ({result.dropped_ghost_fills.length})</h3>
            <p style={{ fontSize: '11px', marginBottom: '5px' }}>The precision engine dropped mathematically impossible ghost fills to protect your PnL accuracy:</p>
            <ul style={{ maxHeight: '150px', overflowY: 'auto', background: 'rgba(0,0,0,0.03)', padding: '8px 12px', borderRadius: '6px' }}>
              {result.dropped_ghost_fills.slice(0, 100).map((fill: any, i: number) => (
                <li key={i} style={{ fontSize: '10px', marginBottom: '2px' }}>
                  <strong>{fill.timestamp?.split('T')[1]?.split('.')[0] || '??:??'}</strong> - {fill.account} | <strong>{fill.side} {fill.dropped_qty}</strong> | Blocked at Limit {fill.limit}
                </li>
              ))}
              {result.dropped_ghost_fills.length > 100 && (
                <li style={{ fontSize: '10px', color: '#64748b', marginTop: '5px', listStyle: 'none', fontWeight: 700 }}>
                  ... and {result.dropped_ghost_fills.length - 100} more (See logs/import_clipping.log for full list)
                </li>
              )}
            </ul>
          </div>
        )}

        {result.errors && result.errors.length > 0 && (
          <div className="parsing-errors" style={{ background: '#fff7ed', border: '1px solid #ffedd5', padding: '10px', borderRadius: '6px', marginBottom: '10px' }}>
            <h4 style={{ margin: 0, color: '#9a3412', fontSize: '12px' }}>⚠️ Import Warnings</h4>
            <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px', fontSize: '11px', color: '#7c2d12' }}>
              {result.errors.slice(0, 20).map((err: string, i: number) => <li key={i}>{err}</li>)}
              {result.errors.length > 20 && <li>...and {result.errors.length - 20} more warnings.</li>}
            </ul>
          </div>
        )}

        {result.stats?.unpaired && (
          <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '6px', color: '#92400e', marginBottom: '8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>⚠️ <strong>{result.stats.unpaired.count}</strong> Unpaired Executions (approx. ${result.stats.unpaired.commission_impact} commission)</span>
            <span style={{ color: '#b45309' }}>These do not form complete trades and are dropped.</span>
          </div>
        )}
        {result.stats?.unpaired?.count > 100 && (
          <div style={{ padding: '8px 12px', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '6px', color: '#1e40af', marginBottom: '8px', fontSize: '11px' }}>
            <strong>Tip:</strong> Binary import pairs fills by FIFO only (no Open/Close). For a list that matches Sierra Chart’s Trades tab, use Trade Activity Log → File → Save Log As and import the text file (includes Open/Close).
          </div>
        )}

        {result.stats && Object.keys(result.stats).filter(k => !['unpaired', 'fills_count', 'trades_closed', 'found', 'processed', 'dropped_long_duration', 'dropped_outliers', 'dropped_eod_1700', 'dropped_pct', 'unpaired_fills', 'breakdown'].includes(k)).length > 0 && (
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
                {Object.entries(result.stats).filter(([k]) => !['unpaired', 'fills_count', 'trades_closed', 'found', 'processed', 'dropped_long_duration', 'dropped_outliers', 'dropped_eod_1700', 'dropped_pct', 'unpaired_fills', 'breakdown'].includes(k)).map(([acc, rules]: any) => (
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
      </div>
    );
  };

  const filtered = dbAccounts.filter(a => filterSymbol === 'ALL' || a.base_symbol === filterSymbol);
  const totalVolume = systemStatus.find(s => s.component.includes('Trades Table'))?.component?.match(/\((.*) records\)/)?.[1] || '0';

  return (
    <div className="monitoring">
      {/* 🔄 Restarting Overlay */}
      {isRestarting && (
        <div className="modal-overlay" style={{ zIndex: 9999, background: 'rgba(15, 23, 42, 0.9)', backdropFilter: 'blur(8px)' }}>
          <div style={{ textAlign: 'center', color: 'white', animation: 'fadeIn 0.5s ease' }}>
            <div className="status-dot online" style={{ width: '60px', height: '60px', margin: '0 auto 20px', background: '#3b82f6', boxShadow: '0 0 20px rgba(59, 130, 246, 0.5)' }}></div>
            <h1 style={{ fontSize: '32px', fontWeight: 900, marginBottom: '10px', letterSpacing: '-0.02em' }}>🔄 SYSTEM RESTARTING</h1>
            <p style={{ fontSize: '18px', opacity: 0.8, fontWeight: 500 }}>The backend service is being power-cycled.</p>
            <div style={{ marginTop: '30px', display: 'flex', justifyContent: 'center', gap: '5px' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{ width: '8px', height: '8px', background: 'white', borderRadius: '50%', animation: `pulse 1.5s infinite ${i * 0.2}s` }}></div>
              ))}
            </div>
            <p style={{ fontSize: '13px', marginTop: '20px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Reconnecting in a few seconds...
            </p>
          </div>
        </div>
      )}
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

          <button
            className="btn btn-scan"
            style={{
              backgroundColor: isRestarting ? '#94a3b8' : '#dc2626',
              marginLeft: '10px',
              color: 'white',
              cursor: isRestarting ? 'not-allowed' : 'pointer',
              opacity: isRestarting ? 0.7 : 1
            }}
            onClick={() => setShowRestartConfirm(true)}
            disabled={isRestarting}
          >
            {isRestarting ? '⏳ RESTARTING...' : '⚠️ RESTART BACKEND'}
          </button>
        </div>
      </div>

      {/* Global Import Progress (Active or Freshly Finished) */}
      {!dismissedStatus && (globalImportStatus?.running || globalImportStatus?.message?.includes('Error') || (globalImportStatus?.finish_time && (
        (new Date().getTime() - new Date(globalImportStatus.finish_time).getTime()) < 60000
      ))) && (
          <div style={{
            background: globalImportStatus.running ? '#eff6ff' : (globalImportStatus.message?.includes('Error') ? '#fef2f2' : '#f0fdf4'),
            border: '1px solid',
            borderColor: globalImportStatus.running ? '#bfdbfe' : (globalImportStatus.message?.includes('Error') ? '#fecaca' : '#bbf7d0'),
            borderRadius: '12px',
            padding: '15px',
            marginBottom: '24px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontWeight: 700, color: globalImportStatus.running ? '#1e40af' : (globalImportStatus.message?.includes('Error') ? '#b91c1c' : '#166534'), display: 'flex', alignItems: 'center', gap: '8px' }}>
                {globalImportStatus.running ? (
                  <>🚀 Import in Progress...</>
                ) : (
                  <>
                    {globalImportStatus.message?.includes('Error') ? '❌ Import Failed' : '✅ Import Finished'}
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
                  <button onClick={() => setDismissedStatus(true)} className="icon-btn">✕</button>
                )}
              </div>
            </div>

            {globalImportStatus?.message && (
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#1e293b', marginTop: '4px' }}>{globalImportStatus.message}</div>
            )}

            {globalImportStatus?.stats && typeof globalImportStatus.stats === 'object' && globalImportStatus.stats.breakdown && Object.keys(globalImportStatus.stats.breakdown).length > 0 && (
              <div style={{ marginTop: '12px', borderTop: '1px solid', borderColor: globalImportStatus.message?.includes('Error') ? '#fecaca' : '#bbf7d0', paddingTop: '12px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', marginBottom: '12px', padding: '8px 12px', background: 'rgba(255,255,255,0.5)', borderRadius: '8px', fontSize: '11px' }}>
                  <div style={{ color: '#0369a1' }}><strong>📋 Processed:</strong> {globalImportStatus.stats.processed} files</div>
                  <div style={{ color: '#15803d' }}><strong>➕ Added:</strong> {globalImportStatus.stats.found} trades</div>
                  <div style={{ color: '#b91c1c' }}>
                    <strong>🛡️ Dropped:</strong> {globalImportStatus.stats.dropped_long_duration + globalImportStatus.stats.dropped_outliers + globalImportStatus.stats.dropped_eod_1700 + (globalImportStatus.stats.dropped_ghost_fills?.length || 0)} ({globalImportStatus.stats.dropped_pct}%)
                  </div>
                  {(globalImportStatus.stats.dropped_long_duration > 0 || globalImportStatus.stats.dropped_eod_1700 > 0) && (
                    <div style={{ color: '#c2410c', fontWeight: 700 }}>
                      <strong>Removed:</strong> {globalImportStatus.stats.dropped_long_duration > 0 && (
                        <span>&gt;24h: {globalImportStatus.stats.dropped_long_duration} trades (${Number(globalImportStatus.stats.dropped_long_duration_pnl ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })} PnL)</span>
                      )}
                      {globalImportStatus.stats.dropped_long_duration > 0 && globalImportStatus.stats.dropped_eod_1700 > 0 && ' | '}
                      {globalImportStatus.stats.dropped_eod_1700 > 0 && (
                        <span>EOD(17:00): {globalImportStatus.stats.dropped_eod_1700} trades (${Number(globalImportStatus.stats.dropped_eod_1700_pnl ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })} PnL)</span>
                      )}
                    </div>
                  )}
                  {globalImportStatus.stats.dropped_ghost_fills > 0 && (
                    <div style={{ color: '#ec4899' }}><strong>👻 Ghost:</strong> {globalImportStatus.stats.dropped_ghost_fills} fills</div>
                  )}
                  {globalImportStatus.stats.dropped_drift > 0 && (
                    <div style={{ color: '#f59e0b' }}><strong>🛡️ Drift:</strong> {globalImportStatus.stats.dropped_drift} fills</div>
                  )}
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
                          <th style={{ padding: '6px 10px', textAlign: 'center', color: '#ec4899' }}>GHOSTS</th>
                          <th style={{ padding: '6px 10px', textAlign: 'center', color: '#f59e0b' }}>DRIFT</th>
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
                            <td style={{ padding: '6px 10px', textAlign: 'center', color: rules.ghost?.count ? '#ec4899' : '#94a3b8' }}>
                              {rules.ghost?.count || 0}
                            </td>
                            <td style={{ padding: '6px 10px', textAlign: 'center', color: rules.drift?.count ? '#f59e0b' : '#94a3b8' }}>
                              {rules.drift?.count || 0}
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
              <button
                className="btn btn-scan"
                onClick={() => setShowReportModal(true)}
                disabled={!lastImportReport}
                style={{
                  opacity: lastImportReport ? 1 : 0.5,
                  background: lastImportReport ? '#f0f9ff' : undefined,
                  border: lastImportReport ? '1px solid #bae6fd' : undefined,
                  color: lastImportReport ? '#0369a1' : undefined
                }}
              >
                <span>📜</span> LATEST REPORT
              </button>
            </div>
          </div>

          {!ingestionEnabled && (
            <div style={{
              position: 'absolute',
              top: '60px', left: 0, right: 0, height: '30px',
              background: 'rgba(239, 68, 68, 0.9)',
              color: 'white',
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '10px',
              fontWeight: 900,
              letterSpacing: '0.1em'
            }}>
              🔒 INGESTION LOCKED (READ ONLY)
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
                      <button className="btn btn-import" onClick={() => handleImport(s.symbol)} disabled={!ingestionEnabled}>IMPORT</button>
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
                  <th style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    Action
                    <button
                      className="icon-btn"
                      onClick={handleWipeAllData}
                      title="WIPE ENTIRE DATABASE"
                      style={{ color: '#ef4444', fontSize: '14px', marginLeft: 'auto' }}
                    >
                      🗑️
                    </button>
                  </th>
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
                          <button className="icon-btn" onClick={() => handleViewRecent(acc.name, acc.base_symbol)} title="View Trades">👁️</button>
                          <button className="icon-btn" onClick={() => setAuditModal({ open: true, account: acc.name, date: new Date().toISOString().split('T')[0] })} title="Data Trust Audit" style={{ background: '#eff6ff', borderRadius: '4px' }}>🛡️</button>
                          <button className="icon-btn" onClick={() => setDeleteConfirm({ account: acc.name, symbol: acc.base_symbol })} title="Delete Cluster">🗑️</button>
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
      {
        pasteModal && (
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
              {renderImportSummary(importResult)}
              <div className="modal-footer">
                <button className="btn" onClick={() => setPasteModal(false)} disabled={isSaving}>Close</button>
                <button
                  className="btn btn-import"
                  disabled={isSaving}
                  onClick={async () => {
                    if (!importTextRef.current?.value) return;
                    setIsSaving(true);
                    setImportResult(null);
                    try {
                      const res = await fetch(`${API_BASE}/api/v1/trades/import-paste`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: importTextRef.current.value })
                      });
                      if (!res.ok) throw new Error(res.statusText);
                      const result = await res.json();
                      const reportWithTime = { ...result, import_time: new Date().toISOString() };
                      setImportResult(reportWithTime);
                      setLastImportReport(reportWithTime);
                      localStorage.setItem('lastTradeImportReport', JSON.stringify(reportWithTime));
                      setIsSaving(false);
                      fetchData();
                    } catch (e) {
                      setIsSaving(false);
                      alert("Import failed: " + e);
                    }
                  }}
                >
                  {isSaving ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className="status-dot online" style={{ width: '8px', height: '8px' }}></div>
                      {saveMsgs[saveStep]}
                    </span>
                  ) : 'Start Import'}
                </button>
              </div>
            </div>
          </div>
        )
      }

      {
        viewTradesModal.open && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ width: '1000px', maxWidth: '95%' }}>
              <div className="section-title">
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <h2 style={{ margin: 0 }}>📊 Performance History: {viewTradesModal.account}</h2>
                  <span className="pill">{viewTradesModal.symbol}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', background: '#f1f5f9', padding: '4px 10px', borderRadius: '8px' }}>
                    <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>Filter Fr:</label>
                    <input
                      type="date"
                      value={filterDate}
                      onChange={(e) => setFilterDate(e.target.value)}
                      style={{ border: '1px solid #cbd5e1', borderRadius: '4px', fontSize: '11px', padding: '2px 5px' }}
                    />
                    <input
                      type="time"
                      value={filterTime}
                      onChange={(e) => setFilterTime(e.target.value)}
                      style={{ border: '1px solid #cbd5e1', borderRadius: '4px', fontSize: '11px', padding: '2px 5px' }}
                    />
                    <button
                      className="btn"
                      style={{ padding: '2px 10px', fontSize: '11px', minWidth: 'auto', background: '#3b82f6', color: 'white' }}
                      onClick={() => handleViewRecent(viewTradesModal.account!, viewTradesModal.symbol!, tradesSize)}
                    >
                      Filter
                    </button>
                    {(filterDate || filterTime !== '00:00') && (
                      <button
                        style={{ background: 'none', border: 'none', color: '#ef4444', fontSize: '10px', cursor: 'pointer', fontWeight: 700 }}
                        onClick={() => { setFilterDate(''); setFilterTime('00:00'); handleViewRecent(viewTradesModal.account!, viewTradesModal.symbol!, tradesSize, '', '00:00'); }}
                      >
                        RESET
                      </button>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>Show:</label>
                    <select
                      value={tradesSize}
                      onChange={(e) => handleViewRecent(viewTradesModal.account!, viewTradesModal.symbol!, parseInt(e.target.value))}
                      style={{ padding: '4px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '11px', fontWeight: 800 }}
                    >
                      <option value="50">Last 50</option>
                      <option value="200">Last 200</option>
                      <option value="1000">Last 1000</option>
                      <option value="100000">ALL</option>
                    </select>
                  </div>
                  <button className="icon-btn" onClick={() => { setViewTradesModal({ open: false }); setFilterDate(''); setFilterTime('00:00'); }}>✕</button>
                </div>
              </div>

              <div
                style={{ maxHeight: '70vh', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                onScroll={(e) => {
                  const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
                  if (scrollHeight - scrollTop - clientHeight < 200) {
                    setDisplayLimit(prev => prev + 500);
                  }
                }}
              >
                <table className="management-table" style={{ fontSize: '12px' }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 5, background: '#f8fafc' }}>
                    <tr>
                      <th>#</th>
                      <th>Entry Time</th>
                      <th>Exit Time</th>
                      <th>Side</th>
                      <th>In</th>
                      <th>Out</th>
                      <th>Qty</th>
                      <th>Profit/Loss</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentTrades.slice(0, displayLimit).map((t, i) => {
                      const nextTrade = recentTrades[i + 1];
                      // Use trip_id from backend if available for visual grouping
                      const showSeparator = nextTrade && t.trip_id && nextTrade.trip_id && t.trip_id !== nextTrade.trip_id;

                      return (
                        <React.Fragment key={t.trade_id || i}>
                          <tr>
                            <td style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '10px' }}>{i + 1}</td>
                            <td style={{ fontWeight: 600 }}>{new Date(t.entry_time).toLocaleString('en-US', { timeZone: 'America/New_York' })}</td>
                            <td>{new Date(t.exit_time).toLocaleTimeString('en-US', { timeZone: 'America/New_York' })}</td>
                            <td><span className={`pill ${t.side?.toLowerCase()}`}>{t.side}</span></td>
                            <td>{t.entry_price.toFixed(2)}</td>
                            <td>{t.exit_price.toFixed(2)}</td>
                            <td style={{ fontWeight: 800 }}>{t.quantity}</td>
                            <td className={(t.profit_loss || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'} style={{ fontSize: '14px' }}>
                              ${(t.profit_loss || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                          </tr>
                          {showSeparator && (
                            <tr key={`sep-${i}`} className="trip-separator">
                              <td colSpan={8}></td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="modal-footer" style={{ borderTop: '1px solid #f1f5f9', paddingTop: '15px' }}>
                <div style={{ flex: 1, fontSize: '12px', color: '#64748b', fontWeight: 500 }}>
                  Showing {recentTrades.length} records.
                </div>
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
        showRestartConfirm && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ width: '400px', textAlign: 'center' }}>
              <h2 style={{ color: '#ef4444' }}>🚀 Confirm Restart</h2>
              <p style={{ margin: '15px 0' }}>The system will be offline for approximately 10 seconds while it power-cycles the backend engine.</p>
              <p style={{ fontSize: '12px', color: '#94a3b8' }}>All active scans will be terminated.</p>
              <div className="modal-footer" style={{ justifyContent: 'center', marginTop: '20px' }}>
                <button className="btn" onClick={() => setShowRestartConfirm(false)}>Cancel</button>
                <button className="btn" style={{ background: '#ef4444', color: 'white' }} onClick={handleRestartBackend}>PRIME RESTART</button>
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
                    <td style={{ padding: '10px' }}><strong>Drift Guard</strong></td>
                    <td style={{ padding: '10px' }}>Net Position &gt; 3 contracts (V_ Accs)</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fef3c7', color: '#d97706' }}>⚠️ WARN</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>Note-Strict (Ghost)</strong></td>
                    <td style={{ padding: '10px' }}>No valid strategy tag in Note (Tag 0x82) & NOT EOD</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>EOD 17:00</strong></td>
                    <td style={{ padding: '10px' }}>16:57 - 17:01 closure window</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#dcfce7', color: '#16a34a' }}>✅ ALLOW</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>Outliers</strong></td>
                    <td style={{ padding: '10px' }}>PnL &gt; 5-sigma OR $50,000</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}><span className="pill" style={{ background: '#fee2e2', color: '#ef4444' }}>❌ DROP</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px' }}><strong>Price Sanity</strong></td>
                    <td style={{ padding: '10px' }}>Price outside market bounds</td>
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
      {
        showVixModal && (
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
        )
      }

      {
        showReportModal && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ width: '800px' }}>
              <div className="section-title">
                <h2>📈 Latest Import Report</h2>
                <button onClick={() => setShowReportModal(false)}>✕</button>
              </div>
              <p style={{ fontSize: '12px', color: '#64748b' }}>
                Summary of the last manual paste or auto-sync activity.
              </p>
              {renderImportSummary(lastImportReport)}
              <div className="modal-footer">
                <button className="btn" onClick={() => setShowReportModal(false)}>Close</button>
                <button className="btn btn-import" onClick={() => { localStorage.removeItem('lastTradeImportReport'); setLastImportReport(null); setShowReportModal(false); }}>🗑️ Clear Report History</button>
              </div>
            </div>
          </div>
        )
      }
      {
        auditModal.open && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ width: '900px' }}>
              <div className="section-title">
                <h2>🛡️ Data Trust Audit: {auditModal.account}</h2>
                <button className="icon-btn" onClick={() => setAuditModal({ open: false, date: '' })}>✕</button>
              </div>

              <div style={{ display: 'flex', gap: '15px', marginBottom: '20px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '11px', fontWeight: 800, color: '#64748b' }}>AUDIT DATE (YYYY-MM-DD)</label>
                  <input
                    type="date"
                    value={auditModal.date}
                    onChange={(e) => setAuditModal(prev => ({ ...prev, date: e.target.value }))}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0', marginTop: '5px' }}
                  />
                </div>
                <div style={{ flex: 3 }}>
                  <label style={{ fontSize: '11px', fontWeight: 800, color: '#64748b' }}>PASTE SC TRADES DATA HERE</label>
                  <textarea
                    ref={importTextRef}
                    placeholder="Go to SC -> Trades -> Select All -> Copy -> Paste here..."
                    style={{ width: '100%', height: '80px', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0', marginTop: '5px', fontSize: '10px', fontFamily: 'monospace' }}
                  />
                </div>
              </div>

              <button className="btn btn-import" onClick={handleAudit} disabled={isSaving || !auditModal.date} style={{ width: '100%', padding: '12px' }}>
                {isSaving ? 'Calculating...' : '🚀 RUN MATHEMATICAL AUDIT'}
              </button>

              {auditModal.result && (
                <div style={{ marginTop: '20px', background: '#f8fafc', padding: '15px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '15px' }}>
                    <div style={{ background: 'white', padding: '10px', borderRadius: '8px', borderLeft: '4px solid #3b82f6' }}>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>MATCHED TRADES</div>
                      <div style={{ fontSize: '18px', fontWeight: 900 }}>{auditModal.result.summary.matched} / {auditModal.result.summary.sc_count}</div>
                      <div style={{ fontSize: '12px', color: auditModal.result.summary.sc_count > 0 && (auditModal.result.summary.matched / auditModal.result.summary.sc_count) >= 0.9 ? '#059669' : '#dc2626', fontWeight: 600 }}>
                        {auditModal.result.summary.sc_count > 0 ? Math.round(100 * auditModal.result.summary.matched / auditModal.result.summary.sc_count) : 0}% match
                      </div>
                    </div>
                    <div style={{ background: 'white', padding: '10px', borderRadius: '8px', borderLeft: '4px solid #10b981' }}>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>DB PNL</div>
                      <div style={{ fontSize: '18px', fontWeight: 900, color: '#059669' }}>${auditModal.result.summary.db_pnl.toLocaleString()}</div>
                    </div>
                    <div style={{ background: 'white', padding: '10px', borderRadius: '8px', borderLeft: '2px solid #94a3b8' }}>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>SC PNL</div>
                      <div style={{ fontSize: '18px', fontWeight: 900 }}>${auditModal.result.summary.sc_pnl.toLocaleString()}</div>
                    </div>
                    <div style={{ background: 'white', padding: '10px', borderRadius: '8px', borderLeft: '4px solid #ef4444' }}>
                      <div style={{ fontSize: '10px', color: '#64748b' }}>PNL DIFF</div>
                      <div style={{ fontSize: '18px', fontWeight: 900, color: '#dc2626' }}>${(auditModal.result.summary.db_pnl - auditModal.result.summary.sc_pnl).toLocaleString()}</div>
                    </div>
                  </div>

                  {auditModal.result.summary.sc_count > 0 && (auditModal.result.summary.matched / auditModal.result.summary.sc_count) < 0.9 && (
                    <div style={{ padding: '10px', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '8px', fontSize: '11px', color: '#92400e', marginBottom: '12px' }}>
                      <strong>To get &gt;90% match with Sierra Chart:</strong> Binary import pairs by FIFO only (no Open/Close). Use Trade Activity Log → File → Save Log As and import the text file (includes Open/Close column) for entry+exit time and price to align with SC.
                    </div>
                  )}

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                    <div>
                      <h4 style={{ fontSize: '11px', color: '#ef4444' }}>⚠️ Rejected by Importer (SC Only)</h4>
                      <p style={{ fontSize: '10px', color: '#64748b' }}>These are likely "Ghost Fills" rejected by Note-Strict or Drift Guard rules.</p>
                      <div style={{ maxHeight: '150px', overflowY: 'auto', background: 'white', borderRadius: '6px', border: '1px solid #fecaca', fontSize: '9px', marginTop: '5px' }}>
                        {auditModal.result.discrepancies.sc_only.length === 0 ? <div style={{ padding: '10px' }}>Perfect match! No SC-only trades.</div> :
                          auditModal.result.discrepancies.sc_only.map((t: any, i: number) => (
                            <div key={i} style={{ padding: '4px 8px', borderBottom: '1px solid #fee2e2' }}>
                              {t.entry_time.split(' ')[1]} | {t.side} | {t.qty} | ${t.pnl} | Px: {t.entry_price}
                            </div>
                          ))
                        }
                      </div>
                    </div>
                    <div>
                      <h4 style={{ fontSize: '11px', color: '#3b82f6' }}>ℹ️ Untracked in SC (DB Only)</h4>
                      <p style={{ fontSize: '10px', color: '#64748b' }}>Trades in our DB that SC didn't report (unlikely if pasting full list).</p>
                      <div style={{ maxHeight: '150px', overflowY: 'auto', background: 'white', borderRadius: '6px', border: '1px solid #bfdbfe', fontSize: '9px', marginTop: '5px' }}>
                        {auditModal.result.discrepancies.db_only.length === 0 ? <div style={{ padding: '10px' }}>No DB-only trades.</div> :
                          auditModal.result.discrepancies.db_only.map((t: any, i: number) => (
                            <div key={i} style={{ padding: '4px 8px', borderBottom: '1px solid #dbeafe' }}>
                              {t.entry_time.split('T')[1]?.split('.')[0]} | {t.side} | {t.qty} | ${t.pnl} | Px: {t.entry_price}
                            </div>
                          ))
                        }
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="modal-footer" style={{ marginTop: '20px' }}>
                <button className="btn" onClick={() => setAuditModal({ open: false, date: '' })}>Close</button>
              </div>
            </div>
          </div>
        )
      }
    </div>
  );
};

export default Monitoring;
