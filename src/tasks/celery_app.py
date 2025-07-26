"""
Celery 应用配置
"""
from celery import Celery
from src.config.settings import CELERY_CONFIG

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
        'src.tasks.transcription_task.*': {'queue': 'transcription'},
        'src.tasks.translation_task.*': {'queue': 'translation'},
        'src.tasks.packaging_task.*': {'queue': 'packaging'},
    }
) 