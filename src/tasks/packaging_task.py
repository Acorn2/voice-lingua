"""
打包任务
处理翻译结果的打包和存储
"""
import logging
from datetime import datetime
from celery import Task
from src.tasks.celery_app import celery_app
from src.database.connection import db_manager
from src.database.models import Task as TaskModel, TranslationResult
from src.types.models import TaskStatus

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="packaging.package_results")
def package_results_task(self: Task, task_id: str):
    """
    打包翻译结果
    
    Args:
        task_id: 任务ID
    
    Returns:
        dict: 打包结果
    """
    try:
        logger.info(f"开始打包任务: {task_id}")
        
        with db_manager.get_session() as db:
            # 获取任务信息
            task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
            if not task:
                raise Exception(f"任务不存在: {task_id}")
            
            # 获取所有翻译结果
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id
            ).all()
            
            # 构建结果数据
            results = {
                "transcription": {
                    "text": task.text_content,
                    "accuracy": task.accuracy,
                    "language": "zh"  # 源语言
                },
                "translations": []
            }
            
            for translation in translations:
                results["translations"].append({
                    "language": translation.target_language,
                    "text": translation.translated_text,
                    "confidence": translation.confidence,
                    "source_type": translation.source_type
                })
            
            # 更新任务状态为完成
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"打包任务完成: {task_id}")
            
            return {
                "task_id": task_id,
                "status": "completed",
                "results": results
            }
            
    except Exception as e:
        logger.error(f"打包任务失败: {task_id} - {str(e)}")
        # 更新任务状态为失败
        try:
            with db_manager.get_session() as db:
                task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
                if task:
                    task.status = TaskStatus.FAILED.value
                    task.error_message = f"打包失败: {str(e)}"
                    task.updated_at = datetime.utcnow()
                    db.commit()
        except Exception as update_error:
            logger.error(f"更新任务失败状态时出错: {update_error}")
        
        self.retry(countdown=60, max_retries=3)
        raise e 