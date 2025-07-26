"""
VoiceLingua 业务日志记录工具

按照项目规范提供结构化的业务级日志记录功能
- 记录任务生命周期事件
- 包含业务上下文和性能指标  
- 支持不同级别的日志输出
- 便于运维监控和问题排查
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

class BusinessLogger:
    """业务级日志记录器"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.task_start_times = {}  # 记录任务开始时间，用于计算耗时
    
    def _format_message(self, 
                       stage: str, 
                       action: str, 
                       task_id: str = None,
                       details: Dict[str, Any] = None) -> str:
        """格式化业务日志消息"""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # 基础消息格式
        message_parts = [f"[{timestamp}]"]
        
        # 添加阶段标识
        stage_emoji = {
            'TRANSCRIPTION': '🎵',
            'TRANSLATION': '🌍', 
            'PACKAGING': '📦',
            'SYSTEM': '⚙️',
            'ERROR': '❌',
            'SUCCESS': '✅'
        }
        emoji = stage_emoji.get(stage, '📋')
        message_parts.append(f"{emoji} [{stage}]")
        
        # 添加任务ID
        if task_id:
            message_parts.append(f"Task:{task_id[:8]}")
        
        # 添加操作描述
        message_parts.append(f"- {action}")
        
        # 添加详细信息
        if details:
            details_str = ", ".join([f"{k}={v}" for k, v in details.items()])
            message_parts.append(f"({details_str})")
        
        return " ".join(message_parts)
    
    def task_start(self, task_id: str, task_type: str, **kwargs):
        """记录任务开始"""
        self.task_start_times[task_id] = time.time()
        details = {"type": task_type, **kwargs}
        message = self._format_message("SYSTEM", "任务开始", task_id, details)
        self.logger.info(message)
    
    def task_complete(self, task_id: str, **kwargs):
        """记录任务完成"""
        duration = self._get_task_duration(task_id)
        details = {"duration": f"{duration:.2f}s", **kwargs}
        message = self._format_message("SUCCESS", "任务完成", task_id, details)
        self.logger.info(message)
        # 清理开始时间记录
        self.task_start_times.pop(task_id, None)
    
    def task_fail(self, task_id: str, error: str, **kwargs):
        """记录任务失败"""
        duration = self._get_task_duration(task_id)
        details = {"duration": f"{duration:.2f}s", "error": error, **kwargs}
        message = self._format_message("ERROR", "任务失败", task_id, details)
        self.logger.error(message)
        # 清理开始时间记录
        self.task_start_times.pop(task_id, None)
    
    def transcription_start(self, task_id: str, audio_file: str, **kwargs):
        """记录转录开始"""
        details = {"audio": audio_file, **kwargs}
        message = self._format_message("TRANSCRIPTION", "开始音频转录", task_id, details)
        self.logger.info(message)
    
    def transcription_complete(self, task_id: str, text_length: int, confidence: float, **kwargs):
        """记录转录完成"""
        details = {"text_length": text_length, "confidence": f"{confidence:.3f}", **kwargs}
        message = self._format_message("TRANSCRIPTION", "转录完成", task_id, details)
        self.logger.info(message)
    
    def transcription_fail(self, task_id: str, error: str, **kwargs):
        """记录转录失败"""
        details = {"error": error, **kwargs}
        message = self._format_message("TRANSCRIPTION", "转录失败", task_id, details)
        self.logger.error(message)
    
    def translation_start(self, task_id: str, source_lang: str, target_lang: str, **kwargs):
        """记录翻译开始"""
        details = {"from": source_lang, "to": target_lang, **kwargs}
        message = self._format_message("TRANSLATION", "开始文本翻译", task_id, details)
        self.logger.info(message)
    
    def translation_complete(self, task_id: str, source_lang: str, target_lang: str, 
                           engine: str, confidence: float, **kwargs):
        """记录翻译完成"""
        details = {"from": source_lang, "to": target_lang, "engine": engine, 
                  "confidence": f"{confidence:.3f}", **kwargs}
        message = self._format_message("TRANSLATION", "翻译完成", task_id, details)
        self.logger.info(message)
    
    def translation_skip(self, task_id: str, language: str, reason: str, **kwargs):
        """记录翻译跳过"""
        details = {"language": language, "reason": reason, **kwargs}
        message = self._format_message("TRANSLATION", "跳过翻译", task_id, details)
        self.logger.info(message)
    
    def translation_fail(self, task_id: str, source_lang: str, target_lang: str, 
                        error: str, **kwargs):
        """记录翻译失败"""
        details = {"from": source_lang, "to": target_lang, "error": error, **kwargs}
        message = self._format_message("TRANSLATION", "翻译失败", task_id, details)
        self.logger.error(message)
    
    def packaging_start(self, task_id: str, translations_count: int, **kwargs):
        """记录打包开始"""
        details = {"translations": translations_count, **kwargs}
        message = self._format_message("PACKAGING", "开始结果打包", task_id, details)
        self.logger.info(message)
    
    def packaging_complete(self, task_id: str, result_url: str, file_size: int = None, **kwargs):
        """记录打包完成"""
        details = {"result_url": result_url, **kwargs}
        if file_size:
            details["size"] = f"{file_size}B"
        message = self._format_message("PACKAGING", "打包完成", task_id, details)
        self.logger.info(message)
    
    def packaging_fail(self, task_id: str, error: str, **kwargs):
        """记录打包失败"""
        details = {"error": error, **kwargs}
        message = self._format_message("PACKAGING", "打包失败", task_id, details)
        self.logger.error(message)
    
    def step(self, stage: str, action: str, task_id: str = None, **kwargs):
        """记录通用业务步骤"""
        message = self._format_message(stage, action, task_id, kwargs)
        self.logger.info(message)
    
    def performance(self, task_id: str, operation: str, duration: float, **kwargs):
        """记录性能指标"""
        details = {"operation": operation, "duration": f"{duration:.3f}s", **kwargs}
        message = self._format_message("SYSTEM", "性能指标", task_id, details)
        self.logger.info(message)
    
    def resource_usage(self, task_id: str = None, **kwargs):
        """记录资源使用情况"""
        message = self._format_message("SYSTEM", "资源使用", task_id, kwargs)
        self.logger.info(message)
    
    def _get_task_duration(self, task_id: str) -> float:
        """获取任务执行时长"""
        start_time = self.task_start_times.get(task_id)
        if start_time:
            return time.time() - start_time
        return 0.0
    
    # === 兼容性方法（支持传统的logger接口） ===
    def info(self, message: str):
        """兼容性方法：标准 info 日志"""
        self.logger.info(message)
    
    def error(self, message: str):
        """兼容性方法：标准 error 日志"""
        self.logger.error(message)
    
    def warning(self, message: str):
        """兼容性方法：标准 warning 日志"""
        self.logger.warning(message)
    
    def debug(self, message: str):
        """兼容性方法：标准 debug 日志"""
        self.logger.debug(message)


