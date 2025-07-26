"""
千问大模型翻译服务
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
import json
import httpx
from datetime import datetime

from src.config.settings import settings, LANGUAGE_MAPPING

logger = logging.getLogger(__name__)


class QwenTranslationService:
    """千问大模型翻译服务"""
    
    def __init__(self):
        self.api_key = settings.qwen_api_key
        self.api_base = settings.qwen_api_base
        self.model = settings.qwen_model
        self.timeout = settings.translation_timeout
        
        # 语言映射 - 千问模型使用的语言代码
        self.language_names = {
            "en": "English",
            "zh": "Chinese",
            "zh-tw": "Traditional Chinese", 
            "ja": "Japanese",
            "ko": "Korean",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "it": "Italian",
            "ru": "Russian"
        }
    
    def is_available(self) -> bool:
        """检查千问服务是否可用"""
        return bool(self.api_key and self.api_key != "your_qwen_api_key_here")
    
    def _build_translation_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        """构建翻译提示词"""
        source_name = self.language_names.get(source_lang, source_lang)
        target_name = self.language_names.get(target_lang, target_lang)
        
        prompt = f"""请将以下{source_name}文本翻译成{target_name}：

原文：{text}

要求：
1. 保持原文的语气和风格
2. 准确传达原文含义
3. 使用自然流畅的{target_name}表达
4. 只返回翻译结果，不要包含其他内容

翻译："""
        
        return prompt
    
    async def translate_text(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "zh"
    ) -> Dict[str, Any]:
        """
        使用千问大模型翻译文本
        
        Args:
            text: 待翻译文本
            target_language: 目标语言代码
            source_language: 源语言代码
            
        Returns:
            翻译结果字典
        """
        try:
            if not self.is_available():
                raise Exception("千问API密钥未配置")
            
            # 构建翻译提示词
            prompt = self._build_translation_prompt(text, source_language, target_language)
            
            # 准备API请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # 较低的温度保证翻译稳定性
                "max_tokens": settings.max_translation_length,
                "stream": False
            }
            
            # 发送API请求
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                response.raise_for_status()
                result = response.json()
            
            # 解析响应
            if "choices" in result and len(result["choices"]) > 0:
                translated_text = result["choices"][0]["message"]["content"].strip()
                
                # 简单的质量检查
                if not translated_text or translated_text == text:
                    raise Exception("翻译结果为空或与原文相同")
                
                # 计算置信度（基于响应质量）
                confidence = self._calculate_confidence(text, translated_text, result)
                
                logger.info(f"千问翻译完成: {source_language} -> {target_language}")
                
                return {
                    "translated_text": translated_text,
                    "confidence": confidence,
                    "engine": "qwen",
                    "model": self.model,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source_language": source_language,
                    "target_language": target_language
                }
            else:
                raise Exception("API响应格式异常")
                
        except httpx.TimeoutException:
            logger.error(f"千问翻译超时: {text[:50]}...")
            raise Exception("翻译请求超时")
        except httpx.HTTPStatusError as e:
            logger.error(f"千问API错误 {e.response.status_code}: {e.response.text}")
            raise Exception(f"API请求失败: {e.response.status_code}")
        except Exception as e:
            logger.error(f"千问翻译失败: {str(e)}")
            raise e
    
    def _calculate_confidence(self, source_text: str, translated_text: str, api_response: Dict) -> float:
        """计算翻译置信度"""
        try:
            # 基础置信度
            confidence = 0.8
            
            # 长度比例检查
            length_ratio = len(translated_text) / max(len(source_text), 1)
            if 0.5 <= length_ratio <= 2.0:
                confidence += 0.1
            
            # 检查是否包含完整的句子结构
            if any(punct in translated_text for punct in '.。！!？?'):
                confidence += 0.05
            
            # 检查API响应中的使用信息
            if "usage" in api_response:
                usage = api_response["usage"]
                completion_tokens = usage.get("completion_tokens", 0)
                if completion_tokens > 0:
                    confidence += 0.05
            
            return min(confidence, 1.0)
            
        except Exception:
            return 0.75  # 默认置信度
    
    async def translate_batch(
        self, 
        texts: List[str], 
        target_language: str, 
        source_language: str = "zh"
    ) -> List[Dict[str, Any]]:
        """
        批量翻译文本
        
        Args:
            texts: 待翻译文本列表
            target_language: 目标语言代码
            source_language: 源语言代码
            
        Returns:
            翻译结果列表
        """
        tasks = []
        for text in texts:
            task = self.translate_text(text, target_language, source_language)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果，将异常转换为错误信息
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "error": str(result),
                        "source_text": texts[i],
                        "engine": "qwen"
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"批量翻译失败: {str(e)}")
            raise e


# 全局千问翻译服务实例
qwen_translation_service = QwenTranslationService() 