import React from 'react';
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

  return (
    <div className="layout">
      <header className="header">
        <div className="header-content">
          <h1 className="app-title">Trading Optimization Platform</h1>
          <nav className="nav">
            <Link to="/" className={isActive('/')}>
              Home
            </Link>
            <Link to="/dashboard" className={isActive('/dashboard')}>
              Dashboard
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