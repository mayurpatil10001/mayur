import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import Analytics from '../../../frontend/src/pages/Analytics/Analytics';
import analyticsReducer from '../../../frontend/src/store/slices/analyticsSlice';

const createMockStore = (initialState: any) => {
  return configureStore({
    reducer: {
      analytics: analyticsReducer,
    },
    preloadedState: {
      analytics: initialState,
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

describe('Analytics Component', () => {
  test('renders loading state', () => {
    const store = createMockStore({
      temporalPatterns: [],
      accountComparisons: [],
      selectedAccount: null,
      selectedSymbol: null,
      dateRange: { start: '', end: '' },
      isLoading: true,
      error: null,
    });

    renderWithStore(<Analytics />, store);
    expect(screen.getByText('Loading analytics data...')).toBeInTheDocument();
  });

  test('renders error state', () => {
    const store = createMockStore({
      temporalPatterns: [],
      accountComparisons: [],
      selectedAccount: null,
      selectedSymbol: null,
      dateRange: { start: '', end: '' },
      isLoading: false,
      error: 'Analytics service unavailable',
    });

    renderWithStore(<Analytics />, store);
    expect(screen.getByText('Error loading analytics: Analytics service unavailable')).toBeInTheDocument();
  });

  test('renders analytics with performance metrics', () => {
    const mockData = {
      performanceMetrics: {
        sharpeRatio: 1.25,
        maxDrawdown: 15.5,
        profitFactor: 1.8,
        volatility: 12.3,
      },
      temporalPatterns: {
        bestHours: [
          { hour: 9, winRate: 75.5 },
          { hour: 14, winRate: 68.2 },
        ],
        bestDays: [
          { dayName: 'Tuesday', avgProfit: 125.50 },
          { dayName: 'Thursday', avgProfit: 98.75 },
        ],
      },
      accountComparison: [
        {
          accountName: 'IPS_TM_10',
          symbol: 'NQ',
          totalTrades: 150,
          winRate: 65.5,
          totalPnL: 2500.75,
          sharpeRatio: 1.35,
        },
      ],
    };

    const store = createMockStore({
      data: mockData,
      loading: false,
      error: null,
    });

    renderWithStore(<Analytics />, store);
    
    expect(screen.getByText('Trading Analytics')).toBeInTheDocument();
    expect(screen.getByText('1.25')).toBeInTheDocument(); // Sharpe ratio
    expect(screen.getByText('15.50%')).toBeInTheDocument(); // Max drawdown
    expect(screen.getByText('1.80')).toBeInTheDocument(); // Profit factor
    expect(screen.getByText('12.30%')).toBeInTheDocument(); // Volatility
  });

  test('renders temporal patterns', () => {
    const mockData = {
      performanceMetrics: {},
      temporalPatterns: {
        bestHours: [
          { hour: 9, winRate: 75.5 },
        ],
        bestDays: [
          { dayName: 'Tuesday', avgProfit: 125.50 },
        ],
      },
      accountComparison: [],
    };

    const store = createMockStore({
      data: mockData,
      loading: false,
      error: null,
    });

    renderWithStore(<Analytics />, store);
    
    expect(screen.getByText('9:00')).toBeInTheDocument();
    expect(screen.getByText('75.5% win rate')).toBeInTheDocument();
    expect(screen.getByText('Tuesday')).toBeInTheDocument();
    expect(screen.getByText('125.50 avg P&L')).toBeInTheDocument();
  });

  test('renders account comparison table', () => {
    const mockData = {
      performanceMetrics: {},
      temporalPatterns: { bestHours: [], bestDays: [] },
      accountComparison: [
        {
          accountName: 'IPS_TM_10',
          symbol: 'NQ',
          totalTrades: 150,
          winRate: 65.5,
          totalPnL: 2500.75,
          sharpeRatio: 1.35,
        },
        {
          accountName: 'IPS_TM_13',
          symbol: 'FDAX',
          totalTrades: 89,
          winRate: 58.2,
          totalPnL: -450.25,
          sharpeRatio: 0.85,
        },
      ],
    };

    const store = createMockStore({
      data: mockData,
      loading: false,
      error: null,
    });

    renderWithStore(<Analytics />, store);
    
    expect(screen.getByText('IPS_TM_10')).toBeInTheDocument();
    expect(screen.getByText('IPS_TM_13')).toBeInTheDocument();
    expect(screen.getByText('$2500.75')).toBeInTheDocument();
    expect(screen.getByText('$-450.25')).toBeInTheDocument();
  });

  test('renders empty states when no data available', () => {
    const mockData = {
      performanceMetrics: {},
      temporalPatterns: { bestHours: [], bestDays: [] },
      accountComparison: [],
    };

    const store = createMockStore({
      data: mockData,
      loading: false,
      error: null,
    });

    renderWithStore(<Analytics />, store);
    
    expect(screen.getAllByText('No temporal data available')).toHaveLength(2);
    expect(screen.getByText('No account data available')).toBeInTheDocument();
  });
});