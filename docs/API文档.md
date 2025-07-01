# LLM Manager API 文档

## 项目概述

LLM Manager API 是一个大语言模型管理服务，提供模型搜索、下载、部署和推理等功能。支持 HuggingFace 和 Ollama 两种模型源，集成 vLLM 高性能推理引擎。

## 基础信息

- **基础URL**: `http://localhost:5000`
- **API版本**: v1
- **响应格式**: JSON
- **认证方式**: 暂无（开发阶段）

## 响应格式

### 成功响应
```json
{
  "success": true,
  "message": "操作成功",
  "data": {...},
  "code": 200,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 错误响应
```json
{
  "success": false,
  "message": "错误信息",
  "error": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 功能模块

### 1. 系统管理

#### 1.1 服务健康检查
- **功能描述**: 检查服务运行状态
- **端点**: `GET /health`
- **请求体**: 无
- **响应示例**:
```json
{
  "status": "healthy",
  "service": "llm-manager-api",
  "version": "1.0.0"
}
```

#### 1.2 API健康检查
- **功能描述**: 检查API服务状态
- **端点**: `GET /api/health`
- **请求体**: 无
- **响应示例**:
```json
{
  "status": "healthy",
  "api_version": "v1",
  "service": "llm-manager-api"
}
```

#### 1.3 系统资源监控
- **功能描述**: 获取系统资源使用情况
- **端点**: `GET /api/system/resources`
- **请求体**: 无
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "cpu": {
      "usage_percent": 25.5,
      "cores": 8
    },
    "memory": {
      "total_gb": 16.0,
      "used_gb": 8.5,
      "available_gb": 7.5,
      "usage_percent": 53.1
    },
    "disk": {
      "total_gb": 500.0,
      "used_gb": 250.0,
      "free_gb": 250.0,
      "usage_percent": 50.0
    }
  }
}
```

#### 1.4 系统负载监控
- **功能描述**: 获取系统负载信息
- **端点**: `GET /api/system/load`
- **请求体**: 无

#### 1.5 系统健康检查
- **功能描述**: 综合系统健康状态检查
- **端点**: `GET /api/system/health`
- **请求体**: 无

### 2. 模型管理

#### 2.1 模型搜索
- **功能描述**: 搜索可用的模型
- **端点**: `GET /api/models/search`
- **查询参数**:
  - `query`: 搜索关键词
  - `source`: 模型源 (huggingface/ollama)
  - `model_type`: 模型类型
  - `page`: 页码 (默认1)
  - `page_size`: 每页数量 (默认20)
- **请求体**: 无
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "microsoft/DialoGPT-medium",
        "name": "DialoGPT Medium",
        "description": "对话生成模型",
        "model_type": "conversational",
        "source": "huggingface",
        "parameters": "117M",
        "downloads": 50000,
        "likes": 1200,
        "tags": ["conversational", "pytorch"]
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

#### 2.2 获取模型信息
- **功能描述**: 获取指定模型的详细信息
- **端点**: `GET /api/models/{model_id}/info`
- **路径参数**:
  - `model_id`: 模型ID
- **请求体**: 无
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "microsoft/DialoGPT-medium",
    "name": "DialoGPT Medium",
    "description": "对话生成模型",
    "model_type": "conversational",
    "source": "huggingface",
    "parameters": "117M",
    "size_gb": 0.5,
    "downloads": 50000,
    "likes": 1200,
    "tags": ["conversational", "pytorch"],
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-12-01T00:00:00Z"
  }
}
```

#### 2.3 获取模型分类
- **功能描述**: 获取可用的模型分类列表
- **端点**: `GET /api/models/categories`
- **查询参数**:
  - `source`: 模型源 (可选)
- **请求体**: 无

#### 2.4 获取热门模型
- **功能描述**: 获取热门模型列表
- **端点**: `GET /api/models/trending`
- **查询参数**:
  - `limit`: 返回数量 (默认10, 最大50)
  - `source`: 模型源 (可选)
- **请求体**: 无

