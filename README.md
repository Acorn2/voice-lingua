# VoiceLingua - 语音转录与多语言翻译系统

VoiceLingua 是一个基于 FastAPI 和 OpenAI Whisper 的高性能语音转录与多语言翻译系统。支持音频文件转录、文本翻译，并提供 STT 准确性校验和多语言并行翻译功能。

## 🚀 核心功能

- **🎵 智能语音转录 (STT)**：使用 OpenAI Whisper 将音频文件转换为高质量文本
- **📝 准确性校验**：基于参考文本使用 Levenshtein 距离算法校验 STT 结果准确性
- **🌍 多语言翻译**：支持英语、简体中文、繁体中文、日语等多种语言的并行翻译
- **⚡ 异步任务处理**：使用 Celery + Redis 处理海量并发任务
- **📦 智能结果打包**：将多语言翻译结果打包为紧凑的 JSON 格式
- **🔍 快速查询**：支持按语言、文本编号和来源查询翻译结果
- **💾 可靠存储**：使用腾讯云COS存储文件，PostgreSQL存储元数据

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
**支持语言**：英语(en), 简体中文(zh), 繁体中文(zh-tw), 日语(ja), 韩语(ko), 法语(fr), 德语(de), 西班牙语(es), 意大利语(it), 俄语(ru)

## 📋 环境要求

- Python 3.9+
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose (可选)
- 腾讯云COS账号和密钥

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

### 3. 使用 Docker Compose 启动（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
```

### 4. 本地开发模式（推荐）

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

# 4. 启动 Celery Worker (新终端)
celery -A src.tasks.celery_app worker --loglevel=info --queues=transcription
celery -A src.tasks.celery_app worker --loglevel=info --queues=translation
celery -A src.tasks.celery_app worker --loglevel=info --queues=packaging
```

### 5. 云服务器配置

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

### 核心 API 端点

#### 1. 创建音频转录任务

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/audio" \
  -H "Content-Type: multipart/form-data" \
  -F "audio_file=@test.mp3" \
  -F "languages=en,zh,ja" \
  -F "reference_text=这是参考文本"
```

#### 2. 创建文本翻译任务

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/text" \
  -H "Content-Type: application/json" \
  -d '{
    "languages": ["en", "ja", "ko"],
    "text_content": "你好，这是一个测试文本。"
  }'
```

#### 3. 查询任务状态

```bash
curl "http://localhost:8000/api/v1/tasks/{task_id}"
```

#### 4. 查询翻译结果

```bash
curl "http://localhost:8000/api/v1/translations/{language}/{text_id}/{source}"
# 例如：
curl "http://localhost:8000/api/v1/translations/en/task-id-123/AUDIO"
```

#### 5. 取消任务

```bash
curl -X DELETE "http://localhost:8000/api/v1/tasks/{task_id}"
```

#### 6. 查询翻译引擎状态

```bash
curl "http://localhost:8000/api/v1/translation/engine/status"
```

### 响应示例

**任务创建成功**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2024-01-01T10:00:00Z",
  "languages": ["en", "zh", "ja"]
}
```

**任务状态查询**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2024-01-01T10:00:00Z",
  "languages": ["en", "zh", "ja"],
  "accuracy": 0.95,
  "result_url": "results/550e8400-e29b-41d4-a716-446655440000.json"
}
```

## 🔧 配置说明

### Whisper 配置

```bash
WHISPER_MODEL=medium        # tiny, base, small, medium, large
WHISPER_DEVICE=cuda         # cuda, cpu
WHISPER_LANGUAGE=zh         # 默认源语言
```

### 翻译模型配置

```bash
TRANSLATION_MODEL=facebook/m2m100_418M

# 翻译引擎选择 (local|qwen|mixed)
TRANSLATION_ENGINE=mixed
# local: 仅使用本地模型 (M2M100)
# qwen: 仅使用千问大模型
# mixed: 优先使用本地模型，失败时使用千问

# 千问大模型配置（可选）
QWEN_MODEL=qwen-plus
QWEN_API_KEY=your_qwen_api_key_here
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 系统限制配置

```bash
MAX_UPLOAD_SIZE=104857600   # 100MB
MEMORY_THRESHOLD=80.0       # 内存使用率阈值
MAX_CONCURRENT_TASKS=10     # 最大并发任务数
```

## 📊 监控和日志

### 日志查看

```bash
# API 服务日志
tail -f logs/voicelingua.log

# Docker 日志
docker-compose logs -f api
docker-compose logs -f worker-transcription
```

### 任务监控

```bash
# 查看 Celery 任务状态
celery -A src.tasks.celery_app inspect active
celery -A src.tasks.celery_app inspect stats
```

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

## 🐛 故障排除

### 常见问题

1. **模型下载缓慢**：
   ```bash
   # 预先下载 Whisper 模型
   python -c "import whisper; whisper.load_model('medium')"
   ```

2. **内存不足**：
   - 调整 `MEMORY_THRESHOLD` 参数
   - 使用更小的模型 (tiny, base)
   - 减少 Worker 并发数

3. **COS 连接失败**：
   - 检查 `TENCENT_SECRET_ID` 和 `TENCENT_SECRET_KEY`
   - 确认存储桶名称和地域正确

4. **任务卡住**：
   ```bash
   # 清理 Redis 队列
   redis-cli FLUSHDB
   
   # 重启 Worker
   docker-compose restart worker-transcription
   ```

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
  -F "languages=en,ja" \
  -F "reference_text=测试参考文本"

# 文本翻译
curl -X POST "http://localhost:8000/api/v1/tasks/text" \
  -H "Content-Type: application/json" \
  -d '{"languages": ["en", "ja"], "text_content": "你好世界"}'
```

### 常用命令

```bash
./start.sh          # 启动所有服务
./stop.sh            # 停止所有服务
./stop.sh status     # 检查服务状态
./start.sh logs      # 查看实时日志
./stop.sh clean      # 停止服务并清理文件
```

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 强大的语音识别模型
- [Hugging Face Transformers](https://github.com/huggingface/transformers) - 优秀的机器学习库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [Celery](https://docs.celeryproject.org/) - 分布式任务队列

---

**VoiceLingua** - 让语音无界，让沟通无限 🌍✨ 