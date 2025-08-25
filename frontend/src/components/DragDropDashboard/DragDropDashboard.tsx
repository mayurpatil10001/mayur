import React, { useState, useEffect, useCallback, useRef } from 'react';
import './DragDropDashboard.css';

// Hook for auto-sizing content
const useAutoSize = (contentRef: React.RefObject<HTMLDivElement>, enabled: boolean) => {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!enabled || !contentRef.current) return;

    const measureContent = () => {
      const element = contentRef.current;
      if (!element) return;

      // Temporarily remove size constraints to measure natural size
      const originalWidth = element.style.width;
      const originalHeight = element.style.height;
      const originalOverflow = element.style.overflow;
      
      element.style.width = 'auto';
      element.style.height = 'auto';
      element.style.overflow = 'visible';
      
      // Force layout recalculation
      void element.offsetHeight;
      
      const rect = element.getBoundingClientRect();
      const scrollWidth = element.scrollWidth;
      const scrollHeight = element.scrollHeight;
      
      // Use the larger of the two measurements
      const naturalWidth = Math.max(rect.width, scrollWidth);
      const naturalHeight = Math.max(rect.height, scrollHeight);
      
      // Restore original styles
      element.style.width = originalWidth;
      element.style.height = originalHeight;
      element.style.overflow = originalOverflow;
      
      const newSize = {
        width: Math.ceil(naturalWidth) + 24, // Add padding
        height: Math.ceil(naturalHeight) + 68 // Add padding + header
      };
      
      setSize(newSize);
    };

    // Measure immediately and after a short delay to catch dynamic content
    measureContent();
    const timer = setTimeout(measureContent, 100);
    
    return () => clearTimeout(timer);
  }, [enabled]);

  return size;
};

interface DashboardItem {
  id: string;
  component: React.ReactNode;
  title: string;
  defaultPosition: { x: number; y: number; width: number; height: number };
  minWidth?: number;
  minHeight?: number;
  resizable?: boolean;
}

interface Position {
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
}

interface DragDropDashboardProps {
  items: DashboardItem[];
  storageKey?: string;
  className?: string;
}

interface DraggableItemProps {
  item: DashboardItem;
  position: Position;
  onPositionChange: (id: string, position: Partial<Position>) => void;
  onBringToFront: (id: string) => void;
}

