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

describe('Dashboard Workflow E2E Tests', () => {
  beforeEach(() => {
    (fetch as jest.Mock).mockClear();
  });

  test('complete dashboard workflow - select account, view metrics, check recommendations', async () => {
    // Mock API responses
    const mockPerformanceMetrics = {
      account_name: 'IPS_TM_10',
      symbol: 'NQ',
      total_return: 1250.75,
      win_rate: 0.655,
      total_trades: 150,
      profit_factor: 1.8,
      max_drawdown: 0.15,
      sharpe_ratio: 1.25,
    };

    const mockRecommendation = {
      account_name: 'IPS_TM_10',
      symbol: 'NQ',
      recommended_action: 'TRADE',
      confidence_score: 0.85,
      expected_return: 125.50,
      reasoning: 'Strong historical performance at this time',
    };

    const mockTrades = {
      items: [
        {
          trade_id: '1',
          symbol: 'NQ',
          profit_loss: 125.50,
          side: 'LONG',
          quantity: 1,
          entry_time: '2024-01-15T10:30:00Z',
        },
      ],
    };

    (fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, data: mockPerformanceMetrics }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, data: [mockRecommendation] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, data: mockTrades }),
      });

    renderApp();

    // Should start on dashboard
    expect(screen.getByText('Trading Optimization Dashboard')).toBeInTheDocument();

    // Select an account
    const accountSelect = screen.getByRole('combobox');
    fireEvent.change(accountSelect, { target: { value: 'IPS_TM_10' } });

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('$1250.75')).toBeInTheDocument();
    });

    // Check that performance metrics are displayed
    expect(screen.getByText('65.5%')).toBeInTheDocument(); // win rate
    expect(screen.getByText('150')).toBeInTheDocument(); // total trades

    // Check that recommendation is displayed
    expect(screen.getByText('TRADE')).toBeInTheDocument();
    expect(screen.getByText('85.0%')).toBeInTheDocument(); // confidence

    // Switch to temporal analysis tab
    fireEvent.click(screen.getByText('Temporal Analysis'));
    expect(screen.getByText('Temporal analysis charts will be displayed here.')).toBeInTheDocument();

    // Switch to monte carlo tab
    fireEvent.click(screen.getByText('Monte Carlo'));
    expect(screen.getByText('Monte Carlo simulation results will be displayed here.')).toBeInTheDocument();

    // Switch back to overview
    fireEvent.click(screen.getByText('Overview'));
    expect(screen.getByText('Recent Trades')).toBeInTheDocument();
  });

  test('navigation workflow - visit all pages', async () => {
    renderApp();

    // Start on dashboard
    expect(screen.getByText('Trading Optimization Dashboard')).toBeInTheDocument();

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
      expect(screen.getByText('Trading Optimization Dashboard')).toBeInTheDocument();
    });
  });

  test('error handling workflow', async () => {
    // Mock API to return errors
    (fetch as jest.Mock).mockRejectedValue(new Error('API Error'));

    renderApp();

    // Select an account to trigger API calls
    const accountSelect = screen.getByRole('combobox');
    fireEvent.change(accountSelect, { target: { value: 'IPS_TM_10' } });

    // Should show error states instead of crashing
    await waitFor(() => {
      // The app should still be functional even with API errors
      expect(screen.getByText('Trading Optimization Dashboard')).toBeInTheDocument();
    });
  });
});