import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchAccounts } from '../../store/slices/accountsSlice';
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

const AccountsByHour: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { accounts, isLoading: accountsLoading } = useSelector((state: RootState) => state.accounts);
  
  const [selectedAccount, setSelectedAccount] = useState<string>('');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [hourlyData, setHourlyData] = useState<HourlyBreakdown[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only fetch accounts when user interacts with the dropdown
  const handleAccountDropdownClick = () => {
    if (accounts.length === 0 && !accountsLoading) {
      dispatch(fetchAccounts());
    }
  };

  // Get unique account names
  const uniqueAccounts = Array.from(new Set(accounts.map(acc => acc.name)));
  
  // Get symbols for selected account
  const availableSymbols = accounts
    .filter(acc => acc.name === selectedAccount)
    .map(acc => acc.symbol);

  const fetchHourlyBreakdown = async () => {
    if (!selectedAccount || !selectedSymbol) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/accounts/${selectedAccount}/hourly-breakdown?symbol=${selectedSymbol}`
      );
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setHourlyData(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setHourlyData([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (selectedAccount && selectedSymbol) {
      fetchHourlyBreakdown();
    }
  }, [selectedAccount, selectedSymbol]);

  // Auto-select first symbol when account changes
  useEffect(() => {
    if (selectedAccount && availableSymbols.length > 0) {
      setSelectedSymbol(availableSymbols[0]);
    }
  }, [selectedAccount]);

  const formatCurrency = (value: number | null | undefined): string => {
    if (value === null || value === undefined || isNaN(value)) {
      return '$0.00';
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const formatPercentage = (value: number | null | undefined): string => {
    if (value === null || value === undefined || isNaN(value)) {
      return '0.00%';
    }
    return `${value.toFixed(2)}%`;
  };

  return (
    <div className="accounts-by-hour">
      <h1>Accounts by Hour</h1>
      <p>30-minute interval breakdown based on trade entry time (matching SierraChart logic)</p>
      
      <div className="controls">
        <div className="control-group">
          <label htmlFor="account-select">Account:</label>
          <select 
            id="account-select"
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            onFocus={handleAccountDropdownClick}
            disabled={accountsLoading}
          >
            <option value="">Select an account...</option>
            {uniqueAccounts.map(account => (
              <option key={account} value={account}>{account}</option>
            ))}
          </select>
        </div>

        {selectedAccount && (
          <div className="control-group">
            <label htmlFor="symbol-select">Symbol:</label>
            <select 
              id="symbol-select"
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
            >
              <option value="">Select a symbol...</option>
              {availableSymbols.map(symbol => (
                <option key={symbol} value={symbol}>{symbol}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="loading">Loading hourly breakdown...</div>
      )}

      {error && (
        <div className="error">Error: {error}</div>
      )}

      {hourlyData.length > 0 && (
        <div className="hourly-table">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Net P&L</th>
                <th>Total Trades</th>
                <th>Avg Trade</th>
                <th>% Winners</th>
                <th>Avg Winner</th>
                <th>Avg Loser</th>
                <th>Largest Winner</th>
                <th>Largest Loser</th>
                <th>Equity Peak</th>
              </tr>
            </thead>
            <tbody>
              {hourlyData.map((row, index) => (
                <tr key={index}>
                  <td className="time-slot">{row.time_slot}</td>
                  <td className={`pnl ${row.net_pnl >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(row.net_pnl)}
                  </td>
                  <td>{row.total_trades}</td>
                  <td className={`pnl ${(row.avg_trade || 0) >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(row.avg_trade)}
                  </td>
                  <td className={(row.win_percentage || 0) >= 50 ? 'positive' : 'negative'}>
                    {row.win_percentage ? row.win_percentage.toFixed(1) : '0.0'}%
                  </td>
                  <td className="positive">{formatCurrency(row.avg_winner)}</td>
                  <td className="negative">{formatCurrency(row.avg_loser)}</td>
                  <td className="positive">{formatCurrency(row.largest_winner)}</td>
                  <td className="negative">{formatCurrency(row.largest_loser)}</td>
                  <td className={`pnl ${(row.equity_peak || 0) >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(row.equity_peak)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedAccount && selectedSymbol && hourlyData.length === 0 && !isLoading && !error && (
        <div className="no-data">
          <h3>No Data Found</h3>
          <p>No trading data found for {selectedAccount} ({selectedSymbol})</p>
        </div>
      )}
    </div>
  );
};

export default AccountsByHour;