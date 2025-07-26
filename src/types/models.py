"""
VoiceLingua 数据模型定义
"""
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(str, Enum):
    """数据来源类型"""
    AUDIO = "AUDIO"
    TEXT = "TEXT"


class TaskType(str, Enum):
    """任务类型"""
    AUDIO = "audio"
    TEXT = "text"


# API 请求模型
class AudioTaskRequest(BaseModel):
    """音频任务创建请求"""
    languages: List[str] = Field(..., description="目标翻译语言列表", min_items=1)
    reference_text: Optional[str] = Field(None, description="参考文本用于准确性校验")

    class Config:
        json_schema_extra = {
            "example": {
                "languages": ["en", "zh", "ja"],
                "reference_text": "这是参考文本"
            }
        }


class TextTaskRequest(BaseModel):
    """文本任务创建请求"""
    languages: List[str] = Field(..., description="目标翻译语言列表", min_items=1)
    text_content: str = Field(..., description="待翻译的文本内容", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "languages": ["en", "zh-tw", "ja"],
                "text_content": "Hello, this is a test text for translation."
            }
        }


# API 响应模型
class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str
    status: TaskStatus
    created_at: str
    languages: List[str]
    accuracy: Optional[float] = Field(None, description="STT 准确性分数 (0-1)")
    error_message: Optional[str] = None
    result_url: Optional[str] = Field(None, description="结果文件COS路径")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "created_at": "2024-01-01T10:00:00Z",
                "languages": ["en", "zh", "ja"],
                "accuracy": 0.95,
                "result_url": "results/550e8400-e29b-41d4-a716-446655440000.json"
            }
        }


class TranslationResult(BaseModel):
    """翻译结果模型"""
    task_id: str
    language: str
    text_id: str
    source: SourceType
    content: str
    accuracy: Optional[float] = None
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "language": "en",
                "text_id": "text_001",
                "source": "AUDIO",
                "content": "Hello, this is a transcribed text.",
                "accuracy": 0.95,
                "timestamp": "2024-01-01T10:02:15Z"
            }
        }


class BatchQueryRequest(BaseModel):
    """批量查询请求"""
    queries: List[Dict[str, str]] = Field(..., description="查询列表")

    class Config:
        json_schema_extra = {
            "example": {
                "queries": [
                    {"language": "en", "text_id": "text_001", "source": "AUDIO"},
                    {"language": "zh", "text_id": "text_002", "source": "TEXT"}
                ]
            }
        }


# 内部数据模型
class TranscriptionResult(BaseModel):
    """转录结果内部模型"""
    text: str
    confidence: float
    accuracy: Optional[float] = None
    language: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TranslationData(BaseModel):
    """翻译数据内部模型"""
    task_id: str
    source_text: str
    translated_text: str
    target_language: str
    source_type: SourceType
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PackageResultData(BaseModel):
    """打包结果数据模型"""
    task_id: str
    task_type: TaskType
    created_at: str
    completed_at: str
    accuracy: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    translations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    query_index: Dict[str, Any] = Field(default_factory=dict)


# 健康检查模型
class HealthCheck(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    timestamp: str
    version: str
    components: Dict[str, Any] = Field(default_factory=dict)


# 错误响应模型
class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str
    detail: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Task not found",
                "detail": "No task found with ID: 550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        } 