#### 2.5 获取模型统计
- **功能描述**: 获取模型统计信息
- **端点**: `GET /api/models/stats`
- **请求体**: 无

#### 2.6 收藏模型
- **功能描述**: 收藏指定模型
- **端点**: `POST /api/models/{model_id}/favorite`
- **路径参数**:
  - `model_id`: 模型ID
- **请求体**: 无

#### 2.7 取消收藏模型
- **功能描述**: 取消收藏指定模型
- **端点**: `DELETE /api/models/{model_id}/favorite`
- **路径参数**:
  - `model_id`: 模型ID
- **请求体**: 无

#### 2.8 同步模型数据
- **功能描述**: 同步远程模型数据到本地
- **端点**: `POST /api/models/sync`
- **请求体**: 无

### 3. 下载管理

#### 3.1 开始下载
- **功能描述**: 创建并开始模型下载任务
- **端点**: `POST /api/downloads/start`
- **请求体**:
```json
{
  "model_id": "microsoft/DialoGPT-medium",
  "source": "huggingface"
}
```
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_123",
      "model_id": "microsoft/DialoGPT-medium",
      "source": "huggingface",
      "status": "pending",
      "progress": 0,
      "created_at": "2024-01-01T00:00:00Z"
    },
    "message": "下载任务已创建"
  }
}
```

#### 3.2 暂停下载
- **功能描述**: 暂停指定的下载任务
- **端点**: `PUT /api/downloads/{task_id}/pause`
- **路径参数**:
  - `task_id`: 任务ID
- **请求体**: 无

#### 3.3 继续下载
- **功能描述**: 继续暂停的下载任务
- **端点**: `PUT /api/downloads/{task_id}/resume`
- **路径参数**:
  - `task_id`: 任务ID
- **请求体**: 无

#### 3.4 取消下载
- **功能描述**: 取消指定的下载任务
- **端点**: `PUT /api/downloads/{task_id}/cancel`
- **路径参数**:
  - `task_id`: 任务ID
- **请求体**: 无

#### 3.5 获取下载状态
- **功能描述**: 获取指定下载任务的状态
- **端点**: `GET /api/downloads/{task_id}`
- **路径参数**:
  - `task_id`: 任务ID
- **请求体**: 无
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "task_123",
    "model_id": "microsoft/DialoGPT-medium",
    "source": "huggingface",
    "status": "downloading",
    "progress": 45.5,
    "downloaded_size": "500MB",
    "total_size": "1.1GB",
    "speed": "10MB/s",
    "eta": "00:01:00",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z"
  }
}
```

#### 3.6 删除下载任务
- **功能描述**: 删除指定的下载任务记录
- **端点**: `DELETE /api/downloads/{task_id}`
- **路径参数**:
  - `task_id`: 任务ID
- **请求体**: 无

#### 3.7 获取下载列表
- **功能描述**: 获取下载任务列表
- **端点**: `GET /api/downloads/list`
- **查询参数**:
  - `status`: 任务状态过滤 (可选)
  - `page`: 页码 (默认1)
  - `page_size`: 每页数量 (默认20, 最大100)
- **请求体**: 无

#### 3.8 获取下载队列状态
- **功能描述**: 获取当前下载队列的状态信息
- **端点**: `GET /api/downloads/queue`
- **请求体**: 无

#### 3.9 获取存储空间信息
- **功能描述**: 获取存储空间使用情况
- **端点**: `GET /api/downloads/storage`
- **请求体**: 无

### 4. 部署管理

#### 4.1 启动部署
- **功能描述**: 启动模型部署服务
- **端点**: `POST /api/deployments/start`
- **请求体**:
```json
{
  "model_id": "microsoft/DialoGPT-medium",
  "model_source": "huggingface",
  "port": 8000,
  "gpu_memory_utilization": 0.8,
  "max_model_len": 2048
}
```
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "deployment_id": "deploy_123",
    "model_id": "microsoft/DialoGPT-medium",
    "status": "starting",
    "host": "localhost",
    "port": 8000,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### 4.2 停止部署
