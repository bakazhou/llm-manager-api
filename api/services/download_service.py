import logging
import os
import shutil
import uuid
from typing import Optional, Dict, Any

from ..config import Config
from ..integrations.huggingface_client import HuggingFaceClient
from ..integrations.ollama_client import OllamaClient
from ..models.download_task import DownloadTask
from ..models.model import db
from ..utils.exceptions import (
    ValidationError,
    NotFoundError,
    DownloadError,
    StorageError
)

# 尝试导入Celery任务，如果失败则设为None
try:
    from tasks.download_tasks import download_model_task
except ImportError:
    download_model_task = None

logger = logging.getLogger(__name__)


class DownloadService:
    """下载服务"""

    def __init__(self):
        self.hf_client = HuggingFaceClient()
        self.ollama_client = OllamaClient()
        self.storage_path = Config.DOWNLOADS_PATH

        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)

    def create_download_task(self, model_id: str, source: str) -> DownloadTask:
        """创建下载任务"""
        try:
            # 验证模型存在
            if source == 'huggingface':
                model_info = self.hf_client.get_model_info(model_id)
                if not model_info:
                    raise NotFoundError(f"model {model_id} does not exist")
            elif source == 'ollama':
                # Ollama模型验证
                available_models = self.ollama_client.list_available_models()
                if model_id not in [m['name'] for m in available_models]:
                    raise NotFoundError(f"Ollama model {model_id} does not exist")
            else:
                raise ValidationError(f"Unsupported model source: {source}")

            # 检查是否已有下载任务
            existing_task = DownloadTask.get_by_model(model_id, source)
            if existing_task and existing_task.status in ['pending', 'downloading']:
                raise ValidationError(f"model {model_id} already has a pending or downloading download task")

            # 处理下载路径
            download_path = self._resolve_download_path(model_id, source)

            # 验证下载路径
            self._validate_download_path(download_path)

            # 检查存储空间
            self._check_storage_space()

            # 创建任务
            task_id = str(uuid.uuid4())
            task = DownloadTask(
                id=task_id,
                model_id=model_id,
                model_source=source,
                status='pending',
                file_path=download_path  # 设置自定义下载路径
            )

            db.session.add(task)
            db.session.commit()

            logger.info(f"Created download task: {task_id} for {model_id}, download path: {download_path}")
            return task

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create download task: {str(e)}")
            raise

    def start_download(self, task_id: str) -> Dict[str, Any]:
        """开始下载"""
        task = DownloadTask.query.get(task_id)
        if not task:
            raise NotFoundError(f"download task {task_id} does not exist")

        if task.status not in ['pending', 'paused']:
            raise ValidationError(f"task status {task.status} cannot start download")

        try:
            task.start_download()
            db.session.commit()

            # 这里会触发Celery异步任务
            if download_model_task:
                try:
                    result = download_model_task.delay(task_id)
                    logger.info(f"Celery task submitted: {result.id}")
                except Exception as e:
                    logger.error(f"Failed to submit Celery task: {e}")
                    # 不抛出异常，允许任务创建但记录错误
            else:
                logger.warning("Celery task system unavailable, download task will be created but not auto-started")

            logger.info(f"Starting download task: {task_id}")
            return {"message": "download has started", "task_id": task_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to start download: {str(e)}")
            raise DownloadError(f"Failed to start download: {str(e)}")

    def pause_download(self, task_id: str) -> Dict[str, Any]:
        """暂停下载"""
        task = DownloadTask.query.get(task_id)
        if not task:
            raise NotFoundError(f"download task {task_id} does not exist")

        if task.status != 'downloading':
            raise ValidationError(f"task status {task.status} cannot pause")

        try:
            task.pause_download()
            db.session.commit()

            # 这里可以发送信号给Celery任务暂停
            logger.info(f"Pausing download task: {task_id}")
            return {"message": "download has paused", "task_id": task_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to pause download: {str(e)}")
            raise DownloadError(f"Failed to pause download: {str(e)}")

    def resume_download(self, task_id: str) -> Dict[str, Any]:
        """继续下载"""
        task = DownloadTask.query.get(task_id)
        if not task:
            raise NotFoundError(f"download task {task_id} does not exist")

        # 允许暂停和失败的任务继续
        if task.status not in ['paused', 'failed']:
            raise ValidationError(f"task status {task.status} cannot continue")

        try:
            task.resume_download()
            db.session.commit()

            # 重新启动Celery任务
            if download_model_task:
                try:
                    result = download_model_task.delay(task_id)
                    logger.info(f"Celery task resubmitted: {result.id}")
                except Exception as e:
                    logger.error(f"Failed to resubmit Celery task: {e}")
            else:
                logger.warning("Celery task system unavailable, cannot continue download task")
            
            logger.info(f"Resuming download task: {task_id}")
            return {"message": "download has continued", "task_id": task_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to resume download: {str(e)}")
            raise DownloadError(f"Failed to resume download: {str(e)}")

    def cancel_download(self, task_id: str) -> Dict[str, Any]:
        """取消下载"""
        task = DownloadTask.query.get(task_id)
        if not task:
            raise NotFoundError(f"download task {task_id} does not exist")

        if task.status in ['completed', 'cancelled']:
            raise ValidationError(f"task status {task.status} cannot cancel")

        try:
            task.cancel_download()
            db.session.commit()

            # 删除部分下载的文件
            if task.file_path and os.path.exists(task.file_path):
                try:
                    if os.path.isfile(task.file_path):
                        os.remove(task.file_path)
                    elif os.path.isdir(task.file_path):
                        shutil.rmtree(task.file_path)
                    logger.info(f"Deleted download file/directory: {task.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file: {e}")

            logger.info(f"Cancelled download task: {task_id}")
            return {"message": "download has been cancelled", "task_id": task_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to cancel download: {str(e)}")
            raise DownloadError(f"Failed to cancel download: {str(e)}")

    def delete_download(self, task_id: str) -> Dict[str, Any]:
        """删除下载任务"""
        task = DownloadTask.query.get(task_id)
        if not task:
            raise NotFoundError(f"download task {task_id} does not exist")

        try:
            # 如果任务正在进行，先取消
            if task.status in ['pending', 'downloading']:
                self.cancel_download(task_id)
                # 重新获取任务状态
                task = DownloadTask.query.get(task_id)

            # 删除文件
            if task.file_path and os.path.exists(task.file_path):
                try:
                    if os.path.isfile(task.file_path):
                        os.remove(task.file_path)
                    elif os.path.isdir(task.file_path):
                        shutil.rmtree(task.file_path)
                    logger.info(f"Deleted download file/directory: {task.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file: {e}")

            # 删除任务记录
            db.session.delete(task)
            db.session.commit()

            logger.info(f"Deleted download task: {task_id}")
            return {"message": "download task has been deleted", "task_id": task_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete download task: {str(e)}")
            raise DownloadError(f"Failed to delete download task: {str(e)}")

    def get_download_status(self, task_id: str) -> Dict[str, Any]:
        """获取下载状态"""
        task = DownloadTask.query.get(task_id)
        if not task:
            raise NotFoundError(f"download task {task_id} does not exist")

        return task.to_dict()

    def list_downloads(self, status: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取下载任务列表"""
        query = DownloadTask.query

        if status:
            query = query.filter(DownloadTask.status == status)

        # 按创建时间倒序
        query = query.order_by(DownloadTask.created_at.desc())

        # 分页
        offset = (page - 1) * page_size
        tasks = query.offset(offset).limit(page_size).all()
        total = query.count()

        return {
            "tasks": [task.to_dict() for task in tasks],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }

    def get_download_queue(self) -> Dict[str, Any]:
        """获取下载队列状态"""
        active_tasks = DownloadTask.get_active_tasks()

        queue_info = {
            "total_active": len(active_tasks),
            "downloading": len([t for t in active_tasks if t.status == 'downloading']),
            "pending": len([t for t in active_tasks if t.status == 'pending']),
            "paused": len([t for t in active_tasks if t.status == 'paused']),
            "tasks": [task.to_dict() for task in active_tasks]
        }

        return queue_info

    def _check_storage_space(self, required_space: int = 1024 * 1024 * 1024):  # 1GB默认
        """检查存储空间"""
        try:
            stat = shutil.disk_usage(self.storage_path)
            free_space = stat.free

            if free_space < required_space:
                raise StorageError(
                    f"Storage space insufficient, need {required_space // (1024 ** 3)}GB, available {free_space // (1024 ** 3)}GB")

        except Exception as e:
            logger.error(f"Failed to check storage space: {e}")
            raise StorageError(f"Failed to check storage space: {str(e)}")

    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储空间信息"""
        try:
            # 获取磁盘使用情况
            total, used, free = shutil.disk_usage(self.storage_path)

            # 获取下载目录大小
            downloads_size = 0
            if os.path.exists(self.storage_path):
                for dirpath, dirnames, filenames in os.walk(self.storage_path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            downloads_size += os.path.getsize(filepath)
                        except OSError:
                            pass

            return {
                "total_space": total,
                "used_space": used,
                "free_space": free,
                "downloads_size": downloads_size,
                "downloads_path": self.storage_path
            }

        except Exception as e:
            logger.error(f"Failed to get storage info: {str(e)}")
            raise StorageError(f"Failed to get storage info: {str(e)}")

    def _resolve_download_path(self, model_id: str, source: str) -> str:
        """解析下载路径"""
        # 使用默认路径
        model_dir_name = model_id.replace('/', '_').replace(':', '_')
        download_path = os.path.join(self.storage_path, source, model_dir_name)

        return os.path.abspath(download_path)

    def _validate_download_path(self, download_path: str) -> None:
        """验证下载路径"""
        try:
            # 检查路径是否安全（防止路径遍历攻击）
            normalized_path = os.path.normpath(download_path)
            if '..' in normalized_path or normalized_path.startswith('/'):
                # 对于绝对路径，进行额外的安全检查
                if not os.path.commonpath([normalized_path, '/']) == '/':
                    raise ValidationError("download path contains unsafe characters")

            # 确保父目录存在
            parent_dir = os.path.dirname(download_path)
            if not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    logger.info(f"Created download directory: {parent_dir}")
                except OSError as e:
                    raise ValidationError(f"Failed to create download directory: {str(e)}")

            # 检查目录是否可写
            if not os.access(parent_dir, os.W_OK):
                raise ValidationError(f"download directory not writable: {parent_dir}")

            # 检查是否有足够的磁盘空间（至少1GB）
            _, _, free_space = shutil.disk_usage(parent_dir)
            min_space = 1024 * 1024 * 1024  # 1GB
            if free_space < min_space:
                raise ValidationError(f"Disk space insufficient, at least need {min_space // (1024 ** 3)}GB")

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to validate download path: {str(e)}")
