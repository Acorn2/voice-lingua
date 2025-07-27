# 下载解码API使用示例

## 概述

VoiceLingua系统提供了一个专门的接口用于下载并解码打包后的任务结果文件。该接口会自动从云存储或本地下载压缩的二进制文件，并解码为可读的JSON格式。

## API接口

### 下载并解码任务结果

**接口**: `GET /api/v1/tasks/{task_id}/download`

**参数**:
- `task_id`: 任务ID (路径参数)

**功能**:
1. 从数据库获取任务信息和result_url
2. 从云存储或本地下载压缩的二进制文件
3. 使用超紧凑二进制解码器解码文件
4. 返回完整的可读JSON格式翻译结果

## 使用示例

### 1. 基本使用

```bash
# 下载并解码任务结果
curl "http://localhost:8000/api/v1/tasks/9fa45ad0-a902-4319-b4d0-bd2b246dd46d/download"
```

### 2. 使用Python请求

```python
import requests
import json

# 任务ID
task_id = "9fa45ad0-a902-4319-b4d0-bd2b246dd46d"

# 发送请求
response = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}/download")

if response.status_code == 200:
    data = response.json()
    
    # 显示基本信息
    print(f"任务ID: {data['task_id']}")
    print(f"任务类型: {data['task_type']}")
    print(f"准确性: {data['accuracy']}")
    
    # 显示翻译结果
    translations = data['translations']
    print(f"支持语言: {list(translations.keys())}")
    
    # 保存到文件
    with open(f"result_{task_id}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
else:
    print(f"请求失败: {response.status_code}")
    print(response.json())
```

### 3. 使用示例脚本

```bash
# 使用提供的示例脚本
python examples/download_decode_example.py 9fa45ad0-a902-4319-b4d0-bd2b246dd46d
```

## 响应格式

### 成功响应 (200)

```json
{
  "task_id": "9fa45ad0",
  "task_type": "audio",
  "created_at": "2025-01-27T09:14:25Z",
  "completed_at": "2025-01-27T09:14:41Z",
  "accuracy": 0.803,
  "text_number": "1",
  "version": "1.0",
  "translations": {
    "en": {
      "AUDIO": {
        "translated_text": "Tilly, a little fox loved her bright red balloon...",
        "confidence": 0.95,
        "source_type": "AUDIO",
        "target_language": "en"
      },
      "TEXT": {
        "translated_text": "Tilly, a little fox, loved her bright red balloon...",
        "confidence": 0.98,
        "source_type": "TEXT",
        "target_language": "en"
      }
    },
    "zh": {
      "AUDIO": {
        "translated_text": "蒂莉，一只小狐狸喜欢她鲜红的气球...",
        "confidence": 0.92,
        "source_type": "AUDIO",
        "target_language": "zh"
      }
    }
  },
  "download_info": {
    "downloaded_at": "2025-01-27T10:30:00Z",
    "original_size": 687,
    "source_url": "https://cos.example.com/results/20250127/task.compact.bin",
    "encoding_version": "1.0"
  }
}
```

### 错误响应

#### 任务不存在 (404)
```json
{
  "detail": "任务不存在: invalid-task-id"
}
```

#### 任务未完成 (400)
```json
{
  "detail": "任务尚未完成打包，当前状态: translation_processing"
}
```

#### 结果文件不存在 (404)
```json
{
  "detail": "任务结果文件不存在"
}
```

#### 下载失败 (500)
```json
{
  "detail": "下载结果文件失败: Connection timeout"
}
```

#### 解码失败 (500)
```json
{
  "detail": "解码结果文件失败: Invalid binary format"
}
```

## 工作流程

### 1. 任务状态检查
- 验证任务是否存在
- 检查任务状态是否为 `packaging_completed`
- 确认 `result_url` 字段不为空

### 2. 文件下载
- **本地文件**: 如果 `result_url` 以 `file://` 开头，直接从本地读取
- **云存储文件**: 使用HTTP请求从云存储下载二进制文件

### 3. 数据解码
- 使用 `src/utils/compact_encoder.py` 中的 `decode_translation_data` 函数
- 自动处理gzip解压缩和JSON解析
- 还原完整的翻译结果结构

### 4. 响应增强
- 添加下载信息元数据
- 包含原始文件大小、下载时间等信息
- 保持完整的数据可追溯性

## 性能特点

### 压缩效果
- **原始JSON**: ~2KB
- **压缩二进制**: ~600B
- **网络传输**: 节省60-80%带宽

### 处理速度
- **下载时间**: 取决于网络和文件大小
- **解码时间**: 通常 < 10ms
- **总响应时间**: 通常 < 1秒

## 使用场景

### 1. 结果查看
```bash
# 快速查看任务的完整翻译结果
curl "http://localhost:8000/api/v1/tasks/{task_id}/download" | jq .
```

### 2. 数据导出
```python
# 批量导出多个任务的结果
task_ids = ["task1", "task2", "task3"]
for task_id in task_ids:
    response = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}/download")
    if response.status_code == 200:
        with open(f"export_{task_id}.json", 'w') as f:
            json.dump(response.json(), f, indent=2)
```

### 3. 数据分析
```python
# 分析翻译质量
response = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}/download")
data = response.json()

# 计算平均置信度
confidences = []
for lang, lang_data in data['translations'].items():
    for source, source_data in lang_data.items():
        if source_data.get('confidence'):
            confidences.append(source_data['confidence'])

avg_confidence = sum(confidences) / len(confidences)
print(f"平均翻译置信度: {avg_confidence:.3f}")
```

## 注意事项

### 1. 任务状态
- 只有状态为 `packaging_completed` 的任务才能下载
- 其他状态会返回400错误

### 2. 文件存储
- 支持本地文件 (`file://` 前缀) 和云存储URL
- 云存储文件需要有效的访问权限

### 3. 网络超时
- 云存储下载设置30秒超时
- 大文件可能需要更长时间

### 4. 内存使用
- 文件完全加载到内存中处理
- 超大文件可能影响性能

## 故障排除

### 1. 下载失败
```bash
# 检查任务状态
curl "http://localhost:8000/api/v1/tasks/{task_id}"

# 确认result_url是否有效
curl -I "{result_url}"
```

### 2. 解码失败
- 确认文件是使用超紧凑二进制编码器生成的
- 检查文件是否完整下载
- 验证编码版本兼容性

### 3. 性能问题
- 使用本地缓存避免重复下载
- 考虑异步处理大批量请求
- 监控内存使用情况

## 相关接口

- `GET /api/v1/tasks/{task_id}` - 查询任务状态
- `GET /api/v1/translations/{language}/{text_number}/{source}` - 快速查询特定翻译
- `POST /api/v1/translations/batch` - 批量查询翻译结果

这个接口为用户提供了一个便捷的方式来获取完整的、解码后的翻译结果，无需手动处理压缩文件的下载和解码过程。