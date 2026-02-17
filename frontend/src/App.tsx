import React from 'react';
import { Routes, Route } from 'react-router-dom';
import './App.css';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard/Dashboard';
import SimpleDashboard from './pages/Dashboard/SimpleDashboard';
import Analytics from './pages/Analytics/Analytics';
import Recommendations from './pages/Recommendations/Recommendations';
import AccountsByHour from './pages/AccountsByHour/AccountsByHour';
import Monitoring from './pages/Monitoring/Monitoring';
import TradeImport from './pages/TradeImport/TradeImport';
import AccountManagement from './pages/AccountManagement/AccountManagement';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <Layout>
          <Routes>
            <Route path="/" element={<SimpleDashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/accounts-by-hour" element={<AccountsByHour />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/trade-import" element={<TradeImport />} />
            <Route path="/account-management" element={<AccountManagement />} />
          </Routes>
        </Layout>
      </ErrorBoundary>
    </div>
  );
}

export default App;