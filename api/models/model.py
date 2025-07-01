from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, Text, DECIMAL, DateTime, Index
from sqlalchemy.dialects.postgresql import JSON

db = SQLAlchemy()


class Model(db.Model):
    """模型信息表"""
    __tablename__ = 'models'

    # 主键和基本信息
    id = Column(String(255), primary_key=True, comment='模型ID')
    name = Column(String(255), nullable=False, comment='模型名称')
    description = Column(Text, comment='模型描述')

    # 来源信息
    source = Column(String(50), nullable=False, comment='模型来源: huggingface, ollama')
    model_type = Column(String(50), comment='模型类型: text-generation, text-classification等')

    # 模型属性
    size_gb = Column(DECIMAL(10, 2), comment='模型大小(GB)')
    parameters = Column(String(50), comment='参数量: 7B, 13B等')

    # 标签和元数据
    tags = Column(JSON, comment='模型标签，JSON格式存储')
    model_metadata = Column(JSON, comment='其他元数据，JSON格式存储')

    # 统计信息
    download_count = Column(db.Integer, default=0, comment='下载次数')
    view_count = Column(db.Integer, default=0, comment='查看次数')
    favorite_count = Column(db.Integer, default=0, comment='收藏次数')

    # 状态信息
    status = Column(String(20), default='active', comment='状态: active, inactive, deprecated')
    is_featured = Column(db.Boolean, default=False, comment='是否为推荐模型')

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    last_sync_at = Column(DateTime, comment='最后同步时间')

    # 索引
    __table_args__ = (
        Index('idx_model_source', 'source'),
        Index('idx_model_type', 'model_type'),
        Index('idx_model_status', 'status'),
        Index('idx_model_featured', 'is_featured'),
        Index('idx_model_created_at', 'created_at'),
        Index('idx_model_name', 'name'),
    )

    def __init__(self, id, name, source, **kwargs):
        self.id = id
        self.name = name
        self.source = source
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self, include_stats=True):
        """转换为字典格式"""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'source': self.source,
            'model_type': self.model_type,
            'size_gb': float(self.size_gb) if self.size_gb else None,
            'parameters': self.parameters,
            'tags': self.tags or [],
            'metadata': self.model_metadata or {},
            'status': self.status,
            'is_featured': self.is_featured,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
        }

        if include_stats:
            result.update({
                'download_count': self.download_count,
                'view_count': self.view_count,
                'favorite_count': self.favorite_count,
            })

        return result

    def increment_view_count(self):
        """增加查看次数"""
        self.view_count = (self.view_count or 0) + 1
        self.updated_at = datetime.utcnow()

    def increment_download_count(self):
        """增加下载次数"""
        self.download_count = (self.download_count or 0) + 1
        self.updated_at = datetime.utcnow()

    def increment_favorite_count(self):
        """增加收藏次数"""
        self.favorite_count = (self.favorite_count or 0) + 1
        self.updated_at = datetime.utcnow()

    def decrement_favorite_count(self):
        """减少收藏次数"""
        self.favorite_count = max(0, (self.favorite_count or 0) - 1)
        self.updated_at = datetime.utcnow()

    def update_sync_time(self):
        """更新同步时间"""
        self.last_sync_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @classmethod
    def search(cls, query=None, source=None, model_type=None, tags=None,
               status='active', is_featured=None, limit=20, offset=0,
               order_by='created_at', order_desc=True):
        """搜索模型"""
        q = cls.query.filter(cls.status == status)

        # 文本搜索
        if query:
            search_term = f'%{query}%'
            q = q.filter(
                db.or_(
                    cls.name.ilike(search_term),
                    cls.description.ilike(search_term),
                    cls.id.ilike(search_term)
                )
            )

        # 来源过滤
        if source:
            q = q.filter(cls.source == source)

        # 模型类型过滤
        if model_type:
            q = q.filter(cls.model_type == model_type)

        # 推荐模型过滤
        if is_featured is not None:
            q = q.filter(cls.is_featured == is_featured)

        # 标签过滤
        if tags:
            for tag in tags:
                q = q.filter(cls.tags.contains([tag]))

        # 排序
        if hasattr(cls, order_by):
            order_field = getattr(cls, order_by)
            if order_desc:
                q = q.order_by(order_field.desc())
            else:
                q = q.order_by(order_field.asc())

        # 分页
        return q.offset(offset).limit(limit).all()

    @classmethod
    def get_by_source_and_id(cls, source, model_id):
        """根据来源和ID获取模型"""
        if source == 'huggingface':
            # HuggingFace模型ID格式: username/model-name
            return cls.query.filter(
                cls.source == source,
                cls.id == model_id
            ).first()
        elif source == 'ollama':
            # Ollama模型ID格式: model-name或model-name:tag
            return cls.query.filter(
                cls.source == source,
                cls.id == model_id
            ).first()
        else:
            return cls.query.filter(cls.id == model_id).first()

    def __repr__(self):
        return f'<Model {self.id} ({self.source})>'
