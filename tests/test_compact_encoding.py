#!/usr/bin/env python3
"""
紧凑编码器测试脚本

演示不同编码格式的压缩效果和性能对比
"""

import json
import sys
import os
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.compact_encoder import CompactTranslationEncoder, UltraCompactEncoder


def load_test_data():
    """加载测试数据"""
    # 使用提供的JSON文件作为测试数据
    test_file = Path(__file__).parent.parent / "docs" / "5c764469-29ad-4d2c-ad8b-2715718c81e6.json"
    
    if test_file.exists():
        with open(test_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 创建模拟数据
        return {
            "task_id": "test-task-12345678",
            "task_type": "audio",
            "status": "completed",
            "created_at": "2025-07-26T12:02:29.804574",
            "completed_at": "2025-07-26T12:06:50.169316",
            "source_language": "en",
            "target_languages": ["en", "zh", "ja", "fr", "de"],
            "transcription": {
                "text": "Hello world, this is a test message for translation.",
                "accuracy": 0.95,
                "language": "en"
            },
            "translations": {
                "en": {
                    "audio_text": {
                        "text": "Hello world, this is a test message for translation.",
                        "source_text": "Hello world, this is a test message for translation.",
                        "confidence": 1.0,
                        "source_type": "AUDIO",
                        "created_at": "2025-07-26T12:03:23.630762"
                    }
                },
                "zh": {
                    "audio_text": {
                        "text": "你好世界，这是一个翻译测试消息。",
                        "source_text": "Hello world, this is a test message for translation.",
                        "confidence": 0.9,
                        "source_type": "AUDIO",
                        "created_at": "2025-07-26T12:03:28.910854"
                    }
                }
            }
        }


def test_compression_performance():
    """测试压缩性能"""
    print("🚀 VoiceLingua 紧凑编码器性能测试")
    print("=" * 60)
    
    # 加载测试数据
    test_data = load_test_data()
    print(f"📄 测试数据：{test_data['task_id']}")
    print(f"🌐 翻译语言数量：{len(test_data.get('translations', {}))}")
    print()
    
    # 获取压缩统计
    stats = CompactTranslationEncoder.get_compression_stats(test_data)
    
    print("📊 文件大小对比：")
    print(f"  📋 原始JSON:      {stats['original_size']:,} 字节")
    print(f"  📄 紧凑JSON:      {stats['compact_json_size']:,} 字节 ({stats['compression_ratios']['compact_json']} 压缩)")
    print(f"  🗜️  二进制压缩:     {stats['binary_size']:,} 字节 ({stats['compression_ratios']['binary']} 压缩)")
    print(f"  ⚡ Base64编码:     {stats['base64_size']:,} 字节 ({stats['compression_ratios']['base64']} 压缩)")
    print()
    
    print("📈 空间节省：")
    print(f"  📄 紧凑JSON:      {stats['size_reduction']['compact_json']} 减少")
    print(f"  🗜️  二进制压缩:     {stats['size_reduction']['binary']} 减少")
    print(f"  ⚡ Base64编码:     {stats['size_reduction']['base64']} 减少")
    print()
    
    # 测试超紧凑编码
    try:
        ultra_data = UltraCompactEncoder.encode_ultra_compact(test_data)
        ultra_size = len(ultra_data)
        ultra_ratio = stats['original_size'] / ultra_size
        ultra_reduction = (1 - ultra_size/stats['original_size']) * 100
        
        print(f"  🔥 超紧凑二进制:   {ultra_size:,} 字节 ({ultra_ratio:.1f}x 压缩, {ultra_reduction:.1f}% 减少)")
        print()
    except Exception as e:
        print(f"  ❌ 超紧凑编码失败: {e}")
        print()
    
    # 性能测试
    print("⏱️  编码性能测试（1000次）：")
    
    def time_function(func, *args, iterations=1000):
        start_time = time.time()
        for _ in range(iterations):
            result = func(*args)
        end_time = time.time()
        return end_time - start_time, result
    
    # 紧凑JSON编码
    compact_time, compact_result = time_function(
        CompactTranslationEncoder.encode_compact_json, test_data
    )
    print(f"  📄 紧凑JSON编码:   {compact_time:.3f}s ({compact_time*1000:.1f}ms/次)")
    
    # 二进制编码
    binary_time, binary_result = time_function(
        CompactTranslationEncoder.encode_binary, test_data
    )
    print(f"  🗜️  二进制编码:     {binary_time:.3f}s ({binary_time*1000:.1f}ms/次)")
    
    # Base64编码
    base64_time, base64_result = time_function(
        CompactTranslationEncoder.encode_base64, test_data
    )
    print(f"  ⚡ Base64编码:     {base64_time:.3f}s ({base64_time*1000:.1f}ms/次)")
    
    print()
    
    # 解码测试
    print("⏱️  解码性能测试（1000次）：")
    
    # 紧凑JSON解码
    decode_compact_time, _ = time_function(
        CompactTranslationEncoder.decode_compact_json, compact_result
    )
    print(f"  📄 紧凑JSON解码:   {decode_compact_time:.3f}s ({decode_compact_time*1000:.1f}ms/次)")
    
    # 二进制解码
    decode_binary_time, _ = time_function(
        CompactTranslationEncoder.decode_binary, binary_result
    )
    print(f"  🗜️  二进制解码:     {decode_binary_time:.3f}s ({decode_binary_time*1000:.1f}ms/次)")
    
    # Base64解码
    decode_base64_time, _ = time_function(
        CompactTranslationEncoder.decode_base64, base64_result
    )
    print(f"  ⚡ Base64解码:     {decode_base64_time:.3f}s ({decode_base64_time*1000:.1f}ms/次)")
    
    print()
    print("✅ 测试完成！")


def test_data_integrity():
    """测试数据完整性"""
    print("\n🔍 数据完整性测试：")
    
    test_data = load_test_data()
    
    # 测试紧凑JSON
    compact_data = CompactTranslationEncoder.encode_compact_json(test_data)
    decoded_data = CompactTranslationEncoder.decode_compact_json(compact_data)
    
    # 检查关键字段
    checks = [
        ("任务ID", test_data["task_id"][:8] == decoded_data["task_id"]),
        ("源语言", test_data["source_language"] == decoded_data["source_language"]),
        ("源文本", test_data["transcription"]["text"] == decoded_data["source_text"]),
        ("翻译数量", len(test_data["translations"]) <= len(decoded_data["translations"]) + 1)  # 源语言可能被合并
    ]
    
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}: {'通过' if result else '失败'}")
    
    # 测试二进制编码
    binary_data = CompactTranslationEncoder.encode_binary(test_data)
    binary_decoded = CompactTranslationEncoder.decode_binary(binary_data)
    
    binary_check = binary_decoded["source_text"] == test_data["transcription"]["text"]
    print(f"  {'✅' if binary_check else '❌'} 二进制编码: {'通过' if binary_check else '失败'}")


