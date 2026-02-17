import React from 'react';

interface MatrixCellData {
    best_account: string;
    total_trades: number;
    total_pnl: number;
    avg_trade: number;
    win_rate: number;
}

interface RecommendationMatrixProps {
    matrix: {
        [timeSlot: string]: {
            [dayOfWeek: number]: MatrixCellData;
        };
    };
    timeSlots: string[];
    dayNames: string[];
    formatCurrency: (value: number) => string;
}

const RecommendationMatrix: React.FC<RecommendationMatrixProps> = ({
    matrix,
    timeSlots,
    dayNames,
    formatCurrency
}) => {
    const getCellData = (timeSlot: string, dayOfWeek: number) => {
        return matrix[timeSlot]?.[dayOfWeek];
    };

    const getCellClass = (cellData: MatrixCellData | undefined) => {
        if (!cellData) return 'matrix-cell empty';
        if (cellData.avg_trade > 50) return 'matrix-cell excellent';
        if (cellData.avg_trade > 0) return 'matrix-cell good';
        if (cellData.avg_trade > -50) return 'matrix-cell neutral';
        return 'matrix-cell poor';
    };

    // Filter time slots to only show those with recommendations
    const filteredTimeSlots = timeSlots.filter(timeSlot => {
        for (let dayOfWeek = 0; dayOfWeek < 6; dayOfWeek++) {
            if (matrix[timeSlot]?.[dayOfWeek]) return true;
        }
        return false;
    });

    return (
        <div className="matrix-container">
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
                                {[0, 1, 2, 3, 4, 5].map(dayOfWeek => {
                                    const cellData = getCellData(timeSlot, dayOfWeek);
                                    const cellClass = getCellClass(cellData);

                                    return (
                                        <td key={dayOfWeek} className={cellClass}>
                                            {cellData ? (
                                                <div className="cell-content">
                                                    <div className="best-account">{cellData.best_account}</div>
                                                    <div className="cell-stats">
                                                        {formatCurrency(cellData.avg_trade)}, {cellData.win_rate.toFixed(1)}%
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
