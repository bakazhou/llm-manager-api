"""
vLLM客户端
用于与vLLM部署的模型服务进行交互
"""

import json
import logging
from typing import Dict, Any, List, Iterator

import requests

logger = logging.getLogger(__name__)


class VLLMClient:
    """vLLM客户端"""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        初始化vLLM客户端
        
        Args:
            base_url: vLLM服务的基础URL，例如 http://localhost:8000
            timeout: 请求超时时间
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.api_base = f"{self.base_url}/v1"

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            response.raise_for_status()
            return {
                "success": True,
                "status": "healthy",
                "data": response.json()
            }
        except Exception as e:
            logger.error(f"vLLM health check failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def list_models(self) -> Dict[str, Any]:
        """获取可用模型列表"""
        try:
            response = requests.get(f"{self.api_base}/models", timeout=self.timeout)
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }
        except Exception as e:
            logger.error(f"Failed to get model list: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def chat_completion(self, messages: List[Dict[str, str]], model: str = None,
                        stream: bool = False, **kwargs) -> Dict[str, Any]:
        """
        聊天补全
        
        Args:
            messages: 聊天消息列表
            model: 模型名称（可选）
            stream: 是否流式输出
            **kwargs: 其他参数，如temperature, max_tokens等
        """
        try:
            payload = {
                "messages": messages,
                "stream": stream,
                **kwargs
            }

            if model:
                payload["model"] = model

            response = requests.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            response.raise_for_status()

            if stream:
                return {
                    "success": True,
                    "stream": self._parse_stream_response(response)
                }
            else:
                return {
                    "success": True,
                    "data": response.json()
                }

        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def completion(self, prompt: str, model: str = None,
                   stream: bool = False, **kwargs) -> Dict[str, Any]:
        """
        文本补全
        
        Args:
            prompt: 输入提示
            model: 模型名称（可选）
            stream: 是否流式输出
            **kwargs: 其他参数，如temperature, max_tokens等
        """
        try:
            payload = {
                "prompt": prompt,
                "stream": stream,
                **kwargs
            }

            if model:
                payload["model"] = model

            response = requests.post(
                f"{self.api_base}/completions",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            response.raise_for_status()

            if stream:
                return {
                    "success": True,
                    "stream": self._parse_stream_response(response)
                }
            else:
                return {
                    "success": True,
                    "data": response.json()
                }

        except Exception as e:
            logger.error(f"Text completion failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_stream_response(self, response) -> Iterator[Dict[str, Any]]:
        """解析流式响应"""
        try:
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # 移除 'data: ' 前缀
                        if data == '[DONE]':
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Failed to parse stream response: {e}")
            yield {"error": str(e)}

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """获取模型信息"""
        try:
            models_result = self.list_models()
            if not models_result["success"]:
                return models_result

            models = models_result["data"].get("data", [])
            for model_info in models:
                if model_info.get("id") == model:
                    return {
                        "success": True,
                        "data": model_info
                    }

            return {
                "success": False,
                "error": f"模型 {model} 不存在"
            }

        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        # 先检查健康状态
        health_result = self.health_check()
        if not health_result["success"]:
            return health_result

        # 再检查模型列表
        models_result = self.list_models()
        if not models_result["success"]:
            return models_result

        return {
            "success": True,
            "message": "连接测试成功",
            "health": health_result["data"],
            "models": models_result["data"]
        }
