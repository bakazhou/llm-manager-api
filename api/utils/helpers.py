"""辅助工具函数"""
import math
from datetime import datetime
from typing import Any, Dict, List


def format_response(data: Any, message: str = "操作成功", code: int = 200) -> Dict[str, Any]:
    """格式化成功响应"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "code": code,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def format_error_response(message: str, error_code: str = "ERROR",
                          details: Any = None, status_code: int = 500) -> Dict[str, Any]:
    """格式化错误响应"""
    response = {
        "success": False,
        "message": message,
        "error": error_code,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if details:
        response["details"] = details

    return response


def paginate_results(items: List[Any], page: int, page_size: int, total: int = None) -> Dict[str, Any]:
    """分页结果"""
    if total is None:
        total = len(items)

    # 计算分页信息
    total_pages = math.ceil(total / page_size) if page_size > 0 else 1
    has_next = page < total_pages
    has_prev = page > 1

    # 计算偏移量
    offset = (page - 1) * page_size

    # 获取当前页数据
    if isinstance(items, list):
        page_items = items[offset:offset + page_size]
    else:
        page_items = items

    return {
        "items": page_items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev,
            "offset": offset
        }
    }


def convert_size_bytes(size_bytes: int) -> Dict[str, Any]:
    """转换字节大小为可读格式"""
    if size_bytes == 0:
        return {"bytes": 0, "readable": "0 B", "unit": "B"}

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    # 格式化数字
    if size >= 100:
        readable = f"{size:.0f} {units[unit_index]}"
    elif size >= 10:
        readable = f"{size:.1f} {units[unit_index]}"
    else:
        readable = f"{size:.2f} {units[unit_index]}"

    return {
        "bytes": size_bytes,
        "readable": readable,
        "unit": units[unit_index],
        "value": round(size, 2)
    }


def merge_model_info(base_info: Dict[str, Any], additional_info: Dict[str, Any]) -> Dict[str, Any]:
    """合并模型信息"""
    merged = base_info.copy()

    # 更新基本字段
    for key, value in additional_info.items():
        if value is not None:
            merged[key] = value

    # 合并标签
    base_tags = merged.get('tags', [])
    additional_tags = additional_info.get('tags', [])
    if additional_tags:
        # 去重合并
        all_tags = base_tags + additional_tags
        merged['tags'] = list(dict.fromkeys(all_tags))  # 保持顺序去重

    # 合并元数据
    base_metadata = merged.get('metadata', {})
    additional_metadata = additional_info.get('metadata', {})
    if additional_metadata:
        base_metadata.update(additional_metadata)
        merged['metadata'] = base_metadata

    return merged


def normalize_model_info(model_info: Dict[str, Any]) -> Dict[str, Any]:
    """标准化模型信息"""
    normalized = {}

    # 必需字段
    normalized['id'] = model_info.get('id', '')
    normalized['name'] = model_info.get('name', '')
    normalized['source'] = model_info.get('source', '')

    # 可选字段
    normalized['description'] = model_info.get('description', '')
    normalized['model_type'] = model_info.get('model_type', 'unknown')
    normalized['parameters'] = model_info.get('parameters', '')
    normalized['tags'] = model_info.get('tags', [])
    normalized['metadata'] = model_info.get('metadata', {})

    # 大小信息
    size_bytes = model_info.get('size_bytes')
    if size_bytes:
        normalized['size_bytes'] = size_bytes
        normalized['size_gb'] = round(size_bytes / (1024 ** 3), 2)
        normalized['size_info'] = convert_size_bytes(size_bytes)

    # 统计信息
    normalized['downloads'] = model_info.get('downloads', 0)
    normalized['likes'] = model_info.get('likes', 0)
    normalized['views'] = model_info.get('views', 0)

    # 时间信息
    normalized['created_at'] = model_info.get('created_at')
    normalized['updated_at'] = model_info.get('updated_at')

    # 状态信息
    normalized['status'] = model_info.get('status', 'active')
    normalized['is_featured'] = model_info.get('is_featured', False)
    normalized['is_local'] = model_info.get('is_local', False)

    return normalized


def extract_model_stats(models: List[Dict[str, Any]]) -> Dict[str, Any]:
    """提取模型统计信息"""
    if not models:
        return {
            "total_models": 0,
            "by_source": {},
            "by_type": {},
            "total_downloads": 0,
            "total_likes": 0,
            "average_size_gb": 0
        }

    stats = {
        "total_models": len(models),
        "by_source": {},
        "by_type": {},
        "total_downloads": 0,
        "total_likes": 0,
        "total_size_gb": 0,
        "models_with_size": 0
    }

    for model in models:
        # 按来源统计
        source = model.get('source', 'unknown')
        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

        # 按类型统计
        model_type = model.get('model_type', 'unknown')
        stats["by_type"][model_type] = stats["by_type"].get(model_type, 0) + 1

        # 下载和点赞统计
        stats["total_downloads"] += model.get('downloads', 0)
        stats["total_likes"] += model.get('likes', 0)

        # 大小统计
        size_gb = model.get('size_gb')
        if size_gb:
            stats["total_size_gb"] += size_gb
            stats["models_with_size"] += 1

    # 计算平均大小
    if stats["models_with_size"] > 0:
        stats["average_size_gb"] = round(stats["total_size_gb"] / stats["models_with_size"], 2)
    else:
        stats["average_size_gb"] = 0

    return stats


def build_search_filters(params: Dict[str, Any]) -> Dict[str, Any]:
    """构建搜索过滤器"""
    filters = {}

    # 文本搜索 - 支持'q'和'query'两种参数名
    query = params.get('q', params.get('query', '')).strip()
    if query:
        filters['query'] = query

    # 来源过滤
    source = params.get('source', '').strip()
    if source:
        filters['source'] = source

    # 模型类型过滤
    model_type = params.get('model_type', '').strip()
    if model_type:
        filters['model_type'] = model_type

    # 标签过滤
    tags = params.get('tags', [])
    if tags:
        filters['tags'] = tags

    # 推荐过滤
    is_featured = params.get('is_featured')
    if is_featured is not None:
        filters['is_featured'] = is_featured

    # 状态过滤
    status = params.get('status', 'active')
    filters['status'] = status

    return filters


def build_sort_options(params: Dict[str, Any]) -> Dict[str, Any]:
    """构建排序选项"""
    sort_by = params.get('sort_by', 'downloads')  # 默认按下载量排序
    sort_order = params.get('sort_order', 'desc')

    # 映射到HuggingFace API支持的排序字段
    sort_field_mapping = {
        'created_at': 'lastModified',
        'updated_at': 'lastModified',
        'downloads': 'downloads',
        'likes': 'likes',
        'last_modified': 'lastModified'
    }

    # 如果sort_by不在映射中，默认使用downloads
    mapped_sort_by = sort_field_mapping.get(sort_by, 'downloads')

    return {
        'sort_by': mapped_sort_by,
        'sort_order': sort_order,
        'order_desc': sort_order.lower() == 'desc'
    }


def calculate_offset(page: int, page_size: int) -> int:
    """计算偏移量"""
    return (page - 1) * page_size


def success_response(data: Any = None, message: str = "操作成功", code: int = 200) -> Dict[str, Any]:
    """成功响应"""
    return format_response(data, message, code)


def error_response(message: str, code: str = "ERROR", details: Any = None) -> Dict[str, Any]:
    """错误响应"""
    return format_error_response(message, code, details)
