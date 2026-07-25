/**
 * frontend/src/store/slices/walkForwardSlice.ts
 */

import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { get, post } from '../../api/client';
import type { WalkForwardResult, JobStatus, MonteCarloResult } from '../../types/walkforward';

interface WalkForwardState {
  currentJobId: string | null;
  jobStatus: JobStatus | null;
  result: WalkForwardResult | null;
  monteCarloResult: MonteCarloResult | null;
  status: 'idle' | 'loading' | 'running' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: WalkForwardState = {
  currentJobId: null,
  jobStatus: null,
  result: null,
  monteCarloResult: null,
  status: 'idle',
  error: null,
};

export const triggerWalkForward = createAsyncThunk(
  'walkforward/trigger',
  async (params: {
    account: string;
    symbol: string;
    in_sample_days?: number;
    out_of_sample_days?: number;
    bh_alpha?: number;
    min_trades_per_slot?: number;
  }) => {
    return post<JobStatus>('/walkforward/run', params);
  },
);

export const pollJobStatus = createAsyncThunk(
  'walkforward/pollStatus',
  async (jobId: string) => {
    return get<JobStatus>(`/walkforward/jobs/${jobId}`);
  },
);

export const fetchWalkForwardResult = createAsyncThunk(
  'walkforward/fetchResult',
  async (jobId: string) => {
    return get<WalkForwardResult>(`/walkforward/results/${jobId}`);
  },
);

export const fetchLatestResult = createAsyncThunk(
  'walkforward/fetchLatest',
  async (params: { account: string; symbol: string }) => {
    return get<WalkForwardResult>('/walkforward/latest', params);
  },
);

export const triggerMonteCarlo = createAsyncThunk(
  'walkforward/monteCarlo',
  async (params: {
    account: string;
    symbol: string;
    n_simulations?: number;
    horizon_days?: number;
    ruin_threshold?: number;
  }) => {
    return post<MonteCarloResult>('/walkforward/monte-carlo', params);
  },
);

const walkForwardSlice = createSlice({
  name: 'walkforward',
  initialState,
  reducers: {
    clearResults(state) {
      state.result = null;
      state.monteCarloResult = null;
      state.jobStatus = null;
      state.currentJobId = null;
      state.status = 'idle';
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(triggerWalkForward.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(triggerWalkForward.fulfilled, (state, action) => {
        state.status = 'running';
        state.currentJobId = action.payload.job_id;
        state.jobStatus = action.payload;
      })
      .addCase(triggerWalkForward.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message ?? 'Failed to start walk-forward job';
      })

      .addCase(pollJobStatus.fulfilled, (state, action) => {
        state.jobStatus = action.payload;
        if (action.payload.status === 'COMPLETE') state.status = 'succeeded';
        if (action.payload.status === 'FAILED') {
          state.status = 'failed';
          state.error = action.payload.message ?? 'Job failed';
        }
      })

      .addCase(fetchWalkForwardResult.fulfilled, (state, action) => {
        state.result = action.payload;
        state.status = 'succeeded';
      })

      .addCase(fetchLatestResult.fulfilled, (state, action) => {
        state.result = action.payload;
        state.status = 'succeeded';
      })

      .addCase(triggerMonteCarlo.fulfilled, (state, action) => {
        state.monteCarloResult = action.payload;
      });
  },
});

export const { clearResults } = walkForwardSlice.actions;
export default walkForwardSlice.reducer;
