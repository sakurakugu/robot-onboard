#!/bin/bash

# Robot Server 停止脚本

set -e

# 定义路径
WORKSPACE_DIR="$HOME/sparkrobot"
PID_DIR="$WORKSPACE_DIR/logs/pid"
PID_FILE="$PID_DIR/robot-server.pid"
SCRIPT_NAME="server.py"
PROCESS_NAME="robot-server"
    
# 检查 PID 文件
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" -o comm= | grep -qx "$PROCESS_NAME"; then
        echo "正在停止 Robot Server (PID: $PID)..."
        kill $PID
        rm -f "$PID_FILE"
        echo "Robot Server 已停止"
        exit 0
    else
        echo "进程已不存在，清理 PID 文件"
        rm -f "$PID_FILE"
    fi
fi

# 尝试通过进程名查找
EXISTING_PID=$(pgrep -f "$PROCESS_NAME" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo "正在停止 Robot Server (PID: $EXISTING_PID)..."
    kill $EXISTING_PID
    echo "Robot Server 已停止"
else
    echo "Robot Server 未运行"
fi
