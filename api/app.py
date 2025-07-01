"""Flask应用入口"""
import atexit
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_restful import Api

from .config import config
from .controllers.chat_controller import (
    ChatController, CompletionController, ModelInfoController
)
from .controllers.deployment_controller import (
    DeploymentStartController,
    DeploymentControlController,
    DeploymentController,
    DeploymentListController,
    DeploymentLogsController,
    DeploymentHealthController
)
from .controllers.download_controller import (
    DownloadStartController,
    DownloadControlController,
    DownloadTaskController,
    DownloadListController,
    DownloadQueueController,
    DownloadStorageController,
    DownloadCancelController
)
from .controllers.model_controller import (
    ModelSearchResource,
    ModelInfoResource,
    ModelCategoriesResource,
    ModelTrendingResource,
    ModelStatsResource,
    ModelFavoriteResource,
    ModelSyncResource
)
from .models.model import db
from .utils.exceptions import APIError
from .utils.helpers import format_error_response
from .utils.event_queue import init_event_queue, shutdown_event_queue
from .websockets import init_socketio
from .websockets.broadcast_ws import init_websocket_event_system
from .services.monitor_service import start_monitoring, stop_monitoring


def create_app(config_name=None):
    """创建Flask应用"""

    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    # 创建Flask应用
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(config[config_name])

    # 配置日志
    setup_logging(app)

    # 初始化扩展
    setup_extensions(app)

    # 注册路由
    setup_routes(app)

    # 注册错误处理
    setup_error_handlers(app)

    # 创建数据库表
    with app.app_context():
        setup_database(app)

    return app


def setup_logging(app):
    """设置日志"""
    log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO

    # 设置根日志级别
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )

    # 设置应用日志
    app.logger.setLevel(log_level)

    # 创建日志目录
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # 配置文件日志处理器
    if not app.config.get('TESTING'):
        file_handler = logging.FileHandler(f'{logs_dir}/app.log')
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s [%(pathname)s:%(lineno)d]: %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        app.logger.addHandler(file_handler)


def setup_extensions(app):
    """初始化扩展"""
    # 初始化数据库
    db.init_app(app)

    # 初始化CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # 初始化事件队列
    init_event_queue()

    # 初始化WebSocket
    socketio = init_socketio(app)
    app.socketio = socketio

    # 初始化WebSocket事件系统
    init_websocket_event_system()

    # 启动统一监控服务
    start_monitoring(app)

    # 注册应用关闭时的清理函数
    @app.teardown_appcontext
    def cleanup_event_queue(exception):
        """应用上下文结束时清理事件队列"""
        if exception:
            app.logger.error(f"Application context ended with exception: {exception}")
    
    # 注册进程退出时的清理函数
    def shutdown_cleanup():
        """进程退出时的清理"""
        try:
            stop_monitoring()
            app.logger.info("Unified monitoring stopped")
            
            shutdown_event_queue()
            app.logger.info("Event queue shutdown completed")
        except Exception as e:
            app.logger.error(f"Error during shutdown cleanup: {e}")
    
    atexit.register(shutdown_cleanup)


