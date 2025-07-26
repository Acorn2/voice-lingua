"""
文本翻译任务模块
"""
import logging
from typing import Optional, Dict, Any
import asyncio
import psutil
from datetime import datetime

from src.tasks.celery_app import celery_app
from src.types.models import TaskStatus, SourceType
from src.config.settings import settings
from src.database.connection import db_manager
from src.database.models import Task, TranslationResult
from src.services.translation_engine_service import translation_engine_service

logger = logging.getLogger(__name__)


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
            # 现在使用配置中的所有支持语言作为目标语言
            target_languages = task.languages
            expected_count = len(target_languages)
            
            # 如果是音频任务且有参考文本，翻译数量会翻倍
            if task.task_type == "audio" and task.reference_text and task.reference_text.strip():
                expected_count *= 2
            
            actual_count = len(translations)
            
            logger.info(f"翻译进度检查: {task_id} - {actual_count}/{expected_count} (目标语言: {target_languages})")
            
            if actual_count >= expected_count:
                # 触发打包任务
                from src.tasks.packaging_task import package_results_task
                package_results_task.delay(task_id)
                return True
            
            return False
            
    except Exception as e:
        logger.error(f"检查翻译完成状态失败: {e}")
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
        logger.info(f"开始翻译任务: {task_id} -> {target_language} ({source})")
        
        # 内存检查
        if not check_memory_usage():
            raise Exception(f"内存使用率过高: {psutil.virtual_memory().percent:.1f}%，暂停处理")
        
        # 转换来源类型
        source_type = SourceType(source)
        
        # 检测源语言
        detected_source_language = detect_text_language(text)
        logger.info(f"检测到源语言: {detected_source_language}, 目标语言: {target_language}")
        logger.info(f"文本内容: {text[:100]}...")
        
        # 如果源语言和目标语言相同，跳过翻译
        if detected_source_language == target_language:
            logger.info(f"源语言({detected_source_language})与目标语言({target_language})相同，跳过翻译")
            
            # 保存原文作为翻译结果
            result_data = {
                "task_id": task_id,
                "source_text": text,
                "translated_text": text,  # 原文作为翻译结果
                "target_language": target_language,
                "source_type": source_type.value,
                "confidence": 1.0,  # 原文置信度为1.0
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
        
        # 使用翻译引擎服务进行翻译
        async def run_translation():
            return await translation_engine_service.translate(
                text=text,
                target_language=target_language,
                source_language=detected_source_language  # 使用检测到的源语言
            )
        
        # 在 Celery 任务中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            translation_result = loop.run_until_complete(run_translation())
        finally:
            loop.close()
        
        # 提取翻译结果
        translated_text = translation_result["translated_text"]
        confidence = translation_result.get("confidence", 0.8)
        engine_used = translation_result.get("engine", "unknown")
        
        # 记录使用的引擎
        logger.info(f"翻译完成 - 引擎: {engine_used}, 置信度: {confidence:.3f}")
        
        # 如果是混合模式的回退，记录详细信息
        if translation_result.get("fallback"):
            logger.info(f"使用回退引擎: {translation_result.get('local_error', 'Unknown error')}")
        
        # 保存翻译结果
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
        
        save_translation_result(task_id, target_language, source_type, result_data)
        
        # 检查是否所有翻译都完成
        check_all_translations_completed(task_id)
        
        logger.info(f"翻译任务完成: {task_id} -> {target_language} ({source})")
        return {
            "status": "success", 
            "translated_text": translated_text,
            "confidence": confidence,
            "engine": engine_used
        }
        
    except Exception as e:
        error_msg = f"翻译失败: {str(e)}"
        logger.error(f"任务 {task_id} - {error_msg}")
        
        # 重试逻辑
        retry_count = settings.translation_retry_count
        if self.request.retries < retry_count:
            logger.info(f"重试翻译任务 {task_id} (第 {self.request.retries + 1} 次)")
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
        logger.error(f"查询翻译结果失败: {e}")
        return []


def get_translation_engine_status() -> Dict[str, Any]:
    """获取翻译引擎状态（用于健康检查）"""
    try:
        return translation_engine_service.get_engine_status()
    except Exception as e:
        logger.error(f"获取翻译引擎状态失败: {e}")
        return {"error": str(e)} 