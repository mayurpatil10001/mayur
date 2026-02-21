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

    const readinessScore = getReadinessScore();

    return (
        <div className="validation-results">
            {/* Horizontal KPI Row */}
            <div className="validation-compact-header">
                <div className="compact-summary-card">
                    <span className="card-label">Total P&L</span>
                    <span className={`card-value ${analysis.total_pnl > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(analysis.total_pnl)}
                    </span>
                    <span className="card-subtitle">{validationData.total_trades} trades</span>
                </div>

                <div className="compact-summary-card">
                    <span className="card-label">Win Rate</span>
                    <span className="card-value">{(analysis.win_rate * 100).toFixed(1)}%</span>
                    <span className="card-subtitle">{analysis.winning_trades} winners</span>
                </div>

                <div className="compact-summary-card">
                    <span className="card-label">Avg Trade</span>
                    <span className={`card-value ${analysis.avg_trade > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(analysis.avg_trade)}
                    </span>
                    <span className="card-subtitle">per trade</span>
                </div>

                <div className="compact-summary-card">
                    <span className="card-label">Sharpe Ratio</span>
                    <span className="card-value">{analysis.sharpe_ratio?.toFixed(2) || '0.00'}</span>
                    <span className="card-subtitle" title={`Annualized over ${analysis.sharpe_calendar_days ?? '?'} calendar days @ ${analysis.sharpe_trades_per_day ?? '?'} trades/day`}>
                        {analysis.sharpe_calendar_days
                            ? `${analysis.sharpe_calendar_days}d · ${analysis.sharpe_trades_per_day}/day`
                            : 'risk-adjusted'}
                    </span>
                </div>
            </div>



            {/* Footer Summary (Readiness + Trust) */}
            <div className="validation-compact-footer">
                <div className="compact-readiness">
                    <span style={{ fontSize: '12px', fontWeight: 600 }}>Readiness:</span>
                    <span className={`readiness-compact-score ${readinessScore >= 80 ? 'ready' : 'not-ready'}`}>
                        {readinessScore}%
                    </span>
                </div>

                <div className="compact-trust-grid">
                    <div className="compact-trust-item">
                        <span className="trust-icon">{analysis.statistical_significance ? '✅' : '❌'}</span>
                        <div className="trust-info">
                            <span className="trust-title">Significance</span>
                        </div>
                    </div>

                    <div className="compact-trust-item">
                        <span className="trust-icon">{analysis.sample_size_adequate ? '✅' : '⚠️'}</span>
                        <div className="trust-info">
                            <span className="trust-title">Sample Size</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StrategyValidation;
