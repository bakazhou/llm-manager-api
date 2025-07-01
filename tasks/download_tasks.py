import logging
import os
import shutil
import time

from api.config import Config
from api.integrations.huggingface_client import HuggingFaceClient
from api.integrations.ollama_client import OllamaClient
from api.models.download_task import DownloadTask
from api.models.model import db
from . import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def download_model_task(self, task_id: str):
    """下载模型的异步任务"""
    # 延迟导入避免循环依赖
    from api.app import create_app

    # 创建应用上下文
    app = create_app()
    with app.app_context():
        task = None
        try:
            # 获取任务
            task = DownloadTask.query.get(task_id)
            if not task:
                logger.error(f"Download task {task_id} does not exist")
                return {"error": "任务不存在"}

            # 检查任务状态
            if task.status not in ['downloading', 'pending']:
                logger.info(f"Task {task_id} status is {task.status}, skipping download")
                return {"message": "任务已停止"}

            logger.info(f"Starting download task execution: {task_id}")

            # 根据模型源选择下载方法
            if task.model_source == 'huggingface':
                # 使用新的snapshot_download方法
                result = _download_huggingface_model_with_snapshot(task, self)
            elif task.model_source == 'ollama':
                result = _download_ollama_model(task, self)
            else:
                raise ValueError(f"不支持的模型源: {task.model_source}")

            return result

        except Exception as e:
            logger.error(f"Download task {task_id} failed: {str(e)}")
            if task:
                task.fail_download()
                db.session.commit()
            return {"error": str(e)}


def _download_huggingface_model_with_snapshot(task: DownloadTask, celery_task) -> dict:
    """使用snapshot_download方法下载HuggingFace模型"""
    try:
        hf_client = HuggingFaceClient()

        # 获取模型下载信息
        download_info = hf_client.get_model_download_info(task.model_id)
        total_size = download_info['total_size_bytes']

        # 更新任务总大小
        task.total_size = total_size
        db.session.commit()

        logger.info(f"Starting to download model {task.model_id}, total size: {download_info['total_size_gb']} GB, "
                    f"file count: {download_info['total_files']}")

        # 使用任务中指定的下载目录
        if task.file_path:
            model_dir = task.file_path
        else:
            model_dir = os.path.join(Config.DOWNLOADS_PATH, 'huggingface', task.model_id.replace('/', '_'))

        # 确保目录存在
        os.makedirs(model_dir, exist_ok=True)

        # 定义进度回调函数
        def progress_callback(progress_info):
            """进度回调函数"""
            try:
                # 检查任务状态
                current_task = DownloadTask.query.get(task.id)
                if current_task.status != 'downloading':
                    logger.info(f"Task {task.id} status changed to {current_task.status}, stopping download")
                    return

                downloaded_size = progress_info['downloaded_size']
                total_size = progress_info['total_size']
                progress_percent = progress_info['progress_percent']

                # 计算下载速度（简单估算）
                current_time = time.time()
                if not hasattr(progress_callback, 'start_time'):
                    progress_callback.start_time = current_time
                    progress_callback.last_downloaded = 0

                elapsed_time = current_time - progress_callback.start_time
                if elapsed_time > 0:
                    speed = downloaded_size / elapsed_time
                else:
                    speed = 0

                # 更新任务进度
                task.update_progress(downloaded_size, total_size, speed)
                db.session.commit()

                # 更新Celery任务状态
                celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'downloaded': downloaded_size,
                        'total': total_size,
                        'progress': progress_percent,
                        'speed': speed,
                        'files_completed': progress_info['files_completed'],
                        'current_file': progress_info['filename']
                    }
                )

                logger.info(f"Download progress: {progress_percent:.1f}% ({downloaded_size}/{total_size} bytes), "
                            f"speed: {speed / 1024 / 1024:.2f} MB/s, file: {progress_info['filename']}")

            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        # Define file filtering rules - ignore non-essential formats
        ignore_patterns = [
            "*.msgpack", "*.h5", "*.ot", "*.onnx", 
            "*.tflite", "*.pb", "*.pbtxt"
        ]

        # 使用snapshot_download下载模型
        result = hf_client.download_model_with_snapshot(
            model_id=task.model_id,
            local_dir=model_dir,
            progress_callback=progress_callback,
            ignore_patterns=ignore_patterns,
            resume_download=True  # 启用断点续传
        )

        # 更新任务状态为完成
        task.complete_download()
        task.file_path = result['local_path']
        task.download_size = result['total_size_bytes']
        db.session.commit()

        logger.info(f"Model download completed: {task.model_id}, path: {result['local_path']}, "
                    f"size: {result['total_size_gb']} GB")

        return {
            "success": True,
            "message": "模型下载完成",
            "path": result['local_path'],
            "size_gb": result['total_size_gb'],
            "files_count": result['total_files']
        }

    except Exception as e:
        logger.error(f"Failed to download model using snapshot_download: {str(e)}")
        task.fail_download()
        db.session.commit()
        raise


def _download_ollama_model(task: DownloadTask, celery_task) -> dict:
    """下载Ollama模型"""
    try:
        ollama_client = OllamaClient()

        # Ollama模型通过API拉取
        result = ollama_client.pull_model(task.model_id)

        if result.get('success'):
            task.file_path = f"ollama://{task.model_id}"
            task.complete_download()
            db.session.commit()
            logger.info(f"Ollama model {task.model_id} pull completed")
            return {"message": "模型拉取完成", "model": task.model_id}
        else:
            raise ValueError(f"Ollama模型拉取失败: {result.get('error', '未知错误')}")

    except Exception as e:
        logger.error(f"Failed to download Ollama model: {str(e)}")
        raise


@celery.task
def cleanup_failed_downloads():
    """清理失败的下载任务"""
    try:
        # 获取失败的任务
        failed_tasks = DownloadTask.query.filter(
            DownloadTask.status == 'failed'
        ).all()

        for task in failed_tasks:
            try:
                # 删除部分下载的文件
                if task.file_path and os.path.exists(task.file_path):
                    if os.path.isfile(task.file_path):
                        os.remove(task.file_path)
                    elif os.path.isdir(task.file_path):
                        shutil.rmtree(task.file_path)

                logger.info(f"Cleaning up failed download task: {task.id}")

            except Exception as e:
                logger.error(f"Failed to cleanup task {task.id}: {str(e)}")

        return {"cleaned_tasks": len(failed_tasks)}

    except Exception as e:
        logger.error(f"Error cleaning up failed download tasks: {str(e)}")
        return {"error": str(e)}


@celery.task
def retry_failed_downloads():
    """重试失败的下载任务"""
    try:
        # 获取可重试的失败任务
        retry_tasks = DownloadTask.query.filter(
            DownloadTask.status == 'failed'
        ).all()

        retried_count = 0
        for task in retry_tasks:
            try:
                # 重置任务状态
                task.status = 'pending'
                db.session.commit()

                # 重新启动下载
                download_model_task.delay(task.id)
                retried_count += 1

                logger.info(f"Retrying download task: {task.id}")

            except Exception as e:
                logger.error(f"Failed to retry task {task.id}: {str(e)}")

        return {"retried_tasks": retried_count}

    except Exception as e:
        logger.error(f"Error retrying failed download tasks: {str(e)}")
        return {"error": str(e)}


def _is_file_complete(file_path: str, expected_size: int) -> bool:
    """检查文件是否完整下载"""
    if not os.path.exists(file_path):
        return False

    if expected_size <= 0:
        # 如果不知道期望大小，认为存在即完整
        return True

    actual_size = os.path.getsize(file_path)
    return actual_size >= expected_size
