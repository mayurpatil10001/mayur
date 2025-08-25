"""
WebSocket handler for real-time monitoring data updates.

This module provides WebSocket connections for streaming real-time updates
of trading performance metrics, alerts, and system status to connected clients.

Requirements: 8.1, 8.2, 10.1
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from dataclasses import asdict
import uuid

from ...services.monitoring.time_bin_monitoring_service import (
    TimeBinMonitoringService, PerformanceSnapshot, MonitoringAlert
)
from ...services.monitoring.alerts_engine import AlertsEngine
from ...services.time_bin_analyzer import TimeBin

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time monitoring."""
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Connection subscriptions
        self.time_bin_subscriptions: Dict[str, Set[TimeBin]] = {}
        self.alert_subscriptions: Dict[str, bool] = {}
        self.system_status_subscriptions: Dict[str, bool] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        logger.info("ConnectionManager initialized")
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Accept a WebSocket connection and assign client ID."""
        await websocket.accept()
        
        if not client_id:
            client_id = str(uuid.uuid4())
        
        self.active_connections[client_id] = websocket
        self.time_bin_subscriptions[client_id] = set()
        self.alert_subscriptions[client_id] = False
        self.system_status_subscriptions[client_id] = False
        self.connection_metadata[client_id] = {
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0
        }
        
        logger.info(f"WebSocket client connected: {client_id}")
        return client_id
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            del self.time_bin_subscriptions[client_id]
            del self.alert_subscriptions[client_id]
            del self.system_status_subscriptions[client_id]
            del self.connection_metadata[client_id]
            logger.info(f"WebSocket client disconnected: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_text(json.dumps(message))
                
                # Update metadata
                if client_id in self.connection_metadata:
                    self.connection_metadata[client_id]['last_activity'] = datetime.now()
                    self.connection_metadata[client_id]['message_count'] += 1
                    
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {str(e)}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
                
                # Update metadata
                if client_id in self.connection_metadata:
                    self.connection_metadata[client_id]['last_activity'] = datetime.now()
                    self.connection_metadata[client_id]['message_count'] += 1
                    
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {str(e)}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    def subscribe_to_time_bin(self, client_id: str, time_bin: TimeBin):
        """Subscribe a client to time-bin updates."""
        if client_id in self.time_bin_subscriptions:
            self.time_bin_subscriptions[client_id].add(time_bin)
            logger.info(f"Client {client_id} subscribed to time-bin {time_bin}")
    
    def unsubscribe_from_time_bin(self, client_id: str, time_bin: TimeBin):
        """Unsubscribe a client from time-bin updates."""
        if client_id in self.time_bin_subscriptions:
            self.time_bin_subscriptions[client_id].discard(time_bin)
            logger.info(f"Client {client_id} unsubscribed from time-bin {time_bin}")
    
    def subscribe_to_alerts(self, client_id: str):
        """Subscribe a client to alert updates."""
        if client_id in self.alert_subscriptions:
            self.alert_subscriptions[client_id] = True
            logger.info(f"Client {client_id} subscribed to alerts")
    
    def subscribe_to_system_status(self, client_id: str):
        """Subscribe a client to system status updates."""
        if client_id in self.system_status_subscriptions:
            self.system_status_subscriptions[client_id] = True
            logger.info(f"Client {client_id} subscribed to system status")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about WebSocket connections."""
        total_connections = len(self.active_connections)
        total_subscriptions = sum(len(subs) for subs in self.time_bin_subscriptions.values())
        alert_subscribers = sum(1 for subscribed in self.alert_subscriptions.values() if subscribed)
        
        return {
            'total_connections': total_connections,
            'total_time_bin_subscriptions': total_subscriptions,
            'alert_subscribers': alert_subscribers,
            'uptime_seconds': 0  # Would calculate actual uptime
        }


