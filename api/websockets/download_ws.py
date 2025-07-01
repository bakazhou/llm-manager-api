import logging
from datetime import datetime
from flask_socketio import emit, join_room, leave_room
from . import socketio
from ..models.download_task import DownloadTask

logger = logging.getLogger(__name__)


@socketio.on('connect')
def on_connect():
    """客户端连接"""
    logger.info(f"WebSocket client connected")
    emit('connected', {'message': '连接成功'})


@socketio.on('disconnect')
def on_disconnect():
    """客户端断开连接"""
    logger.info(f"WebSocket client disconnected")


@socketio.on('subscribe_download')
def on_subscribe_download(data):
    """订阅下载进度"""
    try:
        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'message': '缺少task_id参数'})
            return
        
        # 验证任务是否存在
        task = DownloadTask.query.get(task_id)
        if not task:
            emit('error', {'message': f'下载任务 {task_id} 不存在'})
            return
        
        # 加入房间以接收该任务的进度更新
        join_room(f'download_{task_id}')
        
        # 发送当前状态
        emit('download_status', {
            'task_id': task_id,
            'status': task.status,
            'progress': float(task.progress) if task.progress else 0,
            'download_size': task.download_size or 0,
            'total_size': task.total_size,
            'download_speed': float(task.download_speed) if task.download_speed else 0
        })
        
        logger.info(f"Client subscribed to download task: {task_id}")
        
    except Exception as e:
        logger.error(f"Failed to subscribe to download progress: {str(e)}")
        emit('error', {'message': '订阅失败'})


@socketio.on('unsubscribe_download')
def on_unsubscribe_download(data):
    """取消订阅下载进度"""
    try:
        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'message': '缺少task_id参数'})
            return
        
        # 离开房间
        leave_room(f'download_{task_id}')
        emit('unsubscribed', {'task_id': task_id})
        
        logger.info(f"Client unsubscribed from download task: {task_id}")
        
    except Exception as e:
        logger.error(f"Failed to unsubscribe from download progress: {str(e)}")
        emit('error', {'message': '取消订阅失败'})


def broadcast_download_progress(task_id: str, progress_data: dict):
    """广播下载进度"""
    try:
        socketio.emit('download_progress', {
            'task_id': task_id,
            **progress_data
        }, room=f'download_{task_id}')
        
    except Exception as e:
        logger.error(f"Failed to broadcast download progress: {str(e)}")


def broadcast_download_status(task_id: str, status: str, message: str = None):
    """广播下载状态变更"""
    try:
        socketio.emit('download_status_change', {
            'task_id': task_id,
            'status': status,
            'message': message,
            'timestamp': str(datetime.utcnow())
        }, room=f'download_{task_id}')
        
    except Exception as e:
        logger.error(f"Failed to broadcast download status: {str(e)}")


def broadcast_download_completed(task_id: str, file_path: str):
    """广播下载完成"""
    try:
        socketio.emit('download_completed', {
            'task_id': task_id,
            'file_path': file_path,
            'timestamp': str(datetime.utcnow())
        }, room=f'download_{task_id}')
        

        
    except Exception as e:
        logger.error(f"Failed to broadcast download completion: {str(e)}")


def broadcast_download_failed(task_id: str):
    """广播下载失败"""
    try:
        socketio.emit('download_failed', {
            'task_id': task_id,
            'timestamp': str(datetime.utcnow())
        }, room=f'download_{task_id}')
        

        
    except Exception as e:
        logger.error(f"Failed to broadcast download failure: {str(e)}") 