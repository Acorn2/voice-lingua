#!/usr/bin/env python3
"""
下载和解码任务结果示例
演示如何使用新的下载解码接口
"""
import requests
import json
import sys

def test_download_decode_api(base_url="http://localhost:8000", task_id=None):
    """
    测试下载和解码API接口
    
    Args:
        base_url: API服务器地址
        task_id: 任务ID，如果为None则使用示例ID
    """
    if not task_id:
        print("请提供一个有效的任务ID")
        print("用法: python download_decode_example.py <task_id>")
        return
    
    # 构建API URL
    api_url = f"{base_url}/api/v1/tasks/{task_id}/download"
    
    print(f"正在请求: {api_url}")
    print("=" * 60)
    
    try:
        # 发送请求
        response = requests.get(api_url, timeout=30)
        
        if response.status_code == 200:
            # 成功获取数据
            data = response.json()
            
            print("✅ 下载和解码成功!")
            print(f"任务ID: {data.get('task_id', 'N/A')}")
            print(f"任务类型: {data.get('task_type', 'N/A')}")
            print(f"创建时间: {data.get('created_at', 'N/A')}")
            print(f"完成时间: {data.get('completed_at', 'N/A')}")
            print(f"准确性: {data.get('accuracy', 'N/A')}")
            print(f"文本编号: {data.get('text_number', 'N/A')}")
            
            # 显示翻译结果统计
            translations = data.get('translations', {})
            if translations:
                print(f"\n翻译结果 ({len(translations)} 种语言):")
                for lang_code, lang_data in translations.items():
                    sources = list(lang_data.keys())
                    print(f"  - {lang_code}: {', '.join(sources)}")
            
            # 显示下载信息
            download_info = data.get('download_info', {})
            if download_info:
                print(f"\n下载信息:")
                print(f"  下载时间: {download_info.get('downloaded_at', 'N/A')}")
                print(f"  原始大小: {download_info.get('original_size', 'N/A')} bytes")
                print(f"  来源URL: {download_info.get('source_url', 'N/A')}")
                print(f"  编码版本: {download_info.get('encoding_version', 'N/A')}")
            
            # 保存完整结果到文件
            output_file = f"decoded_result_{task_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n完整结果已保存到: {output_file}")
            
        elif response.status_code == 404:
            error_data = response.json()
            print(f"❌ 任务不存在: {error_data.get('detail', '未知错误')}")
            
        elif response.status_code == 400:
            error_data = response.json()
            print(f"❌ 请求错误: {error_data.get('detail', '未知错误')}")
            
        else:
            print(f"❌ 请求失败 (状态码: {response.status_code})")
            try:
                error_data = response.json()
                print(f"错误详情: {error_data.get('detail', '未知错误')}")
            except:
                print(f"响应内容: {response.text}")
    
    except requests.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("下载和解码任务结果示例")
        print("=" * 40)
        print("用法: python download_decode_example.py <task_id>")
        print("")
        print("示例:")
        print("  python download_decode_example.py 9fa45ad0-a902-4319-b4d0-bd2b246dd46d")
        print("")
        print("该脚本会:")
        print("1. 调用 /api/v1/tasks/{task_id}/download 接口")
        print("2. 下载并解码压缩的结果文件")
        print("3. 显示解码后的翻译结果摘要")
        print("4. 保存完整结果到JSON文件")
        return 1
    
    task_id = sys.argv[1]
    test_download_decode_api(task_id=task_id)
    return 0


if __name__ == "__main__":
    exit(main())