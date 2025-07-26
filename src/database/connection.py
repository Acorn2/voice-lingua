"""
数据库连接管理
"""
from typing import Generator
from sqlalchemy import create_engine
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
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建成功")
    except SQLAlchemyError as e:
        logger.error(f"创建数据库表失败: {e}")
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
                conn.execute("SELECT 1")
            logger.info("数据库连接测试成功")
            return True
        except SQLAlchemyError as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False


# 全局数据库管理器实例
db_manager = DatabaseManager() 