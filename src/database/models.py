"""
数据库 ORM 模型定义
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, DateTime, Text, DECIMAL, JSON, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class Task(Base):
    """任务主表"""
    __tablename__ = "tasks"
    
    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(20), nullable=False)  # 'audio' 或 'text'
    status = Column(String(30), nullable=False, default='transcription_pending')
    languages = Column(JSON, nullable=False)  # 目标语言列表
    file_path = Column(Text, nullable=True)  # 文件路径，支持音频文件和txt文件
    text_content = Column(Text, nullable=True)  # 文本内容，音频转录结果或txt文件内容
    reference_text = Column(Text, nullable=True)
    text_number = Column(String(50), nullable=True)  # 文本编号，从原始文件名提取
    accuracy = Column(DECIMAL(5, 4), nullable=True)  # STT 准确性分数
    error_message = Column(Text, nullable=True)
    result_url = Column(Text, nullable=True)  # 腾讯云COS结果文件路径
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    transcription_completed_at = Column(DateTime, nullable=True)  # 转录完成时间
    translation_completed_at = Column(DateTime, nullable=True)   # 翻译完成时间
    completed_at = Column(DateTime, nullable=True)               # 整个任务完成时间（packaging_completed）
    
    # 关联关系
    translation_results = relationship("TranslationResult", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Task(task_id='{self.task_id}', type='{self.task_type}', status='{self.status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": str(self.task_id),
            "task_type": self.task_type,
            "status": self.status,
            "languages": self.languages,
            "file_path": self.file_path,
            "text_content": self.text_content,
            "reference_text": self.reference_text,
            "text_number": self.text_number,
            "accuracy": float(self.accuracy) if self.accuracy else None,
            "error_message": self.error_message,
            "result_url": self.result_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "transcription_completed_at": self.transcription_completed_at.isoformat() if self.transcription_completed_at else None,
            "translation_completed_at": self.translation_completed_at.isoformat() if self.translation_completed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TranslationResult(Base):
    """翻译结果表"""
    __tablename__ = "translation_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    text_number = Column(String(50), nullable=True)  # 文本编号，从文件名提取
    target_language = Column(String(10), nullable=False)
    source_type = Column(String(10), nullable=False)  # 'AUDIO' 或 'TEXT'
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    confidence = Column(DECIMAL(5, 4), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联关系
    task = relationship("Task", back_populates="translation_results")
    
    # 唯一约束：一个任务的同一语言和来源只能有一个翻译结果
    __table_args__ = (
        {"extend_existing": True},
    )
    
    def __repr__(self):
        return f"<TranslationResult(task_id='{self.task_id}', lang='{self.target_language}', source='{self.source_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": str(self.task_id),
            "text_number": self.text_number,
            "target_language": self.target_language,
            "source_type": self.source_type,
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "confidence": float(self.confidence) if self.confidence else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }





class TaskLog(Base):
    """任务日志表 - 记录任务执行过程"""
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)  # 事件类型：created, processing, completed, failed, etc.
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # 详细信息，JSON 格式
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<TaskLog(task_id='{self.task_id}', event='{self.event_type}', time='{self.created_at}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": str(self.task_id),
            "event_type": self.event_type,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        } 