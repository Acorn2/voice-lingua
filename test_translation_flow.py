#!/usr/bin/env python3
"""
测试完整的翻译流程
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from src.tasks.translation_task import detect_text_language
from src.services.translation_engine_service import TranslationEngineService

async def test_translation_flow():
    """测试完整的翻译流程"""
    
    # 测试用例
    test_cases = [
        {
            "text": "Tilly, a little fox, loved her bright red balloon. She carried it everywhere.",
            "target_languages": ["zh", "ja", "fr"],
            "expected_source": "en"
        },
        {
            "text": "这是一个测试文本，用于验证翻译功能。",
            "target_languages": ["en", "ja"],
            "expected_source": "zh"
        },
        {
            "text": "こんにちは、世界！これは日本語のテストです。",
            "target_languages": ["en", "zh"],
            "expected_source": "ja"
        }
    ]
    
    print("翻译流程测试:")
    print("=" * 80)
    
    translation_service = TranslationEngineService()
    
    for i, case in enumerate(test_cases, 1):
        text = case["text"]
        target_languages = case["target_languages"]
        expected_source = case["expected_source"]
        
        print(f"\n测试用例 {i}:")
        print(f"原文: {text}")
        print(f"目标语言: {target_languages}")
        
        # 1. 语言检测
        detected_source = detect_text_language(text)
        print(f"检测源语言: {detected_source} (期望: {expected_source})")
        
        if detected_source != expected_source:
            print(f"⚠️  语言检测不准确")
        
        # 2. 翻译测试
        for target_lang in target_languages:
            if detected_source == target_lang:
                print(f"  {target_lang}: 跳过翻译 (源语言与目标语言相同)")
                continue
            
            try:
                print(f"  正在翻译到 {target_lang}...")
                result = await translation_service.translate(
                    text=text,
                    target_language=target_lang,
                    source_language=detected_source
                )
                
                translated_text = result["translated_text"]
                engine = result["engine"]
                confidence = result.get("confidence", 0.0)
                
                print(f"  {target_lang}: {translated_text[:50]}... (引擎: {engine}, 置信度: {confidence:.2f})")
                
            except Exception as e:
                print(f"  {target_lang}: ❌ 翻译失败 - {str(e)}")
        
        print("-" * 40)
    
    print("\n✅ 翻译流程测试完成")


if __name__ == "__main__":
    asyncio.run(test_translation_flow())