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
    minReliability?: number;
    selectedBinKeys?: Set<string>;
    onToggleBinSelection?: (payload: { key: string; timeSlot: string; dayOfWeek: number; account: string }) => void;
}

const PredictorMatrix: React.FC<PredictorMatrixProps> = ({
    predictions,
    dayNames,
    timeSlots,
    minReliability = 0,
    selectedBinKeys,
    onToggleBinSelection,
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
                                    const isLowReliability = pred && (Math.round(pred.agreement_ratio * 100) < minReliability);
                                    const effectivePred = isLowReliability ? undefined : pred;
                                    const cellClass = effectivePred ? `matrix-cell ${getConfidenceClass(effectivePred.confidence)}` : 'matrix-cell empty';
                                    const binKey = effectivePred ? `${timeSlot}_${dayIndex}` : '';
                                    const isSelected = !!(binKey && selectedBinKeys?.has(binKey));

                                    return (
                                        <td 
                                            key={dayIndex} 
                                            className={`${cellClass} ${isSelected ? 'selected' : ''}`}
                                            style={{
                                                outline: isSelected ? '3px solid #2563eb' : undefined,
                                                outlineOffset: '-3px',
                                                backgroundColor: isSelected ? 'rgba(37, 99, 235, 0.25)' : undefined,
                                                cursor: effectivePred ? 'pointer' : 'default',
                                                position: 'relative',
                                                boxShadow: isSelected ? 'inset 0 0 10px rgba(37, 99, 235, 0.2)' : undefined
                                            }}
                                            onClick={effectivePred ? () => onToggleBinSelection?.({
                                                key: binKey,
                                                timeSlot,
                                                dayOfWeek: dayIndex,
                                                account: effectivePred.predicted_account,
                                            }) : undefined}
                                        >
                                            {effectivePred ? (
                                                <div className="cell-content">
                                                    {isSelected && (
                                                        <span style={{
                                                            position: 'absolute', top: 2, right: 3,
                                                            background: '#2563eb', color: '#fff',
                                                            borderRadius: 999, padding: '1px 5px',
                                                            fontSize: 7, fontWeight: 700,
                                                        }}>
                                                            SELECTED
                                                        </span>
                                                    )}
                                                    <div className="best-account" style={{ fontSize: '11px', fontWeight: isSelected ? 800 : 400 }}>{effectivePred.predicted_account}</div>
                                                    <div className="cell-stats" style={{ fontSize: '9px', marginTop: '2px' }}>
                                                        {effectivePred.confidence} ({Math.round(effectivePred.agreement_ratio * 100)}%)
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
