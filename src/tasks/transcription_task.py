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

logger = logging.getLogger(__name__)

# 全局 Whisper 模型缓存
_whisper_model = None


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
                
                if details:
                    if "error" in details:
                        task.error_message = details["error"]
                    if "accuracy" in details:
                        task.accuracy = details["accuracy"]
                    if "result_url" in details:
                        task.result_url = details["result_url"]
                
                db.commit()
                logger.info(f"任务状态更新: {task_id} -> {status.value}")
            else:
                logger.error(f"任务不存在: {task_id}")
                
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")


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
        logger.info(f"开始转录任务: {task_id}")
        
        # 内存检查
        if not check_memory_usage():
            raise Exception(f"内存使用率过高: {psutil.virtual_memory().percent:.1f}%，暂停处理")
        
        # 更新任务状态为处理中
        update_task_status(task_id, TaskStatus.PROCESSING, {"message": "开始转录"})
        
        # 获取 Whisper 模型
        model = get_whisper_model()
        
        # 检查音频文件是否存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 执行转录
        logger.info(f"开始转录音频文件: {audio_path}")
        result = model.transcribe(
            audio_path,
            language=settings.whisper_language,
            fp16=torch.cuda.is_available(),
            verbose=False
        )
        
        stt_text = result["text"].strip()
        confidence = result.get("segments", [{}])[-1].get("avg_logprob", 0.0) if result.get("segments") else 0.0
        
        # 转换置信度为 0-1 范围
        confidence = max(0.0, min(1.0, (confidence + 1.0) / 2.0))
        
        logger.info(f"转录完成，文本长度: {len(stt_text)}, 置信度: {confidence:.3f}")
        
        # 准确性校验
        accuracy_score = None
        if reference_text and reference_text.strip():
            # 使用 Levenshtein 距离计算准确性
            distance = levenshtein.distance(stt_text, reference_text.strip())
            max_len = max(len(stt_text), len(reference_text.strip()))
            accuracy_score = 1 - (distance / max_len) if max_len > 0 else 1.0
            accuracy_score = max(0.0, min(1.0, accuracy_score))
            
            logger.info(f"准确性分数: {accuracy_score:.3f} (距离: {distance}, 最大长度: {max_len})")
        
        # 保存转录结果
        stt_result = {
            "text": stt_text,
            "confidence": confidence,
            "accuracy": accuracy_score,
            "language": result.get("language", settings.whisper_language)
        }
        
        save_transcription_result(task_id, stt_result)
        
        # 获取任务的目标语言
        with db_manager.get_session() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                raise Exception(f"任务不存在: {task_id}")
            
            target_languages = task.languages
            
            # 更新转录结果到数据库
            task.text_content = stt_text
            task.updated_at = datetime.utcnow()
            db.commit()
        
        # 导入翻译任务（避免循环导入）
        from src.tasks.translation_task import translate_text_task
        
        # 计算需要翻译的语言数量（排除源语言）
        translation_languages = [lang for lang in target_languages if lang != settings.whisper_language]
        
        # 如果没有需要翻译的语言，直接标记为完成
        if not translation_languages:
            update_task_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"任务无需翻译，直接完成: {task_id}")
        else:
            # 触发翻译任务 - 转录文本
            for language in translation_languages:
                translate_text_task.delay(task_id, stt_text, language, SourceType.AUDIO.value)
            
            # 如果有参考文本，也进行翻译
            if reference_text and reference_text.strip():
                for language in translation_languages:
                    translate_text_task.delay(task_id, reference_text.strip(), language, SourceType.TEXT.value)
        
        logger.info(f"转录任务完成: {task_id}")
        return {
            "status": "success", 
            "text": stt_text, 
            "accuracy": accuracy_score,
            "confidence": confidence
        }
        
    except FileNotFoundError as e:
        error_msg = f"音频文件不存在: {str(e)}"
        logger.error(f"任务 {task_id} - {error_msg}")
        update_task_status(task_id, TaskStatus.FAILED, {"error": error_msg})
        raise
        
    except Exception as e:
        error_msg = f"转录失败: {str(e)}"
        logger.error(f"任务 {task_id} - {error_msg}")
        
        update_task_status(task_id, TaskStatus.FAILED, {"error": error_msg})
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.info(f"重试转录任务 {task_id} (第 {self.request.retries + 1} 次)")
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