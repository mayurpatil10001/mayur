import React from 'react';
import './TradingReadinessAssessment.css';

interface CriteriaItem {
  label: string;
  current: number | string;
  target: number | string;
  unit?: string;
  status: 'good' | 'warning' | 'poor';
}

interface TradingReadinessAssessmentProps {
  riskManagementCriteria: CriteriaItem[];
  performanceCriteria: CriteriaItem[];
  statisticalCriteria?: CriteriaItem[];
}

const TradingReadinessAssessment: React.FC<TradingReadinessAssessmentProps> = ({
  riskManagementCriteria,
  performanceCriteria,
  statisticalCriteria
}) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good':
        return '✅';
      case 'warning':
        return '⚠️';
      case 'poor':
        return '❌';
      default:
        return '⚪';
    }
  };

  const renderCriteriaSection = (title: string, criteria: CriteriaItem[], icon: string) => (
    <div className="criteria-section">
      <div className="criteria-header">
        <span className="criteria-icon">{icon}</span>
        <h4 className="criteria-title">{title}</h4>
      </div>
      <div className="criteria-list">
        {criteria.map((item, index) => (
          <div key={index} className={`criteria-item ${item.status}`}>
            <div className="criteria-status">
              {getStatusIcon(item.status)}
            </div>
            <div className="criteria-content">
              <div className="criteria-label">{item.label}</div>
              <div className="criteria-values">
                <span className="current-value">
                  Current: {item.current}{item.unit || ''}
                </span>
                <span className="target-value">
                  Target: {item.target}{item.unit || ''}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="trading-readiness-assessment">
      <div className="assessment-header">
        <span className="assessment-icon">🎯</span>
        <h3 className="assessment-title">Trading Readiness Assessment</h3>
      </div>
      <p className="assessment-subtitle">
        Minimum conditions required before going live with real capital
      </p>
      
      <div className="criteria-container">
        {renderCriteriaSection(
          "Risk Management Criteria", 
          riskManagementCriteria, 
          "🛡️"
        )}
        
        {renderCriteriaSection(
          "Performance Criteria", 
          performanceCriteria, 
          "📈"
        )}
      </div>

      {statisticalCriteria && statisticalCriteria.length > 0 && (
        <div className="statistical-criteria-section">
          {renderCriteriaSection(
            "Statistical Criteria", 
            statisticalCriteria, 
            "📊"
          )}
        </div>
      )}
    </div>
  );
};

export default TradingReadinessAssessment;