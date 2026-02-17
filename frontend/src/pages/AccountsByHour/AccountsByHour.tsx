import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchAccounts } from '../../store/slices/accountsSlice';
import InteractiveChart from '../../components/InteractiveChart/InteractiveChart';
import './AccountsByHour.css';

interface HourlyBreakdown {
  time_slot: string;
  net_pnl: number;
  total_trades: number;
  avg_trade: number;
  win_percentage: number;
  avg_winner: number;
  avg_loser: number;
  largest_winner: number;
  largest_loser: number;
  drawdown: number;
  runup: number;
  equity_peak: number;
}

interface Trade {
  trade_id: string;
  time_slot: string;
  entry_time: string;
  exit_time: string;
  profit_loss: number;
  side: string;
  quantity: number;
}

const AccountsByHour: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { accounts, isLoading: accountsLoading } = useSelector((state: RootState) => state.accounts);

  const [selectedAccount, setSelectedAccount] = useState<string>(localStorage.getItem('abh_selectedAccount') || '');
  const [selectedSymbol, setSelectedSymbol] = useState<string>(localStorage.getItem('abh_selectedSymbol') || '');
  const [timeHorizon, setTimeHorizon] = useState<string>(localStorage.getItem('abh_timeHorizon') || 'all');
  const [timezoneOffset, setTimezoneOffset] = useState<number>(parseInt(localStorage.getItem('abh_timezoneOffset') || '-5'));
  const [timeBasis, setTimeBasis] = useState<string>(localStorage.getItem('abh_timeBasis') || 'entry');
  const [hourlyData, setHourlyData] = useState<HourlyBreakdown[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timeHorizonOptions = [
    { label: '7 Days', value: '7' },
    { label: '30 Days', value: '30' },
    { label: '90 Days', value: '90' },
    { label: '180 Days', value: '180' },
    { label: '1 Year', value: '365' },
    { label: 'All Time', value: 'all' }
  ];

  const handleAccountDropdownClick = () => {
    if (accounts.length === 0 && !accountsLoading) {
      dispatch(fetchAccounts());
    }
  };

  const uniqueSymbols = Array.from(new Set(accounts.map(acc => acc.symbol))).sort();
  const availableAccounts = accounts
    .filter(acc => acc.symbol === selectedSymbol)
    .map(acc => acc.name);

  const fetchData = async () => {
    if (!selectedAccount || !selectedSymbol) return;

    setIsLoading(true);
    setError(null);

    try {
      const daysBack = timeHorizon === 'all' ? '' : `&days_back=${timeHorizon}`;
      const hourlyResponse = await fetch(
        `http://localhost:8000/api/v1/accounts/${selectedAccount}/hourly-breakdown?symbol=${selectedSymbol}&timezone_offset=${timezoneOffset}&time_basis=${timeBasis}${daysBack}`
      );

      if (!hourlyResponse.ok) throw new Error('Failed to fetch hourly breakdown');
      const hourlyJson = await hourlyResponse.json();
      setHourlyData(hourlyJson.data || []);

      // Fetch trades for chart/list - using large size to ensure we get all trades for the analyzed slots
      let tradesUrl = `http://localhost:8000/api/v1/trades/?account_name=${selectedAccount}&symbol=${selectedSymbol}&size=50000`;

      // If a time horizon is selected, we should also filter the trades by date
      if (timeHorizon !== 'all') {
        const horizonDays = parseInt(timeHorizon);
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - horizonDays);
        tradesUrl += `&start_date=${startDate.toISOString()}`;
      }

      const tradesResponse = await fetch(tradesUrl);
      if (!tradesResponse.ok) throw new Error('Failed to fetch trades');
      const tradesJson = await tradesResponse.json();
      setTrades(tradesJson.data.items || []);

    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (accounts.length === 0) {
      dispatch(fetchAccounts());
    }
  }, [dispatch, accounts.length]);

  useEffect(() => {
    if (accounts.length > 0 && !selectedSymbol) {
      const defaultSym = accounts.find(a => a.symbol === 'CL') ? 'CL' : accounts[0].symbol;
      setSelectedSymbol(defaultSym);
    }
  }, [accounts, selectedSymbol]);

  useEffect(() => {
    if (selectedAccount && selectedSymbol) {
      fetchData();
    }
  }, [selectedAccount, selectedSymbol, timeHorizon, timezoneOffset, timeBasis]);

  useEffect(() => {
    if (selectedSymbol && availableAccounts.length > 0) {
      if (!availableAccounts.includes(selectedAccount)) {
        setSelectedAccount(availableAccounts[0]);
      }
    }
  }, [selectedSymbol, availableAccounts]);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const getChartData = () => {
    if (trades.length === 0) return [];

    const sortedTrades = [...trades].sort((a, b) =>
      new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime()
    );

    let filteredTrades = sortedTrades;
    if (showMultiAnalysis && selectedSlots.length > 0) {
      filteredTrades = sortedTrades.filter(t => selectedSlots.includes(t.time_slot));
    }

    if (filteredTrades.length === 0) return [];

    let cumulativePnl = 0;
    return filteredTrades.map(t => {
      cumulativePnl += t.profit_loss;
      return {
        date: t.entry_time,
        daily_pnl: t.profit_loss,
        cumulative_pnl: cumulativePnl,
        entry_time: t.entry_time
      };
    });
  };

  const [selectedSlots, setSelectedSlots] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('abh_selectedSlots');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  });
  const [showMultiAnalysis, setShowMultiAnalysis] = useState(localStorage.getItem('abh_showMultiAnalysis') === 'true');

  // Persistence effects
  useEffect(() => {
    localStorage.setItem('abh_selectedAccount', selectedAccount);
  }, [selectedAccount]);

  useEffect(() => {
    localStorage.setItem('abh_selectedSymbol', selectedSymbol);
  }, [selectedSymbol]);

  useEffect(() => {
    localStorage.setItem('abh_timeHorizon', timeHorizon);
  }, [timeHorizon]);

  useEffect(() => {
    localStorage.setItem('abh_timezoneOffset', timezoneOffset.toString());
  }, [timezoneOffset]);

  useEffect(() => {
    localStorage.setItem('abh_timeBasis', timeBasis);
  }, [timeBasis]);

  useEffect(() => {
    localStorage.setItem('abh_selectedSlots', JSON.stringify(selectedSlots));
  }, [selectedSlots]);

  useEffect(() => {
    localStorage.setItem('abh_showMultiAnalysis', showMultiAnalysis.toString());
  }, [showMultiAnalysis]);

  // Initial data fetch if state was restored
  useEffect(() => {
    if (accounts.length === 0 && !accountsLoading) {
      dispatch(fetchAccounts());
    }
  }, [dispatch, accountsLoading, accounts.length]);

  useEffect(() => {
    if (selectedAccount && selectedSymbol) {
      fetchData();
    }
  }, [selectedAccount, selectedSymbol, timeHorizon]);

  const toggleSlotSelection = (slot: string) => {
    setSelectedSlots(prev =>
      prev.includes(slot) ? prev.filter(s => s !== slot) : [...prev, slot]
    );
  };

  const toggleAllSlots = () => {
    if (selectedSlots.length === hourlyData.length) {
      setSelectedSlots([]);
    } else {
      setSelectedSlots(hourlyData.map(d => d.time_slot));
    }
  };

  const getSelectedAnalysis = () => {
    const selectedData = hourlyData.filter(d => selectedSlots.includes(d.time_slot));
    if (selectedData.length === 0) return null;

    const totalPnL = selectedData.reduce((sum, d) => sum + d.net_pnl, 0);
    const totalTrades = selectedData.reduce((sum, d) => sum + d.total_trades, 0);
    const avgWinRate = selectedData.reduce((sum, d) => sum + (d.win_percentage * d.total_trades), 0) / totalTrades;

    return {
      totalPnL,
      totalTrades,
      avgWinRate: avgWinRate.toFixed(1)
    };
  };

  const calculateBacktestingStats = () => {
    const chartData = getChartData();
    if (chartData.length === 0) return null;

    const trades = chartData.map(d => d.daily_pnl);
    const winners = trades.filter(t => t > 0);
    const losers = trades.filter(t => t < 0);

    const grossProfit = winners.reduce((sum, t) => sum + t, 0);
    const grossLoss = Math.abs(losers.reduce((sum, t) => sum + t, 0));
    const profitFactor = grossLoss === 0 ? grossProfit : grossProfit / grossLoss;

    const netPnl = trades.reduce((sum, t) => sum + t, 0);
    const totalTrades = trades.length;
    const winRate = (winners.length / totalTrades) * 100;

    // Max Drawdown calculation
    let peak = -Infinity;
    let maxDD = 0;
    let currentPnl = 0;
    trades.forEach(t => {
      currentPnl += t;
      if (currentPnl > peak) peak = currentPnl;
      const dd = peak - currentPnl;
      if (dd > maxDD) maxDD = dd;
    });

    // Simple Sharpe Ratio (trade-based)
    const avgReturn = netPnl / totalTrades;
    const stdDev = Math.sqrt(trades.reduce((sum, t) => sum + Math.pow(t - avgReturn, 2), 0) / totalTrades);
    const sharpe = stdDev === 0 ? 0 : (avgReturn / stdDev) * Math.sqrt(252); // Annualized approximation assuming trades~days

    return {
      profitFactor: profitFactor.toFixed(2),
      winRate: winRate.toFixed(1),
      maxDrawdown: maxDD,
      sharpeRatio: sharpe.toFixed(2),
      avgTrade: (netPnl / totalTrades),
      totalTrades,
      expectancy: (avgReturn).toFixed(2)
    };
  };

  return (
    <div className="accounts-by-hour">
      <h1>Accounts by Hour</h1>

      <div className="selection-header">
        <div className="selection-group">
          <span className="selector-label">1. Select Symbol:</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div className="pill-selector">
              {uniqueSymbols.filter(s => !s.startsWith('Z')).map(s => (
                <button
                  key={s}
                  className={`filter-btn ${selectedSymbol === s ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedSymbol(s);
                    setSelectedSlots([]);
                  }}
                >
                  {s === 'FD' ? 'FDAX' : s}
                </button>
              ))}
            </div>
            {uniqueSymbols.filter(s => s.startsWith('Z')).length > 0 && (
              <div className="pill-selector">
                {uniqueSymbols.filter(s => s.startsWith('Z')).map(s => (
                  <button
                    key={s}
                    className={`filter-btn ${selectedSymbol === s ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedSymbol(s);
                      setSelectedSlots([]);
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="selection-group">
          <span className="selector-label">2. Select Account:</span>
          <select
            value={selectedAccount}
            onChange={(e) => {
              setSelectedAccount(e.target.value);
              setSelectedSlots([]);
            }}
            disabled={!selectedSymbol}
            className="account-select-pill"
          >
            <option value="">Select Account...</option>
            {availableAccounts.map(acc => <option key={acc} value={acc}>{acc}</option>)}
          </select>
        </div>

        <div className="selection-group">
          <span className="selector-label">Time Horizon:</span>
          <div className="pill-selector">
            {timeHorizonOptions.map(opt => (
              <button
                key={opt.value}
                className={`filter-btn ${timeHorizon === opt.value ? 'active' : ''}`}
                style={{ padding: '6px 10px' }}
                onClick={() => setTimeHorizon(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="selection-group">
          <span className="selector-label">TZ Offset (Local):</span>
          <select
            value={timezoneOffset}
            onChange={(e) => setTimezoneOffset(parseInt(e.target.value))}
            className="account-select-pill"
            style={{ minWidth: '80px' }}
          >
            {Array.from({ length: 25 }, (_, i) => i - 12).map(off => (
              <option key={off} value={off}>
                {off >= 0 ? `+${off}` : off}h
              </option>
            ))}
          </select>
        </div>

        <div className="selection-group">
          <span className="selector-label">Basis:</span>
          <div className="pill-selector">
            <button
              className={`filter-btn ${timeBasis === 'entry' ? 'active' : ''}`}
              style={{ padding: '6px 10px' }}
              onClick={() => setTimeBasis('entry')}
            >
              Entry
            </button>
            <button
              className={`filter-btn ${timeBasis === 'exit' ? 'active' : ''}`}
              style={{ padding: '6px 10px' }}
              onClick={() => setTimeBasis('exit')}
            >
              Exit
            </button>
          </div>
        </div>

        <div className="selection-group" style={{ marginLeft: 'auto' }}>
          <button
            className={`filter-btn ${selectedSlots.length > 0 ? 'active' : ''}`}
            disabled={selectedSlots.length === 0}
            onClick={() => setShowMultiAnalysis(!showMultiAnalysis)}
            style={{
              backgroundColor: selectedSlots.length > 0 ? '#3498db' : '#ccc',
              color: 'white',
              cursor: selectedSlots.length > 0 ? 'pointer' : 'not-allowed',
              opacity: selectedSlots.length > 0 ? 1 : 0.6
            }}
          >
            {showMultiAnalysis ? 'Hide Analysis' : `Analyze Selected (${selectedSlots.length})`}
          </button>
        </div>
      </div>

      {showMultiAnalysis && selectedSlots.length > 0 && (
        <div className="multi-analysis-panel" style={{
          backgroundColor: '#e8f4fd',
          padding: '20px',
          borderRadius: '8px',
          marginBottom: '20px',
          border: '2px solid #3498db'
        }}>
          <h3>📊 Combined Analysis for Selected Slots</h3>
          <div className="stats-grid" style={{ display: 'flex', gap: '30px', marginTop: '15px' }}>
            <div>
              <div style={{ color: '#666', fontSize: '12px' }}>COMBINED P&L</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: (getSelectedAnalysis()?.totalPnL || 0) >= 0 ? 'green' : 'red' }}>
                {formatCurrency(getSelectedAnalysis()?.totalPnL || 0)}
              </div>
            </div>
            <div>
              <div style={{ color: '#666', fontSize: '12px' }}>TOTAL TRADES</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{getSelectedAnalysis()?.totalTrades}</div>
            </div>
            <div>
              <div style={{ color: '#666', fontSize: '12px' }}>AVG WIN RATE</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{getSelectedAnalysis()?.avgWinRate}%</div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <button
                className="filter-btn"
                onClick={() => setSelectedSlots([])}
                style={{ backgroundColor: '#e74c3c', color: 'white' }}
              >
                Clear Selection
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading && <div className="loading" style={{
        position: 'fixed',
        top: '20px',
        right: '20px',
        backgroundColor: '#3498db',
        color: 'white',
        padding: '10px 20px',
        borderRadius: '20px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
        zIndex: 1000
      }}>Updating data...</div>}
      {error && <div className="error-message">{error}</div>}

      {selectedAccount && selectedSymbol && (
        <div className="analysis-content" style={{ opacity: isLoading ? 0.6 : 1, transition: 'opacity 0.2s' }}>
          <div className="stats-grid">
            <table className="hourly-table">
              <thead>
                <tr>
                  <th style={{ width: '40px' }}>
                    <input
                      type="checkbox"
                      checked={selectedSlots.length === hourlyData.length && hourlyData.length > 0}
                      onChange={toggleAllSlots}
                    />
                  </th>
                  <th>Time</th>
                  <th>Net P&L</th>
                  <th>Trades</th>
                  <th>Avg Trade</th>
                  <th>Win %</th>
                  <th>Avg Win</th>
                  <th>Avg Loss</th>
                </tr>
              </thead>
              <tbody>
                {hourlyData.map((row, i) => (
                  <tr key={i} className={selectedSlots.includes(row.time_slot) ? 'selected-row' : ''} style={{
                    backgroundColor: selectedSlots.includes(row.time_slot) ? '#f0f7ff' : 'transparent'
                  }}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedSlots.includes(row.time_slot)}
                        onChange={() => toggleSlotSelection(row.time_slot)}
                      />
                    </td>
                    <td className="time-slot">{row.time_slot}</td>
                    <td className={row.net_pnl >= 0 ? 'pos' : 'neg'}>{formatCurrency(row.net_pnl)}</td>
                    <td>{row.total_trades}</td>
                    <td className={row.avg_trade >= 0 ? 'pos' : 'neg'}>{formatCurrency(row.avg_trade)}</td>
                    <td>{row.win_percentage}%</td>
                    <td className="pos">{formatCurrency(row.avg_winner)}</td>
                    <td className="neg">{formatCurrency(row.avg_loser)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="visualization-section" style={{ marginTop: '40px', borderTop: '1px solid #eee', paddingTop: '30px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ margin: 0 }}>📈 Performance & P&L Curve</h2>

              <div className="selection-group" style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <span className="selector-label" style={{ fontWeight: '600', color: '#666' }}>SYNCED TIME HORIZON:</span>
                <div className="pill-selector">
                  {timeHorizonOptions.map(opt => (
                    <button
                      key={opt.value}
                      className={`filter-btn ${timeHorizon === opt.value ? 'active' : ''}`}
                      onClick={() => setTimeHorizon(opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '20px', alignItems: 'start' }}>
              <div className="chart-wrapper">
                {trades.length > 0 ? (
                  <InteractiveChart
                    data={getChartData()}
                    formatCurrency={formatCurrency}
                    height={500}
                  />
                ) : (
                  <div style={{ backgroundColor: 'white', borderRadius: '12px', padding: '24px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)', height: '500px' }}>
                    <div className="no-data-placeholder">No trade data available for chart</div>
                  </div>
                )}
              </div>

              <div className="backtest-stats-panel" style={{ backgroundColor: 'white', borderRadius: '12px', padding: '24px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)', height: 'fit-content' }}>
                <h3 style={{ borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '20px', marginTop: 0 }}>📊 Strategy Metrics</h3>
                {calculateBacktestingStats() ? (
                  <div className="metric-list" style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div className="metric-item">
                      <div style={{ fontSize: '12px', color: '#666' }}>PROFIT FACTOR</div>
                      <div style={{ fontSize: '20px', fontWeight: '700', color: parseFloat(calculateBacktestingStats()!.profitFactor) >= 1.5 ? '#27ae60' : '#e67e22' }}>
                        {calculateBacktestingStats()?.profitFactor}
                      </div>
                    </div>
                    <div className="metric-item">
                      <div style={{ fontSize: '12px', color: '#666' }}>SHARPE RATIO</div>
                      <div style={{ fontSize: '20px', fontWeight: '700', color: parseFloat(calculateBacktestingStats()!.sharpeRatio) >= 1 ? '#27ae60' : '#e67e22' }}>
                        {calculateBacktestingStats()?.sharpeRatio}
                      </div>
                    </div>
                    <div className="metric-item">
                      <div style={{ fontSize: '12px', color: '#666' }}>MAX DRAWDOWN</div>
                      <div style={{ fontSize: '20px', fontWeight: '700', color: '#c0392b' }}>
                        {formatCurrency(calculateBacktestingStats()?.maxDrawdown || 0)}
                      </div>
                    </div>
                    <div className="metric-item">
                      <div style={{ fontSize: '12px', color: '#666' }}>AVG TRADE</div>
                      <div style={{ fontSize: '20px', fontWeight: '700', color: (calculateBacktestingStats()?.avgTrade || 0) >= 0 ? '#27ae60' : '#c0392b' }}>
                        {formatCurrency(calculateBacktestingStats()?.avgTrade || 0)}
                      </div>
                    </div>
                    <div className="metric-item">
                      <div style={{ fontSize: '12px', color: '#666' }}>WIN RATE</div>
                      <div style={{ fontSize: '20px', fontWeight: '700' }}>
                        {calculateBacktestingStats()?.winRate}%
                      </div>
                    </div>
                    <div className="metric-item" style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #f5f5f5' }}>
                      <div style={{ fontSize: '12px', color: '#666' }}>EXPECTANCY (per trade)</div>
                      <div style={{ fontSize: '20px', fontWeight: '700' }}>
                        {formatCurrency(parseFloat(calculateBacktestingStats()?.expectancy || '0'))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ color: '#999', fontStyle: 'italic' }}>Select time slots to view stats</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AccountsByHour;