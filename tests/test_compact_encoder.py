#!/usr/bin/env python3
"""
测试超紧凑二进制编码器
"""
import json
import os
import sys
import tempfile
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.compact_encoder import CompactBinaryEncoder, encode_translation_data, decode_translation_data, get_compression_stats


def create_test_data():
    """创建测试数据"""
    return {
        "task_id": "9fa45ad0-a902-4319-b4d0-bd2b246dd46d",
        "task_type": "audio",
        "created_at": "2025-01-27T09:14:25Z",
        "completed_at": "2025-01-27T09:14:41Z",
        "accuracy": 0.803,
        "text_number": "1",
        "translations": {
            "en": {
                "AUDIO": {
                    "translated_text": "Tilly, a little fox loved her bright red balloon. She carried it everywhere. My name's Tilly. It's my favorite balloon.",
                    "confidence": 0.95,
                    "source_type": "AUDIO",
                    "target_language": "en"
                },
                "TEXT": {
                    "translated_text": "Tilly, a little fox, loved her bright red balloon. She carried it everywhere. My name's Tilly. It's my favorite balloon.",
                    "confidence": 0.98,
                    "source_type": "TEXT", 
                    "target_language": "en"
                }
            },
            "zh": {
                "AUDIO": {
                    "translated_text": "蒂莉，一只小狐狸喜欢她鲜红的气球。她到哪里都带着它。我叫蒂莉。这是我最喜欢的气球。",
                    "confidence": 0.92,
                    "source_type": "AUDIO",
                    "target_language": "zh"
                },
                "TEXT": {
                    "translated_text": "蒂莉，一只小狐狸，喜欢她鲜红的气球。她到哪里都带着它。我叫蒂莉。这是我最喜欢的气球。",
                    "confidence": 0.94,
                    "source_type": "TEXT",
                    "target_language": "zh"
                }
            },
            "ja": {
                "AUDIO": {
                    "translated_text": "ティリーという小さなキツネは、鮮やかな赤い風船を愛していました。彼女はどこへでもそれを持って行きました。私の名前はティリーです。それは私のお気に入りの風船です。",
                    "confidence": 0.89,
                    "source_type": "AUDIO",
                    "target_language": "ja"
                },
                "TEXT": {
                    "translated_text": "ティリーという小さなキツネは、鮮やかな赤い風船を愛していました。彼女はどこへでもそれを持って行きました。私の名前はティリーです。それは私のお気に入りの風船です。",
                    "confidence": 0.91,
                    "source_type": "TEXT",
                    "target_language": "ja"
                }
            }
        }
    }


def test_basic_encoding_decoding():
    """测试基本的编码和解码功能"""
    print("=" * 60)
    print("测试基本编码和解码功能")
    print("=" * 60)
    
    # 创建测试数据
    test_data = create_test_data()
    
    # 编码
    print("正在编码...")
    binary_data = encode_translation_data(test_data)
    print(f"编码完成，二进制数据大小: {len(binary_data)} bytes")
    
    # 解码
    print("正在解码...")
    decoded_data = decode_translation_data(binary_data)
    print("解码完成")
    
    # 验证关键字段
    assert decoded_data["task_id"] == test_data["task_id"][:8]  # 任务ID被截短
    assert decoded_data["task_type"] == test_data["task_type"]
    assert decoded_data["accuracy"] == test_data["accuracy"]
    assert decoded_data["text_number"] == test_data["text_number"]
    
    # 验证翻译结果
    assert "en" in decoded_data["translations"]
    assert "zh" in decoded_data["translations"]
    assert "ja" in decoded_data["translations"]
    
    print("✅ 基本编码解码测试通过")
    return True


def test_compression_stats():
    """测试压缩统计功能"""
    print("\n" + "=" * 60)
    print("测试压缩统计功能")
    print("=" * 60)
    
    test_data = create_test_data()
    
    # 获取压缩统计
    stats = get_compression_stats(test_data)
    
    print(f"原始大小: {stats['original_size']} bytes")
    print(f"压缩后大小: {stats['compressed_size']} bytes")
    print(f"压缩率: {stats['compression_ratio']}")
    print(f"节省空间: {stats['size_reduction']} bytes")
    print(f"编码版本: {stats['encoding_version']}")
    
    # 验证压缩效果
    assert stats['compressed_size'] < stats['original_size']
    assert float(stats['compression_ratio'].rstrip('%')) > 0
    
    print("✅ 压缩统计测试通过")
    return True


def test_file_operations():
    """测试文件操作"""
    print("\n" + "=" * 60)
    print("测试文件操作")
    print("=" * 60)
    
    test_data = create_test_data()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 编码并保存到文件
        binary_data = encode_translation_data(test_data)
        binary_file = os.path.join(temp_dir, "test.bin")
        
        with open(binary_file, 'wb') as f:
            f.write(binary_data)
        
        print(f"二进制文件已保存: {binary_file}")
        print(f"文件大小: {os.path.getsize(binary_file)} bytes")
        
        # 从文件读取并解码
        with open(binary_file, 'rb') as f:
            loaded_binary = f.read()
        
        decoded_data = decode_translation_data(loaded_binary)
        
        # 保存解码后的JSON用于对比
        json_file = os.path.join(temp_dir, "decoded.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(decoded_data, f, ensure_ascii=False, indent=2)
        
        print(f"解码后的JSON文件已保存: {json_file}")
        print(f"JSON文件大小: {os.path.getsize(json_file)} bytes")
        
        # 验证数据完整性
        assert decoded_data["task_type"] == test_data["task_type"]
        assert len(decoded_data["translations"]) == len(test_data["translations"])
        
        print("✅ 文件操作测试通过")
    
    return True


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("测试边界情况")
    print("=" * 60)
    
    # 测试空翻译结果
    empty_data = {
        "task_id": "test-empty",
        "task_type": "text",
        "created_at": "2025-01-27T10:00:00Z",
        "completed_at": "2025-01-27T10:00:01Z",
        "accuracy": None,
        "text_number": None,
        "translations": {}
    }
    
    try:
        binary_data = encode_translation_data(empty_data)
        decoded_data = decode_translation_data(binary_data)
        assert decoded_data["task_type"] == "text"
        assert decoded_data["translations"] == {}
        print("✅ 空数据测试通过")
    except Exception as e:
        print(f"❌ 空数据测试失败: {e}")
        return False
    
    # 测试大量翻译结果
    large_data = create_test_data()
    large_data["translations"]["ko"] = {
        "AUDIO": {
            "translated_text": "틸리라는 작은 여우는 밝은 빨간 풍선을 사랑했습니다. 그녀는 어디든 그것을 가지고 다녔습니다.",
            "confidence": 0.87,
            "source_type": "AUDIO",
            "target_language": "ko"
        }
    }
    
    try:
        binary_data = encode_translation_data(large_data)
        decoded_data = decode_translation_data(binary_data)
        assert "ko" in decoded_data["translations"]
        print("✅ 大数据测试通过")
    except Exception as e:
        print(f"❌ 大数据测试失败: {e}")
        return False
    
    return True


def main():
    """运行所有测试"""
    print("开始测试超紧凑二进制编码器")
    print("=" * 60)
    
    tests = [
        test_basic_encoding_decoding,
        test_compression_stats,
        test_file_operations,
        test_edge_cases
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)
    
    if passed == total:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit(main())