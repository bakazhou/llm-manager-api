import logging

from flask import request
from flask_restful import Resource

from ..services.download_service import DownloadService
from ..utils.exceptions import APIError
from ..utils.helpers import success_response, error_response
from ..utils.validators import validate_json

logger = logging.getLogger(__name__)


class DownloadStartController(Resource):
    """开始下载"""

    def post(self):
        """
        开始模型下载任务
        
        请求体参数:
        - model_id: 模型ID (必需)
        - source: 模型源 ('huggingface' 或 'ollama') (必需)
        
        示例:
        {
            "model_id": "microsoft/DialoGPT-medium",
            "source": "huggingface"
        }
        """
        try:
            # 验证请求数据
            data = validate_json(request, required_fields=['model_id', 'source'])

            model_id = data['model_id']
            source = data['source']

            # 验证参数
            if source not in ['huggingface', 'ollama']:
                return error_response("不支持的模型源", code='INVALID_SOURCE'), 400

            download_service = DownloadService()

            # 创建并开始下载任务
            task = download_service.create_download_task(model_id, source)
            result = download_service.start_download(task.id)

            return success_response(
                data={
                    "task": task.to_dict(),
                    "message": result['message']
                },
                message="下载任务已创建并开始"
            )

        except APIError as e:
            logger.error(f"Failed to start download: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Start download exception: {str(e)}")
            return error_response("Failed to start download"), 500


class DownloadControlController(Resource):
    """下载任务控制"""

    def put(self, task_id, action):
        """控制下载任务 (pause/resume)"""
        try:
            download_service = DownloadService()

            if action == 'pause':
                result = download_service.pause_download(task_id)
            elif action == 'resume':
                result = download_service.resume_download(task_id)
            else:
                return error_response(f"不支持的操作: {action}", code='INVALID_ACTION'), 400

            return success_response(
                data=result,
                message=f"任务{action}成功"
            )

        except APIError as e:
            logger.error(f"Failed to control download task: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Control download task exception: {str(e)}")
            return error_response("Failed to control download task"), 500


class DownloadTaskController(Resource):
    """下载任务管理"""

    def get(self, task_id):
        """获取下载任务状态"""
        try:
            download_service = DownloadService()
            task_info = download_service.get_download_status(task_id)

            return success_response(
                data=task_info,
                message="获取任务状态成功"
            )

        except APIError as e:
            logger.error(f"Failed to get download status: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get download status exception: {str(e)}")
            return error_response("Failed to get download status"), 500

    def delete(self, task_id):
        """删除下载任务"""
        try:
            download_service = DownloadService()
            result = download_service.delete_download(task_id)

            return success_response(
                data=result,
                message="删除下载任务成功"
            )

        except APIError as e:
            logger.error(f"Failed to delete download task: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Delete download task exception: {str(e)}")
            return error_response("Failed to delete download task"), 500


class DownloadListController(Resource):
    """下载任务列表"""

    def get(self):
        """获取下载任务列表"""
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

            download_service = DownloadService()
            result = download_service.list_downloads(status, page, page_size)

            return success_response(
                data=result,
                message="获取下载列表成功"
            )

        except APIError as e:
            logger.error(f"Failed to get download list: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get download list exception: {str(e)}")
            return error_response("Failed to get download list"), 500


class DownloadQueueController(Resource):
    """下载队列状态"""

    def get(self):
        """获取下载队列状态"""
        try:
            download_service = DownloadService()
            queue_info = download_service.get_download_queue()

            return success_response(
                data=queue_info,
                message="获取队列状态成功"
            )

        except APIError as e:
            logger.error(f"Failed to get queue status: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get queue status exception: {str(e)}")
            return error_response("Failed to get queue status"), 500


class DownloadStorageController(Resource):
    """存储空间管理"""

    def get(self):
        """获取存储空间信息"""
        try:
            download_service = DownloadService()
            storage_info = download_service.get_storage_info()

            return success_response(
                data=storage_info,
                message="获取存储信息成功"
            )

        except APIError as e:
            logger.error(f"Failed to get storage info: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Get storage info exception: {str(e)}")
            return error_response("Failed to get storage info"), 500


class DownloadCancelController(Resource):
    """取消下载"""

    def put(self, task_id):
        """取消下载任务"""
        try:
            download_service = DownloadService()
            result = download_service.cancel_download(task_id)

            return success_response(
                data=result,
                message="取消下载成功"
            )

        except APIError as e:
            logger.error(f"Failed to cancel download: {str(e)}")
            return error_response(str(e)), 400
        except Exception as e:
            logger.error(f"Cancel download exception: {str(e)}")
            return error_response("Failed to cancel download"), 500
