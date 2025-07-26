"""
语音转录任务模块
"""
import os
import logging
from typing import Optional, Dict, Any
import whisper
import torch
import psutil
from textdistance import levenshtein
from datetime import datetime

from src.tasks.celery_app import celery_app
from src.types.models import TaskStatus, SourceType
from src.config.settings import settings
from src.database.connection import db_manager
from src.database.models import Task, TranslationResult
from src.services.storage_service import storage_service
from src.utils.logger import get_business_logger, setup_business_logging

# 设置业务日志
setup_business_logging()
logger = get_business_logger(__name__)

# 全局 Whisper 模型缓存
_whisper_model = None


def detect_text_language(text: str) -> str:
    """
    检测文本的源语言
    
    使用字符统计检测方法
    """
    if not text or not text.strip():
        return 'unknown'
    
    text = text.strip()
    
    # 统计不同语言的字符
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars = len([c for c in text if c.isalpha() or '\u4e00' <= c <= '\u9fff'])
    
    if total_chars == 0:
        return 'unknown'
    
    chinese_ratio = chinese_chars / total_chars
    if chinese_ratio > 0.3:  # 如果中文字符超过30%，认为是中文
        return 'zh'
    elif chinese_ratio < 0.1:  # 如果中文字符少于10%，认为是英文
        return 'en'
    else:
        return 'mixed'  # 混合语言


def get_whisper_model():
    """获取 Whisper 模型（懒加载）"""
    global _whisper_model
    
    if _whisper_model is None:
        device = "cuda" if torch.cuda.is_available() and settings.whisper_device == "cuda" else "cpu"
        logger.info(f"加载 Whisper 模型: {settings.whisper_model}, 设备: {device}")
        
        _whisper_model = whisper.load_model(settings.whisper_model, device=device)
        logger.info("Whisper 模型加载完成")
    
    return _whisper_model


def check_memory_usage() -> bool:
    """检查内存使用情况"""
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    if memory_percent > settings.memory_threshold:
        logger.warning(f"内存使用率过高: {memory_percent:.1f}%，阈值: {settings.memory_threshold}%")
        return False
    
    return True


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


def save_transcription_result(task_id: str, stt_result: Dict[str, Any]):
    """保存转录结果"""
    try:
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if task:
                task.accuracy = stt_result.get("accuracy")
                task.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"转录结果保存成功: {task_id}")
            else:
                logger.error(f"任务不存在: {task_id}")
                
    except Exception as e:
        logger.error(f"保存转录结果失败: {e}")


