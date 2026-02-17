import React from 'react';
import InteractiveChart from '../../../components/InteractiveChart/InteractiveChart';

interface BacktestSimulationProps {
    isRunning: boolean;
    status: any;
    results: any;
    error: string | null;
    onRunBacktest: () => void;
    config: any;
    onConfigChange: (config: any) => void;
    formatCurrency: (value: number) => string;
}

const BacktestSimulation: React.FC<BacktestSimulationProps> = ({
    isRunning,
    status,
    results,
    error,
    onRunBacktest,
    config,
    onConfigChange,
    formatCurrency
}) => {
    return (
        <div className="backtest-simulation">
            <div className="simulation-controls">
                <div className="config-grid">
                    <div className="control-group">
                        <label>Initial Capital</label>
                        <input
                            type="number"
                            value={config.initialCapital}
                            onChange={(e) => onConfigChange({ ...config, initialCapital: Number(e.target.value) })}
                        />
                    </div>
                    <div className="control-group">
                        <label>Method</label>
                        <select
                            value={config.method}
                            onChange={(e) => onConfigChange({ ...config, method: e.target.value })}
                        >
                            <option value="simple_historical">Simple Historical</option>
                            <option value="walk_forward">Walk Forward</option>
                        </select>
                    </div>
                </div>

                <button
                    className={`run-sim-btn ${isRunning ? 'running' : ''}`}
                    onClick={onRunBacktest}
                    disabled={isRunning}
                >
                    {isRunning ? '⏳ Running...' : '🚀 Run Backtest Simulation'}
                </button>
            </div>

            {error && <div className="sim-error">{error}</div>}

            {status && isRunning && (
                <div className="sim-progress">
                    <div className="progress-text">Status: {status.status} ({Math.round(status.progress * 100)}%)</div>
                    <div className="progress-bar-container">
                        <div className="progress-bar-fill" style={{ width: `${status.progress * 100}%` }}></div>
                    </div>
                </div>
            )}

            {results && !isRunning && (
                <div className="sim-results">
                    <div className="results-metrics">
                        <div className="metric">
                            <span className="label">Total Return</span>
                            <span className={`value ${results.overall_result.total_return >= 0 ? 'positive' : 'negative'}`}>
                                {formatCurrency(results.overall_result.total_return)}
                            </span>
                        </div>
                        <div className="metric">
                            <span className="label">Win Rate</span>
                            <span className="value">{(results.overall_result.win_rate * 100).toFixed(1)}%</span>
                        </div>
                        <div className="metric">
                            <span className="label">Sharpe</span>
                            <span className="value">{results.overall_result.sharpe_ratio?.toFixed(2) || 'N/A'}</span>
                        </div>
                    </div>

                    {results.overall_result.daily_returns && (
                        <div className="sim-chart">
                            <h4>Equity Growth</h4>
                            <InteractiveChart
                                data={results.overall_result.daily_returns.map((ret: any, i: number) => ({
                                    date: `Day ${i}`,
                                    daily_pnl: ret.daily_return * config.initialCapital,
                                    cumulative_pnl: ret.cumulative_return * config.initialCapital
                                }))}
                                formatCurrency={formatCurrency}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default BacktestSimulation;
