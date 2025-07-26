#!/usr/bin/env python3
"""
VoiceLingua 云服务器连接测试脚本
用于测试 PostgreSQL 和 Redis 连接是否正常
"""
import os
import sys
from datetime import datetime

def test_environment():
    """测试环境配置"""
    print("🔧 检查环境配置...")
    
    # 检查 .env 文件
    if not os.path.exists('.env'):
        print("❌ .env 文件不存在")
        print("请复制 env.example 为 .env 并填入正确配置")
        return False
    
    print("✅ .env 文件存在")
    return True


def test_imports():
    """测试依赖包导入"""
    print("\n📦 检查依赖包...")
    
    try:
        import fastapi
        print("✅ FastAPI 导入成功")
    except ImportError:
        print("❌ FastAPI 导入失败，请运行: pip install -r requirements.txt")
        return False
    
    try:
        import redis
        print("✅ Redis 包导入成功")
    except ImportError:
        print("❌ Redis 包导入失败")
        return False
    
    try:
        import psycopg2
        print("✅ PostgreSQL 驱动导入成功")
    except ImportError:
        print("❌ PostgreSQL 驱动导入失败")
        return False
    
    return True


def test_config_loading():
    """测试配置加载"""
    print("\n⚙️  测试配置加载...")
    
    try:
        from src.config.settings import settings
        print("✅ 配置文件加载成功")
        
        # 显示关键配置信息（不显示敏感信息）
        print(f"   ├─ 应用名称: {settings.app_name}")
        print(f"   ├─ 翻译引擎: {settings.translation_engine}")
        print(f"   ├─ Whisper 模型: {settings.whisper_model}")
        print(f"   └─ 支持语言: {', '.join(settings.get_supported_languages()[:5])}...")
        
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


def test_database_connection():
    """测试数据库连接"""
    print("\n🗄️  测试数据库连接...")
    
    try:
        from src.database.connection import db_manager
        
        if db_manager.test_connection():
            print("✅ PostgreSQL 连接成功")
            return True
        else:
            print("❌ PostgreSQL 连接失败")
            return False
            
    except Exception as e:
        print(f"❌ PostgreSQL 连接错误: {e}")
        print("请检查 DATABASE_URL 配置")
        return False


def test_redis_connection():
    """测试 Redis 连接"""
    print("\n🔑 测试 Redis 连接...")
    
    try:
        from src.config.settings import settings
        import redis
        
        # 测试 Redis 连接
        r = redis.from_url(settings.get_redis_url())
        r.ping()
        print("✅ Redis 连接成功")
        
        # 测试 Celery Broker
        broker_r = redis.from_url(settings.get_celery_broker_url())
        broker_r.ping()
        print("✅ Celery Broker (Redis) 连接成功")
        
        # 测试 Celery Result Backend
        result_r = redis.from_url(settings.get_celery_result_backend())
        result_r.ping()
        print("✅ Celery Result Backend (Redis) 连接成功")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis 连接错误: {e}")
        print("请检查 REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND 配置")
        return False


def test_translation_engine():
    """测试翻译引擎配置"""
    print("\n🔤 测试翻译引擎配置...")
    
    try:
        from src.config.settings import settings
        
        print(f"   ├─ 翻译引擎: {settings.translation_engine}")
        print(f"   ├─ 本地模型: {settings.translation_model}")
        
        if settings.translation_engine in ['qwen', 'mixed']:
            if settings.qwen_api_key and settings.qwen_api_key != "your_qwen_api_key_here":
                print("✅ 千问 API 密钥已配置")
            else:
                print("⚠️  千问 API 密钥未配置（如使用千问翻译请配置）")
        
        print("✅ 翻译引擎配置检查完成")
        return True
        
    except Exception as e:
        print(f"❌ 翻译引擎配置错误: {e}")
        return False


def test_storage_service():
    """测试存储服务配置"""
    print("\n💾 测试存储服务配置...")
    
    try:
        from src.config.settings import settings
        
        # 检查腾讯云COS配置
        if (settings.tencent_secret_id and 
            settings.tencent_secret_key and 
            settings.cos_bucket_name and
            settings.tencent_secret_id != "your_tencent_secret_id"):
            print("✅ 腾讯云COS配置已设置")
        else:
            print("⚠️  腾讯云COS配置不完整")
            print("请检查 TENCENT_SECRET_ID, TENCENT_SECRET_KEY, COS_BUCKET_NAME")
        
        return True
        
    except Exception as e:
        print(f"❌ 存储服务配置错误: {e}")
        return False


def main():
    """主测试函数"""
    print(f"🚀 VoiceLingua 云服务器连接测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    tests = [
        ("环境配置", test_environment),
        ("依赖包", test_imports),
        ("配置加载", test_config_loading),
        ("数据库连接", test_database_connection),
        ("Redis连接", test_redis_connection),
        ("翻译引擎", test_translation_engine),
        ("存储服务", test_storage_service),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        if test_func():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 项通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统配置正确，可以启动服务")
        print("\n🚀 启动命令: ./start.sh")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置后重试")
        print("\n📋 检查清单:")
        print("   1. 确保 .env 文件存在并配置正确")
        print("   2. 检查数据库连接字符串")
        print("   3. 检查 Redis 连接字符串")
        print("   4. 确认云服务器可以访问")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 