@celery_app.task(bind=True, name='tasks.transcription.transcribe_audio')
def transcribe_audio_task(self, task_id: str, audio_path: str, reference_text: Optional[str] = None):
    """
    音频转录任务
    
    使用 Whisper 模型进行语音转文本，并计算准确性
    """
    try:
        # === 任务开始记录 ===
        logger.task_start(task_id, "audio_transcription", 
                         audio_file=audio_path,
                         has_reference=bool(reference_text))
        
        # === 系统资源检查 ===
        memory_percent = psutil.virtual_memory().percent
        cpu_count = psutil.cpu_count()
        logger.resource_usage(task_id, 
                            memory_percent=f"{memory_percent:.1f}%",
                            cpu_count=cpu_count)
        
        if not check_memory_usage():
            raise Exception(f"内存使用率过高: {memory_percent:.1f}%，暂停处理")
        
        # === 状态更新 ===
        logger.step("TRANSCRIPTION", "更新任务状态", task_id, status="PROCESSING")
        update_task_status(task_id, TaskStatus.TRANSCRIPTION_PROCESSING, {"message": "开始转录"})
        
        # === 模型加载 ===
        logger.step("TRANSCRIPTION", "加载Whisper模型", task_id, 
                   model=settings.whisper_model, device=settings.whisper_device)
        model_start_time = datetime.utcnow()
        model = get_whisper_model()
        model_load_time = (datetime.utcnow() - model_start_time).total_seconds()
        logger.performance(task_id, "whisper_model_load", model_load_time)
        
        # === 音频文件检查 ===
        logger.step("TRANSCRIPTION", "检查音频文件", task_id, file_path=audio_path)
        if not os.path.exists(audio_path):
            logger.transcription_fail(task_id, f"音频文件不存在: {audio_path}")
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 获取音频文件信息
        audio_size = os.path.getsize(audio_path)
        logger.step("TRANSCRIPTION", "音频文件信息", task_id, 
                   size=f"{audio_size}B", path=audio_path)
        
        # === 开始转录 ===
        logger.transcription_start(task_id, audio_path,
                                 language=settings.whisper_language,
                                 fp16=torch.cuda.is_available(),
                                 audio_size=audio_size)
        
        transcription_start_time = datetime.utcnow()
        result = model.transcribe(
            audio_path,
            language=settings.whisper_language,
            fp16=torch.cuda.is_available(),
            verbose=False
        )
        transcription_duration = (datetime.utcnow() - transcription_start_time).total_seconds()
        
        # === 处理转录结果 ===
        stt_text = result["text"].strip()
        confidence = result.get("segments", [{}])[-1].get("avg_logprob", 0.0) if result.get("segments") else 0.0
        confidence = max(0.0, min(1.0, (confidence + 1.0) / 2.0))  # 转换置信度为 0-1 范围
        detected_language = result.get("language", settings.whisper_language)
        
        logger.transcription_complete(task_id, len(stt_text), confidence,
                                    duration=f"{transcription_duration:.2f}s",
                                    detected_language=detected_language,
                                    preview=stt_text[:100] + ("..." if len(stt_text) > 100 else ""))
        logger.performance(task_id, "whisper_transcription", transcription_duration)
        
        # === 准确性校验 ===
        accuracy_score = None
        if reference_text and reference_text.strip():
            logger.step("TRANSCRIPTION", "开始准确性校验", task_id,
                       reference_preview=reference_text.strip()[:50] + ("..." if len(reference_text.strip()) > 50 else ""))
            
            accuracy_start_time = datetime.utcnow()
            distance = levenshtein.distance(stt_text, reference_text.strip())
            max_len = max(len(stt_text), len(reference_text.strip()))
            accuracy_score = 1 - (distance / max_len) if max_len > 0 else 1.0
            accuracy_score = max(0.0, min(1.0, accuracy_score))
            accuracy_duration = (datetime.utcnow() - accuracy_start_time).total_seconds()
            
            logger.step("TRANSCRIPTION", "准确性校验完成", task_id,
                       accuracy=f"{accuracy_score:.3f}",
                       edit_distance=distance,
                       max_length=max_len,
                       duration=f"{accuracy_duration:.3f}s")
            logger.performance(task_id, "accuracy_calculation", accuracy_duration)
        else:
            logger.step("TRANSCRIPTION", "跳过准确性校验", task_id, reason="无参考文本")
        
        # === 保存转录结果 ===
        logger.step("TRANSCRIPTION", "保存转录结果", task_id)
        stt_result = {
            "text": stt_text,
            "confidence": confidence,
            "accuracy": accuracy_score,
            "language": detected_language
        }
        
        save_transcription_result(task_id, stt_result)
        
        # === 获取任务信息和语言检测 ===
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                raise Exception(f"任务不存在: {task_id}")
            
            target_languages = task.languages
            
            # 更新转录结果到数据库
            task.text_content = stt_text
            task.updated_at = datetime.utcnow()
            db.commit()
            
            logger.step("TRANSCRIPTION", "数据库更新完成", task_id, 
                       target_languages=target_languages, 
                       text_saved=True)
        
        # === 语言检测和翻译策略 ===
        detected_language = detect_text_language(stt_text)
        logger.step("TRANSCRIPTION", "语言检测完成", task_id,
                   detected=detected_language,
                   target_languages=target_languages)
        
        # 根据检测结果决定翻译策略
        if detected_language == 'unknown':
            translation_languages = target_languages
            logger.step("TRANSCRIPTION", "翻译策略: 语言未知", task_id, 
                       strategy="translate_all")
        elif detected_language == 'mixed':
            translation_languages = target_languages
            logger.step("TRANSCRIPTION", "翻译策略: 混合语言", task_id, 
                       strategy="translate_all")
        else:
            translation_languages = [lang for lang in target_languages if lang != detected_language]
            logger.step("TRANSCRIPTION", "翻译策略: 过滤相同语言", task_id,
                       strategy="filter_same", 
                       filtered_language=detected_language,
                       remaining_languages=translation_languages)
        
        # === 状态更新 ===
        logger.step("TRANSCRIPTION", "更新状态为完成", task_id)
        update_task_status(task_id, TaskStatus.TRANSCRIPTION_COMPLETED)
        
        logger.step("TRANSCRIPTION", "更新状态为翻译待处理", task_id)
        update_task_status(task_id, TaskStatus.TRANSLATION_PENDING)
        
        # === 处理相同语言的情况 ===
        same_language_targets = [lang for lang in target_languages if lang == detected_language]
        if same_language_targets:
            logger.step("TRANSCRIPTION", "处理相同语言目标", task_id,
                       same_languages=same_language_targets,
                       count=len(same_language_targets))
            
            from src.tasks.translation_task import save_translation_result
            for language in same_language_targets:
                result_data = {
                    "task_id": task_id,
                    "source_text": stt_text,
                    "translated_text": stt_text,
                    "target_language": language,
                    "source_type": SourceType.AUDIO.value,
                    "confidence": 1.0,
                    "engine": "skip_same_language",
                    "timestamp": datetime.utcnow().isoformat()
                }
                save_translation_result(task_id, language, SourceType.AUDIO, result_data)
                logger.translation_skip(task_id, language, "源语言与目标语言相同")
                
                # 如果有参考文本，也保存
                if reference_text and reference_text.strip():
                    ref_result_data = {
                        "task_id": task_id,
                        "source_text": reference_text.strip(),
                        "translated_text": reference_text.strip(),
                        "target_language": language,
                        "source_type": SourceType.TEXT.value,
                        "confidence": 1.0,
                        "engine": "skip_same_language",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    save_translation_result(task_id, language, SourceType.TEXT, ref_result_data)
        
        # === 触发翻译任务 ===
        if translation_languages:
            logger.step("TRANSCRIPTION", "触发翻译任务", task_id,
                       languages_to_translate=translation_languages,
                       has_reference=bool(reference_text))
            
            from src.tasks.translation_task import translate_text_task
            
            # 触发翻译任务 - 转录文本
            audio_translation_count = 0
            for language in translation_languages:
                translate_text_task.delay(task_id, stt_text, language, SourceType.AUDIO.value)
                audio_translation_count += 1
                logger.step("TRANSCRIPTION", "已触发音频文本翻译", task_id, 
                           target_language=language)
            
            # 如果有参考文本，也进行翻译
            text_translation_count = 0
            if reference_text and reference_text.strip():
                for language in translation_languages:
                    translate_text_task.delay(task_id, reference_text.strip(), language, SourceType.TEXT.value)
                    text_translation_count += 1
                    logger.step("TRANSCRIPTION", "已触发参考文本翻译", task_id,
                               target_language=language)
            
            total_translations = audio_translation_count + text_translation_count
            logger.step("TRANSCRIPTION", "翻译任务触发完成", task_id,
                       audio_translations=audio_translation_count,
                       text_translations=text_translation_count,
                       total_translations=total_translations)
        else:
            logger.step("TRANSCRIPTION", "无需翻译", task_id, reason="没有需要翻译的语言")
        
        # === 检查翻译完成情况 ===
        from src.tasks.translation_task import check_all_translations_completed
        logger.step("TRANSCRIPTION", "检查翻译完成状态", task_id)
        check_all_translations_completed(task_id)
        
        # === 任务完成 ===
        logger.task_complete(task_id,
                           transcription_duration=f"{transcription_duration:.2f}s",
                           text_length=len(stt_text),
                           confidence=f"{confidence:.3f}",
                           accuracy=f"{accuracy_score:.3f}" if accuracy_score else "N/A")
        
        return {
            "status": "success", 
            "text": stt_text, 
            "accuracy": accuracy_score,
            "confidence": confidence,
            "detected_language": detected_language
        }
        
    except FileNotFoundError as e:
        error_msg = f"音频文件不存在: {str(e)}"
        logger.transcription_fail(task_id, error_msg)
        update_task_status(task_id, TaskStatus.TRANSCRIPTION_FAILED, {"error": error_msg})
        raise
        
    except Exception as e:
        error_msg = f"转录失败: {str(e)}"
        logger.task_fail(task_id, error_msg, stage="transcription")
        
        update_task_status(task_id, TaskStatus.TRANSCRIPTION_FAILED, {"error": error_msg})
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.step("TRANSCRIPTION", "准备重试", task_id,
                       retry_count=self.request.retries + 1,
                       max_retries=self.max_retries)
            raise self.retry(countdown=60, exc=e)
        
        raise e


def get_task_by_id(task_id: str) -> Optional[Task]:
    """根据任务ID获取任务"""
    try:
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            return task
    except Exception as e:
        logger.error(f"查询任务失败: {e}")
        return None 