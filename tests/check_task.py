#!/usr/bin/env python3
"""
快速检查任务状态
"""
import sys
import os
# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import db_manager
from src.database.models import Task, TranslationResult

def check_latest_task():
    """检查最新的任务"""
    try:
        with db_manager.get_session() as db:
            # 查询最新的任务
            task = db.query(Task).order_by(Task.created_at.desc()).first()
            if not task:
                print("没有找到任务")
                return None
            
            # 查询翻译结果
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task.task_id
            ).all()
            
            print(f"最新任务信息:")
            print(f"  任务ID: {task.task_id}")
            print(f"  任务类型: {task.task_type}")
            print(f"  当前状态: {task.status}")
            print(f"  目标语言: {task.languages}")
            print(f"  翻译结果数量: {len(translations)}")
            print(f"  结果URL: {task.result_url}")
            print(f"  创建时间: {task.created_at}")
            print(f"  更新时间: {task.updated_at}")
            
            if task.text_content:
                print(f"  转录文本: {task.text_content}")
            
            # 显示翻译结果
            if translations:
                print(f"\n翻译结果:")
                for t in translations:
                    print(f"  - {t.target_language} ({t.source_type}): {t.translated_text[:50]}...")
            
            return str(task.task_id)
            
    except Exception as e:
        print(f"检查任务失败: {e}")
        return None

if __name__ == "__main__":
    task_id = check_latest_task()
    if task_id:
        print(f"\n要测试完整流程，请运行:")
        print(f"python tests/test_complete_flow.py {task_id}")