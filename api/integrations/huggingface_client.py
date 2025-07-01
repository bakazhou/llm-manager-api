import fnmatch
import logging
import os
import re
from typing import Dict, List, Optional, Any, Callable

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.utils import HfHubHTTPError

from ..utils.exceptions import ExternalServiceError, ModelNotFoundError

logger = logging.getLogger(__name__)


class HuggingFaceClient:
    """HuggingFace Hub客户端"""

    def __init__(self, token: Optional[str] = None, cache_ttl: int = 3600):
        self.token = token
        self.cache_ttl = cache_ttl
        self.api = HfApi(token=token)
        self.base_url = "https://huggingface.co"

        # 支持的模型类型映射
        self.model_type_mapping = {
            'text-generation': ['text-generation', 'causal-lm'],
            'text-classification': ['text-classification', 'sentiment-analysis'],
            'text-to-text-generation': ['text2text-generation', 'summarization', 'translation'],
            'question-answering': ['question-answering'],
            'fill-mask': ['fill-mask', 'masked-lm'],
            'token-classification': ['token-classification', 'ner'],
            'text-embedding': ['sentence-similarity', 'feature-extraction'],
            'image-classification': ['image-classification'],
            'image-to-text': ['image-to-text'],
            'text-to-image': ['text-to-image'],
            'automatic-speech-recognition': ['automatic-speech-recognition'],
            'text-to-speech': ['text-to-speech'],
            'conversational': ['conversational'],
        }

    def search_models(self, query: str = "", limit: int = 20, offset: int = 0,
                      model_type: Optional[str] = None, sort: str = "downloads",
                      direction: str = "desc", **kwargs) -> Dict:
        """搜索模型"""
        try:
            logger.info(f"Search HuggingFace models: query={query}, limit={limit}, offset={offset}")

            # 如果没有查询关键词，返回热门模型
            if not query or query.strip() == "":
                logger.info("No query keywords provided, returning trending models")
                trending_models = self.get_trending_models(limit + offset)

                # 处理分页
                if offset > 0:
                    trending_models = trending_models[offset:]
                trending_models = trending_models[:limit]

                return {
                    'models': trending_models,
                    'total': len(trending_models),
                    'page': offset // limit + 1 if limit > 0 else 1,
                    'page_size': limit,
                    'source': 'huggingface'
                }

            # 有查询关键词时进行搜索
            logger.info(f"Execute keyword search: {query}")

            # 准备搜索参数
            search_params = {
                'search': query,
                'sort': sort,
                'direction': -1 if direction.lower() == "desc" else None,
                'limit': max(limit * 5, 200),  # 搜索更多模型用于过滤
                'full': True
            }

            # 如果指定了模型类型，添加task过滤
            if model_type:
                # 将标准化的模型类型转换为HF的任务类型
                hf_tasks = self.model_type_mapping.get(model_type, [model_type])
                if hf_tasks:
                    search_params['task'] = hf_tasks[0]

            # 搜索模型
            models = self.api.list_models(**search_params)

            # 转换为列表
            model_list = list(models)
            logger.info(f"HuggingFace API returned {len(model_list)} search results")

            # 过滤高质量模型：设置下载量阈值
            min_downloads = 1000  # 最小下载量阈值
            quality_models = []

            for model in model_list:
                try:
                    downloads = getattr(model, 'downloads', 0) or 0
                    if downloads >= min_downloads:
                        quality_models.append(model)
                except Exception as e:
                    logger.warning(f"Failed to check model downloads: {getattr(model, 'id', 'unknown')}, error: {e}")
                    continue

            logger.info(f"After filtering, got {len(quality_models)} high-quality models (downloads >= {min_downloads})")

            # 如果过滤后的高质量模型不够，降低阈值重新过滤
            if len(quality_models) < limit:
                min_downloads = 100
                quality_models = []
                for model in model_list:
                    try:
                        downloads = getattr(model, 'downloads', 0) or 0
                        if downloads >= min_downloads:
                            quality_models.append(model)
                    except Exception as e:
                        continue
                logger.info(f"After lowering threshold, got {len(quality_models)} models (downloads >= {min_downloads})")

            # 如果还是不够，使用所有模型但按下载量排序
            if len(quality_models) < limit:
                quality_models = sorted(model_list,
                                        key=lambda x: getattr(x, 'downloads', 0) or 0,
                                        reverse=True)
                logger.info(f"Using all search results sorted by downloads: {len(quality_models)} models")

            # 处理分页
            if offset > 0:
                quality_models = quality_models[offset:]
            quality_models = quality_models[:limit]

            # 转换为标准格式
            results = []
            for model in quality_models:
                try:
                    model_info = self._convert_model_info(model)
                    results.append(model_info)
                except Exception as e:
                    logger.warning(f"Failed to convert model info: {getattr(model, 'id', 'unknown')}, error: {e}")
                    continue

            logger.info(f"Finally returning {len(results)} models")
            return {
                'models': results,
                'total': len(results),
                'page': offset // limit + 1 if limit > 0 else 1,
                'page_size': limit,
                'source': 'huggingface'
            }

        except HfHubHTTPError as e:
            logger.error(f"HuggingFace API error: {e}")
            raise ExternalServiceError(f"HuggingFace API错误: {e}")
        except Exception as e:
            logger.error(f"Failed to search HuggingFace models: {e}")
            raise ExternalServiceError(f"搜索模型失败: {e}")

    def get_model_info(self, model_id: str) -> Dict:
        """获取模型详细信息"""
        try:
            logger.info(f"Get HuggingFace model info: {model_id}")

            # 获取模型信息
            model_info = self.api.model_info(model_id, files_metadata=True)

            if not model_info:
                raise ModelNotFoundError(f"模型不存在: {model_id}")

            # 转换为标准格式
            result = self._convert_model_info(model_info, detailed=True)

            return result

        except HfHubHTTPError as e:
            if e.response.status_code == 404:
                raise ModelNotFoundError(f"模型不存在: {model_id}")
            logger.error(f"HuggingFace API error: {e}")
            raise ExternalServiceError(f"HuggingFace API错误: {e}")
        except ModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get HuggingFace model info: {e}")
            raise ExternalServiceError(f"获取模型信息失败: {e}")

    def get_model_categories(self) -> List[str]:
        """获取模型分类列表"""
        try:
            # 返回支持的模型类型
            return list(self.model_type_mapping.keys())
        except Exception as e:
            logger.error(f"Failed to get model categories: {e}")
            return []

    def get_trending_models(self, limit: int = 10) -> List[Dict]:
        """获取热门模型"""
        try:
            logger.info(f"Get trending HuggingFace models: limit={limit}")

            # 获取更多模型用于筛选，确保能返回足够的高质量模型
            fetch_limit = max(limit * 2, 50)

            # 按下载量排序获取热门模型，direction=-1表示降序
            models = self.api.list_models(
                sort="downloads",
                direction=-1,
                limit=fetch_limit,
                full=True
            )

            results = []
            processed_count = 0

            for model in models:
                try:
                    # 过滤掉下载量过低的模型
                    downloads = getattr(model, 'downloads', 0) or 0
                    if downloads < 100:  # 最低下载量阈值
                        continue

                    model_info = self._convert_model_info(model)
                    results.append(model_info)
                    processed_count += 1

                    # 达到所需数量就停止
                    if processed_count >= limit:
                        break

                except Exception as e:
                    logger.warning(f"Failed to convert model info: {getattr(model, 'id', 'unknown')}, error: {e}")
                    continue

            logger.info(f"Successfully got {len(results)} trending models")
            return results

        except Exception as e:
            logger.error(f"Failed to get trending models: {e}")
            return []

    def _convert_model_info(self, model_info, detailed: bool = False) -> Dict:
        """转换模型信息为标准格式"""
        try:
            # 基本信息
            result = {
                'id': model_info.id,
                'name': model_info.id.split('/')[-1],  # 获取模型名称
                'full_name': model_info.id,
                'description': getattr(model_info, 'description', '') or '',
                'source': 'huggingface',
                'url': f"{self.base_url}/{model_info.id}",
                'created_at': getattr(model_info, 'created_at', None).isoformat() if getattr(model_info, 'created_at',
                                                                                             None) else None,
                'updated_at': getattr(model_info, 'last_modified', None).isoformat() if getattr(model_info,
                                                                                                'last_modified',
                                                                                                None) else None,
            }

            # 模型类型和任务
            pipeline_tag = getattr(model_info, 'pipeline_tag', None)
            if pipeline_tag:
                # 将HF的任务类型转换为标准化类型
                for standard_type, hf_tasks in self.model_type_mapping.items():
                    if pipeline_tag in hf_tasks:
                        result['model_type'] = standard_type
                        break
                else:
                    result['model_type'] = pipeline_tag
            else:
                result['model_type'] = 'unknown'

            # 标签
            tags = getattr(model_info, 'tags', []) or []
            result['tags'] = [tag for tag in tags if tag]

            # 下载量和点赞数
            result['downloads'] = getattr(model_info, 'downloads', 0) or 0
            result['likes'] = getattr(model_info, 'likes', 0) or 0

            # 模型大小和参数量
            if detailed and hasattr(model_info, 'siblings'):
                total_size = 0
                file_count = 0
                for sibling in model_info.siblings or []:
                    if hasattr(sibling, 'size') and sibling.size:
                        total_size += sibling.size
                        file_count += 1

                if total_size > 0:
                    result['size_bytes'] = total_size
                    result['size_gb'] = round(total_size / (1024 ** 3), 2)
                    result['file_count'] = file_count

            # 从模型名称或标签中提取参数量
            parameters = self._extract_parameters(model_info.id, tags)
            if parameters:
                result['parameters'] = parameters

            # 额外的详细信息
            if detailed:
                # 作者信息
                if '/' in model_info.id:
                    result['author'] = model_info.id.split('/')[0]

                # 许可证
                if hasattr(model_info, 'card_data') and model_info.card_data:
                    license_info = model_info.card_data.get('license')
                    if license_info:
                        result['license'] = license_info

                # 数据集信息
                if hasattr(model_info, 'card_data') and model_info.card_data:
                    datasets = model_info.card_data.get('datasets', [])
                    if datasets:
                        result['datasets'] = datasets

                # 语言信息
                if hasattr(model_info, 'card_data') and model_info.card_data:
                    languages = model_info.card_data.get('language', [])
                    if languages:
                        result['languages'] = languages if isinstance(languages, list) else [languages]

            return result

        except Exception as e:
            logger.error(f"Failed to convert model info: {e}")
            raise

    def _extract_parameters(self, model_id: str, tags: List[str]) -> Optional[str]:
        """从模型ID或标签中提取参数量"""
        # 常见的参数量模式
        patterns = [
            r'(\d+\.?\d*)[Bb]',  # 7B, 13B, 70B
            r'(\d+\.?\d*)[Mm]',  # 125M, 350M
            r'(\d+\.?\d*)B',  # 7B, 13B
            r'(\d+\.?\d*)M',  # 125M, 350M
        ]

        # 在模型ID中搜索
        for pattern in patterns:
            match = re.search(pattern, model_id, re.IGNORECASE)
            if match:
                return match.group(0).upper()

        # 在标签中搜索
        for tag in tags:
            for pattern in patterns:
                match = re.search(pattern, tag, re.IGNORECASE)
                if match:
                    return match.group(0).upper()

        return None

    def validate_model_id(self, model_id: str) -> bool:
        """验证模型ID格式"""
        # HuggingFace模型ID格式: username/model-name
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]+)?/[a-zA-Z0-9]([a-zA-Z0-9\-_.]+)?$'
        return bool(re.match(pattern, model_id))

    def get_download_urls(self, model_id: str) -> List[Dict[str, Any]]:
        """获取模型所有文件的下载链接"""
        try:
            # 获取模型信息包含文件列表
            model_info = self.api.model_info(model_id, files_metadata=True)

            download_urls = []
            for sibling in model_info.siblings or []:
                if sibling.rfilename:
                    download_url = f"https://huggingface.co/{model_id}/resolve/main/{sibling.rfilename}"
                    download_urls.append({
                        'filename': sibling.rfilename,
                        'url': download_url,
                        'size': getattr(sibling, 'size', None)
                    })

            return download_urls

        except Exception as e:
            logger.error(f"Failed to get HuggingFace model download link {model_id}: {str(e)}")
            return []

    def get_download_url(self, model_id: str, filename: str = None) -> str:
        """获取模型下载URL"""
        if filename:
            return f"{self.base_url}/{model_id}/resolve/main/{filename}"
        else:
            return f"{self.base_url}/{model_id}/tree/main"

    def download_model_with_snapshot(
            self,
            model_id: str,
            local_dir: str,
            progress_callback: Optional[Callable] = None,
            allow_patterns: Optional[List[str]] = None,
            ignore_patterns: Optional[List[str]] = None,
            resume_download: bool = True
    ) -> Dict[str, Any]:
        """
        使用snapshot_download方法下载模型
        
        Args:
            model_id: 模型ID
            local_dir: 本地下载目录
            progress_callback: 进度回调函数
            allow_patterns: 允许下载的文件模式（如 ["*.json", "*.bin"]）
            ignore_patterns: 忽略的文件模式（如 ["*.msgpack", "*.h5"]）
            resume_download: 是否支持断点续传
            
        Returns:
            下载结果信息
        """
        try:
            logger.info(f"Starting to download model using snapshot_download: {model_id} -> {local_dir}")

            # 确保目录存在
            os.makedirs(local_dir, exist_ok=True)

            # 获取模型信息用于计算总大小
            model_info = self.api.model_info(model_id, files_metadata=True)
            total_size = 0
            file_count = 0

            if hasattr(model_info, 'siblings') and model_info.siblings:
                for sibling in model_info.siblings:
                    if hasattr(sibling, 'size') and sibling.size:
                        # 检查文件是否匹配过滤条件
                        should_download = True

                        if allow_patterns:
                            should_download = any(
                                self._match_pattern(sibling.rfilename, pattern)
                                for pattern in allow_patterns
                            )

                        if ignore_patterns and should_download:
                            should_download = not any(
                                self._match_pattern(sibling.rfilename, pattern)
                                for pattern in ignore_patterns
                            )

                        if should_download:
                            total_size += sibling.size
                            file_count += 1

            logger.info(f"Expected to download {file_count} files, total size: {total_size / (1024 ** 3):.2f} GB")

            # 创建进度跟踪器
            class ProgressTracker:
                def __init__(self, total_size: int, callback: Optional[Callable] = None):
                    self.total_size = total_size
                    self.downloaded_size = 0
                    self.callback = callback
                    self.files_completed = 0

                def __call__(self, filename: str, size: int):
                    """HuggingFace Hub调用的进度回调"""
                    self.downloaded_size += size
                    self.files_completed += 1

                    if self.callback:
                        progress_info = {
                            'filename': filename,
                            'file_size': size,
                            'downloaded_size': self.downloaded_size,
                            'total_size': self.total_size,
                            'progress_percent': (
                                        self.downloaded_size / self.total_size * 100) if self.total_size > 0 else 0,
                            'files_completed': self.files_completed
                        }
                        self.callback(progress_info)

            # 创建进度跟踪器实例
            progress_tracker = ProgressTracker(total_size, progress_callback) if progress_callback else None

            # 准备下载参数
            download_kwargs = {
                'repo_id': model_id,
                'local_dir': local_dir,
                'resume_download': resume_download,
                'token': self.token,
                'local_dir_use_symlinks': False,  # 使用实际文件而不是符号链接
            }

            # 添加文件过滤
            if allow_patterns:
                download_kwargs['allow_patterns'] = allow_patterns
            if ignore_patterns:
                download_kwargs['ignore_patterns'] = ignore_patterns

            # 执行下载
            logger.info(f"Starting to download model files to: {local_dir}")
            downloaded_path = snapshot_download(**download_kwargs)

            # 计算实际下载的文件信息
            actual_size = 0
            actual_files = 0

            if os.path.exists(downloaded_path):
                for root, dirs, files in os.walk(downloaded_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            actual_size += os.path.getsize(file_path)
                            actual_files += 1

            result = {
                'success': True,
                'model_id': model_id,
                'local_path': downloaded_path,
                'total_files': actual_files,
                'total_size_bytes': actual_size,
                'total_size_gb': round(actual_size / (1024 ** 3), 2),
                'message': f'模型 {model_id} 下载完成'
            }

            logger.info(f"Model download completed: {model_id}, path: {downloaded_path}, "
                        f"文件数: {actual_files}, 大小: {result['total_size_gb']} GB")

            return result

        except HfHubHTTPError as e:
            if e.response.status_code == 404:
                raise ModelNotFoundError(f"模型不存在: {model_id}")
            logger.error(f"HuggingFace API error: {e}")
            raise ExternalServiceError(f"下载模型失败: {e}")
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {str(e)}")
            raise ExternalServiceError(f"下载模型失败: {str(e)}")

    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """检查文件名是否匹配模式"""
        return fnmatch.fnmatch(filename, pattern)

    def get_model_download_info(self, model_id: str) -> Dict[str, Any]:
        """获取模型下载信息（文件列表、大小等）"""
        try:
            model_info = self.api.model_info(model_id, files_metadata=True)

            files_info = []
            total_size = 0

            if hasattr(model_info, 'siblings') and model_info.siblings:
                for sibling in model_info.siblings:
                    file_info = {
                        'filename': sibling.rfilename,
                        'size': getattr(sibling, 'size', 0) or 0,
                        'size_mb': round((getattr(sibling, 'size', 0) or 0) / (1024 ** 2), 2)
                    }
                    files_info.append(file_info)
                    total_size += file_info['size']

            return {
                'model_id': model_id,
                'files': files_info,
                'total_files': len(files_info),
                'total_size_bytes': total_size,
                'total_size_gb': round(total_size / (1024 ** 3), 2)
            }

        except Exception as e:
            logger.error(f"Failed to get model download info {model_id}: {str(e)}")
            raise ExternalServiceError(f"获取模型信息失败: {str(e)}")
