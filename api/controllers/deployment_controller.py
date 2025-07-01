import logging

from flask import request
from flask_restful import Resource

from ..services.deployment_service import DeploymentService
from ..services.system_service import SystemService
from ..utils.exceptions import APIError
from ..utils.helpers import success_response, error_response
from ..utils.validators import validate_json

logger = logging.getLogger(__name__)


class DeploymentStartController(Resource):
    """启动部署"""

    def post(self):
        try:
            # 验证请求数据
            data = validate_json(request, required_fields=['model_id', 'source', 'name'])

            model_id = data['model_id']
            source = data['source']
            name = data['name']
            config = data.get('config', {})

            # 验证参数
            if source not in ['huggingface', 'ollama']:
                return error_response("不支持的模型源", code='INVALID_SOURCE'), 400

            deployment_service = DeploymentService()

            # 创建并启动部署
            deployment = deployment_service.create_deployment(model_id, source, name, config)
            result = deployment_service.start_deployment(deployment.id)

            return success_response(
                data={
                    "deployment": deployment.to_dict(),
                    "result": result
                },
                message="部署启动成功"
            )

        except APIError as e:
            logger.error(f"Failed to start deployment: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Start deployment exception: {str(e)}")
            return error_response("Failed to start deployment"), 500


class DeploymentControlController(Resource):
    """部署控制"""

    def put(self, deployment_id, action):
        """控制部署 (stop/restart)"""
        try:
            deployment_service = DeploymentService()

            if action == 'stop':
                result = deployment_service.stop_deployment(deployment_id)
            elif action == 'restart':
                result = deployment_service.restart_deployment(deployment_id)
            else:
                return error_response(f"不支持的操作: {action}", code='INVALID_ACTION'), 400

            return success_response(
                data=result,
                message=f"部署{action}成功"
            )

        except APIError as e:
            logger.error(f"Failed to control deployment: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Control deployment exception: {str(e)}")
            return error_response("Failed to control deployment"), 500


class DeploymentController(Resource):
    """部署管理"""

    def get(self, deployment_id):
        """获取部署状态"""
        try:
            deployment_service = DeploymentService()
            deployment_info = deployment_service.get_deployment_status(deployment_id)

            return success_response(
                data=deployment_info,
                message="获取部署状态成功"
            )

        except APIError as e:
            logger.error(f"Failed to get deployment status: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get deployment status exception: {str(e)}")
            return error_response("Failed to get deployment status"), 500

    def delete(self, deployment_id):
        """删除部署"""
        try:
            deployment_service = DeploymentService()
            result = deployment_service.delete_deployment(deployment_id)

            return success_response(
                data=result,
                message="删除部署成功"
            )

        except APIError as e:
            logger.error(f"Failed to delete deployment: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Delete deployment exception: {str(e)}")
            return error_response("Failed to delete deployment"), 500


class DeploymentListController(Resource):
    """部署列表"""

    def get(self):
        """获取部署列表"""
        try:
            # 获取查询参数
            status = request.args.get('status')
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))

            # 验证参数
            if page < 1:
                return error_response("页码必须大于0", code='INVALID_PAGE'), 400
            if page_size < 1 or page_size > 100:
                return error_response("页面大小必须在1-100之间", code='INVALID_PAGE_SIZE'), 400

            deployment_service = DeploymentService()
            result = deployment_service.list_deployments(status, page, page_size)

            return success_response(
                data=result,
                message="获取部署列表成功"
            )

        except APIError as e:
            logger.error(f"Failed to get deployment list: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get deployment list exception: {str(e)}")
            return error_response("Failed to get deployment list"), 500


class DeploymentLogsController(Resource):
    """部署日志"""

    def get(self, deployment_id):
        """获取部署日志"""
        try:
            # 获取查询参数
            lines = int(request.args.get('lines', 100))

            # 验证参数
            if lines < 1 or lines > 10000:
                return error_response("日志行数必须在1-10000之间", code='INVALID_LINES'), 400

            deployment_service = DeploymentService()
            logs_info = deployment_service.get_deployment_logs(deployment_id, lines)

            return success_response(
                data=logs_info,
                message="获取部署日志成功"
            )

        except APIError as e:
            logger.error(f"Failed to get deployment logs: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get deployment logs exception: {str(e)}")
            return error_response("Failed to get deployment logs"), 500


class DeploymentHealthController(Resource):
    """部署健康检查"""

    def get(self, deployment_id):
        """检查部署健康状态"""
        try:
            deployment_service = DeploymentService()
            health_info = deployment_service.check_deployment_health(deployment_id)

            return success_response(
                data=health_info,
                message="健康检查完成"
            )

        except APIError as e:
            logger.error(f"Health check failed: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Health check exception: {str(e)}")
            return error_response("Health check failed"), 500



