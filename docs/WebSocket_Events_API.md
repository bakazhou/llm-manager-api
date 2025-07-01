# WebSocket Events API 文档

## 概述

LLM Manager API 提供了基于 WebSocket 的实时监控系统，支持分域事件推送。客户端可以选择性订阅不同类型的事件，获取系统资源、模型状态、活动流、系统告警和部署事件的实时更新。

## 连接信息

- **WebSocket 端点**: `ws://localhost:5000/socket.io/`
- **协议**: Socket.IO v4+
- **传输方式**: WebSocket, Polling (fallback)

## 事件类型

### 1. 系统资源监控 (System Resources)

**订阅事件**: `subscribe_system_resources`
**推送事件**: `system_resources_update`
**推送频率**: 每 2 秒

#### 数据结构
```json
{
  "event_type": "system_resources_update",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "data": {
    "cpu": {
      "usage_percent": 45.2,
      "cores": 8,
      "frequency": 3200,
      "status": "normal"
    },
    "memory": {
      "usage_percent": 67.8,
      "total_gb": 16.0,
      "available_gb": 5.2,
      "status": "normal"
    },
    "disk": {
      "usage_percent": 78.5,
      "total_gb": 500.0,
      "free_gb": 107.5,
      "status": "warning"
    },
    "gpu": {
      "available": true,
      "device_count": 1,
      "devices": [
        {
          "id": 0,
          "name": "NVIDIA RTX 4090",
          "usage_percent": 23.4,
          "memory_usage_percent": 15.6,
          "temperature": 45,
          "status": "normal"
        }
      ]
    },
    "network": {
      "bytes_sent": 1024000,
      "bytes_recv": 2048000,
      "packets_sent": 1500,
      "packets_recv": 2000
    }
  }
}
```

#### 状态值说明
- `normal`: 正常 (< 70%)
- `high`: 较高 (70-79%)
- `warning`: 警告 (80-89%)
- `critical`: 危险 (≥ 90%)

### 2. 模型状态监控 (Model Status)

**订阅事件**: `subscribe_model_status`
**推送事件**: `model_status_update`
**推送频率**: 每 5 秒

#### 数据结构
```json
{
  "event_type": "model_status_update",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "data": {
    "total_models": 3,
    "running_models": 2,
    "failed_models": 0,
    "models": [
      {
        "deployment_id": "dep-123",
        "model_id": "llama2-7b",
        "name": "LLaMA2 Chat",
        "status": "running",
        "health_status": "healthy",
        "uptime_seconds": 3600,
        "port": 8000,
        "host": "localhost",
        "model_source": "huggingface",
        "cpu_cores": 4,
        "memory_limit": "8GB",
        "created_at": "2025-01-01T11:00:00.000Z",
        "deployed_at": "2025-01-01T11:00:30.000Z"
      }
    ]
  }
}
```

#### 模型状态值
- `pending`: 等待部署
- `deploying`: 部署中
- `running`: 运行中
- `stopped`: 已停止
- `failed`: 部署失败

#### 健康状态值
- `healthy`: 健康
- `unhealthy`: 不健康
- `unknown`: 未知

### 3. 活动流 (Activity Stream)

**订阅事件**: `subscribe_activity_stream`
**推送事件**: `activity_stream`
**推送频率**: 实时 (有新活动时立即推送)

#### 数据结构
```json
{
  "event_type": "activity_stream",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "data": {
    "id": "act-456",
    "activity_type": "model_deployment",
    "message": "Model LLaMA2-7B deployment started",
    "severity": "info",
    "resource_type": "deployment",
    "resource_id": "dep-123",
    "created_at": "2025-01-01T12:00:00.000Z",
    "extra_data": {
      "model_id": "llama2-7b",
      "port": 8000
    }
  }
}
```

#### 活动类型
- `model_deployment`: 模型部署
- `model_health_check`: 模型健康检查
- `system_resource_threshold`: 系统资源阈值
- `download_task`: 下载任务
- `user_operation`: 用户操作

#### 严重程度
- `info`: 信息
- `warning`: 警告
- `error`: 错误
- `critical`: 严重

### 4. 系统告警 (System Alerts)

**订阅事件**: `subscribe_system_alerts`
**推送事件**: `system_alerts`
**推送频率**: 实时 (检测到告警时立即推送)

#### 数据结构
```json
{
  "event_type": "system_alerts",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "data": {
    "alert_id": "alert_1640995200",
    "type": "resource_threshold",
    "severity": "warning",
    "title": "High Memory Usage",
    "message": "Memory usage reached 85.2%",
    "resource": {
      "type": "memory",
      "current_value": 85.2,
      "threshold": 80.0,
      "unit": "%"
    },
    "actions": ["check_processes", "restart_services"],
    "auto_resolve": false
  }
}
```

#### 告警类型
- `memory_threshold`: 内存使用率告警
- `disk_threshold`: 磁盘使用率告警
- `gpu_threshold`: GPU使用率告警
- `model_health_check_failed`: 模型健康检查失败

