import React from 'react';

interface MatrixCellData {
    best_account: string;
    total_trades: number;
    total_pnl: number;
    avg_trade: number;
    win_rate: number;
}

interface OOSResultData {
    total_pnl: number;
    trades: number;
    win_rate: number;
    wins: number;
}

interface FoldComparisonMatrixProps {
    trainMatrix: { [key: string]: any };
    oosResults: { [key: string]: OOSResultData };
    timeSlots: string[];
    dayNames: string[];
}

const FoldComparisonMatrix: React.FC<FoldComparisonMatrixProps> = ({
    trainMatrix,
    oosResults,
    timeSlots,
    dayNames
}) => {
    // Helper to get data for a specific cell
    const getTrainData = (timeSlot: string, dayOfWeek: number) => {
        return trainMatrix[`${timeSlot}_${dayOfWeek}`];
    };

    const getOOSData = (timeSlot: string, dayOfWeek: number) => {
        return oosResults[`${timeSlot}_${dayOfWeek}`];
    };

    // Style logic
    const getTrainClass = (data: any) => {
        if (!data) return 'matrix-cell empty';
        return data.avg_trade > 0 ? 'matrix-cell good' : 'matrix-cell poor';
    };

    const getOOSClass = (data: OOSResultData | undefined) => {
        if (!data || data.trades === 0) return 'matrix-cell empty';
        if (data.total_pnl > 500) return 'matrix-cell excellent';
        if (data.total_pnl > 0) return 'matrix-cell good';
        if (data.total_pnl > -500) return 'matrix-cell neutral';
        return 'matrix-cell poor';
    };

    // Filter time slots to those that have either train or OOS data
    const allKeys = [...Object.keys(trainMatrix), ...Object.keys(oosResults)];
    const derivedTimeSlots = Array.from(new Set(allKeys.map(k => k.split('_')[0]))).sort();

    const baseTimeSlots = timeSlots && timeSlots.length > 0 ? timeSlots : derivedTimeSlots;

    const activeTimeSlots = baseTimeSlots.filter(ts => {
        for (let d = 0; d < 6; d++) {
            if (getTrainData(ts, d) || getOOSData(ts, d)) return true;
        }
        return false;
    });

    if (activeTimeSlots.length === 0) {
        return (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', border: '1px dashed var(--border-color)', borderRadius: '8px' }}>
                No significant data found for this fold's matrix comparison.
            </div>
        );
    }

    return (
        <div className="fold-comparison-wrapper">
            <div className="fold-comparison-container" style={{ display: 'flex', gap: '30px', flexWrap: 'wrap', justifyContent: 'space-between' }}>
                {/* TRAIN MATRIX (LEFT) */}
                <div className="matrix-side" style={{ flex: '1 1 45%', minWidth: '450px' }}>
                    <h4 style={{ marginBottom: '15px', color: 'var(--text-secondary)', fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--text-secondary)' }}></span>
                        Training Recommendations (In-Sample)
                    </h4>
                    <div className="matrix-scroll-container" style={{ overflowX: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                        <table className="recommendation-matrix-table mini" style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ background: '#f1f5f9' }}>
                                    <th style={{ padding: '8px', borderBottom: '1px solid var(--border-color)', width: '80px' }}>Time</th>
                                    {dayNames.slice(0, 6).map((day, i) => (
                                        <th key={i} style={{ padding: '8px', borderBottom: '1px solid var(--border-color)', textAlign: 'center' }}>{day[0]}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {activeTimeSlots.map(ts => (
                                    <tr key={ts}>
                                        <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f5f9', fontSize: '11px', fontWeight: 600, background: '#f8fafc' }}>{ts}</td>
                                        {[0, 1, 2, 3, 4, 5].map(d => {
                                            const data = getTrainData(ts, d);
                                            const acct = data?.best_account || (typeof data === 'string' ? data : null);
                                            const tooltip = data && typeof data === 'object' ? `${acct}: $${data.avg_trade} (${data.total_trades} tr)` : (acct || 'No rec');

                                            return (
                                                <td key={d} className={getTrainClass(data)} style={{ padding: '2px', border: '1px solid #f1f5f9', height: '32px', textAlign: 'center' }} title={tooltip}>
                                                    {acct ? (
                                                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                                                            <span style={{ fontSize: '8px', fontWeight: 800, color: '#000000', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }}>{acct}</span>
                                                        </div>
                                                    ) : <span style={{ color: '#cbd5e1' }}>-</span>}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* OOS ACTUAL RESULTS (RIGHT) */}
                <div className="matrix-side" style={{ flex: '1 1 45%', minWidth: '450px' }}>
                    <h4 style={{ marginBottom: '15px', color: 'var(--success-color)', fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--success-color)' }}></span>
                        Actual OOS Performance (Real Results)
                    </h4>
                    <div className="matrix-scroll-container" style={{ overflowX: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                        <table className="recommendation-matrix-table mini" style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ background: '#f1f5f9' }}>
                                    <th style={{ padding: '8px', borderBottom: '1px solid var(--border-color)', width: '80px' }}>Time</th>
                                    {dayNames.slice(0, 6).map((day, i) => (
                                        <th key={i} style={{ padding: '8px', borderBottom: '1px solid var(--border-color)', textAlign: 'center' }}>{day[0]}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {activeTimeSlots.map(ts => (
                                    <tr key={ts}>
                                        <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f5f9', fontSize: '11px', fontWeight: 600, background: '#f8fafc' }}>{ts}</td>
                                        {[0, 1, 2, 3, 4, 5].map(d => {
                                            const data = getOOSData(ts, d);
                                            const tooltip = data ? `$${data.total_pnl.toFixed(0)} across ${data.trades} trades` : 'No trades';
                                            return (
                                                <td key={d} className={getOOSClass(data)} style={{ padding: '2px', border: '1px solid #f1f5f9', height: '32px', textAlign: 'center' }} title={tooltip}>
                                                    {data ? (
                                                        <span style={{ fontSize: '9px', fontWeight: 800, color: '#000000' }}>
                                                            {data.total_pnl > 0 ? '+' : ''}{Math.round(data.total_pnl)}
                                                        </span>
                                                    ) : <span style={{ color: '#cbd5e1' }}>-</span>}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div style={{ marginTop: '12px', fontSize: '11px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                Note: In Actual OOS, values show total PnL for the test period. Hover over cells for exact trade counts.
            </div>
        </div>
    );
};

export default FoldComparisonMatrix;
