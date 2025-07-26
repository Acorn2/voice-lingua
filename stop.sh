#!/bin/bash

# VoiceLingua 服务停止脚本
# 仅停止本地服务，PostgreSQL 和 Redis 在云服务器上

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

# 停止指定 PID 的进程
stop_process() {
    local pid_file=$1
    local service_name=$2
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止 $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null
            
            # 等待进程结束
            local count=0
            while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            # 如果进程仍然存在，强制终止
            if kill -0 "$pid" 2>/dev/null; then
                log_warning "强制终止 $service_name (PID: $pid)"
                kill -9 "$pid" 2>/dev/null
            fi
            
            log_success "$service_name 已停止"
        else
            log_warning "$service_name 进程不存在 (PID: $pid)"
        fi
        rm -f "$pid_file"
    else
        log_warning "$service_name PID 文件不存在: $pid_file"
    fi
}

# 停止所有本地服务
stop_all_services() {
    log_info "正在停止 VoiceLingua 本地服务..."
    log_info "注意：PostgreSQL 和 Redis 在云服务器上，无需停止"
    echo
    
    # 停止 API 服务
    stop_process ".api.pid" "API 服务"
    
    # 停止 Celery Workers
    stop_process ".worker-transcription.pid" "转录 Worker"
    stop_process ".worker-translation.pid" "翻译 Worker"
    stop_process ".worker-packaging.pid" "打包 Worker"
    
    echo
    log_success "所有本地服务已停止"
    log_info "云服务器上的 PostgreSQL 和 Redis 仍在运行"
}

# 停止特定服务
stop_specific_service() {
    case "$1" in
        "api")
            stop_process ".api.pid" "API 服务"
            ;;
        "workers")
            stop_process ".worker-transcription.pid" "转录 Worker"
            stop_process ".worker-translation.pid" "翻译 Worker"
            stop_process ".worker-packaging.pid" "打包 Worker"
            ;;
        "transcription")
            stop_process ".worker-transcription.pid" "转录 Worker"
            ;;
        "translation")
            stop_process ".worker-translation.pid" "翻译 Worker"
            ;;
        "packaging")
            stop_process ".worker-packaging.pid" "打包 Worker"
            ;;
        *)
            log_error "未知服务: $1"
            echo "可用的服务:"
            echo "  api           - API 服务"
            echo "  workers       - 所有 Worker"
            echo "  transcription - 转录 Worker"
            echo "  translation   - 翻译 Worker"
            echo "  packaging     - 打包 Worker"
            echo
            echo "注意：PostgreSQL 和 Redis 在云服务器上，不提供停止功能"
            exit 1
            ;;
    esac
}

# 检查服务状态
check_status() {
    log_info "检查本地服务状态..."
    echo
    
    # 检查 API 服务
    if [[ -f ".api.pid" ]]; then
        local api_pid=$(cat ".api.pid")
        if kill -0 "$api_pid" 2>/dev/null; then
            echo "✅ API 服务运行中 (PID: $api_pid)"
            
            # 测试 API 健康状态
            if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
                echo "   ├─ 健康检查: ✅ 正常"
            else
                echo "   ├─ 健康检查: ❌ 异常"
            fi
        else
            echo "❌ API 服务未运行"
        fi
    else
        echo "❌ API 服务未启动"
    fi
    
    # 检查 Worker 进程
    local workers=("transcription" "translation" "packaging")
    for worker in "${workers[@]}"; do
        local pid_file=".worker-${worker}.pid"
        if [[ -f "$pid_file" ]]; then
            local worker_pid=$(cat "$pid_file")
            if kill -0 "$worker_pid" 2>/dev/null; then
                echo "✅ ${worker^} Worker 运行中 (PID: $worker_pid)"
            else
                echo "❌ ${worker^} Worker 未运行"
            fi
        else
            echo "❌ ${worker^} Worker 未启动"
        fi
    done
    
    echo
    log_info "云服务器状态（通过 API 测试）:"
    
    # 通过 API 检查云服务器状态
    if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
        health_status=$(curl -s http://localhost:8000/api/v1/health 2>/dev/null)
        if echo "$health_status" | grep -q '"database":"healthy"' 2>/dev/null; then
            echo "✅ PostgreSQL 连接正常"
        else
            echo "❌ PostgreSQL 连接异常"
        fi
    else
        echo "❓ 无法检测云服务器状态（API 未运行）"
    fi
    
    # 检查翻译引擎状态
    if curl -f http://localhost:8000/api/v1/translation/engine/status >/dev/null 2>&1; then
        echo "✅ 翻译引擎状态正常"
    else
        echo "❓ 无法检测翻译引擎状态"
    fi
}

# 清理临时文件
cleanup_files() {
    log_info "清理临时文件..."
    
    # 清理 PID 文件
    rm -f .api.pid .worker-*.pid
    log_success "PID 文件已清理"
    
    # 询问是否清理日志文件
    if [[ -d "logs" ]] && [[ "$(ls -A logs 2>/dev/null)" ]]; then
        read -p "是否清理日志文件？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f logs/*.log
            log_success "日志文件已清理"
        fi
    fi
    
    # 询问是否清理上传文件
    if [[ -d "uploads" ]] && [[ "$(ls -A uploads 2>/dev/null)" ]]; then
        read -p "是否清理上传文件？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f uploads/*
            log_success "上传文件已清理"
        fi
    fi
    
    # 询问是否清理临时文件
    if [[ -d "temp" ]] && [[ "$(ls -A temp 2>/dev/null)" ]]; then
        read -p "是否清理临时文件？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f temp/*
            log_success "临时文件已清理"
        fi
    fi
}

# 显示日志
show_logs() {
    log_info "显示实时日志..."
    echo "按 Ctrl+C 退出"
    echo
    
    if [[ -f "logs/api.log" ]] || [[ -f "logs/worker-transcription.log" ]] || [[ -f "logs/worker-translation.log" ]] || [[ -f "logs/worker-packaging.log" ]]; then
        tail -f logs/*.log 2>/dev/null
    else
        log_warning "没有找到日志文件"
        log_info "请先启动服务: ./start.sh"
    fi
}

# 主函数
main() {
    case "${1:-all}" in
        "all"|"")
            stop_all_services
            ;;
        "status")
            check_status
            ;;
        "clean")
            stop_all_services
            cleanup_files
            ;;
        "logs")
            show_logs
            ;;
        *)
            stop_specific_service "$1"
            ;;
    esac
}

# 显示帮助信息
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "VoiceLingua 服务停止脚本"
    echo "仅管理本地服务，PostgreSQL 和 Redis 在云服务器上"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  (无参数)      停止所有本地服务"
    echo "  all           停止所有本地服务"
    echo "  api           仅停止 API 服务"
    echo "  workers       停止所有 Worker"
    echo "  transcription 仅停止转录 Worker"
    echo "  translation   仅停止翻译 Worker"
    echo "  packaging     仅停止打包 Worker"
    echo "  status        检查服务状态"
    echo "  logs          显示实时日志"
    echo "  clean         停止所有服务并清理文件"
    echo "  -h, --help    显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0              # 停止所有本地服务"
    echo "  $0 api          # 仅停止 API 服务"
    echo "  $0 status       # 检查服务状态"
    echo "  $0 logs         # 查看实时日志"
    echo "  $0 clean        # 停止服务并清理文件"
    echo
    echo "云服务器管理:"
    echo "  PostgreSQL 和 Redis 在云服务器上运行"
    echo "  请通过云服务器管理面板进行管理"
    exit 0
fi

# 执行主函数
main "$@" 