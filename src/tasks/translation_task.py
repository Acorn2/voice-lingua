"""
文本翻译任务模块
"""
import asyncio
import logging
import psutil
from datetime import datetime
from typing import Optional, Dict, Any

from src.tasks.celery_app import celery_app
from src.types.models import TaskStatus, SourceType
from src.config.settings import settings
from src.database.connection import db_manager
from src.database.models import Task, TranslationResult
from src.services.translation_engine_service import translation_engine_service
from src.utils.logger import get_business_logger, setup_business_logging

# 设置业务日志
setup_business_logging()
logger = get_business_logger(__name__)


def update_task_status(task_id: str, status: TaskStatus, details: Optional[Dict[str, Any]] = None):
    """更新任务状态"""
    try:
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
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
                logger.step("TRANSLATION", "更新翻译结果", task_id, 
                           language=target_language, source=source.value)
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
                logger.step("TRANSLATION", "保存翻译结果", task_id, 
                           language=target_language, source=source.value)
            
            db.commit()
            
    except Exception as e:
        logger.step("ERROR", "保存翻译结果失败", task_id, error=str(e))


def check_all_translations_completed(task_id: str) -> bool:
    """检查任务的所有翻译是否都已完成"""
    try:
        logger.step("TRANSLATION", "开始检查翻译完成状态", task_id)
        
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                logger.step("TRANSLATION", "任务不存在", task_id)
                return False
            
            # 获取所有翻译结果
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id
            ).all()
            
            # 计算期待的翻译数量
            target_languages = task.languages
            expected_count = len(target_languages)
            
            # 如果是音频任务且有参考文本，翻译数量会翻倍
            if task.task_type == "audio" and task.reference_text and task.reference_text.strip():
                expected_count *= 2
            
            actual_count = len(translations)
            completed_languages = list(set(t.target_language for t in translations))
            
            logger.step("TRANSLATION", "翻译进度统计", task_id,
                       progress=f"{actual_count}/{expected_count}",
                       target_languages=target_languages,
                       completed_languages=completed_languages,
                       has_reference=bool(task.reference_text and task.reference_text.strip()))
            
            if actual_count >= expected_count:
                logger.step("TRANSLATION", "所有翻译已完成", task_id,
                           total_translations=actual_count)
                
                # 更新任务状态为翻译完成
                logger.step("TRANSLATION", "更新状态为翻译完成", task_id)
                update_task_status(task_id, TaskStatus.TRANSLATION_COMPLETED)
                
                # 触发打包任务
                logger.step("TRANSLATION", "触发打包任务", task_id)
                from src.tasks.packaging_task import package_results_task
                package_results_task.delay(task_id)
                return True
            else:
                logger.step("TRANSLATION", "翻译尚未完成", task_id,
                           remaining=expected_count - actual_count)
            
            return False
            
    except Exception as e:
        logger.step("ERROR", "检查翻译完成状态失败", task_id, error=str(e))
        return False


def detect_text_language(text: str) -> str:
    """
    检测文本的源语言
    
    使用字符统计和常见词汇检测方法
    """
    if not text or not text.strip():
        return 'en'  # 默认英文
    
    text = text.strip()
    
    # 统计不同语言的字符
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    japanese_hiragana = sum(1 for char in text if '\u3040' <= char <= '\u309f')
    japanese_katakana = sum(1 for char in text if '\u30a0' <= char <= '\u30ff')
    korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7af')
    
    # 统计拉丁字母
    latin_chars = sum(1 for char in text if char.isalpha() and ord(char) < 256)
    
    # 统计总的有效字符数
    total_chars = len([c for c in text if c.isalpha() or '\u4e00' <= c <= '\u9fff' or 
                      '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' or 
                      '\uac00' <= c <= '\ud7af'])
    
    if total_chars == 0:
        return 'en'  # 默认英文
    
    # 计算各语言字符比例
    chinese_ratio = chinese_chars / total_chars
    japanese_ratio = (japanese_hiragana + japanese_katakana) / total_chars
    korean_ratio = korean_chars / total_chars
    latin_ratio = latin_chars / total_chars
    
    logger.debug(f"语言检测统计 - 中文: {chinese_ratio:.2f}, 日文: {japanese_ratio:.2f}, "
                f"韩文: {korean_ratio:.2f}, 拉丁: {latin_ratio:.2f}")
    
    # 语言检测逻辑（按优先级）
    if chinese_ratio > 0.3:
        return 'zh'
    elif japanese_ratio > 0.2 or japanese_hiragana > 0:  # 平假名是日文的强特征
        return 'ja'
    elif korean_ratio > 0.2:
        return 'ko'
    elif latin_ratio > 0.7:
        # 主要是拉丁字母，进一步检测具体语言
        return detect_latin_language(text)
    elif chinese_ratio > 0.1:
        # 有一定中文字符，但不够多，可能是中英混合
        return 'zh'
    else:
        # 默认英文
        return 'en'


