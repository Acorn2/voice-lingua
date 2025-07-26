"""
VoiceLingua 项目配置文件
"""
import os
from typing import List, Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    app_name: str = "VoiceLingua"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: str = Field(..., env="SECRET_KEY")
    
    # 数据库配置
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Redis 配置
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", env="CELERY_RESULT_BACKEND")
    
    # 腾讯云COS配置
    tencent_secret_id: str = Field(..., env="TENCENT_SECRET_ID")
    tencent_secret_key: str = Field(..., env="TENCENT_SECRET_KEY")
    tencent_cos_region: str = Field(default="ap-beijing", env="TENCENT_COS_REGION")
    cos_bucket_name: str = Field(..., env="COS_BUCKET_NAME")
    
    # Whisper 配置
    whisper_model: str = Field(default="medium", env="WHISPER_MODEL")
    whisper_device: str = Field(default="cuda", env="WHISPER_DEVICE")
    whisper_language: str = Field(default="zh", env="WHISPER_LANGUAGE")
    
    # 翻译配置
    translation_model: str = Field(default="facebook/m2m100_418M", env="TRANSLATION_MODEL")
    max_translation_length: int = Field(default=512, env="MAX_TRANSLATION_LENGTH")
    
    # 系统限制
    max_upload_size: int = Field(default=100 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 100MB
    max_concurrent_tasks: int = Field(default=10, env="MAX_CONCURRENT_TASKS")
    memory_threshold: float = Field(default=80.0, env="MEMORY_THRESHOLD")
    cpu_threshold: float = Field(default=90.0, env="CPU_THRESHOLD")
    
    # 监控配置
    prometheus_port: int = Field(default=8001, env="PROMETHEUS_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/voicelingua.log", env="LOG_FILE")
    
    # 安全配置
    allowed_hosts: List[str] = Field(default=["localhost", "127.0.0.1"], env="ALLOWED_HOSTS")
    cors_origins: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    
    # 支持的语言
    supported_languages: List[str] = Field(
        default=["en", "zh", "zh-tw", "ja", "ko", "fr", "de", "es", "it", "ru"],
        env="SUPPORTED_LANGUAGES"
    )
    
    # 支持的音频格式
    supported_audio_formats: List[str] = Field(
        default=[".mp3", ".wav", ".m4a", ".flac"],
        env="SUPPORTED_AUDIO_FORMATS"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()


# 语言映射配置
LANGUAGE_MAPPING = {
    "en": "en",
    "zh": "zh",
    "zh-tw": "zh_TW", 
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "it": "it",
    "ru": "ru"
}

# Celery 配置
CELERY_CONFIG = {
    "broker_url": settings.celery_broker_url,
    "result_backend": settings.celery_result_backend,
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 30 * 60,  # 30分钟超时
    "task_soft_time_limit": 25 * 60,  # 25分钟软超时
    "worker_prefetch_multiplier": 1,
    "task_acks_late": True,
    "worker_disable_rate_limits": True,
    "task_default_retry_delay": 60,
    "task_max_retries": 3,
    "task_routes": {
        "tasks.transcription.*": {"queue": "transcription"},
        "tasks.translation.*": {"queue": "translation"},
        "tasks.packaging.*": {"queue": "packaging"},
    }
} 