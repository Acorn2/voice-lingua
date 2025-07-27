# VoiceLingua - 语音转录与多语言翻译系统

VoiceLingua 是一个基于 FastAPI 和 OpenAI Whisper 的高性能语音转录与多语言翻译系统。支持音频文件转录、文本翻译，并提供 STT 准确性校验和多语言并行翻译功能。

## 🚀 核心功能

- **🎵 智能语音转录 (STT)**：使用 OpenAI Whisper 将音频文件转换为高质量文本
- **📝 准确性校验**：基于参考文本使用 Levenshtein 距离算法校验 STT 结果准确性
- **🌍 多语言翻译**：支持英语、简体中文、繁体中文、日语等10种语言的并行翻译
- **🤖 智能翻译引擎**：支持本地模型(M2M100)、千问大模型和混合模式
- **⚡ 异步任务处理**：使用 Celery + Redis 处理海量并发任务
- **📦 超紧凑编码**：使用二进制压缩技术，节省60-80%存储空间
- **🔍 快速查询**：支持按语言、文本编号和来源查询翻译结果
- **📄 文件上传支持**：支持音频文件和文本文件上传
- **💾 可靠存储**：使用腾讯云COS存储文件，PostgreSQL存储元数据
- **🔄 任务管理**：完整的任务生命周期管理，支持状态查询和取消操作

## 🏗️ 系统架构

```
用户请求 → FastAPI API → Celery 任务队列 → 并行处理
                ↓              ↓              ↓
           PostgreSQL ← Redis 消息队列 → 腾讯云COS存储
                ↓              ↓              ↓
        任务元数据管理 ← 任务状态跟踪 → 文件&结果存储
```

### 支持的格式和语言

**音频格式**：MP3, WAV, M4A, FLAC  
**文本格式**：TXT (支持UTF-8、GBK、GB2312等编码)  
**支持语言**：英语(en), 简体中文(zh), 繁体中文(zh-tw), 日语(ja), 韩语(ko), 法语(fr), 德语(de), 西班牙语(es), 意大利语(it), 俄语(ru)

### 翻译引擎

- **本地模型**：Facebook M2M100 (支持离线翻译)
- **云端模型**：阿里千问大模型 (更高质量)
- **混合模式**：优先本地，失败时使用云端

## 📋 环境要求

### 基础环境
- Python 3.9+ (推荐 3.11)
- PostgreSQL 14+ (支持云数据库)
- Redis 6+ (支持云Redis)
- Docker & Docker Compose (可选)

### 云服务依赖
- 腾讯云COS存储服务
- 阿里云千问大模型API (可选)

### 系统资源建议
- **内存**: 最低4GB，推荐8GB+
- **存储**: 最低10GB可用空间
- **CPU**: 支持多核并行处理
- **GPU**: 可选，用于Whisper加速 (CUDA支持)

### Python 依赖包
主要依赖包已在 `requirements.txt` 中定义：
- FastAPI 0.104.1 - Web框架
- Celery 5.3.4 - 异步任务队列
- OpenAI Whisper - 语音识别
- Transformers 4.35.2 - 机器学习模型
- SQLAlchemy 2.0.23 - 数据库ORM
- Redis 4.5.2+ - 缓存和消息队列

## 🛠️ 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/voice-lingua.git
cd voice-lingua
```

### 2. 环境配置

复制环境变量配置文件：

```bash
cp env.example .env
```

编辑 `.env` 文件，填入真实的配置值：

```bash
# 必填项
SECRET_KEY=your_super_secure_secret_key
DATABASE_URL=postgresql://postgres:password@localhost:5432/voicelingua
TENCENT_SECRET_ID=your_tencent_secret_id
TENCENT_SECRET_KEY=your_tencent_secret_key
COS_BUCKET_NAME=your_cos_bucket_name

# 可选项（开发环境推荐）
WHISPER_DEVICE=cpu  # Intel Mac 使用 cpu，生产环境使用 cuda
DEBUG=true
```

### 3. 数据库管理

系统提供了专门的数据库管理脚本，用于管理数据库表的创建和维护：

```bash
# 创建数据库表（如果不存在）
python src/database/manage_db.py create

# 测试数据库连接
python src/database/manage_db.py test

# 查看数据库信息
python src/database/manage_db.py info

# 强制重建数据库表（会删除所有数据，谨慎使用）
python src/database/manage_db.py recreate
```

**重要说明**：
- 系统现在会自动检查表是否存在，只在不存在时创建，避免数据丢失
- 如果需要重建表结构，请使用 `python src/database/manage_db.py recreate` 命令
- 生产环境建议将 `DEBUG=false` 以确保数据安全

### 4. 使用 Docker Compose 启动（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
```

