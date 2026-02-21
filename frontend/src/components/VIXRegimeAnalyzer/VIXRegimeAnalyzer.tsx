import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import './VIXRegimeAnalyzer.css';

// ── Interfaces matching actual API responses ──────────────────────────

interface VIXRegimeData {
  date: string;
  vix_level: number;
  regime: 'LOW' | 'MEDIUM' | 'HIGH';
  regime_duration_days: number;
}

interface RegimePerformanceData {
  account: string;
  regime: 'LOW' | 'MEDIUM' | 'HIGH';
  performance_metrics: {
    total_pnl: number;
    average_pnl: number;
    win_rate: number;
    profit_factor: number;
    sharpe_ratio: number;
    total_trades: number;
  };
  statistical_significance: {
    p_value: number;
    is_significant: boolean;
  };
}

interface VIXDistributionData {
  time_bin: string;
  vix_levels: number[];
  regime_counts: { LOW: number; MEDIUM: number; HIGH: number };
  regime_percentages: { LOW: number; MEDIUM: number; HIGH: number };
  average_vix_by_regime: { LOW: number; MEDIUM: number; HIGH: number };
  vix_statistics: { min: number; max: number; mean: number; std: number };
}

interface RegimeTransition {
  date: string;
  from_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  to_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  trigger_vix_level: number;
  days_in_previous_regime: number;
  performance_impact: { performance_change: number };
}

interface CurrentRegimeIndicator {
  current_vix_level: number;
  current_regime: 'LOW' | 'MEDIUM' | 'HIGH';
  days_in_current_regime: number;
  regime_percentile: number;
  regime_forecast: {
    probability_low: number;
    probability_medium: number;
    probability_high: number;
  };
}

// ── New interfaces for profitability analysis ────────────────────────

interface CorrelationTrade {
  date: string;
  pnl: number;
  vix_level: number;
  regime: string;
}

interface PnlCorrelationData {
  trades: CorrelationTrade[];
  correlation: { coefficient: number; p_value: number; interpretation: string } | null;
  regression: { slope: number; intercept: number; r_squared: number } | null;
  optimal_vix_range: { range: number[]; avg_pnl: number; win_rate: number; trade_count: number } | null;
}

interface EquityCurvePoint {
  date: string;
  cumulative_pnl: number;
  trade_pnl: number;
  vix_level: number;
  regime: string;
  drawdown: number;
}

interface EquityByRegimeData {
  equity_curve: EquityCurvePoint[];
  drawdowns_by_regime: Record<string, { max_drawdown: number; avg_drawdown: number; trade_count: number }>;
}

interface TimebinHeatmapEntry {
  hour: number;
  regime: string;
  total_trades: number;
  total_pnl: number;
  avg_pnl: number;
  win_rate: number;
  pnl_delta_vs_overall: number;
  win_rate_delta_vs_overall: number;
}

// ── Props ────────────────────────────────────────────────────────────

interface VIXRegimeAnalyzerProps {
  accountName: string;
  startDate?: string;
  endDate?: string;
  selectedTimeBins?: string[];
  showPerformanceComparison?: boolean;
  showDistributionHistograms?: boolean;
  showTransitionTimeline?: boolean;
  showCurrentIndicator?: boolean;
  height?: number;
  onRegimeClick?: (regime: 'LOW' | 'MEDIUM' | 'HIGH') => void;
  onTransitionClick?: (transition: RegimeTransition) => void;
}

const API_BASE = 'http://localhost:8000/api/vix-regime';

const regimeColors: Record<string, string> = {
  LOW: '#10b981',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444'
};

