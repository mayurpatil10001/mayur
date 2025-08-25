import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { TemporalAnalysis, MonteCarloResults, MonteCarloRequest } from '../../types/api';

interface AnalyticsState {
  // Temporal analysis data by account
  temporalAnalysis: Record<string, TemporalAnalysis>;
  // Monte Carlo results by account
  monteCarloResults: Record<string, MonteCarloResults>;
  // Correlation data
  correlationData: any | null;
  // Loading states
  isLoadingTemporal: boolean;
  isLoadingMonteCarlo: boolean;
  isLoadingCorrelation: boolean;
  // Error states
  temporalError: string | null;
  monteCarloError: string | null;
  correlationError: string | null;
  // Selected accounts for analysis
  selectedAccounts: string[];
  // Date range filter
  dateRange: {
    start_date?: string;
    end_date?: string;
  };
}

const initialState: AnalyticsState = {
  temporalAnalysis: {},
  monteCarloResults: {},
  correlationData: null,
  isLoadingTemporal: false,
  isLoadingMonteCarlo: false,
  isLoadingCorrelation: false,
  temporalError: null,
  monteCarloError: null,
  correlationError: null,
  selectedAccounts: [],
  dateRange: {},
};

// Async thunks
export const fetchTemporalAnalysis = createAsyncThunk(
  'analytics/fetchTemporalAnalysis',
  async ({ accountName, dateRange }: { accountName: string; dateRange?: { start_date?: string; end_date?: string } }) => {
    const queryParams = new URLSearchParams();
    if (dateRange?.start_date) queryParams.append('start_date', dateRange.start_date);
    if (dateRange?.end_date) queryParams.append('end_date', dateRange.end_date);
    
    const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
    const response = await fetch(`http://localhost:8000/api/v1/analytics/temporal/${accountName}${query}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    if (result.status === 'success' && result.data) {
      return { accountName, analysis: result.data };
    }
    throw new Error(result.message || 'Failed to fetch temporal analysis');
  }
);

export const runMonteCarloSimulation = createAsyncThunk(
  'analytics/runMonteCarloSimulation',
  async (request: MonteCarloRequest) => {
    const queryParams = new URLSearchParams();
    queryParams.append('simulations', (request.num_simulations || 10000).toString());
    queryParams.append('time_horizon_days', (request.time_horizon_days || 30).toString());
    queryParams.append('confidence_level', (request.confidence_levels?.[0] || 0.95).toString());
    
    const response = await fetch(`http://localhost:8000/api/v1/analytics/monte-carlo/${request.account_name}?${queryParams.toString()}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    if (result.status === 'success' && result.data) {
      return { accountName: request.account_name, results: result.data };
    }
    throw new Error(result.message || 'Failed to run Monte Carlo simulation');
  }
);

export const fetchAccountCorrelation = createAsyncThunk(
  'analytics/fetchAccountCorrelation',
  async (accountNames: string[]) => {
    const query = `?account_names=${accountNames.join(',')}`;
    const response = await fetch(`http://localhost:8000/api/v1/analytics/correlation${query}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    if (result.status === 'success' && result.data) {
      return result.data;
    }
    throw new Error(result.message || 'Failed to fetch account correlation');
  }
);

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    setSelectedAccounts: (state, action: PayloadAction<string[]>) => {
      state.selectedAccounts = action.payload;
    },
    setDateRange: (state, action: PayloadAction<{ start_date?: string; end_date?: string }>) => {
      state.dateRange = action.payload;
    },
    clearAnalyticsData: (state) => {
      state.temporalAnalysis = {};
      state.monteCarloResults = {};
      state.correlationData = null;
    },
    clearErrors: (state) => {
      state.temporalError = null;
      state.monteCarloError = null;
      state.correlationError = null;
    },
  },
  extraReducers: (builder) => {
    // Temporal analysis
    builder
      .addCase(fetchTemporalAnalysis.pending, (state) => {
        state.isLoadingTemporal = true;
        state.temporalError = null;
      })
      .addCase(fetchTemporalAnalysis.fulfilled, (state, action) => {
        state.isLoadingTemporal = false;
        state.temporalAnalysis[action.payload.accountName] = action.payload.analysis;
      })
      .addCase(fetchTemporalAnalysis.rejected, (state, action) => {
        state.isLoadingTemporal = false;
        state.temporalError = action.error.message || 'Failed to fetch temporal analysis';
      });

    // Monte Carlo simulation
    builder
      .addCase(runMonteCarloSimulation.pending, (state) => {
        state.isLoadingMonteCarlo = true;
        state.monteCarloError = null;
      })
      .addCase(runMonteCarloSimulation.fulfilled, (state, action) => {
        state.isLoadingMonteCarlo = false;
        state.monteCarloResults[action.payload.accountName] = action.payload.results;
      })
      .addCase(runMonteCarloSimulation.rejected, (state, action) => {
        state.isLoadingMonteCarlo = false;
        state.monteCarloError = action.error.message || 'Failed to run Monte Carlo simulation';
      });

    // Account correlation
    builder
      .addCase(fetchAccountCorrelation.pending, (state) => {
        state.isLoadingCorrelation = true;
        state.correlationError = null;
      })
      .addCase(fetchAccountCorrelation.fulfilled, (state, action) => {
        state.isLoadingCorrelation = false;
        state.correlationData = action.payload;
      })
      .addCase(fetchAccountCorrelation.rejected, (state, action) => {
        state.isLoadingCorrelation = false;
        state.correlationError = action.error.message || 'Failed to fetch correlation data';
      });
  },
});

export const { setSelectedAccounts, setDateRange, clearAnalyticsData, clearErrors } = analyticsSlice.actions;
export default analyticsSlice.reducer;