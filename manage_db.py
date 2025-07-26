#!/usr/bin/env python3
"""
数据库管理脚本
用于管理数据库表的创建、重建等操作
"""
import sys
import argparse
from src.database.connection import create_tables, recreate_tables, db_manager
from src.config.settings import settings


def create_db_tables():
    """创建数据库表（如果不存在）"""
    print("正在创建数据库表...")
    try:
        create_tables()
        print("✅ 数据库表创建完成")
    except Exception as e:
        print(f"❌ 创建数据库表失败: {e}")
        sys.exit(1)


def recreate_db_tables():
    """强制重建数据库表（会删除所有数据）"""
    print("⚠️  警告：此操作将删除所有现有数据！")
    confirm = input("确认要重建数据库表吗？(输入 'yes' 确认): ")
    
    if confirm.lower() != 'yes':
        print("操作已取消")
        return
    
    print("正在重建数据库表...")
    try:
        recreate_tables()
        print("✅ 数据库表重建完成")
    except Exception as e:
        print(f"❌ 重建数据库表失败: {e}")
        sys.exit(1)


def test_db_connection():
    """测试数据库连接"""
    print("正在测试数据库连接...")
    try:
        if db_manager.test_connection():
            print("✅ 数据库连接正常")
        else:
            print("❌ 数据库连接失败")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        sys.exit(1)


def show_db_info():
    """显示数据库信息"""
    print("数据库配置信息:")
    print(f"  数据库URL: {settings.database_url}")
    print(f"  调试模式: {settings.debug}")
    
    # 检查表是否存在
    try:
        from sqlalchemy import inspect
        from src.database.connection import engine
        
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            print(f"  现有表: {', '.join(existing_tables)}")
        else:
            print("  现有表: 无")
    except Exception as e:
        print(f"  获取表信息失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="VoiceLingua 数据库管理工具")
    parser.add_argument(
        "action",
        choices=["create", "recreate", "test", "info"],
        help="执行的操作: create(创建表), recreate(重建表), test(测试连接), info(显示信息)"
    )
    
    args = parser.parse_args()
    
    if args.action == "create":
        create_db_tables()
    elif args.action == "recreate":
        recreate_db_tables()
    elif args.action == "test":
        test_db_connection()
    elif args.action == "info":
        show_db_info()


if __name__ == "__main__":
    main()