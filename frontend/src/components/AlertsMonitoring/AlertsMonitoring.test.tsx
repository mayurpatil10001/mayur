/**
 * Tests for AlertsMonitoring component
 * 
 * Tests the alerts and monitoring dashboard functionality including
 * data loading, tab navigation, and alert management.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AlertsMonitoring from './AlertsMonitoring';

// Mock fetch
global.fetch = jest.fn();
const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

// Mock data
const mockAlertSummary = {
  timestamp: '2024-01-01T12:00:00Z',
  monitoring_status: 'running' as const,
  total_rules: 8,
  enabled_rules: 7,
  active_alerts: 2,
  active_by_severity: {
    info: 0,
    warning: 1,
    critical: 1
  },
  total_channels: 3,
  enabled_channels: 2,
  alerts_last_24h: 5
};

const mockActiveAlerts = [
  {
    alert_id: 'alert_1',
    rule_id: 'high_cpu_usage',
    rule_name: 'High CPU Usage',
    message: 'CPU usage is above 80% (Value: 85.5, Threshold: 80.0)',
    severity: 'warning' as const,
    status: 'active' as const,
    metric_name: 'cpu_percent',
    metric_value: 85.5,
    threshold: 80.0,
    triggered_at: '2024-01-01T12:00:00Z',
    tags: { category: 'system', component: 'cpu' }
  },
  {
    alert_id: 'alert_2',
    rule_id: 'critical_memory_usage',
    rule_name: 'Critical Memory Usage',
    message: 'Memory usage is above 95% (Value: 97.2, Threshold: 95.0)',
    severity: 'critical' as const,
    status: 'active' as const,
    metric_name: 'memory_percent',
    metric_value: 97.2,
    threshold: 95.0,
    triggered_at: '2024-01-01T11:30:00Z',
    tags: { category: 'system', component: 'memory' }
  }
];

const mockAlertRules = [
  {
    rule_id: 'high_cpu_usage',
    name: 'High CPU Usage',
    description: 'CPU usage is above 80%',
    metric_name: 'cpu_percent',
    condition: 'greater_than',
    threshold: 80.0,
    severity: 'warning' as const,
    duration_minutes: 5,
    enabled: true,
    tags: { category: 'system' }
  },
  {
    rule_id: 'critical_memory_usage',
    name: 'Critical Memory Usage',
    description: 'Memory usage is above 95%',
    metric_name: 'memory_percent',
    condition: 'greater_than',
    threshold: 95.0,
    severity: 'critical' as const,
    duration_minutes: 2,
    enabled: true,
    tags: { category: 'system' }
  }
];

const mockHealthSummary = {
  overall_status: 'degraded' as const,
  timestamp: '2024-01-01T12:00:00Z',
  system_metrics: {
    timestamp: '2024-01-01T12:00:00Z',
    cpu_percent: 85.5,
    memory_percent: 97.2,
    memory_available_gb: 2.5,
    disk_usage_percent: 75.0,
    disk_free_gb: 50.0,
    active_connections: 10,
    response_time_avg_ms: 250.0,
    error_rate_percent: 3.5
  },
  services: {
    database: {
      service_name: 'database',
      status: 'healthy' as const,
      last_check: '2024-01-01T12:00:00Z',
      response_time_ms: 45.0
    },
    api: {
      service_name: 'api',
      status: 'degraded' as const,
      last_check: '2024-01-01T12:00:00Z',
      response_time_ms: 250.0,
      error_message: 'High response time'
    }
  },
  uptime_status: 'running' as const
};

describe('AlertsMonitoring', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  const setupSuccessfulMocks = () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockAlertSummary })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockActiveAlerts })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockAlertRules })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockHealthSummary })
      } as Response);
  };

  test('renders loading state initially', () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);
    
    expect(screen.getByText('Loading monitoring data...')).toBeInTheDocument();
  });

  test('renders overview tab after loading', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('Monitoring & Alerts')).toBeInTheDocument();
    });

    expect(screen.getByText('Alert System Overview')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument(); // Total rules
    expect(screen.getByText('2')).toBeInTheDocument(); // Active alerts
  });

  test('displays active alerts correctly', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    expect(screen.getByText('Critical Memory Usage')).toBeInTheDocument();
    expect(screen.getByText('CPU usage is above 80% (Value: 85.5, Threshold: 80.0)')).toBeInTheDocument();
    expect(screen.getByText('WARNING')).toBeInTheDocument();
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });

  test('switches tabs correctly', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('Alert System Overview')).toBeInTheDocument();
    });

    // Switch to alerts tab
    fireEvent.click(screen.getByText('Alerts'));
    expect(screen.getAllByText('High CPU Usage')).toHaveLength(1);

    // Switch to rules tab
    fireEvent.click(screen.getByText('Rules'));
    expect(screen.getByText('Alert Rules')).toBeInTheDocument();
    expect(screen.getAllByText('High CPU Usage')).toHaveLength(1);

    // Switch to health tab
    fireEvent.click(screen.getByText('Health'));
    expect(screen.getByText('System Health')).toBeInTheDocument();
    expect(screen.getByText('degraded')).toBeInTheDocument();
  });

  test('displays system health metrics', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      fireEvent.click(screen.getByText('Health'));
    });

    expect(screen.getByText('System Health')).toBeInTheDocument();
    expect(screen.getByText('85.5')).toBeInTheDocument(); // CPU
    expect(screen.getByText('97.2')).toBeInTheDocument(); // Memory
    expect(screen.getByText('75.0')).toBeInTheDocument(); // Disk
  });

  test('displays service health status', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      fireEvent.click(screen.getByText('Health'));
    });

    expect(screen.getByText('database')).toBeInTheDocument();
    expect(screen.getByText('api')).toBeInTheDocument();
    expect(screen.getByText('45.0ms')).toBeInTheDocument();
    expect(screen.getByText('250.0ms')).toBeInTheDocument();
    expect(screen.getByText('High response time')).toBeInTheDocument();
  });

  test('handles suppress alert action', async () => {
    setupSuccessfulMocks();
    
    // Mock suppress alert API call
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response);

    // Mock reload data after suppress
    setupSuccessfulMocks();

    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    const suppressButtons = screen.getAllByText('Suppress');
    fireEvent.click(suppressButtons[0]);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/health/alerts/high_cpu_usage/suppress',
        { method: 'POST' }
      );
    });
  });

  test('handles start monitoring action', async () => {
    setupSuccessfulMocks();
    
    // Mock start monitoring API call
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response);

    // Mock reload data after start
    setupSuccessfulMocks();

    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('Stop Monitoring')).toBeInTheDocument();
    });

    // Change monitoring status to stopped for this test
    mockFetch.mockClear();
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ 
          data: { ...mockAlertSummary, monitoring_status: 'stopped' }
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockActiveAlerts })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockAlertRules })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockHealthSummary })
      } as Response);

    fireEvent.click(screen.getByText('Refresh'));

    await waitFor(() => {
      expect(screen.getByText('Start Monitoring')).toBeInTheDocument();
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    } as Response);

    setupSuccessfulMocks();

    fireEvent.click(screen.getByText('Start Monitoring'));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/health/alerts/monitoring/start',
        { method: 'POST' }
      );
    });
  });

  test('handles API errors gracefully', async () => {
    mockFetch.mockRejectedValueOnce(new Error('API Error'));

    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument();
    });

    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  test('refreshes data periodically', async () => {
    jest.useFakeTimers();
    setupSuccessfulMocks();

    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('Alert System Overview')).toBeInTheDocument();
    });

    // Clear previous fetch calls
    mockFetch.mockClear();
    setupSuccessfulMocks();

    // Fast-forward 30 seconds
    jest.advanceTimersByTime(30000);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(4); // 4 API calls for refresh
    });

    jest.useRealTimers();
  });

  test('displays correct severity badges', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      expect(screen.getByText('WARNING')).toBeInTheDocument();
    });

    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    
    const warningBadge = screen.getByText('WARNING');
    const criticalBadge = screen.getByText('CRITICAL');
    
    expect(warningBadge).toHaveClass('severity-warning');
    expect(criticalBadge).toHaveClass('severity-critical');
  });

  test('displays metric cards with correct status colors', async () => {
    setupSuccessfulMocks();
    render(<AlertsMonitoring />);

    await waitFor(() => {
      fireEvent.click(screen.getByText('Health'));
    });

    // Check that high CPU gets warning/critical styling
    const cpuCard = screen.getByText('85.5').closest('.metric-card');
    expect(cpuCard).toHaveClass('metric-critical');

    // Check that high memory gets critical styling
    const memoryCard = screen.getByText('97.2').closest('.metric-card');
    expect(memoryCard).toHaveClass('metric-critical');
  });

  test('shows no alerts message when no active alerts', async () => {
    // Mock with no active alerts
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ 
          data: { ...mockAlertSummary, active_alerts: 0 }
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: [] })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockAlertRules })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockHealthSummary })
      } as Response);

    render(<AlertsMonitoring />);

    await waitFor(() => {
      fireEvent.click(screen.getByText('Alerts'));
    });

    expect(screen.getByText('No active alerts')).toBeInTheDocument();
  });
});