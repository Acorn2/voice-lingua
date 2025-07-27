#!/usr/bin/env python3
"""
测试下载解码API接口
"""
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from src.main import app
from src.database.models import Task, TaskStatus
from src.utils.compact_encoder import encode_translation_data


def create_test_data():
    """创建测试数据"""
    return {
        "task_id": "test-task-12345678",
        "task_type": "audio",
        "created_at": "2025-01-27T10:00:00Z",
        "completed_at": "2025-01-27T10:02:15Z",
        "accuracy": 0.95,
        "text_number": "123",
        "translations": {
            "en": {
                "AUDIO": {
                    "translated_text": "Hello, this is a test translation.",
                    "confidence": 0.95,
                    "source_type": "AUDIO",
                    "target_language": "en"
                }
            },
            "zh": {
                "AUDIO": {
                    "translated_text": "你好，这是一个测试翻译。",
                    "confidence": 0.92,
                    "source_type": "AUDIO",
                    "target_language": "zh"
                }
            }
        }
    }


def test_download_decode_api_success():
    """测试成功的下载解码"""
    print("=" * 60)
    print("测试成功的下载解码")
    print("=" * 60)
    
    client = TestClient(app)
    test_data = create_test_data()
    task_id = "test-task-12345678"
    
    # 编码测试数据
    binary_data = encode_translation_data(test_data)
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as temp_file:
        temp_file.write(binary_data)
        temp_file_path = temp_file.name
    
    try:
        # 模拟数据库查询
        with patch('src.main.db') as mock_db:
            mock_task = MagicMock()
            mock_task.task_id = task_id
            mock_task.status = TaskStatus.PACKAGING_COMPLETED.value
            mock_task.result_url = f"file://{temp_file_path}"
            
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            
            # 发送请求
            response = client.get(f"/api/v1/tasks/{task_id}/download")
            
            assert response.status_code == 200
            data = response.json()
            
            # 验证解码结果
            assert data["task_type"] == "audio"
            assert "translations" in data
            assert "en" in data["translations"]
            assert "zh" in data["translations"]
            assert "download_info" in data
            
            print("✅ 成功测试通过")
            print(f"任务类型: {data['task_type']}")
            print(f"翻译语言: {list(data['translations'].keys())}")
            print(f"下载信息: {data['download_info']['original_size']} bytes")
            
    finally:
        # 清理临时文件
        os.unlink(temp_file_path)


def test_download_decode_api_task_not_found():
    """测试任务不存在的情况"""
    print("\n" + "=" * 60)
    print("测试任务不存在的情况")
    print("=" * 60)
    
    client = TestClient(app)
    task_id = "non-existent-task"
    
    # 模拟数据库查询返回None
    with patch('src.main.db') as mock_db:
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.get(f"/api/v1/tasks/{task_id}/download")
        
        assert response.status_code == 404
        data = response.json()
        assert "任务不存在" in data["detail"]
        
        print("✅ 任务不存在测试通过")
        print(f"错误信息: {data['detail']}")


def test_download_decode_api_task_not_completed():
    """测试任务未完成的情况"""
    print("\n" + "=" * 60)
    print("测试任务未完成的情况")
    print("=" * 60)
    
    client = TestClient(app)
    task_id = "incomplete-task"
    
    # 模拟未完成的任务
    with patch('src.main.db') as mock_db:
        mock_task = MagicMock()
        mock_task.task_id = task_id
        mock_task.status = TaskStatus.TRANSLATION_PROCESSING.value
        mock_task.result_url = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task
        
        response = client.get(f"/api/v1/tasks/{task_id}/download")
        
        assert response.status_code == 400
        data = response.json()
        assert "尚未完成打包" in data["detail"]
        
        print("✅ 任务未完成测试通过")
        print(f"错误信息: {data['detail']}")


def test_download_decode_api_cloud_storage():
    """测试云存储文件下载"""
    print("\n" + "=" * 60)
    print("测试云存储文件下载")
    print("=" * 60)
    
    client = TestClient(app)
    test_data = create_test_data()
    task_id = "cloud-task-12345678"
    
    # 编码测试数据
    binary_data = encode_translation_data(test_data)
    
    # 模拟云存储响应
    with patch('src.main.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = binary_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # 模拟数据库查询
        with patch('src.main.db') as mock_db:
            mock_task = MagicMock()
            mock_task.task_id = task_id
            mock_task.status = TaskStatus.PACKAGING_COMPLETED.value
            mock_task.result_url = "https://example.com/results/task.bin"
            
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            
            # 发送请求
            response = client.get(f"/api/v1/tasks/{task_id}/download")
            
            assert response.status_code == 200
            data = response.json()
            
            # 验证结果
            assert data["task_type"] == "audio"
            assert "download_info" in data
            assert data["download_info"]["source_url"] == "https://example.com/results/task.bin"
            
            print("✅ 云存储下载测试通过")
            print(f"来源URL: {data['download_info']['source_url']}")


def main():
    """运行所有测试"""
    print("开始测试下载解码API接口")
    print("=" * 60)
    
    tests = [
        test_download_decode_api_success,
        test_download_decode_api_task_not_found,
        test_download_decode_api_task_not_completed,
        test_download_decode_api_cloud_storage
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
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