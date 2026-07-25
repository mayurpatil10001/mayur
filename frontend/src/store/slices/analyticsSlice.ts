/**
 * frontend/src/store/slices/analyticsSlice.ts
 */

import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { get } from '../../api/client';
import type {
  PerformanceSnapshot,
  TimeBinGrid,
  AccountRanking,
  PnLCurvePoint,
  DrawdownPoint,
} from '../../types/analytics';

export interface AnalyticsFilters {
  account: string | null;
  symbol: string | null;
  dateFrom: string | null;
  dateTo: string | null;
  isPromoted: boolean | null;
}

interface AnalyticsState {
  filters: AnalyticsFilters;
  summary: PerformanceSnapshot | null;
  timeBinGrid: TimeBinGrid | null;
  leaderboard: AccountRanking[];
  pnlCurve: PnLCurvePoint[];
  drawdown: DrawdownPoint[];
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: AnalyticsState = {
  filters: { account: null, symbol: null, dateFrom: null, dateTo: null, isPromoted: null },
  summary: null,
  timeBinGrid: null,
  leaderboard: [],
  pnlCurve: [],
  drawdown: [],
  status: 'idle',
  error: null,
};

function buildParams(filters: AnalyticsFilters): Record<string, string> {
  const p: Record<string, string> = {};
  if (filters.account) p['account'] = filters.account;
  if (filters.symbol) p['symbol'] = filters.symbol;
  if (filters.dateFrom) p['date_from'] = filters.dateFrom;
  if (filters.dateTo) p['date_to'] = filters.dateTo;
  if (filters.isPromoted !== null) p['is_promoted'] = String(filters.isPromoted);
  return p;
}

// ── Async thunks ─────────────────────────────────────────────────────────────

export const fetchSummary = createAsyncThunk(
  'analytics/fetchSummary',
  async (filters: AnalyticsFilters) => {
    return get<PerformanceSnapshot>('/analytics/summary', buildParams(filters));
  },
);

export const fetchTimeBinGrid = createAsyncThunk(
  'analytics/fetchTimeBinGrid',
  async (filters: AnalyticsFilters) => {
    return get<TimeBinGrid>('/analytics/time-slots', {
      ...buildParams(filters),
      include_heatmap: true,
    });
  },
);

export const fetchLeaderboard = createAsyncThunk(
  'analytics/fetchLeaderboard',
  async (filters: AnalyticsFilters) => {
    return get<AccountRanking[]>('/analytics/by-account', {
      ...buildParams(filters),
      sort_by: 'sortino_ratio',
      top_n: 20,
    });
  },
);

export const fetchPnLCurve = createAsyncThunk(
  'analytics/fetchPnLCurve',
  async (filters: AnalyticsFilters) => {
    return get<PnLCurvePoint[]>('/analytics/pnl-curve', buildParams(filters));
  },
);

export const fetchDrawdown = createAsyncThunk(
  'analytics/fetchDrawdown',
  async (filters: AnalyticsFilters) => {
    return get<DrawdownPoint[]>('/analytics/drawdown', buildParams(filters));
  },
);

// ── Slice ─────────────────────────────────────────────────────────────────────

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    setFilters(state, action: PayloadAction<Partial<AnalyticsFilters>>) {
      state.filters = { ...state.filters, ...action.payload };
    },
    resetFilters(state) {
      state.filters = initialState.filters;
    },
    clearError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    const pending = (state: AnalyticsState) => {
      state.status = 'loading';
      state.error = null;
    };
    const failed = (state: AnalyticsState, action: any) => {
      state.status = 'failed';
      state.error = action.error.message ?? 'Unknown error';
    };

    builder
      .addCase(fetchSummary.pending, pending)
      .addCase(fetchSummary.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.summary = action.payload;
      })
      .addCase(fetchSummary.rejected, failed)

      .addCase(fetchTimeBinGrid.pending, pending)
      .addCase(fetchTimeBinGrid.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.timeBinGrid = action.payload;
      })
      .addCase(fetchTimeBinGrid.rejected, failed)

      .addCase(fetchLeaderboard.fulfilled, (state, action) => {
        state.leaderboard = action.payload;
      })

      .addCase(fetchPnLCurve.fulfilled, (state, action) => {
        state.pnlCurve = action.payload;
      })

      .addCase(fetchDrawdown.fulfilled, (state, action) => {
        state.drawdown = action.payload;
      });
  },
});

export const { setFilters, resetFilters, clearError } = analyticsSlice.actions;
export default analyticsSlice.reducer;