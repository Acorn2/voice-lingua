#!/usr/bin/env python3
"""
结果解码工具 - 用于解码超紧凑二进制格式的翻译结果
"""
import os
import json
import argparse
from typing import Dict, Any
from src.utils.compact_encoder import decode_translation_data


def decode_result_file(file_path: str) -> Dict[str, Any]:
    """
    解码结果文件
    
    Args:
        file_path: 文件路径（支持 .bin 和 .json 格式）
        
    Returns:
        Dict[str, Any]: 解码后的数据
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.bin':
        # 解码二进制文件
        with open(file_path, 'rb') as f:
            binary_data = f.read()
        
        return decode_translation_data(binary_data)
    
    elif file_ext == '.json':
        # 直接读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    else:
        raise ValueError(f"不支持的文件格式: {file_ext}")


def save_decoded_result(data: Dict[str, Any], output_path: str):
    """
    保存解码后的结果为可读的JSON文件
    
    Args:
        data: 解码后的数据
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_result_summary(data: Dict[str, Any]):
    """
    打印结果摘要
    
    Args:
        data: 解码后的数据
    """
    print("=" * 60)
    print("翻译结果摘要")
    print("=" * 60)
    
    print(f"任务ID: {data.get('task_id', 'N/A')}")
    print(f"任务类型: {data.get('task_type', 'N/A')}")
    print(f"创建时间: {data.get('created_at', 'N/A')}")
    print(f"完成时间: {data.get('completed_at', 'N/A')}")
    print(f"准确性: {data.get('accuracy', 'N/A')}")
    print(f"文本编号: {data.get('text_number', 'N/A')}")
    print(f"编码版本: {data.get('version', 'N/A')}")
    
    translations = data.get('translations', {})
    if translations:
        print(f"\n支持的语言 ({len(translations)} 种):")
        for lang_code, lang_data in translations.items():
            sources = list(lang_data.keys())
            print(f"  - {lang_code}: {', '.join(sources)}")
    
    print("=" * 60)


def main():
    """命令行工具主函数"""
    parser = argparse.ArgumentParser(description="解码超紧凑二进制翻译结果文件")
    parser.add_argument("input_file", help="输入文件路径 (.bin 或 .json)")
    parser.add_argument("-o", "--output", help="输出JSON文件路径")
    parser.add_argument("-s", "--summary", action="store_true", help="显示结果摘要")
    parser.add_argument("-p", "--pretty", action="store_true", help="美化输出JSON")
    
    args = parser.parse_args()
    
    try:
        # 解码文件
        print(f"正在解码文件: {args.input_file}")
        data = decode_result_file(args.input_file)
        
        # 显示摘要
        if args.summary:
            print_result_summary(data)
        
        # 保存输出文件
        if args.output:
            save_decoded_result(data, args.output)
            print(f"解码结果已保存到: {args.output}")
        
        # 美化输出到控制台
        if args.pretty:
            print("\n解码结果:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        
        print("解码完成!")
        
    except Exception as e:
        print(f"解码失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())