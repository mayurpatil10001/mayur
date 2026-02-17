#!/usr/bin/env python3
"""
Advanced Recommendation Engine Integration

This script integrates all the sophisticated analytics components built in the 
advanced trading analytics system into an intelligent recommendation engine.

Components to integrate:
- TimeBinAnalyzer (Tasks 1-4)
- Monte Carlo Risk Engine (Tasks 9-11) 
- Walk-Forward Analysis (Tasks 12-14)
- Market Correlation Analysis (Tasks 5-8)
- VIX Regime Analysis (Tasks 6, 17)
- Statistical Testing Engine (Task 3)

Requirements: 1.6, 8.1-8.6, 12.1-12.6
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Import all the advanced analytics components
from trading_platform.services.time_bin_analyzer import TimeBinAnalyzer, TimeBin
from trading_platform.services.statistical_testing_engine import StatisticalTestingEngine
from trading_platform.services.monte_carlo.time_bin_scenario_generator import TimeBinScenarioGenerator
from trading_platform.services.monte_carlo.risk_metrics_calculator import RiskMetricsCalculator
from trading_platform.services.walk_forward.out_of_sample_validator import OutOfSampleValidator
from trading_platform.services.walk_forward.performance_decay_tracker import PerformanceDecayTracker
from trading_platform.services.market_data_ingestion import MarketDataIngestion
from trading_platform.services.benchmark_comparison_analyzer import BenchmarkComparisonAnalyzer
from trading_platform.services.vix_regime_analyzer import VIXDataIntegration

logger = logging.getLogger(__name__)

class RecommendationConfidence(Enum):
    """Confidence levels for recommendations"""
    VERY_HIGH = "VERY_HIGH"  # >90% statistical confidence
    HIGH = "HIGH"            # 80-90% confidence  
    MEDIUM = "MEDIUM"        # 60-80% confidence
    LOW = "LOW"              # 40-60% confidence
    VERY_LOW = "VERY_LOW"    # <40% confidence

class RecommendationAction(Enum):
    """Recommended actions"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY" 
    HOLD = "HOLD"
    AVOID = "AVOID"
    STRONG_AVOID = "STRONG_AVOID"

@dataclass
class AdvancedRecommendation:
    """Advanced recommendation with full analytics integration"""
    timestamp: datetime
    time_bin: TimeBin
    action: RecommendationAction
    confidence: RecommendationConfidence
    
    # Core metrics
    expected_return: float
    probability_of_profit: float
    risk_score: float
    
    # Statistical validation
    statistical_significance: bool
    p_value: float
    confidence_interval: Tuple[float, float]
    sample_size: int
    
    # Monte Carlo analysis
    var_95: float
    expected_shortfall: float
    worst_case_scenario: float
    best_case_scenario: float
    
    # Walk-forward validation
    out_of_sample_performance: float
    robustness_score: float
    performance_decay_rate: float
    
    # Market correlation
    market_correlation: float
    beta_coefficient: float
    alpha_generation: float
    market_neutrality: bool
    
    # VIX regime analysis
    current_vix_regime: str
    regime_performance: Dict[str, float]
    regime_preference: str
    
    # Reasoning and alerts
    reasoning: str
    alerts: List[str]
    recommendations: List[str]

