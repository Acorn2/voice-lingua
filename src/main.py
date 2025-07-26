"""
VoiceLingua FastAPI 主应用
"""
import os
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import aiofiles

from src.config.settings import settings
from src.types.models import (
    TaskResponse, TextTaskRequest, TranslationResult, 
    HealthCheck, ErrorResponse, TaskStatus, SourceType
)
from src.database.connection import get_db, create_tables, db_manager
from src.database.models import Task, TranslationResult as DBTranslationResult
from src.tasks.transcription_task import transcribe_audio_task
from src.tasks.translation_task import translate_text_task, get_translation_engine_status

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file, mode='w', encoding='utf-8'),  # 使用 'w' 模式重写文件
        logging.StreamHandler()
    ]
)

# 减少 SQLAlchemy 日志的详细程度
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("VoiceLingua API 启动中...")
    
    # 创建必要的目录
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 创建数据库表
    try:
        create_tables()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
    
    # 测试数据库连接
    if not db_manager.test_connection():
        logger.error("数据库连接测试失败")
        raise Exception("数据库连接失败")
    
    logger.info("VoiceLingua API 启动完成")
    
    yield
    
    # 关闭时执行
    logger.info("VoiceLingua API 关闭中...")
    db_manager.close_connection()
    logger.info("VoiceLingua API 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="VoiceLingua API",
    description="高性能语音转录与多语言翻译系统",
    version=settings.app_version,
    lifespan=lifespan
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def save_uploaded_file(upload_file: UploadFile, task_id: str) -> str:
    """保存上传的文件"""
    try:
        # 检查文件格式
        file_extension = os.path.splitext(upload_file.filename or "")[1].lower()
        if file_extension not in settings.supported_audio_formats:
            raise ValueError(f"不支持的文件格式: {file_extension}")
        
        # 生成文件名
        filename = f"{task_id}{file_extension}"
        file_path = os.path.join("uploads", filename)
        
        # 检查文件大小
        content = await upload_file.read()
        if len(content) > settings.max_upload_size:
            raise ValueError(f"文件大小超过限制: {len(content)} > {settings.max_upload_size}")
        
        # 保存文件
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"文件保存成功: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        raise


def create_task_record(
    task_id: str,
    task_type: str,
    languages: List[str],
    audio_file: Optional[str] = None,
    text_content: Optional[str] = None,
    reference_text: Optional[str] = None,
    db: Session = None
) -> Task:
    """创建任务记录"""
    try:
        if db is None:
            db = db_manager.get_session()
            should_close = True
        else:
            should_close = False
        
        # 根据任务类型设置初始状态
        if task_type == "audio":
            initial_status = TaskStatus.TRANSCRIPTION_PENDING.value
        elif task_type == "text":
            initial_status = TaskStatus.TRANSLATION_PENDING.value
        else:
            initial_status = TaskStatus.TRANSCRIPTION_PENDING.value  # 默认状态
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=initial_status,
            languages=languages,
            audio_file_path=audio_file,
            text_content=text_content,
            reference_text=reference_text,
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        logger.info(f"任务记录创建成功: {task_id}")
        
        if should_close:
            db.close()
        
        return task
        
    except Exception as e:
        if should_close:
            db.close()
        logger.error(f"创建任务记录失败: {e}")
        raise


# API 路由定义
@app.post("/api/v1/tasks/audio", response_model=TaskResponse)
async def create_audio_task(
    audio_file: UploadFile = File(..., description="音频文件 (MP3/WAV)"),
    reference_text: Optional[str] = Form(None, description="参考文本"),
    db: Session = Depends(get_db)
):
    """
    创建音频转录与翻译任务
    
    支持的音频格式：MP3, WAV, M4A, FLAC
    自动翻译为所有支持的语言：en, zh, zh-tw, ja, ko, fr, de, es, it, ru
    """
    try:
        # 验证音频文件格式
        if not audio_file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        file_extension = os.path.splitext(audio_file.filename)[1].lower()
        if file_extension not in settings.supported_audio_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的音频格式: {file_extension}。支持的格式: {', '.join(settings.supported_audio_formats)}"
            )
        
        # 使用配置中的所有支持语言作为目标语言
        target_languages = settings.get_supported_languages()
        logger.info(f"使用配置的目标语言: {target_languages}")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 保存文件到本地
        audio_path = await save_uploaded_file(audio_file, task_id)
        
        # 创建任务记录
        task = create_task_record(
            task_id=task_id,
            task_type="audio",
            languages=target_languages,
            audio_file=audio_path,
            reference_text=reference_text,
            db=db
        )
        
        # 异步触发转录任务
        transcribe_audio_task.delay(task_id, audio_path, reference_text)
        
        logger.info(f"音频任务创建成功: {task_id}")
        
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.TRANSCRIPTION_PENDING,
            created_at=task.created_at.isoformat(),
            languages=target_languages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建音频任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"任务创建失败: {str(e)}")