def show_format_examples():
    """显示格式示例"""
    print("\n📋 编码格式示例：")
    
    test_data = load_test_data()
    
    # 原始格式（截取）
    print("\n1️⃣ 原始JSON格式（冗长）：")
    original_sample = {
        "translations": {
            "zh": {
                "audio_text": {
                    "text": "你好世界",
                    "source_text": "Hello world, this is a test...",  # 重复！
                    "confidence": 0.9,
                    "source_type": "AUDIO",
                    "created_at": "2025-07-26T12:03:28.910854"  # 冗余！
                }
            }
        }
    }
    print(json.dumps(original_sample, ensure_ascii=False, indent=2))
    
    # 紧凑格式
    print("\n2️⃣ 紧凑JSON格式（简洁）：")
    compact_sample = {
        "v": "1.0",
        "src": "en",
        "txt": "Hello world, this is a test...",  # 只存储一次！
        "langs": [
            [1, "你好世界", 90, 1]  # [语言代码, 翻译文本, 置信度%, 来源类型]
        ]
    }
    print(json.dumps(compact_sample, ensure_ascii=False, indent=2))
    
    print("\n3️⃣ 数组格式说明：")
    print("  [语言代码, 翻译文本, 置信度(0-100), 来源类型(0=text,1=audio)]")
    print("  语言代码: 0=en, 1=zh, 2=zh-tw, 3=ja, 4=ko, 5=fr, 6=de, 7=es, 8=it, 9=ru")


if __name__ == "__main__":
    test_compression_performance()
    test_data_integrity()
    show_format_examples() 