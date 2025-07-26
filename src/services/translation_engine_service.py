"""
翻译引擎管理服务
"""
import logging
from typing import Dict, Any, Optional
import torch
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

from src.config.settings import settings, LANGUAGE_MAPPING, TranslationEngine
from src.services.qwen_translation_service import qwen_translation_service

logger = logging.getLogger(__name__)


class TranslationEngineService:
    """翻译引擎管理服务"""
    
    def __init__(self):
        self.engine = settings.translation_engine
        
        # 本地模型缓存
        self._local_model = None
        self._local_tokenizer = None
        
        logger.info(f"翻译引擎模式: {self.engine.value}")
    
    def get_local_model(self):
        """获取本地翻译模型（懒加载）"""
        if self._local_model is None:
            device = "cuda" if torch.cuda.is_available() and settings.whisper_device == "cuda" else "cpu"
            logger.info(f"加载本地翻译模型: {settings.translation_model}, 设备: {device}")
            
            self._local_tokenizer = M2M100Tokenizer.from_pretrained(settings.translation_model)
            self._local_model = M2M100ForConditionalGeneration.from_pretrained(settings.translation_model).to(device)
            
            logger.info("本地翻译模型加载完成")
        
        return self._local_model, self._local_tokenizer
    
    async def translate_with_local_model(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "zh"
    ) -> Dict[str, Any]:
        """使用本地模型翻译"""
        try:
            # 检查是否需要跳过翻译（源语言与目标语言相同）
            if target_language == source_language:
                return {
                    "translated_text": text,
                    "confidence": 1.0,
                    "engine": "local",
                    "model": settings.translation_model,
                    "skipped": True
                }
            
            # 获取本地模型
            model, tokenizer = self.get_local_model()
            
            # 设置源语言和目标语言
            tokenizer.src_lang = source_language
            target_lang_code = LANGUAGE_MAPPING.get(target_language, target_language)
            
            logger.info(f"本地模型翻译: {source_language} -> {target_lang_code}")
            
            # 编码输入文本
            encoded = tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=settings.max_translation_length
            )
            
            # 移动到设备
            device = next(model.parameters()).device
            encoded = {k: v.to(device) for k, v in encoded.items()}
            
            # 生成翻译
            with torch.no_grad():
                generated_tokens = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.get_lang_id(target_lang_code),
                    max_length=settings.max_translation_length,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            # 解码结果
            translated_text = tokenizer.batch_decode(
                generated_tokens, 
                skip_special_tokens=True
            )[0].strip()
            
            # 简单的置信度计算（基于文本长度比例）
            confidence = min(1.0, len(translated_text) / max(1, len(text)))
            
            return {
                "translated_text": translated_text,
                "confidence": confidence,
                "engine": "local",
                "model": settings.translation_model
            }
            
        except Exception as e:
            logger.error(f"本地模型翻译失败: {str(e)}")
            raise e
    
    async def translate_with_qwen(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "zh"
    ) -> Dict[str, Any]:
        """使用千问大模型翻译"""
        if not qwen_translation_service.is_available():
            raise Exception("千问API未配置或不可用")
        
        return await qwen_translation_service.translate_text(text, target_language, source_language)
    
    async def translate(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "zh"
    ) -> Dict[str, Any]:
        """
        根据配置的引擎进行翻译
        
        Args:
            text: 待翻译文本
            target_language: 目标语言代码
            source_language: 源语言代码
            
        Returns:
            翻译结果字典
        """
        try:
            if self.engine == TranslationEngine.LOCAL:
                # 仅使用本地模型
                return await self.translate_with_local_model(text, target_language, source_language)
            
            elif self.engine == TranslationEngine.QWEN:
                # 仅使用千问大模型
                return await self.translate_with_qwen(text, target_language, source_language)
            
            elif self.engine == TranslationEngine.MIXED:
                # 混合模式：优先本地模型，失败时使用千问
                try:
                    result = await self.translate_with_local_model(text, target_language, source_language)
                    logger.info(f"混合模式使用本地模型翻译成功: {target_language}")
                    return result
                except Exception as local_error:
                    logger.warning(f"本地模型翻译失败，尝试千问大模型: {str(local_error)}")
                    
                    if qwen_translation_service.is_available():
                        try:
                            result = await self.translate_with_qwen(text, target_language, source_language)
                            result["fallback"] = True
                            result["local_error"] = str(local_error)
                            logger.info(f"混合模式使用千问大模型翻译成功: {target_language}")
                            return result
                        except Exception as qwen_error:
                            logger.error(f"千问大模型翻译也失败: {str(qwen_error)}")
                            raise Exception(f"所有翻译引擎都失败 - 本地: {str(local_error)}, 千问: {str(qwen_error)}")
                    else:
                        logger.error("千问API未配置，无法进行回退翻译")
                        raise local_error
            
            else:
                raise Exception(f"未知的翻译引擎: {self.engine}")
                
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            raise e
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取翻译引擎状态"""
        status = {
            "current_engine": self.engine.value,
            "local_model_loaded": self._local_model is not None,
            "qwen_available": qwen_translation_service.is_available(),
            "supported_languages": settings.supported_languages
        }
        
        if self._local_model is not None:
            device = next(self._local_model.parameters()).device
            status["local_model_device"] = str(device)
            status["local_model_name"] = settings.translation_model
        
        if qwen_translation_service.is_available():
            status["qwen_model"] = settings.qwen_model
            status["qwen_api_base"] = settings.qwen_api_base
        
        return status


# 全局翻译引擎服务实例
translation_engine_service = TranslationEngineService() 