#### 建议操作
- `check_processes`: 检查进程
- `restart_services`: 重启服务
- `cleanup_temp_files`: 清理临时文件
- `archive_logs`: 归档日志
- `restart_model`: 重启模型
- `check_logs`: 检查日志
- `check_gpu_processes`: 检查GPU进程

### 5. 部署事件 (Deployment Events)

**订阅事件**: `subscribe_deployment_events`
**推送事件**: `deployment_events`
**推送频率**: 实时 (部署状态变化时立即推送)

#### 数据结构
```json
{
  "event_type": "deployment_events",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "data": {
    "deployment_id": "dep-123",
    "model_id": "llama2-7b",
    "event": "deployment_started",
    "status": "deploying",
    "message": "Starting deployment for llama2-7b",
    "details": {
      "name": "LLaMA2 Chat",
      "model_source": "huggingface",
      "port": 8000,
      "container_id": "container-abc",
      "estimated_completion": "2025-01-01T12:05:00.000Z"
    }
  }
}
```

#### 部署事件类型
- `deployment_started`: 部署开始
- `deployment_completed`: 部署完成
- `deployment_failed`: 部署失败
- `deployment_stopped`: 部署停止
- `deployment_restarted`: 部署重启

## 订阅管理

### 单独订阅
```javascript
// 订阅系统资源
socket.emit('subscribe_system_resources');

// 订阅模型状态
socket.emit('subscribe_model_status');

// 订阅活动流
socket.emit('subscribe_activity_stream');

// 订阅系统告警
socket.emit('subscribe_system_alerts');

// 订阅部署事件
socket.emit('subscribe_deployment_events');
```

### 批量订阅
```javascript
// 订阅所有事件
socket.emit('subscribe_all');
```

### 取消订阅
```javascript
// 取消单个订阅
socket.emit('unsubscribe_system_resources');
socket.emit('unsubscribe_model_status');
socket.emit('unsubscribe_activity_stream');
socket.emit('unsubscribe_system_alerts');
socket.emit('unsubscribe_deployment_events');

// 取消所有订阅
socket.emit('unsubscribe_all');
```

### 订阅确认
所有订阅请求都会收到确认响应：

```json
{
  "event_type": "system_resources",
  "message": "System resources subscription successful",
  "session_id": "client_1640995200"
}
```

## 向后兼容性

为了保持向后兼容性，系统仍然支持原有的监控接口：

### 传统订阅方式
```javascript
// 等同于 subscribe_all
socket.emit('subscribe_system_monitor');

// 等同于 unsubscribe_all
socket.emit('unsubscribe_system_monitor');
```

## 客户端示例

### JavaScript (Socket.IO)
```javascript
const io = require('socket.io-client');
const socket = io('http://localhost:5000');

// 连接事件
socket.on('connect', () => {
    console.log('Connected to server');
    
    // 订阅系统资源
    socket.emit('subscribe_system_resources');
});

// 监听系统资源更新
socket.on('system_resources_update', (data) => {
    console.log('System Resources:', data.data);
});

// 监听系统告警
socket.on('system_alerts', (data) => {
    console.log('Alert:', data.data.title, data.data.message);
});

// 订阅确认
socket.on('subscribed', (data) => {
    console.log('Subscription confirmed:', data);
});

// 断开连接
socket.on('disconnect', () => {
    console.log('Disconnected from server');
});
```

### Python (python-socketio)
```python
import socketio

sio = socketio.Client()

@sio.event
def connect():
    print('Connected to server')
    sio.emit('subscribe_system_resources')

@sio.event
def system_resources_update(data):
    print('System Resources:', data['data'])

@sio.event
def system_alerts(data):
    alert = data['data']
    print(f"Alert: {alert['title']} - {alert['message']}")

@sio.event
def subscribed(data):
    print('Subscription confirmed:', data)

# 连接到服务器
sio.connect('http://localhost:5000')
sio.wait()
```

## 错误处理

### 连接错误
- 检查服务器是否运行
- 确认端口和地址正确
- 检查网络连接

### 订阅失败
- 确认事件名称正确
- 检查服务器日志
- 重新连接后重试

### 数据丢失
- 客户端应实现重连机制
- 使用心跳检测保持连接
- 缓存重要数据

## 性能优化建议

1. **选择性订阅**: 只订阅需要的事件类型
2. **批处理**: 在短时间内批量处理事件
3. **缓存**: 客户端缓存最新状态
4. **压缩**: 启用 WebSocket 压缩
5. **心跳**: 设置合适的心跳间隔

## 安全考虑

1. **认证**: 生产环境应添加身份认证
2. **授权**: 限制客户端访问权限
3. **速率限制**: 防止客户端滥用
4. **数据验证**: 验证客户端发送的数据
5. **HTTPS**: 生产环境使用 WSS (WebSocket Secure)

## 更新日志

### v2.0.0 (2025-01-01)
- 新增分域事件系统
- 支持选择性订阅
- 优化数据结构
- 保持向后兼容性

### v1.0.0 (2024-12-01)
- 基础监控系统
- 统一事件推送 