### 5. 本地开发模式（推荐）

**系统架构**: 本地运行 API 和 Worker 服务，PostgreSQL 和 Redis 使用云服务器

使用一键启动脚本：

```bash
# 赋予脚本执行权限（首次运行）
chmod +x start.sh stop.sh test_connection.py

# 测试云服务器连接
python3 test_connection.py

# 启动所有服务
./start.sh

# 停止所有服务
./stop.sh

# 检查服务状态
./stop.sh status

# 查看实时日志
./stop.sh logs
```

或者手动启动：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 测试云服务器连接
python3 test_connection.py

# 3. 启动 API 服务
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 4. 启动 Celery Worker (新终端) - macOS 用户使用线程池避免 fork 冲突
celery -A src.tasks.celery_app worker --loglevel=info --queues=transcription --pool=threads
celery -A src.tasks.celery_app worker --loglevel=info --queues=translation --pool=threads
celery -A src.tasks.celery_app worker --loglevel=info --queues=packaging --pool=threads
```

### 6. macOS 用户特别说明

由于 macOS 系统与某些 Python 库（如 Whisper、PyTorch）存在 fork 冲突，推荐使用专门的启动方式：

```bash
# 推荐：使用专用的 macOS 启动脚本
chmod +x start-macos.sh
./start-macos.sh

# 或手动使用 solo 池模式
celery -A src.tasks.celery_app worker --loglevel=info --queues=transcription --pool=solo
celery -A src.tasks.celery_app worker --loglevel=info --queues=translation --pool=solo
celery -A src.tasks.celery_app worker --loglevel=info --queues=packaging --pool=solo
```

**注意**：
- solo 池模式每个队列只能处理一个并发任务
- 如果遇到 `objc[xxxxx]: +[NSMutableString initialize] may have been in progress in another thread when fork() was called` 错误，请使用上述方式
- macOS 启动脚本会自动处理 Python 路径和依赖问题

### 7. 云服务器配置

本项目使用云服务器运行 PostgreSQL 和 Redis，请在 `.env` 文件中配置：

```bash
# 云数据库配置
DATABASE_URL=postgresql://user:password@your-db-host:5432/voicelingua

# 云 Redis 配置
REDIS_URL=redis://your-redis-host:6379/0
REDIS_PASSWORD=your_redis_password  # 如果有密码

# Celery 队列配置（通常与 REDIS_URL 相同）
CELERY_BROKER_URL=redis://your-redis-host:6379/0
CELERY_RESULT_BACKEND=redis://your-redis-host:6379/1
```

## 📚 API 使用说明

### 基础信息

- **API 地址**：`http://localhost:8000`
- **文档地址**：`http://localhost:8000/docs`
- **健康检查**：`GET /api/v1/health`

### API 端点总览

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/health` | GET | 系统健康检查 |
| `/api/v1/tasks/audio` | POST | 创建音频转录任务 |
| `/api/v1/tasks/text` | POST | 创建文本翻译任务（JSON） |
| `/api/v1/tasks/text/upload` | POST | 创建文本翻译任务（文件上传） |
| `/api/v1/tasks/{task_id}` | GET | 查询任务状态 |
| `/api/v1/tasks/{task_id}` | DELETE | 取消任务 |
| `/api/v1/tasks/{task_id}/download` | GET | 下载并解码任务结果 |
| `/api/v1/translations/{lang}/{text_number}/{source}` | GET | 查询翻译结果 |
| `/api/v1/translations/batch` | POST | 批量查询翻译结果 |
| `/api/v1/translation/engine/status` | GET | 查询翻译引擎状态 |
| `/api/v1/encoding/demo` | GET | 紧凑编码格式演示 |

### 核心 API 端点

#### 1. 创建音频转录任务

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/audio" \
  -H "Content-Type: multipart/form-data" \
  -F "audio_file=@test.mp3" \
  -F "reference_text=这是参考文本"
```

#### 2. 创建文本翻译任务（JSON方式）

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text_content": "你好，这是一个测试文本。"
  }'
```

#### 3. 创建文本翻译任务（文件上传）

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/text/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "text_file=@sample.txt"

# 或直接传入文本内容
curl -X POST "http://localhost:8000/api/v1/tasks/text/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "text_content=你好，这是测试文本"
```

#### 4. 查询任务状态

