/**
 * frontend/src/types/walkforward.ts
 */

export interface FoldResult {
  fold_index: number;
  is_start: string;
  is_end: string;
  oos_start: string;
  oos_end: string;
  is_trade_count: number;
  is_promoted_slots: string[];
  oos_trade_count: number;
  oos_total_pnl: number;
  oos_win_rate: number | null;
  oos_sharpe: number | null;
  oos_max_drawdown: number | null;
  oos_profit_factor: number | null;
  oos_expectancy: number | null;
}

export interface WalkForwardResult {
  account_name: string;
  symbol: string;
  n_folds: number;
  in_sample_days: number;
  out_of_sample_days: number;
  total_oos_pnl: number;
  avg_oos_sharpe: number | null;
  avg_oos_drawdown: number | null;
  avg_oos_win_rate: number | null;
  avg_oos_profit_factor: number | null;
  is_decay_detected: boolean;
  decay_slope: number | null;
  decay_r_squared: number | null;
  folds: FoldResult[];
}

export interface JobStatus {
  job_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETE' | 'FAILED';
  progress_pct?: number;
  message?: string;
}

export interface MonteCarloResult {
  account_name: string;
  symbol: string;
  n_simulations: number;
  horizon_days: number;
  ruin_threshold: number;
  p05_curve: number[];
  p50_curve: number[];
  p95_curve: number[];
  median_final_pnl: number | null;
  p05_final_pnl: number | null;
  p95_final_pnl: number | null;
  mean_final_pnl: number | null;
  std_final_pnl: number | null;
  positive_outcome_probability: number | null;
  median_max_drawdown: number | null;
  p95_max_drawdown: number | null;
  ruin_probability: number | null;
  max_drawdown_histogram: { bin_start: number; bin_end: number; count: number }[];
}
