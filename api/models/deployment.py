from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSON

from .model import db


class Deployment(db.Model):
    """部署信息表"""
    __tablename__ = 'deployments'

    # 主键
    id = Column(String(36), primary_key=True, comment='部署ID')

    # 关联信息
    model_id = Column(String(255), nullable=False, comment='模型ID')
    model_source = Column(String(50), nullable=False, comment='模型来源')

    # 部署信息
    name = Column(String(255), nullable=False, comment='部署名称')
    description = Column(Text, comment='部署描述')

    # 状态信息
    status = Column(String(20), nullable=False, default='pending', comment='部署状态')

    # 网络配置
    port = Column(Integer, comment='服务端口')
    host = Column(String(255), default='0.0.0.0', comment='服务主机')

    # 硬件配置
    gpu_device = Column(String(20), comment='GPU设备')
    cpu_cores = Column(Integer, comment='CPU核心数')
    memory_limit = Column(Integer, comment='内存限制(MB)')

    # 容器信息
    container_id = Column(String(64), comment='容器ID')
    image_name = Column(String(255), comment='镜像名称')

    # 配置信息
    config = Column(JSON, comment='部署配置')
    environment = Column(JSON, comment='环境变量')

    # 健康检查
    health_check_url = Column(String(500), comment='健康检查URL')
    last_health_check = Column(DateTime, comment='最后健康检查时间')
    health_status = Column(String(20), default='unknown', comment='健康状态')

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    deployed_at = Column(DateTime, comment='部署时间')
    stopped_at = Column(DateTime, comment='停止时间')

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
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'port': self.port,
            'host': self.host,
            'gpu_device': self.gpu_device,
            'cpu_cores': self.cpu_cores,
            'memory_limit': self.memory_limit,
            'container_id': self.container_id,
            'image_name': self.image_name,
            'config': self.config or {},
            'environment': self.environment or {},
            'health_check_url': self.health_check_url,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'health_status': self.health_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'stopped_at': self.stopped_at.isoformat() if self.stopped_at else None,
        }

    def start_deployment(self):
        """开始部署"""
        self.status = 'deploying'
        self.deployed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        # 触发部署开始事件
        self._trigger_state_event('deploy_started', 
                                started_at=self.deployed_at.isoformat())

    def complete_deployment(self, container_id=None, port=None):
        """完成部署"""
        self.status = 'running'
        if container_id:
            self.container_id = container_id
        if port:
            self.port = port
        self.updated_at = datetime.utcnow()
        # 触发部署完成事件
        self._trigger_state_event('deploy_completed',
                                completed_at=self.updated_at.isoformat(),
                                container_id=container_id,
                                service_url=self.get_service_url())

    def stop_deployment(self):
        """停止部署"""
        self.status = 'stopped'
        self.stopped_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        # 触发部署停止事件
        self._trigger_state_event('deploy_stopped',
                                stopped_at=self.stopped_at.isoformat())

    def fail_deployment(self, error_message=None):
        """部署失败"""
        self.status = 'failed'
        if error_message and self.config:
            self.config['error'] = error_message
        self.updated_at = datetime.utcnow()
        # 触发部署失败事件
        self._trigger_state_event('deploy_failed',
                                failed_at=self.updated_at.isoformat(),
                                error_message=error_message)

    def update_health_status(self, status):
        """更新健康状态"""
        old_health_status = self.health_status
        self.health_status = status
        self.last_health_check = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        # 只有健康状态变为不健康时才触发事件
        if status == 'unhealthy' and old_health_status != 'unhealthy':
            self._trigger_state_event('health_check_failed',
                                    health_check_time=self.last_health_check.isoformat(),
                                    previous_status=old_health_status)

    @classmethod
    def get_active_deployments(cls):
        """获取活跃的部署"""
        return cls.query.filter(
            cls.status.in_(['running', 'deploying'])
        ).all()

    @classmethod
    def get_by_model(cls, model_id, model_source):
        """根据模型获取部署"""
        return cls.query.filter(
            cls.model_id == model_id,
            cls.model_source == model_source
        ).all()

    @classmethod
    def get_by_port(cls, port):
        """根据端口获取部署"""
        return cls.query.filter(cls.port == port).first()

    def is_running(self):
        """检查是否正在运行"""
        return self.status == 'running'

    def is_healthy(self):
        """检查是否健康"""
        return self.health_status == 'healthy'

    def get_service_url(self):
        """获取服务URL"""
        if self.port and self.host:
            return f"http://{self.host}:{self.port}"
        return None

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
                    'deployment_id': self.id,
                    'deployment_name': self.name,
                    'deployment_status': self.status,
                    'health_status': self.health_status,
                    'port': self.port,
                    'host': self.host,
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
            logger.error(f"Failed to trigger state event '{event_name}' for deployment {self.id}: {e}")
    
    def _sync_model_status(self):
        """保持向后兼容的状态同步方法"""
        # 为了向后兼容，保留这个方法但使用事件驱动
        try:
            if self.status in ['preparing', 'deploying']:
                self._trigger_state_event('deploy_started')
            elif self.status == 'running':
                if self.health_status == 'unhealthy':
                    self._trigger_state_event('health_check_failed')
                else:
                    self._trigger_state_event('deploy_completed')
            elif self.status == 'failed':
                self._trigger_state_event('deploy_failed')
            elif self.status in ['stopped', 'stopping']:
                self._trigger_state_event('deploy_stopped')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to sync model status for deployment {self.id}: {e}")

    def __repr__(self):
        return f'<Deployment {self.name} ({self.status})>'
