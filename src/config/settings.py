"""
VoiceLingua 项目配置文件
"""
import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from enum import Enum


class TranslationEngine(str, Enum):
    """翻译引擎类型"""
    LOCAL = "local"     # 仅使用本地模型
    QWEN = "qwen"       # 仅使用千问大模型
    MIXED = "mixed"     # 混合模式，优先本地模型


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
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
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
    translation_engine: TranslationEngine = Field(default=TranslationEngine.MIXED, env="TRANSLATION_ENGINE")
    max_translation_length: int = Field(default=512, env="MAX_TRANSLATION_LENGTH")
    translation_timeout: int = Field(default=30, env="TRANSLATION_TIMEOUT")
    translation_retry_count: int = Field(default=3, env="TRANSLATION_RETRY_COUNT")
    
    # 千问大模型配置
    qwen_model: str = Field(default="qwen-plus", env="QWEN_MODEL")
    qwen_api_key: Optional[str] = Field(default=None, env="QWEN_API_KEY")
    qwen_api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", env="QWEN_API_BASE")
    
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
    allowed_hosts: str = Field(default="localhost,127.0.0.1", env="ALLOWED_HOSTS")
    cors_origins: str = Field(default="http://localhost:3000", env="CORS_ORIGINS")
    
    # 支持的语言
    supported_languages: str = Field(
        default="en,zh,zh-tw,ja,ko,fr,de,es,it,ru",
        env="SUPPORTED_LANGUAGES"
    )
    
    # 支持的音频格式
    supported_audio_formats: str = Field(
        default=".mp3,.wav,.m4a,.flac",
        env="SUPPORTED_AUDIO_FORMATS"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_redis_url(self) -> str:
        """获取带密码的Redis URL"""
        # 如果 URL 中已经包含认证信息，直接返回
        if "@" in self.redis_url:
            return self.redis_url
        
        # 如果有单独的密码配置，则添加到URL中
        if self.redis_password and self.redis_password.strip():
            if "://" in self.redis_url:
                protocol, rest = self.redis_url.split("://", 1)
                return f"{protocol}://:{self.redis_password}@{rest}"
        
        return self.redis_url
    
    def get_celery_broker_url(self) -> str:
        """获取带密码的Celery Broker URL"""
        # 如果 URL 中已经包含认证信息，直接返回
        if "@" in self.celery_broker_url:
            return self.celery_broker_url
        
        # 如果有单独的密码配置，则添加到URL中
        if self.redis_password and self.redis_password.strip():
            if "://" in self.celery_broker_url:
                protocol, rest = self.celery_broker_url.split("://", 1)
                return f"{protocol}://:{self.redis_password}@{rest}"
        
        return self.celery_broker_url
    
    def get_celery_result_backend(self) -> str:
        """获取带密码的Celery Result Backend URL"""
        # 如果 URL 中已经包含认证信息，直接返回
        if "@" in self.celery_result_backend:
            return self.celery_result_backend
        
        # 如果有单独的密码配置，则添加到URL中
        if self.redis_password and self.redis_password.strip():
            if "://" in self.celery_result_backend:
                protocol, rest = self.celery_result_backend.split("://", 1)
                return f"{protocol}://:{self.redis_password}@{rest}"
        
        return self.celery_result_backend
    
    def get_allowed_hosts(self) -> List[str]:
        """获取允许的主机列表"""
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
    
    def get_cors_origins(self) -> List[str]:
        """获取CORS源列表"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return [lang.strip() for lang in self.supported_languages.split(",") if lang.strip()]
    
    def get_supported_audio_formats(self) -> List[str]:
        """获取支持的音频格式列表"""
        return [fmt.strip() for fmt in self.supported_audio_formats.split(",") if fmt.strip()]


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
    "broker_url": settings.get_celery_broker_url(),
    "result_backend": settings.get_celery_result_backend(),
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 30 * 60,  # 30分钟超时
    "task_soft_time_limit": 25 * 60,  # 25分钟软超时
    "worker_prefetch_multiplier": 4,  # 提升任务预取数量
    "task_acks_late": True,
    "worker_disable_rate_limits": True,
    # 高性能优化配置
    "task_compression": "gzip",  # 启用任务压缩
    "result_compression": "gzip",  # 启用结果压缩
    "worker_max_tasks_per_child": 100,  # 防止内存泄露
    "task_default_retry_delay": 60,
    "task_max_retries": 3,
    # 解决 macOS fork 冲突问题
    "worker_pool": "threads",  # 使用线程池而不是进程池
    "worker_pool_restarts": True,
    "task_routes": {
        "tasks.transcription.*": {"queue": "transcription"},
        "tasks.translation.*": {"queue": "translation"},
        "tasks.packaging.*": {"queue": "packaging"},
    }
} 