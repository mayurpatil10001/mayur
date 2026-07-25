/**
 * frontend/src/types/analytics.ts
 */

export interface PerformanceSnapshot {
  account_name: string | null;
  symbol: string | null;
  date_from: string | null;
  date_to: string | null;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number | null;
  net_pnl: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number | null;
  expectancy: number | null;
  avg_trade_pnl: number | null;
  max_drawdown: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  largest_win: number | null;
  largest_loss: number | null;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
}

export interface TimeBinMetrics {
  account_name: string;
  symbol: string;
  time_slot_ny: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number | null;
  total_pnl: number;
  avg_pnl: number | null;
  expectancy: number | null;
  profit_factor: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number | null;
  wilcoxon_pvalue: number | null;
  bh_fdr_pvalue: number | null;
  is_promoted: boolean;
}

export interface HeatmapData {
  accounts: string[];
  slots: string[];
  matrix: (number | null)[][];
  promoted_mask: boolean[][];
  metric: string;
}

export interface TimeBinGrid {
  resolution: string;
  timezone: string;
  alpha: number;
  total_slots: number;
  promoted_slots: number;
  slots: TimeBinMetrics[];
  heatmap: HeatmapData | null;
}

export interface AccountRanking {
  rank: number;
  account_name: string;
  symbol: string | null;
  trade_count: number;
  net_pnl: number;
  win_rate: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number;
  promoted_slots: number;
}

export interface PnLCurvePoint {
  date: string;
  cumulative_pnl: number;
  daily_pnl: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
  drawdown_pct: number;
}
