import logging
import os
import subprocess
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests

from ..config import Config
from ..models.deployment import Deployment
from ..models.model import Model
from ..models.model import db
from ..services.system_service import SystemService
from ..utils.exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
    APIError
)

logger = logging.getLogger(__name__)


class DeploymentService:
    """部署服务"""

    def __init__(self):
        self.system_service = SystemService()
        self.deployments_path = Config.MODELS_PATH

        # 确保部署目录存在
        os.makedirs(self.deployments_path, exist_ok=True)

    def create_deployment(self, model_id: str, source: str, name: str,
                          config: Optional[Dict] = None) -> Deployment:
        """创建部署"""
        try:
            # 验证模型是否存在
            model = Model.query.filter_by(id=model_id, source=source).first()
            if not model:
                raise NotFoundError(f"模型 {model_id} 不存在")

            # 检查部署名称是否重复
            existing = Deployment.query.filter_by(name=name).first()
            if existing:
                raise ConflictError(f"部署名称 {name} 已存在")

            # 分配端口
            port = self._allocate_port(config.get('port') if config else None)
            if not port:
                raise ValidationError("无法分配可用端口")

            # 创建部署记录
            deployment_id = str(uuid.uuid4())
            deployment = Deployment(
                id=deployment_id,
                model_id=model_id,
                model_source=source,
                name=name,
                port=port,
                host=config.get('host', '0.0.0.0') if config else '0.0.0.0',
                gpu_device=config.get('gpu_device') if config else None,
                cpu_cores=config.get('cpu_cores') if config else None,
                memory_limit=config.get('memory_limit') if config else None,
                config=config or {},
                status='pending'
            )

            db.session.add(deployment)
            db.session.commit()

            logger.info(f"Created deployment: {deployment_id} for {model_id}")
            return deployment

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create deployment: {str(e)}")
            raise

    def start_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """启动部署"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署 {deployment_id} 不存在")

        if deployment.status in ['running', 'deploying']:
            raise ValidationError(f"部署状态 {deployment.status} 不能启动")

        try:
            deployment.start_deployment()
            db.session.commit()



            # 根据模型源启动服务
            if deployment.model_source == 'huggingface':
                result = self._start_huggingface_deployment(deployment)
            elif deployment.model_source == 'ollama':
                result = self._start_ollama_deployment(deployment)
            else:
                raise ValidationError(f"不支持的模型源: {deployment.model_source}")

            if result.get('success'):
                deployment.complete_deployment(
                    container_id=result.get('container_id'),
                    port=deployment.port
                )
                # 设置健康检查URL - 根据模型源设置不同的URL
                if deployment.model_source == 'huggingface':
                    deployment.health_check_url = f"http://{deployment.host}:{deployment.port}/health"
                elif deployment.model_source == 'ollama':
                    deployment.health_check_url = f"http://{deployment.host}:{deployment.port}/api/tags"

                db.session.commit()



                logger.info(f"Deployment started successfully: {deployment_id}")

                # 构建返回的服务信息
                service_info = {
                    "message": "部署启动成功",
                    "deployment_id": deployment_id,
                    "service_url": deployment.get_service_url(),
                    "health_url": deployment.health_check_url
                }

                # 如果是vLLM部署，添加OpenAI兼容的API信息
                if deployment.model_source == 'huggingface':
                    service_info.update({
                        "api_base": f"http://{deployment.host}:{deployment.port}/v1",
                        "openai_compatible": True,
                        "endpoints": {
                            "chat_completions": f"http://{deployment.host}:{deployment.port}/v1/chat/completions",
                            "completions": f"http://{deployment.host}:{deployment.port}/v1/completions",
                            "models": f"http://{deployment.host}:{deployment.port}/v1/models"
                        }
                    })

                return service_info
            else:
                deployment.fail_deployment(result.get('error'))
                db.session.commit()
                

                
                raise APIError(f"部署启动失败: {result.get('error')}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to start deployment: {str(e)}")
            raise

    def stop_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """停止部署"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署 {deployment_id} 不存在")

        if deployment.status not in ['running', 'deploying']:
            raise ValidationError(f"部署状态 {deployment.status} 不能停止")

        try:
            # 停止服务
            if deployment.container_id:
                self._stop_container(deployment.container_id)

            deployment.stop_deployment()
            db.session.commit()

            logger.info(f"Stopping deployment: {deployment_id}")
            return {"message": "部署已停止", "deployment_id": deployment_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to stop deployment: {str(e)}")
            raise

    def restart_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """重启部署"""
        # 先停止
        self.stop_deployment(deployment_id)
        time.sleep(2)  # 等待停止完成

        # 再启动
        return self.start_deployment(deployment_id)

    def delete_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """删除部署"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署 {deployment_id} 不存在")

        try:
            # 如果正在运行，先停止
            if deployment.status in ['running', 'deploying']:
                self.stop_deployment(deployment_id)
                # 重新获取部署状态
                deployment = Deployment.query.get(deployment_id)

            # 删除部署记录
            db.session.delete(deployment)
            db.session.commit()

            logger.info(f"Deleting deployment: {deployment_id}")
            return {"message": "部署已删除", "deployment_id": deployment_id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete deployment: {str(e)}")
            raise

    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """获取部署状态"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署 {deployment_id} 不存在")

        # 获取实时状态
        if deployment.is_running():
            # 检查进程是否还在运行
            if deployment.container_id:
                is_alive = self._check_container_status(deployment.container_id)
                if not is_alive:
                    deployment.status = 'stopped'
                    db.session.commit()

        return deployment.to_dict()

    def list_deployments(self, status: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取部署列表"""
        query = Deployment.query

        if status:
            query = query.filter(Deployment.status == status)

        # 按创建时间倒序
        query = query.order_by(Deployment.created_at.desc())

        # 分页
        offset = (page - 1) * page_size
        deployments = query.offset(offset).limit(page_size).all()
        total = query.count()

        return {
            "deployments": [deployment.to_dict() for deployment in deployments],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }

    def get_deployment_logs(self, deployment_id: str, lines: int = 100) -> Dict[str, Any]:
        """获取部署日志"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署 {deployment_id} 不存在")

        try:
            logs = []

            if deployment.container_id:
                # 获取容器日志
                logs = self._get_container_logs(deployment.container_id, lines)
            else:
                # 获取进程日志（如果有日志文件）
                log_file = os.path.join(self.deployments_path, f"{deployment_id}.log")
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        logs = f.readlines()[-lines:]

            return {
                "deployment_id": deployment_id,
                "logs": logs,
                "lines": len(logs),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get deployment logs: {str(e)}")
            return {
                "deployment_id": deployment_id,
                "logs": [],
                "error": str(e)
            }

    def check_deployment_health(self, deployment_id: str) -> Dict[str, Any]:
        """检查部署健康状态"""
        deployment = Deployment.query.get(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署 {deployment_id} 不存在")

        try:
            if deployment.status != 'running':
                deployment.update_health_status('unhealthy')
                db.session.commit()
                return {
                    "deployment_id": deployment_id,
                    "healthy": False,
                    "status": deployment.status,
                    "last_check": deployment.last_health_check.isoformat() if deployment.last_health_check else None
                }

            # 检查进程是否存在
            if deployment.container_id and not self._check_container_status(deployment.container_id):
                deployment.update_health_status('unhealthy')
                deployment.status = 'stopped'
                db.session.commit()
                return {
                    "deployment_id": deployment_id,
                    "healthy": False,
                    "error": "进程不存在",
                    "last_check": deployment.last_health_check.isoformat() if deployment.last_health_check else None
                }

            # 检查服务端口是否可访问
            healthy = False
            response_data = None

            if deployment.model_source == 'huggingface':
                # vLLM健康检查
                try:
                    health_url = f"http://{deployment.host}:{deployment.port}/health"
                    response = requests.get(health_url, timeout=10)
                    if response.status_code == 200:
                        healthy = True
                        response_data = response.json()

                    # 额外检查模型端点
                    if healthy:
                        models_url = f"http://{deployment.host}:{deployment.port}/v1/models"
                        models_response = requests.get(models_url, timeout=5)
                        if models_response.status_code == 200:
                            models_data = models_response.json()
                            response_data['models'] = models_data.get('data', [])

                except requests.RequestException as e:
                    logger.warning(f"vLLM health check failed: {e}")
                    healthy = False
                    response_data = {"error": str(e)}

            elif deployment.model_source == 'ollama':
                # Ollama健康检查
                try:
                    health_url = f"http://{deployment.host}:{deployment.port}/api/tags"
                    response = requests.get(health_url, timeout=10)
                    healthy = response.status_code == 200
                    if healthy:
                        response_data = response.json()
                except requests.RequestException as e:
                    logger.warning(f"Ollama health check failed: {e}")
                    healthy = False
                    response_data = {"error": str(e)}

            # 更新健康状态
            if healthy:
                deployment.update_health_status('healthy')
            else:
                deployment.update_health_status('unhealthy')

            db.session.commit()

            result = {
                "deployment_id": deployment_id,
                "healthy": healthy,
                "port_accessible": healthy,
                "last_check": deployment.last_health_check.isoformat() if deployment.last_health_check else None
            }

            if response_data:
                result["response"] = response_data

            return result

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            deployment.update_health_status('error')
            db.session.commit()

            return {
                "deployment_id": deployment_id,
                "healthy": False,
                "error": str(e),
                "last_check": deployment.last_health_check.isoformat() if deployment.last_health_check else None
            }

    def _allocate_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """分配端口"""
        if preferred_port:
            if self.system_service.check_port_availability(preferred_port):
                return preferred_port
            else:
                raise ValidationError(f"端口 {preferred_port} 已被占用")

        # 自动分配端口
        return self.system_service.find_available_port(8000, 9000)

    def _start_huggingface_deployment(self, deployment: Deployment) -> Dict[str, Any]:
        """启动HuggingFace模型部署（使用vLLM）"""
        try:
            # 构建模型路径
            model_path = os.path.join(Config.DOWNLOADS_PATH, 'huggingface', deployment.model_id.replace('/', '_'))

            if not os.path.exists(model_path):
                return {"success": False, "error": f"模型文件不存在: {model_path}"}

            # 验证模型文件完整性
            required_files = ['config.json']
            for file in required_files:
                if not os.path.exists(os.path.join(model_path, file)):
                    return {"success": False, "error": f"模型文件不完整，缺少: {file}"}

            # 构建vLLM启动命令
            cmd = [
                'python', '-m', 'vllm.entrypoints.openai.api_server',
                '--model', model_path,
                '--host', deployment.host,
                '--port', str(deployment.port),
                '--served-model-name', deployment.model_id
            ]

            # 添加GPU配置
            if deployment.gpu_device is not None:
                # 设置CUDA_VISIBLE_DEVICES环境变量
                env = os.environ.copy()
                env['CUDA_VISIBLE_DEVICES'] = str(deployment.gpu_device)
            else:
                env = os.environ.copy()

            # 添加内存配置
            if deployment.config.get('gpu_memory_utilization'):
                cmd.extend(['--gpu-memory-utilization', str(deployment.config['gpu_memory_utilization'])])
            else:
                cmd.extend(['--gpu-memory-utilization', '0.8'])  # 默认使用80%的GPU内存

            # 添加最大模型长度配置
            if deployment.config.get('max_model_len'):
                cmd.extend(['--max-model-len', str(deployment.config['max_model_len'])])

            # 添加其他vLLM配置
            if deployment.config.get('tensor_parallel_size'):
                cmd.extend(['--tensor-parallel-size', str(deployment.config['tensor_parallel_size'])])

            if deployment.config.get('dtype'):
                cmd.extend(['--dtype', deployment.config['dtype']])
            else:
                cmd.extend(['--dtype', 'auto'])  # 自动选择数据类型

            # 启用OpenAI兼容API
            cmd.extend(['--enable-lora', '--enable-prefix-caching'])

            # 创建日志文件
            log_file = os.path.join(self.deployments_path, f"{deployment.id}_vllm.log")

            logger.info(f"Starting vLLM service: {' '.join(cmd)}")

            # 启动vLLM服务
            with open(log_file, 'w') as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=self.deployments_path
                )

            # 等待服务启动并检查健康状态
            max_wait_time = 120  # 最多等待2分钟
            wait_interval = 5  # 每5秒检查一次
            waited_time = 0

            while waited_time < max_wait_time:
                time.sleep(wait_interval)
                waited_time += wait_interval

                # 检查进程是否还在运行
                if process.poll() is not None:
                    # 进程已退出，读取日志
                    with open(log_file, 'r') as f:
                        logs = f.read()
                    return {
                        "success": False,
                        "error": f"vLLM进程启动失败，退出码: {process.returncode}",
                        "logs": logs[-1000:]  # 返回最后1000个字符的日志
                    }

                # 检查健康状态
                try:
                    health_url = f"http://{deployment.host}:{deployment.port}/health"
                    response = requests.get(health_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"vLLM service started successfully: {deployment.id}")
                        return {
                            "success": True,
                            "container_id": str(process.pid),
                            "port": deployment.port,
                            "api_base": f"http://{deployment.host}:{deployment.port}/v1",
                            "health_url": health_url
                        }
                except requests.RequestException:
                    # 服务还未就绪，继续等待
                    continue

            # 超时
            process.terminate()
            return {
                "success": False,
                "error": f"vLLM服务启动超时（{max_wait_time}秒），可能是模型太大或硬件资源不足"
            }

        except Exception as e:
            logger.error(f"Failed to start vLLM deployment: {str(e)}")
            return {"success": False, "error": str(e)}

    def _start_ollama_deployment(self, deployment: Deployment) -> Dict[str, Any]:
        """启动Ollama模型部署"""
        try:
            # Ollama模型通过ollama serve命令部署
            cmd = [
                'ollama', 'serve',
                '--host', deployment.host,
                '--port', str(deployment.port)
            ]

            if deployment.gpu_device:
                cmd.extend(['--gpu', deployment.gpu_device])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.deployments_path
            )

            # 等待服务启动
            time.sleep(3)

            if process.poll() is None:
                return {
                    "success": True,
                    "container_id": str(process.pid),
                    "port": deployment.port
                }
            else:
                stdout, stderr = process.communicate()
                return {
                    "success": False,
                    "error": f"Ollama服务启动失败: {stderr.decode()}"
                }

        except Exception as e:
            logger.error(f"Failed to start Ollama deployment: {str(e)}")
            return {"success": False, "error": str(e)}

    def _stop_container(self, container_id: str) -> bool:
        """停止容器/进程"""
        try:
            # 如果是进程ID，直接终止进程
            if container_id.isdigit():
                pid = int(container_id)
                return self.system_service.kill_process(pid)
            else:
                # 如果是Docker容器ID，停止容器
                subprocess.run(['docker', 'stop', container_id], check=True)
                return True
        except Exception as e:
            logger.error(f"Failed to stop container: {str(e)}")
            return False

    def _check_container_status(self, container_id: str) -> bool:
        """检查容器/进程状态"""
        try:
            if container_id.isdigit():
                # 检查进程是否存在
                pid = int(container_id)
                return self.system_service.get_process_info(pid) is not None
            else:
                # 检查Docker容器状态
                result = subprocess.run(
                    ['docker', 'inspect', '--format={{.State.Running}}', container_id],
                    capture_output=True, text=True
                )
                return result.stdout.strip() == 'true'
        except Exception:
            return False

    def _get_container_logs(self, container_id: str, lines: int = 100) -> List[str]:
        """获取容器日志"""
        try:
            if container_id.isdigit():
                # 进程日志（从日志文件读取）
                log_file = os.path.join(self.deployments_path, f"{container_id}.log")
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        return f.readlines()[-lines:]
                return []
            else:
                # Docker容器日志
                result = subprocess.run(
                    ['docker', 'logs', '--tail', str(lines), container_id],
                    capture_output=True, text=True
                )
                return result.stdout.split('\n')
        except Exception as e:
            logger.error(f"Failed to get container logs: {str(e)}")
            return []
