from flask_socketio import SocketIO

# 全局SocketIO实例
socketio = None

def init_socketio(app):
    """初始化SocketIO"""
    global socketio
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True
    )
    
    # 导入WebSocket事件处理器
    from . import download_ws
    from .broadcast_ws import register_monitor_events
    
    # 注册监控事件
    register_monitor_events(socketio)
    
    return socketio 