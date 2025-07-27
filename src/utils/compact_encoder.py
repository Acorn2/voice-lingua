#!/usr/bin/env python3
"""
紧凑编码器 - 实现数据文件的高效编码和解码
支持两阶段压缩：紧凑JSON + 二进制压缩
"""
import json
import gzip
import base64
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CompactBinaryEncoder:
    """超紧凑二进制编码器"""
    
    def __init__(self):
        self.version = "1.0"
    
    def encode(self, translation_data: Dict[str, Any]) -> bytes:
        """
        编码翻译数据为超紧凑二进制格式
        
        Args:
            translation_data: 翻译数据字典
            
        Returns:
            bytes: 压缩后的二进制数据
        """
        try:
            # 第一阶段：生成紧凑JSON
            compact_json = self._create_compact_json(translation_data)
            
            # 第二阶段：二进制压缩
            binary_data = self._compress_to_binary(compact_json)
            
            logger.info(f"编码完成: 原始大小 {len(json.dumps(translation_data).encode())} bytes, "
                       f"压缩后 {len(binary_data)} bytes, "
                       f"压缩率 {(1 - len(binary_data) / len(json.dumps(translation_data).encode())) * 100:.1f}%")
            
            return binary_data
            
        except Exception as e:
            logger.error(f"编码失败: {e}")
            raise
    
    def decode(self, binary_data: bytes) -> Dict[str, Any]:
        """
        解码二进制数据为可读的翻译数据
        
        Args:
            binary_data: 压缩的二进制数据
            
        Returns:
            Dict[str, Any]: 解码后的翻译数据
        """
        try:
            # 第一阶段：二进制解压
            compact_json = self._decompress_from_binary(binary_data)
            
            # 第二阶段：解析紧凑JSON
            readable_data = self._parse_compact_json(compact_json)
            
            logger.info(f"解码完成: 二进制大小 {len(binary_data)} bytes")
            
            return readable_data
            
        except Exception as e:
            logger.error(f"解码失败: {e}")
            raise
    
    def _create_compact_json(self, data: Dict[str, Any]) -> str:
        """
        创建紧凑JSON格式
        使用语言短码，移除冗余字段，优化结构
        """
        compact_data = {
            "v": self.version,  # 版本号
            "id": data.get("task_id", "")[:8],  # 任务ID缩短
            "type": data.get("task_type", ""),
            "created": self._compact_datetime(data.get("created_at")),
            "completed": self._compact_datetime(data.get("completed_at")),
            "accuracy": data.get("accuracy"),
            "text_number": data.get("text_number"),
            "translations": {}
        }
        
        # 处理翻译结果 - 使用语言短码
        translations = data.get("translations", {})
        for lang_code, lang_data in translations.items():
            if isinstance(lang_data, dict):
                compact_data["translations"][lang_code] = {}
                
                # 处理AUDIO和TEXT来源的翻译
                for source_type in ["AUDIO", "TEXT"]:
                    if source_type in lang_data:
                        source_data = lang_data[source_type]
                        if isinstance(source_data, dict):
                            # 紧凑格式：只保留必要字段
                            compact_data["translations"][lang_code][source_type] = {
                                "text": source_data.get("translated_text", ""),
                                "conf": source_data.get("confidence")  # 缩短字段名
                            }
                        else:
                            # 如果是字符串，直接存储
                            compact_data["translations"][lang_code][source_type] = {
                                "text": str(source_data),
                                "conf": None
                            }
        
        # 移除空值
        compact_data = self._remove_empty_values(compact_data)
        
        # 生成紧凑JSON（无空格）
        return json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    
    def _compress_to_binary(self, json_str: str) -> bytes:
        """
        将JSON字符串压缩为二进制数据
        使用gzip压缩算法
        """
        # 转换为UTF-8字节
        json_bytes = json_str.encode('utf-8')
        
        # gzip压缩
        compressed = gzip.compress(json_bytes, compresslevel=9)
        
        return compressed
    
    def _decompress_from_binary(self, binary_data: bytes) -> str:
        """
        从二进制数据解压为JSON字符串
        """
        # gzip解压
        decompressed = gzip.decompress(binary_data)
        
        # 转换为字符串
        return decompressed.decode('utf-8')
    
    def _parse_compact_json(self, compact_json: str) -> Dict[str, Any]:
        """
        解析紧凑JSON为标准格式
        """
        compact_data = json.loads(compact_json)
        
        # 还原为标准格式
        standard_data = {
            "task_id": compact_data.get("id", ""),
            "task_type": compact_data.get("type", ""),
            "created_at": self._expand_datetime(compact_data.get("created")),
            "completed_at": self._expand_datetime(compact_data.get("completed")),
            "accuracy": compact_data.get("accuracy"),
            "text_number": compact_data.get("text_number"),
            "version": compact_data.get("v", "1.0"),
            "translations": {}
        }
        
        # 还原翻译结果
        translations = compact_data.get("translations", {})
        for lang_code, lang_data in translations.items():
            standard_data["translations"][lang_code] = {}
            
            for source_type, source_data in lang_data.items():
                if isinstance(source_data, dict):
                    standard_data["translations"][lang_code][source_type] = {
                        "translated_text": source_data.get("text", ""),
                        "confidence": source_data.get("conf"),
                        "source_type": source_type,
                        "target_language": lang_code
                    }
        
        return standard_data
    
    def _compact_datetime(self, dt_str: str) -> str:
        """
        压缩日期时间格式
        从 "2025-01-27T09:14:25Z" 压缩为 "250127091425"
        """
        if not dt_str:
            return ""
        
        try:
            # 解析ISO格式
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1]
            
            dt = datetime.fromisoformat(dt_str.replace('Z', ''))
            
            # 压缩为 YYMMDDHHMMSS 格式
            return dt.strftime("%y%m%d%H%M%S")
        except:
            return dt_str
    
    def _expand_datetime(self, compact_dt: str) -> str:
        """
        展开压缩的日期时间格式
        从 "250127091425" 展开为 "2025-01-27T09:14:25Z"
        """
        if not compact_dt or len(compact_dt) != 12:
            return ""
        
        try:
            # 解析 YYMMDDHHMMSS 格式
            year = 2000 + int(compact_dt[:2])
            month = int(compact_dt[2:4])
            day = int(compact_dt[4:6])
            hour = int(compact_dt[6:8])
            minute = int(compact_dt[8:10])
            second = int(compact_dt[10:12])
            
            dt = datetime(year, month, day, hour, minute, second)
            return dt.isoformat() + "Z"
        except:
            return compact_dt
    
    def _remove_empty_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归移除空值以减少数据大小
        """
        if isinstance(data, dict):
            return {
                k: self._remove_empty_values(v)
                for k, v in data.items()
                if v is not None and v != "" and v != {}
            }
        elif isinstance(data, list):
            return [self._remove_empty_values(item) for item in data if item is not None]
        else:
            return data
    
    def get_encoding_info(self, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取编码信息和压缩统计
        """
        original_json = json.dumps(original_data, ensure_ascii=False)
        original_size = len(original_json.encode('utf-8'))
        
        # 编码
        binary_data = self.encode(original_data)
        compressed_size = len(binary_data)
        
        # 计算压缩率
        compression_ratio = (1 - compressed_size / original_size) * 100
        
        return {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": f"{compression_ratio:.1f}%",
            "size_reduction": original_size - compressed_size,
            "encoding_version": self.version
        }


# 便捷函数
def encode_translation_data(data: Dict[str, Any]) -> bytes:
    """编码翻译数据"""
    encoder = CompactBinaryEncoder()
    return encoder.encode(data)


def decode_translation_data(binary_data: bytes) -> Dict[str, Any]:
    """解码翻译数据"""
    encoder = CompactBinaryEncoder()
    return encoder.decode(binary_data)


def get_compression_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """获取压缩统计信息"""
    encoder = CompactBinaryEncoder()
    return encoder.get_encoding_info(data)