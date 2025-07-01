"""
统一监控服务
整合模型状态监控和系统资源监控，使用单一线程高效运行
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from ..models.model import Model
from ..utils.event_queue import push_model_status, push_system_metrics
from .system_service import SystemService

logger = logging.getLogger(__name__)


class ModelStatus:
    """模型状态数据结构"""
    
    def __init__(self, id: str, name: str, status: str, last_updated: datetime):
        self.id = id
        self.name = name
        self.status = status  # "active" | "inactive" | "training" | "error" | "downloading" | "deploying"
        self.last_updated = last_updated
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "lastUpdated": self.last_updated.isoformat() if self.last_updated else None
        }


class SystemMetric:
    """系统指标数据结构"""
    
    def __init__(self, name: str, value: float, unit: str, status: str):
        self.name = name
        self.value = value
        self.unit = unit
        self.status = status  # "good" | "warning" | "critical"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "status": self.status
        }


class MonitorService:
    """统一监控服务 - 整合模型状态和系统资源监控"""
    
    def __init__(self):
        self.system_service = SystemService()
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 5  # 统一5秒间隔
        self._app = None  # Flask应用实例
        
        # 系统监控阈值配置
        self.system_thresholds = {
            'cpu': {'warning': 70, 'critical': 85},
            'memory': {'warning': 80, 'critical': 90},
            'disk': {'warning': 80, 'critical': 90},
            'gpu_usage': {'warning': 85, 'critical': 95}
        }
        
        # 计数器用于控制不同类型监控的频率
        self.tick_count = 0
        self.model_check_interval = 1  # 每次都检查模型状态
        self.system_check_interval = 1  # 每次都检查系统状态

    def _get_last_updated(self, model: Model) -> datetime:
        """获取最后更新时间"""
        return model.updated_at or model.created_at or datetime.utcnow()
    
    def collect_model_status(self) -> List[ModelStatus]:
        """收集模型状态信息"""
        def _process_models_in_context():
            """在应用上下文中处理模型数据"""
            model_statuses = []
            
            try:
                # 获取所有模型
                models = Model.query.all()
                
                for model in models:
                    try:
                        # 直接使用模型的状态（已通过状态机同步）
                        status = model.status or 'inactive'

                        last_updated_time = self._get_last_updated(model)

                        model_status = ModelStatus(
                            id=model.id,
                            name=model.name,
                            status=status,
                            last_updated=last_updated_time
                        )
                        
                        model_statuses.append(model_status)
                        
                    except Exception as e:
                        logger.error(f"Failed to process model {model.id}: {e}")
                        # 添加错误状态的模型
                        model_status = ModelStatus(
                            id=model.id,
                            name=model.name,
                            status='error',
                            last_updated=datetime.utcnow()
                        )
                        model_statuses.append(model_status)
                
                return model_statuses
                
            except Exception as e:
                logger.error(f"Failed to query models: {e}")
                return []
        
        try:
            # 确保在应用上下文中执行
            if self._app:
                with self._app.app_context():
                    return _process_models_in_context()
            else:
                from flask import current_app
                if current_app:
                    return _process_models_in_context()
                else:
                    logger.warning("No Flask application context available")
                    return []
            
        except Exception as e:
            logger.error(f"Failed to collect model status: {e}")
            return []
    
    def _get_system_status(self, metric_name: str, value: float) -> str:
        """根据阈值获取系统状态"""
        thresholds = self.system_thresholds.get(metric_name, {})
        
        if value >= thresholds.get('critical', 100):
            return 'critical'
        elif value >= thresholds.get('warning', 100):
            return 'warning'
        else:
            return 'good'
    
    def collect_system_metrics(self) -> List[SystemMetric]:
        """收集系统指标"""
        try:
            metrics = []
            system_data = self.system_service.get_system_resources()
            
            # CPU使用率
            cpu_info = system_data.get('cpu', {})
            cpu_usage = cpu_info.get('usage_percent', 0)
            metrics.append(SystemMetric(
                name='cpu_usage',
                value=round(cpu_usage, 1),
                unit='%',
                status=self._get_system_status('cpu', cpu_usage)
            ))
            
            # 内存使用率
            memory_info = system_data.get('memory', {})
            memory_usage = memory_info.get('percent', 0)
            metrics.append(SystemMetric(
                name='memory_usage',
                value=round(memory_usage, 1),
                unit='%',
                status=self._get_system_status('memory', memory_usage)
            ))
            
            # 磁盘使用率
            disk_info = system_data.get('disk', {})
            disk_usage = disk_info.get('percent', 0)
            metrics.append(SystemMetric(
                name='disk_usage',
                value=round(disk_usage, 1),
                unit='%',
                status=self._get_system_status('disk', disk_usage)
            ))
            
            # GPU使用率
            gpu_info = system_data.get('gpu', {})
            gpu_usage = gpu_info.get('usage_percent', 0)
            gpu_available = gpu_info.get('available', False)
            
            metrics.append(SystemMetric(
                name='gpu_usage',
                value=round(gpu_usage, 1),
                unit='%',
                status=self._get_system_status('gpu_usage', gpu_usage) if gpu_available else 'good'
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return []
    
    def monitor_worker(self):
        """统一监控工作线程"""
        logger.info("Unified monitor service started")
        
        while self.monitoring:
            try:
                timestamp = datetime.utcnow().isoformat()
                self.tick_count += 1
                
                # 收集模型状态（每次都执行）
                if self.tick_count % self.model_check_interval == 0:
                    model_statuses = self.collect_model_status()
                    
                    if model_statuses:
                        push_model_status(
                            models=[status.to_dict() for status in model_statuses],
                            timestamp=timestamp,
                            interval=self.monitor_interval
                        )
                        logger.debug(f"Model status pushed: {len(model_statuses)} models")
                
                # 收集系统指标（每次都执行）
                if self.tick_count % self.system_check_interval == 0:
                    system_metrics = self.collect_system_metrics()
                    
                    if system_metrics:
                        push_system_metrics(
                            metrics=[metric.to_dict() for metric in system_metrics],
                            timestamp=timestamp,
                            interval=self.monitor_interval
                        )
                        logger.debug(f"System metrics pushed: {len(system_metrics)} metrics")
                
                # 等待下一次监控
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in unified monitor worker: {e}")
                time.sleep(self.monitor_interval)
        
        logger.info("Unified monitor service stopped")
    
    def start_monitoring(self, app=None):
        """启动统一监控"""
        if self.monitoring:
            logger.warning("Unified monitoring is already running")
            return
        
        # 保存Flask应用实例
        if app:
            self._app = app
        
        self.monitoring = True
        self.tick_count = 0
        self.monitor_thread = threading.Thread(
            target=self.monitor_worker,
            daemon=True,
            name="UnifiedMonitor"
        )
        self.monitor_thread.start()
        logger.info("Unified monitoring started")
    
    def stop_monitoring(self):
        """停止统一监控"""
        if not self.monitoring:
            logger.warning("Unified monitoring is not running")
            return
        
        self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("Unified monitoring stopped")
    
    def is_monitoring(self) -> bool:
        """检查是否正在监控"""
        return self.monitoring and self.monitor_thread and self.monitor_thread.is_alive()
    
    def get_current_model_status(self) -> List[Dict[str, Any]]:
        """获取当前模型状态"""
        model_statuses = self.collect_model_status()
        return [status.to_dict() for status in model_statuses]
    
    def get_current_system_metrics(self) -> List[Dict[str, Any]]:
        """获取当前系统指标"""
        system_metrics = self.collect_system_metrics()
        return [metric.to_dict() for metric in system_metrics]
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """获取监控服务状态"""
        return {
            'monitoring': self.is_monitoring(),
            'interval': self.monitor_interval,
            'system_thresholds': self.system_thresholds,
            'tick_count': self.tick_count,
            'thread_name': self.monitor_thread.name if self.monitor_thread else None
        }


# 全局统一监控服务实例
monitor = MonitorService()


def start_monitoring(app=None):
    """启动统一监控"""
    monitor.start_monitoring(app)


def stop_monitoring():
    """停止统一监控"""
    monitor.stop_monitoring()


def get_monitoring_status() -> Dict[str, Any]:
    """获取监控状态"""
    return monitor.get_monitoring_status()


def get_current_model_status() -> List[Dict[str, Any]]:
    """获取当前模型状态"""
    return monitor.get_current_model_status()


def get_current_system_metrics() -> List[Dict[str, Any]]:
    """获取当前系统指标"""
    return monitor.get_current_system_metrics() 