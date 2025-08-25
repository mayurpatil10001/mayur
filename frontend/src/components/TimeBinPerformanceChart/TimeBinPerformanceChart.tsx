import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Plot from 'react-plotly.js';
import './TimeBinPerformanceChart.css';

// Market Data Interfaces
interface MarketData {
  date: string;
  close: number;
  open: number;
  high: number;
  low: number;
  volume?: number;
}

interface VIXData {
  date: string;
  vix_level: number;
  regime: 'LOW' | 'MEDIUM' | 'HIGH';
}

interface TradePoint {
  date: string;
  entry_time: string;
  profit_loss: number;
  cumulative_pnl: number;
  quantity: number;
  side: 'LONG' | 'SHORT';
  market_spy_price?: number;
  market_qqq_price?: number;
  vix_level?: number;
  vix_regime?: 'LOW' | 'MEDIUM' | 'HIGH';
}

interface TimeBinData {
  account: string;
  hour: number;
  minute_bin: number;
  trades: TradePoint[];
  performance_metrics: {
    total_pnl: number;
    win_rate: number;
    sharpe_ratio?: number;
    max_drawdown: number;
    profit_factor: number;
    total_trades: number;
  };
}

interface MarketCorrelationData {
  spy_correlation: number;
  qqq_correlation: number;
  beta_spy: number;
  beta_qqq: number;
  alpha_spy?: number;
  alpha_qqq?: number;
  correlation_stability: number;
}

// Component Props
interface TimeBinPerformanceChartProps {
  accountName: string;
  hour: number;
  minuteBin: number;
  startDate?: string;
  endDate?: string;
  showMarketOverlay?: boolean;
  showVIXContext?: boolean;
  showTradePoints?: boolean;
  comparisonMode?: boolean;
  comparisonData?: TimeBinData[];
  height?: number;
  onTradePointClick?: (trade: TradePoint) => void;
}

