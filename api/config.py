import os

from dotenv import load_dotenv

load_dotenv()

# 获取项目根目录的绝对路径
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    """基础配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # 数据库配置 - 使用绝对路径确保数据持久性
    DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'llm_manager.db')

    # 确保instance目录存在
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    # 优先使用环境变量，但如果是相对路径的SQLite，则使用绝对路径
    env_db_url = os.environ.get('DATABASE_URL', '')
    if env_db_url and not env_db_url.startswith(('sqlite:///', 'postgresql://', 'mysql://')):
        # 如果环境变量不是完整的数据库URL，使用默认配置
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    elif env_db_url.startswith('sqlite:///') and not os.path.isabs(env_db_url.replace('sqlite:///', '')):
        # 如果是相对路径的SQLite，转换为绝对路径
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    else:
        # 使用环境变量或默认配置
        SQLALCHEMY_DATABASE_URI = env_db_url or f'sqlite:///{DATABASE_PATH}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis配置
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # Celery配置
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # 存储配置 - 使用绝对路径
    STORAGE_PATH = os.environ.get('STORAGE_PATH') or os.path.join(BASE_DIR, 'storage')
    DOWNLOADS_PATH = os.path.join(STORAGE_PATH, 'downloads')
    MODELS_PATH = os.path.join(STORAGE_PATH, 'models')

    # HuggingFace配置
    HUGGINGFACE_TOKEN = os.environ.get('HUGGINGFACE_TOKEN')
    HUGGINGFACE_CACHE_TTL = int(os.environ.get('HUGGINGFACE_CACHE_TTL', 3600))  # 1小时

    # Ollama配置
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL') or 'http://localhost:11434'
    OLLAMA_CACHE_TTL = int(os.environ.get('OLLAMA_CACHE_TTL', 3600))  # 1小时

    # 分页配置
    DEFAULT_PAGE_SIZE = int(os.environ.get('DEFAULT_PAGE_SIZE', 20))
    MAX_PAGE_SIZE = int(os.environ.get('MAX_PAGE_SIZE', 100))


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False

    # 生产环境建议使用PostgreSQL
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:pass@localhost/llm_manager'


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
