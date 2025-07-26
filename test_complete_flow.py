#!/usr/bin/env python3
"""
测试完整的任务流程
"""
import sys
import os
import time
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import db_manager
from src.database.models import Task, TranslationResult
from src.tasks.translation_task import check_all_translations_completed
from src.tasks.packaging_task import package_results_task
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_task_progress(task_id: str):
    """检查任务进度"""
    try:
        with db_manager.get_session() as db:
            # 查询任务
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return None
            
            # 查询翻译结果
            translations = db.query(TranslationResult).filter(
                TranslationResult.task_id == task_id
            ).all()
            
            print(f"\n任务进度报告 - {task_id}")
            print("=" * 50)
            print(f"任务类型: {task.task_type}")
            print(f"当前状态: {task.status}")
            print(f"目标语言: {task.languages}")
            print(f"创建时间: {task.created_at}")
            print(f"更新时间: {task.updated_at}")
            print(f"完成时间: {task.completed_at}")
            print(f"结果URL: {task.result_url}")
            
            if task.text_content:
                print(f"转录文本: {task.text_content[:100]}...")
            
            if task.reference_text:
                print(f"参考文本: {task.reference_text[:100]}...")
            
            print(f"\n翻译结果数量: {len(translations)}")
            
            # 按语言分组显示翻译结果
            by_language = {}
            for t in translations:
                if t.target_language not in by_language:
                    by_language[t.target_language] = []
                by_language[t.target_language].append(t)
            
            for lang, results in by_language.items():
                print(f"\n{lang} ({len(results)} 个结果):")
                for r in results:
                    print(f"  - 来源: {r.source_type}")
                    print(f"    原文: {r.source_text[:50]}...")
                    print(f"    译文: {r.translated_text[:50]}...")
                    print(f"    置信度: {r.confidence}")
            
            # 计算期望的翻译数量
            expected_count = len(task.languages)
            if task.task_type == "audio" and task.reference_text and task.reference_text.strip():
                expected_count *= 2
            
            print(f"\n进度统计:")
            print(f"  期望翻译数量: {expected_count}")
            print(f"  实际翻译数量: {len(translations)}")
            print(f"  完成百分比: {len(translations)/expected_count*100:.1f}%")
            
            return task
            
    except Exception as e:
        logger.error(f"检查任务进度失败: {e}")
        return None

def trigger_packaging_manually(task_id: str):
    """手动触发打包任务"""
    try:
        logger.info(f"手动触发打包任务: {task_id}")
        result = package_results_task.delay(task_id)
        logger.info(f"打包任务已提交: {result.id}")
        
        # 等待任务完成
        timeout = 30  # 30秒超时
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if result.ready():
                if result.successful():
                    logger.info("打包任务完成成功")
                    return result.result
                else:
                    logger.error(f"打包任务失败: {result.result}")
                    return None
            time.sleep(1)
        
        logger.warning("打包任务超时")
        return None
        
    except Exception as e:
        logger.error(f"触发打包任务失败: {e}")
        return None

def check_result_file(task_id: str):
    """检查结果文件"""
    local_file = f"results/{task_id}.json"
    
    if os.path.exists(local_file):
        print(f"\n✅ 本地结果文件存在: {local_file}")
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"文件大小: {os.path.getsize(local_file)} 字节")
            print(f"任务ID: {data.get('task_id')}")
            print(f"任务类型: {data.get('task_type')}")
            print(f"源语言: {data.get('source_language')}")
            print(f"目标语言: {data.get('target_languages')}")
            print(f"翻译数量: {data.get('summary', {}).get('total_translations')}")
            print(f"完成语言: {data.get('summary', {}).get('languages_completed')}")
            
            return True
        except Exception as e:
            print(f"❌ 读取结果文件失败: {e}")
            return False
    else:
        print(f"❌ 本地结果文件不存在: {local_file}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python test_complete_flow.py <task_id>")
        print("示例: python test_complete_flow.py 27f5afee-6df8-4cb2-adea-af0a3137da90")
        sys.exit(1)
    
    task_id = sys.argv[1]
    
    print("VoiceLingua 完整流程测试")
    print("=" * 60)
    
    # 1. 检查任务进度
    task = check_task_progress(task_id)
    if not task:
        sys.exit(1)
    
    # 2. 如果任务状态是 translation_pending，检查翻译完成情况
    if task.status == 'translation_pending':
        print(f"\n任务状态为 translation_pending，检查是否可以触发打包...")
        if check_all_translations_completed(task_id):
            print("✅ 翻译已完成，打包任务已触发")
        else:
            print("⏳ 翻译尚未完成")
    
    # 3. 如果任务状态不是 packaging_completed，手动触发打包
    elif task.status != 'packaging_completed':
        print(f"\n任务状态为 {task.status}，尝试手动触发打包...")
        result = trigger_packaging_manually(task_id)
        if result:
            print("✅ 手动打包成功")
            print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print("❌ 手动打包失败")
    
    # 4. 检查结果文件
    print(f"\n检查结果文件...")
    check_result_file(task_id)
    
    # 5. 重新检查任务状态
    print(f"\n最终任务状态:")
    check_task_progress(task_id)
    
    print("\n" + "=" * 60)
    print("测试完成")