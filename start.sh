#!/bin/bash

# VoiceLingua 本地启动脚本
# 用于在本地环境启动所有必要的服务
# PostgreSQL 和 Redis 使用云服务器，无需本地启动

set -e  # 遇到错误立即退出

# 检测并设置正确的 Python 执行器
PYTHON_CMD="python3"

# 如果在 zsh 中有 python3 alias，尝试获取真实路径
if [[ "$SHELL" == *"zsh"* ]] && type -a python3 2>/dev/null | grep -q "aliased"; then
    # 从 alias 获取真实路径
    PYTHON_CMD="/usr/local/opt/python@3.11/bin/python3.11"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif [[ -f "/usr/local/opt/python@3.11/bin/python3.11" ]]; then
    PYTHON_CMD="/usr/local/opt/python@3.11/bin/python3.11"
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 命令未找到，请先安装 $1"
        exit 1
    fi
}

# 检查端口是否被占用
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        log_warning "端口 $1 已被占用"
        return 1
    fi
    return 0
}

# 检查 Python 环境
check_python_env() {
    log_info "检查 Python 环境..."
    
    # 检查 Python 版本
    python_version=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    log_info "Python 版本: $python_version (使用: $PYTHON_CMD)"
    
    # 检查虚拟环境
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        log_warning "建议使用虚拟环境运行项目"
        read -p "是否继续？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "已取消启动"
            exit 0
        fi
    else
        log_success "虚拟环境: $VIRTUAL_ENV"
    fi
}

# 安装依赖
install_dependencies() {
    log_info "检查并安装 Python 依赖..."
    
    if [[ ! -f "requirements.txt" ]]; then
        log_error "requirements.txt 文件未找到"
        exit 1
    fi
    
    # 检查是否需要安装依赖
    if ! $PYTHON_CMD -c "import fastapi, celery, transformers, pydantic" >/dev/null 2>&1; then
        log_info "安装 Python 依赖包..."
        $PYTHON_CMD -m pip install -r requirements.txt
        log_success "依赖包安装完成"
    else
        log_success "Python 依赖包已安装"
    fi
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    directories=("uploads" "temp" "logs")
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_info "创建目录: $dir"
        fi
    done
    
    log_success "目录创建完成"
}

# 清理旧日志文件
clean_old_logs() {
    log_info "清理旧日志文件..."
    
    # 清理主要日志文件
    log_files=(
        "logs/api.log"
        "logs/worker-transcription.log"
        "logs/worker-translation.log"
        "logs/worker-packaging.log"
        "logs/voicelingua.log"
    )
    
    for log_file in "${log_files[@]}"; do
        if [[ -f "$log_file" ]]; then
            > "$log_file"  # 清空文件内容但保留文件
            log_info "清理日志文件: $log_file"
        fi
    done
    
    log_success "旧日志文件清理完成"
}

# 检查配置文件
check_config() {
    log_info "检查配置文件..."
    
    if [[ ! -f ".env" ]]; then
        if [[ -f "env.example" ]]; then
            log_warning ".env 文件不存在，从 env.example 复制..."
            cp env.example .env
            log_warning "请编辑 .env 文件，填入正确的配置信息"
            log_warning "重要配置项："
            echo "  - DATABASE_URL (PostgreSQL 云服务器地址)"
            echo "  - REDIS_URL (Redis 云服务器地址)"
            echo "  - TENCENT_SECRET_ID"
            echo "  - TENCENT_SECRET_KEY"
            echo "  - COS_BUCKET_NAME"
            echo "  - QWEN_API_KEY (如果使用千问大模型)"
            read -p "配置完成后按回车继续..."
        else
            log_error "配置文件不存在，请创建 .env 文件"
            exit 1
        fi
    else
        log_success "配置文件存在"
    fi
}

# 测试云服务连接
test_cloud_services() {
    log_info "测试云服务器连接..."
    
    # 测试 API 是否能正常启动（间接测试数据库和Redis连接）
    log_info "测试数据库和 Redis 连接..."
    
    # 使用独立的测试脚本进行连接测试
    log_info "运行详细连接测试..."
    if $PYTHON_CMD test_connection.py; then
        log_success "云服务器连接测试通过"
    else
        log_error "云服务器连接测试失败，请检查上面的详细错误信息"
        log_error "常见问题："
        echo "  1. 检查网络连接是否正常"
        echo "  2. 确认云服务器地址和端口正确"
        echo "  3. 验证用户名和密码正确"
        echo "  4. 检查防火墙设置"
        exit 1
    fi
}

# 启动 API 服务
start_api() {
    log_info "启动 FastAPI 服务..."
    
    if check_port 8000; then
        # 后台启动 API 服务
        nohup $PYTHON_CMD -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > logs/api.log 2>&1 &
        API_PID=$!
        echo $API_PID > .api.pid
        
        # 等待服务启动
        log_info "等待 API 服务启动..."
        sleep 5
        
        # 检查服务是否正常启动
        max_attempts=10
        attempt=0
        while [ $attempt -lt $max_attempts ]; do
            if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
                log_success "API 服务启动成功 (PID: $API_PID)"
                log_info "API 文档地址: http://localhost:8000/docs"
                break
            fi
            attempt=$((attempt + 1))
            echo -n "."
            sleep 1
        done
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "API 服务启动失败，请检查日志: logs/api.log"
            return 1
        fi
    else
        log_error "端口 8000 被占用，请先停止占用该端口的进程"
        return 1
    fi
}

