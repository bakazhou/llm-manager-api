from datetime import datetime

from sqlalchemy import Column, String, DECIMAL, DateTime

from .model import db


class DownloadTask(db.Model):
    """下载任务表"""
    __tablename__ = 'download_tasks'

    # 主键
    id = Column(String(36), primary_key=True, comment='任务ID')

    # 关联信息
    model_id = Column(String(255), nullable=False, comment='模型ID')
    model_source = Column(String(50), nullable=False, comment='模型来源')

    # 任务状态
    status = Column(String(20), nullable=False, default='pending', comment='任务状态')
    progress = Column(DECIMAL(5, 2), default=0, comment='下载进度百分比')

    # 大小信息
    download_size = Column(db.BigInteger, default=0, comment='已下载大小(字节)')
    total_size = Column(db.BigInteger, comment='总大小(字节)')

    # 速度信息
    download_speed = Column(DECIMAL(10, 2), comment='下载速度(字节/秒)')

    # 文件信息
    file_path = Column(String(500), comment='文件保存路径')

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    started_at = Column(DateTime, comment='开始时间')
    completed_at = Column(DateTime, comment='完成时间')

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'model_source': self.model_source,
            'status': self.status,
            'progress': float(self.progress) if self.progress else 0,
            'download_size': self.download_size or 0,
            'total_size': self.total_size,
            'download_speed': float(self.download_speed) if self.download_speed else 0,
            'file_path': self.file_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    def update_progress(self, downloaded_size, total_size=None, speed=None):
        """更新下载进度"""
        self.download_size = downloaded_size
        if total_size:
            self.total_size = total_size
        if speed:
            self.download_speed = speed

        # 计算进度百分比
        if self.total_size and self.total_size > 0:
            self.progress = (downloaded_size / self.total_size) * 100

        self.updated_at = datetime.utcnow()

    def start_download(self):
        """开始下载"""
        self.status = 'downloading'
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        # 使用事件驱动状态管理
        self._trigger_state_event('download_started', started_at=self.started_at.isoformat())

    def pause_download(self):
        """暂停下载"""
        self.status = 'paused'
        self.updated_at = datetime.utcnow()
        # 暂停不触发状态机事件，保持当前状态

    def resume_download(self):
        """继续下载"""
        self.status = 'downloading'
        self.updated_at = datetime.utcnow()
        # 继续下载等同于重新开始下载
        self._trigger_state_event('download_started', resumed=True)

    def complete_download(self):
        """完成下载"""
        self.status = 'completed'
        self.progress = 100
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        # 触发下载完成事件
        self._trigger_state_event('download_completed', 
                                completed_at=self.completed_at.isoformat(),
                                file_path=self.file_path)

    def fail_download(self, error_message: str = None):
        """下载失败"""
        self.status = 'failed'
        self.updated_at = datetime.utcnow()
        # 触发下载失败事件
        self._trigger_state_event('download_failed', 
                                error_message=error_message,
                                failed_at=self.updated_at.isoformat())

    def cancel_download(self):
        """取消下载"""
        self.status = 'cancelled'
        self.updated_at = datetime.utcnow()
        # 触发下载取消事件
        self._trigger_state_event('download_cancelled',
                                cancelled_at=self.updated_at.isoformat())

    @classmethod
    def get_active_tasks(cls):
        """获取活跃的下载任务"""
        return cls.query.filter(
            cls.status.in_(['pending', 'downloading', 'paused'])
        ).all()

    @classmethod
    def get_by_model(cls, model_id, model_source):
        """根据模型获取下载任务"""
        return cls.query.filter(
            cls.model_id == model_id,
            cls.model_source == model_source
        ).first()

    def _trigger_state_event(self, event_name: str, **event_data):
        """触发状态变化事件"""
        try:
            # 使用状态机事件代替直接状态同步
            from ..services.model_state_machine import trigger_model_event
            success, error = trigger_model_event(
                self.model_id, 
                self.model_source, 
                event_name,
                {
                    'task_id': self.id,
                    'task_type': 'download',
                    'task_status': self.status,
                    **event_data
                }
            )
            
            if not success:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"State event '{event_name}' failed for model {self.model_id}: {error}")
                
        except Exception as e:
            # 记录错误但不影响主要操作
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to trigger state event '{event_name}' for download task {self.id}: {e}")
    
    def _sync_model_status(self):
        """保持向后兼容的状态同步方法"""
        # 为了向后兼容，保留这个方法但使用事件驱动
        try:
            if self.status == 'downloading':
                self._trigger_state_event('download_started')
            elif self.status == 'completed':
                self._trigger_state_event('download_completed')
            elif self.status == 'failed':
                self._trigger_state_event('download_failed')
            elif self.status == 'cancelled':
                self._trigger_state_event('download_cancelled')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to sync model status for download task {self.id}: {e}")

    def __repr__(self):
        return f'<DownloadTask {self.id} ({self.status})>'