const DraggableItem: React.FC<DraggableItemProps> = ({
  item,
  position,
  onPositionChange,
  onBringToFront
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [autoSizeEnabled, setAutoSizeEnabled] = useState(true);
  const dragRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  
  // Auto-size based on content
  const autoSize = useAutoSize(contentRef, autoSizeEnabled);
  
  // Update position when auto-size changes
  useEffect(() => {
    if (autoSizeEnabled && autoSize.width > 0 && autoSize.height > 0) {
      const newWidth = Math.max(autoSize.width, item.minWidth || 300);
      const newHeight = Math.max(autoSize.height, item.minHeight || 200);
      
      // Only update if significantly different to avoid infinite loops
      const widthDiff = Math.abs(newWidth - position.width);
      const heightDiff = Math.abs(newHeight - position.height);
      
      if (widthDiff > 5 || heightDiff > 5) {
        onPositionChange(item.id, { 
          width: newWidth, 
          height: newHeight 
        });
      }
    }
  }, [autoSize, autoSizeEnabled, item.id, item.minWidth, item.minHeight, onPositionChange, position.width, position.height]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const isHeader = target.classList.contains('dashboard-item-header') || 
                    target.classList.contains('dashboard-item-title') ||
                    target.closest('.dashboard-item-header');
    
    if (isHeader && !target.classList.contains('minimize-btn') && !target.classList.contains('maximize-btn') && !target.classList.contains('auto-size-btn')) {
      setIsDragging(true);
      
      // Calculate offset relative to container
      const container = dragRef.current?.parentElement;
      if (container) {
        const containerRect = container.getBoundingClientRect();
        setDragStart({ 
          x: e.clientX - containerRect.left - position.x, 
          y: e.clientY - containerRect.top - position.y 
        });
      }
      
      onBringToFront(item.id);
      e.preventDefault();
      e.stopPropagation();
    }
  }, [position.x, position.y, onBringToFront, item.id]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging) {
      // Calculate position relative to the dashboard container
      const container = dragRef.current?.parentElement;
      if (container) {
        const containerRect = container.getBoundingClientRect();
        // Remove Math.max(0, ...) to allow negative positions (moving to the left)
        const newX = e.clientX - containerRect.left - dragStart.x;
        const newY = e.clientY - containerRect.top - dragStart.y;
        
        onPositionChange(item.id, { x: newX, y: newY });
      }
    } else if (isResizing) {
      const newWidth = Math.max(item.minWidth || 300, e.clientX - position.x);
      const newHeight = Math.max(item.minHeight || 200, e.clientY - position.y);
      onPositionChange(item.id, { width: newWidth, height: newHeight });
    }
  }, [isDragging, isResizing, dragStart, position, onPositionChange, item.id, item.minWidth, item.minHeight]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setIsResizing(false);
  }, []);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    setIsResizing(true);
    setAutoSizeEnabled(false); // Disable auto-sizing when manually resizing
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const toggleAutoSize = useCallback(() => {
    setAutoSizeEnabled(!autoSizeEnabled);
  }, [autoSizeEnabled]);

  useEffect(() => {
    if (isDragging || isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none';
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.userSelect = '';
      };
    }
  }, [isDragging, isResizing, handleMouseMove, handleMouseUp]);

  return (
    <div
      ref={dragRef}
      className={`dashboard-item ${isDragging ? 'dragging' : ''} ${isResizing ? 'resizing' : ''}`}
      style={{
        position: 'absolute',
        left: position.x,
        top: position.y,
        width: position.width,
        height: position.height,
        zIndex: position.zIndex,
      }}
      onClick={() => onBringToFront(item.id)}
    >
      <div 
        className="dashboard-item-header"
        onMouseDown={handleMouseDown}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <span className="dashboard-item-title">{item.title}</span>
        <div className="dashboard-item-controls">
          <button 
            className={`auto-size-btn ${autoSizeEnabled ? 'active' : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              toggleAutoSize();
            }}
            title={autoSizeEnabled ? 'Disable Auto-Size' : 'Enable Auto-Size'}
          >
            📐
          </button>
          <button 
            className="minimize-btn"
            onClick={(e) => {
              e.stopPropagation();
              // Add minimize functionality
            }}
          >
            −
          </button>
          <button 
            className="maximize-btn"
            onClick={(e) => {
              e.stopPropagation();
              // Add maximize functionality
            }}
          >
            □
          </button>
        </div>
      </div>
      <div className="dashboard-item-content" ref={contentRef}>
        {item.component}
      </div>
      {item.resizable !== false && (
        <div 
          className="resize-handle"
          onMouseDown={handleResizeStart}
        />
      )}
    </div>
  );
};

const DragDropDashboard: React.FC<DragDropDashboardProps> = ({
  items,
  storageKey = 'dashboard-layout',
  className = ''
}) => {
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const [maxZIndex, setMaxZIndex] = useState(1000);
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialize positions
  useEffect(() => {
    const initializePositions = () => {
      const savedPositions = localStorage.getItem(storageKey);
      let initialPositions: Record<string, Position> = {};
      
      if (savedPositions) {
        try {
          const parsed = JSON.parse(savedPositions);
          // Validate that all items have positions
          const hasAllItems = items.every(item => parsed[item.id]);
          if (hasAllItems) {
            initialPositions = parsed;
          }
        } catch (error) {
          console.error('Failed to parse saved positions:', error);
        }
      }
      
      // If no saved positions or missing items, use defaults
      if (Object.keys(initialPositions).length === 0) {
        items.forEach((item, index) => {
          initialPositions[item.id] = {
            ...item.defaultPosition,
            zIndex: 1000 + index
          };
        });
      }
      
      setPositions(initialPositions);
      setIsInitialized(true);
    };

    if (items.length > 0) {
      initializePositions();
    }
  }, [items, storageKey]);

  // Save positions to localStorage
  useEffect(() => {
    if (isInitialized && Object.keys(positions).length > 0) {
      localStorage.setItem(storageKey, JSON.stringify(positions));
    }
  }, [positions, storageKey, isInitialized]);

  const handlePositionChange = useCallback((id: string, newPosition: Partial<Position>) => {
    setPositions(prev => ({
      ...prev,
      [id]: { ...prev[id], ...newPosition }
    }));
  }, []);

  const handleBringToFront = useCallback((id: string) => {
    const newZIndex = maxZIndex + 1;
    setMaxZIndex(newZIndex);
    handlePositionChange(id, { zIndex: newZIndex });
  }, [maxZIndex, handlePositionChange]);

  const resetLayout = useCallback(() => {
    const defaultPositions: Record<string, Position> = {};
    items.forEach((item, index) => {
      defaultPositions[item.id] = {
        ...item.defaultPosition,
        zIndex: 1000 + index
      };
    });
    setPositions(defaultPositions);
    localStorage.removeItem(storageKey);
    setMaxZIndex(1000 + items.length);
  }, [items, storageKey]);

  if (!isInitialized) {
    return <div className="dashboard-loading">Loading dashboard...</div>;
  }

  return (
    <div className={`drag-drop-dashboard ${className}`}>

      <div className="dashboard-container">
        {items.map((item) => {
          const position = positions[item.id];
          if (!position) return null;

          return (
            <DraggableItem
              key={item.id}
              item={item}
              position={position}
              onPositionChange={handlePositionChange}
              onBringToFront={handleBringToFront}
            />
          );
        })}
      </div>
    </div>
  );
};

export default DragDropDashboard;