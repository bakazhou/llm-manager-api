"""
通知服务
用于向客户端发送各种系统通知，包括下载完成、部署失败、内存告警等
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from ..utils.event_queue import push_notification

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """通知类型枚举"""
    MODEL = "model"
    DATA = "data"
    DEPLOYMENT = "deployment"
    SYSTEM = "system"
    DOWNLOAD = "download"


class NotificationStatus(Enum):
    """通知状态枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NotificationService:
    """通知服务类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Notification service initialized")
    
    def _create_notification(self, 
                           notification_type: NotificationType,
                           message: str,
                           status: NotificationStatus = NotificationStatus.INFO,
                           extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建通知数据结构"""
        
        notification = {
            'id': str(uuid.uuid4()),
            'type': notification_type.value,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'status': status.value
        }
        
        # 添加额外数据
        if extra_data:
            notification.update(extra_data)
        
        return notification
    
    def send_notification(self,
                         notification_type: NotificationType,
                         message: str,
                         status: NotificationStatus = NotificationStatus.INFO,
                         extra_data: Optional[Dict[str, Any]] = None):
        """发送通知到事件队列"""
        try:
            notification = self._create_notification(
                notification_type=notification_type,
                message=message,
                status=status,
                extra_data=extra_data
            )
            
            # 推送到事件队列
            push_notification(notification)
            
            self.logger.info(f"Notification sent: {notification_type.value} - {message}")
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    # ==================== 模型相关通知 ====================
    
    def notify_model_download_started(self, model_name: str, model_id: str = None):
        """通知模型下载开始"""
        message = f"开始下载模型: {model_name}"
        extra_data = {'model_id': model_id} if model_id else None
        
        self.send_notification(
            NotificationType.MODEL,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_model_download_completed(self, model_name: str, model_id: str = None):
        """通知模型下载完成"""
        message = f"模型下载完成: {model_name}"
        extra_data = {'model_id': model_id} if model_id else None
        
        self.send_notification(
            NotificationType.MODEL,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_model_download_failed(self, model_name: str, error: str = None, model_id: str = None):
        """通知模型下载失败"""
        message = f"模型下载失败: {model_name}"
        if error:
            message += f" - {error}"
        
        extra_data = {'model_id': model_id, 'error': error} if model_id or error else None
        
        self.send_notification(
            NotificationType.MODEL,
            message,
            NotificationStatus.ERROR,
            extra_data
        )
    
    def notify_model_deleted(self, model_name: str, model_id: str = None):
        """通知模型已删除"""
        message = f"模型已删除: {model_name}"
        extra_data = {'model_id': model_id} if model_id else None
        
        self.send_notification(
            NotificationType.MODEL,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    # ==================== 部署相关通知 ====================
    
    def notify_deployment_started(self, model_name: str, deployment_id: str = None):
        """通知部署开始"""
        message = f"开始部署模型: {model_name}"
        extra_data = {'deployment_id': deployment_id} if deployment_id else None
        
        self.send_notification(
            NotificationType.DEPLOYMENT,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_deployment_completed(self, model_name: str, endpoint: str = None, deployment_id: str = None):
        """通知部署完成"""
        message = f"模型部署成功: {model_name}"
        if endpoint:
            message += f" (端点: {endpoint})"
        
        extra_data = {
            'deployment_id': deployment_id,
            'endpoint': endpoint
        } if deployment_id or endpoint else None
        
        self.send_notification(
            NotificationType.DEPLOYMENT,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_deployment_failed(self, model_name: str, error: str = None, deployment_id: str = None):
        """通知部署失败"""
        message = f"模型部署失败: {model_name}"
        if error:
            message += f" - {error}"
        
        extra_data = {
            'deployment_id': deployment_id,
            'error': error
        } if deployment_id or error else None
        
        self.send_notification(
            NotificationType.DEPLOYMENT,
            message,
            NotificationStatus.ERROR,
            extra_data
        )
    
    def notify_deployment_stopped(self, model_name: str, deployment_id: str = None):
        """通知部署已停止"""
        message = f"模型部署已停止: {model_name}"
        extra_data = {'deployment_id': deployment_id} if deployment_id else None
        
        self.send_notification(
            NotificationType.DEPLOYMENT,
            message,
            NotificationStatus.WARNING,
            extra_data
        )
    
    # ==================== 系统相关通知 ====================
    
    def notify_system_memory_warning(self, usage_percent: float, available_gb: float = None):
        """通知系统内存告警"""
        message = f"系统内存使用率过高: {usage_percent:.1f}%"
        if available_gb:
            message += f"，可用内存: {available_gb:.1f}GB"
        
        extra_data = {
            'usage_percent': usage_percent,
            'available_gb': available_gb
        } if available_gb else {'usage_percent': usage_percent}
        
        self.send_notification(
            NotificationType.SYSTEM,
            message,
            NotificationStatus.WARNING,
            extra_data
        )
    
    def notify_system_disk_warning(self, usage_percent: float, available_gb: float = None):
        """通知系统磁盘告警"""
        message = f"系统磁盘使用率过高: {usage_percent:.1f}%"
        if available_gb:
            message += f"，可用空间: {available_gb:.1f}GB"
        
        extra_data = {
            'usage_percent': usage_percent,
            'available_gb': available_gb
        } if available_gb else {'usage_percent': usage_percent}
        
        self.send_notification(
            NotificationType.SYSTEM,
            message,
            NotificationStatus.WARNING,
            extra_data
        )
    
    def notify_system_error(self, error_message: str, component: str = None):
        """通知系统错误"""
        message = f"系统错误: {error_message}"
        if component:
            message = f"系统错误 ({component}): {error_message}"
        
        extra_data = {'component': component, 'error': error_message} if component else {'error': error_message}
        
        self.send_notification(
            NotificationType.SYSTEM,
            message,
            NotificationStatus.ERROR,
            extra_data
        )
    
    def notify_system_restart(self, component: str = None):
        """通知系统重启"""
        message = "系统重启完成"
        if component:
            message = f"系统组件重启完成: {component}"
        
        extra_data = {'component': component} if component else None
        
        self.send_notification(
            NotificationType.SYSTEM,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    # ==================== 下载相关通知 ====================
    
    def notify_download_started(self, filename: str, size_mb: float = None):
        """通知下载开始"""
        message = f"开始下载: {filename}"
        if size_mb:
            message += f" ({size_mb:.1f}MB)"
        
        extra_data = {'filename': filename, 'size_mb': size_mb} if size_mb else {'filename': filename}
        
        self.send_notification(
            NotificationType.DOWNLOAD,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_download_completed(self, filename: str, size_mb: float = None, duration_seconds: int = None):
        """通知下载完成"""
        message = f"下载完成: {filename}"
        if size_mb:
            message += f" ({size_mb:.1f}MB)"
        if duration_seconds:
            message += f"，耗时: {duration_seconds}秒"
        
        extra_data = {
            'filename': filename,
            'size_mb': size_mb,
            'duration_seconds': duration_seconds
        }
        # 过滤None值
        extra_data = {k: v for k, v in extra_data.items() if v is not None}
        
        self.send_notification(
            NotificationType.DOWNLOAD,
            message,
            NotificationStatus.INFO,
            extra_data if extra_data else None
        )
    
    def notify_download_failed(self, filename: str, error: str = None):
        """通知下载失败"""
        message = f"下载失败: {filename}"
        if error:
            message += f" - {error}"
        
        extra_data = {'filename': filename, 'error': error} if error else {'filename': filename}
        
        self.send_notification(
            NotificationType.DOWNLOAD,
            message,
            NotificationStatus.ERROR,
            extra_data
        )
    
    def notify_download_cancelled(self, filename: str):
        """通知下载被取消"""
        message = f"下载已取消: {filename}"
        extra_data = {'filename': filename}
        
        self.send_notification(
            NotificationType.DOWNLOAD,
            message,
            NotificationStatus.WARNING,
            extra_data
        )
    
    # ==================== 数据相关通知 ====================
    
    def notify_data_backup_completed(self, backup_name: str, size_mb: float = None):
        """通知数据备份完成"""
        message = f"数据备份完成: {backup_name}"
        if size_mb:
            message += f" ({size_mb:.1f}MB)"
        
        extra_data = {'backup_name': backup_name, 'size_mb': size_mb} if size_mb else {'backup_name': backup_name}
        
        self.send_notification(
            NotificationType.DATA,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_data_import_completed(self, dataset_name: str, records_count: int = None):
        """通知数据导入完成"""
        message = f"数据导入完成: {dataset_name}"
        if records_count:
            message += f" ({records_count:,} 条记录)"
        
        extra_data = {
            'dataset_name': dataset_name,
            'records_count': records_count
        } if records_count else {'dataset_name': dataset_name}
        
        self.send_notification(
            NotificationType.DATA,
            message,
            NotificationStatus.INFO,
            extra_data
        )
    
    def notify_data_processing_error(self, dataset_name: str, error: str = None):
        """通知数据处理错误"""
        message = f"数据处理出错: {dataset_name}"
        if error:
            message += f" - {error}"
        
        extra_data = {'dataset_name': dataset_name, 'error': error} if error else {'dataset_name': dataset_name}
        
        self.send_notification(
            NotificationType.DATA,
            message,
            NotificationStatus.ERROR,
            extra_data
        )


# 全局通知服务实例
notification_service = NotificationService()


# ==================== 便捷函数 ====================

def send_notification(notification_type: NotificationType, 
                     message: str, 
                     status: NotificationStatus = NotificationStatus.INFO,
                     extra_data: Optional[Dict[str, Any]] = None):
    """发送通知的便捷函数"""
    notification_service.send_notification(notification_type, message, status, extra_data)


# 模型相关便捷函数
def notify_model_download_started(model_name: str, model_id: str = None):
    notification_service.notify_model_download_started(model_name, model_id)

def notify_model_download_completed(model_name: str, model_id: str = None):
    notification_service.notify_model_download_completed(model_name, model_id)

def notify_model_download_failed(model_name: str, error: str = None, model_id: str = None):
    notification_service.notify_model_download_failed(model_name, error, model_id)

def notify_model_deleted(model_name: str, model_id: str = None):
    notification_service.notify_model_deleted(model_name, model_id)


# 部署相关便捷函数
def notify_deployment_started(model_name: str, deployment_id: str = None):
    notification_service.notify_deployment_started(model_name, deployment_id)

def notify_deployment_completed(model_name: str, endpoint: str = None, deployment_id: str = None):
    notification_service.notify_deployment_completed(model_name, endpoint, deployment_id)

def notify_deployment_failed(model_name: str, error: str = None, deployment_id: str = None):
    notification_service.notify_deployment_failed(model_name, error, deployment_id)

def notify_deployment_stopped(model_name: str, deployment_id: str = None):
    notification_service.notify_deployment_stopped(model_name, deployment_id)


# 系统相关便捷函数
def notify_system_memory_warning(usage_percent: float, available_gb: float = None):
    notification_service.notify_system_memory_warning(usage_percent, available_gb)

def notify_system_disk_warning(usage_percent: float, available_gb: float = None):
    notification_service.notify_system_disk_warning(usage_percent, available_gb)

def notify_system_error(error_message: str, component: str = None):
    notification_service.notify_system_error(error_message, component)


# 下载相关便捷函数
def notify_download_completed(filename: str, size_mb: float = None, duration_seconds: int = None):
    notification_service.notify_download_completed(filename, size_mb, duration_seconds)

def notify_download_failed(filename: str, error: str = None):
    notification_service.notify_download_failed(filename, error) 