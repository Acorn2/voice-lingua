"""
文本翻译任务模块
"""
import logging
from typing import Optional, Dict, Any
import torch
import psutil
from datetime import datetime
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

from src.tasks.celery_app import celery_app
from src.types.models import TaskStatus, SourceType
from src.config.settings import settings, LANGUAGE_MAPPING
from src.database.connection import db_manager
from src.database.models import Task, TranslationResult

logger = logging.getLogger(__name__)

# 全局翻译模型缓存
_translation_model = None
_translation_tokenizer = None


def get_translation_model():
    """获取翻译模型（懒加载）"""
    global _translation_model, _translation_tokenizer
    
    if _translation_model is None:
        device = "cuda" if torch.cuda.is_available() and settings.whisper_device == "cuda" else "cpu"
        logger.info(f"加载翻译模型: {settings.translation_model}, 设备: {device}")
        
        _translation_tokenizer = M2M100Tokenizer.from_pretrained(settings.translation_model)
        _translation_model = M2M100ForConditionalGeneration.from_pretrained(settings.translation_model).to(device)
        
        logger.info("翻译模型加载完成")
    
    return _translation_model, _translation_tokenizer


def check_memory_usage() -> bool:
    """检查内存使用情况"""
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    if memory_percent > settings.memory_threshold:
        logger.warning(f"内存使用率过高: {memory_percent:.1f}%，阈值: {settings.memory_threshold}%")
        return False
    
    return True


def save_translation_result(
    task_id: str, 
    target_language: str, 
    source: SourceType, 
    translation_data: Dict[str, Any]
):
    """保存翻译结果"""
    try:
        with db_manager.get_session() as db:
            # 检查是否已存在相同的翻译结果
            existing = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id,
                TranslationResult.target_language == target_language,
                TranslationResult.source_type == source.value
            ).first()
            
            if existing:
                # 更新现有记录
                existing.translated_text = translation_data["translated_text"]
                existing.confidence = translation_data.get("confidence")
                logger.info(f"更新翻译结果: {task_id} -> {target_language} ({source.value})")
            else:
                # 创建新记录
                translation_result = TranslationResult(
                    task_id=task_id,
                    target_language=target_language,
                    source_type=source.value,
                    source_text=translation_data["source_text"],
                    translated_text=translation_data["translated_text"],
                    confidence=translation_data.get("confidence")
                )
                db.add(translation_result)
                logger.info(f"保存翻译结果: {task_id} -> {target_language} ({source.value})")
            
            db.commit()
            
    except Exception as e:
        logger.error(f"保存翻译结果失败: {e}")


def check_all_translations_completed(task_id: str) -> bool:
    """检查任务的所有翻译是否都已完成"""
    try:
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                return False
            
            # 获取所有翻译结果
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id
            ).all()
            
            # 计算期待的翻译数量
            expected_count = len(task.languages)
            
            # 如果是音频任务且有参考文本，翻译数量会翻倍
            if task.task_type == "audio" and task.reference_text:
                expected_count *= 2
            
            actual_count = len(translations)
            
            logger.info(f"翻译进度检查: {task_id} - {actual_count}/{expected_count}")
            
            if actual_count >= expected_count:
                # 触发打包任务
                from src.tasks.packaging_task import package_results_task
                package_results_task.delay(task_id)
                return True
            
            return False
            
    except Exception as e:
        logger.error(f"检查翻译完成状态失败: {e}")
        return False


@celery_app.task(bind=True, name='tasks.translation.translate_text')
def translate_text_task(
    self, 
    task_id: str, 
    text: str, 
    target_language: str, 
    source: str
):
    """
    文本翻译任务
    
    使用 M2M100 模型进行多语言翻译
    """
    try:
        logger.info(f"开始翻译任务: {task_id} -> {target_language} ({source})")
        
        # 内存检查
        if not check_memory_usage():
            raise Exception(f"内存使用率过高: {psutil.virtual_memory().percent:.1f}%，暂停处理")
        
        # 转换来源类型
        source_type = SourceType(source)
        
        # 检查是否需要跳过翻译（源语言与目标语言相同）
        if target_language == settings.whisper_language:
            translated_text = text
            confidence = 1.0
            logger.info(f"跳过相同语言翻译: {task_id} -> {target_language}")
        else:
            # 获取翻译模型
            model, tokenizer = get_translation_model()
            
            # 设置源语言和目标语言
            tokenizer.src_lang = settings.whisper_language  # 默认源语言
            target_lang_code = LANGUAGE_MAPPING.get(target_language, target_language)
            
            # 执行翻译
            logger.info(f"翻译: {settings.whisper_language} -> {target_lang_code}")
            
            # 编码输入文本
            encoded = tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=settings.max_translation_length
            )
            
            # 移动到设备
            device = next(model.parameters()).device
            encoded = {k: v.to(device) for k, v in encoded.items()}
            
            # 生成翻译
            with torch.no_grad():
                generated_tokens = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.get_lang_id(target_lang_code),
                    max_length=settings.max_translation_length,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            # 解码结果
            translated_text = tokenizer.batch_decode(
                generated_tokens, 
                skip_special_tokens=True
            )[0].strip()
            
            # 简单的置信度计算（基于文本长度比例）
            confidence = min(1.0, len(translated_text) / max(1, len(text)))
        
        # 保存翻译结果
        translation_result = {
            "task_id": task_id,
            "source_text": text,
            "translated_text": translated_text,
            "target_language": target_language,
            "source_type": source_type.value,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        save_translation_result(task_id, target_language, source_type, translation_result)
        
        # 检查是否所有翻译都完成
        check_all_translations_completed(task_id)
        
        logger.info(f"翻译任务完成: {task_id} -> {target_language} ({source})")
        return {
            "status": "success", 
            "translated_text": translated_text,
            "confidence": confidence
        }
        
    except Exception as e:
        error_msg = f"翻译失败: {str(e)}"
        logger.error(f"任务 {task_id} - {error_msg}")
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.info(f"重试翻译任务 {task_id} (第 {self.request.retries + 1} 次)")
            raise self.retry(countdown=60, exc=e)
        
        raise e


def get_all_translations_by_task(task_id: str):
    """获取任务的所有翻译结果"""
    try:
        with db_manager.get_session() as db:
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id
            ).all()
            return translations
    except Exception as e:
        logger.error(f"查询翻译结果失败: {e}")
        return [] 