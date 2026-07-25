/**
 * frontend/src/api/client.ts
 * Axios instance with base URL, auth headers, and error interceptors.
 */

import axios, { AxiosError, type AxiosResponse } from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const API_KEY = import.meta.env.VITE_API_KEY ?? '';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: {
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
  },
});

// ── Request interceptor ───────────────────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  config.headers['X-Request-ID'] = crypto.randomUUID().slice(0, 8);
  return config;
});

// ── Response interceptor ──────────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    const detail = (error.response?.data as any)?.detail ?? error.message;

    if (status === 403) {
      console.error('[API] Unauthorized — check X-API-Key');
    } else if (status === 404) {
      console.warn(`[API] Not found: ${error.config?.url}`);
    } else if (status && status >= 500) {
      console.error(`[API] Server error ${status}: ${detail}`);
    }

    return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)));
  },
);

// ── Typed helper ─────────────────────────────────────────────────────────────
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await apiClient.get<T>(url, { params });
  return res.data;
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = await apiClient.post<T>(url, data);
  return res.data;
}

export default apiClient;
