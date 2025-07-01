"""
集成模块
包含各种外部服务的客户端
"""

from .huggingface_client import HuggingFaceClient
from .ollama_client import OllamaClient
from .vllm_client import VLLMClient

__all__ = ['HuggingFaceClient', 'OllamaClient', 'VLLMClient']