const TimeBinPerformanceChart: React.FC<TimeBinPerformanceChartProps> = ({
  accountName,
  hour,
  minuteBin,
  startDate,
  endDate,
  showMarketOverlay = true,
  showVIXContext = true,
  showTradePoints = true,
  comparisonMode = false,
  comparisonData = [],
  height = 600,
  onTradePointClick
}) => {
  // State management
  const [timeBinData, setTimeBinData] = useState<TimeBinData | null>(null);
  const [marketData, setMarketData] = useState<{ spy: MarketData[]; qqq: MarketData[] }>({ spy: [], qqq: [] });
  const [vixData, setVixData] = useState<VIXData[]>([]);
  const [correlationData, setCorrelationData] = useState<MarketCorrelationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMarketIndex, setSelectedMarketIndex] = useState<'SPY' | 'QQQ'>('SPY');
  const [showMarketOverlayState, setShowMarketOverlay] = useState(showMarketOverlay);
  const [showVIXContextState, setShowVIXContext] = useState(showVIXContext);
  const [showTradePointsState, setShowTradePoints] = useState(showTradePoints);

  // Data fetching
  const fetchTimeBinData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/time-bins/${accountName}/${hour}/${minuteBin}/analysis?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (!response.ok) throw new Error('Failed to fetch time-bin data');
      
      const data = await response.json();
      setTimeBinData(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  }, [accountName, hour, minuteBin, startDate, endDate]);

  const fetchMarketData = useCallback(async () => {
    if (!showMarketOverlayState) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      // Fetch SPY and QQQ data
      const [spyResponse, qqqResponse] = await Promise.all([
        fetch(`/api/market-data/spy?${params}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
        }),
        fetch(`/api/market-data/qqq?${params}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
        })
      ]);
      
      if (spyResponse.ok && qqqResponse.ok) {
        const [spyData, qqqData] = await Promise.all([
          spyResponse.json(),
          qqqResponse.json()
        ]);
        
        setMarketData({ spy: spyData, qqq: qqqData });
      }
      
    } catch (err) {
      console.warn('Failed to fetch market data:', err);
    }
  }, [showMarketOverlayState, startDate, endDate]);

  const fetchVIXData = useCallback(async () => {
    if (!showVIXContextState) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(`/api/vix-data?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setVixData(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch VIX data:', err);
    }
  }, [showVIXContextState, startDate, endDate]);

  const fetchCorrelationData = useCallback(async () => {
    if (!showMarketOverlayState) return;
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      
      const response = await fetch(
        `/api/time-bins/${accountName}/${hour}/${minuteBin}/market-correlation?${params}`,
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }}
      );
      
      if (response.ok) {
        const data = await response.json();
        setCorrelationData(data);
      }
      
    } catch (err) {
      console.warn('Failed to fetch correlation data:', err);
    }
  }, [accountName, hour, minuteBin, showMarketOverlay, startDate, endDate]);

  // Sync internal state with props
  useEffect(() => {
    setShowMarketOverlay(showMarketOverlay);
  }, [showMarketOverlay]);

  useEffect(() => {
    setShowVIXContext(showVIXContext);
  }, [showVIXContext]);

  useEffect(() => {
    setShowTradePoints(showTradePoints);
  }, [showTradePoints]);

  // Load data on mount and prop changes
  useEffect(() => {
    fetchTimeBinData();
  }, [fetchTimeBinData]);

  useEffect(() => {
    fetchMarketData();
  }, [fetchMarketData]);

  useEffect(() => {
    fetchVIXData();
  }, [fetchVIXData]);

  useEffect(() => {
    fetchCorrelationData();
  }, [fetchCorrelationData]);

  // Chart data preparation
  const chartData = useMemo(() => {
    const traces: any[] = [];
    
    if (!timeBinData?.trades?.length) return traces;
    
    const trades = timeBinData.trades;
    const dates = trades.map(t => t.date);
    const cumulativePnL = trades.map(t => t.cumulative_pnl);
    const selectedMarketData = selectedMarketIndex === 'SPY' ? marketData.spy : marketData.qqq;
    
    // Main P&L trace
    traces.push({
      x: dates,
      y: cumulativePnL,
      type: 'scatter',
      mode: 'lines',
      name: `${accountName} ${hour}:${minuteBin.toString().padStart(2, '0')} P&L`,
      line: {
        color: cumulativePnL[cumulativePnL.length - 1] >= 0 ? '#10b981' : '#ef4444',
        width: 3
      },
      hovertemplate: '<b>%{fullData.name}</b><br>' +
                    'Date: %{x}<br>' +
                    'P&L: $%{y:,.2f}<br>' +
                    '<extra></extra>'
    });
    
    // Market overlay
    if (showMarketOverlayState && selectedMarketData?.length) {
      const alignedMarketData = selectedMarketData.filter(m => 
        dates.some(d => d === m.date)
      );
      
      if (alignedMarketData.length) {
        // Normalize market data to fit on same scale
        const marketPrices = alignedMarketData.map(m => m.close);
        const marketMin = Math.min(...marketPrices);
        const marketMax = Math.max(...marketPrices);
        const pnlMin = Math.min(...cumulativePnL);
        const pnlMax = Math.max(...cumulativePnL);
        
        const normalizedMarketData = marketPrices.map(price => 
          pnlMin + (price - marketMin) / (marketMax - marketMin) * (pnlMax - pnlMin)
        );
        
        traces.push({
          x: alignedMarketData.map(m => m.date),
          y: normalizedMarketData,
          type: 'scatter',
          mode: 'lines',
          name: `${selectedMarketIndex} (Normalized)`,
          line: {
            color: '#6366f1',
            width: 2,
            dash: 'dash'
          },
          yaxis: 'y2',
          hovertemplate: '<b>%{fullData.name}</b><br>' +
                        'Date: %{x}<br>' +
                        'Price: $%{text}<br>' +
                        '<extra></extra>',
          text: marketPrices.map(p => p.toFixed(2))
        });
      }
    }
    
    // Trade points
    if (showTradePointsState) {
      const winningTrades = trades.filter(t => t.profit_loss > 0);
      const losingTrades = trades.filter(t => t.profit_loss <= 0);
      
      if (winningTrades.length) {
        traces.push({
          x: winningTrades.map(t => t.date),
          y: winningTrades.map(t => t.cumulative_pnl),
          type: 'scatter',
          mode: 'markers',
          name: 'Winning Trades',
          marker: {
            color: '#10b981',
            size: winningTrades.map(t => Math.min(15, Math.max(5, Math.abs(t.profit_loss) / 100))),
            symbol: 'triangle-up',
            line: { color: 'white', width: 1 }
          },
          hovertemplate: '<b>Winning Trade</b><br>' +
                        'Date: %{x}<br>' +
                        'P&L: $%{text}<br>' +
                        'Cumulative: $%{y:,.2f}<br>' +
                        '<extra></extra>',
          text: winningTrades.map(t => t.profit_loss.toFixed(2))
        });
      }
      
      if (losingTrades.length) {
        traces.push({
          x: losingTrades.map(t => t.date),
          y: losingTrades.map(t => t.cumulative_pnl),
          type: 'scatter',
          mode: 'markers',
          name: 'Losing Trades',
          marker: {
            color: '#ef4444',
            size: losingTrades.map(t => Math.min(15, Math.max(5, Math.abs(t.profit_loss) / 100))),
            symbol: 'triangle-down',
            line: { color: 'white', width: 1 }
          },
          hovertemplate: '<b>Losing Trade</b><br>' +
                        'Date: %{x}<br>' +
                        'P&L: $%{text}<br>' +
                        'Cumulative: $%{y:,.2f}<br>' +
                        '<extra></extra>',
          text: losingTrades.map(t => t.profit_loss.toFixed(2))
        });
      }
    }
    
    // Comparison mode traces
    if (comparisonMode && comparisonData.length) {
      const colors = ['#f59e0b', '#8b5cf6', '#ef4444', '#10b981', '#06b6d4'];
      
      comparisonData.forEach((comparison, index) => {
        if (comparison.trades?.length) {
          traces.push({
            x: comparison.trades.map(t => t.date),
            y: comparison.trades.map(t => t.cumulative_pnl),
            type: 'scatter',
            mode: 'lines',
            name: `${comparison.account} ${comparison.hour}:${comparison.minute_bin.toString().padStart(2, '0')}`,
            line: {
              color: colors[index % colors.length],
              width: 2,
              dash: 'dot'
            },
            hovertemplate: '<b>%{fullData.name}</b><br>' +
                          'Date: %{x}<br>' +
                          'P&L: $%{y:,.2f}<br>' +
                          '<extra></extra>'
          });
        }
      });
    }
    
    return traces;
  }, [timeBinData, marketData, selectedMarketIndex, showMarketOverlayState, showTradePointsState, comparisonMode, comparisonData, accountName, hour, minuteBin]);

  // VIX background shapes
  const backgroundShapes = useMemo(() => {
    if (!showVIXContextState || !vixData.length || !timeBinData?.trades?.length) return [];
    
    const shapes: any[] = [];
    const minDate = timeBinData.trades[0]?.date;
    const maxDate = timeBinData.trades[timeBinData.trades.length - 1]?.date;
    
    if (!minDate || !maxDate) return shapes;
    
    // Group consecutive VIX regimes
    let currentRegime = vixData[0]?.regime;
    let regimeStart = minDate;
    
    vixData.forEach((vix, index) => {
      if (vix.regime !== currentRegime || index === vixData.length - 1) {
        if (currentRegime) {
          const regimeEnd = index === vixData.length - 1 ? maxDate : vix.date;
          
          let color;
          switch (currentRegime) {
            case 'LOW': color = 'rgba(16, 185, 129, 0.1)'; break;   // Green
            case 'MEDIUM': color = 'rgba(245, 158, 11, 0.1)'; break; // Yellow
            case 'HIGH': color = 'rgba(239, 68, 68, 0.1)'; break;   // Red
            default: color = 'rgba(156, 163, 175, 0.1)'; break;
          }
          
          shapes.push({
            type: 'rect',
            x0: regimeStart,
            x1: regimeEnd,
            y0: 0,
            y1: 1,
            yref: 'paper',
            fillcolor: color,
            line: { width: 0 },
            layer: 'below'
          });
        }
        
        currentRegime = vix.regime;
        regimeStart = vix.date;
      }
    });
    
    return shapes;
  }, [showVIXContextState, vixData, timeBinData]);

  // Chart layout
  const layout = useMemo(() => ({
    title: {
      text: comparisonMode 
        ? `Time-Bin Performance Comparison`
        : `${accountName} - ${hour}:${minuteBin.toString().padStart(2, '0')} Time-Bin Performance`,
      font: { size: 16, color: '#1f2937' }
    },
    xaxis: {
      title: 'Date',
      type: 'date' as const,
      showgrid: true,
      gridcolor: '#f3f4f6'
    },
    yaxis: {
      title: 'Cumulative P&L ($)',
      showgrid: true,
      gridcolor: '#f3f4f6',
      tickformat: '$,.0f'
    },
    yaxis2: showMarketOverlayState ? {
      title: `${selectedMarketIndex} Price ($)`,
      overlaying: 'y' as const,
      side: 'right' as const,
      showgrid: false,
      tickformat: '$,.2f'
    } : undefined,
    height: height,
    margin: { t: 60, r: showMarketOverlayState ? 80 : 50, b: 80, l: 80 },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, system-ui, sans-serif', size: 12, color: '#374151' },
    showlegend: true,
    legend: {
      x: 0.02,
      y: 0.98,
      bgcolor: 'rgba(255,255,255,0.9)',
      bordercolor: '#e5e7eb',
      borderwidth: 1
    },
    hovermode: 'x unified',
    shapes: backgroundShapes
  }), [accountName, hour, minuteBin, comparisonMode, height, showMarketOverlay, selectedMarketIndex, backgroundShapes]);

  // Chart configuration
  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'] as any,
    responsive: true
  };

  // Format currency helper
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  if (error) {
    return (
      <div className="time-bin-chart-error">
        <div className="error-message">
          <h3>Error Loading Chart</h3>
          <p>{error}</p>
          <button onClick={fetchTimeBinData} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="time-bin-chart-loading">
        <div className="loading-spinner"></div>
        <p>Loading time-bin performance data...</p>
      </div>
    );
  }

  return (
    <div className="time-bin-performance-chart">
      {/* Chart Controls */}
      <div className="chart-controls">
        <div className="control-group">
          <label>Market Index:</label>
          <select 
            value={selectedMarketIndex} 
            onChange={(e) => setSelectedMarketIndex(e.target.value as 'SPY' | 'QQQ')}
            disabled={!showMarketOverlayState}
          >
            <option value="SPY">SPY</option>
            <option value="QQQ">QQQ</option>
          </select>
        </div>
        
        <div className="toggle-group">
          <label className="toggle">
            <input 
              type="checkbox" 
              checked={showMarketOverlayState} 
              onChange={(e) => setShowMarketOverlay(e.target.checked)}
            />
            <span>Market Overlay</span>
          </label>
          
          <label className="toggle">
            <input 
              type="checkbox" 
              checked={showVIXContextState} 
              onChange={(e) => setShowVIXContext(e.target.checked)}
            />
            <span>VIX Context</span>
          </label>
          
          <label className="toggle">
            <input 
              type="checkbox" 
              checked={showTradePointsState} 
              onChange={(e) => setShowTradePoints(e.target.checked)}
            />
            <span>Trade Points</span>
          </label>
        </div>
      </div>

      {/* Performance Summary */}
      {timeBinData?.performance_metrics && (
        <div className="performance-summary">
          <div className="metric-card">
            <span className="metric-label">Total P&L</span>
            <span className={`metric-value ${timeBinData.performance_metrics.total_pnl >= 0 ? 'positive' : 'negative'}`}>
              {formatCurrency(timeBinData.performance_metrics.total_pnl)}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Win Rate</span>
            <span className="metric-value">{(timeBinData.performance_metrics.win_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Total Trades</span>
            <span className="metric-value">{timeBinData.performance_metrics.total_trades}</span>
          </div>
          {correlationData && (
            <div className="metric-card">
              <span className="metric-label">{selectedMarketIndex} Beta</span>
              <span className="metric-value">
                {selectedMarketIndex === 'SPY' ? correlationData.beta_spy.toFixed(2) : correlationData.beta_qqq.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* VIX Legend */}
      {showVIXContextState && (
        <div className="vix-legend">
          <span className="legend-title">VIX Volatility Regimes:</span>
          <div className="regime-indicator low">Low (&lt;15)</div>
          <div className="regime-indicator medium">Medium (15-25)</div>
          <div className="regime-indicator high">High (&gt;25)</div>
        </div>
      )}

      {/* Main Chart */}
      <div className="chart-container">
        <Plot
          data={chartData}
          layout={layout as any}
          config={config}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
          onHover={(data) => {
            // Handle trade point hover for additional details
            if (data.points?.[0] && onTradePointClick) {
              // Add custom hover behavior if needed
            }
          }}
          onClick={(data) => {
            // Handle trade point clicks
            if (data.points?.[0] && onTradePointClick && timeBinData?.trades) {
              const pointIndex = data.points[0].pointIndex;
              const trade = timeBinData.trades[pointIndex];
              if (trade) {
                onTradePointClick(trade);
              }
            }
          }}
        />
      </div>
    </div>
  );
};

export default TimeBinPerformanceChart;