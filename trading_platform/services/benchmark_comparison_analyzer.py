"""
Benchmark Comparison Analyzer

This service provides comprehensive market correlation and benchmark comparison
analysis for time-bin trading strategies, including beta coefficients, alpha metrics,
market neutrality testing, and correlation stability analysis.

Requirements: 11.3, 11.4, 11.5, 11.6
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session
from loguru import logger
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from .market_data_ingestion import MarketDataIngestion, SynchronizedMarketData
from ..models.database import ProcessedTrade
from ..database.connection import get_db_session


@dataclass
class BetaCoefficients:
    """Container for beta coefficient analysis results."""
    spy_beta: float
    qqq_beta: float
    spy_r_squared: float
    qqq_r_squared: float
    spy_correlation: float
    qqq_correlation: float
    sample_size: int
    calculation_period_days: int


@dataclass
class AlphaMetrics:
    """Container for alpha metrics and risk-adjusted returns."""
    spy_alpha_annual: float
    qqq_alpha_annual: float
    spy_alpha_daily: float
    qqq_alpha_daily: float
    jensen_alpha: float
    information_ratio_spy: float
    information_ratio_qqq: float
    tracking_error_spy: float
    tracking_error_qqq: float
    treynor_ratio: float


@dataclass
class MarketNeutralityTest:
    """Container for market neutrality test results."""
    is_market_neutral_spy: bool
    is_market_neutral_qqq: bool
    spy_correlation_p_value: float
    qqq_correlation_p_value: float
    spy_beta_p_value: float
    qqq_beta_p_value: float
    market_neutrality_score: float  # 0-1, higher = more neutral
    independence_test_statistic: float
    independence_p_value: float


@dataclass
class CorrelationStability:
    """Container for time-varying correlation analysis."""
    rolling_correlations_spy: List[float]
    rolling_correlations_qqq: List[float]
    correlation_dates: List[datetime]
    correlation_volatility_spy: float
    correlation_volatility_qqq: float
    correlation_trend_spy: float  # Slope of correlation over time
    correlation_trend_qqq: float
    stability_score_spy: float  # 0-1, higher = more stable
    stability_score_qqq: float
    regime_correlation_spy: Dict[str, float]  # Correlation by market regime
    regime_correlation_qqq: Dict[str, float]


class BenchmarkComparisonAnalyzer:
    """
    Service for comprehensive benchmark comparison and market correlation analysis.
    
    This class provides:
    - Beta coefficient calculations for market correlation analysis
    - Alpha metrics for risk-adjusted return evaluation
    - Market neutrality testing for independence validation
    - Correlation stability analysis for time-varying relationships
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the benchmark comparison analyzer."""
        self.db_session = db_session or get_db_session()
        self.market_data_service = MarketDataIngestion(db_session=self.db_session)
        
        # Risk-free rate assumption (annualized)
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        
        # Statistical significance thresholds
        self.significance_level = 0.05  # 5% significance level
        self.correlation_stability_window = 30  # Days for rolling correlation
    
    def calculate_beta_coefficients(self, account_name: str, 
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None,
                                  time_bin_hour: Optional[int] = None,
                                  time_bin_minute: Optional[int] = None) -> BetaCoefficients:
        """
        Calculate beta coefficients for market correlation analysis.
        
        Beta measures the sensitivity of strategy returns to market movements:
        - Beta = 1: Moves with market
        - Beta > 1: More volatile than market
        - Beta < 1: Less volatile than market
        - Beta = 0: No correlation with market
        
        Args:
            account_name: Account to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter
            time_bin_hour: Optional hour filter for time-bin analysis
            time_bin_minute: Optional minute bin filter (0 or 30)
            
        Returns:
            BetaCoefficients: Beta analysis results
        """
        logger.info(f"Calculating beta coefficients for account {account_name}")
        
        try:
            # Get trade data and market data
            trade_returns, market_returns = self._get_aligned_returns(
                account_name, start_date, end_date, time_bin_hour, time_bin_minute
            )
            
            if len(trade_returns) < 10:
                raise ValueError(f"Insufficient data for beta calculation: {len(trade_returns)} observations")
            
            # Calculate beta coefficients using linear regression
            spy_returns = market_returns['spy_returns']
            qqq_returns = market_returns['qqq_returns']
            
            # SPY Beta calculation
            spy_beta, spy_r_squared, spy_correlation = self._calculate_single_beta(
                trade_returns, spy_returns, "SPY"
            )
            
            # QQQ Beta calculation
            qqq_beta, qqq_r_squared, qqq_correlation = self._calculate_single_beta(
                trade_returns, qqq_returns, "QQQ"
            )
            
            calculation_period = (max(market_returns['dates']) - min(market_returns['dates'])).days
            
            result = BetaCoefficients(
                spy_beta=spy_beta,
                qqq_beta=qqq_beta,
                spy_r_squared=spy_r_squared,
                qqq_r_squared=qqq_r_squared,
                spy_correlation=spy_correlation,
                qqq_correlation=qqq_correlation,
                sample_size=len(trade_returns),
                calculation_period_days=calculation_period
            )
            
            logger.info(f"Beta coefficients calculated: SPY={spy_beta:.3f}, QQQ={qqq_beta:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating beta coefficients: {e}")
            raise ValueError(f"Failed to calculate beta coefficients: {e}")
    
    def calculate_alpha_metrics(self, account_name: str,
                              start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None,
                              time_bin_hour: Optional[int] = None,
                              time_bin_minute: Optional[int] = None) -> AlphaMetrics:
        """
        Calculate alpha metrics for risk-adjusted return evaluation.
        
        Alpha measures the excess return of a strategy compared to a benchmark:
        - Positive alpha: Outperforming benchmark
        - Negative alpha: Underperforming benchmark
        - Zero alpha: Matching benchmark performance
        
        Args:
            account_name: Account to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter
            time_bin_hour: Optional hour filter
            time_bin_minute: Optional minute bin filter
            
        Returns:
            AlphaMetrics: Alpha analysis results
        """
        logger.info(f"Calculating alpha metrics for account {account_name}")
        
        try:
            # Get beta coefficients first
            beta_coeffs = self.calculate_beta_coefficients(
                account_name, start_date, end_date, time_bin_hour, time_bin_minute
            )
            
            # Get aligned returns
            trade_returns, market_returns = self._get_aligned_returns(
                account_name, start_date, end_date, time_bin_hour, time_bin_minute
            )
            
            # Calculate daily risk-free rate
            daily_rf_rate = self.risk_free_rate / 252  # Assume 252 trading days per year
            
            # Calculate alphas using CAPM: Alpha = R_strategy - (Rf + Beta * (R_market - Rf))
            spy_returns = market_returns['spy_returns']
            qqq_returns = market_returns['qqq_returns']
            
            # Daily alpha calculations
            spy_excess_market = np.array(spy_returns) - daily_rf_rate
            qqq_excess_market = np.array(qqq_returns) - daily_rf_rate
            strategy_excess = np.array(trade_returns) - daily_rf_rate
            
            spy_alpha_daily = np.mean(strategy_excess - beta_coeffs.spy_beta * spy_excess_market)
            qqq_alpha_daily = np.mean(strategy_excess - beta_coeffs.qqq_beta * qqq_excess_market)
            
            # Annualized alphas
            spy_alpha_annual = spy_alpha_daily * 252
            qqq_alpha_annual = qqq_alpha_daily * 252
            
            # Jensen's Alpha (risk-adjusted alpha)
            jensen_alpha = np.mean(trade_returns) - (daily_rf_rate + 
                                                   beta_coeffs.spy_beta * np.mean(spy_excess_market))
            
            # Information Ratios (alpha / tracking error)
            tracking_error_spy = np.std(strategy_excess - beta_coeffs.spy_beta * spy_excess_market) * np.sqrt(252)
            tracking_error_qqq = np.std(strategy_excess - beta_coeffs.qqq_beta * qqq_excess_market) * np.sqrt(252)
            
            information_ratio_spy = (spy_alpha_annual / tracking_error_spy) if tracking_error_spy > 0 else 0
            information_ratio_qqq = (qqq_alpha_annual / tracking_error_qqq) if tracking_error_qqq > 0 else 0
            
            # Treynor Ratio (excess return per unit of systematic risk)
            strategy_excess_annual = np.mean(trade_returns) * 252 - self.risk_free_rate
            treynor_ratio = (strategy_excess_annual / beta_coeffs.spy_beta) if beta_coeffs.spy_beta != 0 else 0
            
            result = AlphaMetrics(
                spy_alpha_annual=spy_alpha_annual,
                qqq_alpha_annual=qqq_alpha_annual,
                spy_alpha_daily=spy_alpha_daily,
                qqq_alpha_daily=qqq_alpha_daily,
                jensen_alpha=jensen_alpha,
                information_ratio_spy=information_ratio_spy,
                information_ratio_qqq=information_ratio_qqq,
                tracking_error_spy=tracking_error_spy,
                tracking_error_qqq=tracking_error_qqq,
                treynor_ratio=treynor_ratio
            )
            
            logger.info(f"Alpha metrics calculated: SPY α={spy_alpha_annual:.4f}, QQQ α={qqq_alpha_annual:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating alpha metrics: {e}")
            raise ValueError(f"Failed to calculate alpha metrics: {e}")
    
    def test_market_neutrality(self, account_name: str,
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None,
                             time_bin_hour: Optional[int] = None,
                             time_bin_minute: Optional[int] = None) -> MarketNeutralityTest:
        """
        Test market neutrality for independence validation.
        
        Tests whether the trading strategy is truly independent of market movements:
        - Correlation significance tests
        - Beta significance tests  
        - Independence statistical tests
        
        Args:
            account_name: Account to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter
            time_bin_hour: Optional hour filter
            time_bin_minute: Optional minute bin filter
            
        Returns:
            MarketNeutralityTest: Market neutrality test results
        """
        logger.info(f"Testing market neutrality for account {account_name}")
        
        try:
            # Get beta coefficients and returns
            beta_coeffs = self.calculate_beta_coefficients(
                account_name, start_date, end_date, time_bin_hour, time_bin_minute
            )
            
            trade_returns, market_returns = self._get_aligned_returns(
                account_name, start_date, end_date, time_bin_hour, time_bin_minute
            )
            
            n_obs = len(trade_returns)
            spy_returns = market_returns['spy_returns']
            qqq_returns = market_returns['qqq_returns']
            
            # Test correlation significance
            spy_corr_stat, spy_corr_p = stats.pearsonr(trade_returns, spy_returns)
            qqq_corr_stat, qqq_corr_p = stats.pearsonr(trade_returns, qqq_returns)
            
            # Test beta significance using t-test
            # H0: Beta = 0 (no market sensitivity)
            spy_beta_t_stat = beta_coeffs.spy_beta * np.sqrt(n_obs - 2) / np.sqrt(1 - beta_coeffs.spy_r_squared)
            qqq_beta_t_stat = beta_coeffs.qqq_beta * np.sqrt(n_obs - 2) / np.sqrt(1 - beta_coeffs.qqq_r_squared)
            
            spy_beta_p = 2 * (1 - stats.t.cdf(abs(spy_beta_t_stat), n_obs - 2))
            qqq_beta_p = 2 * (1 - stats.t.cdf(abs(qqq_beta_t_stat), n_obs - 2))
            
            # Market neutrality determination
            is_neutral_spy = (spy_corr_p > self.significance_level and 
                            spy_beta_p > self.significance_level)
            is_neutral_qqq = (qqq_corr_p > self.significance_level and 
                            qqq_beta_p > self.significance_level)
            
            # Independence test using Ljung-Box test on residuals
            residuals = np.array(trade_returns) - (beta_coeffs.spy_beta * np.array(spy_returns))
            
            # Simple independence test using runs test approximation
            median_residual = np.median(residuals)
            runs = 0
            for i in range(1, len(residuals)):
                if (residuals[i] > median_residual) != (residuals[i-1] > median_residual):
                    runs += 1
            
            n1 = np.sum(residuals > median_residual)
            n2 = len(residuals) - n1
            
            if n1 > 0 and n2 > 0:
                expected_runs = (2 * n1 * n2) / (n1 + n2) + 1
                var_runs = (2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
                
                if var_runs > 0:
                    independence_test_stat = (runs - expected_runs) / np.sqrt(var_runs)
                    independence_p = 2 * (1 - stats.norm.cdf(abs(independence_test_stat)))
                else:
                    independence_test_stat = 0
                    independence_p = 1.0
            else:
                independence_test_stat = 0
                independence_p = 1.0
            
            # Calculate overall market neutrality score (0-1)
            neutrality_components = [
                spy_corr_p / max(spy_corr_p, self.significance_level),
                qqq_corr_p / max(qqq_corr_p, self.significance_level),
                spy_beta_p / max(spy_beta_p, self.significance_level),
                qqq_beta_p / max(qqq_beta_p, self.significance_level),
                independence_p / max(independence_p, self.significance_level)
            ]
            market_neutrality_score = min(np.mean(neutrality_components), 1.0)
            
            result = MarketNeutralityTest(
                is_market_neutral_spy=is_neutral_spy,
                is_market_neutral_qqq=is_neutral_qqq,
                spy_correlation_p_value=spy_corr_p,
                qqq_correlation_p_value=qqq_corr_p,
                spy_beta_p_value=spy_beta_p,
                qqq_beta_p_value=qqq_beta_p,
                market_neutrality_score=market_neutrality_score,
                independence_test_statistic=independence_test_stat,
                independence_p_value=independence_p
            )
            
            logger.info(f"Market neutrality test completed: Score={market_neutrality_score:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Error testing market neutrality: {e}")
            raise ValueError(f"Failed to test market neutrality: {e}")
    
    def calculate_correlation_stability(self, account_name: str,
                                      start_date: Optional[datetime] = None,
                                      end_date: Optional[datetime] = None,
                                      time_bin_hour: Optional[int] = None,
                                      time_bin_minute: Optional[int] = None) -> CorrelationStability:
        """
        Calculate correlation stability for time-varying analysis.
        
        Analyzes how correlations change over time to assess strategy stability:
        - Rolling correlations with configurable window
        - Correlation volatility and trends
        - Regime-specific correlations
        - Stability scoring
        
        Args:
            account_name: Account to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter
            time_bin_hour: Optional hour filter
            time_bin_minute: Optional minute bin filter
            
        Returns:
            CorrelationStability: Time-varying correlation analysis
        """
        logger.info(f"Calculating correlation stability for account {account_name}")
        
        try:
            # Get aligned returns with dates
            trade_returns, market_returns = self._get_aligned_returns(
                account_name, start_date, end_date, time_bin_hour, time_bin_minute
            )
            
            dates = market_returns['dates']
            spy_returns = market_returns['spy_returns']
            qqq_returns = market_returns['qqq_returns']
            vix_levels = market_returns.get('vix_levels', [])
            
            if len(trade_returns) < self.correlation_stability_window * 2:
                raise ValueError(f"Insufficient data for stability analysis: need at least {self.correlation_stability_window * 2} observations")
            
            # Calculate rolling correlations
            rolling_corr_spy = []
            rolling_corr_qqq = []
            rolling_dates = []
            
            for i in range(self.correlation_stability_window, len(trade_returns)):
                window_start = i - self.correlation_stability_window
                window_end = i
                
                trade_window = trade_returns[window_start:window_end]
                spy_window = spy_returns[window_start:window_end]
                qqq_window = qqq_returns[window_start:window_end]
                
                if len(trade_window) >= 10:  # Minimum for reliable correlation
                    spy_corr, _ = stats.pearsonr(trade_window, spy_window)
                    qqq_corr, _ = stats.pearsonr(trade_window, qqq_window)
                    
                    rolling_corr_spy.append(spy_corr)
                    rolling_corr_qqq.append(qqq_corr)
                    rolling_dates.append(dates[window_end - 1])
            
            if len(rolling_corr_spy) < 5:
                raise ValueError("Insufficient data for rolling correlation analysis")
            
            # Calculate correlation volatility (standard deviation of rolling correlations)
            corr_vol_spy = np.std(rolling_corr_spy)
            corr_vol_qqq = np.std(rolling_corr_qqq)
            
            # Calculate correlation trends (slope over time)
            time_indices = np.arange(len(rolling_corr_spy))
            spy_trend_slope, _, _, _, _ = stats.linregress(time_indices, rolling_corr_spy)
            qqq_trend_slope, _, _, _, _ = stats.linregress(time_indices, rolling_corr_qqq)
            
            # Calculate stability scores (higher = more stable)
            # Penalize high volatility and strong trends
            max_volatility = 0.3  # Maximum acceptable correlation volatility
            stability_score_spy = max(0, 1 - (corr_vol_spy / max_volatility) - abs(spy_trend_slope) * 10)
            stability_score_qqq = max(0, 1 - (corr_vol_qqq / max_volatility) - abs(qqq_trend_slope) * 10)
            
            # Regime-specific correlations (if VIX data available)
            regime_corr_spy = {}
            regime_corr_qqq = {}
            
            if vix_levels and len(vix_levels) == len(trade_returns):
                # Define regimes
                low_regime_mask = np.array(vix_levels) < 15
                med_regime_mask = (np.array(vix_levels) >= 15) & (np.array(vix_levels) <= 25)
                high_regime_mask = np.array(vix_levels) > 25
                
                # Calculate regime-specific correlations
                for regime_name, mask in [("Low", low_regime_mask), ("Medium", med_regime_mask), ("High", high_regime_mask)]:
                    if np.sum(mask) >= 10:  # Minimum observations for correlation
                        regime_trade_returns = np.array(trade_returns)[mask]
                        regime_spy_returns = np.array(spy_returns)[mask]
                        regime_qqq_returns = np.array(qqq_returns)[mask]
                        
                        regime_corr_spy[regime_name], _ = stats.pearsonr(regime_trade_returns, regime_spy_returns)
                        regime_corr_qqq[regime_name], _ = stats.pearsonr(regime_trade_returns, regime_qqq_returns)
            
            result = CorrelationStability(
                rolling_correlations_spy=rolling_corr_spy,
                rolling_correlations_qqq=rolling_corr_qqq,
                correlation_dates=rolling_dates,
                correlation_volatility_spy=corr_vol_spy,
                correlation_volatility_qqq=corr_vol_qqq,
                correlation_trend_spy=spy_trend_slope,
                correlation_trend_qqq=qqq_trend_slope,
                stability_score_spy=stability_score_spy,
                stability_score_qqq=stability_score_qqq,
                regime_correlation_spy=regime_corr_spy,
                regime_correlation_qqq=regime_corr_qqq
            )
            
            logger.info(f"Correlation stability calculated: SPY stability={stability_score_spy:.3f}, QQQ stability={stability_score_qqq:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating correlation stability: {e}")
            raise ValueError(f"Failed to calculate correlation stability: {e}")
    
    def _get_aligned_returns(self, account_name: str, start_date: Optional[datetime], 
                           end_date: Optional[datetime], time_bin_hour: Optional[int],
                           time_bin_minute: Optional[int]) -> Tuple[List[float], Dict]:
        """
        Get aligned trade returns and market returns for analysis.
        
        Returns:
            Tuple[List[float], Dict]: Trade returns and market returns dict
        """
        try:
            # Get trade data
            query = self.db_session.query(ProcessedTrade).filter(
                ProcessedTrade.account_name == account_name
            )
            
            if start_date:
                query = query.filter(ProcessedTrade.entry_time >= start_date)
            if end_date:
                query = query.filter(ProcessedTrade.entry_time <= end_date)
            if time_bin_hour is not None:
                query = query.filter(ProcessedTrade.entry_time.extract('hour') == time_bin_hour)
            if time_bin_minute is not None:
                minute_bin = time_bin_minute
                query = query.filter(
                    ((ProcessedTrade.entry_time.extract('minute') >= minute_bin) & 
                     (ProcessedTrade.entry_time.extract('minute') < minute_bin + 30))
                )
            
            trades = query.order_by(ProcessedTrade.entry_time).all()
            
            if len(trades) == 0:
                raise ValueError("No trades found for the specified criteria")
            
            # Group trades by date and calculate daily returns
            daily_trades = {}
            for trade in trades:
                trade_date = trade.entry_time.date()
                if trade_date not in daily_trades:
                    daily_trades[trade_date] = []
                daily_trades[trade_date].append(trade.pnl)
            
            # Calculate daily trade returns (sum of P&L per day)
            trade_dates = sorted(daily_trades.keys())
            trade_returns = [sum(daily_trades[date]) for date in trade_dates]
            
            # Get market data for the same period
            min_date = datetime.combine(min(trade_dates), datetime.min.time())
            max_date = datetime.combine(max(trade_dates), datetime.min.time())
            
            # Synchronize market data
            trade_timestamps = [datetime.combine(date, datetime.min.time()) for date in trade_dates]
            sync_data = self.market_data_service.synchronize_market_data(trade_timestamps)
            
            # Extract market returns
            spy_returns = []
            qqq_returns = []
            vix_levels = []
            aligned_dates = []
            
            for date in trade_dates:
                timestamp = datetime.combine(date, datetime.min.time())
                if timestamp in sync_data.spy_data and timestamp in sync_data.qqq_data:
                    # Calculate daily returns (using price changes, or just use as levels for correlation)
                    spy_returns.append(sync_data.spy_data[timestamp])
                    qqq_returns.append(sync_data.qqq_data[timestamp])
                    if timestamp in sync_data.vix_data:
                        vix_levels.append(sync_data.vix_data[timestamp])
                    aligned_dates.append(timestamp)
            
            # Calculate percentage returns for market data
            if len(spy_returns) > 1:
                spy_pct_returns = [(spy_returns[i] - spy_returns[i-1]) / spy_returns[i-1] 
                                 for i in range(1, len(spy_returns))]
                qqq_pct_returns = [(qqq_returns[i] - qqq_returns[i-1]) / qqq_returns[i-1] 
                                 for i in range(1, len(qqq_returns))]
                
                # Align with trade returns (remove first day if calculating returns)
                trade_returns = trade_returns[1:]
                aligned_dates = aligned_dates[1:]
                if vix_levels:
                    vix_levels = vix_levels[1:]
                
                spy_returns = spy_pct_returns
                qqq_returns = qqq_pct_returns
            
            market_returns = {
                'spy_returns': spy_returns,
                'qqq_returns': qqq_returns,
                'dates': aligned_dates,
                'vix_levels': vix_levels
            }
            
            return trade_returns, market_returns
            
        except Exception as e:
            logger.error(f"Error getting aligned returns: {e}")
            raise ValueError(f"Failed to get aligned returns: {e}")
    
    def _calculate_single_beta(self, trade_returns: List[float], 
                             market_returns: List[float], 
                             benchmark_name: str) -> Tuple[float, float, float]:
        """
        Calculate beta coefficient for a single benchmark using linear regression.
        
        Returns:
            Tuple[float, float, float]: Beta, R-squared, correlation
        """
        try:
            X = np.array(market_returns).reshape(-1, 1)
            y = np.array(trade_returns)
            
            # Fit linear regression
            model = LinearRegression()
            model.fit(X, y)
            
            beta = model.coef_[0]
            
            # Calculate R-squared
            y_pred = model.predict(X)
            r_squared = r2_score(y, y_pred)
            
            # Calculate correlation
            correlation, _ = stats.pearsonr(trade_returns, market_returns)
            
            logger.debug(f"{benchmark_name} beta calculation: β={beta:.4f}, R²={r_squared:.4f}, ρ={correlation:.4f}")
            
            return beta, r_squared, correlation
            
        except Exception as e:
            logger.error(f"Error calculating {benchmark_name} beta: {e}")
            return 0.0, 0.0, 0.0