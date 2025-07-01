"""自定义异常类"""


class APIError(Exception):
    """API基础异常类"""

    def __init__(self, message: str, code: str = None, status_code: int = 500):
        self.message = message
        self.code = code or 'INTERNAL_ERROR'
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(APIError):
    """参数验证错误"""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, code='VALIDATION_ERROR', status_code=400)


class ExternalServiceError(APIError):
    """外部服务错误"""

    def __init__(self, message: str, service: str = None):
        self.service = service
        super().__init__(message, code='EXTERNAL_SERVICE_ERROR', status_code=503)


class ModelNotFoundError(APIError):
    """模型未找到错误"""

    def __init__(self, message: str, model_id: str = None):
        self.model_id = model_id
        super().__init__(message, code='MODEL_NOT_FOUND', status_code=404)


class AuthenticationError(APIError):
    """认证错误"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(message, code='AUTHENTICATION_ERROR', status_code=401)


class AuthorizationError(APIError):
    """授权错误"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(message, code='AUTHORIZATION_ERROR', status_code=403)


class ResourceNotFoundError(APIError):
    """资源未找到错误"""

    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(message, code='RESOURCE_NOT_FOUND', status_code=404)


class ConflictError(APIError):
    """冲突错误"""

    def __init__(self, message: str):
        super().__init__(message, code='CONFLICT_ERROR', status_code=409)


class RateLimitError(APIError):
    """请求频率限制错误"""

    def __init__(self, message: str = "请求过于频繁"):
        super().__init__(message, code='RATE_LIMIT_ERROR', status_code=429)


class DownloadError(APIError):
    """下载错误"""

    def __init__(self, message: str):
        super().__init__(message, code='DOWNLOAD_ERROR', status_code=500)


class StorageError(APIError):
    """存储错误"""

    def __init__(self, message: str):
        super().__init__(message, code='STORAGE_ERROR', status_code=507)


class NotFoundError(APIError):
    """通用未找到错误"""

    def __init__(self, message: str):
        super().__init__(message, code='NOT_FOUND', status_code=404)
