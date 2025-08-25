import { configureStore } from '@reduxjs/toolkit';
import dashboardReducer from './slices/dashboardSlice';
import analyticsReducer from './slices/analyticsSlice';
import recommendationsReducer from './slices/recommendationsSlice';
import accountsReducer from './slices/accountsSlice';

export const store = configureStore({
  reducer: {
    dashboard: dashboardReducer,
    analytics: analyticsReducer,
    recommendations: recommendationsReducer,
    accounts: accountsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;