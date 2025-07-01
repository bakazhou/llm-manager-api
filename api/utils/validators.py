"""参数验证工具"""
import re
from typing import Dict, Any, Optional

from .exceptions import ValidationError


def validate_search_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """验证搜索参数"""
    validated = {}

    # 查询关键词
    query = params.get('query', '').strip()
    if query and len(query) > 200:
        raise ValidationError("搜索关键词过长，最多200个字符", field='query')
    validated['query'] = query

    # 分页参数
    try:
        page = int(params.get('page', 1))
        if page < 1:
            raise ValidationError("页码必须大于0", field='page')
        validated['page'] = page
    except ValueError:
        raise ValidationError("页码必须是数字", field='page')

    try:
        page_size = int(params.get('page_size', 20))
        if page_size < 1 or page_size > 100:
            raise ValidationError("每页数量必须在1-100之间", field='page_size')
        validated['page_size'] = page_size
    except ValueError:
        raise ValidationError("每页数量必须是数字", field='page_size')

    # 来源过滤
    source = params.get('source', '').strip()
    if source and source not in ['huggingface', 'ollama']:
        raise ValidationError("来源必须是'huggingface'或'ollama'", field='source')
    validated['source'] = source

    # 模型类型过滤
    model_type = params.get('model_type', '').strip()
    if model_type:
        valid_types = [
            'text-generation', 'text-classification', 'text-to-text-generation',
            'question-answering', 'fill-mask', 'token-classification',
            'text-embedding', 'image-classification', 'image-to-text',
            'text-to-image', 'automatic-speech-recognition', 'text-to-speech',
            'conversational', 'code-generation'
        ]
        if model_type not in valid_types:
            raise ValidationError(f"模型类型必须是以下之一: {', '.join(valid_types)}", field='model_type')
    validated['model_type'] = model_type

    # 标签过滤
    tags = params.get('tags', [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
    elif not isinstance(tags, list):
        tags = []

    # 验证标签格式
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise ValidationError("标签必须是非空字符串", field='tags')
        if len(tag) > 50:
            raise ValidationError("标签长度不能超过50个字符", field='tags')

    validated['tags'] = tags

    # 排序参数
    sort_by = params.get('sort_by', 'created_at').strip()
    valid_sort_fields = ['created_at', 'updated_at', 'name', 'downloads', 'likes', 'size']
    if sort_by not in valid_sort_fields:
        raise ValidationError(f"排序字段必须是以下之一: {', '.join(valid_sort_fields)}", field='sort_by')
    validated['sort_by'] = sort_by

    # 排序方向
    sort_order = params.get('sort_order', 'desc').strip().lower()
    if sort_order not in ['asc', 'desc']:
        raise ValidationError("排序方向必须是'asc'或'desc'", field='sort_order')
    validated['sort_order'] = sort_order

    # 是否仅显示推荐模型
    is_featured = params.get('is_featured')
    if is_featured is not None:
        if isinstance(is_featured, str):
            is_featured = is_featured.lower() in ['true', '1', 'yes']
        else:
            is_featured = bool(is_featured)
    validated['is_featured'] = is_featured

    return validated


def validate_model_id(model_id: str, source: Optional[str] = None) -> str:
    """验证模型ID格式"""
    if not model_id or not isinstance(model_id, str):
        raise ValidationError("模型ID不能为空", field='model_id')

    model_id = model_id.strip()
    if not model_id:
        raise ValidationError("模型ID不能为空", field='model_id')

    if len(model_id) > 200:
        raise ValidationError("模型ID过长，最多200个字符", field='model_id')

    # 根据来源验证格式
    if source == 'huggingface':
        # HuggingFace格式: username/model-name
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]+)?/[a-zA-Z0-9]([a-zA-Z0-9\-_.]+)?$'
        if not re.match(pattern, model_id):
            raise ValidationError("HuggingFace模型ID格式不正确，应为'username/model-name'", field='model_id')
    elif source == 'ollama':
        # Ollama格式: model-name 或 model-name:tag
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-_]+)?(:[\w\-_.]+)?$'
        if not re.match(pattern, model_id):
            raise ValidationError("Ollama模型ID格式不正确，应为'model-name'或'model-name:tag'", field='model_id')

    return model_id


