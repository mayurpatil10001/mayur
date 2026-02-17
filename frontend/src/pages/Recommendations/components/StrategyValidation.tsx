import React from 'react';

interface StrategyValidationProps {
    validationData: any;
    formatCurrency: (value: number) => string;
    getTimeHorizonLabel: (horizon: string) => string;
    timeHorizon: string;
}

const StrategyValidation: React.FC<StrategyValidationProps> = ({
    validationData,
    formatCurrency,
    getTimeHorizonLabel,
    timeHorizon
}) => {
    if (!validationData || !validationData.analysis) {
        return <div className="no-validation">No validation data available.</div>;
    }

    const { analysis } = validationData;

    const getReadinessScore = () => {
        const criteria = [
            Math.abs(analysis.var_95) / Math.abs(analysis.best_case) <= 1.5,
            analysis.probability_of_profit >= 0.75,
            Math.abs(analysis.var_95) <= 5000,
            analysis.sharpe_ratio >= 1.5,
            analysis.win_rate >= 0.6,
            analysis.profit_factor >= 1.5,
            analysis.statistical_significance,
            analysis.sample_size_adequate
        ];
        const passedCriteria = criteria.filter(Boolean).length;
        return Math.round((passedCriteria / criteria.length) * 100);
    };

    return (
        <div className="validation-results">
            <div className="summary-cards">
                <div className="summary-card total-pnl">
                    <div className="card-header">
                        <span className="card-icon">💰</span>
                        <span className="card-title">Total P&L</span>
                    </div>
                    <div className={`card-value ${analysis.total_pnl > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(analysis.total_pnl)}
                    </div>
                    <div className="card-subtitle">{validationData.total_trades} trades</div>
                </div>

                <div className="summary-card win-rate">
                    <div className="card-header">
                        <span className="card-icon">🎯</span>
                        <span className="card-title">Win Rate</span>
                    </div>
                    <div className={`card-value ${analysis.win_rate > 0.5 ? 'good' : 'neutral'}`}>
                        {(analysis.win_rate * 100).toFixed(1)}%
                    </div>
                    <div className="card-subtitle">{analysis.winning_trades} winners</div>
                </div>

                <div className="summary-card avg-trade">
                    <div className="card-header">
                        <span className="card-icon">📊</span>
                        <span className="card-title">Avg Trade</span>
                    </div>
                    <div className={`card-value ${analysis.avg_trade > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(analysis.avg_trade)}
                    </div>
                    <div className="card-subtitle">per trade</div>
                </div>

                <div className="summary-card sharpe">
                    <div className="card-header">
                        <span className="card-icon">⚡</span>
                        <span className="card-title">Sharpe Ratio</span>
                    </div>
                    <div className={`card-value ${analysis.sharpe_ratio > 1 ? 'good' : analysis.sharpe_ratio > 0 ? 'neutral' : 'negative'}`}>
                        {analysis.sharpe_ratio?.toFixed(2) || 'N/A'}
                    </div>
                    <div className="card-subtitle">risk-adjusted</div>
                </div>
            </div>

            <div className="readiness-score-container">
                <div className="score-header">
                    <h3>Trading Readiness Score</h3>
                    <span className={`score-badge ${getReadinessScore() >= 80 ? 'ready' : 'not-ready'}`}>
                        {getReadinessScore()}%
                    </span>
                </div>
                <div className="score-description">
                    {getReadinessScore() >= 80
                        ? 'Strategy is ready for live trading with proper risk management.'
                        : 'Strategy needs further testing or optimization before live use.'}
                </div>
            </div>

            <div className="trust-section">
                <h3>🔍 Strategy Trust Indicators</h3>
                <div className="trust-grid">
                    <div className={`trust-item ${analysis.statistical_significance ? 'pass' : 'fail'}`}>
                        <span className="trust-icon">{analysis.statistical_significance ? '✅' : '❌'}</span>
                        <div className="trust-info">
                            <div className="trust-title">Statistical Significance</div>
                            <div className="trust-explanation">
                                {analysis.statistical_significance
                                    ? 'Strong evidence results are not due to chance.'
                                    : 'Results may be due to random luck (p \u2265 0.05).'}
                            </div>
                        </div>
                    </div>

                    <div className={`trust-item ${analysis.sample_size_adequate ? 'pass' : 'warning'}`}>
                        <span className="trust-icon">{analysis.sample_size_adequate ? '✅' : '⚠️'}</span>
                        <div className="trust-info">
                            <div className="trust-title">Sample Size Adequacy</div>
                            <div className="trust-explanation">
                                {analysis.sample_size_adequate
                                    ? 'Sufficient trade volume for reliable analysis.'
                                    : 'Need more trades for a conclusive result.'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StrategyValidation;