# 启动 Celery Workers
start_workers() {
    log_info "启动 Celery Worker 进程..."
    
    # 启动转录任务 Worker (使用线程池避免 macOS fork 冲突)
    log_info "启动转录任务 Worker..."
    nohup celery -A src.tasks.celery_app worker --loglevel=info --queues=transcription --concurrency=1 --pool=threads > logs/worker-transcription.log 2>&1 &
    TRANSCRIPTION_PID=$!
    echo $TRANSCRIPTION_PID > .worker-transcription.pid
    
    # 启动翻译任务 Worker (使用线程池避免 macOS fork 冲突)
    log_info "启动翻译任务 Worker..."
    nohup celery -A src.tasks.celery_app worker --loglevel=info --queues=translation --concurrency=2 --pool=threads > logs/worker-translation.log 2>&1 &
    TRANSLATION_PID=$!
    echo $TRANSLATION_PID > .worker-translation.pid
    
    # 启动打包任务 Worker (使用线程池避免 macOS fork 冲突)
    log_info "启动打包任务 Worker..."
    nohup celery -A src.tasks.celery_app worker --loglevel=info --queues=packaging --concurrency=1 --pool=threads > logs/worker-packaging.log 2>&1 &
    PACKAGING_PID=$!
    echo $PACKAGING_PID > .worker-packaging.pid
    
    sleep 3
    log_success "Celery Workers 启动完成"
    log_info "转录 Worker PID: $TRANSCRIPTION_PID"
    log_info "翻译 Worker PID: $TRANSLATION_PID"
    log_info "打包 Worker PID: $PACKAGING_PID"
}

# 显示服务状态
show_status() {
    echo
    log_success "=== VoiceLingua 服务启动完成 ==="
    echo
    log_info "服务地址:"
    echo "  🌐 API 服务:        http://localhost:8000"
    echo "  📚 API 文档:        http://localhost:8000/docs"
    echo "  ❤️  健康检查:       http://localhost:8000/api/v1/health"
    echo "  🔧 翻译引擎状态:    http://localhost:8000/api/v1/translation/engine/status"
    echo
    log_info "日志文件:"
    echo "  📋 API 日志:        logs/api.log"
    echo "  🎵 转录日志:        logs/worker-transcription.log"
    echo "  🌍 翻译日志:        logs/worker-translation.log"
    echo "  📦 打包日志:        logs/worker-packaging.log"
    echo
    log_info "管理命令:"
    echo "  停止服务:          ./stop.sh"
    echo "  检查状态:          ./stop.sh status"
    echo "  查看日志:          ./start.sh logs"
    echo
}

# 主函数
main() {
    echo
    log_info "正在启动 VoiceLingua 语音转录与翻译系统..."
    log_info "使用云服务器上的 PostgreSQL 和 Redis"
    echo
    
    # 基础检查
    check_command "python3"
    check_command "curl"
    
    # 检查和准备环境
    check_python_env
    check_config
    create_directories
    clean_old_logs  # 清理旧日志文件
    install_dependencies
    
    # 测试云服务连接
    test_cloud_services
    
    # 启动本地服务
    start_api
    start_workers
    
    # 显示状态
    show_status
}

# 清理函数
cleanup() {
    log_warning "正在清理资源..."
    
    # 停止所有后台进程
    if [[ -f ".api.pid" ]]; then
        kill $(cat .api.pid) 2>/dev/null || true
        rm -f .api.pid
    fi
    
    if [[ -f ".worker-transcription.pid" ]]; then
        kill $(cat .worker-transcription.pid) 2>/dev/null || true
        rm -f .worker-transcription.pid
    fi
    
    if [[ -f ".worker-translation.pid" ]]; then
        kill $(cat .worker-translation.pid) 2>/dev/null || true
        rm -f .worker-translation.pid
    fi
    
    if [[ -f ".worker-packaging.pid" ]]; then
        kill $(cat .worker-packaging.pid) 2>/dev/null || true
        rm -f .worker-packaging.pid
    fi
    
    exit 0
}

# 注册信号处理
trap cleanup SIGINT SIGTERM

# 检查参数
case "${1:-}" in
    "stop")
        log_info "停止所有服务..."
        cleanup
        ;;
    "status")
        log_info "检查服务状态..."
        if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
            log_success "API 服务运行正常"
        else
            log_error "API 服务未运行"
        fi
        ;;
    "logs")
        log_info "显示实时日志..."
        tail -f logs/*.log
        ;;
    "test")
        log_info "测试云服务器连接..."
        check_config
        test_cloud_services
        ;;
    *)
        main
        ;;
esac 