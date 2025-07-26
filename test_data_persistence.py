#!/usr/bin/env python3
"""
测试数据持久性
验证重启服务后数据是否保持
"""
import uuid
from datetime import datetime
from src.database.connection import db_manager
from src.database.models import Task
from src.types.models import TaskStatus


def test_data_persistence():
    """测试数据持久性"""
    print("🧪 测试数据持久性...")
    
    # 创建测试任务
    test_task_id = str(uuid.uuid4())
    print(f"创建测试任务: {test_task_id}")
    
    db = db_manager.get_session()
    try:
        # 创建任务
        task = Task(
            task_id=test_task_id,
            task_type="test",
            status=TaskStatus.TRANSCRIPTION_PENDING.value,
            languages=["en", "zh"],
            text_content="This is a test task for data persistence"
        )
        
        db.add(task)
        db.commit()
        print("✅ 测试任务创建成功")
        
        # 查询任务
        found_task = db.query(Task).filter(Task.task_id == test_task_id).first()
        if found_task:
            print(f"✅ 任务查询成功: {found_task.text_content}")
            print(f"   创建时间: {found_task.created_at}")
            print(f"   状态: {found_task.status}")
        else:
            print("❌ 任务查询失败")
            return False
        
        # 更新任务
        found_task.status = TaskStatus.TRANSCRIPTION_COMPLETED.value
        found_task.updated_at = datetime.utcnow()
        db.commit()
        print("✅ 任务更新成功")
        
        # 再次查询验证更新
        updated_task = db.query(Task).filter(Task.task_id == test_task_id).first()
        if updated_task and updated_task.status == TaskStatus.TRANSCRIPTION_COMPLETED.value:
            print("✅ 任务更新验证成功")
        else:
            print("❌ 任务更新验证失败")
            return False
        
        print(f"\n📝 测试任务信息:")
        print(f"   任务ID: {updated_task.task_id}")
        print(f"   类型: {updated_task.task_type}")
        print(f"   状态: {updated_task.status}")
        print(f"   语言: {updated_task.languages}")
        print(f"   创建时间: {updated_task.created_at}")
        print(f"   更新时间: {updated_task.updated_at}")
        
        print(f"\n💡 提示: 现在可以重启服务，然后运行以下命令验证数据是否保持:")
        print(f"   python -c \"from src.database.connection import db_manager; from src.database.models import Task; db = db_manager.get_session(); task = db.query(Task).filter(Task.task_id == '{test_task_id}').first(); print('✅ 数据保持成功:', task.text_content if task else '❌ 数据丢失')\"")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    finally:
        db.close()


def cleanup_test_data():
    """清理测试数据"""
    print("🧹 清理测试数据...")
    
    db = db_manager.get_session()
    try:
        # 删除所有测试任务
        deleted_count = db.query(Task).filter(Task.task_type == "test").delete()
        db.commit()
        print(f"✅ 清理完成，删除了 {deleted_count} 个测试任务")
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup_test_data()
    else:
        test_data_persistence()