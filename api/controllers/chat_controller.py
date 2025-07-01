"""
聊天控制器
提供与部署的模型进行聊天交互的API
"""

import logging

from flask import request, Response
from flask_restful import Resource

from ..integrations.vllm_client import VLLMClient
from ..services.deployment_service import DeploymentService
from ..utils.exceptions import APIError
from ..utils.helpers import success_response, error_response
from ..utils.validators import validate_json

logger = logging.getLogger(__name__)


class ChatController(Resource):
    """聊天控制器"""

    def __init__(self):
        self.deployment_service = DeploymentService()

    def post(self, deployment_id):
        """
        与部署的模型进行聊天
        
        请求体参数:
        - messages: 聊天消息列表 (必需)
        - stream: 是否流式输出 (可选，默认false)
        - temperature: 温度参数 (可选)
        - max_tokens: 最大令牌数 (可选)
        - top_p: top_p参数 (可选)
        
        示例:
        {
            "messages": [
                {"role": "user", "content": "Hello!"}
            ],
            "stream": false,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        """
        try:
            # 验证请求数据
            data = validate_json(request, required_fields=['messages'])

            messages = data['messages']
            stream = data.get('stream', False)

            # 验证消息格式
            if not isinstance(messages, list) or not messages:
                return error_response("messages must be a non-empty array", code='INVALID_MESSAGES'), 400

            for msg in messages:
                if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                    return error_response("message format is incorrect, it needs to include role and content fields",
                                          code='INVALID_MESSAGE_FORMAT'), 400

            # 获取部署信息
            deployment = self.deployment_service.get_deployment_status(deployment_id)
            if deployment['status'] != 'running':
                return error_response(f"deployment status is {deployment['status']}, cannot chat",
                                      code='DEPLOYMENT_NOT_RUNNING'), 400

            # 检查是否支持聊天（目前只有vLLM支持）
            if deployment['model_source'] != 'huggingface':
                return error_response("This deployment does not support chat functionality", code='CHAT_NOT_SUPPORTED'), 400

            # 创建vLLM客户端
            base_url = f"http://{deployment['host']}:{deployment['port']}"
            vllm_client = VLLMClient(base_url)

            # 准备聊天参数
            chat_params = {
                'model': deployment['model_id'],
                'stream': stream
            }

            # 添加可选参数
            for param in ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty']:
                if param in data:
                    chat_params[param] = data[param]

            # 调用聊天API
            result = vllm_client.chat_completion(messages, **chat_params)

            if not result['success']:
                return error_response(f"chat request failed: {result['error']}", code='CHAT_REQUEST_FAILED'), 500

            if stream:
                # 流式响应
                def generate():
                    try:
                        for chunk in result['stream']:
                            if 'error' in chunk:
                                yield f"data: {{'error': '{chunk['error']}'}}\n\n"
                                break
                            yield f"data: {chunk}\n\n"
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Failed to generate streaming response: {e}")
                        yield f"data: {{'error': '{str(e)}'}}\n\n"

                return Response(
                    generate(),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*'
                    }
                )
            else:
                # 非流式响应
                return success_response(
                    data=result['data'],
                    message="chat request successful"
                )

        except APIError as e:
            logger.error(f"chat request failed: {str(e)}")
            return error_response(e.message, code=e.code), e.status_code
        except Exception as e:
            logger.error(f"Chat request failed: {str(e)}")
            return error_response("Chat request failed"), 500


class CompletionController(Resource):
    """文本补全控制器"""

    def __init__(self):
        self.deployment_service = DeploymentService()

    def post(self, deployment_id):
        """
        文本补全
        
        请求体参数:
        - prompt: 输入提示 (必需)
        - stream: 是否流式输出 (可选，默认false)
        - temperature: 温度参数 (可选)
        - max_tokens: 最大令牌数 (可选)
        - top_p: top_p参数 (可选)
        
        示例:
        {
            "prompt": "Once upon a time",
            "stream": false,
            "temperature": 0.7,
            "max_tokens": 100
        }
        """
        try:
            # 验证请求数据
            data = validate_json(request, required_fields=['prompt'])

            prompt = data['prompt']
            stream = data.get('stream', False)

            # 获取部署信息
            deployment = self.deployment_service.get_deployment_status(deployment_id)
            if deployment['status'] != 'running':
                return error_response(f"deployment status is {deployment['status']}, cannot complete text",
                                      code='DEPLOYMENT_NOT_RUNNING'), 400

            # 检查是否支持文本补全
            if deployment['model_source'] != 'huggingface':
                return error_response("This deployment does not support text completion functionality", code='COMPLETION_NOT_SUPPORTED'), 400

            # 创建vLLM客户端
            base_url = f"http://{deployment['host']}:{deployment['port']}"
            vllm_client = VLLMClient(base_url)

            # 准备补全参数
            completion_params = {
                'model': deployment['model_id'],
                'stream': stream
            }

            # 添加可选参数
            for param in ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty']:
                if param in data:
                    completion_params[param] = data[param]

            # 调用补全API
            result = vllm_client.completion(prompt, **completion_params)

            if not result['success']:
                return error_response(f"text completion request failed: {result['error']}", code='COMPLETION_REQUEST_FAILED'), 500

            if stream:
                # 流式响应
                def generate():
                    try:
                        for chunk in result['stream']:
                            if 'error' in chunk:
                                yield f"data: {{'error': '{chunk['error']}'}}\n\n"
                                break
                            yield f"data: {chunk}\n\n"
                        yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Failed to generate streaming response: {e}")
                        yield f"data: {{'error': '{str(e)}'}}\n\n"

                return Response(
                    generate(),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*'
                    }
                )
            else:
                # 非流式响应
                return success_response(
                    data=result['data'],
                    message="text completion request successful"
                )

        except APIError as e:
            logger.error(f"text completion request failed: {str(e)}")
            return error_response(e.message, code=e.code), e.status_code
        except Exception as e:
            logger.error(f"Text completion request failed: {str(e)}")
            return error_response("Text completion request failed"), 500


class ModelInfoController(Resource):
    """模型信息控制器"""

    def __init__(self):
        self.deployment_service = DeploymentService()

    def get(self, deployment_id):
        """获取部署的模型信息"""
        try:
            # 获取部署信息
            deployment = self.deployment_service.get_deployment_status(deployment_id)
            if deployment['status'] != 'running':
                return error_response(f"deployment status is {deployment['status']}, cannot get model info",
                                      code='DEPLOYMENT_NOT_RUNNING'), 400

            # 如果是vLLM部署，获取详细的模型信息
            if deployment['model_source'] == 'huggingface':
                base_url = f"http://{deployment['host']}:{deployment['port']}"
                vllm_client = VLLMClient(base_url)

                # 获取模型列表
                models_result = vllm_client.list_models()
                if models_result['success']:
                    deployment['vllm_models'] = models_result['data']

                # 获取健康状态
                health_result = vllm_client.health_check()
                if health_result['success']:
                    deployment['vllm_health'] = health_result['data']

            return success_response(
                data=deployment,
                message="get model info successful"
            )

        except APIError as e:
            logger.error(f"Failed to get model info: {str(e)}")
            return error_response(e.message, code=e.code), e.status_code
        except Exception as e:
            logger.error(f"Get model info exception: {str(e)}")
            return error_response("Failed to get model info"), 500
