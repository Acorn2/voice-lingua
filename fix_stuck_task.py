#!/usr/bin/env python3
"""
修复卡在 transcription_completed 状态的任务
手动触发翻译任务
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import db_manager
from src.database.models import Task
from src.tasks.translation_task import translate_text_task
from src.types.models import TaskStatus, SourceType
from src.tasks.transcription_task import update_task_status
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_stuck_task(task_id: str):
    """修复卡住的任务"""
    try:
        with db_manager.get_session() as db:
            # 查询任务
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            logger.info(f"找到任务: {task_id}, 状态: {task.status}")
            
            if task.status != 'transcription_completed':
                logger.warning(f"任务状态不是 transcription_completed: {task.status}")
                return False
            
            # 获取转录文本和目标语言
            stt_text = task.text_content
            target_languages = task.languages
            reference_text = task.reference_text
            
            if not stt_text:
                logger.error("转录文本为空")
                return False
            
            logger.info(f"转录文本: {stt_text[:100]}...")
            logger.info(f"目标语言: {target_languages}")
            
            # 使用与翻译任务相同的语言检测逻辑
            from src.tasks.translation_task import detect_text_language
            
            detected_language = detect_text_language(stt_text)
            logger.info(f"检测到语言: {detected_language}")
            
            # 计算需要翻译的语言（排除与检测语言相同的目标语言）
            translation_languages = [lang for lang in target_languages if lang != detected_language]
            
            logger.info(f"需要翻译的语言: {translation_languages}")
            
            if not translation_languages:
                logger.info("无需翻译，任务已完成")
                return True
            
            # 更新任务状态为翻译待处理
            update_task_status(task_id, TaskStatus.TRANSLATION_PENDING)
            logger.info(f"任务状态已更新为: {TaskStatus.TRANSLATION_PENDING.value}")
            
            # 触发翻译任务
            for language in translation_languages:
                logger.info(f"触发翻译任务: {language}")
                translate_text_task.delay(task_id, stt_text, language, SourceType.AUDIO.value)
            
            # 如果有参考文本，也进行翻译
            if reference_text and reference_text.strip():
                for language in translation_languages:
                    logger.info(f"触发参考文本翻译任务: {language}")
                    translate_text_task.delay(task_id, reference_text.strip(), language, SourceType.TEXT.value)
            
            logger.info("翻译任务已触发")
            return True
            
    except Exception as e:
        logger.error(f"修复任务失败: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python fix_stuck_task.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    success = fix_stuck_task(task_id)
    
    if success:
        print(f"任务 {task_id} 修复成功")
    else:
        print(f"任务 {task_id} 修复失败")
        sys.exit(1)