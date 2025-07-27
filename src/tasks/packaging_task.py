"""
打包任务
处理翻译结果的打包和存储
"""
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from celery import Task
from src.tasks.celery_app import celery_app
from src.database.connection import db_manager
from src.database.models import Task as TaskModel, TranslationResult
from src.types.models import TaskStatus
from src.services.storage_service import storage_service
from src.utils.logger import get_business_logger, setup_business_logging
from src.utils.compact_encoder import CompactTranslationEncoder, UltraCompactEncoder

# 设置业务日志
setup_business_logging()
logger = get_business_logger(__name__)


def update_task_status(task_id: str, status: TaskStatus, details: Optional[Dict[str, Any]] = None):
    """更新任务状态"""
    try:
        with db_manager.get_session() as db:
            task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
            if task:
                task.status = status.value
                task.updated_at = datetime.utcnow()
                
                # 根据状态更新相应的时间字段
                if status == TaskStatus.TRANSCRIPTION_COMPLETED:
                    task.transcription_completed_at = datetime.utcnow()
                elif status == TaskStatus.TRANSLATION_COMPLETED:
                    task.translation_completed_at = datetime.utcnow()
                elif status == TaskStatus.PACKAGING_COMPLETED:
                    task.completed_at = datetime.utcnow()
                
                if details:
                    if "error" in details:
                        task.error_message = details["error"]
                    if "accuracy" in details:
                        task.accuracy = details["accuracy"]
                    if "result_url" in details:
                        task.result_url = details["result_url"]
                
                db.commit()
                logger.step("SYSTEM", "状态更新成功", task_id, status=status.value)
            else:
                logger.step("ERROR", "任务不存在", task_id)
                
    except Exception as e:
        logger.step("ERROR", "状态更新失败", task_id, error=str(e))


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
        # === 打包任务开始 ===
        logger.step("PACKAGING", "打包任务开始", task_id)
        
        with db_manager.get_session() as db:
            # === 获取任务信息 ===
            logger.step("PACKAGING", "获取任务信息", task_id)
            task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
            if not task:
                logger.packaging_fail(task_id, "任务不存在")
                raise Exception(f"任务不存在: {task_id}")
            
            logger.step("PACKAGING", "任务信息验证", task_id,
                       task_type=task.task_type,
                       status=task.status,
                       target_languages=task.languages)
            
            # === 获取翻译结果 ===
            logger.step("PACKAGING", "获取翻译结果", task_id)
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id
            ).all()
            
            translations_count = len(translations)
            logger.step("PACKAGING", "翻译结果统计", task_id,
                       total_translations=translations_count,
                       languages=[t.target_language for t in translations])
            
            if translations_count == 0:
                logger.packaging_fail(task_id, "没有找到任何翻译结果")
                raise Exception("没有找到任何翻译结果")
            
            # === 检测源语言 ===
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
            logger.step("PACKAGING", "源语言检测", task_id, 
                       source_language=source_language)
            
            # === 构建结果数据 ===
            logger.step("PACKAGING", "构建结果数据", task_id)
            processing_start = task.created_at
            processing_end = datetime.utcnow()
            total_processing_time = (processing_end - processing_start).total_seconds()
            
            results = {
                "task_id": task_id,
                "task_type": task.task_type,
                "status": "completed",
                "created_at": task.created_at.isoformat(),
                "completed_at": processing_end.isoformat(),
                "processing_time_seconds": total_processing_time,
                "source_language": source_language,
                "target_languages": task.languages,
                "transcription": {
                    "text": task.text_content,
                    "accuracy": float(task.accuracy) if task.accuracy else None,
                    "language": source_language
                } if task.text_content else None,
                "translations": {},
                "summary": {
                    "total_translations": translations_count,
                    "languages_completed": list(set(t.target_language for t in translations)),
                    "processing_time_formatted": f"{total_processing_time:.2f}s"
                }
            }
            
            # === 组织翻译结果 ===
            logger.step("PACKAGING", "组织翻译结果", task_id)
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
                
                logger.step("PACKAGING", "添加翻译结果", task_id,
                           language=lang,
                           source_type=source_type,
                           confidence=f"{translation.confidence:.3f}" if translation.confidence else "N/A")
            
            # === 紧凑JSON编码和保存 ===
            logger.step("PACKAGING", "开始紧凑JSON编码", task_id)
            local_results_dir = "results"
            os.makedirs(local_results_dir, exist_ok=True)
            
            # 生成紧凑JSON格式
            compact_file_path = os.path.join(local_results_dir, f"{task_id}.compact.json")
            file_size = 0
            
            try:
                # 编码为紧凑JSON格式
                compact_data = CompactTranslationEncoder.encode_compact_json(results)
                
                # 保存紧凑JSON文件
                with open(compact_file_path, 'w', encoding='utf-8') as f:
                    json.dump(compact_data, f, ensure_ascii=False)
                file_size = os.path.getsize(compact_file_path)
                
                # 获取压缩统计
                compression_stats = CompactTranslationEncoder.get_compression_stats(results)
                
                logger.step("PACKAGING", "紧凑JSON编码完成", task_id,
                           original_size=f"{compression_stats['original_size']}B",
                           compact_size=f"{file_size}B",
                           compression_ratio=compression_stats["compression_ratios"]["compact_json"],
                           space_saved=compression_stats["size_reduction"]["compact_json"])
                
            except Exception as e:
                logger.step("PACKAGING", "紧凑JSON编码失败", task_id, error=str(e))
                # 回退到原始JSON格式
                with open(compact_file_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                file_size = os.path.getsize(compact_file_path)
                logger.step("PACKAGING", "回退到原始JSON格式", task_id, size=f"{file_size}B")
            
            # === 云存储上传 ===
            cos_key = f"results/{datetime.now().strftime('%Y%m%d')}/{task_id}.compact.json"
            logger.step("PACKAGING", "开始云存储上传", task_id, cos_key=cos_key)
            result_url = None
            
            try:
                # 上传紧凑JSON到云存储
                with open(compact_file_path, 'r', encoding='utf-8') as f:
                    compact_data = json.load(f)
                
                if storage_service.upload_json(compact_data, cos_key):
                    result_url = storage_service.get_file_url(cos_key, expires=86400)
                    logger.step("PACKAGING", "云存储上传成功", task_id,
                               cos_key=cos_key,
                               size=f"{file_size}B",
                               expires="24h")
                else:
                    logger.step("PACKAGING", "云存储上传失败", task_id)
                    
            except Exception as e:
                logger.step("PACKAGING", "云存储操作失败", task_id, error=str(e))
                result_url = None
            
            # 如果云存储失败，使用本地文件路径
            if not result_url:
                result_url = f"file://{os.path.abspath(compact_file_path)}"
                logger.step("PACKAGING", "使用本地文件路径", task_id, 
                           fallback_url=result_url)
            
            # === 更新任务状态 ===
            logger.step("PACKAGING", "更新任务状态为完成", task_id,
                       result_url=result_url)
            update_task_status(task_id, TaskStatus.PACKAGING_COMPLETED, {"result_url": result_url})
            
            # === 打包完成 ===
            logger.packaging_complete(task_id, result_url or compact_file_path, file_size,
                                    translations_count=translations_count,
                                    languages_count=len(set(t.target_language for t in translations)),
                                    processing_time=f"{total_processing_time:.2f}s")
            
            return {
                "task_id": task_id,
                "status": "completed",
                "result_url": result_url,
                "local_file": compact_file_path,
                "cos_key": cos_key,
                "translations_count": translations_count,
                "file_size": file_size,
                "processing_time": total_processing_time,
                "results": results
            }
            
    except Exception as e:
        error_msg = f"打包失败: {str(e)}"
        logger.packaging_fail(task_id, error_msg)
        
        # 更新任务状态为失败
        try:
            update_task_status(task_id, TaskStatus.PACKAGING_FAILED, {"error": error_msg})
        except Exception as update_error:
            logger.step("ERROR", "更新任务失败状态时出错", task_id, error=str(update_error))
        
        self.retry(countdown=60, max_retries=3)
        raise e 