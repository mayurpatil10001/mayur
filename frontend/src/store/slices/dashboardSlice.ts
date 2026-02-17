import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiService } from '../../services/api';
import { PerformanceMetrics, TradingRecommendation, Trade, APIResponse } from '../../types/api';

interface DashboardState {
  // Performance data
  performanceMetrics: Record<string, PerformanceMetrics>;
  // Recent recommendations
  currentRecommendation: TradingRecommendation | null;
  // Recent trades
  recentTrades: Trade[];
  // Loading states
  isLoadingMetrics: boolean;
  isLoadingRecommendation: boolean;
  isLoadingTrades: boolean;
  // Error states
  metricsError: string | null;
  recommendationError: string | null;
  tradesError: string | null;
  // Selected account for dashboard
  selectedAccount: string | null;
  // Last updated timestamps
  lastUpdated: string | null;
}

const initialState: DashboardState = {
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
};

// Async thunks
export const fetchPerformanceMetrics = createAsyncThunk(
  'dashboard/fetchPerformanceMetrics',
  async (accountName: string) => {
    const response = await apiService.getPerformanceMetrics(accountName);
    if (response.status === 'success' && response.data) {
      return { accountName, metrics: response.data };
    }
    throw new Error(response.message || 'Failed to fetch performance metrics');
  }
);

export const fetchCurrentRecommendation = createAsyncThunk(
  'dashboard/fetchCurrentRecommendation',
  async (params?: { account_name?: string; symbol?: string }) => {
    const response = await apiService.getCurrentRecommendation(params);
    if (response.status === 'success' && response.data) {
      // Backend returns array, take first recommendation
      return Array.isArray(response.data) && response.data.length > 0 ? response.data[0] : null;
    }
    throw new Error(response.message || 'Failed to fetch recommendation');
  }
);

export const fetchRecentTrades = createAsyncThunk(
  'dashboard/fetchRecentTrades',
  async ({ accountName, limit = 10 }: { accountName: string; limit?: number }) => {
    const response = await apiService.getTrades(accountName, { limit });
    if (response.status === 'success' && response.data) {
      // Backend returns paginated response, extract items
      return response.data.items || response.data || [];
    }
    throw new Error(response.message || 'Failed to fetch trades');
  }
);

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    setSelectedAccount: (state, action: PayloadAction<string>) => {
      state.selectedAccount = action.payload;
    },
    clearDashboardData: (state) => {
      state.performanceMetrics = {};
      state.currentRecommendation = null;
      state.recentTrades = [];
      state.metricsError = null;
      state.recommendationError = null;
      state.tradesError = null;
    },
    clearErrors: (state) => {
      state.metricsError = null;
      state.recommendationError = null;
      state.tradesError = null;
    },
  },
  extraReducers: (builder) => {
    // Performance metrics
    builder
      .addCase(fetchPerformanceMetrics.pending, (state) => {
        state.isLoadingMetrics = true;
        state.metricsError = null;
      })
      .addCase(fetchPerformanceMetrics.fulfilled, (state, action) => {
        state.isLoadingMetrics = false;
        state.performanceMetrics[action.payload.accountName] = action.payload.metrics;
        state.lastUpdated = new Date().toISOString();
      })
      .addCase(fetchPerformanceMetrics.rejected, (state, action) => {
        state.isLoadingMetrics = false;
        state.metricsError = action.error.message || 'Failed to load metrics';
      });

    // Current recommendation
    builder
      .addCase(fetchCurrentRecommendation.pending, (state) => {
        state.isLoadingRecommendation = true;
        state.recommendationError = null;
      })
      .addCase(fetchCurrentRecommendation.fulfilled, (state, action) => {
        state.isLoadingRecommendation = false;
        state.currentRecommendation = action.payload;
        state.lastUpdated = new Date().toISOString();
      })
      .addCase(fetchCurrentRecommendation.rejected, (state, action) => {
        state.isLoadingRecommendation = false;
        state.recommendationError = action.error.message || 'Failed to load recommendation';
      });

    // Recent trades
    builder
      .addCase(fetchRecentTrades.pending, (state) => {
        state.isLoadingTrades = true;
        state.tradesError = null;
      })
      .addCase(fetchRecentTrades.fulfilled, (state, action) => {
        state.isLoadingTrades = false;
        state.recentTrades = action.payload;
        state.lastUpdated = new Date().toISOString();
      })
      .addCase(fetchRecentTrades.rejected, (state, action) => {
        state.isLoadingTrades = false;
        state.tradesError = action.error.message || 'Failed to load trades';
      });
  },
});

export const { setSelectedAccount, clearDashboardData, clearErrors } = dashboardSlice.actions;
export default dashboardSlice.reducer;