import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

export interface TradingRecommendation {
  id?: string;
  timestamp: string;
  account_name: string;
  symbol: string;
  recommended_action: 'TRADE' | 'AVOID';
  confidence_score: number;
  expected_return: number;
  expected_risk: number;
  reasoning: string;
  hour_of_day: number;
  day_of_week: number;
  historical_win_rate: number;
  avg_profit_this_time: number;
  // Legacy properties for backward compatibility
  accountName?: string;
  recommendedAction?: 'TRADE' | 'AVOID';
  confidenceScore?: number;
  expectedReturn?: number;
  expectedRisk?: number;
  hourOfDay?: number;
  dayOfWeek?: number;
  historicalWinRate?: number;
  avgProfitThisTime?: number;
}

export interface RecommendationFilters {
  account?: string;
  symbol?: string;
  action?: 'TRADE' | 'AVOID';
  minConfidence?: number;
  dateRange?: {
    start: string;
    end: string;
  };
}

export interface RecommendationsState {
  recommendations: TradingRecommendation[];
  currentRecommendation: TradingRecommendation | null;
  filters: RecommendationFilters;
  isLoading: boolean;
  error: string | null;
  autoRefresh: boolean;
  refreshInterval: number; // in seconds
}

const initialState: RecommendationsState = {
  recommendations: [],
  currentRecommendation: null,
  filters: {},
  isLoading: false,
  error: null,
  autoRefresh: true,
  refreshInterval: 30,
};

// Async thunks
export const fetchRecommendations = createAsyncThunk(
  'recommendations/fetchRecommendations',
  async (filters: RecommendationFilters = {}) => {
    const queryParams = new URLSearchParams();
    
    if (filters.account) queryParams.append('account_name', filters.account);
    if (filters.symbol) queryParams.append('symbol', filters.symbol);
    if (filters.minConfidence) queryParams.append('min_confidence', filters.minConfidence.toString());

    const response = await fetch(`http://localhost:8000/api/v1/recommendations/current?${queryParams}`);
    if (!response.ok) {
      throw new Error('Failed to fetch recommendations');
    }
    const result = await response.json();
    return result.data || [];
  }
);

export const fetchCurrentRecommendation = createAsyncThunk(
  'recommendations/fetchCurrentRecommendation',
  async () => {
    const response = await fetch('http://localhost:8000/api/v1/recommendations/current');
    if (!response.ok) {
      throw new Error('Failed to fetch current recommendation');
    }
    const result = await response.json();
    return result.data?.[0] || null;
  }
);

const recommendationsSlice = createSlice({
  name: 'recommendations',
  initialState,
  reducers: {
    setFilters: (state, action: PayloadAction<RecommendationFilters>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    clearFilters: (state) => {
      state.filters = {};
    },
    setAutoRefresh: (state, action: PayloadAction<boolean>) => {
      state.autoRefresh = action.payload;
    },
    setRefreshInterval: (state, action: PayloadAction<number>) => {
      state.refreshInterval = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch recommendations
      .addCase(fetchRecommendations.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchRecommendations.fulfilled, (state, action) => {
        state.isLoading = false;
        state.recommendations = action.payload;
      })
      .addCase(fetchRecommendations.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message || 'Failed to fetch recommendations';
      })
      // Fetch current recommendation
      .addCase(fetchCurrentRecommendation.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchCurrentRecommendation.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentRecommendation = action.payload;
      })
      .addCase(fetchCurrentRecommendation.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message || 'Failed to fetch current recommendation';
      });
  },
});

export const { 
  setFilters, 
  clearFilters, 
  setAutoRefresh, 
  setRefreshInterval, 
  clearError 
} = recommendationsSlice.actions;
export default recommendationsSlice.reducer;