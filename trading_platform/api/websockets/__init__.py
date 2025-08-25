"""
WebSocket endpoints for real-time trading data updates.

This module provides WebSocket connections for real-time monitoring
of trading performance, alerts, and system status.
"""

from .monitoring_websocket import MonitoringWebSocket

__all__ = ['MonitoringWebSocket']