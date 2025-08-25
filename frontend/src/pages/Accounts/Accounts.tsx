import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../store/store';
import { fetchAccounts } from '../../store/slices/accountsSlice';
import './Accounts.css';

const Accounts: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { accounts, isLoading, error } = useSelector((state: RootState) => state.accounts);

  useEffect(() => {
    dispatch(fetchAccounts());
  }, [dispatch]);

  // Helper functions for formatting
  const getDayOfWeekName = (dayOfWeek: number | null): string => {
    if (dayOfWeek === null || dayOfWeek === undefined) return 'N/A';
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    return days[dayOfWeek] || 'N/A';
  };

  const formatHour = (hour: number | null): string => {
    if (hour === null || hour === undefined) return 'N/A';
    const period = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    return `${displayHour}:00 ${period}`;
  };

  const formatPnL = (pnl: number): string => {
    const formatted = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(pnl);
    return pnl >= 0 ? formatted : formatted;
  };



  if (isLoading) {
    return (
      <div className="accounts">
        <div className="loading">Loading accounts data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="accounts">
        <div className="error">Error loading accounts: {error}</div>
      </div>
    );
  }

  return (
    <div className="accounts">
      <h1>Trading Accounts</h1>
      
      <div className="accounts-summary">
        <div className="summary-card">
          <h3>Total Accounts</h3>
          <div className="summary-value">{accounts?.length || 0}</div>
        </div>
        <div className="summary-card">
          <h3>Active Accounts</h3>
          <div className="summary-value">
            {accounts?.filter(acc => acc.is_active !== false).length || 0}
          </div>
        </div>
        <div className="summary-card">
          <h3>Symbols Traded</h3>
          <div className="summary-value">
            {new Set(accounts?.map(acc => acc.symbol)).size || 0}
          </div>
        </div>
      </div>

      <div className="accounts-table">
        <div className="table-header">
          <span>Account Name</span>
          <span>Symbol</span>
          <span>Total Trades</span>
          <span>Total P&L</span>
          <span>Best Day</span>
          <span>Best Hour</span>
          <span>First Trade</span>
          <span>Last Trade</span>
          <span>Status</span>
        </div>
        
        {accounts?.length ? (
          accounts.map((account, index) => (
            <div key={index} className="table-row">
              <span className="account-name">{account.name}</span>
              <span className="symbol-badge">{account.symbol}</span>
              <span>{account.total_trades}</span>
              <span className={`pnl ${account.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                {formatPnL(account.total_pnl)}
              </span>
              <span>{getDayOfWeekName(account.best_day_of_week)}</span>
              <span>{formatHour(account.best_hour_of_day)}</span>
              <span>
                {account.first_trade_date 
                  ? new Date(account.first_trade_date).toLocaleDateString()
                  : 'N/A'
                }
              </span>
              <span>
                {account.last_trade_date 
                  ? new Date(account.last_trade_date).toLocaleDateString()
                  : 'N/A'
                }
              </span>
              <span className={`status ${account.is_active !== false ? 'active' : 'inactive'}`}>
                {account.is_active !== false ? 'Active' : 'Inactive'}
              </span>
            </div>
          ))
        ) : (
          <div className="no-accounts">
            <h3>No Accounts Found</h3>
            <p>No trading accounts have been configured or imported yet.</p>
          </div>
        )}
      </div>

      {accounts?.length > 0 && (
        <div className="accounts-details">
          <h2>Account Details</h2>
          <div className="details-grid">
            {accounts.map((account, index) => (
              <div key={index} className="account-detail-card">
                <div className="card-header">
                  <h3>{account.name}</h3>
                  <span className={`status-indicator ${account.is_active !== false ? 'active' : 'inactive'}`}>
                    {account.is_active !== false ? 'Active' : 'Inactive'}
                  </span>
                </div>
                
                <div className="card-content">
                  <div className="detail-row">
                    <span>Symbol:</span>
                    <span className="symbol-badge">{account.symbol}</span>
                  </div>
                  <div className="detail-row">
                    <span>Total Trades:</span>
                    <span>{account.total_trades}</span>
                  </div>
                  <div className="detail-row">
                    <span>Total P&L:</span>
                    <span className={`pnl ${account.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                      {formatPnL(account.total_pnl)}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span>Best Trading Day:</span>
                    <span>{getDayOfWeekName(account.best_day_of_week)}</span>
                  </div>
                  <div className="detail-row">
                    <span>Best Trading Hour:</span>
                    <span>{formatHour(account.best_hour_of_day)}</span>
                  </div>
                  <div className="detail-row">
                    <span>Trading Period:</span>
                    <span>
                      {account.first_trade_date && account.last_trade_date
                        ? `${new Date(account.first_trade_date).toLocaleDateString()} - ${new Date(account.last_trade_date).toLocaleDateString()}`
                        : 'N/A'
                      }
                    </span>
                  </div>
                  <div className="detail-row">
                    <span>Days Active:</span>
                    <span>
                      {account.first_trade_date && account.last_trade_date
                        ? Math.ceil((new Date(account.last_trade_date).getTime() - new Date(account.first_trade_date).getTime()) / (1000 * 60 * 60 * 24))
                        : 'N/A'
                      }
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Accounts;