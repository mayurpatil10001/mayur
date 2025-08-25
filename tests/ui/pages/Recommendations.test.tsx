import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import Recommendations from '../../../frontend/src/pages/Recommendations/Recommendations';
import recommendationsReducer from '../../../frontend/src/store/slices/recommendationsSlice';

const createMockStore = (initialState: any) => {
  return configureStore({
    reducer: {
      recommendations: recommendationsReducer,
    },
    preloadedState: {
      recommendations: initialState,
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

describe('Recommendations Component', () => {
  test('renders loading state', () => {
    const store = createMockStore({
      recommendations: [],
      loading: true,
      error: null,
    });

    renderWithStore(<Recommendations />, store);
    expect(screen.getByText('Loading recommendations...')).toBeInTheDocument();
  });

  test('renders error state', () => {
    const store = createMockStore({
      recommendations: [],
      loading: false,
      error: 'Recommendation service unavailable',
    });

    renderWithStore(<Recommendations />, store);
    expect(screen.getByText('Error loading recommendations: Recommendation service unavailable')).toBeInTheDocument();
  });

  test('renders recommendations with data', () => {
    const mockRecommendations = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        accountName: 'IPS_TM_10',
        symbol: 'NQ',
        recommendedAction: 'TRADE',
        confidenceScore: 0.85,
        expectedReturn: 125.50,
        expectedRisk: 8.5,
        reasoning: 'Strong historical performance at this time',
        hourOfDay: 10,
        dayOfWeek: 1,
        historicalWinRate: 75.5,
        avgProfitThisTime: 98.25,
      },
      {
        timestamp: '2024-01-15T10:30:00Z',
        accountName: 'IPS_TM_13',
        symbol: 'FDAX',
        recommendedAction: 'AVOID',
        confidenceScore: 0.65,
        expectedReturn: -25.75,
        expectedRisk: 12.3,
        reasoning: 'High volatility expected during this period',
        hourOfDay: 10,
        dayOfWeek: 1,
        historicalWinRate: 45.2,
        avgProfitThisTime: -15.50,
      },
    ];

    const store = createMockStore({
      recommendations: mockRecommendations,
      loading: false,
      error: null,
    });

    renderWithStore(<Recommendations />, store);
    
    expect(screen.getByText('Trading Recommendations')).toBeInTheDocument();
    expect(screen.getByText('IPS_TM_10')).toBeInTheDocument();
    expect(screen.getByText('IPS_TM_13')).toBeInTheDocument();
    expect(screen.getByText('TRADE')).toBeInTheDocument();
    expect(screen.getByText('AVOID')).toBeInTheDocument();
  });

  test('displays confidence scores with correct styling', () => {
    const mockRecommendations = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        accountName: 'IPS_TM_10',
        symbol: 'NQ',
        recommendedAction: 'TRADE',
        confidenceScore: 0.85, // High confidence
        expectedReturn: 125.50,
        expectedRisk: 8.5,
        reasoning: 'Test reasoning',
        hourOfDay: 10,
        dayOfWeek: 1,
        historicalWinRate: 75.5,
        avgProfitThisTime: 98.25,
      },
    ];

    const store = createMockStore({
      recommendations: mockRecommendations,
      loading: false,
      error: null,
    });

    renderWithStore(<Recommendations />, store);
    
    const confidenceElement = screen.getByText('85.0%');
    expect(confidenceElement).toHaveClass('confidence-high');
  });

  test('displays expected return with correct styling for positive/negative values', () => {
    const mockRecommendations = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        accountName: 'IPS_TM_10',
        symbol: 'NQ',
        recommendedAction: 'TRADE',
        confidenceScore: 0.85,
        expectedReturn: 125.50, // Positive return
        expectedRisk: 8.5,
        reasoning: 'Test reasoning',
        hourOfDay: 10,
        dayOfWeek: 1,
        historicalWinRate: 75.5,
        avgProfitThisTime: 98.25,
      },
    ];

    const store = createMockStore({
      recommendations: mockRecommendations,
      loading: false,
      error: null,
    });

    renderWithStore(<Recommendations />, store);
    
    const returnElement = screen.getByText('$125.50');
    expect(returnElement).toHaveClass('positive');
  });

  test('refresh button triggers fetchRecommendations', () => {
    const store = createMockStore({
      recommendations: [],
      loading: false,
      error: null,
    });

    const dispatchSpy = jest.spyOn(store, 'dispatch');

    renderWithStore(<Recommendations />, store);
    
    const refreshButton = screen.getByText('Refresh Recommendations');
    fireEvent.click(refreshButton);
    
    expect(dispatchSpy).toHaveBeenCalled();
  });

  test('renders no recommendations state', () => {
    const store = createMockStore({
      recommendations: [],
      loading: false,
      error: null,
    });

    renderWithStore(<Recommendations />, store);
    
    expect(screen.getByText('No Recommendations Available')).toBeInTheDocument();
    expect(screen.getByText('Insufficient historical data')).toBeInTheDocument();
    expect(screen.getByText('Market conditions not favorable')).toBeInTheDocument();
    expect(screen.getByText('All accounts showing high risk patterns')).toBeInTheDocument();
  });

  test('displays current time information', () => {
    const store = createMockStore({
      recommendations: [],
      loading: false,
      error: null,
    });

    renderWithStore(<Recommendations />, store);
    
    expect(screen.getByText('Current Time Analysis')).toBeInTheDocument();
    // Note: Exact time values will depend on when test runs, so we just check for presence
    expect(screen.getByText(/Hour:/)).toBeInTheDocument();
    expect(screen.getByText(/Day:/)).toBeInTheDocument();
  });
});