```bash
curl "http://localhost:8000/api/v1/tasks/{task_id}"
```

#### 5. 查询翻译结果

```bash
curl "http://localhost:8000/api/v1/translations/{language}/{text_number}/{source}"
# 例如：
curl "http://localhost:8000/api/v1/translations/en/001/AUDIO"
curl "http://localhost:8000/api/v1/translations/zh/sample_123/TEXT"
```

#### 6. 批量查询翻译结果

```bash
curl -X POST "http://localhost:8000/api/v1/translations/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      {"language": "en", "text_number": "001", "source": "AUDIO"},
      {"language": "zh", "text_number": "002", "source": "TEXT"}
    ]
  }'
```

#### 7. 下载并解码任务结果

```bash
curl "http://localhost:8000/api/v1/tasks/{task_id}/download"
```

#### 8. 取消任务

```bash
curl -X DELETE "http://localhost:8000/api/v1/tasks/{task_id}"
```

#### 9. 查询翻译引擎状态

```bash
curl "http://localhost:8000/api/v1/translation/engine/status"
```

#### 10. 紧凑编码演示

```bash
curl "http://localhost:8000/api/v1/encoding/demo"
```

### 响应示例

**任务创建成功**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "transcription_pending",
  "created_at": "2025-01-27T10:00:00Z",
  "languages": ["en", "zh", "zh-tw", "ja", "ko", "fr", "de", "es", "it", "ru"]
}
```

**任务状态查询**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "packaging_completed",
  "created_at": "2025-01-27T10:00:00Z",
  "languages": ["en", "zh", "zh-tw", "ja", "ko", "fr", "de", "es", "it", "ru"],
  "accuracy": 0.95,
  "result_url": "results/550e8400-e29b-41d4-a716-446655440000.compact.bin"
}
```

**翻译结果查询**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "en",
  "text_id": "001",
  "source": "AUDIO",
  "content": "Hello, this is a transcribed text.",
  "accuracy": 0.95,
  "timestamp": "2025-01-27T10:02:15Z"
}
```

## 🔧 配置说明

### 核心配置

```bash
# 应用配置
DEBUG=false
SECRET_KEY=your_super_secure_secret_key

# 数据库配置
DATABASE_URL=postgresql://user:password@host:5432/voicelingua

# Redis 配置
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/0
CELERY_RESULT_BACKEND=redis://host:6379/1

# 腾讯云COS存储配置
TENCENT_SECRET_ID=your_secret_id
TENCENT_SECRET_KEY=your_secret_key
TENCENT_COS_REGION=ap-shanghai
COS_BUCKET_NAME=your_bucket_name
```

### Whisper 配置

```bash
WHISPER_MODEL=small         # tiny, base, small, medium, large
WHISPER_DEVICE=cuda         # cuda, cpu (macOS推荐cpu)
WHISPER_LANGUAGE=zh         # 默认源语言
```

### 翻译引擎配置

```bash
# 本地翻译模型
TRANSLATION_MODEL=facebook/m2m100_418M

# 翻译引擎选择 (local|qwen|mixed)
TRANSLATION_ENGINE=qwen
# local: 仅使用本地模型 (M2M100)
# qwen: 仅使用千问大模型
# mixed: 优先使用本地模型，失败时使用千问

# 千问大模型配置
QWEN_MODEL=qwen-plus
QWEN_API_KEY=your_qwen_api_key
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# 翻译参数
MAX_TRANSLATION_LENGTH=512
TRANSLATION_TIMEOUT=30
TRANSLATION_RETRY_COUNT=3
```

### 系统限制配置

```bash
MAX_UPLOAD_SIZE=104857600   # 100MB
MEMORY_THRESHOLD=80.0       # 内存使用率阈值
MAX_CONCURRENT_TASKS=10     # 最大并发任务数

# 支持的语言和格式
SUPPORTED_LANGUAGES=en,zh,zh-tw,ja,ko,fr,de,es,it,ru
SUPPORTED_AUDIO_FORMATS=.mp3,.wav,.m4a,.flac
```

## 📊 监控和日志

### 日志查看

```bash
# 查看所有日志
./start.sh logs

# 单独查看各服务日志
tail -f logs/api.log                    # API 服务日志
tail -f logs/worker-transcription.log   # 转录任务日志
tail -f logs/worker-translation.log     # 翻译任务日志
tail -f logs/worker-packaging.log       # 打包任务日志
tail -f logs/voicelingua.log            # 主应用日志