const VIXRegimeAnalyzer: React.FC<VIXRegimeAnalyzerProps> = ({
  accountName,
  startDate: propStartDate,
  endDate: propEndDate,
  selectedTimeBins = [],
  showPerformanceComparison = true,
  showDistributionHistograms = true,
  showTransitionTimeline = true,
  showCurrentIndicator = true,
  height = 800,
  onRegimeClick,
  onTransitionClick
}) => {
  // ── Date selector state ──────────────────────────────────────────
  // Helper to format dates correctly for HTML5 date inputs (YYYY-MM-DD)
  const formatDateForInput = (dateStr: string | null | undefined): string => {
    if (!dateStr) return '';
    // If it has 'T', it's ISO format, take only the date part
    if (dateStr.includes('T')) return dateStr.split('T')[0];
    // If it's already YYYY-MM-DD or similar, returning slice(0, 10) is safe
    return dateStr.slice(0, 10);
  };

  const defaultStart = new Date();
  defaultStart.setFullYear(defaultStart.getFullYear() - 1);

  const [localStartDate, setLocalStartDate] = useState(
    formatDateForInput(propStartDate) || defaultStart.toISOString().slice(0, 10)
  );
  const [localEndDate, setLocalEndDate] = useState(
    formatDateForInput(propEndDate) || new Date().toISOString().slice(0, 10)
  );

  // Sync with props when they change (e.g. when backtest metadata loads or asset changes)
  useEffect(() => {
    if (propStartDate) {
      const formatted = formatDateForInput(propStartDate);
      setLocalStartDate(formatted);
    }
    if (propEndDate) {
      const formatted = formatDateForInput(propEndDate);
      setLocalEndDate(formatted);
    }
  }, [propStartDate, propEndDate]);

  const startDate = localStartDate;
  const endDate = localEndDate;

  // ── Existing state ───────────────────────────────────────────────
  const [vixData, setVixData] = useState<VIXRegimeData[]>([]);
  const [performanceData, setPerformanceData] = useState<RegimePerformanceData[]>([]);
  const [distributionData, setDistributionData] = useState<VIXDistributionData[]>([]);
  const [transitionData, setTransitionData] = useState<RegimeTransition[]>([]);
  const [currentRegime, setCurrentRegime] = useState<CurrentRegimeIndicator | null>(null);

  // ── New analysis state ───────────────────────────────────────────
  const [correlationData, setCorrelationData] = useState<PnlCorrelationData | null>(null);
  const [equityData, setEquityData] = useState<EquityByRegimeData | null>(null);
  const [heatmapData, setHeatmapData] = useState<TimebinHeatmapEntry[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRegime, setSelectedRegime] = useState<'ALL' | 'LOW' | 'MEDIUM' | 'HIGH'>('ALL');
  const [comparisonMetric, setComparisonMetric] = useState<'total_pnl' | 'win_rate' | 'sharpe_ratio' | 'profit_factor'>('total_pnl');

  const authHeaders = { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` };

  // ── Data fetching ────────────────────────────────────────────────

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const qs = params.toString();

    try {
      // 1. Fetch non-heavy baseline data first
      const dataReqs = await Promise.allSettled([
        fetch(`${API_BASE}/data?${qs}`, { headers: authHeaders }),
        fetch(`${API_BASE}/current`, { headers: authHeaders }),
        fetch(`${API_BASE}/distribution?${qs}`, { headers: authHeaders }),
      ]);

      if (dataReqs[0].status === 'fulfilled' && dataReqs[0].value.ok) setVixData(await dataReqs[0].value.json());
      if (dataReqs[1].status === 'fulfilled' && dataReqs[1].value.ok) setCurrentRegime(await dataReqs[1].value.json());
      if (dataReqs[2].status === 'fulfilled' && dataReqs[2].value.ok) setDistributionData(await dataReqs[2].value.json());

      // 2. Fetch trade-heavy APIs sequentially to prevent SQLite locking and backend timeouts
      const perfRes = await fetch(`${API_BASE}/performance/${accountName}?${qs}`, { headers: authHeaders }).catch(e => null);
      if (perfRes && perfRes.ok) setPerformanceData(await perfRes.json());

      const eqRes = await fetch(`${API_BASE}/equity-by-regime/${accountName}?${qs}`, { headers: authHeaders }).catch(e => null);
      if (eqRes && eqRes.ok) setEquityData(await eqRes.json());

      const corrRes = await fetch(`${API_BASE}/pnl-correlation/${accountName}?${qs}`, { headers: authHeaders }).catch(e => null);
      if (corrRes && corrRes.ok) setCorrelationData(await corrRes.json());

      const hmRes = await fetch(`${API_BASE}/timebin-heatmap/${accountName}?${qs}`, { headers: authHeaders }).catch(e => null);
      if (hmRes && hmRes.ok) setHeatmapData(await hmRes.json());

      const transRes = await fetch(`${API_BASE}/transitions/${accountName}?${qs}`, { headers: authHeaders }).catch(e => null);
      if (transRes && transRes.ok) setTransitionData(await transRes.json());

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load VIX data');
    } finally {
      setIsLoading(false);
    }

  }, [accountName, startDate, endDate]);

  useEffect(() => { fetchAllData(); }, [fetchAllData]);

  // ── Memoized chart data ──────────────────────────────────────────

  // 1. VIX vs P&L Scatter
  const scatterData = useMemo(() => {
    if (!correlationData?.trades?.length) return [];
    const trades = correlationData.trades;
    const regimes: Array<'LOW' | 'MEDIUM' | 'HIGH'> = ['LOW', 'MEDIUM', 'HIGH'];
    const traces: any[] = [];

    regimes.forEach(regime => {
      const filtered = trades.filter(t => t.regime === regime);
      if (!filtered.length) return;
      traces.push({
        x: filtered.map(t => t.vix_level),
        y: filtered.map(t => t.pnl),
        type: 'scatter',
        mode: 'markers',
        name: `${regime} VIX`,
        marker: {
          color: regimeColors[regime],
          size: 8,
          opacity: 0.7,
          line: { color: 'white', width: 1 }
        },
        hovertemplate: 'VIX: %{x:.1f}<br>P&L: $%{y:.2f}<br>Date: %{text}<extra></extra>',
        text: filtered.map(t => t.date)
      });
    });

    // Add regression line
    if (correlationData.regression) {
      const { slope, intercept } = correlationData.regression;
      // Using reduce instead of spread to avoid 'Maximum call stack size exceeded' on large arrays
      const vixLevels = trades.map(t => t.vix_level);
      const xMin = vixLevels.reduce((a, b) => Math.min(a, b), Infinity);
      const xMax = vixLevels.reduce((a, b) => Math.max(a, b), -Infinity);
      traces.push({
        x: [xMin, xMax],
        y: [slope * xMin + intercept, slope * xMax + intercept],
        type: 'scatter',
        mode: 'lines',
        name: `Regression (r=${correlationData.correlation?.coefficient.toFixed(3)})`,
        line: { color: '#6366f1', width: 2, dash: 'dash' },
        hoverinfo: 'skip'
      });
    }

    return traces;
  }, [correlationData, regimeColors]);

  // 2. Equity Curve with Regime Overlay
  const equityCurveData = useMemo(() => {
    if (!equityData?.equity_curve?.length) return [];
    const curve = equityData.equity_curve;

    // Split the curve into segments by regime for better coloring
    const traces: any[] = [];
    let currentSegment: EquityCurvePoint[] = [];
    let currentRegime: string = curve[0].regime;

    curve.forEach((point, i) => {
      if (point.regime !== currentRegime) {
        // Close current segment
        traces.push({
          x: currentSegment.map(p => p.date),
          y: currentSegment.map(p => p.cumulative_pnl),
          type: 'scatter',
          mode: 'lines',
          name: `${currentRegime} Regime`,
          line: { color: regimeColors[currentRegime], width: 2 },
          // Don't fill, just lines for equity curve
        });

        // Start new segment, including the last point of the previous segment to connect them
        currentSegment = [curve[i - 1], point];
        currentRegime = point.regime;
      } else {
        currentSegment.push(point);
      }
    });

    // Add final segment
    if (currentSegment.length > 0) {
      traces.push({
        x: currentSegment.map(p => p.date),
        y: currentSegment.map(p => p.cumulative_pnl),
        type: 'scatter',
        mode: 'lines',
        name: `${currentRegime} Regime`,
        line: { color: regimeColors[currentRegime], width: 2 },
      });
    }

    // Add VIX secondary axis line
    traces.push({
      x: curve.map(p => p.date),
      y: curve.map(p => p.vix_level),
      type: 'scatter',
      mode: 'lines',
      name: 'VIX Level',
      yaxis: 'y2',
      line: { color: '#94a3b8', width: 1, dash: 'dot' },
      opacity: 0.3
    });

    return traces;
  }, [equityData, regimeColors]);

  // 3. P&L by Regime Bars
  const regimeBarData = useMemo(() => {
    if (!performanceData.length) return [];
    const traces: any[] = [];
    const regimes: Array<'LOW' | 'MEDIUM' | 'HIGH'> = ['LOW', 'MEDIUM', 'HIGH'];

    const metricFormatters: Record<string, (d: RegimePerformanceData) => number> = {
      total_pnl: d => d.performance_metrics.total_pnl,
      win_rate: d => d.performance_metrics.win_rate * 100,
      sharpe_ratio: d => d.performance_metrics.sharpe_ratio,
      profit_factor: d => d.performance_metrics.profit_factor,
    };
    const getter = metricFormatters[comparisonMetric] || metricFormatters['total_pnl'];

    regimes.forEach(regime => {
      const d = performanceData.find(p => p.regime === regime);
      if (!d) return;
      traces.push({
        x: [regime],
        y: [getter(d)],
        type: 'bar',
        name: `${regime} VIX`,
        marker: { color: regimeColors[regime] },
        hovertemplate:
          `<b>${regime} VIX</b><br>` +
          `Total P&L: $${d.performance_metrics.total_pnl.toFixed(0)}<br>` +
          `Win Rate: ${(d.performance_metrics.win_rate * 100).toFixed(1)}%<br>` +
          `Sharpe: ${d.performance_metrics.sharpe_ratio.toFixed(3)}<br>` +
          `Trades: ${d.performance_metrics.total_trades}<extra></extra>`,
      });
    });

    return traces;
  }, [performanceData, comparisonMetric]);

  // 3. Equity Curve with Regime Coloring
  const equityCurveTraces = useMemo(() => {
    if (!equityData?.equity_curve?.length) return [];
    const curve = equityData.equity_curve;
    const traces: any[] = [];

    // Main equity line
    traces.push({
      x: curve.map(p => p.date),
      y: curve.map(p => p.cumulative_pnl),
      type: 'scatter',
      mode: 'lines',
      name: 'Cumulative P&L',
      line: { color: '#8b5cf6', width: 2 },
      hovertemplate: 'Date: %{x}<br>Cumul. P&L: $%{y:.0f}<br>VIX: %{text}<extra></extra>',
      text: curve.map(p => `${p.vix_level.toFixed(1)} (${p.regime})`)
    });

    // Regime-colored markers
    const regimes: Array<'LOW' | 'MEDIUM' | 'HIGH'> = ['LOW', 'MEDIUM', 'HIGH'];
    regimes.forEach(regime => {
      const pts = curve.filter(p => p.regime === regime);
      if (!pts.length) return;
      traces.push({
        x: pts.map(p => p.date),
        y: pts.map(p => p.cumulative_pnl),
        type: 'scatter',
        mode: 'markers',
        name: `${regime} regime`,
        marker: { color: regimeColors[regime], size: 6 },
        hoverinfo: 'skip',
        showlegend: true
      });
    });

    // Drawdown area
    traces.push({
      x: curve.map(p => p.date),
      y: curve.map(p => p.drawdown),
      type: 'scatter',
      mode: 'lines',
      name: 'Drawdown',
      fill: 'tozeroy',
      fillcolor: 'rgba(239, 68, 68, 0.15)',
      line: { color: '#ef4444', width: 1 },
      yaxis: 'y2',
      hovertemplate: 'Drawdown: $%{y:.0f}<extra></extra>'
    });

    return traces;
  }, [equityData]);

  // 4. Heatmap
  const heatmapTraces = useMemo(() => {
    if (!heatmapData.length) return [];

    const hours = [...new Set(heatmapData.map(h => h.hour))].sort((a, b) => a - b);
    const regimes = ['LOW', 'MEDIUM', 'HIGH'];

    const zValues: number[][] = [];
    const textValues: string[][] = [];
    const yLabels: string[] = hours.map(h => `${h.toString().padStart(2, '0')}:00`);

    hours.forEach(hour => {
      const row: number[] = [];
      const textRow: string[] = [];
      regimes.forEach(regime => {
        const entry = heatmapData.find(h => h.hour === hour && h.regime === regime);
        row.push(entry ? entry.avg_pnl : 0);
        textRow.push(
          entry
            ? `Hour: ${hour}:00<br>Regime: ${regime}<br>Avg P&L: $${entry.avg_pnl.toFixed(0)}<br>Win Rate: ${(entry.win_rate * 100).toFixed(0)}%<br>Trades: ${entry.total_trades}<br>vs Overall: ${entry.pnl_delta_vs_overall > 0 ? '+' : ''}$${entry.pnl_delta_vs_overall.toFixed(0)}`
            : 'No trades'
        );
      });
      zValues.push(row);
      textValues.push(textRow);
    });

    return [{
      z: zValues,
      x: regimes.map(r => `${r} VIX`),
      y: yLabels,
      type: 'heatmap' as const,
      colorscale: [
        [0, '#ef4444'],     // Red for losses
        [0.5, '#fefce8'],   // Yellow for breakeven
        [1, '#10b981']      // Green for profits
      ],
      zmid: 0,
      hovertemplate: '%{text}<extra></extra>',
      text: textValues,
      colorbar: { title: 'Avg P&L ($)' }
    }] as any;
  }, [heatmapData]);

  // Distribution histogram
  const distributionHistogramData = useMemo(() => {
    if (!distributionData.length || !showDistributionHistograms) return [];
    const traces: any[] = [];
    distributionData.forEach((dist) => {
      traces.push({
        x: dist.vix_levels,
        type: 'histogram',
        name: dist.time_bin,
        opacity: 0.7,
        marker: { color: '#6366f1' },
        xbins: { start: 5, end: 50, size: 1 }
      });
    });
    // Add threshold lines
    traces.push(
      { x: [15, 15], y: [0, 100], type: 'scatter', mode: 'lines', name: 'Low/Medium Threshold', line: { color: '#f59e0b', width: 2, dash: 'dash' }, showlegend: true },
      { x: [25, 25], y: [0, 100], type: 'scatter', mode: 'lines', name: 'Medium/High Threshold', line: { color: '#ef4444', width: 2, dash: 'dash' }, showlegend: true }
    );
    return traces;
  }, [distributionData, showDistributionHistograms]);

  // Transition timeline
  const transitionTimelineData = useMemo(() => {
    if (!transitionData.length || !showTransitionTimeline) return [];
    const traces: any[] = [];
    const transitionGroups = transitionData.reduce((groups, transition) => {
      const key = `${transition.from_regime}_TO_${transition.to_regime}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(transition);
      return groups;
    }, {} as Record<string, RegimeTransition[]>);

    const colors = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#6366f1'];
    Object.entries(transitionGroups).forEach(([transitionType, transitions], index) => {
      traces.push({
        x: transitions.map(t => t.date),
        y: transitions.map(t => t.trigger_vix_level),
        type: 'scatter', mode: 'markers',
        name: transitionType.replace('_TO_', ' → '),
        marker: {
          size: 10, color: colors[index % colors.length],
          symbol: index % 2 === 0 ? 'triangle-up' : 'triangle-down',
          line: { color: 'white', width: 2 }
        },
        hovertemplate: '<b>%{fullData.name}</b><br>Date: %{x}<br>VIX: %{y:.1f}<extra></extra>'
      });
    });
    return traces;
  }, [transitionData, showTransitionTimeline]);

  // ── Helpers ──────────────────────────────────────────────────────

  const formatCurrency = (value: number): string =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);

  const formatPercentage = (value: number): string => `${(value * 100).toFixed(1)}%`;

  // ── Impact summary generation ────────────────────────────────────

  const impactSummary = useMemo(() => {
    if (!correlationData?.correlation || !performanceData.length) return null;

    const { coefficient, interpretation, p_value } = correlationData.correlation;
    const regression = correlationData.regression;
    const optimal = correlationData.optimal_vix_range;

    const lines: string[] = [];

    // Correlation summary
    lines.push(interpretation);

    // Slope insight
    if (regression) {
      const dir = regression.slope < 0 ? 'drops' : 'increases';
      lines.push(`For every 1-pt VIX rise, P&L ${dir} by ~$${Math.abs(regression.slope).toFixed(0)}`);
    }

    // Optimal range
    if (optimal) {
      lines.push(`Best VIX range: ${optimal.range[0]}–${optimal.range[1]} (avg P&L: $${optimal.avg_pnl.toFixed(0)}, ${(optimal.win_rate * 100).toFixed(0)}% WR, ${optimal.trade_count} trades)`);
    }

    // Regime comparison
    const lowRegime = performanceData.find(p => p.regime === 'LOW');
    const highRegime = performanceData.find(p => p.regime === 'HIGH');
    if (lowRegime && highRegime && highRegime.performance_metrics.total_trades > 0 && lowRegime.performance_metrics.total_trades > 0) {
      const delta = lowRegime.performance_metrics.average_pnl - highRegime.performance_metrics.average_pnl;
      if (Math.abs(delta) > 10) {
        const pctDelta = ((delta / Math.abs(highRegime.performance_metrics.average_pnl || 1)) * 100).toFixed(0);
        lines.push(`Avg P&L is $${Math.abs(delta).toFixed(0)} ${delta > 0 ? 'higher' : 'lower'} in Low VIX vs High VIX (${pctDelta}% difference)`);
      }
    }

    return {
      lines,
      severity: Math.abs(coefficient) > 0.3 ? 'high' : Math.abs(coefficient) > 0.1 ? 'medium' : 'low',
      significant: p_value < 0.05
    };
  }, [correlationData, performanceData]);

  // ── Render ───────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="vix-regime-loading">
        <div className="loading-spinner"></div>
        <p>Loading VIX regime analysis...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="vix-regime-error">
        <div className="error-message">
          <h3>Error Loading VIX Analysis</h3>
          <p>{error}</p>
          <button onClick={fetchAllData} className="retry-button">Retry</button>
        </div>
      </div>
    );
  }

  if (!isLoading && vixData.length === 0 && !error) {
    return (
      <div className="vix-regime-no-data">
        <div className="info-message">
          <h3>No VIX Data Available</h3>
          <p>We couldn't retrieve VIX data for the selected period ({startDate} to {endDate}). This may be due to market holidays or data source limits.</p>
          <button onClick={fetchAllData} className="retry-button">Try Again</button>
        </div>
      </div>
    );
  }

  return (
    <div className="vix-regime-analyzer">
      {/* Header and Controls */}
      <div className="analyzer-header">
        <div className="header-content">
          <h2>VIX Regime Analysis - {accountName}</h2>
          <div className="analyzer-controls">
            <div className="control-group">
              <label>Start Date:</label>
              <input type="date" value={localStartDate} onChange={e => setLocalStartDate(e.target.value)} />
            </div>
            <div className="control-group">
              <label>End Date:</label>
              <input type="date" value={localEndDate} onChange={e => setLocalEndDate(e.target.value)} />
            </div>
            <div className="control-group">
              <label>Regime Filter:</label>
              <select value={selectedRegime} onChange={(e) => setSelectedRegime(e.target.value as any)}>
                <option value="ALL">All Regimes</option>
                <option value="LOW">Low VIX</option>
                <option value="MEDIUM">Medium VIX</option>
                <option value="HIGH">High VIX</option>
              </select>
            </div>
            <div className="control-group">
              <label>Metric:</label>
              <select value={comparisonMetric} onChange={(e) => setComparisonMetric(e.target.value as any)}>
                <option value="total_pnl">Total P&L</option>
                <option value="win_rate">Win Rate</option>
                <option value="sharpe_ratio">Sharpe Ratio</option>
                <option value="profit_factor">Profit Factor</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Current Regime Indicator */}
      {showCurrentIndicator && currentRegime && (
        <div className="current-regime-panel">
          <div className="regime-indicator-card">
            <div className="regime-header">
              <h3>Current VIX Regime</h3>
              <div className={`regime-badge ${currentRegime.current_regime.toLowerCase()}`}
                style={{ backgroundColor: regimeColors[currentRegime.current_regime] }}>
                {currentRegime.current_regime}
              </div>
            </div>
            <div className="regime-details">
              <div className="detail-row"><span className="label">VIX Level:</span><span className="value">{currentRegime.current_vix_level.toFixed(1)}</span></div>
              <div className="detail-row"><span className="label">Days in Regime:</span><span className="value">{currentRegime.days_in_current_regime}</span></div>
              <div className="detail-row"><span className="label">Regime Percentile:</span><span className="value">{currentRegime.regime_percentile.toFixed(0)}th</span></div>
            </div>
            <div className="forecast-section">
              <h4>Regime Forecast</h4>
              <div className="forecast-probabilities">
                <div className="prob-item">
                  <span className="prob-label">Low:</span>
                  <span className="prob-value">{formatPercentage(currentRegime.regime_forecast.probability_low)}</span>
                </div>
                <div className="prob-item">
                  <span className="prob-label">Medium:</span>
                  <span className="prob-value">{formatPercentage(currentRegime.regime_forecast.probability_medium)}</span>
                </div>
                <div className="prob-item">
                  <span className="prob-label">High:</span>
                  <span className="prob-value">{formatPercentage(currentRegime.regime_forecast.probability_high)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── VIX Impact Summary Card ─────────────────────────────── */}
      {impactSummary && (
        <div className={`impact-summary-panel severity-${impactSummary.severity}`}>
          <div className="impact-header">
            <h3>📊 VIX Impact Summary</h3>
            {impactSummary.significant && <span className="significance-badge">Statistically Significant</span>}
          </div>
          <ul className="impact-lines">
            {impactSummary.lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Visualization Grid */}
      <div className="visualization-grid">

        {/* ── Equity Curve with VIX Regime Overlay ────────────────── */}
        {equityCurveData.length > 0 && (
          <div className="visualization-panel full-width">
            <div className="panel-header">
              <h3>VIX Regime P&L Analysis</h3>
              <div className="panel-stats">
                <span>Account: {accountName}</span>
                <span>Max DD: {equityData?.drawdowns_by_regime ?
                  Math.min(...Object.values(equityData.drawdowns_by_regime).map(d => d.max_drawdown)).toFixed(2) : '-'}%</span>
              </div>
            </div>
            <div className="chart-container" style={{ height: '480px' }}>
              <Plot
                data={equityCurveData}
                layout={{
                  title: 'Cumulative Equity Curve by VIX Regime',
                  xaxis: { title: 'Time (Trade Entry)', showgrid: true, gridcolor: '#f1f5f9' },
                  yaxis: { title: 'Cumulative P&L ($)', showgrid: true, gridcolor: '#f1f5f9' },
                  yaxis2: {
                    title: 'VIX Level',
                    overlaying: 'y',
                    side: 'right',
                    showgrid: false,
                    range: [0, 50]
                  },
                  height: 480,
                  margin: { t: 50, r: 80, b: 60, l: 80 },
                  showlegend: true,
                  legend: { orientation: 'h', x: 0.5, y: -0.15, xanchor: 'center' },
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  hovermode: 'x unified'
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* ── Panel 1: VIX vs P&L Scatter ────────────────────────── */}
        {scatterData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>VIX Level vs Trade P&L</h3>
              <div className="panel-stats">
                <span>r = {correlationData?.correlation?.coefficient.toFixed(3)}</span>
                <span>R² = {correlationData?.regression?.r_squared.toFixed(3)}</span>
                <span>Trades: {correlationData?.trades.length}</span>
              </div>
            </div>
            <div className="chart-container">
              <Plot
                data={scatterData}
                layout={{
                  title: 'VIX Level vs Trade P&L (Scatter + Regression)',
                  xaxis: { title: 'VIX Level' },
                  yaxis: { title: 'Trade P&L ($)' },
                  height: 420,
                  margin: { t: 50, r: 50, b: 60, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  shapes: correlationData?.optimal_vix_range ? [{
                    type: 'rect', xref: 'x', yref: 'paper',
                    x0: correlationData.optimal_vix_range.range[0],
                    x1: correlationData.optimal_vix_range.range[1],
                    y0: 0, y1: 1,
                    fillcolor: 'rgba(16, 185, 129, 0.08)',
                    layer: 'below',
                    line: { color: '#10b981', width: 1, dash: 'dot' as const }
                  }] : []
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
            {correlationData?.optimal_vix_range && (
              <div className="optimal-range-callout">
                🎯 <strong>Optimal VIX Zone:</strong> {correlationData.optimal_vix_range.range[0]}–{correlationData.optimal_vix_range.range[1]}
                | Avg P&L: {formatCurrency(correlationData.optimal_vix_range.avg_pnl)}
                | Win Rate: {(correlationData.optimal_vix_range.win_rate * 100).toFixed(0)}%
                | {correlationData.optimal_vix_range.trade_count} trades
              </div>
            )}
          </div>
        )}

        {/* ── Panel 2: P&L by Regime Bars ────────────────────────── */}
        {regimeBarData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>Performance by VIX Regime</h3>
              <div className="panel-stats">
                {performanceData.map(p => (
                  <span key={p.regime}>{p.regime}: {p.performance_metrics.total_trades} trades</span>
                ))}
              </div>
            </div>
            <div className="chart-container">
              <Plot
                data={regimeBarData}
                layout={{
                  title: `${comparisonMetric.replace('_', ' ').toUpperCase()} by VIX Regime`,
                  xaxis: { title: 'VIX Regime' },
                  yaxis: {
                    title: comparisonMetric === 'total_pnl' ? 'Total P&L ($)' :
                      comparisonMetric === 'win_rate' ? 'Win Rate (%)' :
                        comparisonMetric === 'sharpe_ratio' ? 'Sharpe Ratio' : 'Profit Factor'
                  },
                  height: 420,
                  margin: { t: 50, r: 50, b: 60, l: 80 },
                  showlegend: false,
                  barmode: 'group'
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
                onClick={(data) => {
                  if (data.points?.[0] && onRegimeClick) {
                    const regime = (data.points[0] as any).x as 'LOW' | 'MEDIUM' | 'HIGH';
                    onRegimeClick(regime);
                  }
                }}
              />
            </div>
          </div>
        )}

        {/* ── Panel 3: Equity Curve with Regime Coloring ─────────── */}
        {equityCurveTraces.length > 0 && (
          <div className="visualization-panel full-width">
            <div className="panel-header">
              <h3>Equity Curve by VIX Regime</h3>
              <div className="panel-stats">
                {equityData?.drawdowns_by_regime && Object.entries(equityData.drawdowns_by_regime).map(([regime, dd]) => (
                  <span key={regime} style={{ color: regimeColors[regime] }}>
                    {regime}: Max DD {formatCurrency(dd.max_drawdown)}
                  </span>
                ))}
              </div>
            </div>
            <div className="chart-container">
              <Plot
                data={equityCurveTraces}
                layout={{
                  title: 'Cumulative P&L with VIX Regime Overlay',
                  xaxis: { title: 'Date', type: 'date' },
                  yaxis: { title: 'Cumulative P&L ($)', side: 'left' },
                  yaxis2: {
                    title: 'Drawdown ($)', side: 'right', overlaying: 'y',
                    showgrid: false, zeroline: false
                  },
                  height: 500,
                  margin: { t: 50, r: 80, b: 60, l: 80 },
                  showlegend: true,
                  legend: { x: 0.02, y: 0.98 },
                  hovermode: 'x unified'
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* ── Panel 4: Time-Bin × Regime Heatmap ─────────────────── */}
        {heatmapTraces.length > 0 && (
          <div className="visualization-panel full-width">
            <div className="panel-header">
              <h3>Trading Hour × VIX Regime Heatmap</h3>
              <div className="panel-stats">
                <span>Hours active: {[...new Set(heatmapData.map(h => h.hour))].length}</span>
                <span>Green = Profitable, Red = Unprofitable</span>
              </div>
            </div>
            <div className="chart-container">
              <Plot
                data={heatmapTraces}
                layout={{
                  title: 'Average P&L by Trading Hour and VIX Regime',
                  xaxis: { title: 'VIX Regime' },
                  yaxis: { title: 'Trading Hour', autorange: 'reversed' as const },
                  height: Math.max(350, [...new Set(heatmapData.map(h => h.hour))].length * 40 + 100),
                  margin: { t: 50, r: 120, b: 60, l: 80 },
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* ── Existing: VIX Distribution ──────────────────────────── */}
        {showDistributionHistograms && distributionHistogramData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>VIX Level Distribution</h3>
              <div className="panel-stats">
                <span>Avg VIX: {distributionData.length ? distributionData[0].vix_statistics.mean.toFixed(1) : '—'}</span>
              </div>
            </div>
            <div className="chart-container">
              <Plot
                data={distributionHistogramData}
                layout={{
                  title: 'VIX Level Distribution',
                  xaxis: { title: 'VIX Level', range: [5, 50] },
                  yaxis: { title: 'Frequency' },
                  height: 400, margin: { t: 50, r: 50, b: 60, l: 80 },
                  showlegend: true, barmode: 'overlay'
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

        {/* ── Existing: Transition Timeline ───────────────────────── */}
        {showTransitionTimeline && transitionTimelineData.length > 0 && (
          <div className="visualization-panel">
            <div className="panel-header">
              <h3>Regime Transitions</h3>
              <div className="panel-stats">
                <span>Transitions: {transitionData.length}</span>
              </div>
            </div>
            <div className="chart-container">
              <Plot
                data={transitionTimelineData}
                layout={{
                  title: 'VIX Regime Transitions',
                  xaxis: { title: 'Date', type: 'date' },
                  yaxis: { title: 'VIX Level', range: [5, 50] },
                  height: 400, margin: { t: 50, r: 50, b: 60, l: 80 },
                  showlegend: true, hovermode: 'closest',
                  shapes: [
                    { type: 'rect', xref: 'paper', yref: 'y', x0: 0, y0: 0, x1: 1, y1: 15, fillcolor: 'rgba(16, 185, 129, 0.1)', layer: 'below', line: { width: 0 } },
                    { type: 'rect', xref: 'paper', yref: 'y', x0: 0, y0: 15, x1: 1, y1: 25, fillcolor: 'rgba(245, 158, 11, 0.1)', layer: 'below', line: { width: 0 } },
                    { type: 'rect', xref: 'paper', yref: 'y', x0: 0, y0: 25, x1: 1, y1: 50, fillcolor: 'rgba(239, 68, 68, 0.1)', layer: 'below', line: { width: 0 } },
                  ]
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          </div>
        )}

      </div>

      {/* Summary Statistics */}
      {distributionData.length > 0 && (
        <div className="summary-panel">
          <div className="panel-header">
            <h3>Regime Summary Statistics</h3>
          </div>
          <div className="summary-grid">
            {distributionData.map((dist, index) => (
              <div key={index} className="summary-card">
                <div className="summary-header"><h4>{dist.time_bin}</h4></div>
                <div className="regime-breakdown">
                  {(['LOW', 'MEDIUM', 'HIGH'] as const).map(regime => (
                    <div key={regime} className={`regime-stat ${regime.toLowerCase()}`}>
                      <div className="regime-info">
                        <span className="regime-name">{regime === 'LOW' ? 'Low' : regime === 'MEDIUM' ? 'Medium' : 'High'} VIX</span>
                        <span className="regime-percentage">{dist.regime_percentages[regime].toFixed(1)}%</span>
                      </div>
                      <div className="regime-details">
                        <span>Avg: {dist.average_vix_by_regime[regime].toFixed(1)}</span>
                        <span>Count: {dist.regime_counts[regime]}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="vix-statistics">
                  <div className="stat-item"><span className="stat-label">Range:</span><span className="stat-value">{dist.vix_statistics.min.toFixed(1)} - {dist.vix_statistics.max.toFixed(1)}</span></div>
                  <div className="stat-item"><span className="stat-label">Mean:</span><span className="stat-value">{dist.vix_statistics.mean.toFixed(1)}</span></div>
                  <div className="stat-item"><span className="stat-label">Volatility:</span><span className="stat-value">{dist.vix_statistics.std.toFixed(1)}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default VIXRegimeAnalyzer;