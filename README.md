# LLM Manager API

一个基于Flask的大语言模型管理服务，支持模型搜索、下载、本地部署和调试等功能。

## 🚀 功能特性

### ✅ 已实现功能

#### 模型搜索与信息管理

- 🔍 **模型搜索**: 支持HuggingFace和Ollama模型搜索
- 📊 **模型信息**: 获取详细的模型信息，包括大小、参数量、标签等
- 🏷️ **分类管理**: 支持模型分类过滤和管理
- ⭐ **热门模型**: 获取热门推荐模型
- 💖 **模型收藏**: 支持模型收藏和取消收藏
- 📈 **统计信息**: 提供模型统计和分析数据
- 🔄 **数据同步**: 支持从外部源同步模型信息

#### 技术特性

- 🌐 **多源集成**: 同时支持HuggingFace Hub和Ollama
- 📦 **RESTful API**: 完整的REST API接口
- 🗄️ **数据缓存**: Redis缓存支持，提高响应速度
- 📝 **完整日志**: 详细的日志记录和错误处理
- 🔒 **参数验证**: 严格的输入参数验证
- 📄 **标准响应**: 统一的API响应格式

### 🚧 待实现功能

- 📥 **模型下载**: 下载管理、暂停、继续、断点续传
- 🚀 **模型部署**: 本地部署、容器化管理
- 💬 **对话调试**: 流式对话、会话管理
- 📊 **系统监控**: 资源监控、性能分析

## 📋 API接口

### 模型管理

- `GET /api/models/search` - 搜索模型
- `GET /api/models/{model_id}/info` - 获取模型详细信息
- `GET /api/models/categories` - 获取模型分类
- `GET /api/models/trending` - 获取热门模型
- `GET /api/models/stats` - 获取模型统计信息
- `POST /api/models/{model_id}/favorite` - 收藏模型
- `DELETE /api/models/{model_id}/favorite` - 取消收藏模型
- `POST /api/models/sync` - 同步模型信息

### 系统接口

- `GET /health` - 健康检查
- `GET /api/health` - API健康检查
- `GET /` - 服务信息和接口列表

## 🛠️ 安装和运行

### 环境要求

- Python 3.9+
- Redis (可选，用于缓存)
- PostgreSQL/SQLite (数据库)

### 安装依赖

```bash
# 使用Pipenv安装（推荐）
pipenv install

# 激活虚拟环境
pipenv shell

# 或使用pip（需要先生成requirements.txt）
pipenv requirements > requirements.txt
pip install -r requirements.txt
```

### 环境配置

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑环境变量
vim .env
```

### 运行应用

```bash
# 使用Pipenv脚本（推荐）
pipenv run start      # 默认环境
pipenv run dev        # 开发环境
pipenv run prod       # 生产环境

# 或直接运行
python run.py development   # 开发环境
python run.py production    # 生产环境
python run.py              # 默认环境
```

## 📝 配置说明

### 环境变量

```bash
# Flask配置
FLASK_ENV=development
SECRET_KEY=your-secret-key

# 数据库
DATABASE_URL=sqlite:///llm_manager.db

# Redis缓存（可选）
REDIS_URL=redis://localhost:6379/0

# HuggingFace配置
HUGGINGFACE_TOKEN=your_token
HUGGINGFACE_CACHE_TTL=3600

# Ollama配置
OLLAMA_BASE_URL=http://localhost:11434

# 服务配置
PORT=5000
```

## 🔍 API使用示例

### 搜索模型

```bash
# 搜索所有模型
curl "http://localhost:5000/api/models/search?q=llama"

# 搜索HuggingFace模型
curl "http://localhost:5000/api/models/search?q=bert&source=huggingface"

# 按类型过滤
curl "http://localhost:5000/api/models/search?model_type=text-generation"
```

### 获取模型信息

```bash
# 获取HuggingFace模型信息
curl "http://localhost:5000/api/models/microsoft%2FDialoGPT-medium/info?source=huggingface"

# 获取Ollama模型信息
curl "http://localhost:5000/api/models/llama2/info?source=ollama"
```

### 获取热门模型

```bash
curl "http://localhost:5000/api/models/trending?limit=10"
```

### 收藏模型

```bash
# 收藏模型
curl -X POST "http://localhost:5000/api/models/microsoft%2FDialoGPT-medium/favorite"

# 取消收藏
curl -X DELETE "http://localhost:5000/api/models/microsoft%2FDialoGPT-medium/favorite"
```

## 📊 响应格式

### 成功响应

```json
{
    "success": true,
    "message": "操作成功",
    "data": {
        // 响应数据
    },
    "code": 200,
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### 错误响应

```json
{
    "success": false,
    "message": "错误描述",
    "error": "ERROR_CODE",
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### 分页响应

```json
{
    "items": [...],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 100,
        "total_pages": 5,
        "has_next": true,
        "has_prev": false
    }
}
```

## 🏗️ 项目结构

```
llm-manager-api/
├── api/                          # API应用主目录
│   ├── __init__.py
│   ├── app.py                    # Flask应用入口
│   ├── config.py                 # 配置文件
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   └── model.py              # 模型信息表
│   ├── services/                 # 业务逻辑层
│   │   ├── __init__.py
│   │   └── model_service.py      # 模型管理服务
│   ├── controllers/              # 控制器层
│   │   ├── __init__.py
│   │   └── model_controller.py   # 模型控制器
│   ├── utils/                    # 工具类
│   │   ├── __init__.py
│   │   ├── validators.py         # 数据验证
│   │   ├── helpers.py            # 辅助函数
│   │   └── exceptions.py         # 自定义异常
│   └── integrations/             # 外部服务集成
│       ├── __init__.py
│       ├── huggingface_client.py # HuggingFace客户端
│       └── ollama_client.py      # Ollama客户端
├── docs/                         # 文档
│   ├── requirements_analysis.md  # 需求分析
│   ├── technical_architecture.md # 技术架构
│   └── task_breakdown.md         # 任务拆分
├── logs/                         # 日志文件
├── storage/                      # 文件存储目录
├── Pipfile                      # Pipenv配置
├── Pipfile.lock                 # Pipenv锁定文件
├── pyproject.toml               # Python项目配置
├── .flake8                      # 代码检查配置
├── .env.example                 # 环境变量示例
├── run.py                       # 启动脚本
├── README.md                    # 项目说明
└── QUICKSTART.md                # 快速启动指南
```

## 🧪 开发计划

### 第一阶段 ✅ 已完成

- [x] 基础架构搭建
- [x] 模型搜索与信息管理
- [x] HuggingFace集成
- [x] Ollama集成
- [x] RESTful API接口

### 第二阶段 🚧 进行中

- [ ] 模型下载管理
- [ ] 下载任务队列
- [ ] 断点续传支持

### 第三阶段 📋 计划中

- [ ] 模型部署管理
- [ ] Docker容器集成
- [ ] 资源监控

### 第四阶段 📋 计划中

- [ ] 对话调试功能
- [ ] WebSocket支持
- [ ] 流式对话

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源。

## 📞 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。 