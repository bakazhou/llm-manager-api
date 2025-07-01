"""
模型状态机系统
实现统一的状态管理和转换逻辑
"""

import logging
from enum import Enum
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from ..models.model import Model, db

logger = logging.getLogger(__name__)


class ModelState(Enum):
    """模型业务状态枚举"""
    INACTIVE = 'inactive'
    DOWNLOADING = 'downloading'
    DEPLOYING = 'deploying'
    ACTIVE = 'active'
    TRAINING = 'training'
    ERROR = 'error'


class ModelEvent(Enum):
    """模型状态转换事件"""
    DOWNLOAD_STARTED = 'download_started'
    DOWNLOAD_COMPLETED = 'download_completed'
    DOWNLOAD_FAILED = 'download_failed'
    DOWNLOAD_CANCELLED = 'download_cancelled'
    DEPLOY_STARTED = 'deploy_started'
    DEPLOY_COMPLETED = 'deploy_completed'
    DEPLOY_FAILED = 'deploy_failed'
    DEPLOY_STOPPED = 'deploy_stopped'
    HEALTH_CHECK_FAILED = 'health_check_failed'
    MANUAL_ERROR_SET = 'manual_error_set'
    MANUAL_RESET = 'manual_reset'


class ModelStateMachine:
    """模型状态机"""
    
    # 状态转换映射表
    TRANSITIONS: Dict[Tuple[ModelState, ModelEvent], ModelState] = {
        # 从 inactive 开始的转换
        (ModelState.INACTIVE, ModelEvent.DOWNLOAD_STARTED): ModelState.DOWNLOADING,
        (ModelState.INACTIVE, ModelEvent.DEPLOY_STARTED): ModelState.DEPLOYING,
        
        # 从 downloading 的转换
        (ModelState.DOWNLOADING, ModelEvent.DOWNLOAD_COMPLETED): ModelState.INACTIVE,
        (ModelState.DOWNLOADING, ModelEvent.DOWNLOAD_FAILED): ModelState.ERROR,
        (ModelState.DOWNLOADING, ModelEvent.DOWNLOAD_CANCELLED): ModelState.INACTIVE,
        (ModelState.DOWNLOADING, ModelEvent.DEPLOY_STARTED): ModelState.DEPLOYING,  # 下载完成后立即部署
        
        # 从 deploying 的转换
        (ModelState.DEPLOYING, ModelEvent.DEPLOY_COMPLETED): ModelState.ACTIVE,
        (ModelState.DEPLOYING, ModelEvent.DEPLOY_FAILED): ModelState.ERROR,
        
        # 从 active 的转换
        (ModelState.ACTIVE, ModelEvent.DEPLOY_STOPPED): ModelState.INACTIVE,
        (ModelState.ACTIVE, ModelEvent.HEALTH_CHECK_FAILED): ModelState.ERROR,
        (ModelState.ACTIVE, ModelEvent.DEPLOY_STARTED): ModelState.DEPLOYING,  # 重新部署
        (ModelState.ACTIVE, ModelEvent.DOWNLOAD_STARTED): ModelState.DOWNLOADING,  # 下载新版本
        
        # 从 error 的转换
        (ModelState.ERROR, ModelEvent.DOWNLOAD_STARTED): ModelState.DOWNLOADING,
        (ModelState.ERROR, ModelEvent.DEPLOY_STARTED): ModelState.DEPLOYING,
        (ModelState.ERROR, ModelEvent.MANUAL_RESET): ModelState.INACTIVE,
        
        # 从 training 的转换（预留）
        (ModelState.TRAINING, ModelEvent.MANUAL_RESET): ModelState.INACTIVE,
        
        # 手动错误设置（从任何状态）
        (ModelState.INACTIVE, ModelEvent.MANUAL_ERROR_SET): ModelState.ERROR,
        (ModelState.DOWNLOADING, ModelEvent.MANUAL_ERROR_SET): ModelState.ERROR,
        (ModelState.DEPLOYING, ModelEvent.MANUAL_ERROR_SET): ModelState.ERROR,
        (ModelState.ACTIVE, ModelEvent.MANUAL_ERROR_SET): ModelState.ERROR,
        (ModelState.TRAINING, ModelEvent.MANUAL_ERROR_SET): ModelState.ERROR,
    }
    
    @classmethod
    def get_valid_transitions(cls, current_state: ModelState) -> List[ModelEvent]:
        """获取当前状态下的有效转换事件"""
        return [event for (state, event) in cls.TRANSITIONS.keys() if state == current_state]
    
    @classmethod
    def can_transition(cls, current_state: ModelState, event: ModelEvent) -> bool:
        """检查是否可以进行状态转换"""
        return (current_state, event) in cls.TRANSITIONS
    
    @classmethod
    def get_next_state(cls, current_state: ModelState, event: ModelEvent) -> Optional[ModelState]:
        """获取转换后的状态"""
        return cls.TRANSITIONS.get((current_state, event))
    
    @classmethod
    @contextmanager
    def _atomic_transaction(cls):
        """原子事务上下文管理器"""
        try:
            yield db.session
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    
    @classmethod
    def transition(cls, model_id: str, model_source: str, event: ModelEvent, 
                   event_data: Optional[Dict] = None, 
                   auto_notify: bool = True) -> Tuple[bool, Optional[str]]:
        """
        执行状态转换
        
        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        try:
            with cls._atomic_transaction():
                # 使用行锁获取模型
                model = Model.query.filter(
                    and_(
                        Model.id == model_id,
                        Model.source == model_source
                    )
                ).with_for_update().first()
                
                if not model:
                    return False, f"Model not found: {model_id} ({model_source})"
                
                # 获取当前状态
                try:
                    current_state = ModelState(model.status) if model.status else ModelState.INACTIVE
                except ValueError:
                    current_state = ModelState.INACTIVE
                    logger.warning(f"Invalid current state '{model.status}' for model {model_id}, resetting to inactive")
                
                # 检查转换是否合法
                if not cls.can_transition(current_state, event):
                    valid_events = cls.get_valid_transitions(current_state)
                    return False, f"Invalid transition: {current_state.value} -> {event.value}. Valid events: {[e.value for e in valid_events]}"
                
                new_state = cls.get_next_state(current_state, event)
                
                # 执行状态转换
                if current_state != new_state:
                    old_status = model.status
                    model.status = new_state.value
                    model.updated_at = datetime.utcnow()
                    
                    logger.info(f"Model state transition: {model_id} {old_status} -> {new_state.value} (event: {event.value})")
                    
                    # 记录状态变化历史
                    cls._record_state_change(model_id, model_source, old_status, new_state.value, event, event_data)
                    
                    # 自动通知状态变化
                    if auto_notify:
                        cls._notify_state_change(model_id, model_source, old_status, new_state.value)
                    
                    return True, None
                else:
                    logger.debug(f"Model {model_id} already in target state {new_state.value}")
                    return True, "Already in target state"
                
        except IntegrityError as e:
            logger.error(f"Database integrity error during state transition: {e}")
            return False, f"Database integrity error: {str(e)}"
        except Exception as e:
            logger.error(f"Failed to transition model state: {e}")
            return False, f"State transition failed: {str(e)}"
    
    @classmethod
    def _record_state_change(cls, model_id: str, model_source: str, 
                           old_status: Optional[str], new_status: str, 
                           event: ModelEvent, event_data: Optional[Dict]):
        """记录状态变化历史"""
        try:
            # 这里可以记录到单独的状态变化历史表
            # 目前先记录到日志
            change_info = {
                'model_id': model_id,
                'model_source': model_source,
                'old_status': old_status,
                'new_status': new_status,
                'event': event.value,
                'event_data': event_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            logger.info(f"State change recorded: {change_info}")
            
        except Exception as e:
            logger.error(f"Failed to record state change: {e}")
    
    @classmethod
    def _notify_state_change(cls, model_id: str, model_source: str, 
                           old_status: Optional[str], new_status: str):
        """通知状态变化"""
        try:
            from ..utils.event_queue import push_model_status
            
            # 构造模型状态
            model_name = model_id.split('/')[-1] if '/' in model_id else model_id
            
            # 根据状态设置显示文本
            if new_status == 'downloading':
                last_updated = "正在下载"
            elif new_status == 'deploying':
                last_updated = "部署中"
            elif new_status == 'training':
                last_updated = "训练中"
            else:
                last_updated = "刚刚"
            
            model_status = {
                "id": model_id,
                "name": model_name,
                "status": new_status,
                "lastUpdated": last_updated
            }
            
            # 立即推送状态变化
            push_model_status(
                models=[model_status],
                timestamp=datetime.utcnow().isoformat(),
                interval=0  # 立即推送
            )
            
            logger.debug(f"State change notification sent: {model_id} {old_status} -> {new_status}")
            
        except Exception as e:
            logger.error(f"Failed to notify state change: {e}")
    
    @classmethod
    def get_model_state(cls, model_id: str, model_source: str) -> Optional[ModelState]:
        """获取模型当前状态"""
        try:
            model = Model.query.filter(
                and_(
                    Model.id == model_id,
                    Model.source == model_source
                )
            ).first()
            
            if not model:
                return None
            
            try:
                return ModelState(model.status) if model.status else ModelState.INACTIVE
            except ValueError:
                logger.warning(f"Invalid status '{model.status}' for model {model_id}")
                return ModelState.INACTIVE
                
        except Exception as e:
            logger.error(f"Failed to get model state: {e}")
            return None
    
    @classmethod
    def force_state(cls, model_id: str, model_source: str, target_state: ModelState,
                   auto_notify: bool = True) -> Tuple[bool, Optional[str]]:
        """强制设置模型状态（绕过状态机验证）"""
        try:
            with cls._atomic_transaction():
                model = Model.query.filter(
                    and_(
                        Model.id == model_id,
                        Model.source == model_source
                    )
                ).with_for_update().first()
                
                if not model:
                    return False, f"Model not found: {model_id} ({model_source})"
                
                old_status = model.status
                model.status = target_state.value
                model.updated_at = datetime.utcnow()
                
                logger.warning(f"Model state force set: {model_id} {old_status} -> {target_state.value}")
                
                # 记录强制状态变化
                cls._record_state_change(
                    model_id, model_source, old_status, target_state.value, 
                    ModelEvent.MANUAL_RESET, {'force_set': True}
                )
                
                if auto_notify:
                    cls._notify_state_change(model_id, model_source, old_status, target_state.value)
                
                return True, None
                
        except Exception as e:
            logger.error(f"Failed to force model state: {e}")
            return False, f"Force state failed: {str(e)}"


# 便捷函数
def trigger_model_event(model_id: str, model_source: str, event_name: str, 
                       event_data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """触发模型事件的便捷函数"""
    try:
        event = ModelEvent(event_name)
        return ModelStateMachine.transition(model_id, model_source, event, event_data)
    except ValueError:
        logger.error(f"Unknown event: {event_name}")
        return False, f"Unknown event: {event_name}"


def get_model_state(model_id: str, model_source: str) -> Optional[str]:
    """获取模型状态的便捷函数"""
    state = ModelStateMachine.get_model_state(model_id, model_source)
    return state.value if state else None


def force_model_state(model_id: str, model_source: str, target_state: str) -> Tuple[bool, Optional[str]]:
    """强制设置模型状态的便捷函数"""
    try:
        state = ModelState(target_state)
        return ModelStateMachine.force_state(model_id, model_source, state)
    except ValueError:
        return False, f"Invalid state: {target_state}" 