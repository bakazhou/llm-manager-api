from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from .model import db


class ChatSession(db.Model):
    """对话会话表"""
    __tablename__ = 'chat_sessions'

    # 主键
    id = Column(String(36), primary_key=True, comment='会话ID')

    # 关联信息
    deployment_id = Column(String(36), ForeignKey('deployments.id'), nullable=False, comment='部署ID')

    # 会话信息
    name = Column(String(255), comment='会话名称')
    description = Column(Text, comment='会话描述')

    # 配置信息
    config = Column(JSON, comment='会话配置')
    system_prompt = Column(Text, comment='系统提示词')

    # 统计信息
    message_count = Column(Integer, default=0, comment='消息数量')
    total_tokens = Column(Integer, default=0, comment='总token数')

    # 状态信息
    status = Column(String(20), default='active', comment='会话状态')
    is_archived = Column(Boolean, default=False, comment='是否归档')

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    last_message_at = Column(DateTime, comment='最后消息时间')

    # 关联关系
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self, include_messages=False):
        """转换为字典格式"""
        result = {
            'id': self.id,
            'deployment_id': self.deployment_id,
            'name': self.name,
            'description': self.description,
            'config': self.config or {},
            'system_prompt': self.system_prompt,
            'message_count': self.message_count or 0,
            'total_tokens': self.total_tokens or 0,
            'status': self.status,
            'is_archived': self.is_archived,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
        }

        if include_messages:
            result['messages'] = [msg.to_dict() for msg in self.messages]

        return result

    def add_message(self, role, content, metadata=None):
        """添加消息"""
        message = ChatMessage(
            session_id=self.id,
            role=role,
            content=content,
            message_metadata=metadata or {}
        )
        db.session.add(message)

        # 更新统计信息
        self.message_count = (self.message_count or 0) + 1
        self.last_message_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        return message

    def __repr__(self):
        return f'<ChatSession {self.name or self.id}>'


class ChatMessage(db.Model):
    """对话消息表"""
    __tablename__ = 'chat_messages'

    # 主键
    id = Column(String(36), primary_key=True, comment='消息ID')

    # 关联信息
    session_id = Column(String(36), ForeignKey('chat_sessions.id'), nullable=False, comment='会话ID')

    # 消息信息
    role = Column(String(20), nullable=False, comment='角色: user, assistant, system')
    content = Column(Text, nullable=False, comment='消息内容')

    # 元数据
    message_metadata = Column(JSON, comment='消息元数据')
    tokens_used = Column(Integer, comment='使用的token数')

    # 状态信息
    is_deleted = Column(Boolean, default=False, comment='是否删除')

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    # 关联关系
    session = relationship("ChatSession", back_populates="messages")

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'metadata': self.message_metadata or {},
            'tokens_used': self.tokens_used,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<ChatMessage {self.id} ({self.role})>'
