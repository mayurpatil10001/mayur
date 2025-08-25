import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import MetricCard from './MetricCard';

describe('MetricCard', () => {
  const mockProps = {
    title: 'Total Return',
    value: 15000.50,
    subtitle: 'Over 6 months',
    trend: 'up' as const,
    trendValue: '+5.2%',
  };

  it('renders with basic props', () => {
    render(<MetricCard title="Test Metric" value="100" />);
    
    expect(screen.getByText('Test Metric')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('displays formatted numerical values correctly', () => {
    render(<MetricCard title="Large Number" value={1234567} />);
    
    expect(screen.getByText('1.2M')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<MetricCard title="Loading Metric" value="100" isLoading={true} />);
    
    expect(screen.getByText('Loading Metric')).toBeInTheDocument();
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('displays trend information when provided', () => {
    render(<MetricCard {...mockProps} />);
    
    expect(screen.getByText('Total Return')).toBeInTheDocument();
    expect(screen.getByText('15K')).toBeInTheDocument();
    expect(screen.getByText('Over 6 months')).toBeInTheDocument();
    expect(screen.getByText('+5.2%')).toBeInTheDocument();
  });

  it('handles click events when clickable', () => {
    const mockClick = jest.fn();
    render(<MetricCard title="Clickable" value="100" onClick={mockClick} />);
    
    const card = screen.getByText('Clickable').closest('.metric-card');
    fireEvent.click(card!);
    
    expect(mockClick).toHaveBeenCalledTimes(1);
  });

  it('applies correct CSS classes based on trend', () => {
    render(<MetricCard title="Up Trend" value="100" trend="up" trendValue="+10%" />);
    
    expect(screen.getByText('+10%').closest('.metric-card-trend')).toHaveClass('trend-up');
  });

  it('renders icon when provided', () => {
    render(<MetricCard title="With Icon" value="100" icon="💰" />);
    
    expect(screen.getByText('💰')).toBeInTheDocument();
  });
});