#!/usr/bin/env python3
"""
文本文件上传示例
演示如何使用 VoiceLingua 的文本文件上传功能
"""
import requests
import tempfile
import os
import time

BASE_URL = "http://localhost:8000"

def create_sample_file():
    """创建示例文本文件"""
    content = """Welcome to VoiceLingua!

This is a sample text file for translation testing.
The system will automatically:
1. Extract the text number from the filename
2. Translate the content to all supported languages
3. Store the results for quick retrieval

You can query the translation results using the text number extracted from this filename.

Thank you for using VoiceLingua!"""
    
    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "sample_001.txt")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"创建示例文件: {file_path}")
    print(f"文件内容长度: {len(content)} 字符")
    print(f"预期文本编号: 001")
    
    return file_path

def upload_text_file(file_path):
    """上传文本文件进行翻译"""
    print(f"\n上传文件: {os.path.basename(file_path)}")
    
    try:
        with open(file_path, 'rb') as f:
            files = {
                'text_file': (os.path.basename(file_path), f, 'text/plain')
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/tasks/text/upload",
                files=files
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文件上传成功!")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {', '.join(result['languages'])}")
            return result['task_id']
        else:
            print(f"❌ 上传失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 上传异常: {e}")
        return None

def check_task_status(task_id):
    """检查任务状态"""
    print(f"\n检查任务状态: {task_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   状态: {result['status']}")
            print(f"   创建时间: {result['created_at']}")
            if result.get('result_url'):
                print(f"   结果URL: {result['result_url']}")
            return result['status']
        else:
            print(f"❌ 查询失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return None

def query_translation_result(text_number, language="en"):
    """查询翻译结果"""
    print(f"\n查询翻译结果: 文本编号={text_number}, 语言={language}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/translations/{language}/{text_number}/TEXT"
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 查询成功!")
            print(f"   任务ID: {result['task_id']}")
            print(f"   语言: {result['language']}")
            print(f"   文本编号: {result['text_id']}")
            print(f"   来源: {result['source']}")
            print(f"   翻译内容: {result['content'][:100]}...")
            return result
        else:
            print(f"❌ 查询失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return None

def main():
    """主函数"""
    print("=== VoiceLingua 文本文件上传示例 ===\n")
    
    # 1. 创建示例文件
    file_path = create_sample_file()
    
    try:
        # 2. 上传文件
        task_id = upload_text_file(file_path)
        
        if not task_id:
            print("文件上传失败，退出示例")
            return
        
        # 3. 等待处理完成
        print("\n等待翻译处理...")
        max_wait_time = 120  # 最大等待2分钟
        wait_interval = 5    # 每5秒检查一次
        waited_time = 0
        
        while waited_time < max_wait_time:
            status = check_task_status(task_id)
            
            if status == "packaging_completed":
                print("✅ 任务处理完成!")
                break
            elif status and "failed" in status:
                print("❌ 任务处理失败!")
                return
            
            time.sleep(wait_interval)
            waited_time += wait_interval
            print(f"   等待中... ({waited_time}/{max_wait_time}秒)")
        
        if waited_time >= max_wait_time:
            print("⚠️  等待超时，但可以尝试查询结果")
        
        # 4. 查询翻译结果
        print("\n查询不同语言的翻译结果:")
        languages = ["en", "zh", "ja", "fr"]
        
        for lang in languages:
            query_translation_result("001", lang)
            time.sleep(1)  # 避免请求过快
        
        print("\n=== 示例完成 ===")
        print("你可以继续使用以下方式查询结果:")
        print(f"curl \"{BASE_URL}/api/v1/translations/zh/001/TEXT\"")
        
    finally:
        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"\n清理临时文件: {file_path}")

if __name__ == "__main__":
    main()