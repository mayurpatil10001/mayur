import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import Dashboard from '../../../frontend/src/pages/Dashboard/Dashboard';
import dashboardReducer from '../../../frontend/src/store/slices/dashboardSlice';

const createMockStore = (initialState: any) => {
  return configureStore({
    reducer: {
      dashboard: dashboardReducer,
    },
    preloadedState: {
      dashboard: initialState,
    },
  });
};

const renderWithStore = (component: React.ReactElement, store: any) => {
  return render(
    <Provider store={store}>
      {component}
    </Provider>
  );
};

describe('Dashboard Component', () => {
  test('renders loading state', () => {
    const store = createMockStore({
      performanceMetrics: {},
      currentRecommendation: null,
      recentTrades: [],
      isLoadingMetrics: true,
      isLoadingRecommendation: false,
      isLoadingTrades: false,
      metricsError: null,
      recommendationError: null,
      tradesError: null,
      selectedAccount: null,
      lastUpdated: null,
    });

    renderWithStore(<Dashboard />, store);
    expect(screen.getByText('Loading metrics...')).toBeInTheDocument();
  });

  test('renders account selector', () => {
    const store = createMockStore({
      performanceMetrics: {},
      currentRecommendation: null,
      recentTrades: [],
      isLoadingMetrics: false,
      isLoadingRecommendation: false,
      isLoadingTrades: false,
      metricsError: null,
      recommendationError: null,
      tradesError: null,
      selectedAccount: null,
      lastUpdated: null,
    });

    renderWithStore(<Dashboard />, store);
    expect(screen.getByText('Trading Optimization Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Select Account')).toBeInTheDocument();
  });

  test('renders dashboard with performance metrics', () => {
    const mockMetrics = {
      account_name: 'IPS_TM_10',
      symbol: 'NQ',
      total_return: 1250.75,
      win_rate: 0.655,
      total_trades: 150,
      profit_factor: 1.8,
      max_drawdown: 0.15,
      sharpe_ratio: 1.25,
    };

    const store = createMockStore({
      performanceMetrics: { 'IPS_TM_10': mockMetrics },
      currentRecommendation: null,
      recentTrades: [],
      isLoadingMetrics: false,
      isLoadingRecommendation: false,
      isLoadingTrades: false,
      metricsError: null,
      recommendationError: null,
      tradesError: null,
      selectedAccount: 'IPS_TM_10',
      lastUpdated: null,
    });

    renderWithStore(<Dashboard />, store);
    
    expect(screen.getByText('Trading Optimization Dashboard')).toBeInTheDocument();
    expect(screen.getByText('$1250.75')).toBeInTheDocument(); // total_return
    expect(screen.getByText('65.5%')).toBeInTheDocument(); // win_rate
    expect(screen.getByText('150')).toBeInTheDocument(); // total_trades
  });

  test('renders no account selected state', () => {
    const store = createMockStore({
      performanceMetrics: {},
      currentRecommendation: null,
      recentTrades: [],
      isLoadingMetrics: false,
      isLoadingRecommendation: false,
      isLoadingTrades: false,
      metricsError: null,
      recommendationError: null,
      tradesError: null,
      selectedAccount: null,
      lastUpdated: null,
    });

    renderWithStore(<Dashboard />, store);
    
    expect(screen.getByText('Select an Account')).toBeInTheDocument();
    expect(screen.getByText('Choose an account from the dropdown above to view dashboard data.')).toBeInTheDocument();
  });

  test('renders current recommendation when available', () => {
    const mockRecommendation = {
      account_name: 'IPS_TM_10',
      symbol: 'NQ',
      recommended_action: 'TRADE',
      confidence_score: 0.85,
      expected_return: 125.50,
      reasoning: 'Strong historical performance at this time',
    };

    const store = createMockStore({
      performanceMetrics: {},
      currentRecommendation: mockRecommendation,
      recentTrades: [],
      isLoadingMetrics: false,
      isLoadingRecommendation: false,
      isLoadingTrades: false,
      metricsError: null,
      recommendationError: null,
      tradesError: null,
      selectedAccount: 'IPS_TM_10',
      lastUpdated: null,
    });

    renderWithStore(<Dashboard />, store);
    
    expect(screen.getByText('IPS_TM_10')).toBeInTheDocument();
    expect(screen.getByText('TRADE')).toBeInTheDocument();
    expect(screen.getByText('85.0%')).toBeInTheDocument(); // confidence
    expect(screen.getByText('Strong historical performance at this time')).toBeInTheDocument();
  });
});