class AdvancedRecommendationEngine:
    """
    Intelligent recommendation engine integrating all advanced analytics
    """
    
    def __init__(self, db_session):
        self.db_session = db_session
        
        # Initialize all analytics components
        self.time_bin_analyzer = TimeBinAnalyzer(db_session)
        self.statistical_engine = StatisticalTestingEngine()
        self.scenario_generator = TimeBinScenarioGenerator(db_session)
        self.risk_calculator = RiskMetricsCalculator()
        self.walk_forward_validator = OutOfSampleValidator(db_session)
        self.decay_tracker = PerformanceDecayTracker(db_session)
        self.market_data_service = MarketDataIngestion(db_session)
        self.benchmark_analyzer = BenchmarkComparisonAnalyzer(db_session)
        self.vix_analyzer = VIXDataIntegration(db_session)
        
        logger.info("Advanced Recommendation Engine initialized with all analytics components")
    
    async def generate_intelligent_recommendations(
        self, 
        current_time: Optional[datetime] = None,
        accounts: Optional[List[str]] = None,
        min_confidence: float = 0.6
    ) -> List[AdvancedRecommendation]:
        """
        Generate intelligent recommendations using all advanced analytics
        
        This is the main integration point that combines:
        1. Time-bin analysis with statistical significance
        2. Monte Carlo risk assessment  
        3. Walk-forward validation
        4. Market correlation analysis
        5. VIX regime analysis
        """
        if current_time is None:
            current_time = datetime.now()
            
        logger.info(f"Generating advanced recommendations for {current_time}")
        
        recommendations = []
        
        # Get current market conditions
        market_conditions = await self._get_current_market_conditions(current_time)
        
        # Get all potential time-bins for current time window
        current_time_bins = self._get_current_time_bins(current_time, accounts)
        
        for time_bin in current_time_bins:
            try:
                recommendation = await self._analyze_time_bin_comprehensive(
                    time_bin, current_time, market_conditions
                )
                
                if recommendation and recommendation.confidence.value in ['HIGH', 'VERY_HIGH']:
                    if self._meets_confidence_threshold(recommendation, min_confidence):
                        recommendations.append(recommendation)
                        
            except Exception as e:
                logger.error(f"Error analyzing time-bin {time_bin}: {e}")
                continue
        
        # Rank recommendations by composite score
        recommendations = self._rank_recommendations(recommendations)
        
        logger.info(f"Generated {len(recommendations)} high-confidence recommendations")
        return recommendations
    
    async def _analyze_time_bin_comprehensive(
        self, 
        time_bin: TimeBin, 
        current_time: datetime,
        market_conditions: Dict
    ) -> Optional[AdvancedRecommendation]:
        """
        Comprehensive analysis of a time-bin using all analytics components
        """
        
        time_bin_metrics = self.time_bin_analyzer.calculate_time_bin_metrics(
            self.time_bin_analyzer.get_time_bin_trades(time_bin)
        )
        
        if not time_bin_metrics or time_bin_metrics.total_trades < 30:
            return None  # Insufficient data
            
        # Statistical significance testing
        significance_test = self.time_bin_analyzer.test_statistical_significance(time_bin_metrics)
        if not significance_test.is_significant:
            return None  # Not statistically significant
        
        # 2. Monte Carlo risk assessment
        scenarios = self.scenario_generator.generate_bootstrap_scenarios(
            time_bin, scenario_count=1000
        )
        
        risk_metrics = self.risk_calculator.calculate_var(scenarios.scenarios, [0.95])
        expected_shortfall = self.risk_calculator.calculate_expected_shortfall(scenarios.scenarios, 0.95)
        probability_metrics = self.risk_calculator.probability_of_profit(scenarios.scenarios)
        
        # 3. Walk-forward validation
        validation_result = self.walk_forward_validator.anchored_walk_forward(
            time_bin, train_periods=5
        )
        
        decay_analysis = self.decay_tracker.detect_strategy_degradation(
            time_bin, lookback_days=30
        )
        
        # 4. Market correlation analysis
        correlation_analysis = self.benchmark_analyzer.calculate_beta_coefficients(
            time_bin, benchmark='SPY'
        )
        
        alpha_metrics = self.benchmark_analyzer.calculate_alpha_metrics(
            time_bin, benchmark='SPY'
        )
        
        neutrality_test = self.benchmark_analyzer.test_market_neutrality(
            time_bin, benchmark='SPY'
        )
        
        # 5. VIX regime analysis
        current_vix = market_conditions.get('current_vix', 20.0)
        regime_analysis = self.vix_analyzer.analyze_regime_performance(
            time_bin, current_vix
        )
        
        # 6. Generate recommendation based on all analytics
        return self._synthesize_recommendation(
            time_bin=time_bin,
            current_time=current_time,
            time_bin_metrics=time_bin_metrics,
            significance_test=significance_test,
            risk_metrics=risk_metrics,
            expected_shortfall=expected_shortfall,
            probability_metrics=probability_metrics,
            validation_result=validation_result,
            decay_analysis=decay_analysis,
            correlation_analysis=correlation_analysis,
            alpha_metrics=alpha_metrics,
            neutrality_test=neutrality_test,
            regime_analysis=regime_analysis,
            market_conditions=market_conditions
        )
    
    def _synthesize_recommendation(self, **analytics_data) -> AdvancedRecommendation:
        """
        Synthesize all analytics into a single intelligent recommendation
        """
        time_bin = analytics_data['time_bin']
        time_bin_metrics = analytics_data['time_bin_metrics']
        risk_metrics = analytics_data['risk_metrics']
        probability_metrics = analytics_data['probability_metrics']
        validation_result = analytics_data['validation_result']
        regime_analysis = analytics_data['regime_analysis']
        
        # Calculate composite confidence score
        confidence_score = self._calculate_confidence_score(analytics_data)
        confidence = self._map_confidence_level(confidence_score)
        
        # Determine recommendation action
        action = self._determine_action(analytics_data)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(analytics_data)
        
        # Generate alerts and recommendations
        alerts = self._generate_alerts(analytics_data)
        recommendations = self._generate_recommendations(analytics_data)
        
        return AdvancedRecommendation(
            timestamp=analytics_data['current_time'],
            time_bin=time_bin,
            action=action,
            confidence=confidence,
            
            # Core metrics
            expected_return=time_bin_metrics.average_pnl,
            probability_of_profit=probability_metrics.probability_of_profit,
            risk_score=min(abs(risk_metrics.var_95) / 1000, 1.0),
            
            # Statistical validation
            statistical_significance=analytics_data['significance_test'].is_significant,
            p_value=analytics_data['significance_test'].p_value,
            confidence_interval=(time_bin_metrics.confidence_interval_95[0], 
                               time_bin_metrics.confidence_interval_95[1]),
            sample_size=time_bin_metrics.total_trades,
            
            # Monte Carlo analysis
            var_95=risk_metrics.var_95,
            expected_shortfall=analytics_data['expected_shortfall'].expected_shortfall,
            worst_case_scenario=min(s.outcome for s in analytics_data['risk_metrics'].scenarios),
            best_case_scenario=max(s.outcome for s in analytics_data['risk_metrics'].scenarios),
            
            # Walk-forward validation
            out_of_sample_performance=validation_result.robustness_score,
            robustness_score=validation_result.robustness_score,
            performance_decay_rate=analytics_data['decay_analysis'].degradation_score,
            
            # Market correlation
            market_correlation=analytics_data['correlation_analysis'].spy_correlation,
            beta_coefficient=analytics_data['correlation_analysis'].beta_spy,
            alpha_generation=analytics_data['alpha_metrics'].alpha_spy,
            market_neutrality=analytics_data['neutrality_test'].is_market_neutral,
            
            # VIX regime analysis
            current_vix_regime=regime_analysis.current_regime,
            regime_performance=regime_analysis.regime_performance,
            regime_preference=regime_analysis.best_regime,
            
            # Reasoning and alerts
            reasoning=reasoning,
            alerts=alerts,
            recommendations=recommendations
        )
    
    def _calculate_confidence_score(self, analytics_data) -> float:
        """Calculate composite confidence score from all analytics"""
        scores = []
        
        # Statistical significance (30% weight)
        if analytics_data['significance_test'].is_significant:
            scores.append(0.3 * (1 - analytics_data['significance_test'].p_value))
        
        # Sample size adequacy (20% weight)
        sample_size = analytics_data['time_bin_metrics'].total_trades
        sample_score = min(sample_size / 100, 1.0)  # 100+ trades = full score
        scores.append(0.2 * sample_score)
        
        # Walk-forward robustness (25% weight)
        robustness = analytics_data['validation_result'].robustness_score
        scores.append(0.25 * robustness)
        
        # Performance consistency (15% weight)
        win_rate = analytics_data['time_bin_metrics'].win_rate
        consistency_score = min(win_rate / 0.6, 1.0)  # 60%+ win rate = full score
        scores.append(0.15 * consistency_score)
        
        # Risk-adjusted returns (10% weight)
        sharpe = analytics_data['time_bin_metrics'].sharpe_ratio or 0
        risk_score = min(max(sharpe, 0) / 2.0, 1.0)  # Sharpe 2.0+ = full score
        scores.append(0.1 * risk_score)
        
        return sum(scores)
    
    def _map_confidence_level(self, score: float) -> RecommendationConfidence:
        """Map confidence score to confidence level"""
        if score >= 0.9:
            return RecommendationConfidence.VERY_HIGH
        elif score >= 0.8:
            return RecommendationConfidence.HIGH
        elif score >= 0.6:
            return RecommendationConfidence.MEDIUM
        elif score >= 0.4:
            return RecommendationConfidence.LOW
        else:
            return RecommendationConfidence.VERY_LOW
    
    def _determine_action(self, analytics_data) -> RecommendationAction:
        """Determine recommendation action based on analytics"""
        metrics = analytics_data['time_bin_metrics']
        probability = analytics_data['probability_metrics']
        decay = analytics_data['decay_analysis']
        
        # Strong positive signals
        if (metrics.average_pnl > 50 and 
            metrics.win_rate > 0.65 and 
            probability.probability_of_profit > 0.7 and
            decay.degradation_score < 0.2):
            return RecommendationAction.STRONG_BUY
        
        # Positive signals
        elif (metrics.average_pnl > 20 and 
              metrics.win_rate > 0.55 and 
              probability.probability_of_profit > 0.6):
            return RecommendationAction.BUY
        
        # Negative signals
        elif (metrics.average_pnl < -20 or 
              metrics.win_rate < 0.45 or 
              decay.degradation_score > 0.7):
            return RecommendationAction.STRONG_AVOID
        
        # Weak negative signals
        elif (metrics.average_pnl < 0 or 
              metrics.win_rate < 0.5):
            return RecommendationAction.AVOID
        
        else:
            return RecommendationAction.HOLD
    
    def _generate_reasoning(self, analytics_data) -> str:
        """Generate human-readable reasoning for the recommendation"""
        metrics = analytics_data['time_bin_metrics']
        regime = analytics_data['regime_analysis']
        
        reasoning_parts = []
        
        # Performance summary
        reasoning_parts.append(
            f"Historical performance: {metrics.total_trades} trades, "
            f"{metrics.win_rate:.1%} win rate, "
            f"${metrics.average_pnl:.2f} average P&L"
        )
        
        # Statistical significance
        if analytics_data['significance_test'].is_significant:
            reasoning_parts.append(
                f"Statistically significant performance (p-value: {analytics_data['significance_test'].p_value:.3f})"
            )
        
        # VIX regime context
        reasoning_parts.append(
            f"Current VIX regime: {regime.current_regime}, "
            f"performs best in {regime.best_regime} volatility"
        )
        
        # Risk assessment
        prob_profit = analytics_data['probability_metrics'].probability_of_profit
        reasoning_parts.append(f"{prob_profit:.1%} probability of profit based on Monte Carlo analysis")
        
        return ". ".join(reasoning_parts)
    
    def _generate_alerts(self, analytics_data) -> List[str]:
        """Generate alerts based on analytics"""
        alerts = []
        
        decay = analytics_data['decay_analysis']
        if decay.degradation_score > 0.5:
            alerts.append("⚠️ Performance degradation detected - consider reduced position size")
        
        sample_size = analytics_data['time_bin_metrics'].total_trades
        if sample_size < 50:
            alerts.append("⚠️ Limited sample size - recommendation has lower confidence")
        
        if not analytics_data['neutrality_test'].is_market_neutral:
            alerts.append("📈 Strategy is correlated with market - consider market conditions")
        
        return alerts
    
    def _generate_recommendations(self, analytics_data) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        regime = analytics_data['regime_analysis']
        if regime.current_regime != regime.best_regime:
            recommendations.append(
                f"💡 Strategy performs better in {regime.best_regime} VIX regime - "
                f"consider waiting for regime change"
            )
        
        validation = analytics_data['validation_result']
        if validation.robustness_score < 0.6:
            recommendations.append("💡 Consider additional validation before increasing position size")
        
        return recommendations
    
    async def _get_current_market_conditions(self, current_time: datetime) -> Dict:
        """Get current market conditions for context"""
        try:
            # Get current VIX level
            vix_data = self.vix_analyzer.fetch_vix_data(
                current_time - timedelta(days=1), current_time
            )
            current_vix = vix_data.data.iloc[-1]['Close'] if not vix_data.data.empty else 20.0
            
            # Get SPY/QQQ levels
            spy_data = self.market_data_service.fetch_spy_data(
                current_time - timedelta(days=1), current_time
            )
            current_spy = spy_data.data.iloc[-1]['Close'] if not spy_data.data.empty else 400.0
            
            # Determine VIX regime
            if current_vix < 15.0:
                vix_regime = 'LOW'
            elif current_vix <= 25.0:
                vix_regime = 'MEDIUM'
            else:
                vix_regime = 'HIGH'
                
            return {
                'current_vix': current_vix,
                'current_spy': current_spy,
                'vix_regime': vix_regime,
                'timestamp': current_time
            }
        except Exception as e:
            logger.error(f"Error getting market conditions: {e}")
            return {
                'current_vix': 20.0,
                'current_spy': 400.0,
                'vix_regime': 'MEDIUM',
                'timestamp': current_time
            }
    
    def _get_current_time_bins(self, current_time: datetime, accounts: Optional[List[str]]) -> List[TimeBin]:
        """Get time-bins for current time window"""
        current_hour = current_time.hour
        current_minute_bin = 0 if current_time.minute < 30 else 30
        current_day_of_week = current_time.weekday()
        
        if accounts is None:
            # Get all accounts from database
            from trading_platform.models.database import Account
            accounts = [a.name for a in self.db_session.query(Account.name).all()]
        
        time_bins = []
        for account in accounts:
            time_bin = TimeBin(
                account_name=account,
                hour=current_hour,
                minute_bin=current_minute_bin,
                day_of_week=current_day_of_week
            )
            time_bins.append(time_bin)
        
        return time_bins
    
    def _meets_confidence_threshold(self, recommendation: AdvancedRecommendation, min_confidence: float) -> bool:
        """Check if recommendation meets confidence threshold"""
        confidence_scores = {
            RecommendationConfidence.VERY_HIGH: 0.95,
            RecommendationConfidence.HIGH: 0.85,
            RecommendationConfidence.MEDIUM: 0.70,
            RecommendationConfidence.LOW: 0.55,
            RecommendationConfidence.VERY_LOW: 0.30
        }
        
        return confidence_scores[recommendation.confidence] >= min_confidence
    
    def _rank_recommendations(self, recommendations: List[AdvancedRecommendation]) -> List[AdvancedRecommendation]:
        """Rank recommendations by composite score"""
        def score_recommendation(rec: AdvancedRecommendation) -> float:
            confidence_weight = {
                RecommendationConfidence.VERY_HIGH: 1.0,
                RecommendationConfidence.HIGH: 0.8,
                RecommendationConfidence.MEDIUM: 0.6,
                RecommendationConfidence.LOW: 0.4,
                RecommendationConfidence.VERY_LOW: 0.2
            }
            
            action_weight = {
                RecommendationAction.STRONG_BUY: 1.0,
                RecommendationAction.BUY: 0.7,
                RecommendationAction.HOLD: 0.3,
                RecommendationAction.AVOID: -0.3,
                RecommendationAction.STRONG_AVOID: -1.0
            }
            
            return (confidence_weight[rec.confidence] * 0.6 + 
                   action_weight[rec.action] * 0.4 +
                   rec.probability_of_profit * 0.3 +
                   rec.robustness_score * 0.2)
        
        return sorted(recommendations, key=score_recommendation, reverse=True)


