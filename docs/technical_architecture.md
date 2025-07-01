# LLM管理服务 - 技术架构设计

## 系统架构概述

LLM管理服务采用分层架构设计，包括API层、业务逻辑层、数据访问层和外部服务集成层。

## 技术选型

### 核心框架

```
Flask              # Web框架
Flask-RESTful      # RESTful API框架
Flask-SQLAlchemy   # ORM框架
Flask-CORS         # 跨域支持
```

### 数据存储

```
SQLAlchemy         # 关系型数据库ORM
Redis              # 缓存和消息队列
SQLite/PostgreSQL # 主数据库
```

### 异步任务处理

```
Celery             # 分布式任务队列
Redis              # Celery后端存储
WebSocket          # 实时通信
```

### 模型管理

```
huggingface-hub    # HuggingFace API
ollama             # Ollama API
transformers       # 模型加载
torch              # 深度学习框架
```

### 系统监控

```
psutil             # 系统资源监控
docker             # 容器管理
logging            # 日志记录
```

### 数据验证

```
pydantic           # 数据验证和序列化
marshmallow        # 数据序列化（备选）
```

## 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端/客户端                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     API网关层                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  REST API   │ │  WebSocket  │ │   CORS      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    业务逻辑层                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  模型管理   │ │  下载管理   │ │  部署管理   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  对话管理   │ │  任务调度   │ │  资源监控   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据访问层                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  数据库ORM  │ │  缓存管理   │ │  文件管理   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    存储层                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ PostgreSQL  │ │    Redis    │ │  文件系统   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  外部服务层                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ HuggingFace │ │   Ollama    │ │   Docker    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 数据库设计

### 表结构设计

#### models 表 - 模型信息

```sql
CREATE TABLE models (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    source VARCHAR(50) NOT NULL,  -- huggingface, ollama
    model_type VARCHAR(50),
    size_gb DECIMAL(10,2),
    parameters VARCHAR(50),
    tags JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### download_tasks 表 - 下载任务

```sql
CREATE TABLE download_tasks (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, downloading, paused, completed, failed, cancelled
    progress DECIMAL(5,2) DEFAULT 0,
    download_size BIGINT DEFAULT 0,
    total_size BIGINT,
    download_speed DECIMAL(10,2),
    file_path VARCHAR(500),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(id)
);
```

#### deployments 表 - 部署信息

```sql
CREATE TABLE deployments (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- deploying, running, stopped, failed
    port INTEGER,
    gpu_device VARCHAR(20),
    config JSON,
    container_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(id)
);
```

#### chat_sessions 表 - 对话会话

```sql
CREATE TABLE chat_sessions (
    id VARCHAR(36) PRIMARY KEY,
    deployment_id VARCHAR(36) NOT NULL,
    name VARCHAR(255),
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);
```

#### chat_messages 表 - 对话消息

```sql
CREATE TABLE chat_messages (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- user, assistant
    content TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
```

## 目录结构设计

```
llm-manager-api/
├── api/                          # API应用主目录
│   ├── __init__.py
│   ├── app.py                    # Flask应用入口
│   ├── config.py                 # 配置文件
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   ├── model.py              # 模型信息表
│   │   ├── download_task.py      # 下载任务表
│   │   ├── deployment.py         # 部署信息表
│   │   └── chat.py               # 对话相关表
│   ├── services/                 # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── model_service.py      # 模型管理服务
│   │   ├── download_service.py   # 下载管理服务
│   │   ├── deployment_service.py # 部署管理服务
│   │   ├── chat_service.py       # 对话服务
│   │   └── system_service.py     # 系统监控服务
│   ├── controllers/              # 控制器层
│   │   ├── __init__.py
│   │   ├── model_controller.py
│   │   ├── download_controller.py
│   │   ├── deployment_controller.py
│   │   ├── chat_controller.py
│   │   └── system_controller.py
│   ├── utils/                    # 工具类
│   │   ├── __init__.py
│   │   ├── validators.py         # 数据验证
│   │   ├── helpers.py            # 辅助函数
│   │   └── exceptions.py         # 自定义异常
│   ├── integrations/             # 外部服务集成
│   │   ├── __init__.py
│   │   ├── huggingface_client.py
│   │   ├── ollama_client.py
│   │   └── docker_client.py
│   └── websockets/               # WebSocket处理
│       ├── __init__.py
│       ├── download_ws.py
│       └── chat_ws.py
├── tasks/                        # Celery任务
│   ├── __init__.py
│   ├── download_tasks.py
│   ├── deployment_tasks.py
│   └── cleanup_tasks.py
├── tests/                        # 测试文件
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_services.py
│   └── test_controllers.py
├── migrations/                   # 数据库迁移
├── docs/                         # 文档
├── logs/                         # 日志文件
├── storage/                      # 模型文件存储
│   ├── downloads/               # 下载文件
│   └── models/                  # 模型文件
├── docker/                       # Docker配置
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt              # Python依赖
├── Pipfile                      # Pipenv配置
├── .env.example                 # 环境变量示例
├── .gitignore
└── README.md
```

## API设计规范

### RESTful API设计原则

1. 使用HTTP动词表示操作（GET、POST、PUT、DELETE）
2. 使用名词表示资源
3. 使用HTTP状态码表示结果
4. 统一的响应格式

### 统一响应格式

```json
{
    "success": true,
    "message": "操作成功",
    "data": {},
    "code": 200,
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### 错误响应格式

```json
{
    "success": false,
    "message": "错误描述",
    "error": "ERROR_CODE",
    "details": {},
    "timestamp": "2024-01-01T00:00:00Z"
}
```

## 部署架构

### 开发环境

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - DATABASE_URL=postgresql://user:pass@db:5432/llmdb
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./storage:/app/storage
    depends_on:
      - db
      - redis

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=llmdb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  celery:
    build: .
    command: celery -A tasks.celery worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/llmdb
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./storage:/app/storage
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
```

### 生产环境考虑

1. **负载均衡**: 使用Nginx进行负载均衡
2. **容器编排**: 使用Docker Swarm或Kubernetes
3. **数据备份**: 定期备份数据库和模型文件
4. **监控告警**: 集成Prometheus + Grafana
5. **日志收集**: 使用ELK栈进行日志收集分析

## 安全考虑

### 1. 身份认证

- JWT Token认证
- API Key认证
- 角色权限控制

### 2. 数据安全

- 敏感信息加密存储
- SQL注入防护
- XSS攻击防护

### 3. 文件安全

- 文件类型验证
- 文件大小限制
- 病毒扫描（可选）

### 4. 网络安全

- HTTPS强制
- CORS策略配置
- 请求频率限制

## 性能优化

### 1. 缓存策略

- Redis缓存热点数据
- 模型信息缓存
- API响应缓存

### 2. 数据库优化

- 索引优化
- 查询优化
- 连接池配置

### 3. 异步处理

- 长时间任务异步化
- 消息队列解耦
- 批量处理优化

### 4. 文件优化

- 断点续传
- 并发下载
- 压缩传输 