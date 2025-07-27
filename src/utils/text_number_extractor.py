"""
文本编号提取工具
从文件名中提取编号作为文本编号
"""
import re
import os
from typing import Optional


def extract_text_number_from_filename(filename: str) -> Optional[str]:
    """
    从文件名中提取文本编号
    
    支持的格式：
    - 1.mp3 -> "1"
    - 001.wav -> "001"
    - text_123.txt -> "123"
    - audio-456.m4a -> "456"
    - file_name_789.mp3 -> "789"
    
    Args:
        filename: 文件名（包含扩展名）
        
    Returns:
        str: 提取的文本编号，如果无法提取则返回None
    """
    if not filename:
        return None
    
    # 移除路径，只保留文件名
    filename = os.path.basename(filename)
    
    # 移除扩展名
    name_without_ext = os.path.splitext(filename)[0]
    
    # 尝试多种模式提取编号
    patterns = [
        r'^(\d+)$',                    # 纯数字：1, 001, 123
        r'^.*?(\d+)$',                 # 以数字结尾：text_123, audio-456
        r'^(\d+)_.*',                  # 以数字开头：123_text, 456-audio
        r'.*?_(\d+)_.*',               # 中间有数字：prefix_123_suffix
        r'.*?-(\d+)-.*',               # 用横线分隔：prefix-123-suffix
        r'.*?(\d+).*',                 # 包含数字：任何位置的数字
    ]
    
    for pattern in patterns:
        match = re.search(pattern, name_without_ext)
        if match:
            return match.group(1)
    
    # 如果都无法匹配，返回文件名本身（去除扩展名）
    return name_without_ext


def generate_text_number_from_task(task_id: str, language: str, source_type: str) -> str:
    """
    当无法从文件名提取编号时，生成一个基于任务的文本编号
    
    Args:
        task_id: 任务ID
        language: 目标语言
        source_type: 来源类型
        
    Returns:
        str: 生成的文本编号
    """
    # 使用任务ID的前8位 + 语言 + 来源类型
    short_task_id = str(task_id).replace('-', '')[:8]
    return f"{short_task_id}_{language}_{source_type}"


def extract_text_number_from_task(task, language: str, source_type: str) -> str:
    """
    从任务中提取文本编号
    
    Args:
        task: 任务对象
        language: 目标语言
        source_type: 来源类型 (AUDIO/TEXT)
        
    Returns:
        str: 文本编号
    """
    text_number = None
    
    # 优先使用存储在数据库中的 text_number
    if hasattr(task, 'text_number') and task.text_number:
        text_number = task.text_number
    # 如果没有存储的编号，尝试从文件路径提取（向后兼容）
    elif task.file_path:
        text_number = extract_text_number_from_filename(task.file_path)
    
    # 如果仍然无法获取，则生成一个
    if not text_number:
        text_number = generate_text_number_from_task(task.task_id, language, source_type)
    
    return text_number


# 测试函数
if __name__ == "__main__":
    test_files = [
        "1.mp3",
        "001.wav", 
        "text_123.txt",
        "audio-456.m4a",
        "file_name_789.mp3",
        "uploads/1227f646-b6d7-4b6e-8824-43ab4f0bed7d.mp3",
        "complex_file_name_999.wav",
        "no_number.txt"
    ]
    
    print("文件名编号提取测试：")
    for filename in test_files:
        number = extract_text_number_from_filename(filename)
        print(f"{filename} -> {number}")