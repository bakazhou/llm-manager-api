import logging
import re
from typing import Dict, List, Optional, Any

from ollama import Client

from ..utils.exceptions import ExternalServiceError, ModelNotFoundError

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama客户端"""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = Client(host=base_url)

        # Ollama模型信息映射
        self.model_info_cache = {}

        # 知名模型的预定义信息
        self.predefined_models = {
            'llama2': {
                'description': 'Meta的Llama 2大型语言模型',
                'model_type': 'text-generation',
                'parameters': '7B',
                'tags': ['meta', 'llama', 'text-generation', 'conversational']
            },
            'llama2:13b': {
                'description': 'Meta的Llama 2大型语言模型 - 13B参数版本',
                'model_type': 'text-generation',
                'parameters': '13B',
                'tags': ['meta', 'llama', 'text-generation', 'conversational']
            },
            'llama2:70b': {
                'description': 'Meta的Llama 2大型语言模型 - 70B参数版本',
                'model_type': 'text-generation',
                'parameters': '70B',
                'tags': ['meta', 'llama', 'text-generation', 'conversational']
            },
            'codellama': {
                'description': 'Meta的Code Llama代码生成模型',
                'model_type': 'text-generation',
                'parameters': '7B',
                'tags': ['meta', 'llama', 'code-generation', 'programming']
            },
            'codellama:13b': {
                'description': 'Meta的Code Llama代码生成模型 - 13B参数版本',
                'model_type': 'text-generation',
                'parameters': '13B',
                'tags': ['meta', 'llama', 'code-generation', 'programming']
            },
            'mistral': {
                'description': 'Mistral AI的7B参数模型',
                'model_type': 'text-generation',
                'parameters': '7B',
                'tags': ['mistral', 'text-generation', 'conversational']
            },
            'mixtral': {
                'description': 'Mistral AI的Mixtral混合专家模型',
                'model_type': 'text-generation',
                'parameters': '8x7B',
                'tags': ['mistral', 'text-generation', 'mixture-of-experts']
            },
            'neural-chat': {
                'description': 'Intel的Neural Chat模型',
                'model_type': 'text-generation',
                'parameters': '7B',
                'tags': ['intel', 'neural-chat', 'conversational']
            },
            'starling-lm': {
                'description': 'Berkeley的Starling语言模型',
                'model_type': 'text-generation',
                'parameters': '7B',
                'tags': ['berkeley', 'starling', 'text-generation']
            },
            'vicuna': {
                'description': 'LMSYS的Vicuna模型',
                'model_type': 'text-generation',
                'parameters': '7B',
                'tags': ['lmsys', 'vicuna', 'conversational']
            },
            'orca-mini': {
                'description': 'Microsoft的Orca Mini模型',
                'model_type': 'text-generation',
                'parameters': '3B',
                'tags': ['microsoft', 'orca', 'mini', 'conversational']
            }
        }

    def search_models(self, query: str = "", limit: int = 20, offset: int = 0,
                      model_type: Optional[str] = None, **kwargs) -> Dict:
        """搜索模型"""
        try:
            logger.info(f"Search Ollama models: query={query}, limit={limit}, offset={offset}")

            # 获取所有可用模型
            all_models = self._get_available_models()

            # 过滤模型
            filtered_models = []
            for model in all_models:
                # 文本搜索
                if query:
                    if (query.lower() not in model['name'].lower() and
                            query.lower() not in model['description'].lower()):
                        continue

                # 模型类型过滤
                if model_type and model['model_type'] != model_type:
                    continue

                filtered_models.append(model)

            # 分页
            total = len(filtered_models)
            start_idx = offset
            end_idx = min(offset + limit, total)
            page_models = filtered_models[start_idx:end_idx]

            return {
                'models': page_models,
                'total': total,
                'page': offset // limit + 1 if limit > 0 else 1,
                'page_size': limit,
                'source': 'ollama'
            }

        except Exception as e:
            logger.error(f"Failed to search Ollama models: {e}")
            raise ExternalServiceError(f"搜索模型失败: {e}")

    def get_model_info(self, model_id: str) -> Dict:
        """获取模型详细信息"""
        try:
            logger.info(f"Get Ollama model info: {model_id}")

            # 首先尝试从本地获取模型信息
            try:
                local_models = self.client.list()
                local_model = None
                for model in local_models.get('models', []):
                    if model['name'] == model_id or model['name'].startswith(f"{model_id}:"):
                        local_model = model
                        break

                if local_model:
                    return self._convert_local_model_info(local_model, detailed=True)
            except Exception as e:
                logger.warning(f"Failed to get local model info: {e}")

            # 如果本地没有，从预定义信息或在线获取
            model_info = self._get_model_info_from_registry(model_id)

            if not model_info:
                raise ModelNotFoundError(f"模型不存在: {model_id}")

            return model_info

        except ModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get Ollama model info: {e}")
            raise ExternalServiceError(f"获取模型信息失败: {e}")

    def get_model_categories(self) -> List[str]:
        """获取模型分类列表"""
        return [
            'text-generation',
            'code-generation',
            'conversational',
            'text-embedding',
            'image-to-text'
        ]

    def get_trending_models(self, limit: int = 10) -> List[Dict]:
        """获取热门模型"""
        try:
            logger.info(f"Get trending Ollama models: limit={limit}")

            # 返回一些热门的预定义模型
            trending_model_names = [
                'llama2', 'llama2:13b', 'mistral', 'codellama',
                'mixtral', 'neural-chat', 'vicuna', 'orca-mini'
            ]

            results = []
            for model_name in trending_model_names[:limit]:
                try:
                    model_info = self._get_model_info_from_registry(model_name)
                    if model_info:
                        results.append(model_info)
                except Exception as e:
                    logger.warning(f"Failed to get model info: {model_name}, error: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"Failed to get trending models: {e}")
            return []

    def get_local_models(self) -> List[Dict]:
        """获取本地已安装的模型"""
        try:
            logger.info("Get local Ollama models")

            models = self.client.list()
            results = []

            for model in models.get('models', []):
                model_info = self._convert_local_model_info(model)
                results.append(model_info)

            return results

        except Exception as e:
            logger.error(f"Failed to get local models: {e}")
            return []

    def _get_available_models(self) -> List[Dict]:
        """获取所有可用模型（本地+在线）"""
        models = []

        # 获取本地模型
        try:
            local_models = self.get_local_models()
            models.extend(local_models)
        except Exception as e:
            logger.warning(f"Failed to get local model: {e}")

        # 添加预定义的在线模型
        for model_name, model_data in self.predefined_models.items():
            # 检查是否已经在本地模型中
            if not any(m['id'] == model_name for m in models):
                model_info = self._create_model_info(model_name, model_data)
                model_info['is_local'] = False
                models.append(model_info)

        return models

    def _convert_local_model_info(self, model_data: Dict, detailed: bool = False) -> Dict:
        """转换本地模型信息为标准格式"""
        try:
            model_name = model_data['name']
            base_name = model_name.split(':')[0]

            # 获取预定义信息
            predefined = self.predefined_models.get(model_name) or self.predefined_models.get(base_name, {})

            # 基本信息
            result = {
                'id': model_name,
                'name': base_name,
                'full_name': model_name,
                'description': predefined.get('description', f'Ollama模型: {model_name}'),
                'source': 'ollama',
                'model_type': predefined.get('model_type', 'text-generation'),
                'tags': predefined.get('tags', []),
                'is_local': True,
                'created_at': None,
                'updated_at': model_data.get('modified_at'),
            }

            # 模型大小
            if 'size' in model_data:
                size_bytes = model_data['size']
                result['size_bytes'] = size_bytes
                result['size_gb'] = round(size_bytes / (1024 ** 3), 2)

            # 参数量
            parameters = predefined.get('parameters') or self._extract_parameters_from_name(model_name)
            if parameters:
                result['parameters'] = parameters

            # 详细信息
            if detailed:
                result['digest'] = model_data.get('digest', '')
                result['model_format'] = model_data.get('details', {}).get('format', '')
                result['quantization'] = model_data.get('details', {}).get('quantization_level', '')

                # 家族信息
                if 'details' in model_data:
                    details = model_data['details']
                    result['family'] = details.get('family', '')
                    result['families'] = details.get('families', [])
                    result['parent_model'] = details.get('parent_model', '')

            return result

        except Exception as e:
            logger.error(f"Failed to convert local model info: {e}")
            raise

    def _get_model_info_from_registry(self, model_id: str) -> Optional[Dict]:
        """从注册表获取模型信息"""
        try:
            # 首先尝试精确匹配
            if model_id in self.predefined_models:
                return self._create_model_info(model_id, self.predefined_models[model_id])

            # 尝试基础名称匹配
            base_name = model_id.split(':')[0]
            if base_name in self.predefined_models:
                model_data = self.predefined_models[base_name].copy()
                # 如果有标签，更新参数量
                if ':' in model_id:
                    tag = model_id.split(':')[1]
                    parameters = self._extract_parameters_from_name(tag)
                    if parameters:
                        model_data['parameters'] = parameters
                return self._create_model_info(model_id, model_data)

            # 如果都没有匹配，返回基本信息
            return self._create_basic_model_info(model_id)

        except Exception as e:
            logger.error(f"Failed to get model info from registry: {e}")
            return None

    def _create_model_info(self, model_id: str, model_data: Dict) -> Dict:
        """创建标准格式的模型信息"""
        base_name = model_id.split(':')[0]

        return {
            'id': model_id,
            'name': base_name,
            'full_name': model_id,
            'description': model_data.get('description', f'Ollama模型: {model_id}'),
            'source': 'ollama',
            'model_type': model_data.get('model_type', 'text-generation'),
            'parameters': model_data.get('parameters', ''),
            'tags': model_data.get('tags', []),
            'is_local': False,
            'created_at': None,
            'updated_at': None,
        }

    def _create_basic_model_info(self, model_id: str) -> Dict:
        """创建基本的模型信息"""
        base_name = model_id.split(':')[0]
        parameters = self._extract_parameters_from_name(model_id)

        return {
            'id': model_id,
            'name': base_name,
            'full_name': model_id,
            'description': f'Ollama模型: {model_id}',
            'source': 'ollama',
            'model_type': 'text-generation',
            'parameters': parameters or '',
            'tags': [],
            'is_local': False,
            'created_at': None,
            'updated_at': None,
        }

    def _extract_parameters_from_name(self, model_name: str) -> Optional[str]:
        """从模型名称中提取参数量"""
        # 常见的参数量模式
        patterns = [
            r'(\d+\.?\d*)[Bb]',  # 7B, 13B, 70B
            r'(\d+\.?\d*)[Mm]',  # 125M, 350M
            r'(\d+x\d+[Bb])',  # 8x7B (Mixtral)
        ]

        for pattern in patterns:
            match = re.search(pattern, model_name, re.IGNORECASE)
            if match:
                return match.group(0).upper()

        return None

    def validate_model_id(self, model_id: str) -> bool:
        """验证模型ID格式"""
        # Ollama模型ID格式: model-name 或 model-name:tag
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]+)?(:[\w\-_.]+)?$'
        return bool(re.match(pattern, model_id))

    def is_model_available(self, model_id: str) -> bool:
        """检查模型是否可用"""
        try:
            # 检查本地是否已安装
            local_models = self.client.list()
            for model in local_models.get('models', []):
                if model['name'] == model_id or model['name'].startswith(f"{model_id}:"):
                    return True

            # 检查是否在预定义列表中
            base_name = model_id.split(':')[0]
            return model_id in self.predefined_models or base_name in self.predefined_models

        except Exception:
            return False

    def pull_model(self, model_id: str) -> Dict[str, Any]:
        """拉取模型到本地"""
        try:
            logger.info(f"Pull Ollama model: {model_id}")

            # 使用ollama客户端拉取模型
            response = self.client.pull(model_id)

            # 检查是否成功
            if response.get('status') == 'success':
                return {"success": True, "model": model_id}
            else:
                return {"success": False, "error": response.get('error', '拉取失败')}

        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return {"success": False, "error": str(e)}

    def delete_model(self, model_id: str) -> bool:
        """删除本地模型"""
        try:
            logger.info(f"Delete Ollama model: {model_id}")

            # 使用ollama客户端删除模型
            self.client.delete(model_id)
            return True

        except Exception as e:
            logger.error(f"Failed to delete model: {e}")
            return False
