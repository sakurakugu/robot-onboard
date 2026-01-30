#!/bin/bash
# 后台运行机器狗客户端

# TODO: 改成ubuntu22的systemd服务，然后让这个脚本用于创建该服务（如果没有的话），然后启动该服务
# 服务名：robot-agent.service  # TODO: 到时候是用robot-agent还是robot-client
# 服务文件路径：/etc/systemd/system/robot-agent.service

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
cd ../src

# 定义路径
WORKSPACE_DIR="$HOME/sparkrobot"
LOGS_DIR="$WORKSPACE_DIR/logs/robot-agent"
PID_DIR="$WORKSPACE_DIR/logs/pid"
STDOUT_LOG="$LOGS_DIR/client_stdout_$(date +'%Y%m%d').log"

# 创建目录
mkdir -p "$LOGS_DIR"
mkdir -p "$PID_DIR"

log() {
    # 获取 ISO 格式时间戳
    local timestamp
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S%:z')
    timestamp=${timestamp//Z/+00:00}

    local msg="[$timestamp] $1"
    # echo 输出内容
    # | tee -a 追加到文件
    echo "$msg" | tee -a "$STDOUT_LOG"
}

# 启动程序
log "========================================"
log "    启动程序"
log "========================================"

# 检查是否已运行
PID_FILE="$PID_DIR/robot-agent.pid"
SCRIPT_NAME="main.py"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID -o args= | grep -q "$SCRIPT_NAME"; then
        log "客户端已在运行 (PID: $PID)"
        exit 1
    else
        log "清理陈旧的 PID 文件。"
        rm -f "$PID_FILE"
    fi
fi

# 防止 PID 文件丢失但进程仍在跑的情况
EXISTING_PID=$(pgrep -f "$SCRIPT_NAME")
if [ -n "$EXISTING_PID" ] && [ "$EXISTING_PID" != "$$" ]; then
    log "检测到已有同名进程运行中 (PID: $EXISTING_PID)，请先停止它。"
    exit 1
fi

# 后台运行
nohup python3 -u main.py >> "$STDOUT_LOG" 2>&1 &
PID=$!

sleep 1
if ps -p $PID > /dev/null; then
    echo $PID > "$PID_FILE"
    log "客户端已启动 (PID: $PID)"
    log "Python 业务日志: $LOGS_DIR/robot_client_$(date +'%Y%m%d').log"
    log "控制台日志: $STDOUT_LOG"
else
    log "启动失败，请检查日志: $LOGS_DIR/client_output.log"
    exit 1
fi