# Docker 日志
docker-compose logs -f api
docker-compose logs -f worker-transcription
docker-compose logs -f worker-translation
docker-compose logs -f worker-packaging
```

### 任务监控

```bash
# 查看 Celery 任务状态
celery -A src.tasks.celery_app inspect active
celery -A src.tasks.celery_app inspect stats
celery -A src.tasks.celery_app inspect registered

# 查看队列状态
celery -A src.tasks.celery_app inspect active_queues
```

### 健康检查

```bash
# 系统健康检查
curl http://localhost:8000/api/v1/health

# 翻译引擎状态
curl http://localhost:8000/api/v1/translation/engine/status
```

## 📈 性能指标

### 处理能力
- **音频转录**: 1分钟音频约需30-60秒处理时间
- **文本翻译**: 单个文本翻译约需1-3秒
- **并发处理**: 支持多任务并行处理
- **存储压缩**: 结果文件压缩率60-80%

### 系统吞吐量
- **API响应**: 平均响应时间 < 100ms
- **任务创建**: 支持每秒100+任务创建
- **查询性能**: 翻译结果查询 < 50ms
- **文件上传**: 支持最大100MB文件

## 🚀 生产部署

### GPU 环境配置

如果使用 GPU 加速，需要修改 `docker-compose.yml`：

```yaml
worker-transcription:
  # ... 其他配置
  environment:
    - WHISPER_DEVICE=cuda
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### 性能优化建议

1. **GPU 使用**：生产环境推荐使用 NVIDIA GPU 加速 Whisper 推理
2. **Worker 扩容**：根据负载调整 Celery Worker 数量
3. **数据库优化**：配置 PostgreSQL 连接池和索引
4. **缓存策略**：使用 Redis 缓存热点翻译结果
5. **负载均衡**：使用 Nginx 进行 API 负载均衡
6. **监控告警**：集成 Prometheus + Grafana 监控

### 扩展部署架构

```
Internet → Load Balancer → API Instances (N)
                              ↓
                         Message Queue (Redis Cluster)
                              ↓
                    Worker Nodes (Transcription/Translation/Packaging)
                              ↓
                    Database Cluster (PostgreSQL) + Object Storage (COS)
```

## 🐛 故障排除

### 常见问题

1. **模型下载缓慢**：
   ```bash
   # 预先下载 Whisper 模型
   python -c "import whisper; whisper.load_model('small')"
   
   # 预先下载翻译模型
   python -c "from transformers import M2M100ForConditionalGeneration; M2M100ForConditionalGeneration.from_pretrained('facebook/m2m100_418M')"
   ```

2. **macOS fork 冲突**：
   ```bash
   # 使用专用的 macOS 启动脚本
   ./start-macos.sh
   
   # 或使用 solo 池模式
   celery -A src.tasks.celery_app worker --pool=solo
   ```

3. **内存不足**：
   - 调整 `MEMORY_THRESHOLD` 参数
   - 使用更小的模型 (tiny, base)
   - 减少 Worker 并发数
   - 使用 `TRANSLATION_ENGINE=qwen` 避免本地模型内存占用

4. **COS 连接失败**：
   - 检查 `TENCENT_SECRET_ID` 和 `TENCENT_SECRET_KEY`
   - 确认存储桶名称和地域正确
   - 检查网络连接和防火墙设置

5. **任务卡住**：
   ```bash
   # 检查任务状态
   python tests/check_task.py <task_id>
   
   # 修复卡住的任务
   python tests/fix_stuck_task.py <task_id>
   
   # 清理 Redis 队列
   redis-cli -h <redis_host> -p 6379 FLUSHDB
   
   # 重启 Worker
   ./stop.sh && ./start.sh
   ```

6. **数据库连接问题**：
   ```bash
   # 测试数据库连接
   python src/database/manage_db.py test
   
   # 重建数据库表
   python src/database/manage_db.py recreate
   ```

7. **千问API调用失败**：
   - 检查 `QWEN_API_KEY` 是否正确
   - 确认API配额是否充足
   - 检查网络连接
   - 可以切换到 `TRANSLATION_ENGINE=local` 使用本地模型

## 🤝 开发贡献

欢迎提交 Issue 和 Pull Request！

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements.txt

# 代码格式化
black src/

# 类型检查
mypy src/

# 运行测试
pytest tests/
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## ⚡ 快速使用指南

### 第一次运行

```bash
# 1. 克隆项目
git clone https://github.com/your-username/voice-lingua.git
cd voice-lingua

# 2. 配置环境
cp env.example .env
# 编辑 .env 文件，填入必要配置

# 3. 一键启动
./start.sh
```