async def main():
    """Test the advanced recommendation engine"""
    from trading_platform.database.database import get_db_session
    
    # Get database session
    db_session = next(get_db_session()) if hasattr(get_db_session(), '__next__') else get_db_session()
    
    try:
        # Initialize the advanced recommendation engine
        engine = AdvancedRecommendationEngine(db_session)
        
        # Generate intelligent recommendations
        recommendations = await engine.generate_intelligent_recommendations(
            current_time=datetime.now(),
            min_confidence=0.7
        )
        
        print(f"\n🎯 Generated {len(recommendations)} Advanced Recommendations\n")
        
        for i, rec in enumerate(recommendations, 1):
            print(f"{'='*60}")
            print(f"Recommendation #{i}")
            print(f"{'='*60}")
            print(f"Time-Bin: {rec.time_bin}")
            print(f"Action: {rec.action.value}")
            print(f"Confidence: {rec.confidence.value}")
            print(f"Expected Return: ${rec.expected_return:.2f}")
            print(f"Probability of Profit: {rec.probability_of_profit:.1%}")
            print(f"Risk Score: {rec.risk_score:.2f}")
            print(f"Statistical Significance: {rec.statistical_significance}")
            print(f"Market Neutrality: {rec.market_neutrality}")
            print(f"VIX Regime: {rec.current_vix_regime}")
            print(f"\nReasoning: {rec.reasoning}")
            
            if rec.alerts:
                print(f"\nAlerts:")
                for alert in rec.alerts:
                    print(f"  {alert}")
            
            if rec.recommendations:
                print(f"\nRecommendations:")
                for recommendation in rec.recommendations:
                    print(f"  {recommendation}")
            
            print()
        
    except Exception as e:
        logger.error(f"Error running advanced recommendation engine: {e}")
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())