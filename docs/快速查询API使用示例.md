# 快速查询 API 使用示例

## 概述

VoiceLingua 系统支持通过 **语言 -> 文本编号 -> 文本来源** 的方式快速查询翻译结果。文本编号从上传的文件名中自动提取。

## 文本编号提取规则

系统会从上传的文件名中自动提取编号作为文本编号：

| 文件名 | 提取的文本编号 |
|--------|----------------|
| `1.mp3` | `1` |
| `001.wav` | `001` |
| `text_123.txt` | `123` |
| `audio-456.m4a` | `456` |
| `file_name_789.mp3` | `789` |

## API 接口

### 1. 单个查询

**接口**: `GET /api/v1/translations/{language}/{text_number}/{source}`

**参数**:
- `language`: 目标语言 (en, zh, zh-tw, ja, ko, fr, de, es, it, ru)
- `text_number`: 文本编号 (从文件名提取)
- `source`: 来源类型 (AUDIO 或 TEXT)

**示例**:
```bash
# 查询编号为 "1" 的音频文件的英文翻译
curl "http://localhost:8000/api/v1/translations/en/1/AUDIO"

# 查询编号为 "123" 的文本文件的中文翻译
curl "http://localhost:8000/api/v1/translations/zh/123/TEXT"
```

**响应示例**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "en",
  "text_id": "1",
  "source": "AUDIO",
  "content": "Hello, this is a transcribed and translated text.",
  "accuracy": 0.95,
  "timestamp": "2024-01-01T10:02:15Z"
}
```

### 2. 批量查询

**接口**: `POST /api/v1/translations/batch`

**请求体**:
```json
[
  {"language": "en", "text_number": "1", "source": "AUDIO"},
  {"language": "zh", "text_number": "2", "source": "TEXT"},
  {"language": "ja", "text_number": "1", "source": "AUDIO"}
]
```

**示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/translations/batch" \
  -H "Content-Type: application/json" \
  -d '[
    {"language": "en", "text_number": "1", "source": "AUDIO"},
    {"language": "zh", "text_number": "1", "source": "AUDIO"}
  ]'
```

**响应示例**:
```json
[
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "en",
    "text_id": "1",
    "source": "AUDIO",
    "content": "Hello, this is a transcribed text.",
    "accuracy": 0.95,
    "timestamp": "2024-01-01T10:02:15Z"
  },
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "zh",
    "text_id": "1",
    "source": "AUDIO",
    "content": "你好，这是转录的文本。",
    "accuracy": 0.92,
    "timestamp": "2024-01-01T10:02:20Z"
  }
]
```

## 使用场景

### 场景1：音频文件处理
1. 上传音频文件 `1.mp3`
2. 系统自动提取文本编号 `1`
3. 完成转录和翻译后，可通过以下方式查询：
   - 英文翻译：`GET /api/v1/translations/en/1/AUDIO`
   - 中文翻译：`GET /api/v1/translations/zh/1/AUDIO`

### 场景2：文本文件处理
1. 上传文本内容（编号为 `123`）
2. 系统生成文本编号 `123`
3. 完成翻译后，可通过以下方式查询：
   - 日文翻译：`GET /api/v1/translations/ja/123/TEXT`
   - 韩文翻译：`GET /api/v1/translations/ko/123/TEXT`

### 场景3：批量查询
当需要获取多个文件的多种语言翻译时，使用批量查询接口可以显著提高效率。

## 错误处理

### 404 错误
```json
{
  "detail": "未找到文本编号 '1' 在语言 'en' 来源 'AUDIO' 的翻译结果"
}
```

### 400 错误
```json
{
  "detail": "无效的来源类型: INVALID"
}
```

## 性能优化

系统在 `translation_results` 表上创建了以下索引以提高查询性能：
- `idx_translation_results_text_number`
- `idx_translation_results_text_number_language_source`

这确保了即使在大量数据的情况下，查询仍然能够快速响应。