- **功能描述**: 停止指定的部署服务
- **端点**: `PUT /api/deployments/{deployment_id}/stop`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**: 无

#### 4.3 重启部署
- **功能描述**: 重启指定的部署服务
- **端点**: `PUT /api/deployments/{deployment_id}/restart`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**: 无

#### 4.4 获取部署状态
- **功能描述**: 获取指定部署的状态信息
- **端点**: `GET /api/deployments/{deployment_id}`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**: 无
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "deployment_id": "deploy_123",
    "model_id": "microsoft/DialoGPT-medium",
    "model_source": "huggingface",
    "status": "running",
    "host": "localhost",
    "port": 8000,
    "gpu_memory_utilization": 0.8,
    "max_model_len": 2048,
    "created_at": "2024-01-01T00:00:00Z",
    "started_at": "2024-01-01T00:01:00Z"
  }
}
```

#### 4.5 删除部署
- **功能描述**: 删除指定的部署记录
- **端点**: `DELETE /api/deployments/{deployment_id}`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**: 无

#### 4.6 获取部署列表
- **功能描述**: 获取所有部署的列表
- **端点**: `GET /api/deployments/list`
- **查询参数**:
  - `status`: 状态过滤 (可选)
- **请求体**: 无

#### 4.7 获取部署日志
- **功能描述**: 获取指定部署的日志信息
- **端点**: `GET /api/deployments/{deployment_id}/logs`
- **路径参数**:
  - `deployment_id`: 部署ID
- **查询参数**:
  - `lines`: 日志行数 (默认100)
- **请求体**: 无

#### 4.8 部署健康检查
- **功能描述**: 检查指定部署的健康状态
- **端点**: `GET /api/deployments/{deployment_id}/health`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**: 无

### 5. 聊天和推理

#### 5.1 聊天对话
- **功能描述**: 与部署的模型进行聊天对话
- **端点**: `POST /api/chat/{deployment_id}`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**:
```json
{
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1000,
  "top_p": 0.9
}
```
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1704067200,
    "model": "microsoft/DialoGPT-medium",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "Hello! How can I help you today?"
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 15,
      "total_tokens": 25
    }
  }
}
```

#### 5.2 文本补全
- **功能描述**: 基于提示进行文本补全
- **端点**: `POST /api/completions/{deployment_id}`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**:
```json
{
  "prompt": "Once upon a time",
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 100,
  "top_p": 0.9
}
```
- **响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "cmpl-123",
    "object": "text_completion",
    "created": 1704067200,
    "model": "microsoft/DialoGPT-medium",
    "choices": [
      {
        "text": ", there was a brave knight who...",
        "index": 0,
        "finish_reason": "length"
      }
    ],
    "usage": {
      "prompt_tokens": 4,
      "completion_tokens": 100,
      "total_tokens": 104
    }
  }
}
```

#### 5.3 获取部署模型信息
- **功能描述**: 获取部署中模型的详细信息
- **端点**: `GET /api/deployments/{deployment_id}/model-info`
- **路径参数**:
  - `deployment_id`: 部署ID
- **请求体**: 无

## 状态码说明

- `pending`: 等待中
- `downloading`: 下载中
- `paused`: 已暂停
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消
- `starting`: 启动中
- `running`: 运行中
- `stopping`: 停止中
- `stopped`: 已停止
- `error`: 错误

## WebSocket 支持

系统支持 WebSocket 实时通信，用于下载进度推送等功能。WebSocket 端点：
- 下载进度推送: `ws://localhost:5000/ws/downloads`

## 错误代码

常见错误代码说明：
- `INVALID_SOURCE`: 不支持的模型源
- `INVALID_ACTION`: 不支持的操作
- `DEPLOYMENT_NOT_RUNNING`: 部署未运行
- `CHAT_NOT_SUPPORTED`: 不支持聊天功能
- `MODEL_NOT_FOUND`: 模型未找到
- `TASK_NOT_FOUND`: 任务未找到
- `DEPLOYMENT_NOT_FOUND`: 部署未找到
