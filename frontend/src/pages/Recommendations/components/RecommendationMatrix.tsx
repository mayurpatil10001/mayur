import React, { useState } from 'react';

interface MatrixCellData {
    best_account: string;
    total_trades: number;
    total_pnl: number;
    avg_trade: number;
    win_rate: number;
    confidence?: number;
    status?: 'STABLE' | 'DRIFTING' | 'CRITICAL' | 'NEW';
    health_score?: number;
    avg_winner?: number | null;
    avg_loser?: number | null;
    largest_winner?: number | null;
    largest_loser?: number | null;
    profit_factor?: number | null;
    // best-bins overlay
    composite_score?: number;
    rank?: number;
    is_best_bin?: boolean;
    // regime overlay
    regime_consistency?: boolean;
    fragility_score?: number | null;
    regime_count?: number;
    persistence_score?: number | null;
    reliability_score?: number;
}

interface RecommendationMatrixProps {
    matrix: {
        [timeSlot: string]: {
            [dayOfWeek: number]: MatrixCellData;
        };
    };
    probabilityMatrix?: {
        [timeSlot: string]: {
            [dayOfWeek: number]: {
                best_account: string;
                accounts: {
                    [account: string]: {
                        confidence_weighted_ev: number;
                        p_profit: number;
                        skewness: number;
                    };
                };
            };
        };
    };
    viewMode: 'standard' | 'probability' | 'ensemble' | 'persistence';
    timeSlots: string[];
    dayNames: string[];
    dayIndices?: number[];
    formatCurrency: (value: number) => string;
    // Best bins overlay
    bestBinsActive?: boolean;
    bestBinsMap?: { [key: string]: { composite_score: number; rank: number } };
    // Regime overlay
    regimeOverlayActive?: boolean;
    regimeMatrix?: {
        [timeSlot: string]: {
            [dayOfWeek: number]: {
                fragility_score?: number | null;
                regime_consistency?: boolean;
                regime_count?: number;
                best_account?: string;
                regime_breakdown?: {
                    [account: string]: {
                        [regime: string]: { avg_trade: number; win_rate: number; trades: number };
                    };
                };
            };
        };
    };
    selectedBinKeys?: Set<string>;
    onToggleBinSelection?: (payload: { key: string; timeSlot: string; dayOfWeek: number; account: string }) => void;
    minReliability?: number;
}

