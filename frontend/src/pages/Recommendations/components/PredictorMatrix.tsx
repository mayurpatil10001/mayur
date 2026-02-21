import React from 'react';

interface Prediction {
    predicted_account: string;
    confidence: string;
    agreement_ratio: number;
}

interface PredictorMatrixProps {
    predictions: {
        [timeSlot: string]: {
            [dayIndex: string]: Prediction;
        };
    };
    dayNames: string[];
    timeSlots: string[];
}

const PredictorMatrix: React.FC<PredictorMatrixProps> = ({
    predictions,
    dayNames,
    timeSlots
}) => {
    // Filter time slots to only show those with predictions
    const filteredTimeSlots = timeSlots.filter(timeSlot => {
        const slotData = predictions[timeSlot];
        return slotData && Object.keys(slotData).length > 0;
    });

    const getConfidenceClass = (confidence: string) => {
        switch (confidence.toLowerCase()) {
            case 'high': return 'excellent';
            case 'medium': return 'good';
            case 'low': return 'neutral';
            default: return 'empty';
        }
    };

    return (
        <div className="matrix-container prediction-matrix">
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
                                {[0, 1, 2, 3, 4, 5].map(dayIndex => {
                                    const pred = predictions[timeSlot]?.[dayIndex.toString()];
                                    const cellClass = pred ? `matrix-cell ${getConfidenceClass(pred.confidence)}` : 'matrix-cell empty';

                                    return (
                                        <td key={dayIndex} className={cellClass}>
                                            {pred ? (
                                                <div className="cell-content">
                                                    <div className="best-account" style={{ fontSize: '11px' }}>{pred.predicted_account}</div>
                                                    <div className="cell-stats" style={{ fontSize: '9px', marginTop: '2px' }}>
                                                        {pred.confidence} ({Math.round(pred.agreement_ratio * 100)}%)
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

export default PredictorMatrix;
