import logging
from datetime import datetime

from flask_socketio import emit, join_room, leave_room
from ..utils.event_queue import register_websocket_callbacks, EventType

logger = logging.getLogger(__name__)

# 事件类型定义
EVENT_TYPES = {
    'SYSTEM_METRICS': 'system_metrics',
    'MODEL_STATUS': 'model_status',
    'NOTIFICATION': 'notification'
}


def register_monitor_events(socketio):
    """注册监控相关的WebSocket事件"""
    
    @socketio.on('subscribe_system_metrics')
    def on_subscribe_system_metrics():
        """订阅系统指标监控"""
        join_room('system_metrics')
        emit('subscribed', {
            'event_type': 'system_metrics',
            'message': 'System metrics subscription successful'
        })
        logger.info("Client subscribed to system metrics")
    
    @socketio.on('unsubscribe_system_metrics')
    def on_unsubscribe_system_metrics():
        """取消订阅系统指标监控"""
        leave_room('system_metrics')
        emit('unsubscribed', {'event_type': 'system_metrics'})
        logger.info("Client unsubscribed from system metrics")
    
    @socketio.on('subscribe_model_status')
    def on_subscribe_model_status():
        """订阅模型状态监控"""
        join_room('model_status')
        emit('subscribed', {
            'event_type': 'model_status',
            'message': 'Model status subscription successful'
        })
        logger.info("Client subscribed to model status")
    
    @socketio.on('unsubscribe_model_status')
    def on_unsubscribe_model_status():
        """取消订阅模型状态监控"""
        leave_room('model_status')
        emit('unsubscribed', {'event_type': 'model_status'})
        logger.info("Client unsubscribed from model status")
    
    @socketio.on('subscribe_notifications')
    def on_subscribe_notifications():
        """订阅通知"""
        join_room('notifications')
        emit('subscribed', {
            'event_type': 'notification',
            'message': 'Notification subscription successful'
        })
        logger.info("Client subscribed to notifications")
    
    @socketio.on('unsubscribe_notifications')
    def on_unsubscribe_notifications():
        """取消订阅通知"""
        leave_room('notifications')
        emit('unsubscribed', {'event_type': 'notification'})
        logger.info("Client unsubscribed from notifications")
    
    @socketio.on('disconnect')
    def on_monitor_disconnect():
        """客户端断开连接"""
        logger.info("Monitor client disconnected")


def _broadcast_system_metrics_from_queue(event_data):
    """从队列广播系统指标到订阅的客户端"""
    try:
        from . import socketio
        socketio.emit('system_metrics', event_data, room='system_metrics')
        logger.debug("System metrics broadcasted from queue")
    except Exception as e:
        logger.error(f"Failed to broadcast system metrics: {e}")


def _broadcast_model_status_from_queue(event_data):
    """从队列广播模型状态到订阅的客户端"""
    try:
        from . import socketio
        socketio.emit('model_status', event_data, room='model_status')
        logger.debug("Model status broadcasted from queue")
    except Exception as e:
        logger.error(f"Failed to broadcast model status: {e}")


def _broadcast_notification_from_queue(event_data):
    """从队列广播通知到订阅的客户端"""
    try:
        from . import socketio
        socketio.emit('notification', event_data, room='notifications')
        logger.debug(f"Notification broadcasted from queue: {event_data.get('notification', {}).get('type')} - {event_data.get('notification', {}).get('message')}")
    except Exception as e:
        logger.error(f"Failed to broadcast notification: {e}")


def init_websocket_event_system():
    """初始化WebSocket事件系统"""
    try:
        # 注册广播回调函数到事件队列
        callbacks = {
            EventType.SYSTEM_METRICS: _broadcast_system_metrics_from_queue,
            EventType.MODEL_STATUS: _broadcast_model_status_from_queue,
            EventType.NOTIFICATION: _broadcast_notification_from_queue
        }
        
        register_websocket_callbacks(callbacks)
        logger.info("WebSocket event system initialized with queue callbacks")
        
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket event system: {str(e)}")