def get_business_logger(name: str) -> BusinessLogger:
    """获取业务日志记录器实例"""
    return BusinessLogger(name)


def log_task_lifecycle(stage: str):
    """任务生命周期日志装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, task_id: str, *args, **kwargs):
            logger = get_business_logger(func.__module__)
            
            try:
                # 记录任务开始
                func_name = func.__name__
                logger.step(stage, f"开始执行 {func_name}", task_id)
                
                start_time = time.time()
                result = func(self, task_id, *args, **kwargs)
                duration = time.time() - start_time
                
                # 记录任务完成
                logger.step(stage, f"完成执行 {func_name}", task_id, duration=f"{duration:.2f}s")
                logger.performance(task_id, func_name, duration)
                
                return result
                
            except Exception as e:
                # 记录任务失败
                duration = time.time() - start_time if 'start_time' in locals() else 0
                logger.step("ERROR", f"执行失败 {func_name}", task_id, 
                          error=str(e), duration=f"{duration:.2f}s")
                raise
                
        return wrapper
    return decorator


def setup_business_logging():
    """设置业务日志配置"""
    
    # 禁用 SQLAlchemy 的详细日志
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
    
    # 配置业务日志格式 - 简化格式，因为我们自己格式化消息
    formatter = logging.Formatter('%(message)s')
    
    # 为每个业务模块设置独立的日志处理器
    modules = [
        'src.tasks.transcription_task',
        'src.tasks.translation_task', 
        'src.tasks.packaging_task'
    ]
    
    for module in modules:
        logger = logging.getLogger(module)
        logger.setLevel(logging.INFO)
        
        # 清除现有处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 确保不传播到父 logger（避免重复日志）
        logger.propagate = False 