def detect_latin_language(text: str) -> str:
    """
    检测拉丁字母文本的具体语言
    
    使用简单的特征词检测
    """
    text_lower = text.lower()
    
    # 英文特征词
    english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has', 'had', 
                         'will', 'would', 'could', 'should', 'this', 'that', 'with', 'from']
    
    # 法文特征词
    french_indicators = ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'est', 'sont', 
                        'avec', 'pour', 'dans', 'sur', 'par', 'ce', 'cette', 'ces']
    
    # 德文特征词
    german_indicators = ['der', 'die', 'das', 'und', 'ist', 'sind', 'mit', 'für', 
                        'in', 'auf', 'von', 'zu', 'ein', 'eine', 'einen']
    
    # 西班牙文特征词
    spanish_indicators = ['el', 'la', 'los', 'las', 'de', 'del', 'y', 'es', 'son', 
                         'con', 'para', 'en', 'por', 'un', 'una', 'este', 'esta']
    
    # 意大利文特征词
    italian_indicators = ['il', 'la', 'lo', 'gli', 'le', 'di', 'del', 'e', 'è', 'sono', 
                         'con', 'per', 'in', 'su', 'da', 'un', 'una', 'questo', 'questa']
    
    # 统计各语言特征词出现次数
    words = text_lower.split()
    
    english_count = sum(1 for word in words if word in english_indicators)
    french_count = sum(1 for word in words if word in french_indicators)
    german_count = sum(1 for word in words if word in german_indicators)
    spanish_count = sum(1 for word in words if word in spanish_indicators)
    italian_count = sum(1 for word in words if word in italian_indicators)
    
    # 找出最高分的语言
    scores = {
        'en': english_count,
        'fr': french_count,
        'de': german_count,
        'es': spanish_count,
        'it': italian_count
    }
    
    max_score = max(scores.values())
    if max_score > 0:
        # 返回得分最高的语言
        for lang, score in scores.items():
            if score == max_score:
                return lang
    
    # 如果没有匹配到特征词，默认英文
    return 'en'


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
    
    使用翻译引擎服务进行多语言翻译（支持本地模型和千问大模型）
    """
    try:
        # === 任务开始记录 ===
        logger.step("TRANSLATION", "翻译任务开始", task_id,
                   target_language=target_language,
                   source_type=source,
                   text_preview=text[:50] + ("..." if len(text) > 50 else ""))
        
        # 更新任务状态为翻译处理中（只在第一个翻译任务时更新）
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if task and task.status == TaskStatus.TRANSLATION_PENDING.value:
                logger.step("TRANSLATION", "更新状态为处理中", task_id)
                update_task_status(task_id, TaskStatus.TRANSLATION_PROCESSING)
        
        # === 系统资源检查 ===
        memory_percent = psutil.virtual_memory().percent
        logger.resource_usage(task_id,
                            memory_percent=f"{memory_percent:.1f}%")
        
        if not check_memory_usage():
            raise Exception(f"内存使用率过高: {memory_percent:.1f}%，暂停处理")
        
        # 转换来源类型
        source_type = SourceType(source)
        
        # === 语言检测 ===
        logger.step("TRANSLATION", "开始检测源语言", task_id)
        detected_source_language = detect_text_language(text)
        logger.step("TRANSLATION", "语言检测完成", task_id,
                   detected_source=detected_source_language,
                   target=target_language)
        
        # === 检查是否需要翻译 ===
        if detected_source_language == target_language:
            logger.translation_skip(task_id, target_language, 
                                  "源语言与目标语言相同")
            
            # 保存原文作为翻译结果
            result_data = {
                "task_id": task_id,
                "source_text": text,
                "translated_text": text,
                "target_language": target_language,
                "source_type": source_type.value,
                "confidence": 1.0,
                "engine": "skip_same_language",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            save_translation_result(task_id, target_language, source_type, result_data)
            check_all_translations_completed(task_id)
            
            return {
                "status": "success", 
                "translated_text": text,
                "confidence": 1.0,
                "engine": "skip_same_language",
                "note": "源语言与目标语言相同，跳过翻译"
            }
        
        # === 开始翻译 ===
        logger.translation_start(task_id, detected_source_language, target_language,
                                source_type=source,
                                text_length=len(text))
        
        async def run_translation():
            return await translation_engine_service.translate(
                text=text,
                target_language=target_language,
                source_language=detected_source_language
            )
        
        # 在 Celery 任务中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        translation_start_time = datetime.utcnow()
        try:
            translation_result = loop.run_until_complete(run_translation())
        finally:
            loop.close()
        translation_duration = (datetime.utcnow() - translation_start_time).total_seconds()
        
        # === 处理翻译结果 ===
        translated_text = translation_result["translated_text"]
        confidence = translation_result.get("confidence", 0.8)
        engine_used = translation_result.get("engine", "unknown")
        
        logger.translation_complete(task_id, detected_source_language, target_language,
                                  engine_used, confidence,
                                  duration=f"{translation_duration:.2f}s",
                                  result_preview=translated_text[:50] + ("..." if len(translated_text) > 50 else ""))
        logger.performance(task_id, "translation", translation_duration)
        
        # 如果是混合模式的回退，记录详细信息
        if translation_result.get("fallback"):
            logger.step("TRANSLATION", "使用回退引擎", task_id,
                       fallback_reason=translation_result.get('local_error', 'Unknown error'))
        
        # === 保存翻译结果 ===
        result_data = {
            "task_id": task_id,
            "source_text": text,
            "translated_text": translated_text,
            "target_language": target_language,
            "source_type": source_type.value,
            "confidence": confidence,
            "engine": engine_used,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.step("TRANSLATION", "保存翻译结果", task_id,
                   target_language=target_language,
                   confidence=f"{confidence:.3f}")
        save_translation_result(task_id, target_language, source_type, result_data)
        
        # === 检查所有翻译是否完成 ===
        logger.step("TRANSLATION", "检查所有翻译完成状态", task_id)
        check_all_translations_completed(task_id)
        
        logger.step("TRANSLATION", "单个翻译任务完成", task_id,
                   target_language=target_language,
                   engine=engine_used,
                   duration=f"{translation_duration:.2f}s")
        
        return {
            "status": "success", 
            "translated_text": translated_text,
            "confidence": confidence,
            "engine": engine_used
        }
        
    except Exception as e:
        error_msg = f"翻译失败: {str(e)}"
        logger.translation_fail(task_id, detected_source_language if 'detected_source_language' in locals() else 'unknown', 
                               target_language, error_msg)
        
        # 重试逻辑
        retry_count = settings.translation_retry_count
        if self.request.retries < retry_count:
            logger.step("TRANSLATION", "准备重试", task_id,
                       retry_count=self.request.retries + 1,
                       max_retries=retry_count,
                       countdown=f"{min(60 * (2 ** self.request.retries), 300)}s")
            # 使用指数退避策略
            countdown = min(60 * (2 ** self.request.retries), 300)  # 最大5分钟
            raise self.retry(countdown=countdown, exc=e)
        
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
        logger.step("ERROR", "查询翻译结果失败", task_id, error=str(e))
        return []


def get_translation_engine_status() -> Dict[str, Any]:
    """获取翻译引擎状态（用于健康检查）"""
    try:
        return translation_engine_service.get_engine_status()
    except Exception as e:
        logger.step("ERROR", "获取翻译引擎状态失败", error=str(e))
        return {"error": str(e)} 