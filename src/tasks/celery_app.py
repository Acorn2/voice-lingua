"""
Celery 应用配置
"""
import logging
import os
from celery import Celery
from celery.signals import worker_ready
from src.config.settings import CELERY_CONFIG

# 配置 Celery worker 日志
def setup_worker_logging():
    """配置 Celery worker 日志，每次启动时重置日志文件"""
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    # 获取当前 worker 的队列名称（从命令行参数中获取）
    import sys
    queue_name = "worker"
    for i, arg in enumerate(sys.argv):
        if arg == "--queues" and i + 1 < len(sys.argv):
            queue_name = sys.argv[i + 1]
            break
    
    # 配置日志文件路径
    log_file = f"logs/worker-{queue_name}.log"
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),  # 使用 'w' 模式重写文件
            logging.StreamHandler()
        ],
        force=True  # 强制重新配置
    )
    
    # 彻底减少 SQLAlchemy 日志的详细程度
    logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

# 创建 Celery 应用实例
celery_app = Celery("voicelingua")

# 应用配置
celery_app.config_from_object(CELERY_CONFIG)

# 自动发现任务
celery_app.autodiscover_tasks([
    'src.tasks.transcription_task',
    'src.tasks.translation_task', 
    'src.tasks.packaging_task'
])

# 配置任务路由
celery_app.conf.update(
    task_routes={
        'tasks.transcription.*': {'queue': 'transcription'},
        'tasks.translation.*': {'queue': 'translation'},
        'packaging.*': {'queue': 'packaging'},
    }
)

# Worker 启动时的信号处理
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Worker 启动时配置日志"""
    setup_worker_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"Worker 启动完成: {sender}")
    logger.info("日志文件已重置，开始记录新的日志") 