"""
VoiceLingua 紧凑编码器

设计一种高效、简洁、快速且紧凑的编码方式，将多语言翻译结果打包成紧凑格式

核心设计原则：
1. 消除重复数据（source_text只存储一次）
2. 使用简短字段名和语言代码
3. 数组格式减少JSON开销
4. 可选的二进制压缩
5. 快速解码和编码
"""

import json
import gzip
import base64
import struct
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import msgpack  # 二进制序列化，比JSON更紧凑


class CompactTranslationEncoder:
    """紧凑翻译结果编码器"""
    
    # 语言代码映射（使用更短的代码）
    LANG_MAP = {
        'en': 0, 'zh': 1, 'zh-tw': 2, 'ja': 3, 'ko': 4,
        'fr': 5, 'de': 6, 'es': 7, 'it': 8, 'ru': 9
    }
    
    REVERSE_LANG_MAP = {v: k for k, v in LANG_MAP.items()}
    
    # 编码格式版本
    VERSION = "1.0"
    
    @classmethod 
    def _calculate_processing_time(cls, task_data: Dict[str, Any]) -> int:
        """计算处理时间（秒）"""
        try:
            if "completed_at" in task_data and "created_at" in task_data:
                completed = datetime.fromisoformat(task_data["completed_at"].replace('Z', '+00:00'))
                created = datetime.fromisoformat(task_data["created_at"].replace('Z', '+00:00'))
                return int((completed - created).total_seconds())
            elif "processing_time_seconds" in task_data:
                return int(task_data["processing_time_seconds"])
            else:
                return 0
        except Exception:
            return 0
    
    @classmethod
    def encode_compact_json(cls, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        编码为紧凑JSON格式
        
        减少字段名长度和重复数据，但保持JSON可读性
        """
        # 提取核心信息
        task_id = task_data["task_id"]
        source_lang = task_data.get("source_language", "en")  # 默认英语
        transcription_text = task_data.get("transcription", {}).get("text", "")
        
        # 构建紧凑格式
        compact = {
            "v": cls.VERSION,  # version
            "id": task_id[:8],  # 短ID（前8位）
            "src": source_lang,  # source language
            "txt": transcription_text,  # source text
            "langs": [],  # 翻译结果数组
            "meta": {
                "total": len(task_data.get("translations", {})),
                "time": cls._calculate_processing_time(task_data)
            }
        }
        
        # 处理翻译结果（数组格式，消除重复）
        translations = task_data.get("translations", {})
        for lang_code, translations_data in translations.items():
            if lang_code == source_lang:
                continue  # 跳过源语言（避免重复）
                
            # 处理可能的嵌套结构
            if isinstance(translations_data, dict):
                for source_type, trans_data in translations_data.items():
                    if isinstance(trans_data, dict) and "text" in trans_data:
                        confidence = trans_data.get("confidence", 0.9)
                        if isinstance(confidence, (int, float)):
                            confidence_percent = int(confidence * 100) if confidence <= 1 else int(confidence)
                        else:
                            confidence_percent = 90
                            
                        lang_entry = [
                            cls.LANG_MAP.get(lang_code, lang_code),  # 语言代码（数字或字符串）
                            trans_data["text"],  # 翻译文本
                            confidence_percent,  # 置信度（整数百分比）
                            1 if source_type == "audio_text" else 0  # 来源类型（0=text, 1=audio）
                        ]
                        compact["langs"].append(lang_entry)
        
        return compact
    
    @classmethod
    def encode_binary(cls, task_data: Dict[str, Any]) -> bytes:
        """
        编码为二进制格式（MessagePack + gzip）
        
        最紧凑的格式，适合存储和传输
        """
        compact_data = cls.encode_compact_json(task_data)
        
        # 使用MessagePack序列化（比JSON更紧凑）
        msgpack_data = msgpack.packb(compact_data, use_bin_type=True)
        
        # gzip压缩
        compressed_data = gzip.compress(msgpack_data, compresslevel=9)
        
        return compressed_data
    
    @classmethod
    def encode_base64(cls, task_data: Dict[str, Any]) -> str:
        """
        编码为Base64字符串格式
        
        适合URL传输和文本存储
        """
        binary_data = cls.encode_binary(task_data)
        return base64.b64encode(binary_data).decode('ascii')
    
    @classmethod
    def decode_compact_json(cls, compact_data: Dict[str, Any]) -> Dict[str, Any]:
        """解码紧凑JSON格式"""
        # 重构完整格式
        full_data = {
            "task_id": compact_data["id"],
            "version": compact_data["v"],
            "source_language": compact_data["src"],
            "source_text": compact_data["txt"],
            "processing_time": compact_data["meta"]["time"],
            "translations": {}
        }
        
        # 添加源语言
        full_data["translations"][compact_data["src"]] = compact_data["txt"]
        
        # 解码翻译结果
        for lang_entry in compact_data["langs"]:
            lang_code = cls.REVERSE_LANG_MAP.get(lang_entry[0], lang_entry[0])
            text = lang_entry[1]
            confidence = lang_entry[2] / 100.0
            source_type = "audio" if lang_entry[3] == 1 else "text"
            
            full_data["translations"][lang_code] = {
                "text": text,
                "confidence": confidence,
                "source_type": source_type
            }
        
        return full_data
    
    @classmethod
    def decode_binary(cls, binary_data: bytes) -> Dict[str, Any]:
        """解码二进制格式"""
        # 解压缩
        decompressed_data = gzip.decompress(binary_data)
        
        # MessagePack反序列化
        compact_data = msgpack.unpackb(decompressed_data, raw=False)
        
        # 转换为完整格式
        return cls.decode_compact_json(compact_data)
    
    @classmethod
    def decode_base64(cls, base64_string: str) -> Dict[str, Any]:
        """解码Base64字符串格式"""
        binary_data = base64.b64decode(base64_string.encode('ascii'))
        return cls.decode_binary(binary_data)
    
    @classmethod
    def get_compression_stats(cls, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取压缩统计信息"""
        original_json = json.dumps(original_data, ensure_ascii=False)
        compact_json_data = cls.encode_compact_json(original_data)
        compact_json = json.dumps(compact_json_data, ensure_ascii=False)
        binary_data = cls.encode_binary(original_data)
        base64_data = cls.encode_base64(original_data)
        
        original_size = len(original_json.encode('utf-8'))
        compact_json_size = len(compact_json.encode('utf-8'))
        binary_size = len(binary_data)
        base64_size = len(base64_data.encode('ascii'))
        
        return {
            "original_size": original_size,
            "compact_json_size": compact_json_size,
            "binary_size": binary_size,
            "base64_size": base64_size,
            "compression_ratios": {
                "compact_json": f"{original_size / compact_json_size:.1f}x",
                "binary": f"{original_size / binary_size:.1f}x",
                "base64": f"{original_size / base64_size:.1f}x"
            },
            "size_reduction": {
                "compact_json": f"{(1 - compact_json_size/original_size)*100:.1f}%",
                "binary": f"{(1 - binary_size/original_size)*100:.1f}%",
                "base64": f"{(1 - base64_size/original_size)*100:.1f}%"
            }
        }


class UltraCompactEncoder:
    """
    超紧凑编码器 - 针对极致压缩优化
    
    使用自定义二进制格式，达到最高压缩比
    """
    
    @classmethod
    def encode_ultra_compact(cls, task_data: Dict[str, Any]) -> bytes:
        """
        超紧凑二进制编码
        
        格式：[头部][源文本][翻译数据]
        - 头部：版本(1B) + 语言数量(1B) + 源语言代码(1B) + 源文本长度(2B)
        - 翻译数据：语言代码(1B) + 置信度(1B) + 文本长度(2B) + 文本数据
        """
        source_text = task_data["transcription"]["text"]
        source_lang_code = CompactTranslationEncoder.LANG_MAP.get(
            task_data["source_language"], 255
        )
        
        # 构建二进制数据
        data = bytearray()
        
        # 头部（5字节）
        data.extend(struct.pack('B', 1))  # 版本
        data.extend(struct.pack('B', len(task_data["translations"]) - 1))  # 翻译语言数量（排除源语言）
        data.extend(struct.pack('B', source_lang_code))  # 源语言代码
        
        source_text_bytes = source_text.encode('utf-8')
        data.extend(struct.pack('H', len(source_text_bytes)))  # 源文本长度
        data.extend(source_text_bytes)  # 源文本
        
        # 翻译数据
        for lang_code, translations in task_data["translations"].items():
            if lang_code == task_data["source_language"]:
                continue
                
            lang_num = CompactTranslationEncoder.LANG_MAP.get(lang_code, 255)
            
            for source_type, trans_data in translations.items():
                text_bytes = trans_data["text"].encode('utf-8')
                confidence_byte = int(trans_data["confidence"] * 255)
                
                data.extend(struct.pack('B', lang_num))  # 语言代码
                data.extend(struct.pack('B', confidence_byte))  # 置信度
                data.extend(struct.pack('H', len(text_bytes)))  # 文本长度
                data.extend(text_bytes)  # 文本内容
        
        # gzip压缩
        return gzip.compress(data, compresslevel=9)
    
    @classmethod
    def decode_ultra_compact(cls, binary_data: bytes) -> Dict[str, Any]:
        """解码超紧凑二进制格式"""
        # 解压缩
        data = gzip.decompress(binary_data)
        
        offset = 0
        
        # 读取头部
        version = struct.unpack('B', data[offset:offset+1])[0]
        offset += 1
        
        translation_count = struct.unpack('B', data[offset:offset+1])[0]
        offset += 1
        
        source_lang_code = struct.unpack('B', data[offset:offset+1])[0]
        offset += 1
        
        source_text_length = struct.unpack('H', data[offset:offset+2])[0]
        offset += 2
        
        source_text = data[offset:offset+source_text_length].decode('utf-8')
        offset += source_text_length
        
        # 构建结果
        result = {
            "version": version,
            "source_language": CompactTranslationEncoder.REVERSE_LANG_MAP.get(source_lang_code, 'unknown'),
            "source_text": source_text,
            "translations": {}
        }
        
        # 添加源语言
        result["translations"][result["source_language"]] = source_text
        
        # 读取翻译数据
        for _ in range(translation_count):
            lang_code = struct.unpack('B', data[offset:offset+1])[0]
            offset += 1
            
            confidence_byte = struct.unpack('B', data[offset:offset+1])[0]
            offset += 1
            
            text_length = struct.unpack('H', data[offset:offset+2])[0]
            offset += 2
            
            text = data[offset:offset+text_length].decode('utf-8')
            offset += text_length
            
            lang_name = CompactTranslationEncoder.REVERSE_LANG_MAP.get(lang_code, f'lang_{lang_code}')
            result["translations"][lang_name] = {
                "text": text,
                "confidence": confidence_byte / 255.0
            }
        
        return result


# 使用示例和性能测试函数
def test_encoders():
    """测试各种编码器的性能"""
    # 这里会在实际使用时导入测试数据
    pass 