#!/usr/bin/env python3
"""
LLM Manager API 启动脚本
"""
import os
import sys

from api.app import create_app


def main():
    """主函数"""
    # 设置环境变量
    if len(sys.argv) > 1 and sys.argv[1] in ['development', 'production', 'testing']:
        os.environ['FLASK_ENV'] = sys.argv[1]

    # 创建应用
    app = create_app()

    # 获取配置
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = app.config.get('DEBUG', False)

    print(f"🚀 启动 LLM Manager API")
    print(f"📍 环境: {os.getenv('FLASK_ENV', 'development')}")
    print(f"🌐 地址: http://{host}:{port}")
    print(f"🔧 调试模式: {'开启' if debug else '关闭'}")
    print(f"📝 API文档: http://{host}:{port}/")
    print(f"❤️  健康检查: http://{host}:{port}/health")

    # 启动应用
    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