def validate_pagination_params(page: Any, page_size: Any) -> tuple[int, int]:
    """验证分页参数"""
    try:
        page = int(page) if page is not None else 1
        if page < 1:
            raise ValidationError("页码必须大于0", field='page')
    except (ValueError, TypeError):
        raise ValidationError("页码必须是数字", field='page')

    try:
        page_size = int(page_size) if page_size is not None else 20
        if page_size < 1 or page_size > 100:
            raise ValidationError("每页数量必须在1-100之间", field='page_size')
    except (ValueError, TypeError):
        raise ValidationError("每页数量必须是数字", field='page_size')

    return page, page_size


def validate_favorite_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """验证收藏参数"""
    validated = {}

    # 模型ID
    model_id = params.get('model_id', '').strip()
    if not model_id:
        raise ValidationError("模型ID不能为空", field='model_id')
    validated['model_id'] = model_id

    # 用户ID（如果有用户系统）
    user_id = params.get('user_id')
    if user_id:
        validated['user_id'] = str(user_id)

    return validated


def validate_json_field(data: Any, field_name: str, required: bool = False) -> Any:
    """验证JSON字段"""
    if data is None:
        if required:
            raise ValidationError(f"{field_name}不能为空", field=field_name)
        return None

    if not isinstance(data, (dict, list)):
        raise ValidationError(f"{field_name}必须是有效的JSON格式", field=field_name)

    return data


def validate_string_field(value: Any, field_name: str, required: bool = False,
                          min_length: int = 0, max_length: int = None) -> Optional[str]:
    """验证字符串字段"""
    if value is None or value == '':
        if required:
            raise ValidationError(f"{field_name}不能为空", field=field_name)
        return None

    if not isinstance(value, str):
        raise ValidationError(f"{field_name}必须是字符串", field=field_name)

    value = value.strip()

    if len(value) < min_length:
        raise ValidationError(f"{field_name}长度不能少于{min_length}个字符", field=field_name)

    if max_length and len(value) > max_length:
        raise ValidationError(f"{field_name}长度不能超过{max_length}个字符", field=field_name)

    return value


def validate_integer_field(value: Any, field_name: str, required: bool = False,
                           min_value: int = None, max_value: int = None) -> Optional[int]:
    """验证整数字段"""
    if value is None:
        if required:
            raise ValidationError(f"{field_name}不能为空", field=field_name)
        return None

    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name}必须是整数", field=field_name)

    if min_value is not None and value < min_value:
        raise ValidationError(f"{field_name}不能小于{min_value}", field=field_name)

    if max_value is not None and value > max_value:
        raise ValidationError(f"{field_name}不能大于{max_value}", field=field_name)

    return value


def validate_json(request, required_fields=None):
    """验证JSON请求数据"""
    if not request.is_json:
        raise ValidationError("请求必须是JSON格式")

    data = request.get_json()
    if data is None:
        raise ValidationError("无效的JSON数据")

    if required_fields:
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"缺少必需字段: {field}", field=field)

    return data


def validate_params(params, schema):
    """验证参数"""
    validated = {}

    for field, rules in schema.items():
        value = params.get(field)

        # 检查必需字段
        if rules.get('required', False) and value is None:
            raise ValidationError(f"缺少必需字段: {field}", field=field)

        # 如果值为空且不是必需字段，跳过验证
        if value is None:
            validated[field] = None
            continue

        # 类型验证
        field_type = rules.get('type')
        if field_type == 'string':
            validated[field] = validate_string_field(
                value, field,
                required=rules.get('required', False),
                min_length=rules.get('min_length', 0),
                max_length=rules.get('max_length')
            )
        elif field_type == 'integer':
            validated[field] = validate_integer_field(
                value, field,
                required=rules.get('required', False),
                min_value=rules.get('min_value'),
                max_value=rules.get('max_value')
            )
        else:
            validated[field] = value

    return validated


def validate_email(email: str) -> str:
    """验证邮箱格式"""
    if not email:
        raise ValidationError("邮箱不能为空", field='email')

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("邮箱格式不正确", field='email')

    return email.lower().strip()
