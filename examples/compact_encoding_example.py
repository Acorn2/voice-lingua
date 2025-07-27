#!/usr/bin/env python3
"""
超紧凑二进制编码使用示例
演示如何使用新的编码器来压缩和解压翻译结果
"""
import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.compact_encoder import (
    CompactBinaryEncoder, 
    encode_translation_data, 
    decode_translation_data, 
    get_compression_stats
)


def create_sample_translation_data():
    """创建示例翻译数据"""
    return {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "task_type": "audio",
        "created_at": "2025-01-27T10:00:00Z",
        "completed_at": "2025-01-27T10:02:15Z",
        "accuracy": 0.95,
        "text_number": "123",
        "translations": {
            "en": {
                "AUDIO": {
                    "translated_text": "Hello, this is a transcribed and translated text from audio.",
                    "confidence": 0.95,
                    "source_type": "AUDIO",
                    "target_language": "en"
                },
                "TEXT": {
                    "translated_text": "Hello, this is a reference text for comparison.",
                    "confidence": 0.98,
                    "source_type": "TEXT",
                    "target_language": "en"
                }
            },
            "zh": {
                "AUDIO": {
                    "translated_text": "你好，这是从音频转录和翻译的文本。",
                    "confidence": 0.92,
                    "source_type": "AUDIO",
                    "target_language": "zh"
                },
                "TEXT": {
                    "translated_text": "你好，这是用于比较的参考文本。",
                    "confidence": 0.94,
                    "source_type": "TEXT",
                    "target_language": "zh"
                }
            },
            "ja": {
                "AUDIO": {
                    "translated_text": "こんにちは、これは音声から転写・翻訳されたテキストです。",
                    "confidence": 0.89,
                    "source_type": "AUDIO",
                    "target_language": "ja"
                },
                "TEXT": {
                    "translated_text": "こんにちは、これは比較用の参照テキストです。",
                    "confidence": 0.91,
                    "source_type": "TEXT",
                    "target_language": "ja"
                }
            }
        }
    }


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("基本使用示例")
    print("=" * 60)
    
    # 创建示例数据
    data = create_sample_translation_data()
    
    print("1. 原始数据:")
    print(f"   任务ID: {data['task_id']}")
    print(f"   任务类型: {data['task_type']}")
    print(f"   支持语言: {list(data['translations'].keys())}")
    
    # 编码
    print("\n2. 编码为超紧凑二进制格式...")
    binary_data = encode_translation_data(data)
    print(f"   编码完成，大小: {len(binary_data)} bytes")
    
    # 解码
    print("\n3. 解码二进制数据...")
    decoded_data = decode_translation_data(binary_data)
    print(f"   解码完成")
    print(f"   任务ID: {decoded_data['task_id']}")
    print(f"   任务类型: {decoded_data['task_type']}")
    print(f"   支持语言: {list(decoded_data['translations'].keys())}")
    
    # 验证数据完整性
    print("\n4. 验证数据完整性...")
    assert decoded_data['task_type'] == data['task_type']
    assert decoded_data['accuracy'] == data['accuracy']
    assert len(decoded_data['translations']) == len(data['translations'])
    print("   ✅ 数据完整性验证通过")


def example_compression_analysis():
    """压缩分析示例"""
    print("\n" + "=" * 60)
    print("压缩分析示例")
    print("=" * 60)
    
    data = create_sample_translation_data()
    
    # 获取压缩统计
    stats = get_compression_stats(data)
    
    print("压缩统计信息:")
    print(f"  原始大小: {stats['original_size']:,} bytes")
    print(f"  压缩后大小: {stats['compressed_size']:,} bytes")
    print(f"  压缩率: {stats['compression_ratio']}")
    print(f"  节省空间: {stats['size_reduction']:,} bytes")
    print(f"  编码版本: {stats['encoding_version']}")
    
    # 计算存储成本节省（假设每GB每月$0.02）
    gb_saved = stats['size_reduction'] / (1024 * 1024 * 1024)
    monthly_savings = gb_saved * 0.02
    print(f"\n成本节省估算（每个文件）:")
    print(f"  存储空间节省: {gb_saved * 1024:.2f} MB")
    print(f"  月度成本节省: ${monthly_savings:.6f}")


def example_file_operations():
    """文件操作示例"""
    print("\n" + "=" * 60)
    print("文件操作示例")
    print("=" * 60)
    
    data = create_sample_translation_data()
    
    # 创建输出目录
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存原始JSON文件
    original_file = os.path.join(output_dir, "original.json")
    with open(original_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 编码并保存二进制文件
    binary_file = os.path.join(output_dir, "compressed.bin")
    binary_data = encode_translation_data(data)
    with open(binary_file, 'wb') as f:
        f.write(binary_data)
    
    # 从二进制文件解码并保存
    decoded_file = os.path.join(output_dir, "decoded.json")
    with open(binary_file, 'rb') as f:
        loaded_binary = f.read()
    
    decoded_data = decode_translation_data(loaded_binary)
    with open(decoded_file, 'w', encoding='utf-8') as f:
        json.dump(decoded_data, f, ensure_ascii=False, indent=2)
    
    # 显示文件大小对比
    original_size = os.path.getsize(original_file)
    binary_size = os.path.getsize(binary_file)
    decoded_size = os.path.getsize(decoded_file)
    
    print("文件大小对比:")
    print(f"  原始JSON文件: {original_size:,} bytes")
    print(f"  压缩二进制文件: {binary_size:,} bytes")
    print(f"  解码JSON文件: {decoded_size:,} bytes")
    print(f"  压缩率: {(1 - binary_size / original_size) * 100:.1f}%")
    
    print(f"\n文件已保存到 {output_dir}/ 目录:")
    print(f"  - {original_file}")
    print(f"  - {binary_file}")
    print(f"  - {decoded_file}")


def example_advanced_usage():
    """高级使用示例"""
    print("\n" + "=" * 60)
    print("高级使用示例 - 自定义编码器")
    print("=" * 60)
    
    # 使用自定义编码器实例
    encoder = CompactBinaryEncoder()
    
    data = create_sample_translation_data()
    
    # 编码
    binary_data = encoder.encode(data)
    print(f"编码完成: {len(binary_data)} bytes")
    
    # 解码
    decoded_data = encoder.decode(binary_data)
    print("解码完成")
    
    # 获取详细的编码信息
    encoding_info = encoder.get_encoding_info(data)
    print("\n详细编码信息:")
    for key, value in encoding_info.items():
        print(f"  {key}: {value}")


def main():
    """运行所有示例"""
    print("超紧凑二进制编码使用示例")
    print("=" * 60)
    
    try:
        example_basic_usage()
        example_compression_analysis()
        example_file_operations()
        example_advanced_usage()
        
        print("\n" + "=" * 60)
        print("🎉 所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())