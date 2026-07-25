/**
 * frontend/src/store/store.ts
 */

import { configureStore } from '@reduxjs/toolkit';
import analyticsReducer from './slices/analyticsSlice';
import walkForwardReducer from './slices/walkForwardSlice';

export const store = configureStore({
  reducer: {
    analytics: analyticsReducer,
    walkforward: walkForwardReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({ serializableCheck: { ignoredActions: [] } }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;