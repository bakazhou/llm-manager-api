"""模型管理服务"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import redis

from ..integrations.huggingface_client import HuggingFaceClient
from ..integrations.ollama_client import OllamaClient
from ..models.model import Model, db
from ..utils.exceptions import ValidationError, ModelNotFoundError, ExternalServiceError
from ..utils.helpers import (
    normalize_model_info, merge_model_info,
    paginate_results, extract_model_stats,
    build_search_filters, build_sort_options, calculate_offset
)
from ..utils.validators import validate_search_params, validate_model_id

logger = logging.getLogger(__name__)


class ModelService:
    """模型管理服务"""

    def __init__(self, config=None):
        self.config = config or {}

        # 初始化客户端
        self.hf_client = HuggingFaceClient(
            token=self.config.get('HUGGINGFACE_TOKEN'),
            cache_ttl=self.config.get('HUGGINGFACE_CACHE_TTL', 3600)
        )

        self.ollama_client = OllamaClient(
            base_url=self.config.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        )

        # 初始化Redis缓存（如果配置了）
        self.cache = None
        if self.config.get('REDIS_URL'):
            try:
                self.cache = redis.from_url(self.config['REDIS_URL'])
            except Exception as e:
                logger.warning(f"Redis connection failed, caching will be disabled: {e}")

    def search_models(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索模型"""
        try:
            # 验证参数
            validated_params = validate_search_params(params)

            logger.info(f"Search models: {validated_params}")

            # 构建过滤器和排序
            filters = build_search_filters(validated_params)
            sort_options = build_sort_options(validated_params)

            page = validated_params['page']
            page_size = validated_params['page_size']

            # 根据来源搜索
            source = filters.get('source')

            if source == 'huggingface':
                return self._search_huggingface_models(filters, sort_options, page, page_size)
            elif source == 'ollama':
                return self._search_ollama_models(filters, sort_options, page, page_size)
            else:
                # 多源搜索
                return self._search_multi_source_models(filters, sort_options, page, page_size)

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to search models: {e}")
            raise ExternalServiceError(f"Failed to search models: {e}")

    def get_model_info(self, model_id: str, source: Optional[str] = None) -> Dict[str, Any]:
        """获取模型详细信息"""
        try:
            # 验证模型ID
            model_id = validate_model_id(model_id, source)

            logger.info(f"Get model info: {model_id}, source: {source}")

            # 首先尝试从数据库获取
            cached_model = self._get_model_from_db(model_id, source)

            # 根据来源获取最新信息
            if source == 'huggingface' or (not source and '/' in model_id):
                external_info = self.hf_client.get_model_info(model_id)
                source = 'huggingface'
            elif source == 'ollama' or (not source and ':' in model_id):
                external_info = self.ollama_client.get_model_info(model_id)
                source = 'ollama'
            else:
                # 尝试自动检测来源
                try:
                    if '/' in model_id:
                        external_info = self.hf_client.get_model_info(model_id)
                        source = 'huggingface'
                    else:
                        external_info = self.ollama_client.get_model_info(model_id)
                        source = 'ollama'
                except:
                    raise ModelNotFoundError(f"模型不存在: {model_id}")

            # 合并信息
            if cached_model:
                # 增加查看次数
                cached_model.increment_view_count()
                db.session.commit()

                # 合并最新的外部信息
                model_info = merge_model_info(cached_model.to_dict(), external_info)
            else:
                # 创建新的模型记录
                model_info = external_info
                self._save_model_to_db(model_info)

            # 标准化信息
            normalized_info = normalize_model_info(model_info)

            return normalized_info

        except (ValidationError, ModelNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            raise ExternalServiceError(f"Failed to get model info: {e}")

    def get_model_categories(self, source: Optional[str] = None) -> List[str]:
        """获取模型分类列表"""
        try:
            if source == 'huggingface':
                return self.hf_client.get_model_categories()
            elif source == 'ollama':
                return self.ollama_client.get_model_categories()
            else:
                # 合并所有来源的分类
                hf_categories = self.hf_client.get_model_categories()
                ollama_categories = self.ollama_client.get_model_categories()

                # 去重合并
                all_categories = list(set(hf_categories + ollama_categories))
                all_categories.sort()

                return all_categories

        except Exception as e:
            logger.error(f"Failed to get model categories: {e}")
            return []

    def get_trending_models(self, limit: int = 10, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取热门模型"""
        try:
            logger.info(f"Get trending models: limit={limit}, source={source}")

            results = []

            if source == 'huggingface':
                results = self.hf_client.get_trending_models(limit)
            elif source == 'ollama':
                results = self.ollama_client.get_trending_models(limit)
            else:
                # 从多个来源获取
                hf_limit = limit // 2
                ollama_limit = limit - hf_limit

                hf_models = self.hf_client.get_trending_models(hf_limit)
                ollama_models = self.ollama_client.get_trending_models(ollama_limit)

                results = hf_models + ollama_models

            # 标准化结果
            normalized_results = []
            for model in results:
                try:
                    normalized = normalize_model_info(model)
                    normalized_results.append(normalized)
                except Exception as e:
                    logger.warning(f"Failed to normalize model info: {e}")
                    continue

            return normalized_results

        except Exception as e:
            logger.error(f"Failed to get trending models: {e}")
            return []

    def get_model_stats(self, source: Optional[str] = None) -> Dict[str, Any]:
        """获取模型统计信息"""
        try:
            logger.info(f"Get model stats: source={source}")

            # 从数据库获取统计信息
            query = Model.query
            if source:
                query = query.filter(Model.source == source)

            models = query.all()
            model_dicts = [model.to_dict() for model in models]

            stats = extract_model_stats(model_dicts)

            # 添加额外统计信息
            stats['last_updated'] = datetime.utcnow().isoformat() + 'Z'

            return stats

        except Exception as e:
            logger.error(f"Failed to get model stats: {e}")
            return {}

    def favorite_model(self, model_id: str, user_id: Optional[str] = None) -> bool:
        """收藏模型"""
        try:
            # 获取或创建模型记录
            model = self._get_or_create_model(model_id)

            # 增加收藏次数
            model.increment_favorite_count()
            db.session.commit()

            logger.info(f"Model favorited successfully: {model_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to favorite model: {e}")
            return False

    def unfavorite_model(self, model_id: str, user_id: Optional[str] = None) -> bool:
        """取消收藏模型"""
        try:
            model = Model.query.filter(Model.id == model_id).first()
            if model:
                model.decrement_favorite_count()
                db.session.commit()

            logger.info(f"Model unfavorited: {model_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unfavorite model: {e}")
            return False

    def sync_models_from_source(self, source: str, limit: int = 100) -> int:
        """从外部源同步模型信息"""
        try:
            logger.info(f"Start syncing models: source={source}, limit={limit}")

            synced_count = 0

            if source == 'huggingface':
                # 获取热门模型进行同步
                models = self.hf_client.get_trending_models(limit)
                for model_info in models:
                    try:
                        self._save_model_to_db(model_info)
                        synced_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to sync model: {model_info.get('id')}, error: {e}")

            elif source == 'ollama':
                # 获取本地模型进行同步
                models = self.ollama_client.get_local_models()
                for model_info in models:
                    try:
                        self._save_model_to_db(model_info)
                        synced_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to sync model: {model_info.get('id')}, error: {e}")

            logger.info(f"Sync completed: source={source}, synced={synced_count}")
            return synced_count

        except Exception as e:
            logger.error(f"Failed to sync models: {e}")
            return 0

    def _search_huggingface_models(self, filters: Dict[str, Any],
                                   sort_options: Dict[str, Any],
                                   page: int, page_size: int) -> Dict[str, Any]:
        """搜索HuggingFace模型"""
        offset = calculate_offset(page, page_size)

        # 获取查询关键词，如果为空则传递None
        query = filters.get('query', '').strip()
        query = query if query else None

        result = self.hf_client.search_models(
            query=query,
            limit=page_size,
            offset=offset,
            model_type=filters.get('model_type'),
            sort=sort_options['sort_by'],
            direction=sort_options['sort_order']
        )

        # 标准化结果
        normalized_models = []
        for model in result['models']:
            normalized = normalize_model_info(model)
            normalized_models.append(normalized)

        return paginate_results(
            normalized_models,
            page,
            page_size,
            result.get('total', len(normalized_models))
        )

    def _search_ollama_models(self, filters: Dict[str, Any],
                              sort_options: Dict[str, Any],
                              page: int, page_size: int) -> Dict[str, Any]:
        """搜索Ollama模型"""
        offset = calculate_offset(page, page_size)

        result = self.ollama_client.search_models(
            query=filters.get('query', ''),
            limit=page_size,
            offset=offset,
            model_type=filters.get('model_type')
        )

        # 标准化结果
        normalized_models = []
        for model in result['models']:
            normalized = normalize_model_info(model)
            normalized_models.append(normalized)

        return paginate_results(
            normalized_models,
            page,
            page_size,
            result.get('total', len(normalized_models))
        )

    def _search_multi_source_models(self, filters: Dict[str, Any],
                                    sort_options: Dict[str, Any],
                                    page: int, page_size: int) -> Dict[str, Any]:
        """多源搜索模型"""
        all_models = []

        # 分配每个来源的查询数量
        per_source_limit = page_size

        try:
            # 搜索HuggingFace
            hf_result = self._search_huggingface_models(filters, sort_options, 1, per_source_limit)
            all_models.extend(hf_result['items'])
        except Exception as e:
            logger.warning(f"HuggingFace search failed: {e}")

        try:
            # 搜索Ollama
            ollama_result = self._search_ollama_models(filters, sort_options, 1, per_source_limit)
            all_models.extend(ollama_result['items'])
        except Exception as e:
            logger.warning(f"Ollama search failed: {e}")

        # 按指定字段排序
        sort_key = sort_options['sort_by']
        reverse = sort_options['order_desc']

        try:
            all_models.sort(
                key=lambda x: x.get(sort_key, 0) if isinstance(x.get(sort_key), (int, float)) else 0,
                reverse=reverse
            )
        except Exception as e:
            logger.warning(f"Sorting failed: {e}")

        # 分页
        return paginate_results(all_models, page, page_size)

    def _get_model_from_db(self, model_id: str, source: Optional[str] = None) -> Optional[Model]:
        """从数据库获取模型"""
        if source:
            return Model.get_by_source_and_id(source, model_id)
        else:
            return Model.query.filter(Model.id == model_id).first()

    def _save_model_to_db(self, model_info: Dict[str, Any]) -> Model:
        """保存模型信息到数据库"""
        try:
            model_id = model_info['id']
            source = model_info['source']

            # 查找现有模型
            existing_model = Model.get_by_source_and_id(source, model_id)

            if existing_model:
                # 更新现有模型
                for key, value in model_info.items():
                    if hasattr(existing_model, key) and value is not None:
                        setattr(existing_model, key, value)
                existing_model.update_sync_time()
                model = existing_model
            else:
                # 创建新模型
                model = Model(
                    id=model_id,
                    name=model_info.get('name', ''),
                    source=source,
                    description=model_info.get('description', ''),
                    model_type=model_info.get('model_type', ''),
                    size_gb=model_info.get('size_gb'),
                    parameters=model_info.get('parameters', ''),
                    tags=model_info.get('tags', []),
                    metadata=model_info.get('metadata', {})
                )
                model.update_sync_time()
                db.session.add(model)

            db.session.commit()
            return model

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save model info: {e}")
            raise

    def _get_or_create_model(self, model_id: str) -> Model:
        """获取或创建模型记录"""
        # 首先尝试从数据库获取
        model = Model.query.filter(Model.id == model_id).first()

        if not model:
            # 从外部源获取信息并创建
            try:
                model_info = self.get_model_info(model_id)
                model = self._save_model_to_db(model_info)
            except:
                # 如果无法获取外部信息，创建基本记录
                model = Model(
                    id=model_id,
                    name=model_id.split('/')[-1] if '/' in model_id else model_id,
                    source='unknown'
                )
                db.session.add(model)
                db.session.commit()

        return model
