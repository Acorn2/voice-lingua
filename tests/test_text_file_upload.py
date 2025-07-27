#!/usr/bin/env python3
"""
测试文本文件上传功能
"""
import requests
import os
import tempfile

BASE_URL = "http://localhost:8000"

def create_test_file(content: str, filename: str) -> str:
    """创建测试文件"""
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path

def test_text_content_form():
    """测试通过表单传递文本内容"""
    print("测试通过表单传递文本内容...")
    
    data = {
        "text_content": "Hello, this is a test text for translation via form."
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/tasks/text/upload",
            data=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 表单文本任务创建成功:")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {result['languages']}")
            return result['task_id']
        else:
            print(f"❌ 表单文本任务创建失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def test_file_upload():
    """测试文件上传功能"""
    print("\n测试文件上传功能...")
    
    # 创建测试文件
    test_content = """This is a test file for translation.
It contains multiple lines of text.
The system should extract the text number from the filename.
Let's see how well it works!"""
    
    test_file_path = create_test_file(test_content, "123.txt")
    
    try:
        with open(test_file_path, 'rb') as f:
            files = {
                'text_file': ('123.txt', f, 'text/plain')
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/tasks/text/upload",
                files=files
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文件上传任务创建成功:")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {result['languages']}")
            return result['task_id']
        else:
            print(f"❌ 文件上传任务创建失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None
    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def test_json_api_compatibility():
    """测试原有JSON API的兼容性"""
    print("\n测试原有JSON API的兼容性...")
    
    data = {
        "text_content": "Hello, this is a test for JSON API compatibility."
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/tasks/text",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ JSON API任务创建成功:")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {result['languages']}")
            return result['task_id']
        else:
            print(f"❌ JSON API任务创建失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def test_error_cases():
    """测试错误情况"""
    print("\n测试错误情况...")
    
    # 测试1: 既不提供文本内容也不提供文件
    print("1. 测试不提供任何内容...")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/tasks/text/upload")
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"❌ 期望400错误，实际返回: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    # 测试2: 同时提供文本内容和文件
    print("2. 测试同时提供文本内容和文件...")
    test_file_path = create_test_file("test content", "test.txt")
    try:
        with open(test_file_path, 'rb') as f:
            files = {'text_file': ('test.txt', f, 'text/plain')}
            data = {'text_content': 'test text'}
            
            response = requests.post(
                f"{BASE_URL}/api/v1/tasks/text/upload",
                files=files,
                data=data
            )
        
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"❌ 期望400错误，实际返回: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
    
    # 测试3: 上传非txt文件
    print("3. 测试上传非txt文件...")
    test_file_path = create_test_file("test content", "test.doc")
    try:
        with open(test_file_path, 'rb') as f:
            files = {'text_file': ('test.doc', f, 'application/msword')}
            
            response = requests.post(
                f"{BASE_URL}/api/v1/tasks/text/upload",
                files=files
            )
        
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"❌ 期望400错误，实际返回: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def main():
    """主测试函数"""
    print("=== VoiceLingua 文本文件上传功能测试 ===\n")
    
    # 测试各种功能
    test_json_api_compatibility()
    test_text_content_form()
    test_file_upload()
    test_error_cases()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()