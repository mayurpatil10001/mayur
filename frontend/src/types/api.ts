// API Types for Trading Optimization Platform

// Common types
export interface APIResponse<T> {
  status: 'success' | 'error' | 'partial';
  data?: T;
  error?: string;
  message?: string;
}

// Performance Metrics
export interface PerformanceMetrics {
  account_name: string;
  symbol: string;
  period_start: string;
  period_end: string;
  total_return: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe_ratio?: number;
  volatility: number;
  largest_win: number;
  largest_loss: number;
  average_trade_duration?: number;
  total_commission?: number;
  net_profit?: number;
}

// Temporal Analysis
export interface TemporalPerformance {
  total_trades: number;
  winning_trades: number;
  total_pnl: number;
  average_pnl: number;
  win_rate: number;
}

export interface TemporalAnalysis {
  account_name: string;
  symbol: string;
  analysis_period_start: string;
  analysis_period_end: string;
  hourly_performance: Record<string, TemporalPerformance>;
  daily_performance: Record<string, TemporalPerformance>;
  best_trading_hours: number[];
  best_trading_days: number[];
  statistical_significance: {
    hourly_anova?: {
      f_statistic: number;
      p_value: number;
      significant: boolean;
    };
    daily_anova?: {
      f_statistic: number;
      p_value: number;
      significant: boolean;
    };
  };
}

// Recommendations
export enum RecommendationAction {
  TRADE = 'TRADE',
  AVOID = 'AVOID',
  WAIT = 'WAIT'
}

export enum StrategyType {
  STATISTICAL = 'STATISTICAL',
  MACHINE_LEARNING = 'MACHINE_LEARNING',
  MONTE_CARLO = 'MONTE_CARLO',
  COMBINED = 'COMBINED'
}

export interface TradingRecommendation {
  timestamp: string;
  account_name: string;
  symbol: string;
  recommended_action: RecommendationAction;
  confidence_score: number;
  expected_return: number;
  expected_risk: number;
  reasoning: string;
  hour_of_day: number;
  day_of_week: number;
  historical_win_rate: number;
  avg_profit_this_time: number;
  strategy_used: StrategyType;
  risk_metrics: {
    var_95?: number;
    max_drawdown_risk?: number;
    volatility?: number;
  };
}

// Monte Carlo
export interface MonteCarloResults {
  account_name: string;
  num_simulations: number;
  time_horizon_days: number;
  expected_return: number;
  expected_volatility: number;
  var_estimates: Record<string, number>;
  expected_shortfall: Record<string, number>;
  percentiles: Record<string, number>;
  probability_of_loss: number;
  sample_paths?: number[][];
  simulation_metadata: {
    historical_data_points: number;
    simulation_start_date: string;
    simulation_end_date: string;
    convergence_achieved: boolean;
  };
}

// Accounts
export interface Account {
  name: string;
  symbol: string;
  total_trades: number;
  first_trade_date?: string;
  last_trade_date?: string;
  is_active: boolean;
}

// Trades
export interface Trade {
  trade_id: string;
  account_name: string;
  symbol: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  side: 'LONG' | 'SHORT';
  profit_loss: number;
  commission: number;
  duration_minutes: number;
  hour_of_day: number;
  day_of_week: number;
}

// Strategy Comparison
export interface StrategyPerformance {
  total_recommendations: number;
  successful_recommendations: number;
  success_rate: number;
  average_return: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

export interface StrategyComparison {
  comparison_period_start: string;
  comparison_period_end: string;
  strategies: Record<string, StrategyPerformance>;
  best_strategy: StrategyType;
  statistical_tests: Record<string, {
    t_statistic: number;
    p_value: number;
    significant: boolean;
  }>;
  recommendation: string;
}

// Request types
export interface DateRangeFilter {
  start_date?: string;
  end_date?: string;
}

export interface RecommendationRequest {
  target_time?: string;
  account_name?: string;
  symbol?: string;
  account_filter?: string[];
  symbol_filter?: string[];
  strategy?: StrategyType;
  risk_tolerance?: 'LOW' | 'MEDIUM' | 'HIGH';
  min_confidence?: number;
}

export interface MonteCarloRequest {
  account_name: string;
  num_simulations?: number;
  time_horizon_days?: number;
  confidence_levels?: number[];
}