#!/bin/bash
# 停止机器狗客户端

WORKSPACE_DIR="$HOME/sparkrobot"
LOGS_DIR="$WORKSPACE_DIR/logs/robot-chat"
PID_DIR="$WORKSPACE_DIR/logs/pid"
PID_FILE="$PID_DIR/robot-chat.pid"
PROCESS_NAME="robot_client.py"
STDOUT_LOG="$LOGS_DIR/client_stdout_$(date +'%Y%m%d').log"

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

if [ ! -f "$PID_FILE" ]; then
    log "未找到 PID 文件，客户端可能未运行。"
    exit 1
fi

PID=$(cat "$PID_FILE")

# 如果进程存在且名称匹配
if ps -p $PID -o args= | grep -q "$PROCESS_NAME"; then
    log "正在停止客户端 (PID: $PID)"
    kill $PID
    # 等待进程完全退出（最多等待5秒）
    for i in {1..5}; do
        if ! ps -p $PID > /dev/null; then break; fi
        sleep 1
    done
    # 如果还没强制退出，使用 kill -9
    if ps -p $PID > /dev/null; then
        log "进程未响应，强制关闭..."
        kill -9 $PID
    fi
    rm -f "$PID_FILE"
    log "客户端已停止。"
else
    log "发现 PID $PID 但不属于 $PROCESS_NAME，可能是陈旧的 PID 文件。"
    rm "$PID_FILE"
fi