const RecommendationMatrix: React.FC<RecommendationMatrixProps> = ({
    matrix,
    probabilityMatrix,
    viewMode,
    timeSlots,
    dayNames,
    dayIndices = [0, 1, 2, 3, 4],
    formatCurrency,
    bestBinsActive = false,
    bestBinsMap = {},
    regimeOverlayActive = false,
    regimeMatrix: regimeMatrixProp,
    selectedBinKeys,
    onToggleBinSelection,
    minReliability = 0,
}) => {
    // Parent may pass null (e.g. useState(null)); default `= {}` only applies to undefined
    const regimeMatrix = regimeMatrixProp ?? {};

    const [tooltip, setTooltip] = useState<{ x: number; y: number; content: React.ReactNode } | null>(null);

    const getCellData = (timeSlot: string, dayOfWeek: number) => {
        const data = matrix?.[timeSlot]?.[dayOfWeek];
        if (data && data.reliability_score !== undefined && data.reliability_score < minReliability) {
            return undefined;
        }
        return data;
    };

    const getCellClass = (cellData: MatrixCellData | undefined) => {
        if (!cellData) return 'matrix-cell empty';
        const pf = cellData.profit_factor ?? 0;
        // Downgrade to poor if profit factor is weak regardless of avg_trade
        if (pf > 0 && pf < 1.3) return 'matrix-cell poor';
        if (cellData.avg_trade > 50) return 'matrix-cell excellent';
        if (cellData.avg_trade > 0) return 'matrix-cell good';
        if (cellData.avg_trade > -50) return 'matrix-cell neutral';
        return 'matrix-cell poor';
    };

    const getRegimeIcon = (timeSlot: string, dayOfWeek: number): { icon: string; tip: string } | null => {
        const cell = regimeMatrix[timeSlot]?.[dayOfWeek];
        if (!cell) return null;
        const regimeCount = cell.regime_count ?? 0;
        const consistent = cell.regime_consistency;
        const fragility = cell.fragility_score ?? null;

        if (consistent) {
            return { icon: '🛡', tip: `Profitable in all ${regimeCount} regimes. Fragility: ${fragility !== null ? fragility.toFixed(2) : 'n/a'}` };
        }
        if (regimeCount >= 2) {
            return { icon: '⚠️', tip: `Profitable in ${regimeCount}/3 regimes. Fragility: ${fragility !== null ? fragility.toFixed(2) : 'n/a'}` };
        }
        if (regimeCount === 1) {
            return { icon: '🚨', tip: `Only profitable in 1 regime. High fragility!` };
        }
        return null;
    };

    const buildCellTooltip = (
        cellData: MatrixCellData,
        timeSlot: string,
        dayOfWeek: number,
        bestBinInfo: { composite_score: number; rank: number } | undefined
    ): React.ReactNode => {
        const regimeCell = regimeMatrix[timeSlot]?.[dayOfWeek];
        const bestAccRegimes = regimeCell?.regime_breakdown?.[cellData.best_account] ?? null;
        return (
            <div style={{ minWidth: 240, fontSize: 12 }}>
                <div style={{ fontWeight: 700, marginBottom: 6, borderBottom: '1px solid #444', paddingBottom: 4 }}>
                    {cellData.best_account} — {timeSlot}
                </div>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                        <tr><td>Avg Trade</td><td style={{ textAlign: 'right', color: cellData.avg_trade > 0 ? '#4ade80' : '#f87171' }}>{formatCurrency(cellData.avg_trade)}</td></tr>
                        <tr><td>Win Rate</td><td style={{ textAlign: 'right' }}>{cellData.win_rate.toFixed(1)}%</td></tr>
                        <tr><td>Profit Factor</td><td style={{ textAlign: 'right', color: (cellData.profit_factor ?? 0) >= 1.5 ? '#4ade80' : '#facc15' }}>{cellData.profit_factor?.toFixed(2) ?? 'n/a'}</td></tr>
                        <tr><td>Avg Winner</td><td style={{ textAlign: 'right', color: '#4ade80' }}>{cellData.avg_winner != null ? formatCurrency(cellData.avg_winner) : 'n/a'}</td></tr>
                        <tr><td>Avg Loser</td><td style={{ textAlign: 'right', color: '#f87171' }}>{cellData.avg_loser != null ? formatCurrency(cellData.avg_loser) : 'n/a'}</td></tr>
                        <tr><td>Largest Win</td><td style={{ textAlign: 'right' }}>{cellData.largest_winner != null ? formatCurrency(cellData.largest_winner) : 'n/a'}</td></tr>
                        <tr><td>Largest Loss</td><td style={{ textAlign: 'right' }}>{cellData.largest_loser != null ? formatCurrency(cellData.largest_loser) : 'n/a'}</td></tr>
                        <tr><td>Total Trades</td><td style={{ textAlign: 'right' }}>{cellData.total_trades.toLocaleString()}</td></tr>
                        <tr><td>Total PnL</td><td style={{ textAlign: 'right', color: cellData.total_pnl > 0 ? '#4ade80' : '#f87171' }}>{formatCurrency(cellData.total_pnl)}</td></tr>
                        {cellData.reliability_score !== undefined && (
                            <tr>
                                <td>Reliability</td>
                                <td style={{ textAlign: 'right' }}>
                                    <span style={{ 
                                        color: cellData.reliability_score >= 90 ? '#4ade80' : 
                                               cellData.reliability_score >= 70 ? '#facc15' : '#f87171',
                                        fontWeight: 700
                                    }}>
                                        {cellData.reliability_score}%
                                    </span>
                                </td>
                            </tr>
                        )}
                        {cellData.status && (
                            <tr>
                                <td>Health</td>
                                <td style={{ textAlign: 'right' }}>
                                    <span style={{ color: cellData.status === 'STABLE' ? '#4ade80' : cellData.status === 'DRIFTING' ? '#facc15' : '#f87171' }}>
                                        {cellData.status} ({cellData.health_score}%)
                                    </span>
                                </td>
                            </tr>
                        )}
                        {bestBinInfo && (
                            <tr>
                                <td>Best Bin Rank</td>
                                <td style={{ textAlign: 'right', color: '#fbbf24' }}>#{bestBinInfo.rank} (score {bestBinInfo.composite_score.toFixed(3)})</td>
                            </tr>
                        )}
                    </tbody>
                </table>
                {bestAccRegimes && (
                    <div style={{ marginTop: 8, borderTop: '1px solid #444', paddingTop: 6 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4 }}>VIX Regime Breakdown:</div>
                        {(['Low', 'Medium', 'High'] as const).map(regime => {
                            const rd = bestAccRegimes[regime];
                            if (!rd) return null;
                            return (
                                <div key={regime} style={{ display: 'flex', justifyContent: 'space-between', color: rd.avg_trade > 0 ? '#4ade80' : '#f87171' }}>
                                    <span>{regime} VIX</span>
                                    <span>{formatCurrency(rd.avg_trade)} ({rd.win_rate.toFixed(0)}% WR, {rd.trades} trades)</span>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        );
    };

    const filteredTimeSlots = timeSlots.filter(timeSlot => {
        for (const dayOfWeek of dayIndices) {
            if (matrix?.[timeSlot]?.[dayOfWeek]) return true;
        }
        return false;
    });

    return (
        <div className="matrix-container" style={{ position: 'relative' }}>
            {tooltip && (
                <div
                    style={{
                        position: 'fixed',
                        left: tooltip.x + 12,
                        top: tooltip.y - 8,
                        background: '#1e2433',
                        border: '1px solid #3a4460',
                        borderRadius: 8,
                        padding: '10px 14px',
                        zIndex: 9999,
                        color: '#e2e8f0',
                        boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
                        pointerEvents: 'none',
                        maxWidth: 300,
                    }}
                >
                    {tooltip.content}
                </div>
            )}
            <table className="recommendation-matrix-table">
                <thead>
                    <tr>
                        <th className="time-header">Time</th>
                        {dayNames.map((day, index) => (
                            <th key={index} className="day-header">{day}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {filteredTimeSlots.map((timeSlot, index) => {
                        const currentHour = timeSlot.split(':')[0];
                        const prevTimeSlot = index > 0 ? filteredTimeSlots[index - 1] : null;
                        const prevHour = prevTimeSlot ? prevTimeSlot.split(':')[0] : null;
                        const isNewHour = currentHour !== prevHour;

                        return (
                            <tr key={timeSlot} className={isNewHour && index !== 0 ? 'hour-divider' : ''}>
                                <td className="time-slot-cell">{timeSlot}</td>
                                {dayIndices.map(dayOfWeek => {
                                    const cellData = getCellData(timeSlot, dayOfWeek);
                                    const probCell = probabilityMatrix?.[timeSlot]?.[dayOfWeek];
                                    let cellClass = getCellClass(cellData);

                                    const binKey = cellData ? `${timeSlot}_${dayOfWeek}` : '';
                                    const bestBinInfo = bestBinsMap[binKey];
                                    const isBestBin = bestBinsActive && !!bestBinInfo;
                                    const isDimmed = bestBinsActive && cellData && !bestBinInfo;
                                    const isSelected = !!(cellData && selectedBinKeys?.has(binKey));

                                    const regimeIcon = regimeOverlayActive ? getRegimeIcon(timeSlot, dayOfWeek) : null;

                                    const displayAccount = (viewMode === 'standard' || viewMode === 'persistence')
                                        ? cellData?.best_account
                                        : (probCell?.best_account || cellData?.best_account);

                                    return (
                                        <td
                                            key={dayOfWeek}
                                            className={cellClass}
                                            style={{
                                                opacity: isDimmed ? 0.35 : 1,
                                                filter: isDimmed ? 'grayscale(1)' : 'none',
                                                outline: isSelected ? '3px solid #2563eb' : (isBestBin ? '2px solid #fbbf24' : undefined),
                                                outlineOffset: isSelected ? '-3px' : (isBestBin ? '-2px' : undefined),
                                                backgroundColor: cellData ? (isSelected ? '#eaf2ff' : '#f8fbff') : undefined,
                                                position: 'relative',
                                                cursor: cellData ? 'pointer' : 'default',
                                            }}
                                            onMouseMove={cellData ? (e) => {
                                                setTooltip({
                                                    x: e.clientX,
                                                    y: e.clientY,
                                                    content: buildCellTooltip(cellData, timeSlot, dayOfWeek, bestBinInfo)
                                                });
                                            } : undefined}
                                            onMouseLeave={() => setTooltip(null)}
                                            onClick={cellData ? () => onToggleBinSelection?.({
                                                key: binKey,
                                                timeSlot,
                                                dayOfWeek,
                                                account: cellData.best_account,
                                            }) : undefined}
                                        >
                                            {cellData ? (
                                                <div className="cell-content">
                                                    {isSelected && (
                                                        <span style={{
                                                            position: 'absolute', top: 2, left: regimeIcon ? 16 : 3,
                                                            background: '#2563eb', color: '#fff',
                                                            borderRadius: 999, padding: '1px 5px',
                                                            fontSize: 8, fontWeight: 700,
                                                        }}>
                                                            SELECTED
                                                        </span>
                                                    )}
                                                    {/* Best bin rank badge */}
                                                    {isBestBin && (
                                                        <span style={{
                                                            position: 'absolute', top: 2, right: 3,
                                                            background: '#fbbf24', color: '#000',
                                                            borderRadius: '50%', width: 16, height: 16,
                                                            fontSize: 9, fontWeight: 700,
                                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                            lineHeight: 1,
                                                        }}>
                                                            {bestBinInfo.rank}
                                                        </span>
                                                    )}
                                                    {/* Regime icon */}
                                                    {regimeIcon && (
                                                        <span
                                                            style={{ position: 'absolute', top: 2, left: 3, fontSize: 10, cursor: 'help' }}
                                                            title={regimeIcon.tip}
                                                        >
                                                            {regimeIcon.icon}
                                                        </span>
                                                    )}
                                                    <div className="account-header">
                                                        <span className="best-account">{displayAccount}</span>
                                                        {cellData.status && (
                                                            <span
                                                                className={`status-indicator ${cellData.status.toLowerCase()}`}
                                                                title={`Status: ${cellData.status} (Health: ${cellData.health_score}%)`}
                                                            >
                                                                
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="cell-stats" style={{ display: 'flex', gap: 8, flexWrap: 'nowrap', marginTop: 2, fontSize: 10, whiteSpace: 'nowrap' }}>
                                                        <span style={{ color: '#d63384', fontWeight: 700 }} title="Avg PnL">
                                                            {formatCurrency(cellData.avg_trade)}
                                                        </span>
                                                        <span style={{ color: '#fd7e14', fontWeight: 700 }} title="Trades">
                                                            {cellData.total_trades}
                                                        </span>
                                                        <span style={{ color: '#111827', fontWeight: 700 }} title="W/L %">
                                                            {cellData.win_rate.toFixed(0)}%
                                                        </span>
                                                        <span style={{ color: '#198754', fontWeight: 700 }} title="Persistence">
                                                            {cellData.persistence_score != null ? `${cellData.persistence_score.toFixed(0)}%` : '—'}
                                                        </span>
                                                        {cellData.reliability_score !== undefined && (
                                                            <span style={{ 
                                                                color: cellData.reliability_score >= 90 ? '#0d9488' : 
                                                                       cellData.reliability_score >= 70 ? '#b45309' : '#b91c1c',
                                                                fontWeight: 800,
                                                                fontSize: 9,
                                                                padding: '1px 3px',
                                                                borderRadius: 4,
                                                                backgroundColor: cellData.reliability_score >= 90 ? '#f0fdfa' : 
                                                                                 cellData.reliability_score >= 70 ? '#fffbeb' : '#fef2f2'
                                                            }} title="Statistical Reliability (CLT Probability)">
                                                                {cellData.reliability_score.toFixed(0)}%
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="empty-cell">-</div>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

export default RecommendationMatrix;
