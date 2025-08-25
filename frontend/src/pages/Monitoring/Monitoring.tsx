/**
 * Monitoring page component
 * 
 * Main page for system monitoring and alerts management.
 * 
 * Requirements: 8.1, 8.3
 */

import React from 'react';
import AlertsMonitoring from '../../components/AlertsMonitoring/AlertsMonitoring';
import './Monitoring.css';

const Monitoring: React.FC = () => {
  return (
    <div className="monitoring-page">
      <AlertsMonitoring />
    </div>
  );
};

export default Monitoring;