### 测试 API

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 上传音频文件进行转录和翻译
curl -X POST "http://localhost:8000/api/v1/tasks/audio" \
  -F "audio_file=@test.mp3" \
  -F "reference_text=测试参考文本"

# 文本翻译（JSON方式）
curl -X POST "http://localhost:8000/api/v1/tasks/text" \
  -H "Content-Type: application/json" \
  -d '{"text_content": "你好世界"}'

# 文本翻译（文件上传）
curl -X POST "http://localhost:8000/api/v1/tasks/text/upload" \
  -F "text_file=@sample.txt"

# 查询翻译结果
curl "http://localhost:8000/api/v1/translations/en/001/AUDIO"

# 下载解码结果
curl "http://localhost:8000/api/v1/tasks/{task_id}/download"
```

### 常用命令

```bash
./start.sh              # 启动所有服务
./start-macos.sh        # macOS 专用启动脚本
./stop.sh               # 停止所有服务
./stop.sh status        # 检查服务状态
./start.sh logs         # 查看实时日志
./stop.sh clean         # 停止服务并清理文件

# 数据库管理
python src/database/manage_db.py create    # 创建数据库表
python src/database/manage_db.py test      # 测试数据库连接

# 示例脚本
python examples/text_file_upload_example.py           # 文本文件上传示例
python examples/download_decode_example.py <task_id>  # 下载解码示例
python examples/compact_encoding_example.py           # 紧凑编码示例
```

## 🌟 核心特性详解

### 1. 超紧凑二进制编码

VoiceLingua 采用创新的二进制压缩技术，将翻译结果压缩至原始大小的20-40%：

- **消除冗余**：移除重复的源文本和时间戳
- **语言编码**：使用数字代码替代语言字符串
- **二进制压缩**：gzip压缩进一步减小文件大小
- **完整可恢复**：保持所有数据的完整性

```bash
# 查看编码演示
curl http://localhost:8000/api/v1/encoding/demo
```

### 2. 智能文本编号提取

系统自动从文件名提取文本编号，支持快速查询：

- `1.mp3` → 文本编号: `1`
- `sample_123.txt` → 文本编号: `123`
- `audio_test_001.wav` → 文本编号: `001`

### 3. 多引擎翻译支持

- **本地模型**：Facebook M2M100，支持离线翻译
- **云端模型**：阿里千问大模型，更高翻译质量
- **混合模式**：智能切换，确保服务可用性

### 4. 完整的任务生命周期

```
音频上传 → 转录处理 → 翻译处理 → 结果打包 → 存储上传
   ↓         ↓         ↓         ↓         ↓
pending → processing → translating → packaging → completed
```

### 5. 高性能查询接口

支持按 `语言 → 文本编号 → 来源` 的三级查询模式：

```bash
GET /api/v1/translations/{language}/{text_number}/{source}
```

## 📁 项目结构

```
VoiceLingua/
├── src/
│   ├── main.py                 # FastAPI 主应用
│   ├── config/                 # 配置管理
│   ├── database/               # 数据库模型和连接
│   ├── tasks/                  # Celery 异步任务
│   ├── types/                  # 数据模型定义
│   ├── utils/                  # 工具函数
│   └── services/               # 业务服务
├── docs/                       # 项目文档
├── examples/                   # 使用示例
├── tests/                      # 测试文件
├── logs/                       # 日志文件
├── uploads/                    # 上传文件目录
├── results/                    # 结果文件目录
├── start.sh                    # 启动脚本
├── start-macos.sh             # macOS 启动脚本
├── stop.sh                     # 停止脚本
└── docker-compose.yml          # Docker 配置
```

## 🧪 测试和示例

项目提供了完整的测试套件和使用示例：

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_complete_flow.py
pytest tests/test_compact_encoder.py
pytest tests/test_translation_flow.py
```

### 使用示例

```bash
# 文本文件上传示例
python examples/text_file_upload_example.py

# 下载解码示例
python examples/download_decode_example.py <task_id>

# 紧凑编码示例
python examples/compact_encoding_example.py
```

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 强大的语音识别模型
- [Hugging Face Transformers](https://github.com/huggingface/transformers) - 优秀的机器学习库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [Celery](https://docs.celeryproject.org/) - 分布式任务队列
- [阿里云千问](https://dashscope.aliyuncs.com/) - 高质量大语言模型

---

**VoiceLingua** - 让语音无界，让沟通无限 🌍✨ 