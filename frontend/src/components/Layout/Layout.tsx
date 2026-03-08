import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path ? 'nav-link active' : 'nav-link';
  };

  const [systemStatus, setSystemStatus] = useState<any[]>([]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const API_BASE = `http://${window.location.hostname}:8000`;
        const res = await fetch(`${API_BASE}/api/system/status`);
        const data = await res.json();
        setSystemStatus(data);
      } catch (e) {
        console.error('Failed to fetch system status', e);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const tradesStatus = systemStatus.find(s => s.component && s.component.includes('Trades Table'));
  const totalVolume = tradesStatus?.component?.split('(')[1]?.split(' ')[0] || '0';

  return (
    <div className="layout">
      <header className="header">
        <div className="header-content">
          <div className="header-title-section">
            <h1 className="app-title" style={{ color: '#ffffff', opacity: 1, visibility: 'visible', textShadow: '0 0 1px rgba(255,255,255,0.5)' }}>Trading Optimization Platform</h1>
            <div className="global-status-indicators">
              <div className="status-item">
                <div className={`status-dot ${systemStatus.find(s => s.component === 'API Server')?.status === 'online' ? 'online' : 'offline'}`}></div>
                <span className="status-label">API</span>
              </div>
              <div className="status-item">
                <div className={`status-dot ${systemStatus.find(s => s.component === 'Database')?.status === 'online' ? 'online' : 'offline'}`}></div>
                <span className="status-label">DB</span>
              </div>
              <div className="status-item">
                <span className="status-label">DB Size:</span>
                <span className="status-val" style={{ fontWeight: 800, color: '#60a5fa' }}>{totalVolume}</span>
              </div>
            </div>
          </div>
          <nav className="nav">
            <Link to="/" className={isActive('/')}>
              Home
            </Link>
            <Link to="/dashboard" className={isActive('/dashboard')}>
              Dashboard
            </Link>
            <Link to="/discovery" className={isActive('/discovery')}>
              Discovery Explorer
            </Link>
            <Link to="/monitoring" className={isActive('/monitoring')}>
              System Control
            </Link>
            <Link to="/recommendations" className={isActive('/recommendations')}>
              Recommendations
            </Link>
            <Link to="/analytics" className={isActive('/analytics')}>
              Analytics
            </Link>
            <Link to="/accounts-by-hour" className={isActive('/accounts-by-hour')}>
              Accounts by Hour
            </Link>
          </nav>
        </div>
      </header>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export default Layout;