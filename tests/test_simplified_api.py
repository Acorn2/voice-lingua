#!/usr/bin/env python3
"""
测试简化后的 API 接口
"""
import requests
import json
import time
import os

# API 基础地址
BASE_URL = "http://localhost:8000"

def test_audio_task():
    """测试音频任务创建（不需要传递 languages 参数）"""
    print("测试音频任务创建...")
    
    # 准备测试文件（这里使用一个示例，实际需要真实的音频文件）
    files = {
        'audio_file': ('test.mp3', open('test.mp3', 'rb') if os.path.exists('test.mp3') else b'fake_audio_data', 'audio/mpeg')
    }
    
    data = {
        'reference_text': '这是一个测试音频文件'
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/tasks/audio", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 音频任务创建成功:")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {result['languages']}")
            return result['task_id']
        else:
            print(f"❌ 音频任务创建失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None
    finally:
        if 'audio_file' in files:
            files['audio_file'][1].close()


def test_text_task():
    """测试文本任务创建（不需要传递 languages 参数）"""
    print("测试文本任务创建...")
    
    data = {
        "text_content": "Hello, this is a test text for automatic translation to all supported languages."
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/tasks/text", 
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文本任务创建成功:")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {result['languages']}")
            return result['task_id']
        else:
            print(f"❌ 文本任务创建失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def test_task_status(task_id):
    """测试任务状态查询"""
    if not task_id:
        return
        
    print(f"查询任务状态: {task_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务状态查询成功:")
            print(f"   任务ID: {result['task_id']}")
            print(f"   状态: {result['status']}")
            print(f"   目标语言: {result['languages']}")
            if result.get('accuracy'):
                print(f"   准确度: {result['accuracy']}")
            if result.get('result_url'):
                print(f"   结果URL: {result['result_url']}")
        else:
            print(f"❌ 任务状态查询失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")


def test_health_check():
    """测试健康检查接口"""
    print("测试健康检查...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 健康检查成功:")
            print(f"   状态: {result['status']}")
            print(f"   版本: {result['version']}")
            print(f"   组件状态: {json.dumps(result['components'], indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("VoiceLingua 简化 API 测试")
    print("=" * 60)
    
    # 1. 健康检查
    test_health_check()
    print()
    
    # 2. 测试文本任务
    text_task_id = test_text_task()
    print()
    
    # 3. 测试音频任务（如果有测试文件）
    if os.path.exists('test.mp3'):
        audio_task_id = test_audio_task()
        print()
    else:
        print("⚠️  跳过音频任务测试（没有找到 test.mp3 文件）")
        audio_task_id = None
        print()
    
    # 4. 等待一段时间后查询任务状态
    if text_task_id or audio_task_id:
        print("等待 5 秒后查询任务状态...")
        time.sleep(5)
        
        if text_task_id:
            test_task_status(text_task_id)
            print()
            
        if audio_task_id:
            test_task_status(audio_task_id)
            print()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)