class MonitoringWebSocket:
    """
    WebSocket handler for real-time monitoring data.
    
    Provides real-time streaming of performance metrics, alerts, and system status
    to connected WebSocket clients with subscription management.
    """
    
    def __init__(
        self,
        monitoring_service: Optional[TimeBinMonitoringService] = None,
        alerts_engine: Optional[AlertsEngine] = None
    ):
        """Initialize the WebSocket handler."""
        self.monitoring_service = monitoring_service
        self.alerts_engine = alerts_engine
        self.connection_manager = ConnectionManager()
        
        # Background tasks
        self.broadcast_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        
        # Data broadcasting intervals
        self.performance_broadcast_interval = 5  # seconds
        self.status_broadcast_interval = 30  # seconds
        
        # Setup callbacks if services are available
        if self.monitoring_service:
            self.monitoring_service.add_performance_callback(self._handle_performance_update)
            self.monitoring_service.add_alert_callback(self._handle_alert_update)
        
        if self.alerts_engine:
            self.alerts_engine.add_alert_callback(self._handle_alert_update)
        
        logger.info("MonitoringWebSocket initialized")
    
    async def start_broadcasting(self):
        """Start background broadcasting tasks."""
        if not self.broadcast_task:
            self.broadcast_task = asyncio.create_task(self._broadcasting_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("WebSocket broadcasting started")
    
    async def stop_broadcasting(self):
        """Stop background broadcasting tasks."""
        self.stop_event.set()
        
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
            self.broadcast_task = None
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
        
        logger.info("WebSocket broadcasting stopped")
    
    async def handle_websocket(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Handle a WebSocket connection."""
        client_id = await self.connection_manager.connect(websocket, client_id)
        
        try:
            # Send initial connection confirmation
            await self.connection_manager.send_personal_message({
                'type': 'connection_established',
                'client_id': client_id,
                'timestamp': datetime.now().isoformat(),
                'available_subscriptions': [
                    'time_bin_performance',
                    'alerts',
                    'system_status'
                ]
            }, client_id)
            
            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_client_message(client_id, message)
                    
                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    await self.connection_manager.send_personal_message({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }, client_id)
                except Exception as e:
                    logger.error(f"Error handling message from {client_id}: {str(e)}")
                    await self.connection_manager.send_personal_message({
                        'type': 'error',
                        'message': f'Message handling error: {str(e)}'
                    }, client_id)
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {str(e)}")
        finally:
            self.connection_manager.disconnect(client_id)
    
    async def _handle_client_message(self, client_id: str, message: Dict[str, Any]):
        """Handle incoming client messages."""
        message_type = message.get('type')
        
        if message_type == 'subscribe_time_bin':
            await self._handle_time_bin_subscription(client_id, message)
        
        elif message_type == 'unsubscribe_time_bin':
            await self._handle_time_bin_unsubscription(client_id, message)
        
        elif message_type == 'subscribe_alerts':
            self.connection_manager.subscribe_to_alerts(client_id)
            await self.connection_manager.send_personal_message({
                'type': 'subscription_confirmed',
                'subscription': 'alerts'
            }, client_id)
        
        elif message_type == 'subscribe_system_status':
            self.connection_manager.subscribe_to_system_status(client_id)
            await self.connection_manager.send_personal_message({
                'type': 'subscription_confirmed',
                'subscription': 'system_status'
            }, client_id)
        
        elif message_type == 'get_current_data':
            await self._send_current_data(client_id, message)
        
        elif message_type == 'ping':
            await self.connection_manager.send_personal_message({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            }, client_id)
        
        else:
            await self.connection_manager.send_personal_message({
                'type': 'error',
                'message': f'Unknown message type: {message_type}'
            }, client_id)
    
    async def _handle_time_bin_subscription(self, client_id: str, message: Dict[str, Any]):
        """Handle time-bin subscription request."""
        try:
            account_name = message.get('account_name')
            hour = message.get('hour')
            minute_bin = message.get('minute_bin')
            
            if not all([account_name, hour is not None, minute_bin is not None]):
                raise ValueError("Missing required fields: account_name, hour, minute_bin")
            
            time_bin = TimeBin(account_name, hour, minute_bin)
            self.connection_manager.subscribe_to_time_bin(client_id, time_bin)
            
            await self.connection_manager.send_personal_message({
                'type': 'subscription_confirmed',
                'subscription': 'time_bin_performance',
                'time_bin': {
                    'account_name': account_name,
                    'hour': hour,
                    'minute_bin': minute_bin
                }
            }, client_id)
            
        except Exception as e:
            await self.connection_manager.send_personal_message({
                'type': 'error',
                'message': f'Subscription error: {str(e)}'
            }, client_id)
    
    async def _handle_time_bin_unsubscription(self, client_id: str, message: Dict[str, Any]):
        """Handle time-bin unsubscription request."""
        try:
            account_name = message.get('account_name')
            hour = message.get('hour')
            minute_bin = message.get('minute_bin')
            
            if not all([account_name, hour is not None, minute_bin is not None]):
                raise ValueError("Missing required fields: account_name, hour, minute_bin")
            
            time_bin = TimeBin(account_name, hour, minute_bin)
            self.connection_manager.unsubscribe_from_time_bin(client_id, time_bin)
            
            await self.connection_manager.send_personal_message({
                'type': 'unsubscription_confirmed',
                'time_bin': {
                    'account_name': account_name,
                    'hour': hour,
                    'minute_bin': minute_bin
                }
            }, client_id)
            
        except Exception as e:
            await self.connection_manager.send_personal_message({
                'type': 'error',
                'message': f'Unsubscription error: {str(e)}'
            }, client_id)
    
    async def _send_current_data(self, client_id: str, message: Dict[str, Any]):
        """Send current data for requested subscriptions."""
        data_type = message.get('data_type')
        
        try:
            if data_type == 'time_bin_performance':
                await self._send_current_time_bin_data(client_id, message)
            elif data_type == 'alerts':
                await self._send_current_alerts(client_id)
            elif data_type == 'system_status':
                await self._send_current_system_status(client_id)
            else:
                await self.connection_manager.send_personal_message({
                    'type': 'error',
                    'message': f'Unknown data type: {data_type}'
                }, client_id)
                
        except Exception as e:
            await self.connection_manager.send_personal_message({
                'type': 'error',
                'message': f'Data retrieval error: {str(e)}'
            }, client_id)
    
    async def _send_current_time_bin_data(self, client_id: str, message: Dict[str, Any]):
        """Send current time-bin performance data."""
        if not self.monitoring_service:
            await self.connection_manager.send_personal_message({
                'type': 'error',
                'message': 'Monitoring service not available'
            }, client_id)
            return
        
        account_name = message.get('account_name')
        hour = message.get('hour')
        minute_bin = message.get('minute_bin')
        
        if not all([account_name, hour is not None, minute_bin is not None]):
            raise ValueError("Missing required fields for time-bin data")
        
        time_bin = TimeBin(account_name, hour, minute_bin)
        
        # Get recent performance history
        history = self.monitoring_service.get_performance_history(time_bin, hours=24)
        
        response_data = {
            'type': 'current_time_bin_data',
            'time_bin': {
                'account_name': account_name,
                'hour': hour,
                'minute_bin': minute_bin
            },
            'history_count': len(history),
            'latest_snapshot': None,
            'timestamp': datetime.now().isoformat()
        }
        
        if history:
            latest = history[-1]  # Most recent
            response_data['latest_snapshot'] = {
                'timestamp': latest.timestamp.isoformat(),
                'trades_count': latest.trades_count,
                'total_pnl': latest.total_pnl,
                'win_rate': latest.win_rate,
                'avg_trade_pnl': latest.avg_trade_pnl,
                'max_drawdown': latest.max_drawdown,
                'sharpe_ratio': latest.sharpe_ratio,
                'profit_factor': latest.profit_factor,
                'statistical_significance': latest.statistical_significance,
                'p_value': latest.p_value,
                'market_correlation': latest.market_correlation
            }
        
        await self.connection_manager.send_personal_message(response_data, client_id)
    
    async def _send_current_alerts(self, client_id: str):
        """Send current active alerts."""
        alerts_data = []
        
        if self.monitoring_service:
            alerts = self.monitoring_service.get_active_alerts()
            alerts_data.extend(alerts)
        
        if self.alerts_engine:
            alerts = self.alerts_engine.get_active_alerts()
            alerts_data.extend(alerts)
        
        # Convert alerts to serializable format
        alerts_json = []
        for alert in alerts_data:
            alerts_json.append({
                'alert_id': alert.alert_id,
                'timestamp': alert.timestamp.isoformat(),
                'time_bin': {
                    'account_name': alert.time_bin.account_name,
                    'hour': alert.time_bin.hour,
                    'minute_bin': alert.time_bin.minute_bin
                },
                'alert_type': alert.alert_type.value,
                'severity': alert.severity.value,
                'message': alert.message,
                'is_acknowledged': alert.is_acknowledged,
                'acknowledged_by': alert.acknowledged_by,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
            })
        
        await self.connection_manager.send_personal_message({
            'type': 'current_alerts',
            'alerts': alerts_json,
            'count': len(alerts_json),
            'timestamp': datetime.now().isoformat()
        }, client_id)
    
    async def _send_current_system_status(self, client_id: str):
        """Send current system status."""
        status_data = {
            'type': 'system_status',
            'timestamp': datetime.now().isoformat(),
            'monitoring_service': None,
            'alerts_engine': None,
            'websocket_connections': self.connection_manager.get_connection_stats()
        }
        
        if self.monitoring_service:
            status_data['monitoring_service'] = self.monitoring_service.get_monitoring_status()
        
        if self.alerts_engine:
            status_data['alerts_engine'] = self.alerts_engine.get_engine_status()
        
        await self.connection_manager.send_personal_message(status_data, client_id)
    
    async def _broadcasting_loop(self):
        """Main broadcasting loop for periodic updates."""
        logger.info("Starting WebSocket broadcasting loop")
        
        last_performance_broadcast = datetime.now()
        last_status_broadcast = datetime.now()
        
        while not self.stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # Broadcast performance updates
                if (current_time - last_performance_broadcast).seconds >= self.performance_broadcast_interval:
                    await self._broadcast_performance_updates()
                    last_performance_broadcast = current_time
                
                # Broadcast status updates
                if (current_time - last_status_broadcast).seconds >= self.status_broadcast_interval:
                    await self._broadcast_system_status()
                    last_status_broadcast = current_time
                
                # Wait before next iteration
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcasting loop: {str(e)}")
                await asyncio.sleep(5)
        
        logger.info("WebSocket broadcasting loop stopped")
    
    async def _broadcast_performance_updates(self):
        """Broadcast performance updates to subscribed clients."""
        if not self.monitoring_service:
            return
        
        # Get all unique time-bins that clients are subscribed to
        all_time_bins = set()
        for time_bins in self.connection_manager.time_bin_subscriptions.values():
            all_time_bins.update(time_bins)
        
        # Send updates for each subscribed time-bin
        for time_bin in all_time_bins:
            try:
                # Get recent performance data
                history = self.monitoring_service.get_performance_history(time_bin, hours=1)
                
                if history:
                    latest_snapshot = history[-1]
                    
                    update_message = {
                        'type': 'performance_update',
                        'time_bin': {
                            'account_name': time_bin.account_name,
                            'hour': time_bin.hour,
                            'minute_bin': time_bin.minute_bin
                        },
                        'snapshot': {
                            'timestamp': latest_snapshot.timestamp.isoformat(),
                            'trades_count': latest_snapshot.trades_count,
                            'total_pnl': latest_snapshot.total_pnl,
                            'win_rate': latest_snapshot.win_rate,
                            'avg_trade_pnl': latest_snapshot.avg_trade_pnl,
                            'max_drawdown': latest_snapshot.max_drawdown,
                            'sharpe_ratio': latest_snapshot.sharpe_ratio,
                            'profit_factor': latest_snapshot.profit_factor,
                            'statistical_significance': latest_snapshot.statistical_significance,
                            'p_value': latest_snapshot.p_value
                        },
                        'broadcast_timestamp': datetime.now().isoformat()
                    }
                    
                    # Send to subscribed clients
                    for client_id, subscribed_time_bins in self.connection_manager.time_bin_subscriptions.items():
                        if time_bin in subscribed_time_bins:
                            await self.connection_manager.send_personal_message(update_message, client_id)
            
            except Exception as e:
                logger.error(f"Error broadcasting performance update for {time_bin}: {str(e)}")
    
    async def _broadcast_system_status(self):
        """Broadcast system status to subscribed clients."""
        status_message = {
            'type': 'system_status_update',
            'timestamp': datetime.now().isoformat(),
            'monitoring_service': None,
            'alerts_engine': None,
            'websocket_connections': self.connection_manager.get_connection_stats()
        }
        
        if self.monitoring_service:
            status_message['monitoring_service'] = self.monitoring_service.get_monitoring_status()
        
        if self.alerts_engine:
            status_message['alerts_engine'] = self.alerts_engine.get_engine_status()
        
        # Send to clients subscribed to system status
        for client_id, subscribed in self.connection_manager.system_status_subscriptions.items():
            if subscribed:
                await self.connection_manager.send_personal_message(status_message, client_id)
    
    async def _cleanup_loop(self):
        """Periodic cleanup of stale connections."""
        while not self.stop_event.is_set():
            try:
                # Clean up connections that haven't been active
                cutoff_time = datetime.now() - timedelta(minutes=30)
                stale_connections = []
                
                for client_id, metadata in self.connection_manager.connection_metadata.items():
                    if metadata['last_activity'] < cutoff_time:
                        stale_connections.append(client_id)
                
                for client_id in stale_connections:
                    logger.info(f"Cleaning up stale connection: {client_id}")
                    self.connection_manager.disconnect(client_id)
                
                # Wait before next cleanup
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {str(e)}")
                await asyncio.sleep(60)
    
    def _handle_performance_update(self, snapshot: PerformanceSnapshot):
        """Handle performance update callback from monitoring service."""
        # This method will be called by the monitoring service
        # We could queue real-time updates here, but the broadcasting loop handles regular updates
        pass
    
    def _handle_alert_update(self, alert: MonitoringAlert):
        """Handle alert update callback."""
        # Create alert message
        alert_message = {
            'type': 'alert_update',
            'alert': {
                'alert_id': alert.alert_id,
                'timestamp': alert.timestamp.isoformat(),
                'time_bin': {
                    'account_name': alert.time_bin.account_name,
                    'hour': alert.time_bin.hour,
                    'minute_bin': alert.time_bin.minute_bin
                },
                'alert_type': alert.alert_type.value,
                'severity': alert.severity.value,
                'message': alert.message,
                'is_acknowledged': alert.is_acknowledged
            },
            'broadcast_timestamp': datetime.now().isoformat()
        }
        
        # Send to clients subscribed to alerts
        async def send_alert():
            for client_id, subscribed in self.connection_manager.alert_subscriptions.items():
                if subscribed:
                    await self.connection_manager.send_personal_message(alert_message, client_id)
        
        # Schedule the coroutine
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(send_alert())
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return {
            **self.connection_manager.get_connection_stats(),
            'broadcasting_active': self.broadcast_task is not None and not self.broadcast_task.done()
        }