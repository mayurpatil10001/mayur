import React, { useRef, useEffect, useState, useCallback } from 'react';
import './InteractiveChart.css';

interface ChartDataPoint {
  date: string;
  daily_pnl: number;
  cumulative_pnl: number;
  entry_time?: string;
  account?: string;
  time_slot?: string;
}

interface InteractiveChartProps {
  data: ChartDataPoint[];
  formatCurrency: (value: number) => string;
  width?: number;
  height?: number;
}

const InteractiveChart: React.FC<InteractiveChartProps> = ({
  data,
  formatCurrency,
  width = 1400,
  height = 600
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);

  // Flag for empty data — used in JSX conditional (NOT as early return, to satisfy Rules of Hooks)
  const isEmpty = !data || data.length === 0;

  // Calculate chart dimensions and data ranges (safe defaults when empty)
  const margin = { top: 50, right: 80, bottom: 80, left: 100 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  const pnlValues = isEmpty ? [0] : data.map(d => d.cumulative_pnl);
  const maxPnL = pnlValues.reduce((a, b) => b > a ? b : a, pnlValues[0]);
  const minPnL = pnlValues.reduce((a, b) => b < a ? b : a, pnlValues[0]);
  // Dynamic scaling with 10% padding
  const padding = (maxPnL - minPnL) * 0.1 || 100;
  const domainMin = minPnL - padding;
  const domainMax = maxPnL + padding;
  const domainRange = domainMax - domainMin || 1000;

  // Helper to map P&L to Y-coordinate
  const getY = useCallback((pnl: number) => {
    return margin.top + chartHeight - ((pnl - domainMin) / domainRange) * chartHeight;
  }, [domainMin, domainRange, margin.top, chartHeight]);

  // Reset zoom and pan
  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Zoom in/out functions
  const zoomIn = useCallback(() => {
    setZoom(prev => Math.min(prev * 1.5, 10));
  }, []);

  const zoomOut = useCallback(() => {
    setZoom(prev => Math.max(prev / 1.5, 0.1));
  }, []);

  // Handle mouse wheel for zooming
  const handleWheel = useCallback((event: React.WheelEvent) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prev => Math.max(0.1, Math.min(10, prev * delta)));
  }, []);

  // Handle mouse events for panning
  const handleMouseDown = useCallback((event: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: event.clientX - pan.x, y: event.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback((event: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: event.clientX - dragStart.x,
        y: event.clientY - dragStart.y
      });
    }
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Generate clean chart path
  const generatePath = useCallback(() => {
    if (data.length === 0) return '';

    const pointSpacing = (chartWidth * zoom) / Math.max(data.length - 1, 1);

    let pathData = '';
    data.forEach((point, index) => {
      const x = margin.left + index * pointSpacing + pan.x;
      const y = getY(point.cumulative_pnl);

      if (index === 0) {
        pathData += `M ${x} ${y}`;
      } else {
        pathData += ` L ${x} ${y}`;
      }
    });

    return pathData;
  }, [data, chartWidth, zoom, pan, margin.left, getY]);

  // Generate grid lines
  const generateGridLines = useCallback(() => {
    const gridLines = [];
    const ySteps = 8;
    const xSteps = Math.min(20, data.length);

    // Horizontal grid lines
    for (let i = 0; i <= ySteps; i++) {
      const ratio = i / ySteps;
      const y = margin.top + chartHeight * (1 - ratio);
      const value = domainMin + ratio * domainRange;

      gridLines.push(
        <g key={`h-grid-${i}`}>
          <line
            x1={margin.left}
            y1={y}
            x2={margin.left + chartWidth}
            y2={y}
            stroke="#f3f4f6"
            strokeWidth="1"
            strokeDasharray="2,2"
          />
          <text
            x={margin.left - 10}
            y={y + 4}
            fontSize="12"
            fill="#6b7280"
            textAnchor="end"
          >
            {formatCurrency(value)}
          </text>
        </g>
      );
    }

    // Vertical grid lines (dates) - Show fewer dates with better spacing
    const maxDateLabels = Math.min(12, Math.floor(chartWidth / 100)); // One date per 100px
    for (let i = 0; i <= maxDateLabels; i++) {
      const dataIndex = Math.floor((i * (data.length - 1)) / maxDateLabels);
      if (dataIndex < data.length) {
        const x = margin.left + (dataIndex * chartWidth * zoom / Math.max(data.length - 1, 1)) + pan.x;
        if (x >= margin.left && x <= margin.left + chartWidth) {
          const date = new Date(data[dataIndex].date);
          const dateStr = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: data.length > 365 ? '2-digit' : undefined // Show year only for long periods
          });

          gridLines.push(
            <g key={`v-grid-${i}`}>
              <line
                x1={x}
                y1={margin.top}
                x2={x}
                y2={margin.top + chartHeight}
                stroke="#f3f4f6"
                strokeWidth="1"
                strokeDasharray="2,2"
              />
              <text
                x={x}
                y={height - 60}
                fontSize="12"
                fill="#6b7280"
                textAnchor="middle"
                transform={`rotate(-45, ${x}, ${height - 60})`}
                fontWeight="500"
              >
                {dateStr}
              </text>
            </g>
          );
        }
      }
    }

    return gridLines;
  }, [data, chartWidth, chartHeight, margin, domainMin, domainRange, zoom, pan, formatCurrency, height]);

  // Generate data points
  const generateDataPoints = useCallback(() => {
    const pointSpacing = (chartWidth * zoom) / Math.max(data.length - 1, 1);

    return data.map((point, index) => {
      const x = margin.left + index * pointSpacing + pan.x;
      const y = getY(point.cumulative_pnl);

      // Only render points that are visible
      if (x < margin.left - 20 || x > margin.left + chartWidth + 20) {
        return null;
      }

      return (
        <circle
          key={index}
          cx={x}
          cy={y}
          r={hoveredPoint === index ? 5 : 2}
          fill={point.cumulative_pnl >= 0 ? '#10b981' : '#ef4444'}
          stroke="white"
          strokeWidth="1"
          className="chart-point"
          onMouseEnter={() => setHoveredPoint(index)}
          onMouseLeave={() => setHoveredPoint(null)}
          opacity="0.8"
        />
      );
    }).filter(Boolean);
  }, [data, chartWidth, zoom, pan, margin.left, getY, hoveredPoint]);

  if (isEmpty) {
    return (
      <div className="interactive-chart" style={{ margin: 0 }}>
        <div style={{
          width,
          height: Math.min(height, 300),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)',
          borderRadius: '12px',
          border: '1px solid #dee2e6',
          color: '#6c757d',
          flexDirection: 'column',
          gap: '10px'
        }}>
          <span style={{ fontSize: '40px' }}>📊</span>
          <span style={{ fontSize: '16px', fontWeight: 500 }}>No chart data available</span>
          <span style={{ fontSize: '13px', opacity: 0.7 }}>Select a symbol and time horizon to view the equity curve</span>
        </div>
      </div>
    );
  }

  return (
    <div className="interactive-chart" style={{ margin: 0 }}>
      <div className="chart-controls">
        <div className="zoom-controls">
          <button onClick={zoomIn} className="zoom-btn">
            <span>🔍+</span>
          </button>
          <button onClick={zoomOut} className="zoom-btn">
            <span>🔍-</span>
          </button>
          <button onClick={resetView} className="reset-btn">
            Reset View
          </button>
        </div>
        <div className="chart-info">
          <span>Zoom: {(zoom * 100).toFixed(0)}%</span>
          <span>Points: {data.length}</span>
        </div>
      </div>

      <div className="chart-container">
        <svg
          ref={svgRef}
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
        >
          {/* Background */}
          <rect
            width={width}
            height={height}
            fill="white"
            stroke="#e5e7eb"
            strokeWidth="1"
          />

          {/* Grid lines */}
          {generateGridLines()}

          {/* Chart area clipping */}
          <defs>
            <clipPath id="chart-area">
              <rect
                x={margin.left}
                y={margin.top}
                width={chartWidth}
                height={chartHeight}
              />
            </clipPath>
          </defs>

          {/* P&L line */}
          <g clipPath="url(#chart-area)">
            {/* Clean single path line */}
            {data.length > 1 && (
              <path
                d={generatePath()}
                fill="none"
                stroke={data[data.length - 1]?.cumulative_pnl >= 0 ? '#10b981' : '#ef4444'}
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.9"
              />
            )}

            {/* Data points - only show on hover or when zoomed in */}
            {(zoom > 1.5 || hoveredPoint !== null) && generateDataPoints()}
          </g>

          {/* Axes */}
          <line
            x1={margin.left}
            y1={margin.top}
            x2={margin.left}
            y2={margin.top + chartHeight}
            stroke="#374151"
            strokeWidth="2"
          />
          <line
            x1={margin.left}
            y1={margin.top + chartHeight}
            x2={margin.left + chartWidth}
            y2={margin.top + chartHeight}
            stroke="#374151"
            strokeWidth="2"
          />

          {/* Chart title */}
          <text
            x={width / 2}
            y={25}
            fontSize="16"
            fontWeight="600"
            fill="#374151"
            textAnchor="middle"
          >
            Cumulative P&L Over Time
          </text>

          {/* Tooltip */}
          {hoveredPoint !== null && data[hoveredPoint] && (
            <g>
              <rect
                x={margin.left + (hoveredPoint * chartWidth * zoom / Math.max(data.length - 1, 1)) + pan.x + 10}
                y={getY(data[hoveredPoint].cumulative_pnl) - 40}
                width="200"
                height="60"
                fill="rgba(0, 0, 0, 0.9)"
                rx="4"
                stroke="rgba(255, 255, 255, 0.2)"
                strokeWidth="1"
              />
              <text
                x={margin.left + (hoveredPoint * chartWidth * zoom / Math.max(data.length - 1, 1)) + pan.x + 20}
                y={getY(data[hoveredPoint].cumulative_pnl) - 20}
                fontSize="12"
                fill="white"
                fontWeight="500"
              >
                Date: {data[hoveredPoint].date}
              </text>
              <text
                x={margin.left + (hoveredPoint * chartWidth * zoom / Math.max(data.length - 1, 1)) + pan.x + 20}
                y={getY(data[hoveredPoint].cumulative_pnl) - 5}
                fontSize="12"
                fill="white"
                fontWeight="500"
              >
                P&L: {formatCurrency(data[hoveredPoint].cumulative_pnl)}
              </text>
            </g>
          )}
        </svg>
      </div>


    </div>
  );
};

export default InteractiveChart;