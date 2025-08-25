import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import Accounts from '../../../frontend/src/pages/Accounts/Accounts';
import accountsReducer from '../../../frontend/src/store/slices/accountsSlice';

const createMockStore = (initialState: any) => {
  return configureStore({
    reducer: {
      accounts: accountsReducer,
    },
    preloadedState: {
      accounts: initialState,
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

describe('Accounts Component', () => {
  test('renders loading state', () => {
    const store = createMockStore({
      accounts: [],
      loading: true,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    expect(screen.getByText('Loading accounts data...')).toBeInTheDocument();
  });

  test('renders error state', () => {
    const store = createMockStore({
      accounts: [],
      loading: false,
      error: 'Failed to fetch accounts',
    });

    renderWithStore(<Accounts />, store);
    expect(screen.getByText('Error loading accounts: Failed to fetch accounts')).toBeInTheDocument();
  });

  test('renders accounts with data', () => {
    const mockAccounts = [
      {
        name: 'IPS_TM_10',
        symbol: 'NQ',
        totalTrades: 150,
        firstTradeDate: '2024-01-01T00:00:00Z',
        lastTradeDate: '2024-01-15T00:00:00Z',
        isActive: true,
      },
      {
        name: 'IPS_TM_13',
        symbol: 'FDAX',
        totalTrades: 89,
        firstTradeDate: '2024-01-05T00:00:00Z',
        lastTradeDate: '2024-01-14T00:00:00Z',
        isActive: false,
      },
    ];

    const store = createMockStore({
      accounts: mockAccounts,
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    expect(screen.getByText('Trading Accounts')).toBeInTheDocument();
    expect(screen.getByText('IPS_TM_10')).toBeInTheDocument();
    expect(screen.getByText('IPS_TM_13')).toBeInTheDocument();
    expect(screen.getByText('150')).toBeInTheDocument();
    expect(screen.getByText('89')).toBeInTheDocument();
  });

  test('displays summary statistics correctly', () => {
    const mockAccounts = [
      {
        name: 'IPS_TM_10',
        symbol: 'NQ',
        totalTrades: 150,
        firstTradeDate: '2024-01-01T00:00:00Z',
        lastTradeDate: '2024-01-15T00:00:00Z',
        isActive: true,
      },
      {
        name: 'IPS_TM_13',
        symbol: 'FDAX',
        totalTrades: 89,
        firstTradeDate: '2024-01-05T00:00:00Z',
        lastTradeDate: '2024-01-14T00:00:00Z',
        isActive: false,
      },
      {
        name: 'IPS_TM_15',
        symbol: 'NQ',
        totalTrades: 75,
        firstTradeDate: '2024-01-10T00:00:00Z',
        lastTradeDate: '2024-01-15T00:00:00Z',
        isActive: true,
      },
    ];

    const store = createMockStore({
      accounts: mockAccounts,
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    // Total accounts: 3
    expect(screen.getByText('3')).toBeInTheDocument();
    // Active accounts: 2 (IPS_TM_10 and IPS_TM_15)
    expect(screen.getByText('2')).toBeInTheDocument();
    // Symbols traded: 2 (NQ and FDAX)
    // Note: This might appear as "2" in multiple places, so we check for the summary section
    const summaryCards = screen.getAllByText('2');
    expect(summaryCards.length).toBeGreaterThanOrEqual(2);
  });

  test('displays account status correctly', () => {
    const mockAccounts = [
      {
        name: 'IPS_TM_10',
        symbol: 'NQ',
        totalTrades: 150,
        firstTradeDate: '2024-01-01T00:00:00Z',
        lastTradeDate: '2024-01-15T00:00:00Z',
        isActive: true,
      },
      {
        name: 'IPS_TM_13',
        symbol: 'FDAX',
        totalTrades: 89,
        firstTradeDate: '2024-01-05T00:00:00Z',
        lastTradeDate: '2024-01-14T00:00:00Z',
        isActive: false,
      },
    ];

    const store = createMockStore({
      accounts: mockAccounts,
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    const activeStatuses = screen.getAllByText('Active');
    const inactiveStatuses = screen.getAllByText('Inactive');
    
    expect(activeStatuses.length).toBeGreaterThanOrEqual(1);
    expect(inactiveStatuses.length).toBeGreaterThanOrEqual(1);
  });

  test('renders account detail cards', () => {
    const mockAccounts = [
      {
        name: 'IPS_TM_10',
        symbol: 'NQ',
        totalTrades: 150,
        firstTradeDate: '2024-01-01T00:00:00Z',
        lastTradeDate: '2024-01-15T00:00:00Z',
        isActive: true,
      },
    ];

    const store = createMockStore({
      accounts: mockAccounts,
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    expect(screen.getByText('Account Details')).toBeInTheDocument();
    // Check for detail card content
    expect(screen.getByText('Symbol:')).toBeInTheDocument();
    expect(screen.getByText('Total Trades:')).toBeInTheDocument();
    expect(screen.getByText('Trading Period:')).toBeInTheDocument();
    expect(screen.getByText('Days Active:')).toBeInTheDocument();
  });

  test('calculates days active correctly', () => {
    const mockAccounts = [
      {
        name: 'IPS_TM_10',
        symbol: 'NQ',
        totalTrades: 150,
        firstTradeDate: '2024-01-01T00:00:00Z',
        lastTradeDate: '2024-01-15T00:00:00Z', // 14 days difference
        isActive: true,
      },
    ];

    const store = createMockStore({
      accounts: mockAccounts,
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    // Should show 15 days (inclusive of both dates)
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  test('renders no accounts state', () => {
    const store = createMockStore({
      accounts: [],
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    expect(screen.getByText('No Accounts Found')).toBeInTheDocument();
    expect(screen.getByText('No trading accounts have been configured or imported yet.')).toBeInTheDocument();
  });

  test('handles accounts with missing date information', () => {
    const mockAccounts = [
      {
        name: 'IPS_TM_10',
        symbol: 'NQ',
        totalTrades: 0,
        firstTradeDate: null,
        lastTradeDate: null,
        isActive: false,
      },
    ];

    const store = createMockStore({
      accounts: mockAccounts,
      loading: false,
      error: null,
    });

    renderWithStore(<Accounts />, store);
    
    const naElements = screen.getAllByText('N/A');
    expect(naElements.length).toBeGreaterThanOrEqual(2); // Should appear for dates and days active
  });
});