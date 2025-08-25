import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { store } from '../../../frontend/src/store/store';
import App from '../../../frontend/src/App';

// Mock fetch for API calls
global.fetch = jest.fn();

const renderApp = () => {
  return render(
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  );
};

describe('App Integration Tests', () => {
  beforeEach(() => {
    (fetch as jest.Mock).mockClear();
  });

  test('renders app with navigation and default dashboard route', () => {
    renderApp();
    
    expect(screen.getByText('Trading Optimization Platform')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.getByText('Recommendations')).toBeInTheDocument();
    expect(screen.getByText('Accounts')).toBeInTheDocument();
    
    // Should show dashboard content by default
    expect(screen.getByText('Trading Dashboard')).toBeInTheDocument();
  });

  test('navigation between pages works correctly', async () => {
    renderApp();
    
    // Navigate to Analytics
    fireEvent.click(screen.getByText('Analytics'));
    await waitFor(() => {
      expect(screen.getByText('Trading Analytics')).toBeInTheDocument();
    });

    // Navigate to Recommendations
    fireEvent.click(screen.getByText('Recommendations'));
    await waitFor(() => {
      expect(screen.getByText('Trading Recommendations')).toBeInTheDocument();
    });

    // Navigate to Accounts
    fireEvent.click(screen.getByText('Accounts'));
    await waitFor(() => {
      expect(screen.getByText('Trading Accounts')).toBeInTheDocument();
    });

    // Navigate back to Dashboard
    fireEvent.click(screen.getByText('Dashboard'));
    await waitFor(() => {
      expect(screen.getByText('Trading Dashboard')).toBeInTheDocument();
    });
  });

  test('active navigation link styling is applied correctly', () => {
    renderApp();
    
    // Dashboard should be active by default
    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink).toHaveClass('active');

    // Navigate to Analytics
    fireEvent.click(screen.getByText('Analytics'));
    
    const analyticsLink = screen.getByText('Analytics').closest('a');
    expect(analyticsLink).toHaveClass('active');
    expect(dashboardLink).not.toHaveClass('active');
  });

  test('handles API errors gracefully across pages', async () => {
    // Mock API to return errors
    (fetch as jest.Mock).mockRejectedValue(new Error('API Error'));

    renderApp();

    // Dashboard should show error state
    await waitFor(() => {
      expect(screen.getByText(/Error loading dashboard/)).toBeInTheDocument();
    });

    // Navigate to Analytics - should also handle error
    fireEvent.click(screen.getByText('Analytics'));
    await waitFor(() => {
      expect(screen.getByText(/Error loading analytics/)).toBeInTheDocument();
    });
  });

  test('loading states are displayed correctly', async () => {
    // Mock API to return pending promise
    (fetch as jest.Mock).mockImplementation(() => new Promise(() => {}));

    renderApp();

    // Should show loading state
    expect(screen.getByText('Loading dashboard data...')).toBeInTheDocument();

    // Navigate to other pages and check loading states
    fireEvent.click(screen.getByText('Analytics'));
    expect(screen.getByText('Loading analytics data...')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Recommendations'));
    expect(screen.getByText('Loading recommendations...')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Accounts'));
    expect(screen.getByText('Loading accounts data...')).toBeInTheDocument();
  });

  test('responsive layout works on different screen sizes', () => {
    // Mock window.innerWidth for mobile
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 768,
    });

    renderApp();

    // Layout should still render correctly on mobile
    expect(screen.getByText('Trading Optimization Platform')).toBeInTheDocument();
    expect(screen.getByText('Trading Dashboard')).toBeInTheDocument();
  });

  test('Redux store state is shared across components', async () => {
    // Mock successful API response
    const mockDashboardData = {
      totalAccounts: 5,
      activeTrades: 12,
      totalPnL: 1250.75,
      winRate: 65.5,
      recentActivity: [],
    };

    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockDashboardData,
    });

    renderApp();

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument(); // totalAccounts
    });

    // Navigate to another page and back - data should persist
    fireEvent.click(screen.getByText('Analytics'));
    fireEvent.click(screen.getByText('Dashboard'));

    // Data should still be there (from Redux store)
    expect(screen.getByText('5')).toBeInTheDocument();
  });
});