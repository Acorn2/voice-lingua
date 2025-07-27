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
from src.utils.compact_encoder import CompactTranslationEncoder, UltraCompactEncoder

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file, mode='w', encoding='utf-8'),  # 使用 'w' 模式重写文件
        logging.StreamHandler()
    ]
)

# 彻底减少 SQLAlchemy 日志的详细程度
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
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
    file_path: Optional[str] = None,
    text_content: Optional[str] = None,
    reference_text: Optional[str] = None,
    text_number: Optional[str] = None,
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
            file_path=file_path,
            text_content=text_content,
            reference_text=reference_text,
            text_number=text_number,
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
        
        # 在文件重命名前提取文本编号
        from src.utils.text_number_extractor import extract_text_number_from_filename
        text_number = extract_text_number_from_filename(audio_file.filename)
        if not text_number:
            text_number = f"audio_{int(datetime.utcnow().timestamp())}"
        
        logger.info(f"从音频文件 {audio_file.filename} 提取文本编号: {text_number}")
        
        # 保存文件到本地
        audio_path = await save_uploaded_file(audio_file, task_id)
        
        # 创建任务记录
        task = create_task_record(
            task_id=task_id,
            task_type="audio",
            languages=target_languages,
            file_path=audio_path,
            reference_text=reference_text,
            text_number=text_number,
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
    创建文本翻译任务（JSON方式）
    
    自动翻译为所有支持的语言：en, zh, zh-tw, ja, ko, fr, de, es, it, ru
    """
    try:
        # 使用配置中的所有支持语言作为目标语言
        target_languages = settings.get_supported_languages()
        logger.info(f"使用配置的目标语言: {target_languages}")
        
        task_id = str(uuid.uuid4())
        
        # 为直接传入的文本生成一个简单的编号
        text_number = f"text_{int(datetime.utcnow().timestamp())}"
        
        # 创建任务记录
        task = create_task_record(
            task_id=task_id,
            task_type="text",
            languages=target_languages,
            text_content=request.text_content,
            text_number=text_number,
            db=db
        )
        
        # 异步触发线程池批量翻译任务（高性能多线程优化）
        from src.tasks.translation_task import batch_translate_threaded_task
        batch_translate_threaded_task.delay(task_id, request.text_content, target_languages, SourceType.TEXT.value)
        
        logger.info(f"文本任务创建成功: {task_id}, 文本编号: {text_number}, 文本长度: {len(request.text_content)}")
        
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


@app.post("/api/v1/tasks/text/upload", response_model=TaskResponse)
async def create_text_task_with_file(
    text_content: Optional[str] = Form(None, description="直接传入的文本内容"),
    text_file: Optional[UploadFile] = File(None, description="上传的文本文件 (.txt)"),
    db: Session = Depends(get_db)
):
    """
    创建文本翻译任务（支持文件上传）
    
    支持两种方式：
    1. 直接传入文本内容 (text_content)
    2. 上传文本文件 (text_file, 支持 .txt 格式)
    
    自动翻译为所有支持的语言：en, zh, zh-tw, ja, ko, fr, de, es, it, ru
    """
    """
    创建文本翻译任务
    
    支持两种方式：
    1. 直接传入文本内容 (text_content)
    2. 上传文本文件 (text_file, 支持 .txt 格式)
    
    自动翻译为所有支持的语言：en, zh, zh-tw, ja, ko, fr, de, es, it, ru
    """
    try:
        # 验证输入参数
        if not text_content and not text_file:
            raise HTTPException(
                status_code=400, 
                detail="必须提供 text_content 或 text_file 其中之一"
            )
        
        if text_content and text_file:
            raise HTTPException(
                status_code=400, 
                detail="不能同时提供 text_content 和 text_file，请选择其中一种方式"
            )
        
        # 处理文本内容
        final_text_content = ""
        text_number = None
        
        if text_content:
            # 直接使用传入的文本内容
            final_text_content = text_content.strip()
            if not final_text_content:
                raise HTTPException(status_code=400, detail="文本内容不能为空")
            
            # 为直接传入的文本生成一个简单的编号
            text_number = f"text_{int(datetime.utcnow().timestamp())}"
            
        elif text_file:
            # 验证文件类型
            if not text_file.filename.lower().endswith('.txt'):
                raise HTTPException(
                    status_code=400, 
                    detail="只支持 .txt 格式的文本文件"
                )
            
            # 验证文件大小 (限制为 10MB)
            if text_file.size and text_file.size > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400, 
                    detail="文件大小不能超过 10MB"
                )
            
            # 读取文件内容
            try:
                content = await text_file.read()
                # 尝试不同的编码方式
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                    try:
                        final_text_content = content.decode(encoding).strip()
                        logger.info(f"成功使用 {encoding} 编码读取文件: {text_file.filename}")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail="无法解码文件内容，请确保文件是有效的文本文件"
                    )
                
                if not final_text_content:
                    raise HTTPException(status_code=400, detail="文件内容不能为空")
                
                # 从文件名提取文本编号
                from src.utils.text_number_extractor import extract_text_number_from_filename
                text_number = extract_text_number_from_filename(text_file.filename)
                if not text_number:
                    text_number = f"file_{int(datetime.utcnow().timestamp())}"
                
                logger.info(f"从文件 {text_file.filename} 提取文本编号: {text_number}")
                
            except Exception as e:
                logger.error(f"读取文件失败: {str(e)}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"读取文件失败: {str(e)}"
                )
        
        # 使用配置中的所有支持语言作为目标语言
        target_languages = settings.get_supported_languages()
        logger.info(f"使用配置的目标语言: {target_languages}")
        
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = create_task_record(
            task_id=task_id,
            task_type="text",
            languages=target_languages,
            text_content=final_text_content,
            text_number=text_number,
            db=db
        )
        
        # 异步触发线程池批量翻译任务（高性能多线程优化）
        from src.tasks.translation_task import batch_translate_threaded_task
        batch_translate_threaded_task.delay(task_id, final_text_content, target_languages, SourceType.TEXT.value)
        
        logger.info(f"文本任务创建成功: {task_id}, 文本编号: {text_number}, 文本长度: {len(final_text_content)}")
        
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


@app.get("/api/v1/translations/{language}/{text_number}/{source}", response_model=TranslationResult)
async def get_translation_by_text_number(
    language: str, 
    text_number: str, 
    source: str,
    db: Session = Depends(get_db)
):
    """
    按语言、文本编号和来源查询翻译结果
    
    这是系统要求的核心查询接口：通过 语言 -> 文本编号 -> 文本来源 快速查询
    文本编号从上传的文件名中提取（如：1.mp3 -> "1", text_123.txt -> "123"）
    
    Args:
        language: 目标语言 (如: en, zh, ja)
        text_number: 文本编号 (从文件名提取)
        source: 来源类型 (AUDIO 或 TEXT)
    
    Returns:
        TranslationResult: 翻译结果
    """
    try:
        # 验证来源类型
        try:
            source_type = SourceType(source)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的来源类型: {source}")
        
        # 直接从 TranslationResult 表查询，使用新增的 text_number 字段
        translation = db.query(DBTranslationResult).filter(
            DBTranslationResult.text_number == text_number,
            DBTranslationResult.target_language == language,
            DBTranslationResult.source_type == source
        ).first()
        
        if not translation:
            raise HTTPException(
                status_code=404, 
                detail=f"未找到文本编号 '{text_number}' 在语言 '{language}' 来源 '{source}' 的翻译结果"
            )
        
        return TranslationResult(
            task_id=str(translation.task_id),
            language=translation.target_language,
            text_id=translation.text_number,
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


@app.post("/api/v1/translations/batch", response_model=List[TranslationResult])
async def batch_get_translations(
    queries: List[dict],
    db: Session = Depends(get_db)
):
    """
    批量查询翻译结果
    
    Args:
        queries: 查询列表，每个查询包含 language, text_number, source
        
    Example:
        [
            {"language": "en", "text_number": "1", "source": "AUDIO"},
            {"language": "zh", "text_number": "2", "source": "TEXT"}
        ]
    
    Returns:
        List[TranslationResult]: 翻译结果列表
    """
    try:
        results = []
        
        for query in queries:
            # 验证查询参数
            if not all(key in query for key in ["language", "text_number", "source"]):
                continue
            
            language = query["language"]
            text_number = query["text_number"]
            source = query["source"]
            
            # 验证来源类型
            try:
                source_type = SourceType(source)
            except ValueError:
                continue
            
            # 查询翻译结果
            translation = db.query(DBTranslationResult).filter(
                DBTranslationResult.text_number == text_number,
                DBTranslationResult.target_language == language,
                DBTranslationResult.source_type == source
            ).first()
            
            if translation:
                results.append(TranslationResult(
                    task_id=str(translation.task_id),
                    language=translation.target_language,
                    text_id=translation.text_number,
                    source=SourceType(translation.source_type),
                    content=translation.translated_text,
                    accuracy=float(translation.confidence) if translation.confidence else None,
                    timestamp=translation.created_at.isoformat()
                ))
        
        return results
        
    except Exception as e:
        logger.error(f"批量查询翻译失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量查询失败: {str(e)}")


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
@app.get("/api/v1/encoding/demo", summary="编码格式演示")
async def encoding_demo():
    """
    紧凑编码格式演示
    
    展示原始格式 vs 各种紧凑编码格式的对比
    """
    # 创建演示数据
    demo_data = {
        "task_id": "demo-12345678",
        "task_type": "audio",
        "status": "completed",
        "created_at": "2025-07-26T12:02:29.804574",
        "completed_at": "2025-07-26T12:06:50.169316",
        "source_language": "en",
        "target_languages": ["en", "zh", "zh-tw", "ja", "ko", "fr", "de", "es", "it", "ru"],
        "transcription": {
            "text": "Hello world! This is a demonstration of our compact encoding system for multilingual translation results.",
            "accuracy": 0.95,
            "language": "en"
        },
        "translations": {
            "zh": {
                "audio_text": {
                    "text": "你好世界！这是我们多语言翻译结果紧凑编码系统的演示。",
                    "source_text": "Hello world! This is a demonstration of our compact encoding system for multilingual translation results.",
                    "confidence": 0.9,
                    "source_type": "AUDIO",
                    "created_at": "2025-07-26T12:03:28.910854"
                }
            },
            "ja": {
                "audio_text": {
                    "text": "こんにちは世界！これは私たちの多言語翻訳結果のコンパクトエンコーディングシステムのデモンストレーションです。",
                    "source_text": "Hello world! This is a demonstration of our compact encoding system for multilingual translation results.",
                    "confidence": 0.95,
                    "source_type": "AUDIO",
                    "created_at": "2025-07-26T12:03:33.719359"
                }
            }
        }
    }
    
    # 获取压缩统计
    stats = CompactTranslationEncoder.get_compression_stats(demo_data)
    
    return JSONResponse(content={
        "demo_title": "VoiceLingua 紧凑编码演示",
        "original_format": {
            "description": "传统JSON格式（冗长且重复）",
            "size": stats["original_size"],
            "sample": {
                "translations": {
                    "zh": {
                        "audio_text": {
                            "text": "你好世界！",
                            "source_text": "Hello world! This is...",  # 每个翻译都重复存储！
                            "confidence": 0.9,
                            "source_type": "AUDIO",
                            "created_at": "2025-07-26T12:03:28.910854"  # 冗余时间戳！
                        }
                    }
                }
            }
        },
        "compact_format": {
            "description": "紧凑JSON格式（简洁高效）",
            "size": stats["compact_json_size"],
            "compression_ratio": stats["compression_ratios"]["compact_json"],
            "space_saved": stats["size_reduction"]["compact_json"],
            "sample": {
                "v": "1.0",
                "src": "en",
                "txt": "Hello world! This is...",  # 只存储一次！
                "langs": [
                    [1, "你好世界！", 90, 1],  # [语言代码, 翻译, 置信度%, 类型]
                    [3, "こんにちは世界！", 95, 1]
                ]
            }
        },
        "binary_format": {
            "description": "二进制压缩格式（最高压缩比）",
            "size": stats["binary_size"],
            "compression_ratio": stats["compression_ratios"]["binary"],
            "space_saved": stats["size_reduction"]["binary"],
            "note": "使用MessagePack序列化 + gzip压缩"
        },
        "encoding_rules": {
            "language_codes": {
                "0": "en", "1": "zh", "2": "zh-tw", "3": "ja", "4": "ko",
                "5": "fr", "6": "de", "7": "es", "8": "it", "9": "ru"
            },
            "confidence": "整数百分比（0-100）",
            "source_type": "0=text, 1=audio",
            "advantages": [
                "消除重复的source_text（节省50-70%空间）",
                "使用数字语言代码（节省字符数）",
                "数组格式减少JSON开销",
                "二进制压缩进一步减小文件大小",
                "保持完整的数据可恢复性"
            ]
        },
        "performance_comparison": stats
    })


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

