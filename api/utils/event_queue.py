"""
事件队列管理器
用于解耦服务层和WebSocket广播层
"""

import logging
import queue
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    SYSTEM_METRICS = "system_metrics"
    MODEL_STATUS = "model_status"
    NOTIFICATION = "notification"


class EventQueue:
    """事件队列管理器"""
    
    def __init__(self):
        # 为每种事件类型创建独立的队列
        self.queues = {
            EventType.SYSTEM_METRICS: queue.Queue(),
            EventType.MODEL_STATUS: queue.Queue(),
            EventType.NOTIFICATION: queue.Queue()
        }
        
        # 队列监听器线程
        self.listeners = {}
        self.running = False
        
        # WebSocket广播回调函数
        self.broadcast_callbacks = {}
        
        logger.info("Event queue manager initialized")
    
    def register_broadcast_callback(self, event_type: EventType, callback):
        """注册WebSocket广播回调函数"""
        self.broadcast_callbacks[event_type] = callback
        logger.info(f"Registered broadcast callback for {event_type.value}")
    
    def push_system_metrics(self, metrics: list, timestamp: str = None, interval: int = None):
        """推送系统指标事件到队列"""
        event_data = {
            'type': 'system_metrics',
            'metrics': metrics,
            'timestamp': timestamp or datetime.utcnow().isoformat(),
            'interval': interval
        }
        
        self.queues[EventType.SYSTEM_METRICS].put(event_data)
        logger.debug(f"System metrics pushed to queue: {len(metrics)} metrics")
    
    def push_model_status(self, models: list, timestamp: str = None, interval: int = None):
        """推送模型状态事件到队列"""
        event_data = {
            'type': 'model_status',
            'models': models,
            'timestamp': timestamp or datetime.utcnow().isoformat(),
            'interval': interval
        }
        
        self.queues[EventType.MODEL_STATUS].put(event_data)
        logger.debug(f"Model status pushed to queue: {len(models)} models")
    
    def push_notification(self, notification: dict, timestamp: str = None):
        """推送通知事件到队列"""
        event_data = {
            'type': 'notification',
            'notification': notification,
            'timestamp': timestamp or datetime.utcnow().isoformat()
        }
        
        self.queues[EventType.NOTIFICATION].put(event_data)
        logger.debug(f"Notification pushed to queue: {notification.get('type')} - {notification.get('message')}")
    
    def start_listeners(self):
        """启动队列监听器"""
        if self.running:
            return
        
        self.running = True
        
        for event_type in EventType:
            listener_thread = threading.Thread(
                target=self._queue_listener,
                args=(event_type,),
                daemon=True,
                name=f"EventQueue-{event_type.value}"
            )
            listener_thread.start()
            self.listeners[event_type] = listener_thread
            
        logger.info("Event queue listeners started")
    
    def stop_listeners(self):
        """停止队列监听器"""
        self.running = False
        
        # 向所有队列发送停止信号
        for event_type in EventType:
            self.queues[event_type].put(None)  # 停止信号
        
        # 等待所有监听器线程结束
        for event_type, thread in self.listeners.items():
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.listeners.clear()
        logger.info("Event queue listeners stopped")
    
    def _queue_listener(self, event_type: EventType):
        """队列监听器工作线程"""
        logger.info(f"Started listener for {event_type.value} events")
        
        while self.running:
            try:
                # 从队列获取事件，设置超时避免阻塞
                event_data = self.queues[event_type].get(timeout=1)
                
                # 检查停止信号
                if event_data is None:
                    break
                
                # 调用对应的广播回调函数
                callback = self.broadcast_callbacks.get(event_type)
                if callback:
                    try:
                        callback(event_data)
                        logger.debug(f"Broadcasted {event_type.value} event: {event_data.get('type')}")
                    except Exception as e:
                        logger.error(f"Failed to broadcast {event_type.value} event: {e}")
                else:
                    logger.warning(f"No broadcast callback registered for {event_type.value}")
                
                # 标记任务完成
                self.queues[event_type].task_done()
                
            except queue.Empty:
                # 超时，继续循环
                continue
            except Exception as e:
                logger.error(f"Error in {event_type.value} queue listener: {e}")
                time.sleep(1)  # 出错时稍作等待
        
        logger.info(f"Stopped listener for {event_type.value} events")
    
    def get_queue_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        stats = {}
        for event_type in EventType:
            stats[event_type.value] = self.queues[event_type].qsize()
        return stats
    
    def clear_queues(self):
        """清空所有队列"""
        for event_type in EventType:
            while not self.queues[event_type].empty():
                try:
                    self.queues[event_type].get_nowait()
                    self.queues[event_type].task_done()
                except queue.Empty:
                    break
        logger.info("All event queues cleared")


# 全局事件队列实例
event_queue = EventQueue()


def init_event_queue():
    """初始化事件队列"""
    event_queue.start_listeners()
    logger.info("Global event queue initialized")


def shutdown_event_queue():
    """关闭事件队列"""
    event_queue.stop_listeners()
    logger.info("Global event queue shutdown")


# 便捷函数，供其他服务使用

def push_system_metrics(metrics: list, timestamp: str = None, interval: int = None):
    """推送系统指标"""
    event_queue.push_system_metrics(
        metrics=metrics,
        timestamp=timestamp,
        interval=interval
    )


def push_model_status(models: list, timestamp: str = None, interval: int = None):
    """推送模型状态"""
    event_queue.push_model_status(
        models=models,
        timestamp=timestamp,
        interval=interval
    )


def push_notification(notification: dict, timestamp: str = None):
    """推送通知"""
    event_queue.push_notification(
        notification=notification,
        timestamp=timestamp
    )


def register_websocket_callbacks(callbacks: Dict[EventType, callable]):
    """注册WebSocket广播回调函数"""
    for event_type, callback in callbacks.items():
        event_queue.register_broadcast_callback(event_type, callback) 