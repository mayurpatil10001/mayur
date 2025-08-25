import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

export interface Account {
  name: string;
  symbol: string;
  total_trades: number;
  first_trade_date: string;
  last_trade_date: string;
  total_pnl: number;
  best_day_of_week: number | null;
  best_hour_of_day: number | null;
  is_active?: boolean;
}

export interface AccountsState {
  accounts: Account[];
  selectedAccount: Account | null;
  isLoading: boolean;
  error: string | null;
}

const initialState: AccountsState = {
  accounts: [],
  selectedAccount: null,
  isLoading: false,
  error: null,
};

// Async thunks
export const fetchAccounts = createAsyncThunk(
  'accounts/fetchAccounts',
  async () => {
    const response = await fetch('http://localhost:3001/api/v1/accounts/?size=100');
    if (!response.ok) {
      throw new Error('Failed to fetch accounts');
    }
    const result = await response.json();
    return result.data?.items || [];
  }
);

export const fetchAccountDetails = createAsyncThunk(
  'accounts/fetchAccountDetails',
  async (accountName: string) => {
    const response = await fetch(`http://localhost:3001/api/v1/accounts/${accountName}`);
    if (!response.ok) {
      throw new Error('Failed to fetch account details');
    }
    const result = await response.json();
    return result.data || null;
  }
);

const accountsSlice = createSlice({
  name: 'accounts',
  initialState,
  reducers: {
    setSelectedAccount: (state, action: PayloadAction<Account | null>) => {
      state.selectedAccount = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch accounts
      .addCase(fetchAccounts.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchAccounts.fulfilled, (state, action) => {
        state.isLoading = false;
        state.accounts = action.payload;
      })
      .addCase(fetchAccounts.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message || 'Failed to fetch accounts';
      })
      // Fetch account details
      .addCase(fetchAccountDetails.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchAccountDetails.fulfilled, (state, action) => {
        state.isLoading = false;
        state.selectedAccount = action.payload;
      })
      .addCase(fetchAccountDetails.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message || 'Failed to fetch account details';
      });
  },
});

export const { setSelectedAccount, clearError } = accountsSlice.actions;
export default accountsSlice.reducer;