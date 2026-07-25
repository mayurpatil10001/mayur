/**
 * frontend/src/App.tsx
 */

import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard/Dashboard';
import Analytics from './pages/Analytics/Analytics';
import Recommendations from './pages/Recommendations/Recommendations';
import WalkForward from './pages/WalkForward/WalkForward';
import MonteCarlo from './pages/MonteCarlo/MonteCarlo';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="recommendations" element={<Recommendations />} />
          <Route path="walkforward" element={<WalkForward />} />
          <Route path="montecarlo" element={<MonteCarlo />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;