@app.post("/api/v1/tasks/text", response_model=TaskResponse)
async def create_text_task(
    request: TextTaskRequest,
    db: Session = Depends(get_db)
):
    """
    创建文本翻译任务
    
    自动翻译为所有支持的语言：en, zh, zh-tw, ja, ko, fr, de, es, it, ru
    """
    try:
        # 使用配置中的所有支持语言作为目标语言
        target_languages = settings.get_supported_languages()
        logger.info(f"使用配置的目标语言: {target_languages}")
        
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = create_task_record(
            task_id=task_id,
            task_type="text",
            languages=target_languages,
            text_content=request.text_content,
            db=db
        )
        
        # 异步触发翻译任务
        for language in target_languages:
            translate_text_task.delay(task_id, request.text_content, language, SourceType.TEXT.value)
        
        logger.info(f"文本任务创建成功: {task_id}")
        
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.TRANSLATION_PENDING,
            created_at=task.created_at.isoformat(),
            languages=target_languages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建文本任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"任务创建失败: {str(e)}")


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    查询任务状态和结果
    """
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return TaskResponse(
            task_id=str(task.task_id),
            status=TaskStatus(task.status),
            created_at=task.created_at.isoformat(),
            languages=task.languages,
            accuracy=float(task.accuracy) if task.accuracy else None,
            error_message=task.error_message,
            result_url=task.result_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """
    取消任务
    """
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 检查任务是否已完成或失败，无法取消
        completed_statuses = [
            TaskStatus.TRANSCRIPTION_COMPLETED.value,
            TaskStatus.TRANSLATION_COMPLETED.value,
            TaskStatus.PACKAGING_COMPLETED.value,
            TaskStatus.TRANSCRIPTION_FAILED.value,
            TaskStatus.TRANSLATION_FAILED.value,
            TaskStatus.PACKAGING_FAILED.value
        ]
        
        if task.status in completed_statuses:
            raise HTTPException(status_code=400, detail="任务已完成或失败，无法取消")
        
        # 根据当前状态设置相应的取消状态
        if task.status.startswith("translation"):
            task.status = TaskStatus.TRANSLATION_CANCELLED.value
        else:
            # 对于转录和打包阶段，使用翻译取消状态作为通用取消状态
            task.status = TaskStatus.TRANSLATION_CANCELLED.value
        task.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"任务已取消: {task_id}")
        return {"message": "任务已成功取消", "task_id": task_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")


@app.get("/api/v1/translations/{language}/{text_id}/{source}", response_model=TranslationResult)
async def get_translation(
    language: str, 
    text_id: str, 
    source: str,
    db: Session = Depends(get_db)
):
    """
    按语言、文本编号和来源查询翻译结果
    
    这是系统要求的核心查询接口：通过 语言 -> 文本编号 -> 文本来源 快速查询
    """
    try:
        # 验证来源类型
        try:
            source_type = SourceType(source)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的来源类型: {source}")
        
        # 这里简化实现，实际应该根据 text_id 查询对应的任务
        # 暂时使用 task_id 作为 text_id 的映射
        translation = db.query(DBTranslationResult).filter(
            DBTranslationResult.task_id == text_id,
            DBTranslationResult.target_language == language,
            DBTranslationResult.source_type == source
        ).first()
        
        if not translation:
            raise HTTPException(status_code=404, detail="翻译结果不存在")
        
        return TranslationResult(
            task_id=str(translation.task_id),
            language=translation.target_language,
            text_id=text_id,
            source=SourceType(translation.source_type),
            content=translation.translated_text,
            accuracy=float(translation.confidence) if translation.confidence else None,
            timestamp=translation.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询翻译失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/v1/translation/engine/status")
async def get_translation_engine_status_api():
    """
    获取翻译引擎状态
    """
    try:
        status = get_translation_engine_status()
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"获取翻译引擎状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@app.get("/api/v1/health", response_model=HealthCheck)
async def health_check():
    """
    健康检查接口
    """
    components = {}
    
    # 检查数据库连接
    try:
        if db_manager.test_connection():
            components["database"] = "healthy"
        else:
            components["database"] = "unhealthy"
    except Exception:
        components["database"] = "unhealthy"
    
    # 检查存储服务（简化检查）
    components["storage"] = "healthy"  # 实际应该测试 COS 连接

    # 检查翻译引擎状态
    try:
        engine_status = get_translation_engine_status()
        components["translation_engine"] = engine_status
    except Exception as e:
        components["translation_engine"] = {"status": "unhealthy", "error": str(e)}
    
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.app_version,
        components=components
    )


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc) if settings.debug else "服务器内部错误"
        ).dict()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    ) 