def setup_routes(app):
    """设置路由"""
    # 创建API实例
    api = Api(app)

    # 健康检查端点
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'llm-manager-api',
            'version': '1.0.0'
        })

    @app.route('/api/health')
    def api_health_check():
        return jsonify({
            'status': 'healthy',
            'api_version': 'v1',
            'service': 'llm-manager-api'
        })

    # 注册模型管理相关路由
    # 模型搜索
    api.add_resource(ModelSearchResource, '/api/models/search')

    # 模型信息
    api.add_resource(ModelInfoResource, '/api/models/<path:model_id>/info')

    # 模型分类
    api.add_resource(ModelCategoriesResource, '/api/models/categories')

    # 热门模型
    api.add_resource(ModelTrendingResource, '/api/models/trending')

    # 模型统计
    api.add_resource(ModelStatsResource, '/api/models/stats')

    # 模型收藏
    api.add_resource(ModelFavoriteResource, '/api/models/<path:model_id>/favorite')

    # 模型同步
    api.add_resource(ModelSyncResource, '/api/models/sync')

    # 下载管理相关路由
    # 开始下载
    api.add_resource(DownloadStartController, '/api/downloads/start')

    # 下载任务控制
    api.add_resource(DownloadControlController, '/api/downloads/<string:task_id>/<string:action>')

    # 取消下载
    api.add_resource(DownloadCancelController, '/api/downloads/<string:task_id>/cancel')

    # 下载任务管理
    api.add_resource(DownloadTaskController, '/api/downloads/<string:task_id>')

    # 下载任务列表
    api.add_resource(DownloadListController, '/api/downloads/list')

    # 下载队列状态
    api.add_resource(DownloadQueueController, '/api/downloads/queue')

    # 存储空间信息
    api.add_resource(DownloadStorageController, '/api/downloads/storage')

    # 部署管理相关路由
    # 启动部署
    api.add_resource(DeploymentStartController, '/api/deployments/start')

    # 部署控制
    api.add_resource(DeploymentControlController, '/api/deployments/<string:deployment_id>/<string:action>')

    # 部署管理
    api.add_resource(DeploymentController, '/api/deployments/<string:deployment_id>')

    # 部署列表
    api.add_resource(DeploymentListController, '/api/deployments/list')

    # 部署日志
    api.add_resource(DeploymentLogsController, '/api/deployments/<string:deployment_id>/logs')

    # 部署健康检查
    api.add_resource(DeploymentHealthController, '/api/deployments/<string:deployment_id>/health')

    # 聊天和推理相关路由
    # 与部署的模型聊天
    api.add_resource(ChatController, '/api/chat/<string:deployment_id>')

    # 文本补全
    api.add_resource(CompletionController, '/api/completions/<string:deployment_id>')

    # 获取部署的模型详细信息
    api.add_resource(ModelInfoController, '/api/deployments/<string:deployment_id>/model-info')



    # 根路径
    @app.route('/')
    def index():
        return jsonify({
            'message': 'LLM Manager API',
            'version': '1.0.0',
            'description': '大语言模型管理服务API',
            'endpoints': {
                'health': '/health',
                'api_health': '/api/health',
                'models_search': '/api/models/search',
                'model_info': '/api/models/{model_id}/info',
                'model_categories': '/api/models/categories',
                'trending_models': '/api/models/trending',
                'model_stats': '/api/models/stats',
                'model_favorite': '/api/models/{model_id}/favorite',
                'model_sync': '/api/models/sync',
                'download_start': '/api/downloads/start',
                'download_control': '/api/downloads/{task_id}/{action}',
                'download_cancel': '/api/downloads/{task_id}/cancel',
                'download_task': '/api/downloads/{task_id}',
                'download_list': '/api/downloads/list',
                'download_queue': '/api/downloads/queue',
                'download_storage': '/api/downloads/storage',
                'deployment_start': '/api/deployments/start',
                'deployment_control': '/api/deployments/{deployment_id}/{action}',
                'deployment_status': '/api/deployments/{deployment_id}',
                'deployment_list': '/api/deployments/list',
                'deployment_logs': '/api/deployments/{deployment_id}/logs',
                'deployment_health': '/api/deployments/{deployment_id}/health',
                'chat': '/api/chat/{deployment_id}',
                'completions': '/api/completions/{deployment_id}',
                'deployment_model_info': '/api/deployments/{deployment_id}/model-info',
                'websocket_download': '/ws/download-progress'
            }
        })


def setup_error_handlers(app):
    """设置错误处理器"""

    @app.errorhandler(APIError)
    def handle_api_error(error):
        """处理API自定义错误"""
        response = format_error_response(
            message=error.message,
            error_code=error.code,
            details=getattr(error, 'details', None)
        )
        return jsonify(response), error.status_code

    @app.errorhandler(404)
    def handle_not_found(error):
        """处理404错误"""
        response = format_error_response(
            message="接口不存在",
            error_code="NOT_FOUND"
        )
        return jsonify(response), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """处理405错误"""
        response = format_error_response(
            message="请求方法不允许",
            error_code="METHOD_NOT_ALLOWED"
        )
        return jsonify(response), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        """处理500错误"""
        app.logger.error(f"Internal server error: {error}")
        response = format_error_response(
            message="内部服务器错误",
            error_code="INTERNAL_ERROR"
        )
        return jsonify(response), 500

    @app.errorhandler(Exception)
    def handle_general_exception(error):
        """处理一般异常"""
        app.logger.error(f"Unhandled exception: {error}")

        # 开发环境显示详细错误信息
        if app.config.get('DEBUG'):
            response = format_error_response(
                message=f"未处理的异常: {str(error)}",
                error_code="UNHANDLED_EXCEPTION",
                details={'exception_type': type(error).__name__}
            )
        else:
            response = format_error_response(
                message="服务器内部错误",
                error_code="INTERNAL_ERROR"
            )

        return jsonify(response), 500


def setup_database(app):
    """设置数据库"""
    try:
        # 创建所有表
        db.create_all()
        app.logger.info("Database tables created successfully")

        # 检查数据库连接
        with db.engine.connect() as conn:
            conn.execute(db.text("SELECT 1"))
        app.logger.info("Database connection is healthy")

    except Exception as e:
        app.logger.error(f"Database initialization failed: {e}")
        raise


# 创建应用实例
app = create_app()

if __name__ == '__main__':
    # 直接运行时的配置
    port = int(os.getenv('PORT', 5000))
    app.socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=app.config.get('DEBUG', False)
    )
