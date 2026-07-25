/**
 * frontend/src/components/Layout/Layout.tsx
 */

import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import './Layout.css';

const Layout: React.FC = () => {
  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-logo">📈</span>
          <span className="brand-title">SC Optimize</span>
        </div>
        <nav className="sidebar-nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item--active' : ''}`
            }
          >
            📊 Dashboard
          </NavLink>
          <NavLink
            to="/analytics"
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item--active' : ''}`
            }
          >
            🔥 Analytics
          </NavLink>
          <NavLink
            to="/recommendations"
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item--active' : ''}`
            }
          >
            🎯 Recommendations
          </NavLink>
          <NavLink
            to="/walkforward"
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item--active' : ''}`
            }
          >
            🔄 Walk-Forward
          </NavLink>
          <NavLink
            to="/montecarlo"
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item--active' : ''}`
            }
          >
            🎲 Monte Carlo
          </NavLink>
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;