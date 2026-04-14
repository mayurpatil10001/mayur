// API Service for Trading Optimization Platform

import {
  APIResponse,
  Account,
  PerformanceMetrics,
  TemporalAnalysis,
  TradingRecommendation,
  MonteCarloResults,
  Trade,
  StrategyComparison,
  DateRangeFilter,
  RecommendationRequest,
  MonteCarloRequest
} from '../types/api';

/**
 * Same origin strategy as DiscoveryExplorer: direct :8000 on the page hostname.
 * Avoids CRA proxy-only relative URLs that can break POST (bake-off, correlation) or diverge from Discovery.
 */
export function getApiV1BaseUrl(): string {
  const env = process.env.REACT_APP_API_URL?.replace(/\/$/, '');
  if (env) {
    if (env.endsWith('/api/v1')) return env;
    return `${env}/api/v1`;
  }
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8000/api/v1`;
  }
  return 'http://localhost:8000/api/v1';
}

/** Backtesting router is mounted at /api/backtesting (not under /api/v1). */
export function getApiBacktestingBaseUrl(): string {
  return getApiV1BaseUrl().replace(/\/api\/v1\/?$/, '/api/backtesting');
}

const API_BASE_URL = getApiV1BaseUrl();

class ApiService {
  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    const token = localStorage.getItem('authToken');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<APIResponse<T>> {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Network error' }));
      throw new Error(error.message || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  }

  private buildQueryString(params: Record<string, any>): string {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value.toString());
      }
    });
    return searchParams.toString();
  }

  // Account endpoints
  async getAccounts(): Promise<APIResponse<Account[]>> {
    const response = await fetch(`${API_BASE_URL}/accounts`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<Account[]>(response);
  }

  async getAccount(accountName: string): Promise<APIResponse<Account>> {
    const response = await fetch(`${API_BASE_URL}/accounts/${accountName}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<Account>(response);
  }

  // Analytics endpoints
  async getPerformanceMetrics(
    accountName: string,
    filters?: DateRangeFilter & { symbol?: string }
  ): Promise<APIResponse<PerformanceMetrics>> {
    const query = filters ? `?${this.buildQueryString(filters)}` : '';
    const response = await fetch(`${API_BASE_URL}/analytics/performance/${accountName}${query}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<PerformanceMetrics>(response);
  }

  async getTemporalAnalysis(
    accountName: string,
    filters?: DateRangeFilter
  ): Promise<APIResponse<TemporalAnalysis>> {
    const query = filters ? `?${this.buildQueryString(filters)}` : '';
    const response = await fetch(`${API_BASE_URL}/analytics/temporal/${accountName}${query}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<TemporalAnalysis>(response);
  }

  async runMonteCarloSimulation(
    request: MonteCarloRequest
  ): Promise<APIResponse<MonteCarloResults>> {
    const query = `?simulations=${request.num_simulations || 10000}&time_horizon_days=${request.time_horizon_days || 30}&confidence_level=${request.confidence_levels?.[0] || 0.95}`;
    const response = await fetch(`${API_BASE_URL}/analytics/monte-carlo/${request.account_name}${query}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<MonteCarloResults>(response);
  }

  async getAccountCorrelation(
    accountNames: string[]
  ): Promise<APIResponse<any>> {
    const query = `?account_names=${accountNames.join(',')}`;
    const response = await fetch(`${API_BASE_URL}/analytics/correlation${query}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<any>(response);
  }

  // Recommendation endpoints
  async getCurrentRecommendation(
    request?: RecommendationRequest
  ): Promise<APIResponse<TradingRecommendation[]>> {
    const query = request ? `?${this.buildQueryString(request)}` : '';
    const response = await fetch(`${API_BASE_URL}/recommendations/current${query}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    return this.handleResponse<TradingRecommendation[]>(response);
  }

  async getRecommendationsByAccount(
    accountName: string,
    filters?: DateRangeFilter
  ): Promise<APIResponse<TradingRecommendation[]>> {
    const query = filters ? `?${this.buildQueryString(filters)}` : '';
    const response = await fetch(`${API_BASE_URL}/recommendations/history/${accountName}${query}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<TradingRecommendation[]>(response);
  }

  async compareStrategies(
    accountName: string,
    filters?: DateRangeFilter
  ): Promise<APIResponse<StrategyComparison>> {
    const query = filters ? `?account_name=${accountName}&${this.buildQueryString(filters)}` : `?account_name=${accountName}`;
    const response = await fetch(`${API_BASE_URL}/recommendations/strategies/compare${query}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<StrategyComparison>(response);
  }

  // Trade endpoints
  async getTrades(
    accountName: string,
    filters?: DateRangeFilter & { symbol?: string; limit?: number; offset?: number }
  ): Promise<APIResponse<any>> {
    const queryParams = new URLSearchParams();
    queryParams.append('account_name', accountName);

    if (filters?.limit) queryParams.append('limit', filters.limit.toString());
    if (filters?.offset) queryParams.append('offset', filters.offset.toString());
    if (filters?.symbol) queryParams.append('symbol', filters.symbol);
    if (filters?.start_date) queryParams.append('start_date', filters.start_date);
    if (filters?.end_date) queryParams.append('end_date', filters.end_date);

    const response = await fetch(`${API_BASE_URL}/trades?${queryParams}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<any>(response);
  }

  async getTrade(tradeId: string): Promise<APIResponse<Trade>> {
    const response = await fetch(`${API_BASE_URL}/trades/detail/${tradeId}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<Trade>(response);
  }

  // Auth endpoints
  async login(username: string, password: string): Promise<APIResponse<{ access_token: string }>> {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username,
        password,
      }),
    });

    const result = await this.handleResponse<{ access_token: string }>(response);
    if (result.status === 'success' && result.data?.access_token) {
      localStorage.setItem('authToken', result.data.access_token);
    }
    return result;
  }

  async logout(): Promise<void> {
    localStorage.removeItem('authToken');
  }

  async getCurrentUser(): Promise<APIResponse<any>> {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse<any>(response);
  }
}

export const apiService = new ApiService();