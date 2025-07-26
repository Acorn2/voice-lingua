"""
数据库连接管理
"""
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from src.config.settings import settings
from src.database.models import Base

logger = logging.getLogger(__name__)

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,  # 开发模式下显示 SQL 语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """创建数据库表"""
    try:
        # 检查表是否存在，只在不存在时创建
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            logger.info(f"数据库表已存在，跳过创建: {existing_tables}")
        else:
            logger.info("数据库表不存在，开始创建")
            Base.metadata.create_all(bind=engine)
            logger.info("数据库表创建成功")
    except SQLAlchemyError as e:
        logger.error(f"创建数据库表失败: {e}")
        raise


def recreate_tables():
    """强制重建数据库表（会删除所有数据）"""
    try:
        logger.warning("强制重建数据库表，所有数据将被删除")
        Base.metadata.drop_all(bind=engine)
        logger.info("旧表已删除")
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表重建成功")
    except SQLAlchemyError as e:
        logger.error(f"重建数据库表失败: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话
    
    用于 FastAPI 依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"数据库操作失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    def close_connection(self):
        """关闭数据库连接"""
        self.engine.dispose()
        logger.info("数据库连接已关闭")
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")
            return True
        except SQLAlchemyError as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False


# 全局数据库管理器实例
db_manager = DatabaseManager() 