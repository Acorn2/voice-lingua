"""
打包任务
处理翻译结果的打包和存储
"""
import logging
import json
import os
from datetime import datetime
from celery import Task
from src.tasks.celery_app import celery_app
from src.database.connection import db_manager
from src.database.models import Task as TaskModel, TranslationResult
from src.types.models import TaskStatus
from src.services.storage_service import storage_service

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
            
            # 检测源语言（从转录任务中的语言检测逻辑）
            def detect_source_language(text):
                if not text:
                    return 'unknown'
                chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
                total_chars = len([c for c in text if c.isalpha() or '\u4e00' <= c <= '\u9fff'])
                if total_chars == 0:
                    return 'unknown'
                chinese_ratio = chinese_chars / total_chars
                return 'zh' if chinese_ratio > 0.3 else 'en'
            
            source_language = detect_source_language(task.text_content) if task.text_content else 'unknown'
            
            # 构建完整的结果数据
            results = {
                "task_id": task_id,
                "task_type": task.task_type,
                "status": "completed",
                "created_at": task.created_at.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "source_language": source_language,
                "target_languages": task.languages,
                "transcription": {
                    "text": task.text_content,
                    "accuracy": float(task.accuracy) if task.accuracy else None,
                    "language": source_language
                } if task.text_content else None,
                "translations": {},
                "summary": {
                    "total_translations": len(translations),
                    "languages_completed": list(set(t.target_language for t in translations)),
                    "processing_time": None  # 可以计算处理时间
                }
            }
            
            # 按语言和来源组织翻译结果
            for translation in translations:
                lang = translation.target_language
                source_type = translation.source_type
                
                if lang not in results["translations"]:
                    results["translations"][lang] = {}
                
                # 根据来源类型设置键名
                key = "audio_text" if source_type == "AUDIO" else "reference_text"
                
                results["translations"][lang][key] = {
                    "text": translation.translated_text,
                    "source_text": translation.source_text,
                    "confidence": float(translation.confidence) if translation.confidence else None,
                    "source_type": source_type,
                    "created_at": translation.created_at.isoformat()
                }
            
            # 保存结果到本地文件
            local_results_dir = "results"
            os.makedirs(local_results_dir, exist_ok=True)
            local_file_path = os.path.join(local_results_dir, f"{task_id}.json")
            
            try:
                with open(local_file_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                logger.info(f"结果文件保存到本地: {local_file_path}")
            except Exception as e:
                logger.error(f"保存本地结果文件失败: {e}")
                # 继续执行，不因为本地保存失败而中断
            
            # 上传到云存储
            cos_key = f"results/{datetime.now().strftime('%Y/%m/%d')}/{task_id}.json"
            result_url = None
            
            try:
                if storage_service.upload_json(results, cos_key):
                    # 生成访问URL（24小时有效）
                    result_url = storage_service.get_file_url(cos_key, expires=86400)
                    logger.info(f"结果文件上传到云存储成功: {cos_key}")
                else:
                    logger.error("结果文件上传到云存储失败")
            except Exception as e:
                logger.error(f"云存储操作失败: {e}")
                # 如果云存储失败，使用本地文件路径
                result_url = f"file://{os.path.abspath(local_file_path)}"
            
            # 更新任务状态为打包完成
            task.status = TaskStatus.PACKAGING_COMPLETED.value
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            task.result_url = result_url  # 设置结果URL
            db.commit()
            
            logger.info(f"打包任务完成: {task_id}")
            
            return {
                "task_id": task_id,
                "status": "completed",
                "result_url": result_url,
                "local_file": local_file_path,
                "cos_key": cos_key,
                "translations_count": len(translations),
                "results": results
            }
            
    except Exception as e:
        logger.error(f"打包任务失败: {task_id} - {str(e)}")
        # 更新任务状态为失败
        try:
            with db_manager.get_session() as db:
                task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
                if task:
                    task.status = TaskStatus.PACKAGING_FAILED.value
                    task.error_message = f"打包失败: {str(e)}"
                    task.updated_at = datetime.utcnow()
                    db.commit()
        except Exception as update_error:
            logger.error(f"更新任务失败状态时出错: {update_error}")
        
        self.retry(countdown=60, max_retries=3)
        raise e 